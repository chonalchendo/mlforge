# Fraud Detection Example

A comprehensive fraud detection pipeline using mlforge's feature store capabilities.

## Overview

This example demonstrates:
- **Multiple entity types** (user, merchant, card, user-merchant pairs)
- **Rolling aggregations** at different granularities (1h, 1d, 7d, 30d)
- **Point-in-time correct** training data retrieval
- **Real-time feature serving** with Redis
- **Model training** with scikit-learn

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Fraud Detection Pipeline                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │ Transactions │────▶│   Features   │────▶│    Model     │    │
│  │    Source    │     │              │     │   Training   │    │
│  └──────────────┘     │ - user_spend │     └──────────────┘    │
│                       │ - merchant   │                          │
│                       │ - card_vel   │     ┌──────────────┐    │
│                       │ - user_merch │────▶│   Real-time  │    │
│                       └──────────────┘     │   Serving    │    │
│                              │             └──────────────┘    │
│                              ▼                    │             │
│                       ┌──────────────┐           ▼             │
│                       │    Stores    │     ┌──────────────┐    │
│                       │ Local │Redis │     │    Fraud     │    │
│                       └──────────────┘     │   Scoring    │    │
│                                            └──────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Features

### Entity Definitions

| Entity | Join Key | Generated From | Purpose |
|--------|----------|----------------|---------|
| `user` | `user_id` | first, last, dob | User spending patterns |
| `merchant` | `merchant_id` | merchant name | Merchant behavior |
| `card` | `card_id` | cc_num | Card velocity (fraud signal) |
| `user_merchant` | `[user_id, merchant_id]` | composite | Interaction frequency |

### Feature Definitions

| Feature | Entity | Windows | Aggregations |
|---------|--------|---------|--------------|
| `user_spend` | user | 1d, 7d, 30d | sum, mean, count, std |
| `merchant_spend` | merchant | 1d, 7d, 30d | sum, mean, count, std |
| `card_velocity` | card | 1d, 7d | count |

## Quick Start

### 1. Install Dependencies

From the repository root:

```bash
uv sync
```

### 2. Build Features (Offline Store)

```bash
cd examples/fraud-detection
mlforge build
```

This builds all features to the local feature store (`./feature_store/`).

### 3. Train Model

```bash
uv run python src/fraud/train.py
```

Expected output:
```
Entity DataFrame shape: (1000, 20)
Fraud rate: 12.50%

Training DataFrame shape: (1000, 45)
Columns: ['user_id', 'amt__sum__1d', 'amt__mean__1d', ...]

Feature columns (36):
  - amt__sum__1d
  - amt__mean__1d
  ...

Model Performance:
  Train accuracy: 0.987
  Test accuracy:  0.923

Top 10 Feature Importances:
  amt__sum__7d: 0.1234
  ...
```

### 4. Real-time Serving (Optional)

Start Redis:

```bash
docker-compose up -d
```

Build to online store:

```bash
mlforge build --profile online --online
```

Run serving example:

```bash
uv run python src/fraud/serve.py
```

## Project Structure

```
fraud-detection/
├── src/fraud/
│   ├── __init__.py
│   ├── entities.py      # Entity definitions
│   ├── features.py      # Feature definitions with metrics
│   ├── definitions.py   # Definitions object
│   ├── train.py         # Model training example
│   └── serve.py         # Real-time serving example
├── data/
│   └── transactions.parquet  # Transaction data
├── feature_store/       # Built features (gitignored)
├── mlforge.yaml         # Profile configuration
├── docker-compose.yml   # Redis container
├── pyproject.toml
└── README.md
```

## Key Concepts Demonstrated

### 1. Multiple Entity Types

```python
user = mlf.Entity(
    name="user",
    join_key="user_id",
    from_columns=["first", "last", "dob"],  # Surrogate key from PII
)

card = mlf.Entity(
    name="card",
    join_key="card_id",
    from_columns=["cc_num"],  # Surrogate key from card number
)
```

### 2. Rolling Aggregations

```python
spend_metrics = mlf.Rolling(
    windows=["1d", "7d", "30d"],
    aggregations={"amt": ["sum", "mean", "count", "std"]},
)

@mlf.feature(
    source=transactions,
    entities=[user],
    timestamp=timestamp,
    interval=timedelta(days=1),
    metrics=[spend_metrics],
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    ...
```

### 3. Point-in-Time Correct Training Data

```python
training_df = get_training_data(
    features=["user_spend", "merchant_spend", "card_velocity"],
    entity_df=entity_df,
    entities=[with_user_id, with_merchant_id, with_card_id],
    timestamp="transaction_date",  # Features joined as of this time
    store="./feature_store",
)
```

### 4. Real-Time Feature Serving

```python
result = get_online_features(
    features=["user_spend", "merchant_spend", "card_velocity"],
    entity_df=request_df,
    store=RedisStore(host="localhost"),
    entities=[with_user_id, with_merchant_id, with_card_id],
)
```

## CLI Commands

```bash
# List all features
mlforge list features

# List features by tag
mlforge list features --tags "spending"

# Inspect a feature
mlforge inspect feature user_spend

# Build specific features
mlforge build --features "user_spend,card_velocity"

# Build by tag
mlforge build --tags "velocity"

# Show current profile
mlforge profile

# Use a different profile
mlforge build --profile online
```

## Extending the Example

### Add New Features

1. Define entity in `entities.py` (if new)
2. Add feature function in `features.py`
3. Rebuild: `mlforge build`

### Add New Aggregations

```python
# Add new aggregations to existing metrics
spend_metrics = mlf.Rolling(
    windows=["1d", "7d", "30d"],
    aggregations={
        "amt": ["sum", "mean", "count", "std", "min", "max"],
    },
)
```

### Add Validators

```python
@mlf.feature(
    validators={
        "amt": [mlf.greater_than_or_equal(value=0)],
        "user_id": [mlf.not_null()],
    },
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    ...
```

## Cleanup

```bash
# Stop Redis
docker-compose down

# Remove feature store
rm -rf feature_store/

# Remove Docker volumes and images (optional - frees disk space)
docker-compose down -v --rmi local
docker system prune -f
```
