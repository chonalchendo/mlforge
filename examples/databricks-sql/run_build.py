"""
End-to-end verification: Build features to Unity Catalog via Databricks Connect.

This script:
1. Loads environment variables from .env
2. Creates Definitions with mlforge.yaml config
3. Builds features to sbx.features.* tables

Usage:
    cd examples/databricks-sql
    uv run python run_build.py
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
else:
    print("No .env file found!")
    sys.exit(1)

# Change to the example directory (where mlforge.yaml is)
os.chdir(Path(__file__).parent)

print("=" * 60)
print("mlforge End-to-End Verification")
print("=" * 60)
print(f"\nTarget catalog: {os.environ.get('DATABRICKS_SANDBOX_CATALOG')}")
print(f"Target schema: features")

# Import definitions (this will load mlforge.yaml and create Databricks session)
print("\n[1/3] Loading feature definitions and connecting to Databricks...")

try:
    from definitions import defs
    print(f"   Loaded {len(defs.features)} features:")
    for name in defs.features:
        print(f"     - {name}")
except Exception as e:
    print(f"   Failed to load definitions: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Build features
print("\n[2/3] Building features...")

try:
    build_result = defs.build(preview=True, preview_rows=3)
    print(f"\n   Build completed successfully!")
    print(f"   Features built: {build_result.built}")
except Exception as e:
    print(f"   Build failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Verify by querying the tables
print("\n[3/3] Verifying tables in Unity Catalog...")

try:
    from pyspark.sql import SparkSession

    spark = SparkSession.getActiveSession()
    if spark:
        catalog = os.environ.get('DATABRICKS_SANDBOX_CATALOG')
        for feature_name in defs.features:
            table = f"{catalog}.features.{feature_name}"
            try:
                count = spark.read.table(table).count()
                print(f"   {table}: {count} rows")
            except Exception as e:
                print(f"   {table}: ERROR - {e}")
    else:
        print("   No active SparkSession - skipping table verification")
except Exception as e:
    print(f"   Verification failed: {e}")

print("\n" + "=" * 60)
print("Verification Complete!")
print("=" * 60)
print(f"\nFeatures are available at:")
catalog = os.environ.get('DATABRICKS_SANDBOX_CATALOG')
for feature_name in defs.features:
    print(f"  - {catalog}.features.{feature_name}")
print("\nQuery in Databricks SQL:")
print(f"  SELECT * FROM {catalog}.features.pickup_zone_stats LIMIT 10;")
