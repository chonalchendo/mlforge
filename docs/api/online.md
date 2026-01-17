# Online Store API

The online stores module provides interfaces and implementations for real-time feature serving.

## Abstract Base Class

::: mlforge.stores.base.OnlineStore

---

## Implementations

### RedisStore

Redis-backed online store for low-latency feature serving.

::: mlforge.stores.redis.RedisStore

### DynamoDBStore

AWS DynamoDB online store for serverless feature serving.

::: mlforge.stores.dynamodb.DynamoDBStore

### DatabricksOnlineStore

Databricks Online Tables for managed feature serving.

::: mlforge.stores.databricks_online_tables.DatabricksOnlineStore

---

## Type Aliases

```python
from mlforge.stores import OnlineStoreKind

# Type alias for all online store implementations
type OnlineStoreKind = RedisStore | DynamoDBStore | DatabricksOnlineStore
```
