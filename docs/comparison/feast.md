# mlforge vs Feast

A detailed comparison of mlforge and Feast, the most popular open-source feature store.

## Overview

| Aspect | mlforge | Feast |
|--------|---------|-------|
| **Philosophy** | Simple, local-first, Python-native | Infrastructure-heavy, Kubernetes-focused |
| **Learning curve** | Minutes | Hours to days |
| **Setup complexity** | `mlforge init` | Registry, offline store, online store, Kubernetes |
| **Primary use case** | Small-to-medium teams, rapid iteration | Enterprise, large-scale production |

## Feature Definition: Side-by-Side

### mlforge: Single Decorator

```python
import mlforge as mlf
import polars as pl

@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    timestamp="transaction_date",
    interval="1d",
    metrics=[
        mlf.Aggregate(field="amount", function="sum", windows=["7d", "30d"],
                      name="total_spend", description="Total amount spent"),
        mlf.Aggregate(field="amount", function="mean", windows=["7d", "30d"],
                      name="avg_spend", description="Average transaction amount"),
        mlf.Aggregate(field="amount", function="count", windows=["7d", "30d"],
                      name="txn_count", description="Number of transactions"),
    ],
    validators={"amount": [mlf.not_null(), mlf.greater_than(0)]},
    description="User spending patterns"
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(["user_id", "transaction_date", "amount"])
```

**Lines of code: 19**

### Feast: Multiple Classes Required

```python
from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float64, Int64
from datetime import timedelta

# Step 1: Define the data source
transactions_source = FileSource(
    path="data/transactions.parquet",
    timestamp_field="transaction_date",
)

# Step 2: Define the entity
user = Entity(
    name="user",
    join_keys=["user_id"],
    description="User entity",
)

# Step 3: Define the feature view
user_spend_fv = FeatureView(
    name="user_spend",
    entities=[user],
    ttl=timedelta(days=365),
    schema=[
        Field(name="amount_sum_7d", dtype=Float64),
        Field(name="amount_mean_7d", dtype=Float64),
        Field(name="amount_count_7d", dtype=Int64),
        Field(name="amount_sum_30d", dtype=Float64),
        Field(name="amount_mean_30d", dtype=Float64),
        Field(name="amount_count_30d", dtype=Int64),
    ],
    source=transactions_source,
    description="User spending patterns",
)

# Step 4: Compute aggregations separately (Feast doesn't compute them)
# You need to pre-compute these in a separate pipeline (Spark, dbt, etc.)
```

**Lines of code: 35+ (plus separate aggregation pipeline)**

### Key Differences

| Aspect | mlforge | Feast |
|--------|---------|-------|
| **Feature definition** | Single `@feature` decorator | Entity + FeatureView + FileSource classes |
| **Aggregations** | Built-in `Aggregate` metrics | Pre-compute externally |
| **Validation** | Built-in validators | Requires Great Expectations integration |
| **Type inference** | Automatic from Polars | Manual schema definition |

---

## Project Setup

### mlforge: One Command

```bash
mlforge init my-features --profile
cd my-features
mlforge build
```

Creates a complete project with environment profiles:

```
my-features/
├── src/my_features/
│   ├── definitions.py
│   ├── features.py
│   └── entities.py
├── mlforge.yaml          # Environment profiles
├── feature_store/
└── pyproject.toml
```

### Feast: Multi-Step Setup

```bash
pip install feast
feast init my_project
cd my_project

# Edit feature_store.yaml
# Define entities, sources, feature views
# Apply configuration
feast apply

# Materialize (requires online store)
feast materialize-incremental $(date +%Y-%m-%d)
```

**Feast requires:**
- Registry (SQLite, PostgreSQL, or cloud)
- Offline store (file, BigQuery, Snowflake, etc.)
- Online store (Redis, DynamoDB, etc.) for serving
- Kubernetes for production deployment

---

## Environment Configuration

### mlforge: YAML Profiles

