"""
Feature definitions for transactions-online example.

This example demonstrates building features to both offline and online stores.
Uses a simplified user_spend feature for clarity.
"""

from datetime import timedelta

import polars as pl

import mlforge as mlf

SOURCE = "data/transactions.parquet"

USER_KEY = "user_id"

# Create a surrogate key from user identifying columns
with_user_id = mlf.entity_key("first", "last", "dob", alias=USER_KEY)

# Define rolling aggregations over 7 and 30 day windows
spend_metrics = mlf.Rolling(
    windows=[timedelta(days=7), "30d"],
    aggregations={"amt": ["count", "sum"]},
)


@mlf.feature(
    keys=[USER_KEY],
    source=SOURCE,
    tags=["users"],
    description="User spending aggregations for real-time serving",
    timestamp="transaction_date",
    interval=timedelta(days=1),
    metrics=[spend_metrics],
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    """
    Compute user spend aggregations.

    Transforms raw transactions into daily user spend metrics
    with 7-day and 30-day rolling windows.
    """
    return df.pipe(with_user_id).select(
        pl.col("user_id"),
        pl.col("trans_date_trans_time")
        .str.to_datetime("%Y-%m-%d %H:%M:%S")
        .alias("transaction_date"),
        pl.col("amt"),
    )
