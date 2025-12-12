# Point-in-Time Correctness

Point-in-time (PIT) correctness ensures that features used for training or prediction reflect only the data available at a specific moment in time. This prevents data leakage, where future information accidentally influences model training.

## The Problem: Data Leakage

Consider a fraud detection model trained on historical transactions:

```python
# WRONG - causes data leakage
transactions = pl.read_parquet("data/transactions.parquet")
user_stats = pl.read_parquet("features/user_total_spend.parquet")

# Standard join uses ALL user data
training_data = transactions.join(user_stats, on="user_id")
```

**Problem**: For a transaction on 2024-01-05, the joined `user_total_spend` includes transactions from 2024-01-06, 2024-01-07, etc. The model learns from future data it wouldn't have during real-time inference.

## The Solution: Asof Joins

An asof join matches each entity to the most recent feature value available **at or before** the entity's timestamp:

```python
# CORRECT - point-in-time correct
from mlforge import get_training_data

training_data = get_training_data(
    features=["user_spend_mean_30d"],
    entity_df=transactions,
    timestamp="transaction_time"  # Enables asof join
)
```

Now for a transaction on 2024-01-05, `user_spend_mean_30d` reflects only data up to 2024-01-05.

## Temporal Features

To enable PIT correctness, features must include a timestamp column.

### Defining Temporal Features

Use the `timestamp` parameter in `@feature`:

```python
from mlforge import feature
import polars as pl

@feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    timestamp="feature_timestamp",  # Enables PIT joins
    description="User mean spend over 30-day windows"
)
def user_spend_mean_30d(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df
        .with_columns(
            pl.col("trans_date_trans_time")
            .str.to_datetime("%Y-%m-%d %H:%M:%S")
            .alias("trans_dt")
        )
        .sort("trans_dt")
        .group_by_dynamic(
            "trans_dt",
            every="1d",      # Daily aggregation
            period="30d",    # 30-day rolling window
            by="user_id"
        )
        .agg(pl.col("amt").mean().alias("user_spend_mean_30d"))
        .rename({"trans_dt": "feature_timestamp"})  # IMPORTANT
    )
```

**Key points**:

1. Declare `timestamp="feature_timestamp"` in the decorator
2. Output DataFrame must have a `feature_timestamp` column
3. Values in `feature_timestamp` indicate when each feature value became available

### Timestamp Convention

mlforge uses `feature_timestamp` as the standard column name. Always rename your time column:

```python
.rename({"event_time": "feature_timestamp"})
```

This ensures `get_training_data()` correctly identifies the timestamp for asof joins.

## Using Point-in-Time Joins

### Step 1: Materialize Temporal Features

Build features with timestamps:

```bash
mlforge build definitions.py
```

### Step 2: Prepare Entity Data

Ensure your entity DataFrame has a timestamp column:

```python
import polars as pl

transactions = pl.read_parquet("data/transactions.parquet")

# Convert to datetime if needed
transactions = transactions.with_columns(
    pl.col("trans_date_trans_time")
    .str.to_datetime("%Y-%m-%d %H:%M:%S")
    .alias("transaction_time")
)
```

### Step 3: Retrieve with Point-in-Time Correctness

Pass the `timestamp` parameter:

```python
from mlforge import get_training_data

training_data = get_training_data(
    features=["user_spend_mean_30d"],
    entity_df=transactions,
    timestamp="transaction_time"  # Enables asof join
)
```

## How Asof Joins Work

Given:

- **Entity DataFrame** (transactions):
  ```
  ┌─────────┬──────────────────────┬───────┐
  │ user_id │ transaction_time     │ label │
  ├─────────┼──────────────────────┼───────┤
  │ u1      │ 2024-01-05 10:00:00  │ 0     │
  │ u1      │ 2024-01-15 14:00:00  │ 1     │
  │ u2      │ 2024-01-10 09:00:00  │ 0     │
  └─────────┴──────────────────────┴───────┘
  ```

- **Feature DataFrame** (user_spend_mean_30d):
  ```
  ┌─────────┬──────────────────────┬────────────────────┐
  │ user_id │ feature_timestamp    │ user_spend_mean_30d│
  ├─────────┼──────────────────────┼────────────────────┤
  │ u1      │ 2024-01-01 00:00:00  │ 20.0               │
  │ u1      │ 2024-01-10 00:00:00  │ 25.0               │
  │ u1      │ 2024-01-20 00:00:00  │ 30.0               │
  │ u2      │ 2024-01-05 00:00:00  │ 15.0               │
  │ u2      │ 2024-01-15 00:00:00  │ 18.0               │
  └─────────┴──────────────────────┴────────────────────┘
  ```

The asof join produces:

```
┌─────────┬──────────────────────┬───────┬────────────────────┐
│ user_id │ transaction_time     │ label │ user_spend_mean_30d│
├─────────┼──────────────────────┼───────┼────────────────────┤
│ u1      │ 2024-01-05 10:00:00  │ 0     │ 20.0               │  ← 2024-01-01 feature
│ u1      │ 2024-01-15 14:00:00  │ 1     │ 25.0               │  ← 2024-01-10 feature
│ u2      │ 2024-01-10 09:00:00  │ 0     │ 15.0               │  ← 2024-01-05 feature
└─────────┴──────────────────────┴───────┴────────────────────┘
```

