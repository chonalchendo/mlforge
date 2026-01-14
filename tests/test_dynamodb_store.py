"""Tests for DynamoDB online store implementation."""

import json
import sys
from unittest.mock import MagicMock

import pytest

from mlforge.online import DynamoDBStore

# =============================================================================
# DynamoDBStore Initialization Tests
# =============================================================================


def test_dynamodb_store_import_error_message_is_helpful(mocker):
    # Given boto3 import fails
    def raise_import_error(*args, **kwargs):
        raise ImportError("No module named 'boto3'")

    mocker.patch.dict(sys.modules, {"boto3": None})
    mocker.patch("builtins.__import__", side_effect=raise_import_error)

    # When creating DynamoDBStore
    # Then ImportError should have helpful message
    with pytest.raises(ImportError) as exc_info:
        DynamoDBStore(table_name="test")

    assert "mlforge[dynamodb]" in str(exc_info.value)


def test_dynamodb_store_initialization_with_required_params(mocker):
    # Given a mock boto3 module
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")

    # When creating DynamoDBStore with required params
    store = DynamoDBStore(table_name="test-features")

    # Then defaults should be set correctly
    assert store.table_name == "test-features"
    assert store.region is None
    assert store.endpoint_url is None
    assert store.ttl_seconds is None


def test_dynamodb_store_initialization_with_custom_values(mocker):
    # Given a mock boto3 module
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")

    # When creating DynamoDBStore with custom values
    store = DynamoDBStore(
        table_name="my-features",
        region="us-west-2",
        endpoint_url="http://localhost:8000",
        ttl_seconds=86400,
    )

    # Then custom values should be set
    assert store.table_name == "my-features"
    assert store.region == "us-west-2"
    assert store.endpoint_url == "http://localhost:8000"
    assert store.ttl_seconds == 86400


def test_dynamodb_store_creates_client_with_correct_params(mocker):
    # Given a mock boto3 module
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")

    # When creating DynamoDBStore
    DynamoDBStore(
        table_name="test-features",
        region="eu-west-1",
        endpoint_url="http://localhost:8000",
    )

    # Then boto3 client should be created with correct params
    mock_boto3.client.assert_called_once_with(
        "dynamodb",
        region_name="eu-west-1",
        endpoint_url="http://localhost:8000",
    )


# =============================================================================
# DynamoDBStore Key Building Tests
# =============================================================================


def test_dynamodb_store_build_entity_hash_returns_hash(mocker):
    # Given a DynamoDBStore
    mock_boto3 = MagicMock()
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When building a hash
    entity_hash = store._build_entity_hash({"user_id": "123"})

    # Then hash should be 16-char hex string
    assert len(entity_hash) == 16
    assert entity_hash.isalnum()


def test_dynamodb_store_build_entity_hash_is_order_independent(mocker):
    # Given a DynamoDBStore
    mock_boto3 = MagicMock()
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When building hashes with different key orders
    hash1 = store._build_entity_hash({"user_id": "123", "account_id": "456"})
    hash2 = store._build_entity_hash({"account_id": "456", "user_id": "123"})

    # Then hashes should be identical
    assert hash1 == hash2


# =============================================================================
# DynamoDBStore Write Tests
# =============================================================================


def test_dynamodb_store_write_without_ttl(mocker):
    # Given a DynamoDBStore without TTL
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When writing a value
    store.write(
        feature_name="user_spend",
        entity_keys={"user_id": "123"},
        values={"amount": 100.0},
    )

    # Then put_item should be called
    mock_client.put_item.assert_called_once()

    # And item should have correct structure
    call_args = mock_client.put_item.call_args
    item = call_args[1]["Item"]
    assert "entity_key" in item
    assert item["feature_name"]["S"] == "user_spend"
    assert json.loads(item["feature_values"]["S"]) == {"amount": 100.0}
    assert "ttl" not in item


