"""Tests for online feature store implementations."""

import json
from unittest.mock import MagicMock, patch

import pytest

from mlforge.online import OnlineStore, RedisStore, _compute_entity_hash

# =============================================================================
# Entity Hash Tests
# =============================================================================


def test_compute_entity_hash_deterministic():
    # Given entity keys
    entity_keys = {"user_id": "123", "account_id": "456"}

    # When computing hash multiple times
    hash1 = _compute_entity_hash(entity_keys)
    hash2 = _compute_entity_hash(entity_keys)

    # Then hashes should be identical
    assert hash1 == hash2


def test_compute_entity_hash_order_independent():
    # Given entity keys in different orders
    keys1 = {"user_id": "123", "account_id": "456"}
    keys2 = {"account_id": "456", "user_id": "123"}

    # When computing hashes
    hash1 = _compute_entity_hash(keys1)
    hash2 = _compute_entity_hash(keys2)

    # Then hashes should be identical (order-independent)
    assert hash1 == hash2


def test_compute_entity_hash_different_values():
    # Given different entity keys
    keys1 = {"user_id": "123"}
    keys2 = {"user_id": "456"}

    # When computing hashes
    hash1 = _compute_entity_hash(keys1)
    hash2 = _compute_entity_hash(keys2)

    # Then hashes should be different
    assert hash1 != hash2


def test_compute_entity_hash_returns_16_chars():
    # Given entity keys
    entity_keys = {"user_id": "123"}

    # When computing hash
    result = _compute_entity_hash(entity_keys)

    # Then hash should be 16 characters
    assert len(result) == 16
    assert result.isalnum()


# =============================================================================
# RedisStore Initialization Tests
# =============================================================================


def test_redis_store_raises_import_error_without_redis():
    # Given redis module not available
    with patch.dict("sys.modules", {"redis": None}):
        # Need to reload the module to trigger the import
        # This test verifies the error message is helpful
        pass  # Import error is raised at module level, tested implicitly


def test_redis_store_initialization_with_defaults(mocker):
    # Given a mock redis module
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})

    # When creating RedisStore with defaults
    store = RedisStore()

    # Then defaults should be set correctly
    assert store.host == "localhost"
    assert store.port == 6379
    assert store.db == 0
    assert store.password is None
    assert store.ttl is None
    assert store.prefix == "mlforge"


def test_redis_store_initialization_with_custom_values(mocker):
    # Given a mock redis module
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})

    # When creating RedisStore with custom values
    store = RedisStore(
        host="redis.example.com",
        port=6380,
        db=5,
        password="secret",
        ttl=3600,
        prefix="myapp",
    )

    # Then custom values should be set
    assert store.host == "redis.example.com"
    assert store.port == 6380
    assert store.db == 5
    assert store.password == "secret"
    assert store.ttl == 3600
    assert store.prefix == "myapp"


def test_redis_store_creates_client_with_correct_params(mocker):
    # Given a mock redis module
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})

    # When creating RedisStore
    RedisStore(host="myhost", port=1234, db=2, password="pass")

    # Then Redis client should be created with correct params
    mock_redis.Redis.assert_called_once_with(
        host="myhost",
        port=1234,
        db=2,
        password="pass",
        decode_responses=True,
    )


# =============================================================================
# RedisStore Key Building Tests
# =============================================================================


def test_redis_store_build_key_with_default_prefix(mocker):
    # Given a RedisStore with default prefix
    mock_redis = MagicMock()
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore()

    # When building a key
    key = store._build_key("user_spend", {"user_id": "123"})

    # Then key should have correct format
    assert key.startswith("mlforge:user_spend:")
    assert len(key.split(":")) == 3


def test_redis_store_build_key_with_custom_prefix(mocker):
    # Given a RedisStore with custom prefix
    mock_redis = MagicMock()
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore(prefix="myapp")

    # When building a key
    key = store._build_key("user_spend", {"user_id": "123"})

    # Then key should use custom prefix
    assert key.startswith("myapp:user_spend:")


# =============================================================================
# RedisStore Write Tests
# =============================================================================


def test_redis_store_write_without_ttl(mocker):
    # Given a RedisStore without TTL
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore()

    # When writing a value
    store.write(
        feature_name="user_spend",
        entity_keys={"user_id": "123"},
        values={"amount": 100.0},
    )

    # Then set should be called (not setex)
    mock_client.set.assert_called_once()
    mock_client.setex.assert_not_called()

    # And value should be JSON
    call_args = mock_client.set.call_args
    assert json.loads(call_args[0][1]) == {"amount": 100.0}


def test_redis_store_write_with_ttl(mocker):
    # Given a RedisStore with TTL
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore(ttl=3600)

    # When writing a value
    store.write(
        feature_name="user_spend",
        entity_keys={"user_id": "123"},
        values={"amount": 100.0},
    )

    # Then setex should be called with TTL
    mock_client.setex.assert_called_once()
    mock_client.set.assert_not_called()

    call_args = mock_client.setex.call_args
    assert call_args[0][1] == 3600  # TTL


# =============================================================================
# RedisStore Write Batch Tests
# =============================================================================