```yaml
# mlforge.yaml
default_profile: dev

profiles:
  dev:
    offline_store:
      KIND: local
      path: ./feature_store

  production:
    offline_store:
      KIND: s3
      bucket: ${oc.env:S3_BUCKET}
      prefix: features
    online_store:
      KIND: redis
      host: ${oc.env:REDIS_HOST}
```

Switch environments:

```bash
mlforge build --profile production
# or
export MLFORGE_PROFILE=production
mlforge build
```

### Feast: Single Config File

```yaml
# feature_store.yaml
project: my_project
registry: s3://my-bucket/registry.db
provider: aws
online_store:
  type: redis
  connection_string: redis://...
offline_store:
  type: file
```

No built-in profile switching - requires separate config files or environment variable substitution.

---

## Versioning: The Biggest Gap

### mlforge: Automatic Semantic Versioning

```bash
# First build creates v1.0.0
mlforge build

# Add a column → v1.1.0 (MINOR)
# Remove a column → v2.0.0 (MAJOR)
# Same schema, new data → v1.0.1 (PATCH)

# Compare versions
mlforge diff user_spend

# Rollback if needed
mlforge rollback user_spend --previous
```

Retrieve specific versions:

```python
from my_features.definitions import defs

training_df = defs.get_training_data(
    features=[
        "user_spend",                    # Latest version
        ("merchant_risk", "1.0.0"),      # Pinned version
    ],
    entity_df=labels_df,
)
```

### Feast: No Built-in Versioning

Feast has no built-in feature versioning. Users must:

1. Create new FeatureView names manually (`user_spend_v2`)
2. Manage version history externally
3. No automatic change detection

---

## Team Collaboration

### mlforge: Git-Native Workflow

```bash
# Developer 1: Build and commit metadata
mlforge build --features user_spend
git add feature_store/user_spend/
git commit -m "feat: add user_spend feature"
git push

# Developer 2: Pull and sync
git pull
mlforge sync  # Rebuilds data from metadata
```

**What gets committed:**
- `.meta.json` (feature metadata)
- `_latest.json` (version pointer)

**What's ignored:**
- `data.parquet` (auto-generated `.gitignore`)

### Feast: Central Registry

Requires a shared registry that all team members connect to:

```yaml
registry: s3://my-bucket/registry.db
```

**Challenges:**
- Registry conflicts when multiple developers push changes
- No built-in sync mechanism
- Requires cloud infrastructure for collaboration

---

## Feature Retrieval

### mlforge: Definitions Methods

```python
from my_features.definitions import defs

# Training data with point-in-time correctness
training_df = defs.get_training_data(
    features=["user_spend", "merchant_revenue"],
    entity_df=labels_df,
    timestamp="label_time",
)

# Online inference
features_df = defs.get_online_features(
    features=["user_spend", "merchant_revenue"],
    entity_df=request_df,
)
```

Entity keys are handled automatically based on feature definitions.

### Feast: Store Methods

```python
from feast import FeatureStore

store = FeatureStore(repo_path=".")

# Historical features
training_df = store.get_historical_features(
    entity_df=labels_df,
    features=["user_spend:amount_sum_7d", "user_spend:amount_mean_7d"],
).to_df()

# Online features
features = store.get_online_features(
    features=["user_spend:amount_sum_7d"],
    entity_rows=[{"user_id": "u1"}],
).to_dict()
```

---

## Data Validation

### mlforge: Built-in Validators

```python
@mlf.feature(
    keys=["user_id"],
    source="data.parquet",
    validators={
        "amount": [mlf.not_null(), mlf.greater_than(0)],
        "email": [mlf.matches_regex(r"^[\w.-]+@[\w.-]+\.\w+$")],
        "status": [mlf.is_in(["active", "inactive"])],
    }
)
def validated_feature(df): ...
```

Run validation:

```bash
mlforge validate
```

### Feast: External Integration

Feast recommends integrating with Great Expectations - no built-in validation.

---

## Online Serving

### mlforge: Redis via Profiles

```yaml
# mlforge.yaml
profiles:
  production:
    offline_store:
      KIND: s3
      bucket: my-features
    online_store:
      KIND: redis
      host: ${oc.env:REDIS_HOST}
```