def test_dynamodb_store_write_with_ttl(mocker):
    # Given a DynamoDBStore with TTL
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features", ttl_seconds=3600)

    # When writing a value
    store.write(
        feature_name="user_spend",
        entity_keys={"user_id": "123"},
        values={"amount": 100.0},
    )

    # Then put_item should be called with TTL
    call_args = mock_client.put_item.call_args
    item = call_args[1]["Item"]
    assert "ttl" in item
    assert "N" in item["ttl"]


# =============================================================================
# DynamoDBStore Write Batch Tests
# =============================================================================


def test_dynamodb_store_write_batch_empty_records(mocker):
    # Given a DynamoDBStore
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When writing empty batch
    count = store.write_batch(
        feature_name="user_spend",
        records=[],
        entity_key_columns=["user_id"],
    )

    # Then count should be 0 and batch_write_item not called
    assert count == 0
    mock_client.batch_write_item.assert_not_called()


def test_dynamodb_store_write_batch_multiple_records(mocker):
    # Given a DynamoDBStore
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_client.batch_write_item.return_value = {"UnprocessedItems": {}}
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When writing multiple records
    records = [
        {"user_id": "123", "amount": 100.0},
        {"user_id": "456", "amount": 200.0},
    ]
    count = store.write_batch(
        feature_name="user_spend",
        records=records,
        entity_key_columns=["user_id"],
    )

    # Then count should be correct
    assert count == 2

    # And batch_write_item should be called
    mock_client.batch_write_item.assert_called_once()

    # Verify request structure
    call_args = mock_client.batch_write_item.call_args
    request_items = call_args[1]["RequestItems"]
    assert "test-features" in request_items
    assert len(request_items["test-features"]) == 2


def test_dynamodb_store_write_batch_with_ttl(mocker):
    # Given a DynamoDBStore with TTL
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_client.batch_write_item.return_value = {"UnprocessedItems": {}}
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features", ttl_seconds=3600)

    # When writing batch
    records = [{"user_id": "123", "amount": 100.0}]
    store.write_batch(
        feature_name="user_spend",
        records=records,
        entity_key_columns=["user_id"],
    )

    # Then items should have TTL
    call_args = mock_client.batch_write_item.call_args
    request_items = call_args[1]["RequestItems"]["test-features"]
    item = request_items[0]["PutRequest"]["Item"]
    assert "ttl" in item


def test_dynamodb_store_write_batch_chunks_large_batches(mocker):
    # Given a DynamoDBStore
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_client.batch_write_item.return_value = {"UnprocessedItems": {}}
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When writing more than 25 records (DynamoDB batch limit)
    records = [{"user_id": str(i), "amount": float(i)} for i in range(30)]
    count = store.write_batch(
        feature_name="user_spend",
        records=records,
        entity_key_columns=["user_id"],
    )

    # Then batch_write_item should be called twice (25 + 5)
    assert count == 30
    assert mock_client.batch_write_item.call_count == 2


# =============================================================================
# DynamoDBStore Read Tests
# =============================================================================


def test_dynamodb_store_read_existing_key(mocker):
    # Given a DynamoDBStore with existing data
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_client.get_item.return_value = {
        "Item": {
            "entity_key": {"S": "abc123"},
            "feature_name": {"S": "user_spend"},
            "feature_values": {"S": '{"amount": 100.0, "count": 5}'},
        }
    }
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When reading
    result = store.read(
        feature_name="user_spend",
        entity_keys={"user_id": "123"},
    )

    # Then result should be parsed JSON
    assert result == {"amount": 100.0, "count": 5}


def test_dynamodb_store_read_missing_key(mocker):
    # Given a DynamoDBStore with no data
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_client.get_item.return_value = {}
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When reading non-existent key
    result = store.read(
        feature_name="user_spend",
        entity_keys={"user_id": "999"},
    )

    # Then result should be None
    assert result is None


# =============================================================================
# DynamoDBStore Read Batch Tests
# =============================================================================


def test_dynamodb_store_read_batch_empty_keys(mocker):
    # Given a DynamoDBStore
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When reading empty batch
    results = store.read_batch(
        feature_name="user_spend",
        entity_keys=[],
    )

    # Then result should be empty list
    assert results == []
    mock_client.batch_get_item.assert_not_called()


