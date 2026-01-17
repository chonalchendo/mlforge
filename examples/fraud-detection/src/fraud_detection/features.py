"""Feature definitions for fraud detection."""

from datetime import timedelta

import polars as pl

import mlforge as mlf
from fraud_detection.entities import card, merchant, user

transactions = mlf.Source("data/transactions.parquet")

timestamp = mlf.Timestamp(
    column="trans_date_trans_time",
    format="%Y-%m-%d %H:%M:%S",
)

spend_metrics = [
    mlf.Aggregate(field="amt", function="sum", windows=["1d", "7d", "30d"], name="total_spend"),
    mlf.Aggregate(field="amt", function="mean", windows=["1d", "7d", "30d"], name="avg_spend"),
    mlf.Aggregate(field="amt", function="count", windows=["1d", "7d", "30d"], name="txn_count"),
    mlf.Aggregate(field="amt", function="std", windows=["1d", "7d", "30d"], name="spend_std"),
]

velocity_metrics = [
    mlf.Aggregate(field="amt", function="count", windows=["1d", "7d"], name="velocity"),
]


@mlf.feature(
    source=transactions,
    entities=[user],
    timestamp=timestamp,
    interval=timedelta(days=1),
    metrics=spend_metrics,
    validators={"amt": [mlf.greater_than_or_equal(value=0)]},
    tags=["user", "spending"],
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    return df.select("user_id", "trans_date_trans_time", "amt")


@mlf.feature(
    source=transactions,
    entities=[merchant],
    timestamp=timestamp,
    interval=timedelta(days=1),
    metrics=spend_metrics,
    tags=["merchant", "spending"],
)
def merchant_spend(df: pl.DataFrame) -> pl.DataFrame:
    return df.select("merchant_id", "trans_date_trans_time", "amt")


@mlf.feature(
    source=transactions,
    entities=[card],
    timestamp=timestamp,
    interval=timedelta(days=1),
    metrics=velocity_metrics,
    tags=["card", "velocity"],
)
def card_velocity(df: pl.DataFrame) -> pl.DataFrame:
    return df.select("card_id", "trans_date_trans_time", "amt")
