"""
Tests for UnityCatalogStore.

These tests use mocked SparkSession since PySpark/Databricks
isn't available in the test environment.
"""

from unittest.mock import MagicMock, patch

import pytest

from mlforge.stores.unity_catalog import (
    UnityCatalogStore,
    _escape_string,
    _validate_identifier,
)


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestValidateIdentifier:
    """Tests for _validate_identifier function."""

    def test_valid_simple_name(self):
        """Should accept simple alphanumeric names."""
        assert _validate_identifier("my_feature", "test") == "my_feature"
        assert _validate_identifier("Feature1", "test") == "Feature1"
        assert _validate_identifier("_private", "test") == "_private"

    def test_valid_with_underscores(self):
        """Should accept names with underscores."""
        assert _validate_identifier("user_spend_7d", "test") == "user_spend_7d"

    def test_invalid_starts_with_digit(self):
        """Should reject names starting with digits."""
        with pytest.raises(ValueError, match="Invalid test"):
            _validate_identifier("1feature", "test")

    def test_invalid_special_characters(self):
        """Should reject names with special characters."""
        with pytest.raises(ValueError, match="Invalid test"):
            _validate_identifier("my-feature", "test")
        with pytest.raises(ValueError, match="Invalid test"):
            _validate_identifier("my.feature", "test")
        with pytest.raises(ValueError, match="Invalid test"):
            _validate_identifier("my feature", "test")

    def test_invalid_sql_injection_attempt(self):
        """Should reject SQL injection attempts."""
        with pytest.raises(ValueError, match="Invalid test"):
            _validate_identifier("'; DROP TABLE users; --", "test")
        with pytest.raises(ValueError, match="Invalid test"):
            _validate_identifier("feature' OR '1'='1", "test")


class TestEscapeString:
    """Tests for _escape_string function."""

    def test_no_quotes(self):
        """Should return string unchanged when no quotes."""
        assert _escape_string("hello world") == "hello world"

    def test_single_quotes(self):
        """Should double single quotes."""
        assert _escape_string("it's") == "it''s"
        assert _escape_string("'quoted'") == "''quoted''"

    def test_multiple_quotes(self):
        """Should handle multiple quotes."""
        assert _escape_string("a'b'c") == "a''b''c"


# =============================================================================
# UnityCatalogStore Initialization Tests
# =============================================================================


class TestUnityCatalogStoreInit:
    """Tests for UnityCatalogStore initialization."""

    def test_raises_without_pyspark(self):
        """Should raise ImportError when pyspark not installed."""
        with patch.dict("sys.modules", {"pyspark": None, "pyspark.sql": None}):
            with patch(
                "mlforge.stores.unity_catalog.UnityCatalogStore._get_spark_session"
            ) as mock_get:
                mock_get.side_effect = ImportError(
                    "pyspark is required for UnityCatalogStore"
                )
                with pytest.raises(ImportError, match="pyspark"):
                    UnityCatalogStore(catalog="main")

    def test_raises_without_active_session(self):
        """Should raise RuntimeError when no SparkSession."""
        with patch(
            "mlforge.stores.unity_catalog.UnityCatalogStore._get_spark_session"
        ) as mock_get:
            mock_get.side_effect = RuntimeError("No active SparkSession")
            with pytest.raises(RuntimeError, match="SparkSession"):
                UnityCatalogStore(catalog="main")

    def test_validates_catalog_name(self):
        """Should reject invalid catalog names."""
        with pytest.raises(ValueError, match="Invalid catalog"):
            # Need to bypass the spark session check
            with patch(
                "mlforge.stores.unity_catalog.UnityCatalogStore._get_spark_session"
            ):
                UnityCatalogStore(catalog="invalid-name")

    def test_validates_schema_name(self):
        """Should reject invalid schema names."""
        with pytest.raises(ValueError, match="Invalid schema"):
            with patch(
                "mlforge.stores.unity_catalog.UnityCatalogStore._get_spark_session"
            ):
                UnityCatalogStore(catalog="main", schema="invalid.schema")


# =============================================================================
# UnityCatalogStore Method Tests (with mocked Spark)
# =============================================================================


@pytest.fixture
def mock_spark():
    """Create a mock SparkSession."""
    mock = MagicMock()
    mock.sql.return_value.first.return_value = None
    mock.sql.return_value.collect.return_value = []
    return mock


@pytest.fixture
def unity_store(mock_spark):
    """Create a UnityCatalogStore with mocked SparkSession."""
    with patch(
        "mlforge.stores.unity_catalog.UnityCatalogStore._get_spark_session",
        return_value=mock_spark,
    ):
        store = UnityCatalogStore(catalog="main", schema="features")
        return store


class TestUnityCatalogStoreProperties:
    """Tests for UnityCatalogStore property methods."""

    def test_full_schema_name(self, unity_store):
        """Should return catalog.schema format."""
        assert unity_store._full_schema_name == "main.features"

    def test_full_metadata_table_name(self, unity_store):
        """Should return full path to metadata table."""
        assert (
            unity_store._full_metadata_table_name
            == "main.features._mlforge_metadata"
        )

    def test_table_name_for(self, unity_store):
        """Should return full table path."""
        assert (
            unity_store._table_name_for("user_spend")
            == "main.features.user_spend"
        )

    def test_table_name_for_validates_feature_name(self, unity_store):
        """Should reject invalid feature names."""
        with pytest.raises(ValueError, match="Invalid feature_name"):
            unity_store._table_name_for("invalid-feature")


