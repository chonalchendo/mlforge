"""
DynamoDB online store backend.

Provides serverless, fully managed feature storage with single-digit
millisecond latency for real-time ML inference.
"""

import hashlib
import json
from decimal import Decimal
from typing import Any, override

from mlforge.stores.base import OnlineStore


class _FeatureEncoder(json.JSONEncoder):
    """JSON encoder for feature values with non-standard types."""

    def default(self, o: Any) -> Any:
        """Convert non-JSON-serializable types to JSON-compatible values."""
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def _compute_entity_hash(entity_keys: dict[str, str]) -> str:
    """Compute a stable hash for entity keys."""
    sorted_keys = sorted(entity_keys.items())
    key_str = json.dumps(sorted_keys, sort_keys=True)
    return hashlib.sha256(key_str.encode()).hexdigest()[:16]


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
            PermissionError: If table creation fails due to IAM permissions.
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
