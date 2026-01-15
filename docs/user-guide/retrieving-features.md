# Retrieving Features

mlforge provides two methods on your `Definitions` object for retrieving features:

| Method | Use Case | Store Type | Point-in-Time |
|--------|----------|------------|---------------|
| `defs.get_training_data()` | Training, batch scoring | Offline (LocalStore, S3Store) | Yes |
| `defs.get_online_features()` | Real-time inference | Online (RedisStore) | No (latest only) |

```python
from my_project.definitions import defs

# Training data - entities handled automatically
training_data = defs.get_training_data(
    features=["user_spend", "merchant_revenue"],
    entity_df=transactions,
    timestamp="event_time",
)

# Online inference - entities handled automatically
features = defs.get_online_features(
    features=["user_spend", "merchant_revenue"],
    entity_df=request_df,
)
```

!!! tip "Automatic Entity Key Handling"
    When retrieving multiple features with **different entities** (e.g., user features and merchant features), the Definitions methods automatically determine the correct entity keys for each feature. This prevents errors where wrong entity keys would cause silent lookup failures.

---

## Offline Retrieval (Training)

Use `get_training_data()` to join features to your entity DataFrame for training or batch scoring.

### Basic Usage

```python
from my_project.definitions import defs

training_data = defs.get_training_data(
    features=["user_total_spend", "user_avg_spend"],
    entity_df=entities,
    timestamp="event_time",  # Optional: for point-in-time joins
)
```

### Method Signature

```python
def get_training_data(
    self,
    features: list[str | tuple[str, str] | FeatureSpec],
    entity_df: pl.DataFrame,
    timestamp: str | None = None,
    store: Store | None = None,
) -> pl.DataFrame
```

### Parameters

#### features (required)

List of feature specifications. Supports three formats:

**1. String (simple)** - All columns, latest version:

```python
training_data = defs.get_training_data(
    features=["user_age", "user_tenure_days"],
    entity_df=entities
)
```

**2. Tuple (version pinning)** - All columns, specific version:

```python
training_data = defs.get_training_data(
    features=[("user_age", "1.0.0"), "user_tenure_days"],
    entity_df=entities
)
```

**3. FeatureSpec (column selection)** - Specific columns and/or version:

```python
import mlforge as mlf

training_data = defs.get_training_data(
    features=[
        # Select specific columns (memory efficient for wide features)
        mlf.FeatureSpec(name="user_spend", columns=["amt_sum_7d", "amt_mean_7d"]),
        # Pin version
        mlf.FeatureSpec(name="merchant_risk", version="1.0.0"),
        # Both column selection and version
        mlf.FeatureSpec(name="user_activity", columns=["login_count"], version="2.0.0"),
    ],
    entity_df=entities
)
```

!!! tip "When to use FeatureSpec"
    Use `FeatureSpec` with column selection when:

    - Your feature has many columns but you only need a few
    - You want to reduce memory usage during training
    - You want explicit control over which columns are loaded

#### entity_df (required)

DataFrame containing entity source columns and optionally timestamps. This is typically your:

- Training labels
- Prediction entities
- Evaluation dataset

```python
entities = pl.DataFrame({
    "first": ["Alice", "Bob"],
    "last": ["Smith", "Jones"],
    "dob": ["1990-01-01", "1985-05-15"],
    "label": [0, 1],
})
```

The method automatically generates surrogate keys based on each feature's entity definition.

#### timestamp (optional)

Column name in `entity_df` to use for point-in-time joins. When specified, features with timestamps are joined using asof joins.

```python
training_data = defs.get_training_data(
    features=["user_spend_mean_30d"],
    entity_df=transactions,
    timestamp="transaction_time"  # Point-in-time correct
)
```

See [Point-in-Time Correctness](point-in-time.md) for details.

#### store (optional)

Override the default offline store. Useful for testing or accessing a different store.

```python
test_store = mlf.LocalStore("./test_feature_store")
training_data = defs.get_training_data(
    features=["user_age"],
    entity_df=entities,
    store=test_store
)
```

