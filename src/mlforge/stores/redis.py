"""
Redis online store backend.

Provides low-latency feature serving for real-time ML inference.
"""

import hashlib
import json
from decimal import Decimal
from typing import Any, cast, override

from mlforge.stores.base import OnlineStore


class _FeatureEncoder(json.JSONEncoder):
    """JSON encoder for feature values with non-standard types.

    Handles types that json.dumps() doesn't support natively:
    - Decimal: Converted to float (common in financial/aggregation features)

    Used internally by RedisStore.write() and write_batch() for serialization.
    """

    def default(self, o: Any) -> Any:
        """Convert non-JSON-serializable types to JSON-compatible values."""
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def _compute_entity_hash(entity_keys: dict[str, str]) -> str:
    """
    Compute a stable hash for entity keys.

    Sorts keys for deterministic ordering, then hashes the JSON representation.

    Args:
        entity_keys: Entity key columns and values

    Returns:
        Hex digest of the hash (first 16 chars for brevity)
    """
    sorted_keys = sorted(entity_keys.items())
    key_str = json.dumps(sorted_keys, sort_keys=True)
    return hashlib.sha256(key_str.encode()).hexdigest()[:16]


class RedisStore(OnlineStore):
    """
    Redis-backed online feature store.

    Stores feature values as JSON in Redis with optional TTL.
    Uses Redis pipelines for efficient batch operations.

    Key format: mlforge:{feature_name}:{entity_key_hash}
    Value format: JSON serialized feature values

    Attributes:
        host: Redis server hostname
        port: Redis server port
        db: Redis database number
        password: Redis password (optional)
        ttl: Time-to-live in seconds (optional, None = no expiry)
        prefix: Key prefix (default: "mlforge")

    Example:
        store = RedisStore(host="localhost", port=6379, ttl=3600)

        # Write single entity
        store.write(
            feature_name="user_spend",
            entity_keys={"user_id": "user_123"},
            values={"amount__sum__7d": 1500.0},
        )

        # Read single entity
        features = store.read(
            feature_name="user_spend",
            entity_keys={"user_id": "user_123"},
        )
        # Returns: {"amount__sum__7d": 1500.0}
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        ttl: int | None = None,
        prefix: str = "mlforge",
    ) -> None:
        """
        Initialize Redis online store.

        Args:
            host: Redis server hostname. Defaults to "localhost".
            port: Redis server port. Defaults to 6379.
            db: Redis database number. Defaults to 0.
            password: Redis password. Defaults to None.
            ttl: Time-to-live in seconds. Defaults to None (no expiry).
            prefix: Key prefix for all keys. Defaults to "mlforge".

        Raises:
            ImportError: If redis package is not installed
        """
        try:
            import redis
        except ImportError as e:
            raise ImportError(
                "Redis package not installed. "
                "Install with: pip install mlforge[redis]"
            ) from e

        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.ttl = ttl
        self.prefix = prefix

        self._client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True,
        )

    def _build_key(self, feature_name: str, entity_keys: dict[str, str]) -> str:
        """Build Redis key with configured prefix."""
        entity_hash = _compute_entity_hash(entity_keys)
        return f"{self.prefix}:{feature_name}:{entity_hash}"

    @override
    def write(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
        values: dict[str, Any],
    ) -> None:
        """
        Write feature values for a single entity.

        Args:
            feature_name: Name of the feature
            entity_keys: Entity key columns and values
            values: Feature column values to store
        """
        key = self._build_key(feature_name, entity_keys)
        value_json = json.dumps(values, cls=_FeatureEncoder)

        if self.ttl:
            self._client.setex(key, self.ttl, value_json)
        else:
            self._client.set(key, value_json)

    @override
    def write_batch(
        self,
        feature_name: str,
        records: list[dict[str, Any]],
        entity_key_columns: list[str],
    ) -> int:
        """
        Write feature values for multiple entities using Redis pipeline.

        Args:
            feature_name: Name of the feature
            records: List of records with entity keys and feature values
            entity_key_columns: Column names that form the entity key

        Returns:
            Number of records written
        """
        if not records:
            return 0

        pipe = self._client.pipeline()

        for record in records:
            # Extract entity keys
            entity_keys = {col: str(record[col]) for col in entity_key_columns}

            # Extract feature values (all columns except entity keys)
            values = {
                k: v for k, v in record.items() if k not in entity_key_columns
            }

            key = self._build_key(feature_name, entity_keys)
            value_json = json.dumps(values, cls=_FeatureEncoder)

            if self.ttl:
                pipe.setex(key, self.ttl, value_json)
            else:
                pipe.set(key, value_json)

        pipe.execute()
        return len(records)

    @override
    def read(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> dict[str, Any] | None:
        """
        Read feature values for a single entity.

        Args:
            feature_name: Name of the feature
            entity_keys: Entity key columns and values

        Returns:
            Feature values dict, or None if not found
        """
        key = self._build_key(feature_name, entity_keys)
        value = cast(str | None, self._client.get(key))

        if value is None:
            return None

        return json.loads(value)

    @override
    def read_batch(
        self,
        feature_name: str,
        entity_keys: list[dict[str, str]],
    ) -> list[dict[str, Any] | None]:
        """
        Read feature values for multiple entities using Redis pipeline.

        Args:
            feature_name: Name of the feature
            entity_keys: List of entity key dicts

        Returns:
            List of feature value dicts (None for missing entities)
        """
        if not entity_keys:
            return []

        pipe = self._client.pipeline()

        for keys in entity_keys:
            key = self._build_key(feature_name, keys)
            pipe.get(key)

        results = pipe.execute()

        return [
            json.loads(value) if value is not None else None
            for value in results
        ]

    @override
    def delete(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> bool:
        """
        Delete feature values for a single entity.

        Args:
            feature_name: Name of the feature
            entity_keys: Entity key columns and values

        Returns:
            True if deleted, False if not found
        """
        key = self._build_key(feature_name, entity_keys)
        deleted = cast(int, self._client.delete(key))
        return deleted > 0

    @override
    def exists(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> bool:
        """
        Check if feature values exist for an entity.

        Args:
            feature_name: Name of the feature
            entity_keys: Entity key columns and values

        Returns:
            True if exists, False otherwise
        """
        key = self._build_key(feature_name, entity_keys)
        count = cast(int, self._client.exists(key))
        return count > 0

    def ping(self) -> bool:
        """
        Check Redis connection.

        Returns:
            True if connected, False otherwise
        """
        try:
            return bool(self._client.ping())
        except Exception:
            return False
