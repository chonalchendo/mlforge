# Transactions Online Example

This example demonstrates using mlforge's online store feature with Redis for real-time feature serving.

## Overview

The online store pattern is used when you need low-latency feature retrieval for ML inference:

1. **Offline Store** (default): Features stored as Parquet files for training and batch processing
2. **Online Store**: Latest feature values stored in Redis for real-time serving

## Configuration

This example uses profile-based configuration via `mlforge.yaml`:

```yaml
default_profile: offline

profiles:
  offline:
    offline_store:
      KIND: local
      path: ./feature_store

  online:
    offline_store:
      KIND: local
      path: ./feature_store
    online_store:
      KIND: redis
      host: localhost
      port: 6379
      prefix: mlforge
```

### Profiles

| Profile | Offline Store | Online Store | Use Case |
|---------|--------------|--------------|----------|
| `offline` | LocalStore | None | Development, training |
| `online` | LocalStore | RedisStore | Real-time serving |

## Prerequisites

- Docker (for Redis)
- uv package manager

## Quick Start

### 1. Start Redis

```bash
docker-compose up -d
```

Verify Redis is running:

```bash
docker exec mlforge-redis redis-cli ping
# Should return: PONG
```

### 2. Install Dependencies

From the repository root:

```bash
uv sync
```

### 3. Build Features to Offline Store

```bash
cd examples/transactions-online
mlforge build
```

This uses the default `offline` profile and builds features to `./feature_store/` as Parquet files.

### 4. Build Features to Online Store

```bash
mlforge build --profile online --online
```

This uses the `online` profile (which includes RedisStore) and pushes latest values to Redis.

Expected output:
```
Wrote X records to online store (1 features)
```

### 5. Check Current Profile

```bash
mlforge profile
```

Or check a specific profile:

```bash
mlforge profile --profile online
```

### 6. Verify Features in Redis

Check keys exist:

```bash
docker exec mlforge-redis redis-cli KEYS "mlforge:*" | head -5
```

Read a sample value:

```bash
docker exec mlforge-redis redis-cli GET "mlforge:user_spend:<hash>"
```

### 7. Read Features via Python

```bash
uv run python src/transactions_online/read_features.py
```

This script demonstrates:
- Connecting to Redis
- Reading features using `get_online_features()`
- Entity key generation via the `user` Entity

## Features Demonstrated

This example showcases several mlforge features:

### Source

```python
source = mlf.Source("data/transactions.parquet")
```

### Entity (Surrogate Key Generation)

```python
user = mlf.Entity(
    name="user",
    join_key="user_id",
    from_columns=["first", "last", "dob"],
)
```

### Timestamp (Explicit Format)

```python
timestamp = mlf.Timestamp(
    column="trans_date_trans_time",
    format="%Y-%m-%d %H:%M:%S",
    alias="transaction_date",
)
```

### Rolling Metrics

```python
spend_metrics = mlf.Rolling(
    windows=[timedelta(days=7), "30d"],
    aggregations={"amt": ["count", "sum"]},
)
```

### Validators

```python
validators={"amt": [mlf.greater_than_or_equal(value=0)]}
```

## Project Structure

```
transactions-online/
├── src/transactions_online/
│   ├── __init__.py
│   ├── definitions.py      # Definitions (loads from mlforge.yaml)
│   ├── features.py         # Feature definitions
│   └── read_features.py    # Script to read from Redis
├── data/                   # Symlink to transaction data
├── mlforge.yaml            # Profile configuration
├── docker-compose.yml      # Redis container
├── pyproject.toml
└── README.md
```

## RedisStore Options

```python
from mlforge.online import RedisStore

online_store = RedisStore(
    host="localhost",      # Redis host
    port=6379,             # Redis port
    db=0,                  # Redis database number
    password=None,         # Redis password (optional)
    ttl=None,              # Time-to-live in seconds (optional)
    prefix="mlforge",      # Key prefix
)
```

### Key Format

Redis keys follow the pattern:
```
{prefix}:{feature_name}:{entity_hash}
```

Example:
```
mlforge:user_spend:a1b2c3d4e5f6g7h8
```

### Value Format

Values are JSON-encoded feature dictionaries:
```json
{
  "users__amt__count__1d__7d": 15,
  "users__amt__sum__1d__7d": 1250.50,
  "users__amt__count__1d__30d": 45,
  "users__amt__sum__1d__30d": 3500.75
}
```

## Cleanup

Stop Redis:

```bash
docker-compose down
```

Remove feature store:

```bash
rm -rf feature_store/
```

## Using in Production

For production deployments:

1. **Use environment variables** for sensitive config:
   ```yaml
   online_store:
     KIND: redis
     host: ${oc.env:REDIS_HOST}
     password: ${oc.env:REDIS_PASSWORD}
   ```

2. **Use Redis Cluster** for high availability

3. **Set TTL** to auto-expire stale features:
   ```yaml
   online_store:
     KIND: redis
     ttl: 86400  # 24 hours
   ```

4. **Monitor Redis memory** usage

5. **Use connection pooling** for high-throughput applications
