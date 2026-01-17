"""Tests for Databricks Online Tables store implementation."""

import sys
from unittest.mock import MagicMock

import pytest

from mlforge.stores.databricks_online_tables import (
    DatabricksOnlineStore,
    _escape_string,
    _validate_identifier,
)

# =============================================================================
# Identifier Validation Tests
# =============================================================================


def test_validate_identifier_accepts_valid_identifiers():
    # Given valid SQL identifiers
    valid = ["user_id", "UserSpend", "_private", "feature123", "a"]

    # When validating each
    # Then no exceptions should be raised
    for name in valid:
        assert _validate_identifier(name) == name


def test_validate_identifier_rejects_invalid_identifiers():
    # Given invalid SQL identifiers
    invalid = ["123start", "has space", "has-dash", "has.dot", "has;semi", ""]

    # When validating each
    # Then ValueError should be raised
    for name in invalid:
        with pytest.raises(ValueError, match="Invalid"):
            _validate_identifier(name, "test")


def test_escape_string_escapes_single_quotes():
    # Given a string with single quotes
    value = "O'Brien's"

    # When escaping
    result = _escape_string(value)

    # Then quotes should be doubled
    assert result == "O''Brien''s"


def test_escape_string_leaves_safe_strings_unchanged():
    # Given safe strings
    safe = ["hello", "user_123", "feature.name"]

    # When escaping
    for value in safe:
        assert _escape_string(value) == value


# =============================================================================
# DatabricksOnlineStore Initialization Tests
# =============================================================================


def test_databricks_store_import_error_message_is_helpful(mocker):
    # Given databricks-sdk import fails
    def raise_import_error(*args, **kwargs):
        if "databricks" in args[0]:
            raise ImportError("No module named 'databricks'")
        return MagicMock()

    mocker.patch.dict(sys.modules, {"databricks": None, "databricks.sdk": None})
    mocker.patch("builtins.__import__", side_effect=raise_import_error)

    # When creating DatabricksOnlineStore
    # Then ImportError should have helpful message
    with pytest.raises(ImportError) as exc_info:
        DatabricksOnlineStore(catalog="main")

    assert "mlforge[databricks]" in str(exc_info.value)


def test_databricks_store_initialization_with_defaults(mocker):
    # Given a mock databricks-sdk
    mock_sdk = MagicMock()
    mock_client = MagicMock()
    mock_sdk.WorkspaceClient.return_value = mock_client
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})

    # When creating DatabricksOnlineStore with defaults
    store = DatabricksOnlineStore(catalog="main")

    # Then defaults should be set correctly
    assert store._catalog == "main"
    assert store._schema == "features_online"
    assert store._sync_mode == "triggered"
    assert store._auto_create is True


def test_databricks_store_initialization_with_custom_values(mocker):
    # Given a mock databricks-sdk
    mock_sdk = MagicMock()
    mock_client = MagicMock()
    mock_sdk.WorkspaceClient.return_value = mock_client
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})

    # When creating DatabricksOnlineStore with custom values
    store = DatabricksOnlineStore(
        catalog="prod",
        schema="online_features",
        sync_mode="continuous",
        auto_create=False,
    )

    # Then custom values should be set
    assert store._catalog == "prod"
    assert store._schema == "online_features"
    assert store._sync_mode == "continuous"
    assert store._auto_create is False


def test_databricks_store_validates_catalog_name(mocker):
    # Given a mock databricks-sdk
    mock_sdk = MagicMock()
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})

    # When creating DatabricksOnlineStore with invalid catalog
    # Then ValueError should be raised
    with pytest.raises(ValueError, match="Invalid catalog"):
        DatabricksOnlineStore(catalog="invalid-catalog")


def test_databricks_store_validates_schema_name(mocker):
    # Given a mock databricks-sdk
    mock_sdk = MagicMock()
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})

    # When creating DatabricksOnlineStore with invalid schema
    # Then ValueError should be raised
    with pytest.raises(ValueError, match="Invalid schema"):
        DatabricksOnlineStore(catalog="main", schema="invalid.schema")


