# Entity Keys

Entity keys are identifiers that uniquely reference entities in your feature store. mlforge provides the `Entity` class for defining entities and the `surrogate_key()` utility for generating keys from multiple columns.

## Entity Class

The `Entity` class defines the subject of a feature (user, merchant, account, etc.) with its join key and optional surrogate key generation.

### Basic Usage

```python
import mlforge as mlf

# Simple entity - column already exists in data
merchant = mlf.Entity(name="merchant", join_key="merchant_id")

# Surrogate key from multiple columns
user = mlf.Entity(
    name="user",
    join_key="user_id",
    from_columns=["first", "last", "dob"],
)

# Composite key (multiple columns)
user_merchant = mlf.Entity(
    name="user_merchant",
    join_key=["user_id", "merchant_id"],
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Logical name for the entity (e.g., "user", "merchant") |
| `join_key` | `str \| list[str]` | Column name(s) that identify this entity |
| `from_columns` | `list[str] \| None` | Source columns to hash into a surrogate key (optional) |

### When to Use `from_columns`

Use `from_columns` when you need to generate a surrogate key from multiple source columns:

```python
# Your data has natural key columns
# first, last, dob -> generates user_id via hashing

user = mlf.Entity(
    name="user",
    join_key="user_id",
    from_columns=["first", "last", "dob"],
)
```

Omit `from_columns` when your data already has the join key column:

```python
# Your data already has user_id column
user = mlf.Entity(name="user", join_key="user_id")
```

## Using Entities in Feature Definitions

Pass entities to the `@feature` decorator:

```python
import mlforge as mlf
import polars as pl

user = mlf.Entity(
    name="user",
    join_key="user_id",
    from_columns=["first", "last", "dob"],
)

@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    entities=[user],
    description="Total spend by user",
)
def user_total_spend(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df
        .group_by("user_id")
        .agg(pl.col("amount").sum().alias("total_spend"))
    )
```

## Using Entities in Retrieval

Pass entities to `get_training_data()` or `get_online_features()` when your entity DataFrame needs key generation or validation:

```python
import mlforge as mlf
import polars as pl

user = mlf.Entity(
    name="user",
    join_key="user_id",
    from_columns=["first", "last", "dob"],
)

# Entity data without user_id - will be generated
entities = pl.DataFrame({
    "first": ["Alice", "Bob"],
    "last": ["Smith", "Jones"],
    "dob": ["1990-01-01", "1985-05-15"],
    "label": [0, 1],
})

# Retrieve features - user_id is generated automatically
training_data = mlf.get_training_data(
    features=["user_total_spend"],
    entity_df=entities,
    entities=[user],
)

print(training_data)
```

Output:

```
shape: (2, 5)
┌───────┬───────┬────────────┬──────────────────────┬─────────────┬───────┐
│ first ┆ last  ┆ dob        ┆ user_id              ┆ total_spend ┆ label │
├───────┼───────┼────────────┼──────────────────────┼─────────────┼───────┤
│ Alice ┆ Smith ┆ 1990-01-01 ┆ 12345678901234567890 ┆ 150.0       ┆ 0     │
│ Bob   ┆ Jones ┆ 1985-05-15 ┆ 98765432109876543210 ┆ 250.0       ┆ 1     │
└───────┴───────┴────────────┴──────────────────────┴─────────────┴───────┘
```

### Direct Entities (No Generation)

When your entity DataFrame already has the join key, use an entity without `from_columns`:

```python
merchant = mlf.Entity(name="merchant", join_key="merchant_id")

# entity_df already has merchant_id - just validates it exists
entities = pl.DataFrame({
    "merchant_id": ["m1", "m2"],
    "label": [0, 1],
})

training_data = mlf.get_training_data(
    features=["merchant_revenue"],
    entity_df=entities,
    entities=[merchant],  # Validates merchant_id exists
)
```

### Multiple Entities

Use multiple entities when joining features with different keys:

```python
user = mlf.Entity(
    name="user",
    join_key="user_id",
    from_columns=["first", "last", "dob"],
)
merchant = mlf.Entity(name="merchant", join_key="merchant_id")

training_data = mlf.get_training_data(
    features=["user_spend", "merchant_revenue"],
    entity_df=transactions,
    entities=[user, merchant],
)
```

## Surrogate Keys

A surrogate key is a generated identifier created by hashing natural key columns. Use `surrogate_key()` when you need to generate keys manually.

### Basic Usage

```python
from mlforge import surrogate_key
import polars as pl

