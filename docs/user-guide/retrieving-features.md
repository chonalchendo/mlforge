# Retrieving Features

Once features are built, use `get_training_data()` to join them to your entity DataFrame.

## Basic Usage

```python
from mlforge import get_training_data
import polars as pl

# Load your entity data (e.g., labels, predictions)
entities = pl.read_parquet("data/labels.parquet")

# Get features joined to entities
training_data = get_training_data(
    features=["user_total_spend", "user_avg_spend"],
    entity_df=entities
)
```

## Function Signature

```python
def get_training_data(
    features: list[str],
    entity_df: pl.DataFrame,
    store: str | Path | Store = "./feature_store",
    entities: list[EntityKeyTransform] | None = None,
    timestamp: str | None = None,
) -> pl.DataFrame
```

### Parameters

#### features (required)

List of feature names to retrieve. Must match the names of built features.

```python
training_data = get_training_data(
    features=["user_age", "user_tenure_days"],
    entity_df=entities
)
```

#### entity_df (required)

DataFrame containing entity keys and optionally timestamps. This is typically your:

- Training labels
- Prediction entities
- Evaluation dataset

```python
entities = pl.DataFrame({
    "user_id": ["u1", "u2", "u3"],
    "label": [0, 1, 0]
})
```

#### store (optional)

Path to feature store or a `Store` instance. Defaults to `"./feature_store"`.

```python
# Using default path
training_data = get_training_data(
    features=["user_age"],
    entity_df=entities
)

# Custom path
training_data = get_training_data(
    features=["user_age"],
    entity_df=entities,
    store="./my_features"
)

# Store instance
from mlforge import LocalStore

store = LocalStore("./my_features")
training_data = get_training_data(
    features=["user_age"],
    entity_df=entities,
    store=store
)
```

#### entities (optional)

List of entity key transforms to apply to `entity_df` before joining. Use this when your entity DataFrame doesn't have the required keys.

```python
from mlforge import entity_key

# Define transform
with_user_id = entity_key("first", "last", "dob", alias="user_id")

# Apply during retrieval
training_data = get_training_data(
    features=["user_spend_stats"],
    entity_df=raw_entities,
    entities=[with_user_id]  # Adds user_id column
)
```

See [Entity Keys](entity-keys.md) for details.

#### timestamp (optional)

Column name in `entity_df` to use for point-in-time joins. When specified, features with timestamps are joined using asof joins.

```python
training_data = get_training_data(
    features=["user_spend_mean_30d"],
    entity_df=transactions,
    timestamp="transaction_time"  # Point-in-time correct
)
```

See [Point-in-Time Correctness](point-in-time.md) for details.

## Join Behavior

### Standard Joins

When `timestamp` is not specified, features are joined using standard left joins:

```python
entities = pl.DataFrame({
    "user_id": ["u1", "u2", "u3"],
    "label": [0, 1, 0]
})

training_data = get_training_data(
    features=["user_total_spend"],
    entity_df=entities
)

# Joins on common columns (user_id)
```

### Point-in-Time Joins

When `timestamp` is specified and features have timestamps, asof joins are used:

```python
transactions = pl.DataFrame({
    "user_id": ["u1", "u1", "u2"],
    "transaction_time": ["2024-01-05", "2024-01-15", "2024-01-10"],
    "label": [0, 1, 0]
})

training_data = get_training_data(
    features=["user_spend_mean_30d"],  # Has feature_timestamp
    entity_df=transactions,
    timestamp="transaction_time"  # Asof join
)

# Features reflect data available at each transaction_time
```

### Join Key Detection

Join keys are automatically detected from common columns:

```python
# entity_df has: user_id, merchant_id, label
# feature has: user_id, merchant_id, total_spend

# Joins on: user_id, merchant_id
training_data = get_training_data(
    features=["user_merchant_spend"],
    entity_df=entities
)
```

Timestamp columns are excluded from join keys when performing asof joins.

## Complete Example

