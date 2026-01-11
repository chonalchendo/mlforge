"""
Feature retrieval functions for training and inference.

This module provides two main functions for retrieving features:

- get_training_data(): Retrieve features from offline stores for training.
  Supports versioning and point-in-time correct joins.

- get_online_features(): Retrieve features from online stores for inference.
  Returns latest values with low-latency key lookups.

Example (training):
    import mlforge as mlf

    user = mlf.Entity(
        name="user",
        join_key="user_id",
        from_columns=["first", "last", "dob"],
    )

    training_df = mlf.get_training_data(
        features=["user_spend", ("merchant_risk", "1.0.0")],
        entity_df=transactions,
        store=mlf.LocalStore("./feature_store"),
        entities=[user],
        timestamp="event_time",
    )

Example (inference):
    import mlforge as mlf

    user = mlf.Entity(
        name="user",
        join_key="user_id",
        from_columns=["first", "last", "dob"],
    )

    features_df = mlf.get_online_features(
        features=["user_spend", "merchant_risk"],
        entity_df=request_df,
        store=mlf.RedisStore(host="localhost"),
        entities=[user],
    )
"""

import warnings
from pathlib import Path

import polars as pl

import mlforge.entities as entities_
import mlforge.online as online_
import mlforge.store as store_
import mlforge.types as types_
import mlforge.utils as utils

# Type alias for feature specification: "feature_name" or ("feature_name", "1.0.0")
FeatureSpec = str | tuple[str, str]


def get_training_data(
    features: list[FeatureSpec],
    entity_df: pl.DataFrame,
    store: str | Path | store_.Store = "./feature_store",
    entities: list[entities_.Entity] | None = None,
    timestamp: str | None = None,
) -> pl.DataFrame:
    """
    Retrieve features and join to an entity DataFrame.

    Args:
        features: Feature specifications. Can be:
            - "feature_name" - uses latest version
            - ("feature_name", "1.0.0") - uses specific version
        entity_df: DataFrame with entity keys to join on
        store: Path to feature store or Store instance
        entities: Entity definitions for key generation/validation.
            When an entity has from_columns, a surrogate key is generated.
            Otherwise, validates that join_key columns exist.
        timestamp: Column in entity_df to use for point-in-time joins.
                   If provided, features with timestamps will be asof-joined.

    Returns:
        entity_df with feature columns joined

    Example:
        import mlforge as mlf

        user = mlf.Entity(
            name="user",
            join_key="user_id",
            from_columns=["first", "last", "dob"],
        )

        transactions = pl.read_parquet("data/transactions.parquet")

        # Point-in-time correct training data with mixed versions
        training_df = mlf.get_training_data(
            features=[
                "user_spend_mean_30d",              # latest version
                ("merchant_features", "1.0.0"),    # pinned version
            ],
            entity_df=transactions,
            entities=[user],
            timestamp="trans_date_trans_time",
        )
    """
    if isinstance(store, (str, Path)):
        store = store_.LocalStore(path=store)

    result = _apply_entities(entity_df, entities)

    for feature_spec in features:
        # Parse feature specification
        if isinstance(feature_spec, tuple):
            feature_name, feature_version = feature_spec
        else:
            feature_name = feature_spec
            feature_version = None  # Use latest

        if not store.exists(feature_name, feature_version):
            version_str = (
                f" version '{feature_version}'" if feature_version else ""
            )
            raise ValueError(
                f"Feature '{feature_name}'{version_str} not found. Run `mlforge build` first."
            )

        feature_df = store.read(feature_name, feature_version)
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

    Uses canonical types for consistent detection across engines.

    Args:
        df: Feature DataFrame to inspect

    Returns:
        Name of timestamp column, or None if no timestamp detected
    """
    # Convention: look for 'feature_timestamp' or any datetime column
    if "feature_timestamp" in df.columns:
        return "feature_timestamp"

    # Use canonical types for consistent temporal detection
    datetime_cols = [
        col
        for col, dtype in zip(df.columns, df.dtypes)
        if types_.from_polars(dtype).is_temporal()
        and types_.from_polars(dtype).kind
        in (types_.TypeKind.DATETIME, types_.TypeKind.DATE)
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

    Uses canonical types for comparison to ensure consistent behavior
    across different engines (Polars, DuckDB).

    Args:
        left: Entity DataFrame (e.g., transactions, predictions)
        right: Feature DataFrame with temporal features
        on_keys: Entity key columns to join on
        left_timestamp: Timestamp column in entity DataFrame
        right_timestamp: Timestamp column in feature DataFrame

    Returns:
        Entity DataFrame with features joined point-in-time correctly

    Raises:
        ValueError: If timestamp columns have incompatible canonical types
    """
    left_dtype = left.schema[left_timestamp]
    right_dtype = right.schema[right_timestamp]

    # Use canonical types for comparison to handle cross-engine type differences
    left_canonical = types_.from_polars(left_dtype)
    right_canonical = types_.from_polars(right_dtype)

    # Compare canonical types (ignoring timezone differences for now)
    if left_canonical.kind != right_canonical.kind:
        raise ValueError(
            f"Timestamp dtype mismatch: entity_df['{left_timestamp}'] is {left_canonical.to_canonical_string()}, "
            f"but feature has {right_canonical.to_canonical_string()}. "
            f"Convert entity_df timestamp to datetime before calling get_training_data()."
        )

    left_sorted = left.sort(left_timestamp)
    right_sorted = right.sort(right_timestamp)

    right_renamed = right_sorted.rename(
        {right_timestamp: f"__{right_timestamp}"}
    )

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