df = pl.DataFrame({
    "first": ["Alice", "Bob"],
    "last": ["Smith", "Jones"],
    "dob": ["1990-01-01", "1985-05-15"],
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
    "last": ["Smith", "Jones"],
})

result = df.with_columns(
    surrogate_key("first", "last").alias("user_id")
)

# Both rows get unique IDs despite the null
```

## When to Use Surrogate Keys

### Use surrogate keys when:

1. **Natural keys are composite**
   ```python
   # Instead of: keys=["first", "last", "dob"]
   # Use: keys=["user_id"]
   user = mlf.Entity(
       name="user",
       join_key="user_id",
       from_columns=["first", "last", "dob"],
   )
   ```

2. **Natural keys are PII**
   ```python
   # Hash email addresses
   user = mlf.Entity(
       name="user",
       join_key="user_id",
       from_columns=["email"],
   )
   ```

3. **You need stable identifiers across datasets**
   ```python
   # Same user_id generated in different sources
   user = mlf.Entity(
       name="user",
       join_key="user_id",
       from_columns=["first", "last", "dob"],
   )
   ```

### Don't use surrogate keys when:

1. **You already have a natural ID column**
   ```python
   # If your data has user_id, just use it
   user = mlf.Entity(name="user", join_key="user_id")
   ```

2. **Keys are simple and non-sensitive**
   ```python
   # product_id, order_id, etc.
   product = mlf.Entity(name="product", join_key="product_id")
   ```

## Complete Example

```python
# entities.py
import mlforge as mlf

# Define all entities
user = mlf.Entity(
    name="user",
    join_key="user_id",
    from_columns=["first", "last", "dob"],
)
merchant = mlf.Entity(name="merchant", join_key="merchant_id")
account = mlf.Entity(
    name="account",
    join_key="account_id",
    from_columns=["cc_num"],
)
```

```python
# features.py
import mlforge as mlf
import polars as pl
from entities import user, merchant, account

SOURCE = "data/transactions.parquet"

@mlf.feature(keys=["user_id"], source=SOURCE, entities=[user])
def user_total_spend(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df
        .group_by("user_id")
        .agg(pl.col("amt").sum().alias("total_spend"))
    )

@mlf.feature(keys=["merchant_id"], source=SOURCE, entities=[merchant])
def merchant_total_revenue(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df
        .group_by("merchant_id")
        .agg(pl.col("amt").sum().alias("total_revenue"))
    )

@mlf.feature(keys=["account_id"], source=SOURCE, entities=[account])
def account_total_spend(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df
        .group_by("account_id")
        .agg(pl.col("amt").sum().alias("total_spend"))
    )
```

```python
# train.py
import mlforge as mlf
import polars as pl
from entities import user, merchant

# Load raw transaction data
transactions = pl.read_parquet("data/transactions.parquet")

# Get features with automatic key generation
training_data = mlf.get_training_data(
    features=["user_total_spend", "merchant_total_revenue"],
    entity_df=transactions,
    entities=[user, merchant],
)
```

## Best Practices

### 1. Define Entities Once

Create a dedicated module for entity definitions:

```python
# entities.py
import mlforge as mlf

user = mlf.Entity(
    name="user",
    join_key="user_id",
    from_columns=["first", "last", "dob"],
)
merchant = mlf.Entity(name="merchant", join_key="merchant_id")
```

Import and reuse across features:

```python
# features.py
from entities import user, merchant
```

### 2. Use Consistent Names

Use the same entity across your project:

```python
# Good - consistent naming
user = mlf.Entity(name="user", join_key="user_id", from_columns=["first", "last", "dob"])

# Bad - inconsistent
uid_entity = mlf.Entity(name="uid", join_key="uid", from_columns=["first", "last", "dob"])
```

### 3. Document Natural Keys

Add comments explaining what natural keys compose each surrogate:

```python
# user_id: hash(first, last, dob)
user = mlf.Entity(
    name="user",
    join_key="user_id",
    from_columns=["first", "last", "dob"],
)

# merchant_id: direct column (no hashing)
merchant = mlf.Entity(name="merchant", join_key="merchant_id")
```

## Next Steps

- [Point-in-Time Correctness](point-in-time.md) - Temporal feature joins
- [Retrieving Features](retrieving-features.md) - Using entities in retrieval
- [API Reference - Utils](../api/utils.md) - Complete API documentation
