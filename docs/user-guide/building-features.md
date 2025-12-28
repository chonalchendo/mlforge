# Building Features

Once you've defined features, the next step is to build them and persist to storage. This guide covers building features using both the CLI and the Python API.

## Using the CLI

The recommended way to build features is via the `mlforge build` command.

### Basic Usage

```bash
mlforge build
```

This will:

1. Load your `Definitions` object from `definitions.py`
2. Materialize all registered features
3. Write them to your configured offline store
4. Display a preview of each feature

### Build Specific Features

Build only selected features by name:

```bash
mlforge build --features user_total_spend,user_avg_spend
```

Or build features by tag:

```bash
mlforge build --tags user_metrics,demographics
```

!!! note "Mutually exclusive filters"
    The `--features` and `--tags` options cannot be used together. Choose one filtering approach per build command.

### Force Rebuild

By default, mlforge skips features that already exist. Use `--force` to rebuild:

```bash
mlforge build --force
```

### Disable Preview

Turn off the data preview:

```bash
mlforge build --no-preview
```

### Control Preview Size

Adjust the number of rows shown:

```bash
mlforge build --preview-rows 10
```

### Verbose Logging

Enable debug logging:

```bash
mlforge build --verbose
```

## Using the Python API

You can also build features programmatically:

```python
import mlforge as mlf
import features

defs = mlf.Definitions(
    name="my-project",
    features=[features],
    offline_store=mlf.LocalStore("./feature_store")
)

# Build all features
defs.build()
```

### Build Specific Features

By feature name:

```python
defs.build(feature_names=["user_total_spend", "user_avg_spend"])
```

By tag:

```python
defs.build(tag_names=["user_metrics", "demographics"])
```

!!! note "Mutually exclusive parameters"
    The `feature_names` and `tag_names` parameters cannot be used together.

### Force Rebuild

```python
defs.build(force=True)
```

### Disable Preview

```python
defs.build(preview=False)
```

### Custom Preview Size

```python
defs.build(preview_rows=10)
```

### Get Output Paths

The `build()` method returns a dictionary mapping feature names to their file paths:

```python
from pathlib import Path

paths = defs.build()

for feature_name, path in paths.items():
    print(f"{feature_name}: {path}")

# Output:
# user_total_spend: feature_store/user_total_spend.parquet
# user_avg_spend: feature_store/user_avg_spend.parquet
```

## Storage Backend

Features are stored in the configured offline store. mlforge supports both local and cloud storage backends.

### LocalStore

Stores features as individual Parquet files on the local filesystem:

```python
import mlforge as mlf

store = mlf.LocalStore(path="./feature_store")
```

Each feature is saved as `feature_store/<feature_name>.parquet`.

### S3Store

Stores features in Amazon S3 for production deployments:

```python
import mlforge as mlf

store = mlf.S3Store(
    bucket="mlforge-features",
    prefix="prod/features"
)
```

Features are stored at `s3://mlforge-features/prod/features/<feature_name>.parquet`.

!!! tip "AWS Credentials"
    S3Store uses standard AWS credential resolution (environment variables, `~/.aws/credentials`, or IAM roles).

See the [Storage Backends](storage-backends.md) guide for detailed configuration and IAM policy examples.

## Listing Features

View all registered features:

```bash
mlforge list
```

Filter by tags:

```bash
mlforge list --tags user_metrics
```

Output:

```
┌──────────────────┬──────────────┬──────────────────────────┬──────────────┬─────────────────────┐
│ Name             │ Keys         │ Source                   │ Tags         │ Description         │
├──────────────────┼──────────────┼──────────────────────────┼──────────────┼─────────────────────┤
│ user_total_spend │ [user_id]    │ data/transactions.parquet│ user_metrics │ Total spend by user │
│ user_avg_spend   │ [user_id]    │ data/transactions.parquet│ user_metrics │ Avg spend by user   │
└──────────────────┴──────────────┴──────────────────────────┴──────────────┴─────────────────────┘
```

Or in Python:

```python
# List all features
features = defs.list_features()

for feature in features:
    print(f"{feature.name}: {feature.description}")

# List features by tag
user_features = defs.list_features(tags=["user_metrics"])
```

## Error Handling

### FeatureMaterializationError

Raised when a feature function fails or returns invalid data:

```python
from mlforge.errors import FeatureMaterializationError

try:
    defs.build()
except FeatureMaterializationError as e:
    print(f"Failed to materialize feature: {e}")
```

Common causes:

1. **Feature function returns None**
   ```python
   @mlf.feature(keys=["user_id"], source="data/users.parquet")
   def broken_feature(df):
       df.group_by("user_id").agg(...)
       # Missing return statement!
   ```

2. **Feature function returns wrong type**
   ```python
   @mlf.feature(keys=["user_id"], source="data/users.parquet")
   def broken_feature(df):
       return df.to_dict()  # Should return DataFrame
   ```

3. **Missing key columns in output**
   ```python
   @mlf.feature(keys=["user_id"], source="data/users.parquet")
   def broken_feature(df):
       return df.select("amount")  # user_id is missing!
   ```

### Source File Errors

If the source file doesn't exist or has an unsupported format:

```python
@mlf.feature(keys=["user_id"], source="data/missing.parquet")
def my_feature(df): ...

# Raises: FileNotFoundError
defs.build()
```

Supported formats: `.parquet`, `.csv`

## Workflow Example

A typical development workflow:

```bash
# 1. Define features
cat > features.py << 'EOF'
import mlforge as mlf
import polars as pl

@mlf.feature(keys=["user_id"], source="data/users.parquet")
def user_age(df):
    return df.select(["user_id", "age"])
EOF

# 2. Create definitions
cat > definitions.py << 'EOF'
import mlforge as mlf
import features

defs = mlf.Definitions(
    name="user-features",
    features=[features],
    offline_store=mlf.LocalStore("./feature_store")
)
EOF

# 3. Build features
mlforge build

# 4. Verify
mlforge list

# 5. Rebuild specific features if needed
mlforge build --features user_age --force
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
@mlf.feature(keys=["id"], source="data/large_file.parquet")
def my_feature(df): ...
```

### 2. Filter Early

If you don't need all source data, filter it early in your feature function:

```python
@mlf.feature(keys=["user_id"], source="data/all_events.parquet")
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
mlforge build --features new_feature
```

Once it works, build all features together.

## Next Steps

- [Retrieving Features](retrieving-features.md) - Use features in training pipelines
- [Entity Keys](entity-keys.md) - Work with surrogate keys
- [Point-in-Time Correctness](point-in-time.md) - Temporal feature joins
