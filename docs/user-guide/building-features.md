# Building Features

Once you've defined features, the next step is to materialize them to storage. This guide covers building features using both the CLI and the Python API.

## Using the CLI

The recommended way to build features is via the `mlforge build` command.

### Basic Usage

```bash
mlforge build definitions.py
```

This will:

1. Load your `Definitions` object from `definitions.py`
2. Materialize all registered features
3. Write them to your configured offline store
4. Display a preview of each feature

### Build Specific Features

Build only selected features:

```bash
mlforge build definitions.py --features user_total_spend,user_avg_spend
```

### Force Rebuild

By default, mlforge skips features that already exist. Use `--force` to rebuild:

```bash
mlforge build definitions.py --force
```

### Disable Preview

Turn off the data preview:

```bash
mlforge build definitions.py --no-preview
```

### Control Preview Size

Adjust the number of rows shown:

```bash
mlforge build definitions.py --preview-rows 10
```

### Verbose Logging

Enable debug logging:

```bash
mlforge build definitions.py --verbose
```

## Using the Python API

You can also materialize features programmatically:

```python
from mlforge import Definitions, LocalStore
import features

defs = Definitions(
    name="my-project",
    features=[features],
    offline_store=LocalStore("./feature_store")
)

# Materialize all features
defs.materialize()
```

### Materialize Specific Features

```python
defs.materialize(feature_names=["user_total_spend", "user_avg_spend"])
```

### Force Rebuild

```python
defs.materialize(force=True)
```

### Disable Preview

```python
defs.materialize(preview=False)
```

### Custom Preview Size

```python
defs.materialize(preview_rows=10)
```

### Get Output Paths

The `materialize()` method returns a dictionary mapping feature names to their file paths:

```python
from pathlib import Path

paths = defs.materialize()

for feature_name, path in paths.items():
    print(f"{feature_name}: {path}")

# Output:
# user_total_spend: feature_store/user_total_spend.parquet
# user_avg_spend: feature_store/user_avg_spend.parquet
```

## Storage Backend

Features are stored in the configured offline store. Currently, mlforge supports local Parquet storage via `LocalStore`.

### LocalStore

Stores features as individual Parquet files:

```python
from mlforge import LocalStore

store = LocalStore(path="./feature_store")
```

Each feature is saved as `feature_store/<feature_name>.parquet`.

### Custom Storage Path

```python
from pathlib import Path

store = LocalStore(path=Path.home() / "ml_projects" / "features")
```

## Listing Features

View all registered features:

```bash
mlforge list definitions.py
```

Output:

```
┌──────────────────┬──────────────┬──────────────────────────┬─────────────────────┐
│ Name             │ Keys         │ Source                   │ Description         │
├──────────────────┼──────────────┼──────────────────────────┼─────────────────────┤
│ user_total_spend │ [user_id]    │ data/transactions.parquet│ Total spend by user │
│ user_avg_spend   │ [user_id]    │ data/transactions.parquet│ Avg spend by user   │
└──────────────────┴──────────────┴──────────────────────────┴─────────────────────┘
```

Or in Python:

```python
features = defs.list_features()

for feature in features:
    print(f"{feature.name}: {feature.description}")
```

## Error Handling

### FeatureMaterializationError

Raised when a feature function fails or returns invalid data:

```python
from mlforge.errors import FeatureMaterializationError

try:
    defs.materialize()
except FeatureMaterializationError as e:
    print(f"Failed to materialize feature: {e}")
```

Common causes:

1. **Feature function returns None**
   ```python
   @feature(keys=["user_id"], source="data/users.parquet")
   def broken_feature(df):
       df.group_by("user_id").agg(...)
       # Missing return statement!
   ```

2. **Feature function returns wrong type**
   ```python
   @feature(keys=["user_id"], source="data/users.parquet")
   def broken_feature(df):
       return df.to_dict()  # Should return DataFrame
   ```

3. **Missing key columns in output**
   ```python
   @feature(keys=["user_id"], source="data/users.parquet")
   def broken_feature(df):
       return df.select("amount")  # user_id is missing!
   ```

### Source File Errors

If the source file doesn't exist or has an unsupported format:

```python
@feature(keys=["user_id"], source="data/missing.parquet")
def my_feature(df): ...

# Raises: FileNotFoundError
defs.materialize()
```

Supported formats: `.parquet`, `.csv`

## Workflow Example

A typical development workflow:

```bash
# 1. Define features
cat > features.py << 'EOF'
from mlforge import feature
import polars as pl

@feature(keys=["user_id"], source="data/users.parquet")
def user_age(df):
    return df.select(["user_id", "age"])
EOF

# 2. Create definitions
cat > definitions.py << 'EOF'
from mlforge import Definitions, LocalStore
import features

defs = Definitions(
    name="user-features",
    features=[features],
    offline_store=LocalStore("./feature_store")
)
EOF

# 3. Build features
mlforge build definitions.py

# 4. Verify
mlforge list definitions.py

# 5. Rebuild specific features if needed
mlforge build definitions.py --features user_age --force
```

## Performance Tips

### 1. Use Parquet for Sources

Parquet is significantly faster than CSV for large datasets:

```python
# Convert CSV to Parquet once
import polars as pl

df = pl.read_csv("data/large_file.csv")
df.write_parquet("data/large_file.parquet")

# Then use Parquet in features
@feature(keys=["id"], source="data/large_file.parquet")
def my_feature(df): ...
```

### 2. Filter Early

If you don't need all source data, filter it early in your feature function:

```python
@feature(keys=["user_id"], source="data/all_events.parquet")
def recent_user_activity(df):
    return (
        df
        .filter(pl.col("event_date") >= "2024-01-01")  # Filter early
        .group_by("user_id")
        .agg(pl.col("event_id").count())
    )
```

### 3. Build Features Incrementally

During development, build one feature at a time:

```bash
mlforge build definitions.py --features new_feature
```

Once it works, build all features together.

## Next Steps

- [Retrieving Features](retrieving-features.md) - Use features in training pipelines
- [Entity Keys](entity-keys.md) - Work with surrogate keys
- [Point-in-Time Correctness](point-in-time.md) - Temporal feature joins
