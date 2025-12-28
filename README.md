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

Define features using the `@feature` decorator:

```python
from datetime import timedelta
import polars as pl
from mlforge import feature, Rolling, not_null, greater_than

@feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    timestamp="transaction_date",
    interval=timedelta(days=1),
    metrics=[
        Rolling(
            windows=["7d", "30d"],
            aggregations={"amount": ["sum", "mean", "count"]}
        )
    ],
    validators={
        "amount": [not_null(), greater_than(0)],
        "user_id": [not_null()],
    },
    description="User spending patterns over rolling windows"
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(["user_id", "transaction_date", "amount"])
```

Register features and build them:

```python
from mlforge import Definitions, LocalStore
import my_features

defs = Definitions(
    name="my-project",
    features=[my_features],
    offline_store=LocalStore("./feature_store")
)

# Build features to storage
defs.build()
```

Retrieve features for training with point-in-time correctness:

```python
from mlforge import get_training_data

training_df = get_training_data(
    entity_df=labels_df,
    features=["user_spend"],
    store=LocalStore("./feature_store"),
    timestamp="label_time"
)
```

## Features

- **Feature Definition**: Define features with the `@feature` decorator
- **Rolling Aggregations**: Compute time-windowed metrics (sum, mean, count, etc.)
- **Data Validation**: Validate feature data before materialization with built-in validators
- **Storage Backends**: Local filesystem (Parquet) and Amazon S3 support
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

View feature manifest:

```bash
mlforge manifest
```

## Validators

Built-in validators for data quality:

```python
from mlforge import (
    not_null,
    unique,
    greater_than,
    less_than,
    greater_than_or_equal,
    less_than_or_equal,
    in_range,
    matches_regex,
    is_in,
)

@feature(
    keys=["id"],
    source="data.parquet",
    validators={
        "email": [not_null(), matches_regex(r"^[\w.-]+@[\w.-]+\.\w+$")],
        "age": [not_null(), in_range(0, 120)],
        "status": [is_in(["active", "inactive"])],
    }
)
def validated_feature(df):
    return df
```

## Storage Backends

### Local Storage

```python
from mlforge import LocalStore

store = LocalStore("./feature_store")
```

### S3 Storage

```python
from mlforge import S3Store

store = S3Store(
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
