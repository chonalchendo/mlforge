"""
Verify Databricks Connect works in your environment.

Databricks Connect allows running PySpark code locally that executes
on a remote Databricks cluster or serverless compute.

Prerequisites:
    pip install databricks-connect

Usage:
    1. Copy .env.example to .env and fill in credentials
    2. Run: uv run python verify_databricks_connect.py
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
print("Databricks Connect Verification")
print("=" * 60)

# Step 1: Check databricks-connect is installed
print("\n[1/5] Checking databricks-connect installation...")
try:
    from databricks.connect import DatabricksSession

    print("   databricks-connect is installed")
except ImportError:
    print("   databricks-connect not installed")
    print("\n   Install with:")
    print("       pip install databricks-connect")
    sys.exit(1)

# Step 2: Check credentials
print("\n[2/5] Checking credentials...")
host = os.environ.get("DATABRICKS_HOST", "").replace("https://", "")
token = os.environ.get("DATABRICKS_TOKEN", "")

if not host:
    print("   Missing DATABRICKS_HOST")
    print("   Set in .env file or environment variable")
    sys.exit(1)

if not token:
    print("   Missing DATABRICKS_TOKEN")
    print("   Set in .env file or environment variable")
    sys.exit(1)

print(f"   Host: {host}")
print(f"   Token: {'*' * 10}...{token[-4:]}")

# Step 3: Create session with serverless
print("\n[3/5] Creating DatabricksSession (serverless)...")
try:
    # Try serverless first
    spark = (
        DatabricksSession.builder.remote(
            host=f"https://{host}",
            token=token,
        )
        .serverless(True)
        .getOrCreate()
    )

    print(f"   Connected to {host}")
    print(f"   Spark version: {spark.version}")

except Exception as e:
    print(f"   Failed to create session: {e}")
    print("\n   This might mean:")
    print("   - Databricks Connect is not enabled in your workspace")
    print("   - Your token doesn't have the right permissions")
    print("   - Serverless compute is not available")
    print("\n   Check Databricks Connect docs:")
    print("   https://docs.databricks.com/en/dev-tools/databricks-connect/")
    sys.exit(1)

# Step 4: Test reading a UC table
print("\n[4/5] Reading sample UC table (samples.nyctaxi.trips)...")
try:
    df = spark.read.table("samples.nyctaxi.trips")
    count = df.count()
    print(f"   Read samples.nyctaxi.trips: {count:,} rows")

except Exception as e:
    print(f"   Failed to read table: {e}")
    print("\n   This might mean:")
    print("   - The samples catalog is not available in your workspace")
    print("   - Your token doesn't have SELECT permission")
    sys.exit(1)

# Step 5: Test a simple transformation
print("\n[5/5] Running PySpark transformation...")
try:
    from pyspark.sql import functions as F

    result = df.groupBy("pickup_zip").agg(
        F.count("*").alias("trip_count"),
        F.avg("fare_amount").alias("avg_fare"),
    )

    # Collect a small sample
    sample = result.limit(5).toPandas()

    print("   Transformation executed successfully")
    print("\n   Sample output:")
    print(sample.to_string(index=False))

except Exception as e:
    print(f"   Transformation failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Cleanup
spark.stop()

print("\n" + "=" * 60)
print("SUCCESS: Databricks Connect is working!")
print("=" * 60)
print("\nYour environment supports:")
print("  - Remote PySpark execution via Databricks Connect")
print("  - Reading Unity Catalog tables")
print("  - PySpark transformations (groupBy, agg, etc.)")
print("\nThis confirms mlforge can use PySparkEngine with Databricks Connect")
print("to build features from your laptop directly to Unity Catalog.")
print("\nNext: Test writing to your personal sandbox catalog:")
print("  - Modify this script to write to dev_<username>.features.test_table")
print("  - Or wait for mlforge v0.8.0 which will handle this automatically")