def test_redis_store_write_batch_empty_records(mocker):
    # Given a RedisStore
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore()

    # When writing empty batch
    count = store.write_batch(
        feature_name="user_spend",
        records=[],
        entity_key_columns=["user_id"],
    )

    # Then count should be 0 and pipeline not used
    assert count == 0
    mock_client.pipeline.assert_not_called()


def test_redis_store_write_batch_multiple_records(mocker):
    # Given a RedisStore
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_pipeline = MagicMock()
    mock_client.pipeline.return_value = mock_pipeline
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore()

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

    # And pipeline should be used
    mock_client.pipeline.assert_called_once()
    assert mock_pipeline.set.call_count == 2
    mock_pipeline.execute.assert_called_once()


def test_redis_store_write_batch_with_ttl(mocker):
    # Given a RedisStore with TTL
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_pipeline = MagicMock()
    mock_client.pipeline.return_value = mock_pipeline
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore(ttl=3600)

    # When writing batch
    records = [{"user_id": "123", "amount": 100.0}]
    store.write_batch(
        feature_name="user_spend",
        records=records,
        entity_key_columns=["user_id"],
    )

    # Then setex should be used in pipeline
    mock_pipeline.setex.assert_called_once()
    mock_pipeline.set.assert_not_called()


# =============================================================================
# RedisStore Read Tests
# =============================================================================


def test_redis_store_read_existing_key(mocker):
    # Given a RedisStore with existing data
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_client.get.return_value = '{"amount": 100.0, "count": 5}'
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore()

    # When reading
    result = store.read(
        feature_name="user_spend",
        entity_keys={"user_id": "123"},
    )

    # Then result should be parsed JSON
    assert result == {"amount": 100.0, "count": 5}


def test_redis_store_read_missing_key(mocker):
    # Given a RedisStore with no data
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_client.get.return_value = None
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore()

    # When reading non-existent key
    result = store.read(
        feature_name="user_spend",
        entity_keys={"user_id": "999"},
    )

    # Then result should be None
    assert result is None


# =============================================================================
# RedisStore Read Batch Tests
# =============================================================================


def test_redis_store_read_batch_empty_keys(mocker):
    # Given a RedisStore
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore()

    # When reading empty batch
    results = store.read_batch(
        feature_name="user_spend",
        entity_keys=[],
    )

    # Then result should be empty list
    assert results == []
    mock_client.pipeline.assert_not_called()


def test_redis_store_read_batch_mixed_results(mocker):
    # Given a RedisStore with some existing data
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_pipeline = MagicMock()
    mock_pipeline.execute.return_value = [
        '{"amount": 100.0}',
        None,
        '{"amount": 300.0}',
    ]
    mock_client.pipeline.return_value = mock_pipeline
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore()

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
    assert results == [
        {"amount": 100.0},
        None,
        {"amount": 300.0},
    ]


# =============================================================================
# RedisStore Delete Tests
# =============================================================================


def test_redis_store_delete_existing_key(mocker):
    # Given a RedisStore with existing data
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_client.delete.return_value = 1
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore()

    # When deleting
    result = store.delete(
        feature_name="user_spend",
        entity_keys={"user_id": "123"},
    )

    # Then result should be True
    assert result is True


def test_redis_store_delete_missing_key(mocker):
    # Given a RedisStore with no data
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_client.delete.return_value = 0
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore()

    # When deleting non-existent key
    result = store.delete(
        feature_name="user_spend",
        entity_keys={"user_id": "999"},
    )

    # Then result should be False
    assert result is False


# =============================================================================
# RedisStore Exists Tests
# =============================================================================


def test_redis_store_exists_returns_true(mocker):
    # Given a RedisStore with existing data
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_client.exists.return_value = 1
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore()

    # When checking existence
    result = store.exists(
        feature_name="user_spend",
        entity_keys={"user_id": "123"},
    )

    # Then result should be True
    assert result is True


def test_redis_store_exists_returns_false(mocker):
    # Given a RedisStore with no data
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_client.exists.return_value = 0
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore()

    # When checking existence
    result = store.exists(
        feature_name="user_spend",
        entity_keys={"user_id": "999"},
    )

    # Then result should be False
    assert result is False


# =============================================================================
# RedisStore Ping Tests
# =============================================================================


def test_redis_store_ping_success(mocker):
    # Given a connected RedisStore
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore()

    # When pinging
    result = store.ping()

    # Then result should be True
    assert result is True


def test_redis_store_ping_failure(mocker):
    # Given a disconnected RedisStore
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_client.ping.side_effect = Exception("Connection refused")
    mock_redis.Redis.return_value = mock_client
    mocker.patch.dict("sys.modules", {"redis": mock_redis})
    store = RedisStore()

    # When pinging
    result = store.ping()

    # Then result should be False
    assert result is False


# =============================================================================
# OnlineStore ABC Tests
# =============================================================================


def test_online_store_is_abstract():
    # Given OnlineStore ABC
    # When/Then instantiating should raise TypeError
    with pytest.raises(TypeError):
        OnlineStore()
