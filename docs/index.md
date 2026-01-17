# mlforge

A simple feature store SDK for machine learning workflows.

mlforge provides a lightweight, Python-first approach to feature engineering and management. It focuses on simplicity while delivering the essential capabilities you need: feature definition, building, and point-in-time correct retrieval.

## Key Features

- **Simple API** - Define features with a decorator, build with one command
- **Point-in-time correctness** - Automatic temporal joins prevent data leakage
- **Feature versioning** - Automatic semantic versioning with content-hash tracking
- **Multiple compute engines** - Choose Polars or DuckDB based on your needs
- **Online & offline stores** - Redis for real-time serving, Parquet for batch
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

## Why mlforge?

**Built for simplicity** - No infrastructure to manage, no complex configuration. Just Python functions and Parquet files.

**Point-in-time correctness by default** - Temporal features are automatically joined using asof joins, preventing data leakage in your training sets.

**Local development** - Perfect for prototyping, small projects, or teams that don't need distributed infrastructure.

## Installation

=== "pip"
    ```bash
    pip install mlforge-sdk
    ```

=== "uv"
    ```bash
    uv add mlforge-sdk
    ```

## Next Steps

- [Quickstart Guide](getting-started/quickstart.md) - Build your first feature in 5 minutes
- [Defining Features](user-guide/defining-features.md) - Learn the `@feature` decorator
- [CLI Reference](cli.md) - Command-line tools for building features
- [API Reference](api/core.md) - Complete API documentation