def test_dynamodb_store_read_batch_mixed_results(mocker):
    # Given a DynamoDBStore with some existing data
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # Build expected keys for the mock response
    key1 = store._build_entity_hash({"user_id": "123"})
    key3 = store._build_entity_hash({"user_id": "789"})

    mock_client.batch_get_item.return_value = {
        "Responses": {
            "test-features": [
                {
                    "entity_key": {"S": key1},
                    "feature_name": {"S": "user_spend"},
                    "feature_values": {"S": '{"amount": 100.0}'},
                },
                {
                    "entity_key": {"S": key3},
                    "feature_name": {"S": "user_spend"},
                    "feature_values": {"S": '{"amount": 300.0}'},
                },
            ]
        },
        "UnprocessedKeys": {},
    }

    # When reading batch
    entity_keys = [
        {"user_id": "123"},
        {"user_id": "456"},
        {"user_id": "789"},
    ]
    results = store.read_batch(
        feature_name="user_spend",
        entity_keys=entity_keys,
    )

    # Then results should include None for missing
    assert results[0] == {"amount": 100.0}
    assert results[1] is None
    assert results[2] == {"amount": 300.0}


# =============================================================================
# DynamoDBStore Delete Tests
# =============================================================================


def test_dynamodb_store_delete_existing_key(mocker):
    # Given a DynamoDBStore with existing data
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_client.delete_item.return_value = {
        "Attributes": {"entity_key": {"S": "abc123"}}
    }
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When deleting
    result = store.delete(
        feature_name="user_spend",
        entity_keys={"user_id": "123"},
    )

    # Then result should be True
    assert result is True


def test_dynamodb_store_delete_missing_key(mocker):
    # Given a DynamoDBStore with no data
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_client.delete_item.return_value = {}
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When deleting non-existent key
    result = store.delete(
        feature_name="user_spend",
        entity_keys={"user_id": "999"},
    )

    # Then result should be False
    assert result is False


# =============================================================================
# DynamoDBStore Exists Tests
# =============================================================================


def test_dynamodb_store_exists_returns_true(mocker):
    # Given a DynamoDBStore with existing data
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_client.get_item.return_value = {
        "Item": {"entity_key": {"S": "abc123"}}
    }
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When checking existence
    result = store.exists(
        feature_name="user_spend",
        entity_keys={"user_id": "123"},
    )

    # Then result should be True
    assert result is True


def test_dynamodb_store_exists_returns_false(mocker):
    # Given a DynamoDBStore with no data
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_client.get_item.return_value = {}
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When checking existence
    result = store.exists(
        feature_name="user_spend",
        entity_keys={"user_id": "999"},
    )

    # Then result should be False
    assert result is False


# =============================================================================
# DynamoDBStore Ping Tests
# =============================================================================


def test_dynamodb_store_ping_success(mocker):
    # Given a connected DynamoDBStore
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_client.describe_table.return_value = {
        "Table": {"TableName": "test-features"}
    }
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When pinging
    result = store.ping()

    # Then result should be True
    assert result is True


def test_dynamodb_store_ping_failure(mocker):
    # Given a disconnected DynamoDBStore
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_client.describe_table.side_effect = Exception("Table not found")
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When pinging
    result = store.ping()

    # Then result should be False
    assert result is False


# =============================================================================
# DynamoDBStore Table Creation Tests
# =============================================================================


def test_dynamodb_store_ensure_table_exists_when_table_exists(mocker):
    # Given a mock boto3 module with existing table
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_client.describe_table.return_value = {
        "Table": {"TableName": "test-features"}
    }
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )

    # When creating DynamoDBStore
    DynamoDBStore(table_name="test-features")

    # Then create_table should not be called
    mock_client.create_table.assert_not_called()