def get_online_features(
    features: list[str],
    entity_df: pl.DataFrame,
    store: online_.OnlineStore,
    entities: list[entities_.Entity] | None = None,
) -> pl.DataFrame:
    """
    Retrieve features from an online store for inference.

    Unlike get_training_data(), this function:
    - Always returns latest values (no point-in-time joins)
    - Does not support versioning (online stores hold latest only)
    - Uses direct key lookups instead of DataFrame joins

    Note:
        For retrieving multiple features with different entities (e.g., user_spend
        and merchant_spend), use Definitions.get_online_features() instead. It
        automatically determines the correct entity keys for each feature, avoiding
        the common error of entity key mismatches.

    Args:
        features: List of feature names to retrieve
        entity_df: DataFrame with entity keys (e.g., inference requests)
        store: Online store instance (e.g., RedisStore)
        entities: Entity definitions for key generation/validation.
            When an entity has from_columns, a surrogate key is generated.
            Otherwise, validates that join_key columns exist.
            Important: All features will use ALL entity keys for lookup.
            For multi-entity scenarios, use Definitions.get_online_features().

    Returns:
        entity_df with feature columns joined (None for missing entities)

    Example:
        import mlforge as mlf

        user = mlf.Entity(
            name="user",
            join_key="user_id",
            from_columns=["first", "last", "dob"],
        )

        store = mlf.RedisStore(host="localhost")
        request_df = pl.DataFrame({
            "first": ["John", "Jane"],
            "last": ["Doe", "Smith"],
            "dob": ["1990-01-01", "1985-06-20"],
        })

        features_df = mlf.get_online_features(
            features=["user_spend"],
            entity_df=request_df,
            entities=[user],
            store=store,
        )

        # For multiple features with different entities, prefer:
        # result = defs.get_online_features(
        #     features=["user_spend", "merchant_spend"],
        #     entity_df=request_df,
        # )
    """
    result = _apply_entities(entity_df, entities)

    # Retrieve each feature and join to result
    for feature_name in features:
        result = _join_online_feature(result, feature_name, store, entities)

    return result


