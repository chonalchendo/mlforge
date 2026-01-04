# Online Stores

Online stores provide low-latency feature serving for real-time inference. mlforge supports Redis as an online store backend.

## Overview

| Store | Use Case | Latency | Setup |
|-------|----------|---------|-------|
| LocalStore | Development, batch | ~10ms | None |
| S3Store | Production batch | ~100ms | AWS credentials |
| **RedisStore** | Real-time inference | ~1ms | Redis server |

## Redis Store

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

Configure Redis in your definitions file:

```python
import mlforge as mlf
from mlforge.online import RedisStore

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

### Building to Online Store

Build features to Redis using the `--online` flag:

```bash
mlforge build --online
```

This extracts the latest value per entity and writes to Redis.

### Key Format

Features are stored with keys in the format:

```
{prefix}:{feature_name}:{entity_hash}
```

Example:
```
mlforge:user_spend:a1b2c3d4e5f6g7h8
```

### Reading Features

#### Low-level API

```python
from mlforge.online import RedisStore

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

#### High-level API (Recommended)

```python
import mlforge as mlf
from mlforge.online import RedisStore
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

## Connection Options

### Authentication

```python
store = RedisStore(
    host="redis.example.com",
    port=6379,
    password="your-redis-password",
)
```

### Database Selection

Redis supports multiple databases (0-15 by default):

```python
store = RedisStore(
    host="localhost",
    db=1,  # Use database 1 instead of 0
)
```

### TTL (Time-to-Live)

Set automatic expiration for features:

```python
store = RedisStore(
    host="localhost",
    ttl=86400,  # Expire after 24 hours
)
```

## Best Practices

### 1. Use Separate Databases for Environments

```python
# Development
dev_store = RedisStore(host="localhost", db=0)

# Staging
staging_store = RedisStore(host="localhost", db=1)

# Production
prod_store = RedisStore(host="redis.prod.internal", db=0)
```

### 2. Set TTL for Stale Data Prevention

```python
store = RedisStore(
    host="localhost",
    ttl=7 * 24 * 3600,  # 7 days
)
```

### 3. Use Connection Pooling in Production

RedisStore uses connection pooling by default. For high-throughput scenarios, tune your Redis server's `maxclients` setting.

### 4. Monitor Redis Memory

```bash
redis-cli info memory
```

### 5. Verify Connection Before Use

```python
store = RedisStore(host="localhost")

if not store.ping():
    raise RuntimeError("Cannot connect to Redis")
```

## Troubleshooting

### Connection Refused

```
redis.exceptions.ConnectionError: Error connecting to localhost:6379
```

**Solution**: Ensure Redis is running:
```bash
docker ps | grep redis
# or
redis-cli ping
```

### Authentication Error

```
redis.exceptions.AuthenticationError: Authentication required
```

**Solution**: Provide password:
```python
store = RedisStore(host="localhost", password="your-password")
```

### Memory Issues

If Redis runs out of memory:

1. Set TTL to expire old features
2. Use Redis persistence (`RDB` or `AOF`)
3. Scale Redis (Redis Cluster for large deployments)

## Next Steps

- [Retrieving Features](retrieving-features.md) - Use `get_online_features()`
- [Building Features](building-features.md) - Build to online store
- [API Reference](../api/online.md) - RedisStore API documentation