# =============================================================================
# DatabricksOnlineStore Property Tests
# =============================================================================


def test_databricks_store_full_schema_name(mocker):
    # Given a DatabricksOnlineStore
    mock_sdk = MagicMock()
    mock_sdk.WorkspaceClient.return_value = MagicMock()
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When getting full schema name
    result = store.full_schema_name

    # Then it should be catalog.schema
    assert result == "main.features"


def test_databricks_store_table_name_for(mocker):
    # Given a DatabricksOnlineStore
    mock_sdk = MagicMock()
    mock_sdk.WorkspaceClient.return_value = MagicMock()
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When getting table name for a feature
    result = store._table_name_for("user_spend")

    # Then it should be fully qualified
    assert result == "main.features.user_spend"


def test_databricks_store_table_name_for_validates_feature_name(mocker):
    # Given a DatabricksOnlineStore
    mock_sdk = MagicMock()
    mock_sdk.WorkspaceClient.return_value = MagicMock()
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When getting table name for invalid feature
    # Then ValueError should be raised
    with pytest.raises(ValueError, match="Invalid feature_name"):
        store._table_name_for("invalid-feature")


# =============================================================================
# DatabricksOnlineStore Online Table Management Tests
# =============================================================================


def test_databricks_store_online_table_exists_returns_true(mocker):
    # Given a DatabricksOnlineStore with existing table
    mock_sdk = MagicMock()
    mock_errors = MagicMock()
    mock_not_found = type("NotFound", (Exception,), {})
    mock_errors.NotFound = mock_not_found

    mock_client = MagicMock()
    mock_client.online_tables.get.return_value = MagicMock()
    mock_sdk.WorkspaceClient.return_value = mock_client
    mocker.patch.dict(
        "sys.modules",
        {"databricks.sdk": mock_sdk, "databricks.sdk.errors": mock_errors},
    )
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When checking if table exists
    result = store._online_table_exists("user_spend")

    # Then result should be True
    assert result is True
    mock_client.online_tables.get.assert_called_once_with(
        "main.features.user_spend"
    )


def test_databricks_store_online_table_exists_returns_false(mocker):
    # Given a DatabricksOnlineStore with non-existent table
    mock_sdk = MagicMock()
    mock_errors = MagicMock()
    mock_not_found = type("NotFound", (Exception,), {})
    mock_errors.NotFound = mock_not_found

    mock_client = MagicMock()
    mock_client.online_tables.get.side_effect = mock_not_found("Not found")
    mock_sdk.WorkspaceClient.return_value = mock_client
    mocker.patch.dict(
        "sys.modules",
        {"databricks.sdk": mock_sdk, "databricks.sdk.errors": mock_errors},
    )
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When checking if table exists
    result = store._online_table_exists("user_spend")

    # Then result should be False
    assert result is False


def test_databricks_store_sync_feature_creates_table_when_auto_create(mocker):
    # Given a DatabricksOnlineStore with auto_create enabled
    mock_sdk = MagicMock()
    mock_errors = MagicMock()
    mock_not_found = type("NotFound", (Exception,), {})
    mock_errors.NotFound = mock_not_found

    mock_client = MagicMock()
    mock_client.online_tables.get.side_effect = [
        mock_not_found("Not found"),  # First call - table doesn't exist
        MagicMock(),  # Second call - after creation
    ]
    mock_sdk.WorkspaceClient.return_value = mock_client

    # Mock the catalog service imports
    mock_catalog = MagicMock()
    mocker.patch.dict(
        "sys.modules",
        {
            "databricks.sdk": mock_sdk,
            "databricks.sdk.errors": mock_errors,
            "databricks.sdk.service": MagicMock(),
            "databricks.sdk.service.catalog": mock_catalog,
        },
    )
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When syncing feature
    store.sync_feature(
        feature_name="user_spend",
        source_table="main.offline.user_spend",
        primary_keys=["user_id"],
    )

    # Then create should be called
    mock_client.online_tables.create.assert_called_once()


