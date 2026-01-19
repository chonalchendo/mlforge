"""
Verification script for Databricks SQL Connector integration.

This script tests the Unity Catalog SQL transpilation feature with
a real Databricks SQL Warehouse connection.

Usage:
    1. Copy .env.example to .env and fill in your credentials:
       cp .env.example .env

    2. Run this script from the examples/databricks-sql directory:
       cd examples/databricks-sql
       uv run python verify_databricks.py
"""

import os
import sys
from pathlib import Path

# Load .env file if it exists
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
    print("No .env file found. Checking environment variables...")

# Check for required environment variables
required_vars = ["DATABRICKS_HOST", "DATABRICKS_HTTP_PATH", "DATABRICKS_TOKEN"]
missing = [v for v in required_vars if not os.environ.get(v)]

if missing:
    print("\nMissing required credentials:")
    for var in missing:
        print(f"  - {var}")
    print("\nSetup instructions:")
    print("  1. Copy .env.example to .env:")
    print("     cp .env.example .env")
    print("  2. Edit .env with your Databricks credentials")
    print("  3. Run this script again")
    sys.exit(1)

print("=" * 60)
print("Databricks SQL Connector Verification")
print("=" * 60)

# Step 1: Test basic connection
print("\n[1/4] Testing Databricks SQL Connector connection...")

try:
    from databricks import sql

    conn = sql.connect(
        server_hostname=os.environ["DATABRICKS_HOST"].replace("https://", ""),
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    )

    with conn.cursor() as cursor:
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        assert result[0] == 1, "Expected 1"

    print("   Connection successful!")

except ImportError:
    print("   ERROR: databricks-sql-connector not installed")
    print("   Run: pip install mlforge[databricks-sql]")
    sys.exit(1)
except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

# Step 2: Test Source with table parameter
print("\n[2/4] Testing Source with table parameter...")

from mlforge import Source

try:
    # Create a UC source
    source = Source(table="samples.nyctaxi.trips")

    assert source.table == "samples.nyctaxi.trips"
    assert source.is_unity_catalog is True
    assert source.location == "unity-catalog"
    assert source.name == "trips"
    assert source.path is None

    print("   Source(table=...) works correctly!")

except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

# Step 3: Test DatabricksEngine initialization
print("\n[3/4] Testing DatabricksEngine initialization...")

try:
    from mlforge.engines import DatabricksEngine

    engine = DatabricksEngine(
        host=os.environ["DATABRICKS_HOST"].replace("https://", ""),
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    print("   DatabricksEngine initialized!")

except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

# Step 4: Test SQL feature execution
print("\n[4/4] Testing SQL feature execution...")

try:
    from mlforge import feature

    # Define a SQL feature using the samples.nyctaxi.trips table
    # This is a sample dataset available in Databricks
    @feature(
        source=Source(table="samples.nyctaxi.trips"),
        keys=["pickup_zip"],
    )
    def pickup_stats():
        """Count trips per pickup zip code."""
        return """
            SELECT
                pickup_zip,
                COUNT(*) as trip_count,
                AVG(trip_distance) as avg_distance
            FROM {source}
            WHERE pickup_zip IS NOT NULL
            GROUP BY pickup_zip
            LIMIT 10
        """

    # Execute the feature
    result = engine.execute(pickup_stats)

    # Check results
    df = result.to_polars()
    print(f"   Query returned {result.row_count()} rows")
    print(f"   Columns: {df.columns}")
    print("\n   Sample data:")
    print(df.head(5))

    print("\n   SQL feature execution works!")

except Exception as e:
    print(f"   ERROR: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Cleanup
engine.close()
conn.close()

print("\n" + "=" * 60)
print("All verifications passed!")
print("=" * 60)
print("\nThe Unity Catalog SQL transpilation feature is working correctly.")
print("\nYou can now use features like:")
print("""
    from mlforge import feature, Source

    orders = Source(table="your_catalog.your_schema.orders")

    @feature(source=orders, keys=["customer_id"])
    def customer_spend():
        return '''
            SELECT customer_id, SUM(amount) as total
            FROM {source}
            GROUP BY customer_id
        '''
""")
