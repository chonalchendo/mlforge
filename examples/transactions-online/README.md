# Transactions Online Example

This example demonstrates using mlforge's online store feature with Redis for real-time feature serving.

## Overview

The online store pattern is used when you need low-latency feature retrieval for ML inference:

1. **Offline Store** (default): Features stored as Parquet files for training and batch processing
2. **Online Store**: Latest feature values stored in Redis for real-time serving

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
uv run mlforge build
```

This builds features to `./feature_store/` as Parquet files.

### 4. Build Features to Online Store

```bash
uv run mlforge build --online
```

This extracts the latest value per entity and writes to Redis.

Expected output:
```
Wrote X records to online store (1 features)
```

### 5. Verify Features in Redis

Check keys exist:

```bash
docker exec mlforge-redis redis-cli KEYS "mlforge:*" | head -5
```

Read a sample value:

```bash
docker exec mlforge-redis redis-cli GET "mlforge:user_spend:<hash>"
```

### 6. Read Features via Python

```bash
uv run python src/transactions_online/read_features.py
```

This script demonstrates:
- Connecting to Redis
- Reading single entity features
- Batch reading multiple entities

## Project Structure

```
transactions-online/
├── src/transactions_online/
│   ├── __init__.py
│   ├── definitions.py      # Definitions with RedisStore
│   ├── features.py         # Feature definitions
│   └── read_features.py    # Script to read from Redis
├── data/                   # Symlink to transaction data
├── docker-compose.yml      # Redis container
├── pyproject.toml
└── README.md
```

## Configuration

### RedisStore Options

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

1. **Use Redis Cluster** for high availability
2. **Set TTL** to auto-expire stale features
3. **Monitor Redis memory** usage
4. **Use connection pooling** for high-throughput applications

Example with TTL:

```python
online_store = RedisStore(
    host="redis.prod.example.com",
    port=6379,
    password="<secret>",
    ttl=86400,  # 24 hours
)
```
