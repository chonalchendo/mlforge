"""
Online feature store implementations for real-time serving.

This module re-exports online store classes from mlforge.stores for backward compatibility.
New code should import directly from mlforge.stores.

Example:
    # Preferred (new code)
    from mlforge.stores import RedisStore, DynamoDBStore

    # Also works (backward compatibility)
    from mlforge.online import RedisStore, DynamoDBStore
"""

from mlforge.stores import (
    DynamoDBStore,
    OnlineStore,
    OnlineStoreKind,
    RedisStore,
)
from mlforge.stores.redis import _compute_entity_hash

__all__ = [
    "OnlineStore",
    "RedisStore",
    "DynamoDBStore",
    "OnlineStoreKind",
    "_compute_entity_hash",
]
