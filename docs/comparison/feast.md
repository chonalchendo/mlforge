# mlforge vs Feast

A detailed comparison of mlforge and Feast, the most popular open-source feature store.

## Overview

| Aspect | mlforge | Feast |
|--------|---------|-------|
| **Philosophy** | Simple, local-first, Python-native | Infrastructure-heavy, Kubernetes-focused |
| **Learning curve** | Minutes | Hours to days |
| **Setup complexity** | `pip install mlforge-sdk` | Registry, offline store, online store, Kubernetes |
| **Primary use case** | Small-to-medium teams, rapid iteration | Enterprise, large-scale production |
| **GitHub stars** | Growing | 6.6K+ |
| **Downloads** | Growing | 12M+ |

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
        mlf.Rolling(
            windows=["7d", "30d"],
            aggregations={"amount": ["sum", "mean", "count"]}
        )
    ],
    validators={"amount": [mlf.not_null(), mlf.greater_than(0)]},
    description="User spending patterns"
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(["user_id", "transaction_date", "amount"])
```

**Lines of code: 15**

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
| **Aggregations** | Built-in `Rolling` metrics | Pre-compute externally |
| **Validation** | Built-in validators | Requires Great Expectations integration |
| **Type inference** | Automatic from Polars | Manual schema definition |

---

## Versioning: The Biggest Gap

### mlforge: Automatic Semantic Versioning

mlforge automatically versions features using semantic versioning:

```python
# First build creates v1.0.0
defs.build()

# Add a column → v1.1.0 (MINOR)
# Remove a column → v2.0.0 (MAJOR)
# Same schema, new data → v1.0.1 (PATCH)

# Retrieve specific version
training_df = mlf.get_training_data(
    features=[
        "user_spend",                    # Latest version
        ("merchant_risk", "1.0.0"),      # Pinned version
    ],
    entity_df=labels_df,
    store=store,
)
```

**Version detection is automatic:**
- Schema hash detects column changes
- Config hash detects metric/key changes
- Content hash detects data changes

### Feast: No Explicit Versioning

Feast has no built-in feature versioning. Users must:

1. Create new FeatureView names manually (`user_spend_v2`)
2. Manage version history externally
3. No automatic change detection

**From Feast GitHub Issue #5789:**
> "Feature version support requested - users want to manage multiple versions of the same feature"

This is a frequently requested feature that Feast hasn't implemented.

---

## Local Development

### mlforge: Works Out of the Box

```bash
# Install
pip install mlforge-sdk

# Build features
mlforge build

# That's it. No infrastructure needed.
```

Features are stored as Parquet files:
```
feature_store/
├── user_spend/
│   ├── 1.0.0/
│   │   ├── data.parquet
│   │   └── .meta.json
│   └── _latest.json
```

### Feast: Requires Infrastructure

```bash
# Install
pip install feast

# Initialize project
feast init my_project

# Apply configuration (creates registry)
feast apply

# Materialize to online store (requires online store setup)
feast materialize-incremental $(date +%Y-%m-%d)
```

**Feast requires:**
- Registry (SQLite, PostgreSQL, or cloud)
- Offline store (file, BigQuery, Snowflake, etc.)
- Online store (Redis, DynamoDB, etc.) for serving
- Kubernetes for production deployment

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
mlforge sync  # Rebuilds data.parquet from metadata
```

**What gets committed:**
- `.meta.json` (feature metadata)
- `_latest.json` (version pointer)

**What's ignored:**
- `data.parquet` (auto-generated `.gitignore`)

### Feast: Central Registry

Feast requires a central registry that all team members connect to:

```python
# feast_repo/feature_store.yaml
project: my_project
registry: s3://my-bucket/registry.db  # Shared registry
provider: aws
online_store:
  type: redis
  connection_string: redis://...
```

**Challenges:**
- Registry conflicts when multiple developers push changes
- No built-in sync mechanism
- Requires cloud infrastructure for team collaboration

---

## Compute Engines

### mlforge: Polars + DuckDB

```python
# Default: DuckDB (optimized for rolling aggregations)
defs = mlf.Definitions(
    features=[features],
    offline_store=store,
    default_engine="duckdb",  # or "polars"
)

# Per-feature override
@mlf.feature(
    keys=["user_id"],
    source="data.parquet",
    engine="polars",  # Use Polars for this feature
)
def my_feature(df): ...
```

**Both engines:**
- Work locally without cluster setup
- Handle datasets up to ~100GB
- Use the same Polars API for user code