def test_databricks_store_sync_feature_raises_when_auto_create_disabled(mocker):
    # Given a DatabricksOnlineStore with auto_create disabled
    mock_sdk = MagicMock()
    mock_errors = MagicMock()
    mock_not_found = type("NotFound", (Exception,), {})
    mock_errors.NotFound = mock_not_found

    mock_client = MagicMock()
    mock_client.online_tables.get.side_effect = mock_not_found("Not found")
    mock_sdk.WorkspaceClient.return_value = mock_client
    mocker.patch.dict(
        "sys.modules",
        {"databricks.sdk": mock_sdk, "databricks.sdk.errors": mock_errors},
    )
    store = DatabricksOnlineStore(
        catalog="main", schema="features", auto_create=False
    )

    # When syncing feature
    # Then ValueError should be raised
    with pytest.raises(ValueError, match="not found"):
        store.sync_feature(
            feature_name="user_spend",
            source_table="main.offline.user_spend",
            primary_keys=["user_id"],
        )


# =============================================================================
# DatabricksOnlineStore Write Tests (Not Supported)
# =============================================================================


def test_databricks_store_write_raises_not_implemented(mocker):
    # Given a DatabricksOnlineStore
    mock_sdk = MagicMock()
    mock_sdk.WorkspaceClient.return_value = MagicMock()
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When writing
    # Then NotImplementedError should be raised with helpful message
    with pytest.raises(NotImplementedError) as exc_info:
        store.write(
            feature_name="user_spend",
            entity_keys={"user_id": "123"},
            values={"amount": 100.0},
        )

    assert "not supported" in str(exc_info.value).lower()
    assert "Delta" in str(exc_info.value)


def test_databricks_store_write_batch_raises_not_implemented(mocker):
    # Given a DatabricksOnlineStore
    mock_sdk = MagicMock()
    mock_sdk.WorkspaceClient.return_value = MagicMock()
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When writing batch
    # Then NotImplementedError should be raised
    with pytest.raises(NotImplementedError) as exc_info:
        store.write_batch(
            feature_name="user_spend",
            records=[{"user_id": "123", "amount": 100.0}],
            entity_key_columns=["user_id"],
        )

    assert "not supported" in str(exc_info.value).lower()


# =============================================================================
# DatabricksOnlineStore Read Tests
# =============================================================================


def test_databricks_store_read_returns_features(mocker):
    # Given a DatabricksOnlineStore with data
    mock_sdk = MagicMock()
    mock_client = MagicMock()

    # Mock statement execution result
    mock_result = MagicMock()
    mock_result.result.data_array = [["123", 100.0, 5]]

    # Create column mocks with proper .name attribute
    mock_col1 = MagicMock()
    mock_col1.name = "user_id"
    mock_col2 = MagicMock()
    mock_col2.name = "amount"
    mock_col3 = MagicMock()
    mock_col3.name = "count"
    mock_result.manifest.schema.columns = [mock_col1, mock_col2, mock_col3]

    mock_client.statement_execution.execute_statement.return_value = mock_result

    # Mock warehouse list
    mock_warehouse = MagicMock()
    mock_warehouse.id = "warehouse-123"
    mock_client.warehouses.list.return_value = [mock_warehouse]

    mock_sdk.WorkspaceClient.return_value = mock_client
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When reading
    result = store.read(
        feature_name="user_spend",
        entity_keys={"user_id": "123"},
    )

    # Then result should be dict with feature values
    assert result == {"user_id": "123", "amount": 100.0, "count": 5}


def test_databricks_store_read_returns_none_when_not_found(mocker):
    # Given a DatabricksOnlineStore with no data
    mock_sdk = MagicMock()
    mock_client = MagicMock()

    # Mock empty result
    mock_result = MagicMock()
    mock_result.result.data_array = []
    mock_client.statement_execution.execute_statement.return_value = mock_result

    # Mock warehouse list
    mock_warehouse = MagicMock()
    mock_warehouse.id = "warehouse-123"
    mock_client.warehouses.list.return_value = [mock_warehouse]

    mock_sdk.WorkspaceClient.return_value = mock_client
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When reading non-existent entity
    result = store.read(
        feature_name="user_spend",
        entity_keys={"user_id": "999"},
    )

    # Then result should be None
    assert result is None