## Join Behavior

### Standard Joins

When `timestamp` is not specified, features are joined using standard left joins:

```python
entities = pl.DataFrame({
    "first": ["Alice", "Bob"],
    "last": ["Smith", "Jones"],
    "dob": ["1990-01-01", "1985-05-15"],
    "label": [0, 1],
})

training_data = defs.get_training_data(
    features=["user_total_spend"],
    entity_df=entities
)

# Automatically generates user_id from entity definition
# Then joins on user_id
```

### Point-in-Time Joins

When `timestamp` is specified and features have timestamps, asof joins are used:

```python
transactions = pl.DataFrame({
    "first": ["Alice", "Alice", "Bob"],
    "last": ["Smith", "Smith", "Jones"],
    "dob": ["1990-01-01", "1990-01-01", "1985-05-15"],
    "transaction_time": ["2024-01-05", "2024-01-15", "2024-01-10"],
    "label": [0, 1, 0]
})

training_data = defs.get_training_data(
    features=["user_spend_mean_30d"],
    entity_df=transactions,
    timestamp="transaction_time"
)

# Features reflect data available at each transaction_time
```

## Complete Example

```python
from my_project.definitions import defs
import polars as pl

# 1. Load entity data with raw columns
transactions = pl.read_parquet("data/transactions.parquet")

# 2. Retrieve features with point-in-time correctness
# Entity keys are generated automatically from feature definitions
training_data = defs.get_training_data(
    features=["user_spend_mean_30d", "user_total_spend", "merchant_revenue"],
    entity_df=transactions,
    timestamp="trans_date_trans_time",
)

# 3. Use in training
from sklearn.ensemble import RandomForestClassifier

X = training_data.select(["user_spend_mean_30d", "user_total_spend", "merchant_revenue"])
y = training_data.select("label")

model = RandomForestClassifier()
model.fit(X.to_pandas(), y.to_pandas())
```

## Error Handling

### Missing Features

If a requested feature hasn't been built:

```python
try:
    training_data = defs.get_training_data(
        features=["nonexistent_feature"],
        entity_df=entities
    )
except ValueError as e:
    print(e)
    # Unknown feature: 'nonexistent_feature'
```

Build the feature first:

```bash
mlforge build
```

### Invalid Columns (FeatureSpec)

If you request columns that don't exist in the feature:

```python
from mlforge.errors import FeatureSpecError

try:
    training_data = defs.get_training_data(
        features=[
            mlf.FeatureSpec(name="user_spend", columns=["nonexistent_column"])
        ],
        entity_df=entities
    )
except FeatureSpecError as e:
    print(e)
    # FeatureSpecError: Columns not found in feature 'user_spend': ['nonexistent_column']
    # Available columns:
    #   - user_id
    #   - amt_sum_7d
    #   - amt_mean_7d
```

Use `mlforge inspect feature <name>` to see available columns.

### No Store Configured

If no offline store is configured:

```python
try:
    training_data = defs.get_training_data(
        features=["user_spend"],
        entity_df=entities
    )
except ValueError as e:
    print(e)
    # No store configured. Either pass store= parameter
    # or configure store in Definitions/mlforge.yaml.
```

### Timestamp Type Mismatch

For asof joins, timestamp columns must have matching data types:

```python
# entity_df["event_time"] is String
# feature["feature_timestamp"] is Datetime

try:
    training_data = defs.get_training_data(
        features=["temporal_feature"],
        entity_df=entities,
        timestamp="event_time"
    )
except ValueError as e:
    print(e)
    # Timestamp dtype mismatch
```

Solution: Convert timestamps before retrieval:

```python
entities = entities.with_columns(
    pl.col("event_time").str.to_datetime().alias("event_time")
)

training_data = defs.get_training_data(
    features=["temporal_feature"],
    entity_df=entities,
    timestamp="event_time"
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

training_data = defs.get_training_data(
    features=["temporal_features"],
    entity_df=entities,
    timestamp="event_time"
)
```

### 2. Verify Features Exist

