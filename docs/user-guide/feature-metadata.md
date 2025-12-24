# Feature Metadata

mlforge automatically captures and stores metadata for every feature you build. This metadata provides visibility into your feature store, making it easier to understand what features exist, when they were last updated, and what columns they contain.

## What is Captured

When you build a feature with `mlforge build`, the following metadata is automatically captured:

### Feature Configuration

- **Name**: Feature identifier
- **Entity**: Primary entity key
- **Keys**: All entity key columns
- **Timestamp**: Temporal column (if applicable)
- **Interval**: Time interval for rolling aggregations (if applicable)
- **Tags**: Feature grouping tags
- **Description**: Human-readable description from the `@feature` decorator

### Storage Details

- **Path**: Location of the materialized feature file
- **Source**: Path to the source data file
- **Row Count**: Number of rows in the materialized feature
- **Last Updated**: ISO 8601 timestamp of when the feature was last built

### Column Information

For each column in the feature:

- **Name**: Column name
- **Type**: Polars data type (e.g., `Utf8`, `Float64`, `Date`)
- **Input**: Source column (for aggregations)
- **Aggregation**: Type of aggregation (for rolling metrics)
- **Window**: Time window (for rolling metrics)

## Where Metadata is Stored

Metadata is stored in `.meta.json` files alongside your feature parquet files:

```
feature_store/
├── _metadata/
│   ├── user_spend.meta.json
│   ├── merchant_spend.meta.json
│   └── account_spend.meta.json
├── user_spend.parquet
├── merchant_spend.parquet
└── account_spend.parquet
```

Each `.meta.json` file contains the complete metadata for one feature in JSON format.

## Viewing Metadata

### Using the CLI

#### Inspect a Specific Feature

Use the `inspect` command to view detailed metadata for a feature:

```bash
mlforge inspect user_spend
```

This displays:

- Feature configuration
- Storage details
- Column information in a formatted table
- Tags and description

#### View All Features

Use the `manifest` command to see a summary of all features:

```bash
mlforge manifest
```

This shows a table with key metrics for each feature:

- Feature name
- Entity
- Row count
- Column count
- Last updated timestamp

### Programmatically

You can also read metadata in your Python code:

```python
from mlforge import LocalStore

store = LocalStore("./feature_store")

# Read metadata for a specific feature
metadata = store.read_metadata("user_spend")

if metadata:
    print(f"Feature: {metadata.name}")
    print(f"Rows: {metadata.row_count:,}")
    print(f"Last updated: {metadata.last_updated}")

    # Inspect columns
    for col in metadata.columns:
        if col.agg:
            print(f"  {col.name}: {col.agg}({col.input}) over {col.window}")
        else:
            print(f"  {col.name}: {col.dtype}")
```

## Rolling Metric Columns

For features with Rolling metrics, mlforge captures additional metadata about each aggregation column:

```python
from mlforge import feature
from mlforge.metrics import Rolling

@feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    timestamp="transaction_date",
    interval="1d",
    metrics=[
        Rolling(
            windows=["7d", "30d"],
            aggregations={"amt": ["sum", "count", "mean"]}
        )
    ]
)
def user_spend(df):
    return df
```

After building, the metadata will show:

- **Column**: `user_spend__amt__sum__1d__7d`
- **Type**: `Float64`
- **Input**: `amt`
- **Aggregation**: `sum`
- **Window**: `7d`

This makes it easy to understand what each rolling aggregation column represents.

## Consolidated Manifest

You can generate a consolidated `manifest.json` file that contains metadata for all features:

```bash
mlforge manifest --regenerate
```

This creates a single JSON file with all feature metadata, useful for:

- Documentation generation
- Feature catalog UIs
- Integration with other tools
- Version control tracking

The manifest file structure:

```json
{
  "version": "1.0",
  "generated_at": "2024-01-16T08:30:00Z",
  "features": {
    "user_spend": { ... },
    "merchant_spend": { ... },
    "account_spend": { ... }
  }
}
```

## Use Cases

### Feature Discovery

Quickly understand what features exist in your store:

```bash
mlforge manifest
```

### Debugging

Check when a feature was last built and how many rows it has:

```bash
mlforge inspect user_spend
```

### Monitoring

Track feature freshness by comparing `last_updated` timestamps:

```python
from mlforge import LocalStore
from datetime import datetime, timezone, timedelta

store = LocalStore("./feature_store")

# Find stale features (not updated in last 24 hours)
cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

for meta in store.list_metadata():
    last_updated = datetime.fromisoformat(meta.last_updated.replace('Z', '+00:00'))
    if last_updated < cutoff:
        print(f"Stale feature: {meta.name} (last updated {meta.last_updated})")
```

### Documentation

Generate feature catalogs from metadata:

```python
from mlforge import LocalStore

store = LocalStore("./feature_store")

print("# Feature Catalog\n")

for meta in store.list_metadata():
    print(f"## {meta.name}")
    if meta.description:
        print(f"\n{meta.description}\n")
    print(f"- **Entity**: {meta.entity}")
    print(f"- **Rows**: {meta.row_count:,}")
    print(f"- **Columns**: {len(meta.columns)}")
    if meta.tags:
        print(f"- **Tags**: {', '.join(meta.tags)}")
    print()
```

## Metadata Schema

See the [Manifest API Reference](../api/manifest.md#metadata-schema) for detailed JSON schema documentation.

## Next Steps

- [CLI Reference](../cli.md) - `inspect` and `manifest` commands
- [Manifest API](../api/manifest.md) - Programmatic access to metadata
- [Building Features](building-features.md) - How to build features that generate metadata
