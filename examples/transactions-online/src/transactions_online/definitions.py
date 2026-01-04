"""
Feature store definitions with online store configuration.

This example demonstrates configuring both offline (LocalStore) and
online (RedisStore) storage backends. Features are built to offline
storage by default, and can be pushed to online storage with --online flag.

Usage:
    # Build to offline store (parquet files)
    mlforge build

    # Build to online store (Redis)
    mlforge build --online
"""

import mlforge as mlf
from mlforge.online import RedisStore

from transactions_online import features

defs = mlf.Definitions(
    name="Transactions Online Example",
    features=[features],
    offline_store=mlf.LocalStore(path="./feature_store"),
    online_store=RedisStore(
        host="localhost",
        port=6379,
        prefix="mlforge",
        ttl=None,  # No expiry - set to seconds for auto-expiry
    ),
)
