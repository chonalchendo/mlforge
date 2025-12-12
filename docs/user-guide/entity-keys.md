# Entity Keys

Entity keys are identifiers that uniquely reference entities in your feature store. mlforge provides utilities for working with both natural keys and surrogate keys.

## Surrogate Keys

A surrogate key is a generated identifier created by hashing natural key columns. Use `surrogate_key()` to create them.

### Basic Usage

```python
from mlforge import surrogate_key
import polars as pl

df = pl.DataFrame({
    "first": ["Alice", "Bob"],
    "last": ["Smith", "Jones"],
    "dob": ["1990-01-01", "1985-05-15"]
})

# Generate surrogate key
result = df.with_columns(
    surrogate_key("first", "last", "dob").alias("user_id")
)

print(result)
```

Output:

```
┌───────┬───────┬────────────┬──────────────────────┐
│ first │ last  │ dob        │ user_id              │
├───────┼───────┼────────────┼──────────────────────┤
│ Alice │ Smith │ 1990-01-01 │ 12345678901234567890 │
│ Bob   │ Jones │ 1985-05-15 │ 98765432109876543210 │
└───────┴───────┴────────────┴──────────────────────┘
```

### How It Works

`surrogate_key()` concatenates column values with a separator, handles nulls, and hashes the result:

```python
surrogate_key("col1", "col2", "col3")

# Equivalent to:
# concat_str([col1, col2, col3], separator="||")
#   .fill_null("__NULL__")
#   .hash()
#   .cast(String)
```

### Null Handling

Null values are replaced with `"__NULL__"` before hashing:

```python
df = pl.DataFrame({
    "first": ["Alice", None],
    "last": ["Smith", "Jones"]
})

result = df.with_columns(
    surrogate_key("first", "last").alias("user_id")
)

# Both rows get unique IDs despite the null
```

### Multiple Columns

Use as many columns as needed:

```python
# Simple key
user_id = surrogate_key("email")

# Composite key
transaction_id = surrogate_key("user_id", "merchant_id", "timestamp")

# Complex key
session_id = surrogate_key("device_id", "ip_address", "user_agent", "timestamp")
```

## Entity Key Transforms

The `entity_key()` function creates reusable transformations that add surrogate keys to DataFrames.

### Basic Usage

```python
from mlforge import entity_key
import polars as pl

# Define a reusable transform
with_user_id = entity_key("first", "last", "dob", alias="user_id")

# Apply to DataFrame
df = pl.DataFrame({
    "first": ["Alice", "Bob"],
    "last": ["Smith", "Jones"],
    "dob": ["1990-01-01", "1985-05-15"]
})

result = df.pipe(with_user_id)

print(result)
```

Output:

```
┌───────┬───────┬────────────┬──────────────────────┐
│ first │ last  │ dob        │ user_id              │
├───────┼───────┼────────────┼──────────────────────┤
│ Alice │ Smith │ 1990-01-01 │ 12345678901234567890 │
│ Bob   │ Jones │ 1985-05-15 │ 98765432109876543210 │
└───────┴───────┴────────────┴──────────────────────┘
```

### Using in Features

Entity transforms are commonly used in feature definitions:

```python
from mlforge import feature, entity_key
import polars as pl

# Define entity transforms
with_user_id = entity_key("first", "last", "dob", alias="user_id")
with_merchant_id = entity_key("merchant", alias="merchant_id")

@feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    description="Total spend by user"
)
def user_total_spend(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df
        .pipe(with_user_id)  # Add user_id
        .group_by("user_id")
        .agg(pl.col("amount").sum().alias("total_spend"))
    )

@feature(
    keys=["user_id", "merchant_id"],
    source="data/transactions.parquet",
    description="Spend by user and merchant"
)
def user_merchant_spend(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df
        .pipe(with_user_id)        # Add user_id
        .pipe(with_merchant_id)    # Add merchant_id
        .group_by(["user_id", "merchant_id"])
        .agg(pl.col("amount").sum().alias("total_spend"))
    )
```

### Using in Retrieval

Pass entity transforms to `get_training_data()` when your entity DataFrame lacks required keys:

```python
from mlforge import get_training_data, entity_key
import polars as pl

# Entity data without user_id
entities = pl.DataFrame({
    "first": ["Alice", "Bob"],
    "last": ["Smith", "Jones"],
    "dob": ["1990-01-01", "1985-05-15"],
    "label": [0, 1]
})

# Define transform
with_user_id = entity_key("first", "last", "dob", alias="user_id")

# Retrieve features
training_data = get_training_data(
    features=["user_total_spend"],
    entity_df=entities,
    entities=[with_user_id]  # Adds user_id before joining
)

print(training_data)
```

Output:

```
┌───────┬───────┬────────────┬──────────────────────┬─────────────┬───────┐
│ first │ last  │ dob        │ user_id              │ total_spend │ label │
├───────┼───────┼────────────┼──────────────────────┼─────────────┼───────┤
│ Alice │ Smith │ 1990-01-01 │ 12345678901234567890 │ 150.0       │ 0     │
│ Bob   │ Jones │ 1985-05-15 │ 98765432109876543210 │ 250.0       │ 1     │
└───────┴───────┴────────────┴──────────────────────┴─────────────┴───────┘
```

### Multiple Transforms

Apply multiple transforms at once:

```python
from mlforge import entity_key, get_training_data

with_user_id = entity_key("first", "last", "dob", alias="user_id")
with_account_id = entity_key("cc_num", alias="account_id")

training_data = get_training_data(
    features=["user_spend", "account_spend"],
    entity_df=raw_data,
    entities=[with_user_id, with_account_id]  # Both transforms applied
)
```

## Complete Example

Here's a real-world example using the transactions dataset:

```python
# entities.py
from mlforge import entity_key

# Define all entity transforms
with_user_id = entity_key("first", "last", "dob", alias="user_id")
with_merchant_id = entity_key("merchant", alias="merchant_id")
with_account_id = entity_key("cc_num", alias="account_id")
```

```python
# features.py
from mlforge import feature
import polars as pl
from entities import with_user_id, with_merchant_id, with_account_id

SOURCE = "data/transactions.parquet"

@feature(keys=["user_id"], source=SOURCE)
def user_total_spend(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.pipe(with_user_id)
        .group_by("user_id")
        .agg(pl.col("amt").sum().alias("total_spend"))
    )

@feature(keys=["merchant_id"], source=SOURCE)
def merchant_total_revenue(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.pipe(with_merchant_id)
        .group_by("merchant_id")
        .agg(pl.col("amt").sum().alias("total_revenue"))
    )

@feature(keys=["account_id"], source=SOURCE)
def account_total_spend(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.pipe(with_account_id)
        .group_by("account_id")
        .agg(pl.col("amt").sum().alias("total_spend"))
    )
```

```python
# train.py
from mlforge import get_training_data
import polars as pl
from entities import with_user_id, with_merchant_id

# Load raw transaction data
transactions = pl.read_parquet("data/transactions.parquet")

# Get features with automatic key generation
training_data = get_training_data(
    features=["user_total_spend", "merchant_total_revenue"],
    entity_df=transactions,
    entities=[with_user_id, with_merchant_id]
)
```

## When to Use Surrogate Keys

### Use surrogate keys when:

1. **Natural keys are composite**
   ```python
   # Instead of: keys=["first", "last", "dob"]
   # Use: keys=["user_id"]
   with_user_id = entity_key("first", "last", "dob", alias="user_id")
   ```

2. **Natural keys are PII**
   ```python
   # Hash email addresses
   with_user_id = entity_key("email", alias="user_id")
   ```

3. **You need stable identifiers across datasets**
   ```python
   # Same user_id in different sources
   users = raw_users.pipe(with_user_id)
   transactions = raw_transactions.pipe(with_user_id)
   ```

### Don't use surrogate keys when:

1. **You already have a natural ID column**
   ```python
   # If your data has user_id, just use it
   @feature(keys=["user_id"], source="data/users.parquet")
   def user_age(df): ...
   ```

2. **Keys are simple and non-sensitive**
   ```python
   # product_id, order_id, etc.
   @feature(keys=["product_id"], source="data/products.parquet")
   def product_price(df): ...
   ```

## Best Practices

### 1. Define Transforms Once

Create a dedicated module for entity transforms:

```python
# entities.py
from mlforge import entity_key

with_user_id = entity_key("first", "last", "dob", alias="user_id")
with_merchant_id = entity_key("merchant", alias="merchant_id")
```

Import and reuse across features:

```python
# features.py
from entities import with_user_id, with_merchant_id
```

### 2. Use Consistent Aliases

Use the same alias name across your project:

```python
# Good - consistent naming
with_user_id = entity_key("first", "last", "dob", alias="user_id")

# Bad - inconsistent
with_uid = entity_key("first", "last", "dob", alias="uid")
```

### 3. Document Natural Keys

Add comments explaining what natural keys compose each surrogate:

```python
# user_id: hash(first, last, dob)
with_user_id = entity_key("first", "last", "dob", alias="user_id")

# merchant_id: hash(merchant)
with_merchant_id = entity_key("merchant", alias="merchant_id")
```

### 4. Validate Key Columns Exist

Check that required columns are present before applying transforms:

```python
from mlforge import entity_key

with_user_id = entity_key("first", "last", "dob", alias="user_id")

# This will raise a clear error if columns are missing
df = raw_data.pipe(with_user_id)
```

## Next Steps

- [Point-in-Time Correctness](point-in-time.md) - Temporal feature joins
- [Retrieving Features](retrieving-features.md) - Using entity transforms in retrieval
- [API Reference - Utils](../api/utils.md) - Complete API documentation
