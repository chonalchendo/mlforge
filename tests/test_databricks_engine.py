"""
Tests for Databricks SQL Connector engine.

These tests use mocks since databricks-sql-connector is an optional dependency.
"""

from unittest.mock import MagicMock, patch

import pytest

import mlforge.errors as errors
from mlforge import Source, feature
from mlforge.engines import DatabricksSQLEngine
from mlforge.results import DatabricksSQLResult


class TestDatabricksSQLResult:
    """Tests for DatabricksSQLResult class."""

    def test_result_row_count(self):
        """Result should return correct row count."""
        result = DatabricksSQLResult(
            columns=["id", "value"],
            rows=[(1, "a"), (2, "b"), (3, "c")],
            sql="SELECT * FROM test",
        )

        assert result.row_count() == 3

    def test_result_to_polars(self):
        """Result should convert to Polars DataFrame."""
        result = DatabricksSQLResult(
            columns=["id", "name"],
            rows=[(1, "alice"), (2, "bob")],
            sql="SELECT * FROM users",
        )

        df = result.to_polars()

        assert df.shape == (2, 2)
        assert df.columns == ["id", "name"]
        assert df["id"].to_list() == [1, 2]
        assert df["name"].to_list() == ["alice", "bob"]

    def test_result_schema(self):
        """Result should return schema from Polars conversion."""
        result = DatabricksSQLResult(
            columns=["id", "amount"],
            rows=[(1, 100.5), (2, 200.0)],
            sql="SELECT * FROM orders",
        )

        schema = result.schema()

        assert "id" in schema
        assert "amount" in schema

    def test_result_write_parquet(self, tmp_path):
        """Result should write to parquet file."""
        result = DatabricksSQLResult(
            columns=["id", "value"],
            rows=[(1, 10), (2, 20)],
            sql="SELECT * FROM test",
        )

        path = tmp_path / "test.parquet"
        result.write_parquet(path)

        assert path.exists()

    def test_result_caches_polars_conversion(self):
        """Result should cache Polars conversion."""
        result = DatabricksSQLResult(
            columns=["id"],
            rows=[(1,), (2,)],
            sql="SELECT id FROM test",
        )

        df1 = result.to_polars()
        df2 = result.to_polars()

        # Should be the same cached object
        assert df1 is df2


class TestSourceWithTable:
    """Tests for Source class with table parameter."""

    def test_source_with_table_only(self):
        """Source with table should be Unity Catalog source."""
        source = Source(table="main.analytics.fct_orders")

        assert source.table == "main.analytics.fct_orders"
        assert source.path is None
        assert source.is_unity_catalog is True
        assert source.location == "unity-catalog"

    def test_source_table_name_extraction(self):
        """Source name should be extracted from table."""
        source = Source(table="catalog.schema.my_table")

        assert source.name == "my_table"

    def test_source_requires_path_or_table(self):
        """Source should require either path or table."""
        with pytest.raises(ValueError, match="requires either"):
            Source()

    def test_source_rejects_both_path_and_table(self):
        """Source should reject both path and table."""
        with pytest.raises(ValueError, match="cannot have both"):
            Source(path="data.parquet", table="catalog.schema.table")

    def test_source_with_path_still_works(self):
        """Source with path should still work as before."""
        source = Source(path="data/transactions.parquet")

        assert source.path == "data/transactions.parquet"
        assert source.table is None
        assert source.is_unity_catalog is False
        assert source.location == "local"


