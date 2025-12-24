# Manifest API

The manifest module provides dataclasses and utilities for tracking feature metadata.

## Overview

When features are built, mlforge automatically captures metadata about each feature, including:

- Feature configuration (keys, timestamp, interval)
- Storage details (path, row count)
- Column information (names, types, aggregations)
- Build timestamp and source data

This metadata is stored in `.meta.json` files alongside the feature parquet files and can be queried using the CLI or programmatically.

## Dataclasses

::: mlforge.manifest.ColumnMetadata
    options:
      heading_level: 3

::: mlforge.manifest.FeatureMetadata
    options:
      heading_level: 3

::: mlforge.manifest.Manifest
    options:
      heading_level: 3

## Functions

::: mlforge.manifest.derive_column_metadata
    options:
      heading_level: 3

::: mlforge.manifest.write_metadata_file
    options:
      heading_level: 3

::: mlforge.manifest.read_metadata_file
    options:
      heading_level: 3

::: mlforge.manifest.write_manifest_file
    options:
      heading_level: 3

::: mlforge.manifest.read_manifest_file
    options:
      heading_level: 3

## Usage Examples

### Reading Feature Metadata

```python
from mlforge import LocalStore

store = LocalStore("./feature_store")

# Read metadata for a specific feature
metadata = store.read_metadata("user_spend")

if metadata:
    print(f"Feature: {metadata.name}")
    print(f"Rows: {metadata.row_count:,}")
    print(f"Last updated: {metadata.last_updated}")
    print(f"Columns: {len(metadata.columns)}")
```

### Listing All Metadata

```python
from mlforge import LocalStore

store = LocalStore("./feature_store")

# Get all feature metadata
all_metadata = store.list_metadata()

for meta in all_metadata:
    print(f"{meta.name}: {meta.row_count:,} rows")
```

### Creating a Consolidated Manifest

```python
from mlforge import LocalStore
from mlforge.manifest import Manifest, write_manifest_file
from datetime import datetime, timezone

store = LocalStore("./feature_store")

# Create manifest from all features
manifest = Manifest(
    generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
)

for meta in store.list_metadata():
    manifest.add_feature(meta)

# Write to file
write_manifest_file("manifest.json", manifest)
```

### Inspecting Column Metadata

```python
from mlforge import LocalStore

store = LocalStore("./feature_store")
metadata = store.read_metadata("user_spend")

if metadata and metadata.columns:
    for col in metadata.columns:
        if col.agg:
            # Rolling aggregation column
            print(f"{col.name}: {col.agg}({col.input}) over {col.window}")
        else:
            # Regular column
            print(f"{col.name}: {col.dtype}")
```

## Metadata Schema

### Feature Metadata JSON

Per-feature metadata is stored in `_metadata/<feature_name>.meta.json`:

```json
{
  "name": "merchant_spend",
  "path": "merchant_spend.parquet",
  "entity": "merchant_id",
  "keys": ["merchant_id"],
  "source": "data/transactions.parquet",
  "row_count": 15482,
  "last_updated": "2024-01-16T08:30:00Z",
  "timestamp": "transaction_date",
  "interval": "1d",
  "columns": [
    {"name": "merchant_id", "dtype": "Utf8"},
    {"name": "transaction_date", "dtype": "Date"},
    {
      "name": "amt__count__7d",
      "dtype": "UInt32",
      "input": "amt",
      "agg": "count",
      "window": "7d"
    },
    {
      "name": "amt__sum__7d",
      "dtype": "Float64",
      "input": "amt",
      "agg": "sum",
      "window": "7d"
    }
  ],
  "tags": ["merchants"],
  "description": "Merchant spend aggregations"
}
```

### Consolidated Manifest JSON

The manifest consolidates all feature metadata into a single file:

```json
{
  "version": "1.0",
  "generated_at": "2024-01-16T08:30:00Z",
  "features": {
    "merchant_spend": {
      "name": "merchant_spend",
      "path": "merchant_spend.parquet",
      ...
    },
    "user_spend": {
      "name": "user_spend",
      "path": "user_spend.parquet",
      ...
    }
  }
}
```

## Column Naming Convention

For features with Rolling metrics, columns follow this pattern:

```
{feature_name}__{column}__{aggregation}__{interval}__{window}
```

Examples:

- `user_spend__amt__sum__1d__7d` - Sum of `amt` over 7-day window with 1-day interval
- `user_spend__amt__count__1d__30d` - Count of `amt` over 30-day window with 1-day interval

The `derive_column_metadata()` function parses these column names to extract:

- `input`: Source column name (`amt`)
- `agg`: Aggregation type (`sum`, `count`, etc.)
- `window`: Time window (`7d`, `30d`, etc.)

## See Also

- [CLI Reference](../cli.md) - `inspect` and `manifest` commands
- [Building Features](../user-guide/building-features.md) - How metadata is generated during builds
- [Store API](store.md) - Store metadata methods
