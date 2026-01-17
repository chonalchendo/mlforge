"""
Feature definitions for transactions-online example.

Demonstrates:
- Source: Data source abstraction
- Entity: Surrogate key generation from multiple columns
- Timestamp: Explicit format and alias configuration
- Aggregate: Rolling window aggregations
- Validators: Data quality checks
"""

from datetime import timedelta

import polars as pl

import mlforge as mlf

### Source Definition

source = mlf.Source("data/transactions.parquet")

### Entity Definitions

user = mlf.Entity(
    name="user",
    join_key="user_id",
    from_columns=["first", "last", "dob"],
)

### Timestamp Configuration

# Explicit timestamp parsing with format and alias
timestamp = mlf.Timestamp(
    column="trans_date_trans_time",
    format="%Y-%m-%d %H:%M:%S",
    alias="transaction_date",
)

### Metrics

spend_metrics = [
    mlf.Aggregate(field="amt", function="count", windows=["7d", "30d"], name="txn_count"),
    mlf.Aggregate(field="amt", function="sum", windows=["7d", "30d"], name="total_spend"),
]


@mlf.feature(
    source=source,
    entities=[user],
    tags=["users"],
    description="User spending aggregations for real-time serving",
    timestamp=timestamp,
    interval=timedelta(days=1),
    metrics=spend_metrics,
    validators={"amt": [mlf.greater_than_or_equal(value=0)]},
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    """
    Compute user spend aggregations.

    The engine handles:
    - Entity key generation (user_id from first, last, dob)
    - Timestamp parsing (trans_date_trans_time -> transaction_date)
    - Rolling window aggregations (7d, 30d)
    - Validation (amt >= 0)
    """
    return df.select(
        pl.col("user_id"),
        pl.col("trans_date_trans_time"),  # Engine parses via Timestamp config
        pl.col("amt"),
    )