class TestDatabricksSQLEngine:
    """Tests for DatabricksSQLEngine class."""

    def test_engine_requires_connection_params(self):
        """Engine should raise if connection params missing."""
        with patch.object(DatabricksSQLEngine, "_verify_connector_installed"):
            with pytest.raises(ValueError, match="host, http_path, and token"):
                DatabricksSQLEngine()

    def test_engine_with_explicit_params(self):
        """Engine should accept explicit connection params."""
        with patch.object(DatabricksSQLEngine, "_verify_connector_installed"):
            engine = DatabricksSQLEngine(
                host="test.databricks.com",
                http_path="/sql/warehouses/abc",
                token="test_token",
            )

            assert engine._host == "test.databricks.com"
            assert engine._http_path == "/sql/warehouses/abc"
            assert engine._token == "test_token"

    def test_execute_requires_unity_catalog_source(self):
        """Engine should reject non-UC sources."""
        with patch.object(DatabricksSQLEngine, "_verify_connector_installed"):
            engine = DatabricksSQLEngine(
                host="test.databricks.com",
                http_path="/sql/warehouses/abc",
                token="test_token",
            )

            @feature(source=Source(path="data.parquet"), keys=["id"])
            def file_based_feature(df):
                return df

            with pytest.raises(
                errors.FeatureMaterializationError,
                match="requires Unity Catalog source",
            ):
                engine.execute(file_based_feature)

    def test_execute_requires_sql_string_return(self):
        """Engine should require SQL string return from feature function."""
        with patch.object(DatabricksSQLEngine, "_verify_connector_installed"):
            engine = DatabricksSQLEngine(
                host="test.databricks.com",
                http_path="/sql/warehouses/abc",
                token="test_token",
            )

            @feature(source=Source(table="main.schema.table"), keys=["id"])
            def feature_with_arg(df):
                return df  # Returns DataFrame, not SQL

            with pytest.raises(
                errors.FeatureMaterializationError,
                match="must take no arguments",
            ):
                engine.execute(feature_with_arg)

    def test_execute_with_sql_feature(self):
        """Engine should execute SQL-returning feature."""
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("total",)]
        mock_cursor.fetchall.return_value = [(1, 100), (2, 200)]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        with patch.object(DatabricksSQLEngine, "_verify_connector_installed"):
            engine = DatabricksSQLEngine(
                host="test.databricks.com",
                http_path="/sql/warehouses/abc",
                token="test_token",
            )
            engine._connection = mock_connection

            @feature(source=Source(table="main.analytics.orders"), keys=["id"])
            def customer_totals():
                return (
                    "SELECT id, SUM(amount) as total FROM {source} GROUP BY id"
                )

            result = engine.execute(customer_totals)

            # Verify SQL was executed with substituted table name
            mock_cursor.execute.assert_called_once()
            executed_sql = mock_cursor.execute.call_args[0][0]
            assert "main.analytics.orders" in executed_sql
            assert "{source}" not in executed_sql

            # Verify result
            assert result.row_count() == 2
            df = result.to_polars()
            assert df.columns == ["id", "total"]

    def test_query_method(self):
        """Engine should support ad-hoc SQL queries via query() method."""
        mock_cursor = MagicMock()
        mock_cursor.description = [("col1",), ("col2",)]
        mock_cursor.fetchall.return_value = [("a", 1), ("b", 2)]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        with patch.object(DatabricksSQLEngine, "_verify_connector_installed"):
            engine = DatabricksSQLEngine(
                host="test.databricks.com",
                http_path="/sql/warehouses/abc",
                token="test_token",
            )
            engine._connection = mock_connection

            result = engine.query("SELECT col1, col2 FROM test_table")

            mock_cursor.execute.assert_called_once_with(
                "SELECT col1, col2 FROM test_table"
            )
            assert result.row_count() == 2

    def test_connection_lazy_creation(self):
        """Connection should be created lazily."""
        with patch.object(DatabricksSQLEngine, "_verify_connector_installed"):
            engine = DatabricksSQLEngine(
                host="test.databricks.com",
                http_path="/sql/warehouses/abc",
                token="test_token",
            )

            # Connection should not exist yet
            assert engine._connection is None

    def test_close_connection(self):
        """Engine should close connection when requested."""
        mock_connection = MagicMock()

        with patch.object(DatabricksSQLEngine, "_verify_connector_installed"):
            engine = DatabricksSQLEngine(
                host="test.databricks.com",
                http_path="/sql/warehouses/abc",
                token="test_token",
            )
            engine._connection = mock_connection

            engine.close()

            mock_connection.close.assert_called_once()
            assert engine._connection is None


class TestBackwardCompatibility:
    """Test backward compatibility of DatabricksEngine alias."""

    def test_databricks_engine_alias_exists(self):
        """DatabricksEngine should be an alias for DatabricksSQLEngine."""
        from mlforge.engines import DatabricksEngine

        assert DatabricksEngine is DatabricksSQLEngine