def test_databricks_store_read_batch_empty_keys(mocker):
    # Given a DatabricksOnlineStore
    mock_sdk = MagicMock()
    mock_sdk.WorkspaceClient.return_value = MagicMock()
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When reading empty batch
    results = store.read_batch(feature_name="user_spend", entity_keys=[])

    # Then result should be empty list
    assert results == []


def test_databricks_store_read_batch_multiple_keys(mocker):
    # Given a DatabricksOnlineStore
    mock_sdk = MagicMock()
    mock_client = MagicMock()

    # Mock warehouse list
    mock_warehouse = MagicMock()
    mock_warehouse.id = "warehouse-123"
    mock_client.warehouses.list.return_value = [mock_warehouse]

    # Mock results - first found, second not found
    mock_result1 = MagicMock()
    mock_result1.result.data_array = [["123", 100.0]]

    # Create column mocks with proper .name attribute
    mock_col1 = MagicMock()
    mock_col1.name = "user_id"
    mock_col2 = MagicMock()
    mock_col2.name = "amount"
    mock_result1.manifest.schema.columns = [mock_col1, mock_col2]

    mock_result2 = MagicMock()
    mock_result2.result.data_array = []

    mock_client.statement_execution.execute_statement.side_effect = [
        mock_result1,
        mock_result2,
    ]

    mock_sdk.WorkspaceClient.return_value = mock_client
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When reading batch
    results = store.read_batch(
        feature_name="user_spend",
        entity_keys=[{"user_id": "123"}, {"user_id": "456"}],
    )

    # Then results should match
    assert len(results) == 2
    assert results[0] == {"user_id": "123", "amount": 100.0}
    assert results[1] is None


# =============================================================================
# DatabricksOnlineStore Delete Tests (Not Supported)
# =============================================================================


def test_databricks_store_delete_raises_not_implemented(mocker):
    # Given a DatabricksOnlineStore
    mock_sdk = MagicMock()
    mock_sdk.WorkspaceClient.return_value = MagicMock()
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When deleting
    # Then NotImplementedError should be raised
    with pytest.raises(NotImplementedError) as exc_info:
        store.delete(
            feature_name="user_spend",
            entity_keys={"user_id": "123"},
        )

    assert "not supported" in str(exc_info.value).lower()


# =============================================================================
# DatabricksOnlineStore Exists Tests
# =============================================================================


def test_databricks_store_exists_returns_true(mocker):
    # Given a DatabricksOnlineStore with data
    mock_sdk = MagicMock()
    mock_client = MagicMock()

    # Mock found result
    mock_result = MagicMock()
    mock_result.result.data_array = [["123", 100.0]]

    # Create column mocks with proper .name attribute
    mock_col1 = MagicMock()
    mock_col1.name = "user_id"
    mock_col2 = MagicMock()
    mock_col2.name = "amount"
    mock_result.manifest.schema.columns = [mock_col1, mock_col2]

    mock_client.statement_execution.execute_statement.return_value = mock_result

    # Mock warehouse list
    mock_warehouse = MagicMock()
    mock_warehouse.id = "warehouse-123"
    mock_client.warehouses.list.return_value = [mock_warehouse]

    mock_sdk.WorkspaceClient.return_value = mock_client
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When checking existence
    result = store.exists(
        feature_name="user_spend",
        entity_keys={"user_id": "123"},
    )

    # Then result should be True
    assert result is True


def test_databricks_store_exists_returns_false(mocker):
    # Given a DatabricksOnlineStore with no data
    mock_sdk = MagicMock()
    mock_client = MagicMock()

    # Mock empty result
    mock_result = MagicMock()
    mock_result.result.data_array = []
    mock_client.statement_execution.execute_statement.return_value = mock_result

    # Mock warehouse list
    mock_warehouse = MagicMock()
    mock_warehouse.id = "warehouse-123"
    mock_client.warehouses.list.return_value = [mock_warehouse]

    mock_sdk.WorkspaceClient.return_value = mock_client
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When checking existence
    result = store.exists(
        feature_name="user_spend",
        entity_keys={"user_id": "999"},
    )

    # Then result should be False
    assert result is False


