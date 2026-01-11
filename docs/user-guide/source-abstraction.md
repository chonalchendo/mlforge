# Source Abstraction

The `Source` class provides a unified interface for specifying data sources with automatic location inference and format detection. Instead of manually configuring storage backends and file formats, you simply provide a path and mlforge handles the rest.

## Basic Usage

```python
import mlforge as mlf

# Local file - format auto-detected from extension
transactions = mlf.Source("data/transactions.parquet")

# S3 source - location inferred from prefix
s3_data = mlf.Source("s3://my-bucket/data/events.parquet")

# GCS source
gcs_data = mlf.Source("gs://my-bucket/data/users.parquet")
```

## How It Works

When you create a `Source`, mlforge automatically:

1. **Infers location** from the path prefix (`s3://`, `gs://`, or local)
2. **Detects format** from the file extension (`.parquet`, `.csv`)
3. **Derives a name** from the path stem (e.g., `transactions` from `data/transactions.parquet`)

```python
source = mlf.Source("s3://bucket/data/transactions.parquet")

assert source.location == "s3"
assert source.name == "transactions"
assert source.is_parquet == True
```

## Using Source with Features

Pass a `Source` directly to the `@feature` decorator:

```python
import mlforge as mlf
import polars as pl

# Define source once
transactions = mlf.Source("data/transactions.parquet")

@mlf.feature(
    source=transactions,  # Use Source object
    entities=[user],
    timestamp=timestamp,
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    return df.select("user_id", "trans_date_trans_time", "amt")
```

This is equivalent to using a path string, but provides additional benefits:

- **Reusable**: Define once, use across multiple features
- **Self-documenting**: Location and format are explicit
- **Type-safe**: IDE autocomplete for format options

## Supported Locations

| Prefix | Location | Example |
|--------|----------|---------|
| (none) | Local filesystem | `data/transactions.parquet` |
| `s3://` | Amazon S3 | `s3://bucket/data/transactions.parquet` |
| `gs://` | Google Cloud Storage | `gs://bucket/data/transactions.parquet` |

Check the location programmatically:

```python
source = mlf.Source("s3://bucket/data.parquet")

source.is_local  # False
source.is_s3     # True
source.is_gcs    # False
```

## Supported Formats

### Parquet (default)

```python
# Auto-detected from .parquet extension
source = mlf.Source("data/transactions.parquet")

# With format options
source = mlf.Source(
    "data/transactions.parquet",
    format=mlf.ParquetFormat(
        columns=["user_id", "amount"],  # Read specific columns
        row_groups=[0, 1],              # Read specific row groups
    ),
)
```

### CSV

```python
# Auto-detected from .csv extension
source = mlf.Source("data/events.csv")

# With format options
source = mlf.Source(
    "data/events.csv",
    format=mlf.CSVFormat(
        delimiter="|",       # Custom delimiter
        has_header=True,     # First row is header (default)
        quote_char='"',      # Quote character (default)
        skip_rows=0,         # Skip rows at start
    ),
)
```

### Delta Lake

```python
# Auto-detected for directories without extension
source = mlf.Source("data/delta_table/")

# With specific version
source = mlf.Source(
    "data/delta_table/",
    format=mlf.DeltaFormat(version=5),  # Read specific version
)
```

Check the format programmatically:

```python
source = mlf.Source("data/transactions.parquet")

source.is_parquet  # True
source.is_csv      # False
source.is_delta    # False
```

## Custom Names

By default, the source name is derived from the path stem. Override it with the `name` parameter:

```python
# Default name: "transactions"
source = mlf.Source("data/transactions.parquet")
assert source.name == "transactions"

# Custom name
source = mlf.Source("data/transactions.parquet", name="txn_data")
assert source.name == "txn_data"
```

## Format Options Reference

### ParquetFormat

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `columns` | `list[str]` | `None` | Columns to read (None = all) |
| `row_groups` | `list[int]` | `None` | Row groups to read (None = all) |

```python
mlf.ParquetFormat(
    columns=["user_id", "amount", "timestamp"],
    row_groups=[0, 1, 2],
)
```

### CSVFormat

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `delimiter` | `str` | `","` | Field separator (single character) |
| `has_header` | `bool` | `True` | First row is header |
| `quote_char` | `str` | `'"'` | Quote character (single character) |
| `skip_rows` | `int` | `0` | Rows to skip at start |

```python
# Tab-delimited file without header
mlf.CSVFormat(
    delimiter="\t",
    has_header=False,
    skip_rows=2,  # Skip comment lines
)
```

### DeltaFormat

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `version` | `int` | `None` | Table version to read (None = latest) |

```python
# Read specific historical version
mlf.DeltaFormat(version=5)
```

## Complete Example

```python
# features.py
import mlforge as mlf
import polars as pl
from entities import user, merchant

# Define sources
transactions = mlf.Source("s3://data-lake/transactions.parquet")
events = mlf.Source(
    "s3://data-lake/events.csv",
    format=mlf.CSVFormat(delimiter="|"),
)

# Define timestamp
timestamp = mlf.Timestamp(
    column="event_time",
    format="%Y-%m-%d %H:%M:%S",
)

@mlf.feature(
    source=transactions,
    entities=[user],
    timestamp=timestamp,
    tags=["user", "spending"],
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    return df.select("user_id", "event_time", "amount")

@mlf.feature(
    source=events,
    entities=[merchant],
    timestamp=timestamp,
    tags=["merchant", "activity"],
)
def merchant_activity(df: pl.DataFrame) -> pl.DataFrame:
    return df.select("merchant_id", "event_time", "event_type")
```

## Best Practices

### 1. Define Sources at Module Level

```python
# Good - reusable across features
transactions = mlf.Source("data/transactions.parquet")

@mlf.feature(source=transactions, ...)
def feature_a(df): ...

@mlf.feature(source=transactions, ...)
def feature_b(df): ...
```

### 2. Use Explicit Formats for Non-Standard Files

```python
# Good - explicit format for pipe-delimited CSV
source = mlf.Source(
    "data/legacy_export.csv",
    format=mlf.CSVFormat(delimiter="|"),
)

# Bad - relies on detection that may fail
source = mlf.Source("data/legacy_export.csv")
```

### 3. Use Cloud Paths Directly

```python
# Good - mlforge handles cloud storage
source = mlf.Source("s3://bucket/data.parquet")

# Unnecessary - manual storage configuration
# The Source class handles this automatically
```

## Next Steps

- [Timestamp Handling](timestamp-handling.md) - Configure datetime parsing
- [Defining Features](defining-features.md) - Use sources in feature definitions
- [Building Features](building-features.md) - Materialize features to storage
