"""Feature definitions for credit card transaction analytics.

This module demonstrates mlforge features with:
- Rolling window aggregations (7d, 30d, 90d)
- Point-in-time features (latest transaction info)
- Data quality validators
- Multiple entity types
- Cross-entity features (customer-merchant pairs)

Features are stored in Databricks Unity Catalog as Delta tables
and synced to Online Tables for real-time serving.
"""

from datetime import timedelta

import polars as pl

import mlforge as mlf
from databricks_features.entities import customer, customer_merchant, merchant

# Data source - parquet file for local dev, can be Delta table path for Databricks
transactions = mlf.Source("data/transactions.parquet")

# Timestamp configuration with explicit format for reliable parsing
timestamp = mlf.Timestamp(
    column="transaction_time",
    format="%Y-%m-%d %H:%M:%S",
)

# Rolling metrics for spending patterns
# Windows capture short-term (7d), medium-term (30d), and long-term (90d) behavior
spend_metrics = mlf.Rolling(
    windows=["7d", "30d", timedelta(days=90)],
    aggregations={
        "amount": ["sum", "mean", "count", "std", "min", "max"],
    },
)

# Velocity metrics for fraud detection signals
# High transaction counts in short windows may indicate fraud
velocity_metrics = mlf.Rolling(
    windows=["1d", "7d"],
    aggregations={
        "amount": ["count"],
    },
)

# Merchant diversity metrics - track count of transactions at different merchants
# Note: n_unique not supported in DuckDB compiler, use count instead
merchant_diversity_metrics = mlf.Rolling(
    windows=["7d", "30d"],
    aggregations={
        "amount": [
            "count"
        ],  # Number of transactions (proxy for merchant diversity)
    },
)


@mlf.feature(
    source=transactions,
    entities=[customer],
    timestamp=timestamp,
    interval=timedelta(days=1),
    metrics=[spend_metrics],
    validators={
        "amount": [
            mlf.greater_than_or_equal(value=0),
            mlf.less_than(value=100000),  # Sanity check for data quality
        ],
        "customer_id": [mlf.not_null()],
    },
    tags=["customer", "spending", "core"],
    description="Customer spending patterns over rolling windows",
)
def customer_spend(df: pl.DataFrame) -> pl.DataFrame:
    """Customer spending aggregations."""
    return df.select(
        "customer_id",
        "transaction_time",
        "amount",
    )


@mlf.feature(
    source=transactions,
    entities=[merchant],
    timestamp=timestamp,
    interval=timedelta(days=1),
    metrics=[spend_metrics],
    validators={
        "amount": [mlf.greater_than_or_equal(value=0)],
    },
    tags=["merchant", "spending", "core"],
    description="Merchant transaction volume and spending patterns",
)
def merchant_spend(df: pl.DataFrame) -> pl.DataFrame:
    """Merchant-level spending aggregations."""
    return df.select(
        "merchant_id",
        "transaction_time",
        "amount",
    )


@mlf.feature(
    source=transactions,
    entities=[customer],
    timestamp=timestamp,
    interval=timedelta(days=1),
    metrics=[velocity_metrics],
    tags=["customer", "velocity", "fraud"],
    description="Transaction velocity for fraud detection",
)
def customer_velocity(df: pl.DataFrame) -> pl.DataFrame:
    """Customer transaction velocity for fraud signals."""
    return df.select(
        "customer_id",
        "transaction_time",
        "amount",
    )


@mlf.feature(
    source=transactions,
    entities=[customer_merchant],
    timestamp=timestamp,
    interval=timedelta(days=1),
    metrics=[
        mlf.Rolling(
            windows=["30d", "90d"],
            aggregations={
                "amount": ["sum", "count", "mean"],
            },
        ),
    ],
    tags=["customer", "merchant", "cross-entity"],
    description="Customer behavior at specific merchants",
)
def customer_merchant_affinity(df: pl.DataFrame) -> pl.DataFrame:
    """Cross-entity feature: customer spending patterns at specific merchants.

    High affinity (frequent visits, consistent spending) at a merchant may
    indicate legitimate transactions, while sudden new merchant activity
    could be a fraud signal.
    """
    return df.select(
        "customer_id",
        "merchant_id",
        "transaction_time",
        "amount",
    )


@mlf.feature(
    source=transactions,
    entities=[customer],
    timestamp=timestamp,
    interval=timedelta(days=1),
    tags=["customer", "point-in-time", "core"],
    description="Latest transaction details for each customer",
)
def customer_latest_transaction(df: pl.DataFrame) -> pl.DataFrame:
    """Point-in-time feature: most recent transaction details.

    No rolling metrics - returns the raw values from each transaction,
    useful for capturing the latest state rather than aggregates.
    """
    return df.select(
        "customer_id",
        "transaction_time",
        pl.col("amount").alias("latest_amount"),
        pl.col("merchant_category").alias("latest_category"),
        pl.col("is_online").alias("latest_is_online"),
    )
