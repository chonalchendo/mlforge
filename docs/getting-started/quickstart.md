# Quickstart

Build your first feature store in under 5 minutes.

## 1. Initialize a Project

```bash
mlforge init my-features --profile
cd my-features
```

This creates:

```
my-features/
├── src/my_features/
│   ├── definitions.py    # Feature registry
│   ├── features.py       # Feature definitions
│   └── entities.py       # Entity definitions
├── data/                 # Source data
├── feature_store/        # Built features
├── mlforge.yaml          # Environment profiles
└── pyproject.toml
```

## 2. Add Sample Data

Create sample transaction data:

```python
import polars as pl
from pathlib import Path

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

Path("data").mkdir(exist_ok=True)
transactions.write_parquet("data/transactions.parquet")
```

## 3. Define Features

Edit `src/my_features/features.py`:

```python
import mlforge as mlf
import polars as pl

@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    description="Total spend per user"
)
def user_total_spend(df: pl.DataFrame) -> pl.DataFrame:
    return df.group_by("user_id").agg(
        pl.col("amount").sum().alias("total_spend")
    )

@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    description="Average transaction amount per user"
)
def user_avg_transaction(df: pl.DataFrame) -> pl.DataFrame:
    return df.group_by("user_id").agg(
        pl.col("amount").mean().alias("avg_transaction")
    )
```

## 4. Build Features

```bash
mlforge build
```

Output:

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
from my_features.definitions import defs
import polars as pl

# Entity data (e.g., labels for training)
entities = pl.DataFrame({
    "user_id": ["u1", "u2", "u3"],
    "label": [0, 1, 0]
})

# Get training data
training_data = defs.get_training_data(
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

## 6. Explore Your Features

```bash
# List features
mlforge list features

# Inspect a feature
mlforge inspect feature user_total_spend

# List versions
mlforge list versions user_total_spend
```

## What You Built

1. **Initialized** a project with `mlforge init`
2. **Defined** features using the `@mlf.feature` decorator
3. **Built** features to local storage with `mlforge build`
4. **Retrieved** features for training with `defs.get_training_data()`

## Environment Profiles

Your `mlforge.yaml` configures different environments:

```yaml
default_profile: dev

profiles:
  dev:
    offline_store:
      KIND: local
      path: ./feature_store

  production:
    offline_store:
      KIND: s3
      bucket: ${oc.env:S3_BUCKET}
      prefix: features
```

Build to production:

```bash
S3_BUCKET=my-bucket mlforge build --profile production
```

## Next Steps

- [Defining Features](../user-guide/defining-features.md) - Feature options and patterns
- [Entity Keys](../user-guide/entity-keys.md) - Surrogate key generation
- [Point-in-Time Correctness](../user-guide/point-in-time.md) - Temporal joins
- [Online Stores](../user-guide/online-stores.md) - Redis for real-time serving
- [CLI Reference](../cli.md) - All CLI commands
