"""
Feature definitions for NYC Taxi dataset.

This module defines features using PySpark transformations that run
on Databricks via Databricks Connect.

Usage:
    # Build features to dev sandbox
    mlforge build --profile dev

    # Or programmatically:
    from definitions import defs
    defs.build()
"""

from pyspark.sql import DataFrame as SparkDataFrame
from pyspark.sql import functions as F

from mlforge import Definitions, Source, feature

# =============================================================================
# Source Tables
# =============================================================================

# Sample NYC taxi trips data (available in all Databricks workspaces)
trips = Source(table="samples.nyctaxi.trips")


# =============================================================================
# Features
# =============================================================================


@feature(
    source=trips,
    keys=["pickup_zip"],
    description="Aggregated statistics per pickup zone",
    tags=["nyc-taxi", "zone-stats"],
)
def pickup_zone_stats(df: SparkDataFrame) -> SparkDataFrame:
    """
    Calculate trip statistics aggregated by pickup zip code.

    Returns columns:
        - pickup_zip: Pickup zone identifier
        - trip_count: Total number of trips
        - total_fare: Sum of all fares
        - avg_fare: Average fare amount
        - avg_distance: Average trip distance
    """
    return (
        df.filter(F.col("pickup_zip").isNotNull())
        .groupBy("pickup_zip")
        .agg(
            F.count("*").alias("trip_count"),
            F.sum("fare_amount").alias("total_fare"),
            F.avg("fare_amount").alias("avg_fare"),
            F.avg("trip_distance").alias("avg_distance"),
        )
    )


@feature(
    source=trips,
    keys=["dropoff_zip"],
    description="Aggregated statistics per dropoff zone",
    tags=["nyc-taxi", "zone-stats"],
)
def dropoff_zone_stats(df: SparkDataFrame) -> SparkDataFrame:
    """
    Calculate trip statistics aggregated by dropoff zip code.
    """
    return (
        df.filter(F.col("dropoff_zip").isNotNull())
        .groupBy("dropoff_zip")
        .agg(
            F.count("*").alias("trip_count"),
            F.avg("fare_amount").alias("avg_fare"),
            F.avg("trip_distance").alias("avg_distance"),
        )
    )


@feature(
    source=trips,
    keys=["pickup_zip", "dropoff_zip"],
    description="Statistics for pickup-dropoff route pairs",
    tags=["nyc-taxi", "routes"],
)
def route_stats(df: SparkDataFrame) -> SparkDataFrame:
    """
    Calculate statistics for each pickup-dropoff route combination.

    Only includes routes with at least 10 trips to filter out noise.
    """
    return (
        df.filter(F.col("pickup_zip").isNotNull())
        .filter(F.col("dropoff_zip").isNotNull())
        .groupBy("pickup_zip", "dropoff_zip")
        .agg(
            F.count("*").alias("trip_count"),
            F.avg("fare_amount").alias("avg_fare"),
            F.avg("trip_distance").alias("avg_distance"),
            F.percentile_approx("fare_amount", 0.5).alias("median_fare"),
        )
        .filter(F.col("trip_count") >= 10)  # Filter low-volume routes
    )


# =============================================================================
# Feature Definitions
# =============================================================================

# Create Definitions - profile will be loaded from mlforge.yaml
# When running locally, use: mlforge build --profile dev
defs = Definitions(
    name="nyc-taxi-features",
    features=[
        pickup_zone_stats,
        dropoff_zone_stats,
        route_stats,
    ],
    default_engine="pyspark",  # Use PySpark for Databricks
)
