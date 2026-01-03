# Feature: Redis Online Store

**Version:** v0.5.0
**Status:** Planned
**Effort:** Medium
**Breaking Changes:** No

## Summary

Real-time feature serving via Redis for low-latency ML inference. Completes the offline -> online feature store loop and provides the foundation for future online stores (DynamoDB, etc.).

## Motivation

- Enable real-time ML inference with feature retrieval
- Complete the offline -> online feature store loop
- Provide foundation for future online stores (DynamoDB, etc.)
- Low-latency feature serving (sub-millisecond reads)

## Design Principles

- **Simple key-value model** - Entity keys map to feature values
- **JSON serialization** - Human-readable, debuggable
- **Optional TTL** - Configurable expiry per store
- **Batch operations** - Efficient bulk reads/writes

## API Design

### Python API

```python
from mlforge import Definitions
from mlforge.store import LocalStore
from mlforge.online import RedisStore

offline_store = LocalStore(path="./feature_store")
online_store = RedisStore(host="localhost", port=6379, db=0)

defs = Definitions(
    store=offline_store,
    online_store=online_store,
)

# Build to offline store (default)
defs.build(features=["user_spend"])

# Build to online store
defs.build(features=["user_spend"], online=True)
```

### Reading from Online Store

```python
# Single entity
features = online_store.read(
    feature_name="user_spend",
    entity_keys={"user_id": "user_123"},
)
# Returns: {"amount__sum__7d": 1500.0, "amount__mean__7d": 214.28, ...}

# Batch read
features_batch = online_store.read_batch(
    feature_name="user_spend",
    entity_keys=[
        {"user_id": "user_123"},
        {"user_id": "user_456"},
    ],
)
```

### CLI

```bash
mlforge build --features user_spend --online
```

### RedisStore Configuration

```python
RedisStore(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0,
    password: str | None = None,
    ttl: int | None = None,  # seconds, None = no expiry
)
```

## Implementation Details

### Redis Data Model

```
Key: mlforge:{feature_name}:{entity_key_hash}
Value: JSON serialized feature values
TTL: Optional, configurable per RedisStore instance
```

Example:
```
Key: mlforge:user_spend:abc123def456
Value: {"amount__sum__7d": 1500.0, "amount__mean__7d": 214.28}
TTL: 3600 (1 hour)
```

### OnlineStore ABC

```python
from abc import ABC, abstractmethod
from typing import Any

class OnlineStore(ABC):
    @abstractmethod
    def write(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
        values: dict[str, Any]
    ) -> None:
        """Write feature values for a single entity."""
        ...

    @abstractmethod
    def write_batch(
        self,
        feature_name: str,
        records: list[dict[str, Any]],
        entity_key_columns: list[str]
    ) -> None:
        """Write feature values for multiple entities."""
        ...

    @abstractmethod
    def read(
        self,
        feature_name: str,
        entity_keys: dict[str, str]
    ) -> dict[str, Any] | None:
        """Read feature values for a single entity."""
        ...

    @abstractmethod
    def read_batch(
        self,
        feature_name: str,
        entity_keys: list[dict[str, str]]
    ) -> list[dict[str, Any] | None]:
        """Read feature values for multiple entities."""
        ...
```

### Key Files

| File | Changes |
|------|---------|
| `src/mlforge/online.py` | New file - OnlineStore ABC, RedisStore |
| `src/mlforge/core.py` | online_store parameter, build(online=True) |
| `src/mlforge/cli.py` | --online flag |

### Implementation Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 10 | Online Store ABC | Planned |
| 11 | Redis Store implementation | Planned |
| 12 | Online Store integration | Planned |

## Definition of Done

### Code
- [ ] Implementation complete
- [ ] Type hints on all public functions
- [ ] Docstrings following Google style
- [ ] No ruff/ty errors

### Tests
- [ ] Unit tests written (`tests/test_online.py`)
- [ ] Integration tests with Redis
- [ ] All tests passing
- [ ] Coverage >= 80%

### Documentation
- [ ] API docs updated
- [ ] User guide updated
- [ ] CLI docs updated
- [ ] CHANGELOG entry added

### Verification
- [ ] Works in `examples/transactions`
- [ ] Code review completed
- [ ] No regressions in existing functionality

## Dependencies

- **Depends on:** Versioning (for metadata), DuckDB Engine (optional)
- **Blocked by:** None
- **Optional dependency:** `redis>=5.0.0`

## Testing Strategy

### Unit Tests

- `test_redis_store_write_read` - Basic write/read
- `test_redis_store_batch_operations` - Batch read/write
- `test_redis_store_ttl` - TTL expiry works
- `test_redis_store_missing_key` - Returns None for missing

### Integration Tests

- `test_build_to_online_store` - Full build pipeline
- `test_online_offline_sync` - Data consistency

### Example Verification

```bash
# Start Redis
docker run -d -p 6379:6379 redis:latest

cd examples/transactions
# Configure online store in definitions.py
uv run mlforge build --features user_spend_30d_interval --online

# Verify in Redis
redis-cli KEYS "mlforge:*"
```

## Installation

```bash
pip install mlforge[redis]

# Or everything
pip install mlforge[all]
```

## Future Considerations

- DynamoDB online store - v0.8.0
- Feature freshness tracking
- Online/offline consistency checks
- `mlforge serve` REST API - v0.6.0+
