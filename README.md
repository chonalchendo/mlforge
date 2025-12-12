# mlforge

[![PyPI version](https://badge.fury.io/py/mlforge-sdk.svg)](https://pypi.org/project/mlforge-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/mlforge-sdk.svg)](https://pypi.org/project/mlforge-sdk/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A simple feature store SDK for machine learning workflows.

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
import polars as pl
from mlforge import feature, entity_key

# Create reusable entity key transforms
with_user_id = entity_key("first", "last", "dob", alias="user_id")

@feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    description="Total spend by user"
)
def user_total_spend(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.pipe(with_user_id)
        .group_by("user_id")
        .agg(pl.col("amt").sum().alias("total_spend"))
    )
```

Register features and materialize them:

```python
from mlforge import Definitions, LocalStore
import my_features

defs = Definitions(
    name="my-project",
    features=[my_features],
    offline_store=LocalStore("./feature_store")
)

# Materialize features to storage
defs.materialize()
```

Retrieve features for training:

```python
from mlforge import get_training_data

training_df = get_training_data(
    features=["user_total_spend"],
    entity_df=transactions,
    entities=[with_user_id],
    timestamp="trans_date_trans_time"  # Point-in-time correct joins
)
```

## Features

- **Simple API**: Define features with a `@feature` decorator
- **Entity Keys**: Generate surrogate keys from natural keys using `entity_key()`
- **Local Storage**: Persist features to Parquet with `LocalStore`
- **Point-in-Time Joins**: Retrieve training data with temporal correctness using `get_training_data()`
- **CLI**: Build and list features from the command line

## CLI Usage

Build features:

```bash
mlforge build definitions.py
```

Build specific features:

```bash
mlforge build definitions.py --features user_total_spend,merchant_total_spend
```

List registered features:

```bash
mlforge list definitions.py
```

## Documentation

Full documentation is available at [https://chonalchendo.github.io/mlforge](https://chonalchendo.github.io/mlforge)

## Contributing

Contributions are welcome! Please see the [repository](https://github.com/chonalchendo/mlforge) for development setup and guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
