# Databricks Unity Catalog + Online Tables Example

A comprehensive example demonstrating mlforge integration with Databricks for enterprise ML feature engineering.

## Overview

This example shows how to build a fraud detection feature pipeline using:

- **Databricks Unity Catalog** - Offline feature storage with governance, lineage, and versioning via Delta Lake
- **Databricks Online Tables** - Low-latency feature serving for real-time inference
- **mlforge** - Feature engineering SDK with point-in-time correctness

## Architecture

```
                          ┌─────────────────────────────────────────────────────────┐
                          │                   Databricks Lakehouse                   │
                          │                                                          │
┌──────────────┐          │  ┌─────────────────────┐     ┌─────────────────────┐   │
│ Transaction  │──────────┼─▶│   Unity Catalog     │────▶│   Online Tables     │   │
│    Source    │  Build   │  │   (Delta Tables)    │Sync │  (Low-latency)      │   │
└──────────────┘          │  │                     │     │                     │   │
                          │  │ - customer_spend    │     │ - customer_spend    │   │
                          │  │ - merchant_spend    │     │ - customer_velocity │   │
                          │  │ - customer_velocity │     │                     │   │
                          │  └─────────────────────┘     └─────────────────────┘   │
                          │            │                           │               │
                          └────────────┼───────────────────────────┼───────────────┘
                                       │                           │
                                       ▼                           ▼
                          ┌─────────────────────┐     ┌─────────────────────┐
                          │   Training Data     │     │   Real-time         │
                          │   Retrieval         │     │   Inference         │
                          │                     │     │                     │
                          │ get_training_data() │     │ get_online_features │
                          └─────────────────────┘     └─────────────────────┘
```

## Features Demonstrated

### Entity Definitions

| Entity | Join Key | Generated From | Purpose |
|--------|----------|----------------|---------|
| `customer` | `customer_id` | first_name, last_name, dob | Customer spending patterns |
| `merchant` | `merchant_id` | merchant_name | Merchant transaction volumes |
| `transaction` | `transaction_id` | - | Individual transaction details |
| `customer_merchant` | `[customer_id, merchant_id]` | - | Cross-entity affinity features |

### Feature Definitions

| Feature | Entity | Windows | Aggregations | Purpose |
|---------|--------|---------|--------------|---------|
| `customer_spend` | customer | 7d, 30d, 90d | sum, mean, count, std, min, max | Spending patterns |
| `merchant_spend` | merchant | 7d, 30d, 90d | sum, mean, count, std, min, max | Merchant volumes |
| `customer_velocity` | customer | 1d, 7d | count | Fraud velocity signals |
| `customer_merchant_affinity` | customer_merchant | 30d, 90d | sum, count, mean | Customer-merchant patterns |
| `customer_latest_transaction` | customer | - | point-in-time | Latest transaction details |

### Data Validators

```python
validators={
    "amount": [
        mlf.greater_than_or_equal(value=0),
        mlf.less_than(value=100000),
    ],
    "customer_id": [mlf.not_null()],
}
```

## Quick Start

### 1. Local Development

```bash
# From repository root
cd examples/databricks

# Generate sample data
uv run python src/databricks_features/generate_data.py

# Build features (local store)
uv run mlforge build

# Run demo
uv run python src/databricks_features/main.py
```

### 2. Train Model

```bash
# Build features first
uv run mlforge build

# Train fraud detection model
uv run python src/databricks_features/train.py
```

### 3. Databricks Deployment

```bash
# Set environment variables
export DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
export DATABRICKS_TOKEN=your-token

# Build to Unity Catalog
uv run mlforge build --profile databricks

# Features are automatically synced to Online Tables based on sync_mode
```

## Project Structure

```
databricks/
├── src/databricks_features/
│   ├── __init__.py
│   ├── entities.py        # Entity definitions with surrogate keys
│   ├── features.py        # Feature definitions with rolling metrics
│   ├── definitions.py     # Definitions registry
│   ├── generate_data.py   # Synthetic data generator
│   ├── main.py            # Demo: build + retrieve features
│   ├── train.py           # Model training pipeline
│   └── serve.py           # Online serving demonstration
├── data/
│   └── transactions.parquet  # Transaction data (generated)
├── feature_store/            # Local feature store (gitignored)
├── mlforge.yaml              # Profile configuration
├── pyproject.toml
└── README.md
```

## Configuration Profiles

The `mlforge.yaml` file defines storage backends for different environments:

```yaml
default_profile: dev

profiles:
  # Local development
  dev:
    offline_store:
      KIND: local
      path: ./feature_store

  # Databricks production
  databricks:
    offline_store:
      KIND: unity_catalog
      catalog: main
      schema: ml_features
    online_store:
      KIND: databricks_online
      catalog: main
      schema: ml_features_online
      sync_mode: triggered

  # Real-time streaming sync
  databricks_realtime:
    offline_store:
      KIND: unity_catalog
      catalog: main
      schema: ml_features
    online_store:
      KIND: databricks_online
      catalog: main
      schema: ml_features_online
      sync_mode: continuous
```

