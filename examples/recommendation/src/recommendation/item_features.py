"""Item features for recommendation system."""

from datetime import timedelta

import polars as pl

import mlforge as mlf
from recommendation.entities import item

item_events = mlf.Source("data/item_events.parquet")

timestamp = mlf.Timestamp(column="event_time", format="%Y-%m-%d %H:%M:%S")

popularity_metrics = [
    mlf.Aggregate(
        field="view_count",
        function="sum",
        windows=["1d", "7d", "30d"],
        name="views",
        description="Total item views",
    ),
    mlf.Aggregate(
        field="purchase_count",
        function="sum",
        windows=["1d", "7d", "30d"],
        name="purchases",
        description="Total item purchases",
    ),
]


@mlf.feature(
    source=item_events,
    entities=[item],
    timestamp=timestamp,
    interval=timedelta(days=1),
    metrics=popularity_metrics,
    tags=["item", "popularity"],
)
def item_popularity(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(
        pl.col("item_id"),
        pl.col("event_time"),
        (pl.col("event_type") == "view").cast(pl.Int32).alias("view_count"),
        (pl.col("event_type") == "purchase").cast(pl.Int32).alias("purchase_count"),
    )