### Feast: External Compute

Feast doesn't compute features - it stores and serves them. You need:

- **Spark** for batch transformations
- **Flink** for streaming transformations
- **dbt** for SQL transformations

```python
# Feast just stores pre-computed features
# You need a separate pipeline to compute them
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

**9 built-in validators:**
- `not_null()`, `unique()`
- `greater_than()`, `less_than()`, `in_range()`
- `greater_than_or_equal()`, `less_than_or_equal()`
- `matches_regex()`, `is_in()`

### Feast: External Integration

Feast recommends integrating with Great Expectations:

```python
# Requires separate Great Expectations setup
# No built-in validation
```

---

## Point-in-Time Correctness

### mlforge: Built-in Asof Joins

```python
training_df = mlf.get_training_data(
    features=["user_spend"],
    entity_df=labels_df,
    store=store,
    timestamp="label_time",  # Point-in-time join
)
```

**Automatic behavior:**
- Detects timestamp columns
- Uses backward-looking asof join
- Prevents future data leakage

### Feast: Also Supported

```python
training_df = store.get_historical_features(
    entity_df=labels_df,
    features=["user_spend:amount_sum_7d"],
).to_df()
```

Both tools support point-in-time correctness - this is table stakes for feature stores.

---

## Online Serving

### mlforge: Simple Redis Integration

```python
from mlforge.online import RedisStore

# Build to online store
defs.build(online=True)

# Retrieve for inference
features_df = mlf.get_online_features(
    features=["user_spend"],
    entity_df=request_df,
    store=RedisStore(host="localhost"),
)
```

### Feast: Multiple Online Stores

```python
# feast_repo/feature_store.yaml
online_store:
  type: redis
  connection_string: redis://localhost:6379

# Materialize to online store
feast materialize-incremental $(date +%Y-%m-%d)

# Retrieve
features = store.get_online_features(
    features=["user_spend:amount_sum_7d"],
    entity_rows=[{"user_id": "u1"}],
).to_dict()
```

Feast supports more online stores (DynamoDB, Bigtable, etc.), but requires more setup.

---

## CLI Comparison

### mlforge CLI

```bash
mlforge build                    # Build all features
mlforge build --features user_spend
mlforge build --tags users
mlforge build --version 2.0.0    # Override version

mlforge validate                 # Run validators
mlforge list                     # List features
mlforge inspect user_spend       # Show metadata
mlforge versions user_spend      # List versions
mlforge sync                     # Rebuild from metadata
```

### Feast CLI

```bash
feast init my_project            # Initialize project
feast apply                      # Apply configuration
feast materialize-incremental    # Materialize to online
feast materialize                # Full materialization
feast ui                         # Start web UI
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

### Choose Feast When:

- You need **enterprise scale** (100+ data scientists)
- You have **existing Kubernetes infrastructure**
- You need **many online store options** (DynamoDB, Bigtable, etc.)
- You have **dedicated MLOps team** to manage infrastructure
- You need **streaming features** (Kafka, Kinesis)
- You're already using **Spark/Flink** for transformations

---

## Migration from Feast to mlforge

If you're considering migrating from Feast:

### Step 1: Convert Feature Views to @feature Decorators

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
    metrics=[mlf.Rolling(windows=["7d"], aggregations={"amount": ["sum"]})]
)
def user_spend(df):
    return df.select(["user_id", "transaction_date", "amount"])
```

### Step 2: Replace Registry with Git

- Remove Feast registry configuration
- Commit `.meta.json` files to Git
- Use `mlforge sync` for team collaboration

### Step 3: Simplify Infrastructure

- Remove Kubernetes deployment
- Use local Parquet files or S3
- Use Redis for online serving (same as Feast)

---

## Summary

| Capability | mlforge | Feast |
|-----------|---------|-------|
| **Setup time** | 5 minutes | Hours |
| **Feature definition** | 15 lines | 35+ lines |
| **Versioning** | Automatic semantic | Manual/none |
| **Local development** | First-class | Afterthought |
| **Team collaboration** | Git-native | Central registry |
| **Aggregations** | Built-in | External |
| **Validation** | Built-in | External |
| **Infrastructure** | None required | Kubernetes |
| **Scale** | Small-to-medium | Enterprise |

**Bottom line:** mlforge is the feature store that gets out of your way. If you want simplicity and fast iteration, choose mlforge. If you need enterprise scale and have dedicated MLOps resources, consider Feast.
