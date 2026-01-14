"""
Online feature store implementations for real-time serving.

This module provides the OnlineStore abstract base class and concrete
implementations for low-latency feature retrieval during ML inference.

Example:
    from mlforge.online import RedisStore

    online_store = RedisStore(host="localhost", port=6379)

    # Write features
    online_store.write(
        feature_name="user_spend",
        entity_keys={"user_id": "user_123"},
        values={"amount__sum__7d": 1500.0},
    )

    # Read features
    features = online_store.read(
        feature_name="user_spend",
        entity_keys={"user_id": "user_123"},
    )
"""

import hashlib
import json
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, cast, override


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


class OnlineStore(ABC):
    """
    Abstract base class for online feature storage backends.

    Online stores provide low-latency read/write access to feature values
    for real-time ML inference. Unlike offline stores (which store full
    feature history), online stores typically only hold the latest values.

    Key design:
        - Simple key-value model: entity keys -> feature values
        - JSON serialization for human-readable debugging
        - Batch operations for efficient bulk access
    """

    @abstractmethod
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
            entity_keys: Entity key columns and values (e.g., {"user_id": "123"})
            values: Feature column values (e.g., {"amount__sum__7d": 1500.0})
        """
        ...

    @abstractmethod
    def write_batch(
        self,
        feature_name: str,
        records: list[dict[str, Any]],
        entity_key_columns: list[str],
    ) -> int:
        """
        Write feature values for multiple entities.

        Args:
            feature_name: Name of the feature
            records: List of records, each containing entity keys and feature values
            entity_key_columns: Column names that form the entity key

        Returns:
            Number of records written
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    def read_batch(
        self,
        feature_name: str,
        entity_keys: list[dict[str, str]],
    ) -> list[dict[str, Any] | None]:
        """
        Read feature values for multiple entities.

        Args:
            feature_name: Name of the feature
            entity_keys: List of entity key dicts

        Returns:
            List of feature value dicts (None for missing entities)
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...


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


class DynamoDBStore(OnlineStore):
    """
    DynamoDB-backed online feature store.

    Stores feature values in AWS DynamoDB with optional TTL for automatic
    expiration. Provides serverless, fully managed storage with single-digit
    millisecond latency.

    Table schema:
        - Partition key: entity_key (String) - hash of entity keys
        - Sort key: feature_name (String)
        - Attributes: feature_values (JSON string), updated_at, ttl

    Attributes:
        table_name: DynamoDB table name
        region: AWS region (optional, uses default from AWS config)
        endpoint_url: Custom endpoint URL (for local testing with DynamoDB Local)
        ttl_seconds: Time-to-live in seconds (optional, None = no expiry)
        auto_create: Create table if it doesn't exist (default: True)

    Example:
        store = DynamoDBStore(
            table_name="my-features",
            region="us-west-2",
            ttl_seconds=86400 * 7,  # 7 days
        )

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

        # Local testing with DynamoDB Local
        store = DynamoDBStore(
            table_name="test-features",
            endpoint_url="http://localhost:8000",
        )
    """

    # DynamoDB batch operation limits
    _BATCH_WRITE_LIMIT = 25
    _BATCH_READ_LIMIT = 100

    def __init__(
        self,
        table_name: str,
        region: str | None = None,
        endpoint_url: str | None = None,
        ttl_seconds: int | None = None,
        auto_create: bool = True,
    ) -> None:
        """
        Initialize DynamoDB online store.

        Args:
            table_name: DynamoDB table name.
            region: AWS region. Defaults to None (uses AWS config default).
            endpoint_url: Custom endpoint URL for local testing. Defaults to None.
            ttl_seconds: Time-to-live in seconds. Defaults to None (no expiry).
            auto_create: Create table if it doesn't exist. Defaults to True.

        Raises:
            ImportError: If boto3 package is not installed.
            DynamoDBStoreError: If table creation fails due to IAM permissions.
        """
        try:
            import boto3
            from botocore.exceptions import ClientError

            self._ClientError = ClientError
        except ImportError as e:
            raise ImportError(
                "boto3 package not installed. "
                "Install with: pip install mlforge[dynamodb]"
            ) from e

        self.table_name = table_name
        self.region = region
        self.endpoint_url = endpoint_url
        self.ttl_seconds = ttl_seconds

        self._client = boto3.client(
            "dynamodb",
            region_name=region,
            endpoint_url=endpoint_url,
        )

        if auto_create:
            self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """Create table if it doesn't exist."""
        try:
            self._client.describe_table(TableName=self.table_name)
        except self._ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                self._create_table()
            else:
                raise

    def _create_table(self) -> None:
        """Create the DynamoDB table with required schema."""
        try:
            self._client.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {"AttributeName": "entity_key", "KeyType": "HASH"},
                    {"AttributeName": "feature_name", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "entity_key", "AttributeType": "S"},
                    {"AttributeName": "feature_name", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )

            # Wait for table to be active
            waiter = self._client.get_waiter("table_exists")
            waiter.wait(TableName=self.table_name)

            # Enable TTL
            self._client.update_time_to_live(
                TableName=self.table_name,
                TimeToLiveSpecification={
                    "Enabled": True,
                    "AttributeName": "ttl",
                },
            )
        except self._ClientError as e:
            if e.response["Error"]["Code"] == "AccessDeniedException":
                raise PermissionError(
                    f"Cannot create table '{self.table_name}'.\n\n"
                    "IAM permission 'dynamodb:CreateTable' is required for "
                    "auto-creation.\n\n"
                    "Options:\n"
                    "  1. Grant dynamodb:CreateTable permission to your IAM role\n"
                    "  2. Create the table manually (see docs for schema)\n"
                    "  3. Use auto_create=False and ensure table exists\n\n"
                    "Table schema required:\n"
                    "  - Partition key: entity_key (String)\n"
                    "  - Sort key: feature_name (String)\n"
                    "  - TTL attribute: ttl (enabled)"
                ) from e
            raise

    def _build_entity_hash(self, entity_keys: dict[str, str]) -> str:
        """Build entity key hash for DynamoDB partition key."""
        return _compute_entity_hash(entity_keys)

    def _dynamo_key(
        self, entity_hash: str, feature_name: str
    ) -> dict[str, dict[str, str]]:
        """Build DynamoDB key dict for get/delete operations."""
        return {
            "entity_key": {"S": entity_hash},
            "feature_name": {"S": feature_name},
        }

    def _build_item(
        self,
        entity_hash: str,
        feature_name: str,
        values: dict[str, Any],
        timestamp: str,
        ttl_value: str | None = None,
    ) -> dict[str, Any]:
        """Build DynamoDB item dict for put operations."""
        item: dict[str, Any] = {
            "entity_key": {"S": entity_hash},
            "feature_name": {"S": feature_name},
            "feature_values": {"S": json.dumps(values, cls=_FeatureEncoder)},
            "updated_at": {"S": timestamp},
        }
        if ttl_value:
            item["ttl"] = {"N": ttl_value}
        return item

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
            feature_name: Name of the feature.
            entity_keys: Entity key columns and values.
            values: Feature column values to store.
        """
        import time
        from datetime import datetime, timezone

        entity_hash = self._build_entity_hash(entity_keys)
        now = datetime.now(timezone.utc).isoformat()
        ttl_value = (
            str(int(time.time()) + self.ttl_seconds)
            if self.ttl_seconds
            else None
        )

        item = self._build_item(
            entity_hash, feature_name, values, now, ttl_value
        )
        self._client.put_item(TableName=self.table_name, Item=item)

    @override
    def write_batch(
        self,
        feature_name: str,
        records: list[dict[str, Any]],
        entity_key_columns: list[str],
    ) -> int:
        """
        Write feature values for multiple entities using BatchWriteItem.

        Args:
            feature_name: Name of the feature.
            records: List of records with entity keys and feature values.
            entity_key_columns: Column names that form the entity key.

        Returns:
            Number of records written.
        """
        import time
        from datetime import datetime, timezone

        if not records:
            return 0

        written = 0
        now = datetime.now(timezone.utc).isoformat()
        ttl_value = (
            str(int(time.time()) + self.ttl_seconds)
            if self.ttl_seconds
            else None
        )

        # Process in chunks due to DynamoDB batch limit
        for i in range(0, len(records), self._BATCH_WRITE_LIMIT):
            chunk = records[i : i + self._BATCH_WRITE_LIMIT]
            request_items: list[dict[str, Any]] = []

            for record in chunk:
                entity_keys = {
                    col: str(record[col]) for col in entity_key_columns
                }
                values = {
                    k: v
                    for k, v in record.items()
                    if k not in entity_key_columns
                }

                entity_hash = self._build_entity_hash(entity_keys)
                item = self._build_item(
                    entity_hash, feature_name, values, now, ttl_value
                )
                request_items.append({"PutRequest": {"Item": item}})

            # Execute batch write with retry for unprocessed items
            response = self._client.batch_write_item(
                RequestItems={self.table_name: request_items}
            )
            unprocessed = response.get("UnprocessedItems", {})

            for retry in range(3):
                if not unprocessed:
                    break
                time.sleep(0.1 * (2**retry))
                response = self._client.batch_write_item(
                    RequestItems=unprocessed
                )
                unprocessed = response.get("UnprocessedItems", {})

            written += len(chunk) - len(unprocessed.get(self.table_name, []))

        return written

    @override
    def read(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> dict[str, Any] | None:
        """
        Read feature values for a single entity.

        Args:
            feature_name: Name of the feature.
            entity_keys: Entity key columns and values.

        Returns:
            Feature values dict, or None if not found.
        """
        entity_hash = self._build_entity_hash(entity_keys)
        response = self._client.get_item(
            TableName=self.table_name,
            Key=self._dynamo_key(entity_hash, feature_name),
        )

        item = response.get("Item")
        if item is None:
            return None

        return json.loads(item["feature_values"]["S"])

    def _process_batch_response(
        self,
        response: dict[str, Any],
        key_to_index: dict[str, int],
        results: list[dict[str, Any] | None],
    ) -> None:
        """Process batch_get_item response and populate results."""
        for item in response.get("Responses", {}).get(self.table_name, []):
            entity_hash = item["entity_key"]["S"]
            idx = key_to_index[entity_hash]
            results[idx] = json.loads(item["feature_values"]["S"])

    @override
    def read_batch(
        self,
        feature_name: str,
        entity_keys: list[dict[str, str]],
    ) -> list[dict[str, Any] | None]:
        """
        Read feature values for multiple entities using BatchGetItem.

        Args:
            feature_name: Name of the feature.
            entity_keys: List of entity key dicts.

        Returns:
            List of feature value dicts (None for missing entities).
        """
        import time

        if not entity_keys:
            return []

        # Build key mapping to preserve order
        key_to_index: dict[str, int] = {}
        results: list[dict[str, Any] | None] = [None] * len(entity_keys)

        for idx, keys in enumerate(entity_keys):
            entity_hash = self._build_entity_hash(keys)
            key_to_index[entity_hash] = idx

        # Process in chunks due to DynamoDB batch limit
        all_keys = list(key_to_index.keys())
        for i in range(0, len(all_keys), self._BATCH_READ_LIMIT):
            chunk_keys = all_keys[i : i + self._BATCH_READ_LIMIT]
            request_keys = [
                self._dynamo_key(ek, feature_name) for ek in chunk_keys
            ]

            response = self._client.batch_get_item(
                RequestItems={self.table_name: {"Keys": request_keys}}
            )
            self._process_batch_response(response, key_to_index, results)

            # Retry unprocessed keys
            unprocessed = response.get("UnprocessedKeys", {})
            for retry in range(3):
                if not unprocessed:
                    break
                time.sleep(0.1 * (2**retry))
                response = self._client.batch_get_item(RequestItems=unprocessed)
                self._process_batch_response(response, key_to_index, results)
                unprocessed = response.get("UnprocessedKeys", {})

        return results

    @override
    def delete(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> bool:
        """
        Delete feature values for a single entity.

        Args:
            feature_name: Name of the feature.
            entity_keys: Entity key columns and values.

        Returns:
            True if deleted, False if not found.
        """
        entity_hash = self._build_entity_hash(entity_keys)
        response = self._client.delete_item(
            TableName=self.table_name,
            Key=self._dynamo_key(entity_hash, feature_name),
            ReturnValues="ALL_OLD",
        )
        return "Attributes" in response

    @override
    def exists(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> bool:
        """
        Check if feature values exist for an entity.

        Args:
            feature_name: Name of the feature.
            entity_keys: Entity key columns and values.

        Returns:
            True if exists, False otherwise.
        """
        entity_hash = self._build_entity_hash(entity_keys)
        response = self._client.get_item(
            TableName=self.table_name,
            Key=self._dynamo_key(entity_hash, feature_name),
            ProjectionExpression="entity_key",
        )
        return "Item" in response

    def ping(self) -> bool:
        """
        Check DynamoDB connection and table access.

        Returns:
            True if table exists and is accessible, False otherwise.
        """
        try:
            self._client.describe_table(TableName=self.table_name)
            return True
        except Exception:
            return False


# Type alias for online store implementations
type OnlineStoreKind = OnlineStore
