# mlforge

[![PyPI version](https://badge.fury.io/py/mlforge-sdk.svg)](https://pypi.org/project/mlforge-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/mlforge-sdk.svg)](https://pypi.org/project/mlforge-sdk/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A simple feature store SDK for machine learning workflows. Build, version, and serve ML features with point-in-time correctness.

## Installation

```bash
pip install mlforge-sdk
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add mlforge-sdk
```

## Quick Start

Define features with the `@feature` decorator:

```python
import mlforge as mlf
import polars as pl
from datetime import timedelta

@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    timestamp="transaction_date",
    interval=timedelta(days=1),
    metrics=[
        mlf.Rolling(
            windows=["7d", "30d"],
            aggregations={"amount": ["sum", "mean", "count"]}
        )
    ],
    validators={
        "amount": [mlf.not_null(), mlf.greater_than(0)],
    },
    description="User spending patterns over rolling windows"
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(["user_id", "transaction_date", "amount"])
```

Register and build features:

```python
import mlforge as mlf
import my_features

defs = mlf.Definitions(
    name="my-project",
    features=[my_features],
    offline_store=mlf.LocalStore("./feature_store")
)

# Build features with automatic versioning
defs.build()
```

Retrieve features for training with point-in-time correctness:

```python
import mlforge as mlf

training_df = mlf.get_training_data(
    entity_df=labels_df,
    features=["user_spend"],
    store=mlf.LocalStore("./feature_store"),
    timestamp="label_time"
)
```

## Features

- **🎯 Feature Definition**: Define features with the `@mlf.feature` decorator
- **📊 Rolling Aggregations**: Compute time-windowed metrics with `mlf.Rolling`
- **✅ Data Validation**: Built-in validators for data quality (`not_null`, `greater_than`, etc.)
- **🔢 Semantic Versioning**: Automatic version detection and bumping (MAJOR/MINOR/PATCH)
- **💾 Storage Backends**: Local filesystem and Amazon S3 support
- **⏰ Point-in-Time Joins**: Retrieve training data with temporal correctness
- **📝 Feature Metadata**: Automatic tracking of schemas, versions, and change history
- **🔧 CLI Tools**: Build, validate, inspect, and sync features from the command line
- **🤝 Git Collaboration**: Share feature definitions via Git, sync data locally

## CLI Usage

### Build Features

Build all features with automatic versioning:

```bash
mlforge build
```

Build specific features:

```bash
mlforge build --features user_spend,merchant_spend
```

Build features by tag:

```bash
mlforge build --tags users
```

Override automatic versioning:

```bash
mlforge build --version 2.0.0
```

### Versioning

List all versions of a feature:

```bash
mlforge versions user_spend
```

Inspect a specific version:

```bash
mlforge inspect user_spend --version 1.0.0
```

### Validation

Validate features without building:

```bash
mlforge validate
```

Validate specific features:

```bash
mlforge validate --features user_spend
```

### Feature Discovery

List registered features:

```bash
mlforge list
```

List features by tag:

```bash
mlforge list --tags users
```

Inspect feature metadata:

```bash
mlforge inspect user_spend
```

Display feature manifest:

```bash
mlforge manifest
```

### Team Collaboration

Sync features after pulling metadata from Git:

```bash
mlforge sync
```

Preview what would be synced:

```bash
mlforge sync --dry-run
```

Sync specific features:

```bash
mlforge sync --features user_spend
```

Force sync even if source data changed:

```bash
mlforge sync --force
```

## Automatic Versioning

mlforge automatically versions your features using semantic versioning:

- **MAJOR** (2.0.0): Breaking changes (columns removed, dtype changed)
- **MINOR** (1.1.0): Additive changes (columns added, config changed)
- **PATCH** (1.0.1): Data refresh (same schema and config)

```python
# First build creates v1.0.0
defs.build()

# Rebuild with same schema → v1.0.1 (PATCH)
defs.build(force=True)

# Add a column → v1.1.0 (MINOR)
# Remove a column → v2.0.0 (MAJOR)
```

Features are stored in versioned directories:

```
feature_store/
├── user_spend/
│   ├── 1.0.0/
│   │   ├── data.parquet
│   │   └── .meta.json
│   ├── 1.0.1/
│   │   └── ...
│   ├── _latest.json
│   └── .gitignore
```

## Git Collaboration

mlforge enables teams to share feature definitions via Git:

1. **Metadata is committed**: `.meta.json` and `_latest.json` files
2. **Data is ignored**: Auto-generated `.gitignore` excludes `data.parquet`
3. **Teammates sync locally**: Run `mlforge sync` to rebuild data

```bash
# Developer 1: Build and commit metadata
mlforge build --features user_spend
git add feature_store/user_spend/
git commit -m "feat: add user_spend feature"
git push

# Developer 2: Pull and sync
git pull
mlforge sync  # Rebuilds data.parquet from metadata
```

## Validators

Built-in validators for data quality:

```python
import mlforge as mlf

@mlf.feature(
    keys=["id"],
    source="data.parquet",
    validators={
        "email": [mlf.not_null(), mlf.matches_regex(r"^[\w.-]+@[\w.-]+\.\w+$")],
        "age": [mlf.not_null(), mlf.in_range(0, 120)],
        "status": [mlf.is_in(["active", "inactive"])],
        "score": [mlf.greater_than_or_equal(0), mlf.less_than_or_equal(100)],
    }
)
def validated_feature(df):
    return df.select(["id", "email", "age", "status", "score"])
```

Available validators:
- `not_null()` - No null values
- `unique()` - All values unique
- `greater_than(value)` - All values > threshold
- `less_than(value)` - All values < threshold
- `greater_than_or_equal(value)` - All values ≥ threshold
- `less_than_or_equal(value)` - All values ≤ threshold
- `in_range(min, max)` - All values within range
- `matches_regex(pattern)` - All values match regex
- `is_in(values)` - All values in allowed set

## Storage Backends

### Local Storage

```python
import mlforge as mlf

store = mlf.LocalStore("./feature_store")
```

### S3 Storage

```python
import mlforge as mlf

store = mlf.S3Store(
    bucket="my-features",
    prefix="prod/features",
    region="us-west-2"
)
```

S3 credentials are resolved via standard AWS credential chain (environment variables, `~/.aws/credentials`, or IAM roles).

## Entity Keys

Create reusable entity key transformations:

```python
import mlforge as mlf

# Create surrogate key from multiple columns
with_user_id = mlf.entity_key("first_name", "last_name", "dob", alias="user_id")

@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet"
)
def user_feature(df):
    return df.pipe(with_user_id).select(["user_id", "amount"])
```

Generate surrogate keys directly:

```python
import polars as pl
import mlforge as mlf

df = pl.DataFrame({
    "first": ["Alice", "Bob"],
    "last": ["Smith", "Jones"],
})

df = mlf.surrogate_key(df, ["first", "last"], alias="user_id")
# Adds column: user_id = hash("Alice:Smith"), hash("Bob:Jones")
```

## Point-in-Time Correctness

Retrieve training data with temporal correctness to prevent label leakage:

```python
import mlforge as mlf
import polars as pl

# Labels with timestamps
labels_df = pl.DataFrame({
    "user_id": ["u1", "u2", "u3"],
    "label_time": ["2024-01-15", "2024-01-16", "2024-01-17"],
    "label": [1, 0, 1],
})

# Get features as they existed at label_time
training_df = mlf.get_training_data(
    entity_df=labels_df,
    features=["user_spend"],
    store=mlf.LocalStore("./feature_store"),
    timestamp="label_time"
)
```

This ensures that features computed at `2024-01-15` only use data available before that date, preventing future information from leaking into training data.

## Documentation

Full documentation is available at [https://chonalchendo.github.io/mlforge](https://chonalchendo.github.io/mlforge)

## Requirements

- Python ≥ 3.13
- Polars ≥ 1.35.2

## Contributing

Contributions are welcome! Please see the [repository](https://github.com/chonalchendo/mlforge) for development setup and guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