class TestUnityCatalogStoreVersioning:
    """Tests for version-related methods."""

    def test_list_versions_empty(self, unity_store, mock_spark):
        """Should return empty list when no versions exist."""
        mock_spark.sql.return_value.collect.return_value = []
        versions = unity_store.list_versions("user_spend")
        assert versions == []

    def test_list_versions_returns_sorted(self, unity_store, mock_spark):
        """Should return versions in sorted order."""
        # Mock rows returned from SQL
        mock_rows = [
            MagicMock(version="1.0.0"),
            MagicMock(version="2.0.0"),
            MagicMock(version="1.1.0"),
        ]
        mock_spark.sql.return_value.collect.return_value = mock_rows

        versions = unity_store.list_versions("user_spend")
        # version_utils.sort_versions sorts oldest to newest
        assert versions == ["1.0.0", "1.1.0", "2.0.0"]

    def test_get_latest_version_none_when_empty(self, unity_store, mock_spark):
        """Should return None when no versions exist."""
        mock_spark.sql.return_value.first.return_value = None
        latest = unity_store.get_latest_version("user_spend")
        assert latest is None

    def test_get_latest_version_returns_version(self, unity_store, mock_spark):
        """Should return latest version string."""
        mock_spark.sql.return_value.first.return_value = MagicMock(
            version="2.0.0"
        )
        latest = unity_store.get_latest_version("user_spend")
        assert latest == "2.0.0"

    def test_exists_false_when_no_versions(self, unity_store, mock_spark):
        """Should return False when no versions exist."""
        mock_spark.sql.return_value.collect.return_value = []
        assert unity_store.exists("user_spend") is False

    def test_exists_true_when_versions_exist(self, unity_store, mock_spark):
        """Should return True when versions exist."""
        mock_spark.sql.return_value.collect.return_value = [
            MagicMock(version="1.0.0")
        ]
        assert unity_store.exists("user_spend") is True

    def test_exists_specific_version(self, unity_store, mock_spark):
        """Should check specific version existence."""
        mock_spark.sql.return_value.first.return_value = MagicMock(
            delta_version=5
        )
        assert unity_store.exists("user_spend", "1.0.0") is True

        mock_spark.sql.return_value.first.return_value = None
        assert unity_store.exists("user_spend", "2.0.0") is False


class TestUnityCatalogStorePaths:
    """Tests for path-related methods."""

    def test_path_for_returns_table_name(self, unity_store):
        """Should return full table name."""
        path = unity_store.path_for("user_spend")
        assert path == "main.features.user_spend"

    def test_metadata_path_for_returns_metadata_table(self, unity_store):
        """Should return metadata table path."""
        path = unity_store.metadata_path_for("user_spend")
        assert path == "main.features._mlforge_metadata"


class TestUnityCatalogStoreRead:
    """Tests for read method."""

    def test_read_raises_when_feature_not_found(self, unity_store, mock_spark):
        """Should raise FileNotFoundError when feature doesn't exist."""
        mock_spark.sql.return_value.first.return_value = None

        with pytest.raises(FileNotFoundError, match="not found"):
            unity_store.read("nonexistent_feature")

    def test_read_raises_when_version_not_found(self, unity_store, mock_spark):
        """Should raise FileNotFoundError when version doesn't exist."""
        # First call returns latest version, second call returns no delta version
        mock_spark.sql.return_value.first.side_effect = [
            MagicMock(version="1.0.0"),  # get_latest_version
            None,  # _get_delta_version
        ]

        with pytest.raises(FileNotFoundError, match="not found"):
            unity_store.read("user_spend")


class TestUnityCatalogStoreSQLSafety:
    """Tests to verify SQL injection protection."""

    def test_list_versions_escapes_feature_name(self, unity_store, mock_spark):
        """Should escape feature names in SQL queries."""
        mock_spark.sql.return_value.collect.return_value = []

        # This should not cause SQL issues
        unity_store.list_versions("feature'with'quotes")

        # Verify the SQL was called with escaped value
        call_args = mock_spark.sql.call_args[0][0]
        assert "feature''with''quotes" in call_args

    def test_get_delta_version_escapes_inputs(self, unity_store, mock_spark):
        """Should escape both feature name and version."""
        mock_spark.sql.return_value.first.return_value = None

        unity_store._get_delta_version("feature'name", "1.0.0'bad")

        call_args = mock_spark.sql.call_args[0][0]
        assert "feature''name" in call_args
        assert "1.0.0''bad" in call_args


# =============================================================================
# Profile Configuration Tests
# =============================================================================


class TestUnityCatalogStoreConfig:
    """Tests for profile configuration."""

    def test_config_creates_store(self):
        """Should create store from config."""
        from mlforge.profiles import UnityCatalogStoreConfig

        config = UnityCatalogStoreConfig(
            catalog="main",
            schema_="features",
            volume="artifacts",
        )

        assert config.KIND == "unity-catalog"
        assert config.catalog == "main"
        assert config.schema_ == "features"
        assert config.volume == "artifacts"

    def test_config_with_alias(self):
        """Should accept 'schema' as alias for 'schema_'."""
        from mlforge.profiles import UnityCatalogStoreConfig

        # Using the alias
        config = UnityCatalogStoreConfig.model_validate(
            {"catalog": "main", "schema": "my_schema"}
        )
        assert config.schema_ == "my_schema"

    def test_config_default_schema(self):
        """Should default schema to 'features'."""
        from mlforge.profiles import UnityCatalogStoreConfig

        config = UnityCatalogStoreConfig(catalog="main")
        assert config.schema_ == "features"
