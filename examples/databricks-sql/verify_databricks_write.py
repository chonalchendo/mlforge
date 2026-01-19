"""
Verify writing to Unity Catalog via Databricks Connect.

This tests the full workflow:
1. Read from sample UC table
2. Transform with PySpark
3. Write to your personal sandbox catalog

Prerequisites:
    pip install databricks-connect

Usage:
    1. Set your sandbox catalog in .env:
       DATABRICKS_SANDBOX_CATALOG=dev_yourname
    
    2. Run: python verify_databricks_write.py
"""

import os
import sys
from pathlib import Path

# Load .env file
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    print(f"Loading credentials from {env_file}")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

print("=" * 60)
print("Databricks Connect Write Verification")
print("=" * 60)

# Check credentials
host = os.environ.get("DATABRICKS_HOST", "").replace("https://", "")
token = os.environ.get("DATABRICKS_TOKEN", "")
sandbox_catalog = os.environ.get("DATABRICKS_SANDBOX_CATALOG", "")

if not host or not token:
    print("\nMissing DATABRICKS_HOST or DATABRICKS_TOKEN")
    sys.exit(1)

if not sandbox_catalog:
    print("\nMissing DATABRICKS_SANDBOX_CATALOG")
    print("Add to your .env file:")
    print("    DATABRICKS_SANDBOX_CATALOG=dev_yourname")
    print("\nOr set environment variable:")
    print("    export DATABRICKS_SANDBOX_CATALOG=dev_yourname")
    sys.exit(1)

print(f"\nTarget catalog: {sandbox_catalog}")
print(f"Target schema: features (will be created if needed)")
print(f"Target table: {sandbox_catalog}.features.test_pickup_stats")

# Confirm before writing
response = input("\nProceed with write test? [y/N] ").strip().lower()
if response != "y":
    print("Aborted.")
    sys.exit(0)

# Create session
print("\n[1/5] Creating DatabricksSession...")
from databricks.connect import DatabricksSession

spark = (
    DatabricksSession.builder.remote(
        host=f"https://{host}",
        token=token,
    )
    .serverless(True)
    .getOrCreate()
)
print(f"   Connected (Spark {spark.version})")

# Create schema if not exists
print(f"\n[2/5] Creating schema {sandbox_catalog}.features...")
try:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {sandbox_catalog}.features")
    print(f"   Schema ready")
except Exception as e:
    print(f"   Failed to create schema: {e}")
    print("\n   You may need to create the catalog first, or check permissions.")
    spark.stop()
    sys.exit(1)

# Read source data
print("\n[3/5] Reading source table...")
df = spark.read.table("samples.nyctaxi.trips")
print(f"   Read {df.count():,} rows from samples.nyctaxi.trips")

# Transform
print("\n[4/5] Running transformation...")
from pyspark.sql import functions as F

result = df.groupBy("pickup_zip").agg(
    F.count("*").alias("trip_count"),
    F.sum("fare_amount").alias("total_fare"),
    F.avg("fare_amount").alias("avg_fare"),
    F.avg("trip_distance").alias("avg_distance"),
)
print(f"   Aggregated to {result.count():,} rows")

# Write to UC
print(f"\n[5/5] Writing to {sandbox_catalog}.features.test_pickup_stats...")
try:
    (
        result.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(f"{sandbox_catalog}.features.test_pickup_stats")
    )
    print("   Write successful!")
    
    # Verify by reading back
    verify_df = spark.read.table(f"{sandbox_catalog}.features.test_pickup_stats")
    print(f"   Verified: {verify_df.count():,} rows in table")
    print("\n   Sample data:")
    verify_df.limit(5).show()
    
except Exception as e:
    print(f"   Write failed: {e}")
    print("\n   Common issues:")
    print("   - Catalog doesn't exist (create it in Databricks UI)")
    print("   - No CREATE TABLE permission on the schema")
    print("   - Schema name conflict")
    spark.stop()
    sys.exit(1)

spark.stop()

print("\n" + "=" * 60)
print("SUCCESS: Full read-transform-write workflow works!")
print("=" * 60)
print(f"\nYour feature table is at: {sandbox_catalog}.features.test_pickup_stats")
print("\nThis confirms mlforge can:")
print("  1. Read from Unity Catalog tables")
print("  2. Transform with PySpark")
print("  3. Write features to your sandbox catalog")
print("\nYou can query the table in Databricks SQL:")
print(f"    SELECT * FROM {sandbox_catalog}.features.test_pickup_stats LIMIT 10")
