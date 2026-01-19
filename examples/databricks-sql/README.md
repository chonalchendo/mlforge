# Databricks Integration Example

This example demonstrates the full mlforge workflow with Databricks:

1. **Define features locally** (in VSCode or your editor)
2. **Build features** via Databricks Connect (execution on Databricks)
3. **Write to Unity Catalog** (features stored as Delta tables)

## Features

- **`pickup_zone_stats`**: Trip statistics aggregated by pickup zip code
- **`dropoff_zone_stats`**: Trip statistics aggregated by dropoff zip code
- **`route_stats`**: Statistics for pickup-dropoff route pairs

All features use the `samples.nyctaxi.trips` sample dataset available in Databricks.

## Setup

### 1. Environment Variables

Copy the template and add your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```
DATABRICKS_HOST=dbc-xxxxx.cloud.databricks.com
DATABRICKS_TOKEN=dapi_your_token
DATABRICKS_SANDBOX_CATALOG=sbx  # Your personal sandbox catalog
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/xxx  # Optional, for SQL queries
```

### 2. Install Dependencies

```bash
pip install mlforge[databricks-connect]
```

### 3. Verify Connection

Test that Databricks Connect works:

```bash
python verify_databricks_connect.py
```

Test writing to your sandbox:

```bash
python verify_databricks_write.py
```

## Usage

### Build Features (dbt-like workflow)

```bash
# Build all features to your sandbox catalog
cd examples/databricks-sql
mlforge build --profile dev

# Or build specific features
mlforge build --profile dev --features pickup_zone_stats
```

This will:
1. Connect to Databricks via Databricks Connect (serverless)
2. Execute PySpark transformations on Databricks
3. Write results to `{DATABRICKS_SANDBOX_CATALOG}.features.*`

### Query Your Features

In Databricks SQL or a notebook:

```sql
SELECT * FROM sbx.features.pickup_zone_stats LIMIT 10;
```

## How It Works

### Feature Definitions

Features are PySpark transformations:

```python
from pyspark.sql import DataFrame as SparkDataFrame
from pyspark.sql import functions as F
from mlforge import Source, feature

trips = Source(table="samples.nyctaxi.trips")

@feature(source=trips, keys=["pickup_zip"])
def pickup_zone_stats(df: SparkDataFrame) -> SparkDataFrame:
    return (
        df.groupBy("pickup_zip")
        .agg(
            F.count("*").alias("trip_count"),
            F.avg("fare_amount").alias("avg_fare"),
        )
    )
```

### Configuration (mlforge.yaml)

```yaml
databricks:
  host: ${oc.env:DATABRICKS_HOST}
  token: ${oc.env:DATABRICKS_TOKEN}
  serverless: true

profiles:
  dev:
    offline_store:
      KIND: unity-catalog
      catalog: ${oc.env:DATABRICKS_SANDBOX_CATALOG}
      schema: features
```

### Workflow

```
Local (VSCode)              Databricks
      │                          │
      │  mlforge build           │
      │  ─────────────────────►  │
      │                          │  1. Read source table
      │  Databricks Connect      │  2. Execute PySpark
      │  ◄─────────────────────  │  3. Write Delta table
      │                          │
      │  Feature in UC!          │
      ▼                          ▼
```

## Production Deployment

For production, features are built via Databricks Workflows:

1. Merge your feature branch to main
2. Databricks Workflow runs `mlforge build --profile prod`
3. Features written to production catalog

The same `definitions.py` works in both dev and prod - only the target catalog changes.
