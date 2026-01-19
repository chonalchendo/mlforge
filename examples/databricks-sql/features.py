"""
Feature definitions for NYC Taxi dataset in Unity Catalog.

Uses the samples.nyctaxi.trips dataset available in all Databricks workspaces.
"""

from mlforge import Source, feature

# Source table from Databricks sample data
trips = Source(table="samples.nyctaxi.trips")


@feature(source=trips, keys=["pickup_zip"])
def pickup_zone_stats():
    """Aggregate statistics per pickup zone."""
    return """
        SELECT
            pickup_zip,
            COUNT(*) as trip_count,
            AVG(trip_distance) as avg_distance,
            AVG(fare_amount) as avg_fare,
            SUM(fare_amount) as total_fare
        FROM {source}
        WHERE pickup_zip IS NOT NULL
        GROUP BY pickup_zip
    """


@feature(source=trips, keys=["dropoff_zip"])
def dropoff_zone_stats():
    """Aggregate statistics per dropoff zone."""
    return """
        SELECT
            dropoff_zip,
            COUNT(*) as trip_count,
            AVG(trip_distance) as avg_distance,
            AVG(fare_amount) as avg_fare
        FROM {source}
        WHERE dropoff_zip IS NOT NULL
        GROUP BY dropoff_zip
    """


@feature(source=trips, keys=["pickup_zip", "dropoff_zip"])
def route_stats():
    """Statistics for pickup-dropoff route pairs."""
    return """
        SELECT
            pickup_zip,
            dropoff_zip,
            COUNT(*) as trip_count,
            AVG(trip_distance) as avg_distance,
            AVG(fare_amount) as avg_fare,
            PERCENTILE_APPROX(fare_amount, 0.5) as median_fare
        FROM {source}
        WHERE pickup_zip IS NOT NULL
          AND dropoff_zip IS NOT NULL
        GROUP BY pickup_zip, dropoff_zip
        HAVING COUNT(*) >= 10
    """