Check built features before retrieval:

```bash
mlforge list features
```

### 3. Handle Missing Values

Features may have nulls for entities not in the feature source:

```python
training_data = defs.get_training_data(
    features=["user_total_spend"],
    entity_df=entities
)

# Fill nulls if needed
training_data = training_data.with_columns(
    pl.col("user_total_spend").fill_null(0)
)
```

---

## Online Retrieval (Inference)

For real-time inference, use `get_online_features()` to retrieve features from an online store like Redis.

### Basic Usage

```python
from my_project.definitions import defs
import polars as pl

# Inference request with raw entity columns
request_df = pl.DataFrame({
    "request_id": ["req_001", "req_002"],
    "first": ["John", "Jane"],
    "last": ["Doe", "Smith"],
    "dob": ["1990-01-15", "1985-06-20"],
    "merchant_id": ["m_123", "m_456"],
})

# Retrieve multiple features with different entities
# Each feature uses only its own entity keys automatically
features_df = defs.get_online_features(
    features=["user_spend", "merchant_revenue", "user_merchant_affinity"],
    entity_df=request_df,
)
```

### Method Signature

```python
def get_online_features(
    self,
    features: list[str],
    entity_df: pl.DataFrame,
    store: OnlineStore | None = None,
) -> pl.DataFrame
```

### Parameters

#### features (required)

List of feature names to retrieve. Online stores only hold the latest version.

```python
features_df = defs.get_online_features(
    features=["user_spend", "merchant_revenue"],
    entity_df=request_df,
)
```

#### entity_df (required)

DataFrame with entity source columns. The method generates surrogate keys automatically based on each feature's entity definition.

```python
request_df = pl.DataFrame({
    "first": ["John", "Jane"],
    "last": ["Doe", "Smith"],
    "dob": ["1990-01-15", "1985-06-20"],
})
```

#### store (optional)

Override the default online store. Useful for testing.

```python
test_store = mlf.RedisStore(host="localhost", port=6380)
features_df = defs.get_online_features(
    features=["user_spend"],
    entity_df=request_df,
    store=test_store
)
```

### Key Differences from Training Retrieval

| Aspect | `get_training_data()` | `get_online_features()` |
|--------|----------------------|------------------------|
| **Versioning** | Supports `("feature", "1.0.0")` | No versioning (latest only) |
| **Point-in-time** | Uses `timestamp` parameter | Not applicable |
| **Store type** | Offline (LocalStore, S3Store) | Online (RedisStore) |
| **Missing entities** | Returns null | Returns null |

### Prerequisites

Before using online retrieval:

1. **Configure online store** in your definitions:
   ```python
   import mlforge as mlf

   defs = mlf.Definitions(
       name="my-project",
       features=[user_spend],
       offline_store=mlf.LocalStore("./feature_store"),
       online_store=mlf.RedisStore(host="localhost"),
   )
   ```

2. **Build to online store**:
   ```bash
   mlforge build --online
   ```

3. **Ensure Redis is running**:
   ```bash
   docker run -d -p 6379:6379 redis:7-alpine
   ```

See [Online Stores](online-stores.md) for detailed setup instructions.

### Error Handling

#### No Online Store Configured

```python
try:
    features_df = defs.get_online_features(
        features=["user_spend"],
        entity_df=request_df
    )
except ValueError as e:
    print(e)
    # No online store configured. Either pass store= parameter
    # or configure online_store in Definitions/mlforge.yaml.
```

#### Unknown Feature

```python
try:
    features_df = defs.get_online_features(
        features=["nonexistent_feature"],
        entity_df=request_df
    )
except ValueError as e:
    print(e)
    # Unknown feature: 'nonexistent_feature'
```

---

## Next Steps

- [Entity Keys](entity-keys.md) - Work with surrogate keys and entities
- [Point-in-Time Correctness](point-in-time.md) - Understand temporal joins
- [Online Stores](online-stores.md) - Set up Redis for real-time serving
- [API Reference](../api/retrieval.md) - Detailed API documentation
