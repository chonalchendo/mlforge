import warnings
from pathlib import Path

import polars as pl

import mlforge.store as store_
import mlforge.utils as utils


def get_training_data(
    features: list[str],
    entity_df: pl.DataFrame,
    store: str | Path | store_.Store = "./feature_store",
    entities: list[utils.EntityKeyTransform] | None = None,
    timestamp: str | None = None,
) -> pl.DataFrame:
    """
    Retrieve features and join to an entity DataFrame.

    Args:
        features: Feature names to retrieve
        entity_df: DataFrame with entity keys to join on
        store: Path to feature store or Store instance
        entities: Entity key transforms to apply to entity_df before joining
        timestamp: Column in entity_df to use for point-in-time joins.
                   If provided, features with timestamps will be asof-joined.

    Returns:
        entity_df with feature columns joined

    Example:
        from mlforge import get_training_data
        from transactions.entities import with_user_id

        transactions = pl.read_parquet("data/transactions.parquet")

        # Point-in-time correct training data
        training_df = get_training_data(
            features=["user_spend_mean_30d"],
            entity_df=transactions,
            entities=[with_user_id],
            timestamp="trans_date_trans_time",
        )
    """
    if isinstance(store, (str, Path)):
        store = store_.LocalStore(path=store)

    result = entity_df

    # Apply entity key transforms
    for entity_fn in entities or []:
        if not hasattr(entity_fn, "_entity_key_columns"):
            raise ValueError(
                f"Entity transform '{entity_fn.__name__}' is missing metadata. "
                f"Use mlforge.entity_key() to create entity transforms."
            )

        required_columns = entity_fn._entity_key_columns
        missing_columns = [c for c in required_columns if c not in result.columns]

        if missing_columns:
            raise ValueError(
                f"Entity '{entity_fn._entity_key_alias}' requires columns {list(required_columns)}, "
                f"but entity_df is missing: {missing_columns}"
            )

        result = result.pipe(entity_fn)

    for feature_name in features:
        if not store.exists(feature_name):
            raise ValueError(
                f"Feature '{feature_name}' not found. Run `mlforge build` first."
            )

        feature_df = store.read(feature_name)
        join_keys = list(set(result.columns) & set(feature_df.columns))

        # Remove timestamp columns from join keys—they're handled separately
        if timestamp:
            join_keys = [k for k in join_keys if k != timestamp]

        if not join_keys:
            raise ValueError(
                f"No common columns to join '{feature_name}'. "
                f"entity_df has: {result.columns}, feature has: {feature_df.columns}"
            )

        # Determine join strategy
        feature_timestamp = _get_feature_timestamp(feature_df)

        if timestamp and feature_timestamp:
            # Point-in-time join
            result = _asof_join(
                left=result,
                right=feature_df,
                on_keys=join_keys,
                left_timestamp=timestamp,
                right_timestamp=feature_timestamp,
            )
        else:
            # Standard join
            result = result.join(feature_df, on=join_keys, how="left")

    return result


def _get_feature_timestamp(df: pl.DataFrame) -> str | None:
    """
    Detect timestamp column in feature DataFrame.

    Uses convention-based detection: looks for 'feature_timestamp' column
    first, then falls back to any single datetime/date column.

    Args:
        df: Feature DataFrame to inspect

    Returns:
        Name of timestamp column, or None if no timestamp detected
    """
    # Convention: look for 'feature_timestamp' or any datetime column
    if "feature_timestamp" in df.columns:
        return "feature_timestamp"

    datetime_cols = [
        col
        for col, dtype in zip(df.columns, df.dtypes)
        if dtype in [pl.Datetime, pl.Date]
    ]

    # If exactly one datetime column (besides potential keys), use it
    if len(datetime_cols) == 1:
        return datetime_cols[0]

    return None


def _asof_join(
    left: pl.DataFrame,
    right: pl.DataFrame,
    on_keys: list[str],
    left_timestamp: str,
    right_timestamp: str,
) -> pl.DataFrame:
    """
    Perform a point-in-time correct asof join.

    Joins feature data to entity data using backward-looking temporal joins,
    ensuring features are computed only from data available at event time.

    Args:
        left: Entity DataFrame (e.g., transactions, predictions)
        right: Feature DataFrame with temporal features
        on_keys: Entity key columns to join on
        left_timestamp: Timestamp column in entity DataFrame
        right_timestamp: Timestamp column in feature DataFrame

    Returns:
        Entity DataFrame with features joined point-in-time correctly

    Raises:
        ValueError: If timestamp columns have mismatched data types
    """

    left_dtype = left.schema[left_timestamp]
    right_dtype = right.schema[right_timestamp]

    if left_dtype != right_dtype:
        raise ValueError(
            f"Timestamp dtype mismatch: entity_df['{left_timestamp}'] is {left_dtype}, "
            f"but feature has {right_dtype}. "
            f"Convert entity_df timestamp to datetime before calling get_training_data()."
        )

    left_sorted = left.sort(left_timestamp)
    right_sorted = right.sort(right_timestamp)

    right_renamed = right_sorted.rename({right_timestamp: f"__{right_timestamp}"})

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Sortedness of columns cannot be checked",
            category=UserWarning,
        )
        result = left_sorted.join_asof(
            right_renamed,
            left_on=left_timestamp,
            right_on=f"__{right_timestamp}",
            by=on_keys,
            strategy="backward",
        )

    result = result.drop(f"__{right_timestamp}")

    return result