```bash
mlforge build --online --profile production
```

```python
features_df = defs.get_online_features(
    features=["user_spend"],
    entity_df=request_df,
)
```

### Feast: Multiple Online Stores

```yaml
online_store:
  type: redis
  connection_string: redis://localhost:6379
```

```bash
feast materialize-incremental $(date +%Y-%m-%d)
```

Feast supports more online stores (DynamoDB, Bigtable, etc.), but requires more setup.

---

## CLI Comparison

### mlforge CLI

```bash
mlforge init my-project --profile  # Initialize project
mlforge build                      # Build all features
mlforge build --online             # Build to online store
mlforge build --profile production # Use specific profile
mlforge validate                   # Run validators
mlforge list features              # List features
mlforge list entities              # List entities
mlforge inspect feature user_spend # Show metadata
mlforge diff user_spend            # Compare versions
mlforge rollback user_spend 1.0.0  # Rollback version
mlforge sync                       # Rebuild from metadata
mlforge profile --validate         # Validate store connectivity
```

### Feast CLI

```bash
feast init my_project              # Initialize project
feast apply                        # Apply configuration
feast materialize-incremental      # Materialize to online
feast materialize                  # Full materialization
feast ui                           # Start web UI
```

---

## When to Choose Each

### Choose mlforge When:

- You want **simplicity over features**
- You're a **small-to-medium team** (1-20 data scientists)
- You need **fast iteration** and local development
- You want **automatic versioning** without manual tracking
- You prefer **Git-native workflows**
- You don't want to manage **Kubernetes infrastructure**
- You need **built-in aggregations** (rolling windows)
- You want **environment profiles** (dev/staging/prod)

### Choose Feast When:

- You need **enterprise scale** (100+ data scientists)
- You have **existing Kubernetes infrastructure**
- You need **many online store options** (DynamoDB, Bigtable, etc.)
- You have **dedicated MLOps team** to manage infrastructure
- You need **streaming features** (Kafka, Kinesis)
- You're already using **Spark/Flink** for transformations

---

## Migration from Feast to mlforge

### Step 1: Initialize Project

```bash
mlforge init my-features --profile
```

### Step 2: Convert Feature Views

**Feast:**
```python
user_spend_fv = FeatureView(
    name="user_spend",
    entities=[user],
    schema=[Field(name="amount_sum_7d", dtype=Float64)],
    source=transactions_source,
)
```

**mlforge:**
```python
@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    timestamp="transaction_date",
    metrics=[
        mlf.Aggregate(field="amount", function="sum", windows=["7d"],
                      name="total_spend", description="Total amount spent")
    ]
)
def user_spend(df):
    return df.select(["user_id", "transaction_date", "amount"])
```

### Step 3: Configure Profiles

```yaml
# mlforge.yaml
profiles:
  dev:
    offline_store:
      KIND: local
      path: ./feature_store
  production:
    offline_store:
      KIND: s3
      bucket: my-features
    online_store:
      KIND: redis
      host: ${oc.env:REDIS_HOST}
```

### Step 4: Build and Validate

```bash
mlforge build
mlforge validate
mlforge profile --validate
```

---

## Summary

| Capability | mlforge | Feast |
|-----------|---------|-------|
| **Setup time** | 1 command | Hours |
| **Feature definition** | 15 lines | 35+ lines |
| **Environment profiles** | Built-in YAML | Manual |
| **Versioning** | Automatic semantic | Manual/none |
| **Version diff/rollback** | Built-in CLI | None |
| **Local development** | First-class | Afterthought |
| **Team collaboration** | Git-native | Central registry |
| **Aggregations** | Built-in | External |
| **Validation** | Built-in | External |
| **Infrastructure** | None required | Kubernetes |
| **Scale** | Small-to-medium | Enterprise |

**Bottom line:** mlforge is the feature store that gets out of your way. If you want simplicity and fast iteration, choose mlforge. If you need enterprise scale and have dedicated MLOps resources, consider Feast.
