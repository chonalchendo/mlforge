# Online Stores

Online stores provide low-latency feature serving for real-time inference. mlforge supports multiple online store backends.

## Overview

| Store | Use Case | Latency | Setup |
|-------|----------|---------|-------|
| **RedisStore** | General real-time inference | ~1ms | Redis server |
| **DynamoDBStore** | Serverless, AWS-native | ~5ms | AWS account |
| **DatabricksOnlineStore** | Databricks-managed serving | ~10ms | Databricks workspace |

---

## Redis Store

Redis is the recommended online store for most use cases. It provides sub-millisecond latency and simple setup.

### Installation

Install mlforge with Redis support:

=== "pip"
    ```bash
    pip install mlforge-sdk[redis]
    ```

=== "uv"
    ```bash
    uv add mlforge-sdk[redis]
    ```

### Starting Redis

=== "Docker"
    ```bash
    docker run -d --name redis -p 6379:6379 redis:7-alpine
    ```

=== "Docker Compose"
    ```yaml
    # docker-compose.yml
    services:
      redis:
        image: redis:7-alpine
        ports:
          - "6379:6379"
    ```
    ```bash
    docker-compose up -d
    ```

=== "Local Install"
    ```bash
    # macOS
    brew install redis
    redis-server

    # Ubuntu
    sudo apt install redis-server
    sudo systemctl start redis
    ```

### Configuration

```python
import mlforge as mlf
from mlforge.stores import RedisStore

defs = mlf.Definitions(
    name="my-project",
    features=[user_spend, merchant_risk],
    offline_store=mlf.LocalStore("./feature_store"),
    online_store=RedisStore(
        host="localhost",
        port=6379,
        db=0,
        password=None,  # Set for authenticated Redis
        prefix="mlforge",  # Key prefix
        ttl=None,  # Optional TTL in seconds
    ),
)
```

### Key Format

Features are stored with keys in the format:

```
{prefix}:{feature_name}:{entity_hash}
```

Example:
```
mlforge:user_spend:a1b2c3d4e5f6g7h8
```

### When to Use

- General-purpose real-time inference
- Self-managed infrastructure
- Sub-millisecond latency requirements
- Simple setup and operations

---

## DynamoDB Store

DynamoDB provides serverless, fully managed feature storage with single-digit millisecond latency. Ideal for AWS-native deployments.

### Installation

Install mlforge with DynamoDB support:

=== "pip"
    ```bash
    pip install mlforge-sdk[dynamodb]
    ```

=== "uv"
    ```bash
    uv add mlforge-sdk[dynamodb]
    ```

### Configuration

```python
import mlforge as mlf
from mlforge.stores import DynamoDBStore

defs = mlf.Definitions(
    name="my-project",
    features=[user_spend],
    offline_store=mlf.S3Store(bucket="my-features"),
    online_store=DynamoDBStore(
        table_name="my-features",
        region="us-west-2",
        ttl_seconds=86400 * 7,  # 7 days
    ),
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `table_name` | str | required | DynamoDB table name |
| `region` | str | None | AWS region (uses default from AWS config) |
| `endpoint_url` | str | None | Custom endpoint (for DynamoDB Local) |
| `ttl_seconds` | int | None | Time-to-live in seconds (None = no expiry) |
| `auto_create` | bool | True | Create table if it doesn't exist |

### Table Schema

DynamoDBStore uses the following schema:

| Attribute | Type | Description |
|-----------|------|-------------|
| `entity_key` | String (PK) | Hash of entity keys |
| `feature_name` | String (SK) | Feature name |
| `feature_values` | String | JSON-encoded feature values |
| `updated_at` | String | ISO timestamp |
| `ttl` | Number | Unix timestamp for expiration |

### IAM Permissions

Minimal IAM policy for DynamoDBStore:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:BatchGetItem",
        "dynamodb:BatchWriteItem",
        "dynamodb:DeleteItem",
        "dynamodb:DescribeTable"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/my-features"
    }
  ]
}
```

Add `dynamodb:CreateTable` if using `auto_create=True`:

```json
{
  "Effect": "Allow",
  "Action": ["dynamodb:CreateTable", "dynamodb:UpdateTimeToLive"],
  "Resource": "arn:aws:dynamodb:*:*:table/my-features"
}
```

### Local Development

Use DynamoDB Local for development:

```bash
docker run -d -p 8000:8000 amazon/dynamodb-local
```

```python
store = DynamoDBStore(
    table_name="test-features",
    endpoint_url="http://localhost:8000",
)
```

### When to Use

- AWS-native deployments
- Serverless architectures (Lambda, Fargate)
- Pay-per-request pricing model
- No infrastructure management

---

## Databricks Online Store

Databricks Online Tables provide managed feature serving that automatically syncs from Delta tables in Unity Catalog.

### Prerequisites

- Databricks workspace with Unity Catalog enabled
- `UnityCatalogStore` as offline store
- `engine="pyspark"` in Definitions

### Installation

Install mlforge with Databricks support:

=== "pip"
    ```bash
    pip install mlforge-sdk[databricks]
    ```

=== "uv"
    ```bash
    uv add mlforge-sdk[databricks]
    ```

### Configuration