def _apply_entities(
    df: pl.DataFrame,
    entities: list[entities_.Entity] | None,
) -> pl.DataFrame:
    """
    Apply entity key generation and validation.

    For entities with from_columns: validates source columns exist,
    then generates surrogate key using utils.surrogate_key().

    For entities without from_columns: validates join_key columns exist.

    Args:
        df: DataFrame to transform
        entities: List of entity definitions

    Returns:
        DataFrame with surrogate key columns added (where needed)

    Raises:
        ValueError: If required columns are missing
    """
    result = df

    for entity in entities or []:
        if entity.requires_generation and entity.from_columns is not None:
            from_columns = entity.from_columns

            # Validate source columns exist
            missing = [c for c in from_columns if c not in result.columns]
            if missing:
                raise ValueError(
                    f"Entity '{entity.name}' requires columns "
                    f"{list(from_columns)}, "
                    f"but entity_df is missing: {missing}"
                )
            # Generate surrogate key
            result = result.with_columns(
                utils.surrogate_key(*from_columns).alias(entity.join_key)
            )
        else:
            # Validate join key columns exist
            missing = [c for c in entity.key_columns if c not in result.columns]
            if missing:
                raise ValueError(
                    f"Entity '{entity.name}' requires columns "
                    f"{entity.key_columns}, "
                    f"but entity_df is missing: {missing}"
                )

    return result


def _join_online_feature(
    result: pl.DataFrame,
    feature_name: str,
    store: online_.OnlineStore,
    entities: list[entities_.Entity] | None,
) -> pl.DataFrame:
    """
    Retrieve a single feature from online store and join to result.

    Determines entity key columns from the entity transforms, extracts
    unique entity combinations, batch-reads from the store, and joins
    the feature values back to the result DataFrame.

    Args:
        result: Current result DataFrame
        feature_name: Name of feature to retrieve
        store: Online store instance
        entities: Entity transforms (used to determine key columns)

    Returns:
        Result DataFrame with feature columns joined
    """
    # Determine entity key columns from transforms
    entity_key_columns = _get_entity_key_columns(entities)

    if not entity_key_columns:
        raise ValueError(
            "Cannot determine entity keys for online retrieval. "
            "Provide entity transforms via the 'entities' parameter."
        )

    return join_online_feature_by_keys(
        result, feature_name, store, entity_key_columns
    )


def join_online_feature_by_keys(
    result: pl.DataFrame,
    feature_name: str,
    store: online_.OnlineStore,
    entity_key_columns: list[str],
) -> pl.DataFrame:
    """
    Join a single feature from online store using specific entity key columns.

    This is the core join logic used by both the standalone get_online_features()
    and Definitions.get_online_features(). It extracts unique entity combinations,
    batch-reads from the store, and joins the feature values back.

    Args:
        result: Current result DataFrame with entity keys
        feature_name: Name of feature to retrieve
        store: Online store instance
        entity_key_columns: Specific entity key columns for this feature

    Returns:
        Result DataFrame with feature columns joined
    """
    # Extract unique entity combinations
    unique_entities = result.select(entity_key_columns).unique()
    entity_dicts = [
        {col: str(row[col]) for col in entity_key_columns}
        for row in unique_entities.iter_rows(named=True)
    ]

    if not entity_dicts:
        return result

    # Batch read from online store
    values = store.read_batch(feature_name, entity_dicts)

    # Build feature DataFrame from results
    feature_rows = []
    for entity_dict, value in zip(entity_dicts, values):
        if value is not None:
            feature_rows.append({**entity_dict, **value})

    if not feature_rows:
        return result

    feature_df = pl.DataFrame(feature_rows)

    # Cast entity key columns back to original types for join compatibility
    for col in entity_key_columns:
        if col in result.columns:
            feature_df = feature_df.with_columns(
                pl.col(col).cast(result.schema[col])
            )

    return result.join(feature_df, on=entity_key_columns, how="left")


def _get_entity_key_columns(
    entities: list[entities_.Entity] | None,
) -> list[str]:
    """
    Extract all entity key column names.

    Args:
        entities: List of entity definitions

    Returns:
        Flat list of all join key column names
    """
    if not entities:
        return []

    columns = []
    for entity in entities:
        columns.extend(entity.key_columns)
    return columns
