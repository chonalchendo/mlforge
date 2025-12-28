# mlforge

[![PyPI version](https://badge.fury.io/py/mlforge-sdk.svg)](https://pypi.org/project/mlforge-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/mlforge-sdk.svg)](https://pypi.org/project/mlforge-sdk/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A simple feature store SDK for machine learning workflows. Build, validate, and serve ML features with point-in-time correctness.

## Installation

```bash
pip install mlforge-sdk
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add mlforge-sdk
```

## Quick Start

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
        "user_id": [mlf.not_null()],
    },
    description="User spending patterns over rolling windows"
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(["user_id", "transaction_date", "amount"])
```

Register features and build them:

```python
import mlforge as mlf
import my_features

defs = mlf.Definitions(
    name="my-project",
    features=[my_features],
    offline_store=mlf.LocalStore("./feature_store")
)

# Build features to storage
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

- **Feature Definition**: Define features with the `@mlf.feature` decorator
- **Rolling Aggregations**: Compute time-windowed metrics with `mlf.Rolling`
- **Data Validation**: Validate data with built-in validators (`mlf.not_null()`, `mlf.greater_than()`, etc.)
- **Storage Backends**: Local filesystem and Amazon S3 support
- **Point-in-Time Joins**: Retrieve training data with temporal correctness
- **Feature Metadata**: Automatic tracking of schemas, row counts, and lineage
- **CLI**: Build, validate, and inspect features from the command line

## CLI Usage

Build all features:

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

Validate features without building:

```bash
mlforge validate
```

List registered features:

```bash
mlforge list
```

Inspect feature metadata:

```bash
mlforge inspect user_spend
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
    return df
```

Available validators: `not_null`, `unique`, `greater_than`, `less_than`, `greater_than_or_equal`, `less_than_or_equal`, `in_range`, `matches_regex`, `is_in`

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

## Documentation

Full documentation is available at [https://chonalchendo.github.io/mlforge](https://chonalchendo.github.io/mlforge)

## Contributing

Contributions are welcome! Please see the [repository](https://github.com/chonalchendo/mlforge) for development setup and guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
