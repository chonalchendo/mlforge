"""User features for recommendation system."""

from datetime import timedelta

import polars as pl

import mlforge as mlf
from recommendation.entities import user

user_events = mlf.Source("data/user_events.parquet")

timestamp = mlf.Timestamp(column="event_time", format="%Y-%m-%d %H:%M:%S")


@mlf.feature(
    source=user_events,
    entities=[user],
    timestamp=timestamp,
    interval=timedelta(days=1),
    metrics=[
        mlf.Aggregate(
            field="view_count",
            function="sum",
            windows=["1d", "7d", "30d"],
            name="views",
            description="Total page views by user",
        ),
        mlf.Aggregate(
            field="click_count",
            function="sum",
            windows=["1d", "7d", "30d"],
            name="clicks",
            description="Total clicks by user",
        ),
        mlf.Aggregate(
            field="purchase_count",
            function="sum",
            windows=["1d", "7d", "30d"],
            name="purchases",
            description="Total purchases by user",
        ),
    ],
    tags=["user", "engagement"],
)
def user_engagement(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(
        pl.col("user_id"),
        pl.col("event_time"),
        (pl.col("event_type") == "view").cast(pl.Int32).alias("view_count"),
        (pl.col("event_type") == "click").cast(pl.Int32).alias("click_count"),
        (pl.col("event_type") == "purchase").cast(pl.Int32).alias("purchase_count"),
    )