# =============================================================================
# DatabricksOnlineStore Ping Tests
# =============================================================================


def test_databricks_store_ping_success(mocker):
    # Given a connected DatabricksOnlineStore
    mock_sdk = MagicMock()
    mock_client = MagicMock()
    mock_client.online_tables.list.return_value = []
    mock_sdk.WorkspaceClient.return_value = mock_client
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When pinging
    result = store.ping()

    # Then result should be True
    assert result is True


def test_databricks_store_ping_failure(mocker):
    # Given a disconnected DatabricksOnlineStore
    mock_sdk = MagicMock()
    mock_client = MagicMock()
    mock_client.online_tables.list.side_effect = Exception("Connection failed")
    mock_sdk.WorkspaceClient.return_value = mock_client
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When pinging
    result = store.ping()

    # Then result should be False
    assert result is False


# =============================================================================
# DatabricksOnlineStore SQL Warehouse Tests
# =============================================================================


def test_databricks_store_get_sql_warehouse_raises_when_none_available(mocker):
    # Given a DatabricksOnlineStore with no warehouses
    mock_sdk = MagicMock()
    mock_client = MagicMock()
    mock_client.warehouses.list.return_value = []
    mock_sdk.WorkspaceClient.return_value = mock_client
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(catalog="main", schema="features")

    # When getting warehouse ID
    # Then RuntimeError should be raised
    with pytest.raises(RuntimeError, match="No SQL warehouse"):
        store._get_sql_warehouse_id()


# =============================================================================
# DatabricksOnlineStore Continuous Sync Mode Tests
# =============================================================================


def test_databricks_store_continuous_sync_mode_creates_table(mocker):
    # Given a DatabricksOnlineStore with continuous sync mode
    mock_sdk = MagicMock()
    mock_errors = MagicMock()
    mock_not_found = type("NotFound", (Exception,), {})
    mock_errors.NotFound = mock_not_found

    mock_client = MagicMock()
    mock_client.online_tables.get.side_effect = [
        mock_not_found("Not found"),  # First call - table doesn't exist
        MagicMock(),  # Second call - after creation
    ]
    mock_sdk.WorkspaceClient.return_value = mock_client

    # Mock the catalog service imports
    mock_catalog = MagicMock()
    mocker.patch.dict(
        "sys.modules",
        {
            "databricks.sdk": mock_sdk,
            "databricks.sdk.errors": mock_errors,
            "databricks.sdk.service": MagicMock(),
            "databricks.sdk.service.catalog": mock_catalog,
        },
    )
    store = DatabricksOnlineStore(
        catalog="main", schema="features", sync_mode="continuous"
    )

    # When syncing feature
    store.sync_feature(
        feature_name="user_spend",
        source_table="main.offline.user_spend",
        primary_keys=["user_id"],
    )

    # Then create should be called with continuous scheduling policy
    mock_client.online_tables.create.assert_called_once()
    call_args = mock_client.online_tables.create.call_args
    assert call_args is not None


# =============================================================================
# DatabricksOnlineStore Warehouse ID Tests
# =============================================================================


def test_databricks_store_uses_explicit_warehouse_id(mocker):
    # Given a DatabricksOnlineStore with explicit warehouse_id
    mock_sdk = MagicMock()
    mock_sdk.WorkspaceClient.return_value = MagicMock()
    mocker.patch.dict("sys.modules", {"databricks.sdk": mock_sdk})
    store = DatabricksOnlineStore(
        catalog="main", schema="features", warehouse_id="custom-warehouse-123"
    )

    # When getting warehouse ID
    warehouse_id = store._get_sql_warehouse_id()

    # Then it should return the explicit warehouse ID
    assert warehouse_id == "custom-warehouse-123"