```python
from mlforge import get_training_data, entity_key
import polars as pl

# 1. Load entity data
transactions = pl.read_parquet("data/transactions.parquet")

# 2. Define entity transform
with_user_id = entity_key("first", "last", "dob", alias="user_id")

# 3. Retrieve features with point-in-time correctness
training_data = get_training_data(
    features=["user_spend_mean_30d", "user_total_spend"],
    entity_df=transactions,
    entities=[with_user_id],
    timestamp="trans_date_trans_time",
    store="./feature_store"
)

# 4. Use in training
from sklearn.ensemble import RandomForestClassifier

X = training_data.select(["user_spend_mean_30d", "user_total_spend"])
y = training_data.select("label")

model = RandomForestClassifier()
model.fit(X.to_pandas(), y.to_pandas())
```

## Error Handling

### Missing Features

If a requested feature hasn't been built:

```python
from mlforge import get_training_data

try:
    training_data = get_training_data(
        features=["nonexistent_feature"],
        entity_df=entities
    )
except ValueError as e:
    print(e)
    # Feature 'nonexistent_feature' not found. Run `mlforge build` first.
```

Build the feature first:

```bash
mlforge build definitions.py
```

### Missing Join Keys

If entity_df and features don't share common columns:

```python
# entity_df has: customer_id, label
# feature has: user_id, total_spend

try:
    training_data = get_training_data(
        features=["user_total_spend"],
        entity_df=entities
    )
except ValueError as e:
    print(e)
    # No common columns to join 'user_total_spend'.
```

Solution: Use entity transforms to add required keys:

```python
with_user_id = entity_key("customer_id", alias="user_id")

training_data = get_training_data(
    features=["user_total_spend"],
    entity_df=entities,
    entities=[with_user_id]
)
```

### Timestamp Type Mismatch

For asof joins, timestamp columns must have matching data types:

```python
# entity_df["event_time"] is String
# feature["feature_timestamp"] is Datetime

try:
    training_data = get_training_data(
        features=["temporal_feature"],
        entity_df=entities,
        timestamp="event_time"
    )
except ValueError as e:
    print(e)
    # Timestamp dtype mismatch: entity_df['event_time'] is String,
    # but feature has Datetime.
```

Solution: Convert timestamps before calling `get_training_data()`:

```python
entities = entities.with_columns(
    pl.col("event_time").str.to_datetime().alias("event_time")
)

training_data = get_training_data(
    features=["temporal_feature"],
    entity_df=entities,
    timestamp="event_time"
)
```

## Multiple Feature Stores

You can retrieve features from different stores by calling `get_training_data()` multiple times:

```python
# Features from store A
training_data = get_training_data(
    features=["user_age", "user_tenure"],
    entity_df=entities,
    store="./store_a"
)

# Add features from store B
training_data = get_training_data(
    features=["user_spend_stats"],
    entity_df=training_data,
    store="./store_b"
)
```

## Best Practices

### 1. Convert Timestamps Early

Always convert timestamp columns to proper datetime types before retrieval:

```python
entities = (
    pl.read_parquet("data/labels.parquet")
    .with_columns(
        pl.col("event_time").str.to_datetime("%Y-%m-%d %H:%M:%S")
    )
)

training_data = get_training_data(
    features=["temporal_features"],
    entity_df=entities,
    timestamp="event_time"
)
```

### 2. Use Type Hints

Add type hints for clarity:

```python
import polars as pl

entities: pl.DataFrame = pl.read_parquet("data/labels.parquet")

training_data: pl.DataFrame = get_training_data(
    features=["user_age"],
    entity_df=entities
)
```

### 3. Verify Features Exist

Check built features before retrieval:

```bash
mlforge list definitions.py
```

### 4. Handle Missing Values

Features may have nulls for entities not in the feature source:

```python
training_data = get_training_data(
    features=["user_total_spend"],
    entity_df=entities
)

# Fill nulls if needed
training_data = training_data.with_columns(
    pl.col("user_total_spend").fill_null(0)
)
```

## Next Steps

- [Entity Keys](entity-keys.md) - Work with surrogate keys and transforms
- [Point-in-Time Correctness](point-in-time.md) - Understand temporal joins
- [API Reference](../api/retrieval.md) - Detailed API documentation