## Key Concepts

### 1. Surrogate Key Generation

```python
customer = mlf.Entity(
    name="customer",
    join_key="customer_id",
    from_columns=["first_name", "last_name", "date_of_birth"],
)
```

mlforge generates deterministic surrogate keys from PII columns, enabling:
- Consistent key generation across training and inference
- PII removal from feature tables
- Automatic key generation during feature retrieval

### 2. Rolling Window Aggregations

```python
spend_metrics = mlf.Rolling(
    windows=["7d", "30d", timedelta(days=90)],
    aggregations={
        "amount": ["sum", "mean", "count", "std", "min", "max"],
    },
)
```

Windows can be specified as strings (`"7d"`) or `timedelta` objects.

### 3. Point-in-Time Correctness

```python
training_df = defs.get_training_data(
    features=["customer_spend", "customer_velocity"],
    entity_df=entity_df,
    timestamp="label_time",  # Features computed as-of this time
)
```

Features are joined as-of the specified timestamp, preventing data leakage.

### 4. Unity Catalog Storage

Features stored as Delta tables with:
- Automatic versioning via Delta time travel
- Metadata tracking in `_mlforge_metadata` table
- Governance and lineage tracking
- SQL access for ad-hoc queries

### 5. Online Tables Sync

```yaml
online_store:
  KIND: databricks_online
  sync_mode: triggered  # or 'snapshot', 'continuous'
```

- `snapshot`: Full refresh on each sync
- `triggered`: Incremental sync on demand
- `continuous`: Near real-time streaming sync

## CLI Commands

```bash
# List all features
uv run mlforge list features

# List features by tag
uv run mlforge list features --tags "fraud"

# Inspect a feature
uv run mlforge inspect feature customer_spend

# Build specific features
uv run mlforge build --features "customer_spend,customer_velocity"

# Build by tag
uv run mlforge build --tags "core"

# Build with Databricks profile
uv run mlforge build --profile databricks

# Show current profile
uv run mlforge profile
```

## Databricks-Specific Notes

### Prerequisites

1. Databricks workspace with Unity Catalog enabled
2. Personal access token or OAuth credentials
3. Catalog and schema permissions

### Environment Variables

```bash
export DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
export DATABRICKS_TOKEN=dapi...
```

### SQL Warehouse (Optional)

For Online Tables with SQL warehouse:

```yaml
online_store:
  KIND: databricks_online
  warehouse_id: your-warehouse-id
```

### Delta Table Format

Features in Unity Catalog are stored as Delta tables:

```sql
-- Query features directly
SELECT * FROM main.ml_features.customer_spend
WHERE customer_id = 'abc123'

-- Query specific version
SELECT * FROM main.ml_features.customer_spend VERSION AS OF 5
```

## Extending the Example

### Add New Features

1. Define entity in `entities.py` (if new)
2. Add feature function in `features.py`
3. Rebuild: `uv run mlforge build`

### Add Cross-Entity Features

```python
@mlf.feature(
    source=transactions,
    entities=[customer_merchant],  # Composite entity
    timestamp=timestamp,
    metrics=[affinity_metrics],
)
def customer_merchant_affinity(df: pl.DataFrame) -> pl.DataFrame:
    return df.select("customer_id", "merchant_id", "transaction_time", "amount")
```

### Add Custom Validators

```python
@mlf.feature(
    validators={
        "amount": [
            mlf.greater_than_or_equal(value=0),
            mlf.less_than(value=100000),
        ],
        "customer_id": [mlf.not_null()],
        "email": [mlf.matches_regex(r"^[\w.-]+@[\w.-]+\.\w+$")],
    },
)
def validated_feature(df: pl.DataFrame) -> pl.DataFrame:
    ...
```

## Troubleshooting

### Build Fails with Unity Catalog

1. Check credentials: `echo $DATABRICKS_HOST`
2. Verify catalog permissions in Databricks
3. Ensure schema exists or user has CREATE permission

### Online Tables Not Syncing

1. Check sync_mode in mlforge.yaml
2. Verify Delta table has data
3. Check Online Table status in Databricks UI

### Feature Retrieval Returns Nulls

1. Ensure features are built: `uv run mlforge list features`
2. Check timestamp alignment with data
3. Verify entity key generation matches

## Cleanup

```bash
# Remove local feature store
rm -rf feature_store/

# Remove generated data
rm -rf data/

# Databricks cleanup (run in Databricks)
# DROP SCHEMA main.ml_features CASCADE;
# DROP SCHEMA main.ml_features_online CASCADE;
```
