# Quickstart

This guide will walk you through creating your first feature store in under 5 minutes.

## Setup

First, install mlforge:

=== "pip"
    ```bash
    pip install mlforge-sdk
    ```

=== "uv"
    ```bash
    uv add mlforge-sdk
    ```

## 1. Prepare Your Data

Create a simple dataset. For this example, we'll use transaction data:

```python
import polars as pl
from pathlib import Path

# Create sample transaction data
transactions = pl.DataFrame({
    "user_id": ["u1", "u1", "u2", "u2", "u3"],
    "amount": [10.0, 25.0, 50.0, 15.0, 100.0],
    "transaction_time": [
        "2024-01-01 10:00:00",
        "2024-01-02 11:00:00",
        "2024-01-01 12:00:00",
        "2024-01-03 09:00:00",
        "2024-01-01 15:00:00",
    ]
})

# Save to parquet
Path("data").mkdir(exist_ok=True)
transactions.write_parquet("data/transactions.parquet")
```

## 2. Define Features

Create a file called `features.py`:

```python
from mlforge import feature
import polars as pl

@feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    tags=["spending"],
    description="Total spend per user"
)
def user_total_spend(df: pl.DataFrame) -> pl.DataFrame:
    return df.group_by("user_id").agg(
        pl.col("amount").sum().alias("total_spend")
    )

@feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    tags=["spending"],
    description="Average transaction amount per user"
)
def user_avg_transaction(df: pl.DataFrame) -> pl.DataFrame:
    return df.group_by("user_id").agg(
        pl.col("amount").mean().alias("avg_transaction")
    )
```

## 3. Create Feature Definitions

Create `definitions.py`:

```python
from mlforge import Definitions, LocalStore
import features

defs = Definitions(
    name="quickstart",
    features=[features],
    offline_store=LocalStore("./feature_store")
)
```

## 4. Build Features

Materialize your features using the CLI:

```bash
mlforge build definitions.py
```

You should see output like:

```
Materializing user_total_spend
┌─────────┬─────────────┐
│ user_id │ total_spend │
├─────────┼─────────────┤
│ u1      │ 35.0        │
│ u2      │ 65.0        │
│ u3      │ 100.0       │
└─────────┴─────────────┘

Materializing user_avg_transaction
┌─────────┬─────────────────┐
│ user_id │ avg_transaction │
├─────────┼─────────────────┤
│ u1      │ 17.5            │
│ u2      │ 32.5            │
│ u3      │ 100.0           │
└─────────┴─────────────────┘

Built 2 features
```

## 5. Retrieve Features

Use features in your training pipeline:

```python
from mlforge import get_training_data
import polars as pl

# Load entity data (e.g., labels for training)
entities = pl.DataFrame({
    "user_id": ["u1", "u2", "u3"],
    "label": [0, 1, 0]
})

# Get training data with features
training_data = get_training_data(
    features=["user_total_spend", "user_avg_transaction"],
    entity_df=entities
)

print(training_data)
```

Output:

```
┌─────────┬───────┬─────────────┬─────────────────┐
│ user_id │ label │ total_spend │ avg_transaction │
├─────────┼───────┼─────────────┼─────────────────┤
│ u1      │ 0     │ 35.0        │ 17.5            │
│ u2      │ 1     │ 65.0        │ 32.5            │
│ u3      │ 0     │ 100.0       │ 100.0           │
└─────────┴───────┴─────────────┴─────────────────┘
```

## What Just Happened?

1. You defined features using the `@feature` decorator
2. Registered them with a `Definitions` object
3. Materialized them to local Parquet storage with `mlforge build`
4. Retrieved them for training using `get_training_data()`

## Next Steps

- [Learn more about defining features](../user-guide/defining-features.md)
- [Explore entity keys for complex joins](../user-guide/entity-keys.md)
- [Understand point-in-time correctness](../user-guide/point-in-time.md)
- [Browse the CLI reference](../cli.md)
