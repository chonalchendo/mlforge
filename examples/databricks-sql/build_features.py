"""
Build features using Databricks SQL Connector.

This demonstrates executing SQL features against Unity Catalog tables
and saving results locally (or viewing them).

For writing back TO Unity Catalog, you would need to run inside Databricks
with PySpark, using UnityCatalogStore.

Usage:
    cd examples/databricks-sql
    uv run python build_features.py
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

# Check credentials
required_vars = ["DATABRICKS_HOST", "DATABRICKS_HTTP_PATH", "DATABRICKS_TOKEN"]
missing = [v for v in required_vars if not os.environ.get(v)]
if missing:
    print(f"Missing: {missing}. Copy .env.example to .env and fill in credentials.")
    sys.exit(1)

print("=" * 60)
print("Building Features from Unity Catalog")
print("=" * 60)

# Import mlforge components
from mlforge.engines import DatabricksEngine

# Import our feature definitions
import features

# Initialize the Databricks engine
print("\n[1/4] Connecting to Databricks SQL Warehouse...")
engine = DatabricksEngine(
    host=os.environ["DATABRICKS_HOST"].replace("https://", ""),
    http_path=os.environ["DATABRICKS_HTTP_PATH"],
    token=os.environ["DATABRICKS_TOKEN"],
)
print("   Connected!")

# Create output directory for local storage
output_dir = Path(__file__).parent / "feature_store"
output_dir.mkdir(exist_ok=True)

# Build each feature
feature_list = [
    features.pickup_zone_stats,
    features.dropoff_zone_stats,
    features.route_stats,
]

print(f"\n[2/4] Building {len(feature_list)} features...")

results = {}
for i, feat in enumerate(feature_list, 1):
    print(f"\n   [{i}/{len(feature_list)}] Building {feat.name}...")

    try:
        result = engine.execute(feat)
        results[feat.name] = result

        print(f"       Rows: {result.row_count()}")
        print(f"       Columns: {list(result.schema().keys())}")

    except Exception as e:
        print(f"       ERROR: {e}")
        continue

print(f"\n[3/4] Saving features to {output_dir}...")

for name, result in results.items():
    output_path = output_dir / f"{name}.parquet"
    result.write_parquet(output_path)
    print(f"   Saved: {output_path}")

print("\n[4/4] Previewing results...")

for name, result in results.items():
    df = result.to_polars()
    print(f"\n--- {name} ---")
    print(df.head(5))

# Cleanup
engine.close()

print("\n" + "=" * 60)
print("Build complete!")
print("=" * 60)
print(f"\nFeatures saved to: {output_dir}")
print("\nNext steps:")
print("  - Query features locally with Polars")
print("  - To write TO Unity Catalog, run inside Databricks with UnityCatalogStore")