```python
import mlforge as mlf
from mlforge.stores import DatabricksOnlineStore, UnityCatalogStore

defs = mlf.Definitions(
    name="my-project",
    features=[user_spend],
    offline_store=UnityCatalogStore(
        catalog="main",
        schema="features",
    ),
    online_store=DatabricksOnlineStore(
        catalog="main",
        schema="features_online",
        sync_mode="triggered",
    ),
    engine="pyspark",
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `catalog` | str | required | Unity Catalog catalog name |
| `schema` | str | "features_online" | Schema for Online Tables |
| `sync_mode` | str | "triggered" | Sync mode: "snapshot", "triggered", or "continuous" |
| `auto_create` | bool | True | Auto-create Online Tables |
| `warehouse_id` | str | None | SQL warehouse ID for queries |

### Sync Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `snapshot` | Full refresh on each sync | Small tables, infrequent updates |
| `triggered` | Incremental sync on demand | Default, manual control |
| `continuous` | Near real-time streaming sync | Real-time features |

### How It Works

1. Features are built to Delta tables in Unity Catalog (offline store)
2. Online Tables automatically sync from the Delta tables
3. Reads query the Online Tables for low-latency serving

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Feature Build  │────▶│  Delta Table    │────▶│  Online Table   │
│  (PySpark)      │     │  (Unity Catalog)│     │  (Auto-sync)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Important Notes

!!! warning "No Direct Writes"
    Databricks Online Tables don't support direct writes. Data flows from the offline Delta table:

    ```python
    # This will raise NotImplementedError
    store.write(feature_name="user_spend", entity_keys={...}, values={...})

    # Instead, build to offline store and sync
    defs.build(features=["user_spend"], online=True)
    ```

### When to Use

- Databricks-native deployments
- Unity Catalog for governance
- Automatic sync without custom pipelines
- Integration with Databricks ML workflows

---

## Reading Features

### Low-level API

All online stores support the same interface:

```python
from mlforge.stores import RedisStore  # or DynamoDBStore

store = RedisStore(host="localhost")

# Single entity
value = store.read(
    feature_name="user_spend",
    entity_keys={"user_id": "12345"}
)
# Returns: {"amt__sum__7d": 150.0, "amt__count__7d": 5}

# Batch read
values = store.read_batch(
    feature_name="user_spend",
    entity_keys=[
        {"user_id": "12345"},
        {"user_id": "67890"},
    ]
)
# Returns: [{"amt__sum__7d": 150.0, ...}, {"amt__sum__7d": 200.0, ...}]
```

### High-level API (Recommended)

Use `get_online_features()` for production inference:

```python
import mlforge as mlf
from mlforge.stores import RedisStore
import polars as pl

store = RedisStore(host="localhost")
with_user_id = mlf.entity_key("first", "last", "dob", alias="user_id")

# Inference request
request_df = pl.DataFrame({
    "request_id": ["req_001", "req_002"],
    "first": ["John", "Jane"],
    "last": ["Doe", "Smith"],
    "dob": ["1990-01-15", "1985-06-20"],
})

# Retrieve features (applies entity transform, joins results)
features_df = mlf.get_online_features(
    features=["user_spend"],
    entity_df=request_df,
    store=store,
    entities=[with_user_id],
)
```

---

## Building to Online Store

Build features to the online store using the `--online` flag:

```bash
mlforge build --online
```

Or programmatically:

```python
defs.build(online=True)
```

This extracts the latest value per entity and writes to the online store.

---

## Connection Options

### TTL (Time-to-Live)

Set automatic expiration for features:

=== "Redis"
    ```python
    store = RedisStore(host="localhost", ttl=86400)  # 24 hours
    ```

=== "DynamoDB"
    ```python
    store = DynamoDBStore(table_name="features", ttl_seconds=86400)
    ```

### Verify Connection

```python
store = RedisStore(host="localhost")

if not store.ping():
    raise RuntimeError("Cannot connect to online store")
```

---

## Best Practices

### 1. Set TTL for Stale Data Prevention

```python
store = RedisStore(host="localhost", ttl=7 * 24 * 3600)  # 7 days
```

### 2. Use Separate Environments

```python
# Development
dev_store = RedisStore(host="localhost", db=0)

# Production
prod_store = RedisStore(host="redis.prod.internal", db=0)
```

### 3. Monitor Store Health

```python
if not store.ping():
    logger.error("Online store unavailable")
    # Fall back to offline store or return cached values
```

### 4. Batch Reads for Performance

```python
# Prefer batch reads over multiple single reads
values = store.read_batch(feature_name="user_spend", entity_keys=keys)
```

---

## Troubleshooting

### Connection Refused (Redis)

```
redis.exceptions.ConnectionError: Error connecting to localhost:6379
```

**Solution**: Ensure Redis is running:
```bash
docker ps | grep redis
redis-cli ping
```

### Authentication Error (DynamoDB)

```
botocore.exceptions.NoCredentialsError: Unable to locate credentials
```

**Solution**: Configure AWS credentials:
```bash
aws configure
# or
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
```

### Permission Denied (DynamoDB)

```
PermissionError: Cannot create table 'my-features'
```

**Solution**: Grant `dynamodb:CreateTable` permission or use `auto_create=False` with a pre-created table.

---

## Next Steps

- [Retrieving Features](retrieving-features.md) - Use `get_online_features()`
- [Building Features](building-features.md) - Build to online store
- [Storage Backends](storage-backends.md) - Configure offline stores
- [API Reference](../api/online.md) - Online store API documentation
