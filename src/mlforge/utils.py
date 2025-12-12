# mlforge/utils.py
from typing import Protocol

import polars as pl


class EntityKeyTransform(Protocol):
    """
    Protocol for entity key transformation functions.

    Defines the interface for functions created by entity_key() that
    add surrogate keys to DataFrames. Includes metadata attributes
    for column tracking.

    Attributes:
        _entity_key_columns: Source columns used to generate the key
        _entity_key_alias: Name of the generated key column
    """

    _entity_key_columns: tuple[str, ...]
    _entity_key_alias: str

    def __call__(self, df: pl.DataFrame) -> pl.DataFrame: ...


def surrogate_key(*columns: str) -> pl.Expr:
    """
    Generate a surrogate key by hashing column values.

    Concatenates column values with null handling, then produces a hash.
    Useful for creating stable identifiers from natural keys.

    Args:
        *columns: Column names to include in the hash

    Returns:
        Polars expression that produces a string hash

    Raises:
        ValueError: If no columns are provided

    Example:
        df.with_columns(
            surrogate_key("first_name", "last_name", "dob").alias("user_id")
        )
    """
    if not columns:
        raise ValueError("surrogate_key requires at least one column")

    concat_expr = pl.concat_str(
        [pl.col(c).cast(pl.Utf8).fill_null("__NULL__") for c in columns],
        separator="||",
    )

    return concat_expr.hash().cast(pl.Utf8)


def entity_key(*columns: str, alias: str) -> EntityKeyTransform:
    """
    Create a reusable entity key transformation function.

    Returns a function that adds a surrogate key column to a DataFrame
    by hashing the specified source columns. Useful for defining entity
    relationships and passing to get_training_data().

    Args:
        *columns: Source column names to hash
        alias: Name for the generated surrogate key column

    Returns:
        Transform function compatible with df.pipe() and get_training_data()

    Raises:
        ValueError: If no columns provided or alias is empty

    Example:
        # Define reusable transform
        with_user_id = entity_key("first", "last", "dob", alias="user_id")

        # Apply to DataFrame
        users_df = df.pipe(with_user_id)

        # Use in feature retrieval
        training_data = get_training_data(
            features=["user_age"],
            entity_df=transactions,
            entities=[with_user_id]
        )
    """
    if not columns:
        raise ValueError("entity_key requires at least one column")

    if not alias:
        raise ValueError("entity_key requires an alias")

    def transform(df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns(surrogate_key(*columns).alias(alias))

    transform._entity_key_columns = columns  # type: ignore[attr-defined]
    transform._entity_key_alias = alias  # type: ignore[attr-defined]

    return transform  # type: ignore[return-value]