def test_dynamodb_store_create_table_called_with_correct_schema(mocker):
    # Given a DynamoDBStore
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_waiter = MagicMock()
    mock_client.get_waiter.return_value = mock_waiter
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When calling _create_table directly
    store._create_table()

    # Then create_table should be called with correct schema
    mock_client.create_table.assert_called_once()
    call_args = mock_client.create_table.call_args[1]
    assert call_args["TableName"] == "test-features"
    assert call_args["BillingMode"] == "PAY_PER_REQUEST"

    # Verify key schema
    key_schema = call_args["KeySchema"]
    assert {"AttributeName": "entity_key", "KeyType": "HASH"} in key_schema
    assert {"AttributeName": "feature_name", "KeyType": "RANGE"} in key_schema

    # Verify TTL was enabled
    mock_client.update_time_to_live.assert_called_once()


def test_dynamodb_store_auto_create_false_skips_table_check(mocker):
    # Given a mock boto3 module
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )

    # When creating DynamoDBStore with auto_create=False
    DynamoDBStore(table_name="test-features", auto_create=False)

    # Then describe_table should not be called
    mock_client.describe_table.assert_not_called()


# =============================================================================
# DynamoDBStore Retry Logic Tests
# =============================================================================


def test_dynamodb_store_write_batch_retries_unprocessed_items(mocker):
    # Given a DynamoDBStore where first batch_write returns unprocessed items
    mock_boto3 = MagicMock()
    mock_client = MagicMock()

    # First call returns unprocessed, second call succeeds
    mock_client.batch_write_item.side_effect = [
        {"UnprocessedItems": {"test-features": [{"PutRequest": {"Item": {}}}]}},
        {"UnprocessedItems": {}},
    ]
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    mocker.patch("time.sleep")  # Skip actual sleep
    store = DynamoDBStore(table_name="test-features")

    # When writing batch
    records = [{"user_id": "123", "amount": 100.0}]
    count = store.write_batch(
        feature_name="user_spend",
        records=records,
        entity_key_columns=["user_id"],
    )

    # Then batch_write_item should be called twice (initial + retry)
    assert mock_client.batch_write_item.call_count == 2
    # Count should reflect successful write after retry
    assert count == 1


def test_dynamodb_store_read_batch_retries_unprocessed_keys(mocker):
    # Given a DynamoDBStore where first batch_get returns unprocessed keys
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    mocker.patch("time.sleep")  # Skip actual sleep
    store = DynamoDBStore(table_name="test-features")

    key1 = store._build_entity_hash({"user_id": "123"})

    # First call returns unprocessed, second call returns the item
    mock_client.batch_get_item.side_effect = [
        {
            "Responses": {"test-features": []},
            "UnprocessedKeys": {
                "test-features": {
                    "Keys": [
                        {
                            "entity_key": {"S": key1},
                            "feature_name": {"S": "user_spend"},
                        }
                    ]
                }
            },
        },
        {
            "Responses": {
                "test-features": [
                    {
                        "entity_key": {"S": key1},
                        "feature_name": {"S": "user_spend"},
                        "feature_values": {"S": '{"amount": 100.0}'},
                    }
                ]
            },
            "UnprocessedKeys": {},
        },
    ]

    # When reading batch
    results = store.read_batch(
        feature_name="user_spend",
        entity_keys=[{"user_id": "123"}],
    )

    # Then batch_get_item should be called twice (initial + retry)
    assert mock_client.batch_get_item.call_count == 2
    assert results[0] == {"amount": 100.0}


def test_dynamodb_store_read_batch_chunks_large_requests(mocker):
    # Given a DynamoDBStore
    mock_boto3 = MagicMock()
    mock_client = MagicMock()
    mock_client.batch_get_item.return_value = {
        "Responses": {"test-features": []},
        "UnprocessedKeys": {},
    }
    mock_boto3.client.return_value = mock_client
    mocker.patch.dict(
        "sys.modules", {"boto3": mock_boto3, "botocore": MagicMock()}
    )
    mocker.patch.object(DynamoDBStore, "_ensure_table_exists")
    store = DynamoDBStore(table_name="test-features")

    # When reading more than 100 keys (DynamoDB batch limit)
    entity_keys = [{"user_id": str(i)} for i in range(105)]
    store.read_batch(feature_name="user_spend", entity_keys=entity_keys)

    # Then batch_get_item should be called twice (100 + 5)
    assert mock_client.batch_get_item.call_count == 2
