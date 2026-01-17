"""
Offline and online feature store implementations.

This module provides storage backends for persisting and retrieving
materialized features. Offline stores handle batch data for training,
while online stores provide low-latency access for inference.

Offline Stores:
    LocalStore: Local filesystem storage
    S3Store: Amazon S3 storage
    GCSStore: Google Cloud Storage
    UnityCatalogStore: Databricks Unity Catalog storage

Online Stores:
    RedisStore: Redis for real-time serving
    DynamoDBStore: AWS DynamoDB for serverless serving
    DatabricksOnlineStore: Databricks Online Tables for managed serving

Example:
    from mlforge.stores import LocalStore, RedisStore

    offline_store = LocalStore("./feature_store")
    online_store = RedisStore(host="localhost", port=6379)
"""

from mlforge.stores.base import OnlineStore, Store
from mlforge.stores.databricks_online_tables import DatabricksOnlineStore
from mlforge.stores.databricks_unity_catalog import UnityCatalogStore
from mlforge.stores.dynamodb import DynamoDBStore
from mlforge.stores.gcs import GCSStore
from mlforge.stores.local import LocalStore
from mlforge.stores.redis import RedisStore
from mlforge.stores.s3 import S3Store

# Type aliases for store implementations
type OfflineStoreKind = LocalStore | S3Store | GCSStore | UnityCatalogStore
type OnlineStoreKind = OnlineStore

__all__ = [
    # Base classes
    "Store",
    "OnlineStore",
    # Offline stores
    "LocalStore",
    "S3Store",
    "GCSStore",
    "UnityCatalogStore",
    # Online stores
    "RedisStore",
    "DynamoDBStore",
    "DatabricksOnlineStore",
    # Type aliases
    "OfflineStoreKind",
    "OnlineStoreKind",
]
