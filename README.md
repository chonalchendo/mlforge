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

### 1. Initialize a project

```bash
mlforge init my-features --profile
cd my-features
```

This creates:

```
my-features/
├── src/my_features/
│   ├── definitions.py
│   ├── features.py
│   └── entities.py
├── data/
├── feature_store/
├── mlforge.yaml
└── pyproject.toml
```

### 2. Configure environments

Edit `mlforge.yaml` to configure your stores:

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
    online_store:
      KIND: redis
      host: ${oc.env:REDIS_HOST}
```

### 3. Define features

Edit `src/my_features/features.py`:

```python
import mlforge as mlf
import polars as pl

@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    timestamp="transaction_date",
    metrics=[
        mlf.Rolling(
            windows=["7d", "30d"],
            aggregations={"amount": ["sum", "mean", "count"]}
        )
    ],
    validators={
        "amount": [mlf.not_null(), mlf.greater_than(0)],
    },
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(["user_id", "transaction_date", "amount"])
```

### 4. Build features

```bash
mlforge build
```

### 5. Retrieve for training

```python
from my_features.definitions import defs

training_df = defs.get_training_data(
    features=["user_spend"],
    entity_df=labels_df,
    timestamp="label_time"
)
```

## Features

- **Feature Definition**: Define features with the `@mlf.feature` decorator
- **Rolling Aggregations**: Compute time-windowed metrics with `mlf.Rolling`
- **Data Validation**: Built-in validators for data quality
- **Semantic Versioning**: Automatic version detection (MAJOR/MINOR/PATCH)
- **Storage Backends**: Local filesystem, Amazon S3, Google Cloud Storage
- **Online Serving**: Redis-backed real-time feature retrieval
- **Entity Keys**: Surrogate key generation with `mlf.Entity`
- **Point-in-Time Joins**: Training data with temporal correctness
- **Environment Profiles**: Configure dev/staging/prod via `mlforge.yaml`
- **CLI Tools**: Build, validate, inspect, diff, rollback features
- **Git Collaboration**: Share definitions via Git, sync data locally

## CLI Reference

```bash
# Project setup
mlforge init my-project --profile    # Create new project with mlforge.yaml
mlforge profile --validate           # Validate store connectivity

# Build and validate
mlforge build                        # Build all features
mlforge build --online               # Build to online store (Redis)
mlforge build --profile production   # Use production profile
mlforge validate                     # Validate without building

# Discovery
mlforge list features                # List all features
mlforge list entities                # List all entities
mlforge list versions user_spend     # List feature versions
mlforge inspect feature user_spend   # Inspect feature metadata

# Version management
mlforge diff user_spend              # Compare versions
mlforge rollback user_spend --previous  # Rollback to previous version

# Team collaboration
mlforge sync                         # Rebuild from Git metadata
mlforge sync --dry-run               # Preview sync
```

## Environment Profiles

Configure different environments in `mlforge.yaml`:

```yaml
default_profile: dev

profiles:
  dev:
    offline_store:
      KIND: local
      path: ./feature_store

  staging:
    offline_store:
      KIND: s3
      bucket: staging-features
      prefix: v1

  production:
    offline_store:
      KIND: s3
      bucket: prod-features
      prefix: v1
    online_store:
      KIND: redis
      host: ${oc.env:REDIS_HOST}
      password: ${oc.env:REDIS_PASSWORD}
```

Switch profiles:

```bash
mlforge build --profile production
# or
export MLFORGE_PROFILE=production
mlforge build
```

## Online Serving

Build features to Redis for real-time inference:

```bash
mlforge build --online --profile production
```

Retrieve features:

```python
from my_features.definitions import defs

features = defs.get_online_features(
    features=["user_spend", "merchant_revenue"],
    entity_df=request_df,
)
```

## Entity Keys

Define entities for automatic surrogate key generation:

```python
import mlforge as mlf

user = mlf.Entity(
    name="user",
    join_key="user_id",
    from_columns=["first", "last", "dob"],
)

@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    entities=[user],
)
def user_spend(df):
    return df.group_by("user_id").agg(pl.col("amount").sum())
```

Entity keys are generated automatically during build and retrieval.

## Automatic Versioning

mlforge versions features using semantic versioning:

- **MAJOR** (2.0.0): Breaking changes (columns removed, dtype changed)
- **MINOR** (1.1.0): Additive changes (columns added, config changed)
- **PATCH** (1.0.1): Data refresh (same schema and config)

```bash
mlforge build                    # Creates v1.0.0
mlforge build --force            # Creates v1.0.1 (PATCH)
mlforge diff user_spend          # Compare versions
mlforge rollback user_spend 1.0.0  # Rollback if needed
```

## Git Collaboration

Share feature definitions via Git:

```bash
# Developer 1: Build and commit
mlforge build --features user_spend
git add feature_store/user_spend/
git commit -m "feat: add user_spend"
git push

# Developer 2: Pull and sync
git pull
mlforge sync  # Rebuilds data from metadata
```

## Documentation

Full documentation: [https://chonalchendo.github.io/mlforge](https://chonalchendo.github.io/mlforge)

## Requirements

- Python >= 3.13
- Polars >= 1.35.2

## License

MIT License - see [LICENSE](LICENSE) for details.