Each transaction gets the most recent feature value available **before** its timestamp.

## Mixed Features

You can mix temporal and non-temporal features in a single retrieval:

```python
training_data = get_training_data(
    features=[
        "user_age",             # Non-temporal (standard join)
        "user_spend_mean_30d",  # Temporal (asof join)
    ],
    entity_df=transactions,
    timestamp="transaction_time"
)
```

- `user_age`: Joined with standard left join on `user_id`
- `user_spend_mean_30d`: Joined with asof join on `user_id` and `transaction_time`

## Complete Example

```python
# features.py
from mlforge import feature, entity_key
import polars as pl

with_user_id = entity_key("first", "last", "dob", alias="user_id")

@feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    timestamp="feature_timestamp",
    description="User 7-day rolling average spend"
)
def user_spend_mean_7d(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df
        .pipe(with_user_id)
        .with_columns(
            pl.col("trans_date_trans_time")
            .str.to_datetime("%Y-%m-%d %H:%M:%S")
            .alias("trans_dt")
        )
        .sort("trans_dt")
        .group_by_dynamic(
            "trans_dt",
            every="1d",
            period="7d",
            by="user_id"
        )
        .agg(pl.col("amt").mean().alias("user_spend_mean_7d"))
        .rename({"trans_dt": "feature_timestamp"})
    )
```

```python
# definitions.py
from mlforge import Definitions, LocalStore
import features

defs = Definitions(
    name="fraud-detection",
    features=[features],
    offline_store=LocalStore("./feature_store")
)
```

```bash
# Build features
mlforge build definitions.py
```

```python
# train.py
from mlforge import get_training_data, entity_key
import polars as pl

# Load and prepare entity data
transactions = (
    pl.read_parquet("data/transactions.parquet")
    .with_columns(
        pl.col("trans_date_trans_time")
        .str.to_datetime("%Y-%m-%d %H:%M:%S")
        .alias("transaction_time")
    )
)

# Define entity transform
with_user_id = entity_key("first", "last", "dob", alias="user_id")

# Retrieve features with PIT correctness
training_data = get_training_data(
    features=["user_spend_mean_7d"],
    entity_df=transactions,
    entities=[with_user_id],
    timestamp="transaction_time"
)

# Train model
X = training_data.select("user_spend_mean_7d")
y = training_data.select("is_fraud")
```

## Common Pitfalls

### 1. Forgetting to Rename Timestamp

```python
# WRONG - timestamp not renamed
@feature(
    keys=["user_id"],
    source="data/events.parquet",
    timestamp="feature_timestamp"
)
def user_event_count(df):
    return (
        df
        .group_by_dynamic("event_time", every="1d", by="user_id")
        .agg(pl.col("event_id").count())
        # Missing: .rename({"event_time": "feature_timestamp"})
    )
```

**Fix**: Always rename to `feature_timestamp`:

```python
.rename({"event_time": "feature_timestamp"})
```

### 2. Timestamp Type Mismatch

```python
# Entity timestamp is String
entities = pl.DataFrame({
    "user_id": ["u1"],
    "event_time": ["2024-01-05 10:00:00"]  # String type
})

# Feature timestamp is Datetime
# Asof join will fail!
```

**Fix**: Convert to datetime before retrieval:

```python
entities = entities.with_columns(
    pl.col("event_time").str.to_datetime().alias("event_time")
)
```

### 3. Not Sorting Data

Asof joins require sorted data. mlforge handles this automatically, but if you see warnings:

```python
UserWarning: Sortedness of columns cannot be checked
```

It's safe to ignore—mlforge sorts internally.

### 4. Using Future Data

Ensure feature timestamps don't include future events:

```python
# WRONG - includes future transactions
.group_by_dynamic("trans_dt", every="1d", period="30d", by="user_id")

# Event on 2024-01-05 computes features from 2024-01-05 to 2024-02-04
# This includes future data!
```

**Fix**: Use past-looking windows:

```python
# Compute trailing 30 days BEFORE each date
.rolling(
    index_column="trans_dt",
    period="30d",
    closed="left",  # Exclude current day
    by="user_id"
)
```

## Best Practices

### 1. Always Use Timestamps for Time-Series Features

If your feature uses temporal data, declare a timestamp:

```python
@feature(
    keys=["user_id"],
    source="data/events.parquet",
    timestamp="feature_timestamp"  # Required for temporal features
)
```

### 2. Test for Data Leakage

Verify features don't include future data:

```python
# Check feature values
feature_df = store.read("user_spend_mean_30d")

# For each row, verify feature_timestamp <= latest event used
```

### 3. Use Consistent Datetime Format

Convert timestamps to datetime early:

```python
df = (
    pl.read_parquet("data/events.parquet")
    .with_columns(
        pl.col("event_time").str.to_datetime("%Y-%m-%d %H:%M:%S")
    )
)
```

### 4. Document Temporal Logic

Add comments explaining window logic:

```python
# Compute 7-day trailing average (excluding current day)
.rolling(index_column="date", period="7d", closed="left", by="user_id")
```

## Next Steps

- [Retrieving Features](retrieving-features.md) - Complete retrieval guide
- [Building Features](building-features.md) - Materialize temporal features
- [API Reference - Retrieval](../api/retrieval.md) - Detailed API docs
