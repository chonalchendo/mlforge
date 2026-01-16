# mlforge/utils.py
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    import mlforge.entities as entities_


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


def apply_entity_keys(
    df: pl.DataFrame,
    entities: list["entities_.Entity"],
) -> pl.DataFrame:
    """
    Generate surrogate keys for entities that require it.

    For each entity with from_columns specified, generates a surrogate
    key column using the surrogate_key() function.

    Args:
        df: Source Polars DataFrame
        entities: List of Entity objects

    Returns:
        DataFrame with generated key columns added
    """
    for entity in entities:
        if entity.requires_generation:
            df = df.with_columns(
                surrogate_key(*entity.from_columns).alias(entity.join_key)
            )
    return df
