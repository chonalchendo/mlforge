# mlforge

A simple feature store SDK for machine learning workflows.

mlforge provides a lightweight, Python-first approach to feature engineering and management. It focuses on simplicity while delivering the essential capabilities you need: feature definition, building, and point-in-time correct retrieval.

## Key Features

- **Simple API** - Define features with a decorator, build with one command
- **Point-in-time correctness** - Automatic temporal joins prevent data leakage
- **Feature versioning** - Automatic semantic versioning with content-hash tracking
- **Multiple compute engines** - Choose Polars, DuckDB, or PySpark based on your needs
- **Flexible storage** - Local, S3, GCS, or Databricks Unity Catalog
- **Online serving** - Redis, DynamoDB, or Databricks Online Tables for real-time inference
- **Type-safe** - Built on Polars with unified type system across engines
- **CLI included** - Build, list, sync, and manage features from the command line

## Quick Example

```python
from mlforge import feature, Definitions, LocalStore
import polars as pl

# Define a feature
@feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    timestamp="transaction_time",
    description="User spending statistics"
)
def user_spend_stats(df: pl.DataFrame) -> pl.DataFrame:
    return df.group_by("user_id").agg(
        pl.col("amount").mean().alias("avg_spend"),
        pl.col("amount").count().alias("transaction_count")
    )

# Register and build
defs = Definitions(
    name="my-project",
    features=[user_spend_stats],
    offline_store=LocalStore("./feature_store")
)

defs.build()
```

Retrieve features with point-in-time correctness:

```python
from mlforge import get_training_data
import polars as pl

# Load your entity data
entities = pl.read_parquet("data/labels.parquet")

# Get features joined correctly (supports versioning)
training_data = get_training_data(
    features=[
        "user_spend_stats",           # Latest version
        ("merchant_risk", "1.0.0"),   # Pinned version
    ],
    entity_df=entities,
    timestamp="event_time"
)
```

Real-time inference with Redis:

```python
from mlforge import get_online_features
from mlforge.stores import RedisStore

store = RedisStore(host="localhost")

# Retrieve features for inference
features_df = get_online_features(
    features=["user_spend_stats"],
    entity_df=request_df,
    store=store,
    entities=[with_user_id],
)
```

## Storage Options

| Type | Options | Use Case |
|------|---------|----------|
| **Offline** | LocalStore, S3Store, GCSStore, UnityCatalogStore | Batch training data |
| **Online** | RedisStore, DynamoDBStore, DatabricksOnlineStore | Real-time inference |

## Why mlforge?

**Built for simplicity** - No infrastructure to manage, no complex configuration. Just Python functions and Parquet files.

**Point-in-time correctness by default** - Temporal features are automatically joined using asof joins, preventing data leakage in your training sets.

**Flexible deployment** - Start local, scale to cloud. Works with AWS, GCP, or Databricks.

## Installation

=== "pip"
    ```bash
    pip install mlforge-sdk
    ```

=== "uv"
    ```bash
    uv add mlforge-sdk
    ```

### Optional Dependencies

```bash
# Cloud storage
pip install mlforge-sdk[s3]       # Amazon S3
pip install mlforge-sdk[gcs]      # Google Cloud Storage

# Online stores
pip install mlforge-sdk[redis]    # Redis
pip install mlforge-sdk[dynamodb] # AWS DynamoDB

# Databricks
pip install mlforge-sdk[databricks]  # Unity Catalog + Online Tables

# Compute engines
pip install mlforge-sdk[duckdb]   # DuckDB engine
```

## Next Steps

- [Quickstart Guide](getting-started/quickstart.md) - Build your first feature in 5 minutes
- [Defining Features](user-guide/defining-features.md) - Learn the `@feature` decorator
- [Storage Backends](user-guide/storage-backends.md) - Configure offline storage
- [Online Stores](user-guide/online-stores.md) - Set up real-time serving
- [CLI Reference](cli.md) - Command-line tools for building features
- [API Reference](api/core.md) - Complete API documentation
