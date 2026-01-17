"""
Tests for DuckDB compute backend.

Tests the DuckDBEngine, DuckDBCompiler, and DuckDBResult classes.
"""

from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

import mlforge.errors as errors
from mlforge import Aggregate, Definitions, LocalStore, Source, feature
from mlforge.compilers import DuckDBCompiler, DuckDBComputeContext
from mlforge.engines import DuckDBEngine
from mlforge.results import DuckDBResult

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_transactions_parquet(tmp_path: Path) -> Path:
    """Create a sample transactions parquet file for testing."""
    df = pl.DataFrame(
        {
            "user_id": ["u1", "u1", "u1", "u2", "u2", "u2"],
            "event_time": [
                datetime(2024, 1, 1),
                datetime(2024, 1, 2),
                datetime(2024, 1, 8),
                datetime(2024, 1, 1),
                datetime(2024, 1, 3),
                datetime(2024, 1, 10),
            ],
            "amount": [100.0, 200.0, 150.0, 50.0, 75.0, 125.0],
        }
    )
    path = tmp_path / "transactions.parquet"
    df.write_parquet(path)
    return path


@pytest.fixture
def sample_transactions_csv(tmp_path: Path) -> Path:
    """Create a sample transactions CSV file for testing."""
    df = pl.DataFrame(
        {
            "user_id": ["u1", "u1", "u2"],
            "event_time": [
                datetime(2024, 1, 1),
                datetime(2024, 1, 2),
                datetime(2024, 1, 1),
            ],
            "amount": [100.0, 200.0, 50.0],
        }
    )
    path = tmp_path / "transactions.csv"
    df.write_csv(path)
    return path


@pytest.fixture
def duckdb_engine() -> DuckDBEngine:
    """Create a DuckDB engine instance."""
    return DuckDBEngine()


# =============================================================================
# DuckDBResult Tests
# =============================================================================


class TestDuckDBResult:
    """Tests for DuckDBResult class."""

    def test_result_to_polars(self):
        """DuckDBResult.to_polars() should return a Polars DataFrame."""
        import duckdb

        conn = duckdb.connect()
        relation = conn.sql("SELECT 1 as a, 2 as b")
        result = DuckDBResult(relation)

        df = result.to_polars()

        assert isinstance(df, pl.DataFrame)
        assert df.columns == ["a", "b"]
        assert df.height == 1

    def test_result_row_count(self):
        """DuckDBResult.row_count() should return correct count."""
        import duckdb

        conn = duckdb.connect()
        relation = conn.sql("SELECT * FROM (VALUES (1), (2), (3)) AS t(x)")
        result = DuckDBResult(relation)

        assert result.row_count() == 3

    def test_result_schema(self):
        """DuckDBResult.schema() should return column types."""
        import duckdb

        conn = duckdb.connect()
        relation = conn.sql("SELECT 1 as int_col, 'hello' as str_col")
        result = DuckDBResult(relation)

        schema = result.schema()

        assert "int_col" in schema
        assert "str_col" in schema

    def test_result_base_schema(self):
        """DuckDBResult.base_schema() should return stored base schema."""
        import duckdb

        conn = duckdb.connect()
        relation = conn.sql("SELECT 1 as a")
        base_schema = {"a": "Int64", "b": "String"}
        result = DuckDBResult(relation, base_schema=base_schema)

        assert result.base_schema() == base_schema

    def test_result_write_parquet(self, tmp_path: Path):
        """DuckDBResult.write_parquet() should write to file."""
        import duckdb

        conn = duckdb.connect()
        relation = conn.sql("SELECT 1 as a, 2 as b")
        result = DuckDBResult(relation)

        output_path = tmp_path / "output.parquet"
        result.write_parquet(output_path)

        assert output_path.exists()
        # Verify content
        df = pl.read_parquet(output_path)
        assert df.columns == ["a", "b"]


# =============================================================================
# DuckDBCompiler Tests
# =============================================================================


class TestDuckDBCompiler:
    """Tests for DuckDBCompiler class."""

    def test_build_aggregate_sql_generates_valid_sql(self):
        """Compiler should generate valid SQL for aggregate metrics."""
        import duckdb

        compiler = DuckDBCompiler()

        # Create a test relation
        conn = duckdb.connect()
        df = pl.DataFrame(
            {
                "user_id": ["u1", "u1"],
                "event_time": [datetime(2024, 1, 1), datetime(2024, 1, 2)],
                "amount": [100.0, 200.0],
            }
        )
        relation = conn.from_arrow(df.to_arrow())

        ctx = DuckDBComputeContext(
            keys=["user_id"],
            interval="1d",
            timestamp="event_time",
            relation=relation,
            tag="test",
        )

        metric = Aggregate(
            field="amount", function="sum", windows=["7d"], name="total_spend"
        )

        sql = compiler._build_aggregate_sql(metric, ctx)

        # Verify SQL contains expected elements for GROUP BY approach
        assert "SELECT" in sql
        assert "user_id" in sql
        assert "event_time" in sql
        assert "SUM" in sql
        assert "GROUP BY" in sql
        assert "DATE_TRUNC" in sql  # Time bucket truncation

    def test_compile_aggregate_produces_result(self):
        """Compiler should produce a DuckDB relation with metrics."""
        import duckdb

        compiler = DuckDBCompiler()

        conn = duckdb.connect()
        df = pl.DataFrame(
            {
                "user_id": ["u1", "u1", "u1"],
                "event_time": [
                    datetime(2024, 1, 1),
                    datetime(2024, 1, 2),
                    datetime(2024, 1, 3),
                ],
                "amount": [100.0, 200.0, 150.0],
            }
        )
        relation = conn.from_arrow(df.to_arrow())

        ctx = DuckDBComputeContext(
            keys=["user_id"],
            interval="1d",
            timestamp="event_time",
            relation=relation,
            tag="test",
            connection=conn,  # Pass the connection
        )

        metric = Aggregate(
            field="amount", function="sum", windows=["7d"], name="total_spend"
        )

        result = compiler.compile(metric, ctx)

        # Convert to Polars to verify
        result_df = result.pl()
        assert "user_id" in result_df.columns
        assert "event_time" in result_df.columns
        assert "total_spend_1d_7d" in result_df.columns

    def test_compile_aggregate_multiple_windows(self):
        """Compiler should handle multiple window sizes correctly."""
        import duckdb

        compiler = DuckDBCompiler()

        conn = duckdb.connect()
        df = pl.DataFrame(
            {
                "user_id": ["u1", "u1", "u1", "u1"],
                "event_time": [
                    datetime(2024, 1, 1),
                    datetime(2024, 1, 2),
                    datetime(2024, 1, 8),
                    datetime(2024, 1, 15),
                ],
                "amount": [100.0, 200.0, 150.0, 300.0],
            }
        )
        relation = conn.from_arrow(df.to_arrow())

        ctx = DuckDBComputeContext(
            keys=["user_id"],
            interval="1d",
            timestamp="event_time",
            relation=relation,
            tag="test",
            connection=conn,
        )

        # Multiple windows triggers _build_multi_window_sql
        metric = Aggregate(
            field="amount",
            function="sum",
            windows=["7d", "14d"],
            name="total_spend",
        )

        result = compiler.compile(metric, ctx)

        # Convert to Polars to verify
        result_df = result.pl()
        assert "user_id" in result_df.columns
        assert "event_time" in result_df.columns
        assert "total_spend_1d_7d" in result_df.columns
        assert "total_spend_1d_14d" in result_df.columns


# =============================================================================
# DuckDBEngine Tests
# =============================================================================


class TestDuckDBEngine:
    """Tests for DuckDBEngine class."""

    def test_engine_loads_parquet(
        self, duckdb_engine: DuckDBEngine, sample_transactions_parquet: Path
    ):
        """Engine should load parquet files."""
        source = Source(str(sample_transactions_parquet))
        relation = duckdb_engine._load_source(source)

        df = relation.pl()
        assert df.height == 6
        assert "user_id" in df.columns

    def test_engine_loads_csv(
        self, duckdb_engine: DuckDBEngine, sample_transactions_csv: Path
    ):
        """Engine should load CSV files."""
        source = Source(str(sample_transactions_csv))
        relation = duckdb_engine._load_source(source)

        df = relation.pl()
        assert df.height == 3
        assert "user_id" in df.columns

    def test_engine_rejects_unsupported_format(
        self, duckdb_engine: DuckDBEngine
    ):
        """Engine should reject unsupported file formats."""
        # Create a Source with an explicitly unsupported format type
        # (This tests the edge case where format detection might fail)
        with pytest.raises(ValueError, match="Cannot auto-detect format"):
            Source("data.json")

    def test_engine_execute_simple_feature(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """Engine should execute a simple feature without metrics."""

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            engine="duckdb",
        )
        def simple_feature(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[simple_feature],
            offline_store=store,
        )

        # Build the feature
        results = defs.build(feature_names=["simple_feature"], preview=False)

        assert "simple_feature" in results.paths
        # Verify the data was written
        df = store.read("simple_feature")
        assert df.height == 6
        assert set(df.columns) == {"user_id", "amount"}

    def test_engine_execute_feature_with_metrics(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """Engine should execute a feature with aggregate metrics."""

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            timestamp="event_time",
            interval="1d",
            engine="duckdb",
            metrics=[
                Aggregate(
                    field="amount",
                    function="sum",
                    windows=["7d"],
                    name="total_spend",
                ),
                Aggregate(
                    field="amount",
                    function="mean",
                    windows=["7d"],
                    name="avg_spend",
                ),
            ],
        )
        def user_spend(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "event_time", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[user_spend],
            offline_store=store,
        )

        # Build the feature
        results = defs.build(feature_names=["user_spend"], preview=False)

        assert "user_spend" in results.paths
        # Verify the data was written with metrics columns
        df = store.read("user_spend")
        assert "user_id" in df.columns
        assert "event_time" in df.columns
        assert "total_spend_1d_7d" in df.columns
        assert "avg_spend_1d_7d" in df.columns


# =============================================================================
# Integration Tests
# =============================================================================


class TestDuckDBIntegration:
    """Integration tests for DuckDB engine with Definitions."""

    def test_feature_level_engine_selection(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """Features should use their specified engine."""

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            engine="duckdb",
        )
        def duckdb_feature(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "amount")

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            engine="polars",
        )
        def polars_feature(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[duckdb_feature, polars_feature],
            offline_store=store,
        )

        # Build both features
        results = defs.build(preview=False)

        assert "duckdb_feature" in results.paths
        assert "polars_feature" in results.paths

        # Both should produce valid data
        df1 = store.read("duckdb_feature")
        df2 = store.read("polars_feature")
        assert df1.height == df2.height

    def test_default_engine_fallback(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """Features without engine should use Definitions default."""

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
        )
        def default_engine_feature(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[default_engine_feature],
            offline_store=store,
            default_engine="duckdb",
        )

        # Build the feature - should use DuckDB
        results = defs.build(preview=False)

        assert "default_engine_feature" in results.paths
        df = store.read("default_engine_feature")
        assert df.height == 6

    def test_duckdb_with_validators(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """DuckDB engine should run validators correctly."""
        from mlforge import greater_than, not_null

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            engine="duckdb",
            validators={
                "user_id": [not_null()],
                "amount": [greater_than(0)],
            },
        )
        def validated_feature(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[validated_feature],
            offline_store=store,
        )

        # Build should succeed (data passes validation)
        results = defs.build(preview=False)
        assert "validated_feature" in results.paths

    def test_duckdb_with_failing_validators(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """DuckDB engine should handle validation failures gracefully."""
        from mlforge import greater_than

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            engine="duckdb",
            validators={
                # This will fail - amounts are positive, not > 1000
                "amount": [greater_than(1000)],
            },
        )
        def failing_validated_feature(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[failing_validated_feature],
            offline_store=store,
        )

        # Build should complete but not write the failing feature
        results = defs.build(preview=False)

        # The failing feature should not be in results.paths
        assert "failing_validated_feature" not in results.paths

    def test_duckdb_missing_entity_keys(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """DuckDB engine should raise error when entity keys are missing."""

        @feature(
            keys=["nonexistent_key"],
            source=str(sample_transactions_parquet),
            engine="duckdb",
        )
        def missing_key_feature(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[missing_key_feature],
            offline_store=store,
        )

        with pytest.raises(ValueError, match="Entity keys.*not found"):
            defs.build(preview=False)

    def test_duckdb_missing_timestamp(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """DuckDB engine should raise error when timestamp column is missing."""

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            timestamp="nonexistent_timestamp",
            interval="1d",
            engine="duckdb",
            metrics=[
                Aggregate(
                    field="amount", function="sum", windows=["7d"], name="total"
                )
            ],
        )
        def missing_timestamp_feature(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[missing_timestamp_feature],
            offline_store=store,
        )

        with pytest.raises(errors.TimestampParseError, match="not found"):
            defs.build(preview=False)

    def test_duckdb_missing_interval(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """DuckDB engine should raise error when interval is missing with metrics."""

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            timestamp="event_time",
            # interval is missing
            engine="duckdb",
            metrics=[
                Aggregate(
                    field="amount", function="sum", windows=["7d"], name="total"
                )
            ],
        )
        def missing_interval_feature(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "event_time", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[missing_interval_feature],
            offline_store=store,
        )

        with pytest.raises(
            ValueError, match="Aggregation interval is not specified"
        ):
            defs.build(preview=False)

    def test_duckdb_lazyframe_handling(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """DuckDB engine should handle LazyFrame returns from feature functions."""

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            engine="duckdb",
        )
        def lazy_feature(df: pl.DataFrame) -> pl.LazyFrame:
            # Return a LazyFrame instead of DataFrame
            return df.lazy().select("user_id", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[lazy_feature],
            offline_store=store,
        )

        # Build should succeed - engine should collect the LazyFrame
        results = defs.build(preview=False)
        assert "lazy_feature" in results.paths
        df = store.read("lazy_feature")
        assert df.height == 6

    def test_duckdb_multiple_metrics(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """DuckDB engine should handle multiple Aggregate metrics correctly."""

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            timestamp="event_time",
            interval="1d",
            engine="duckdb",
            metrics=[
                Aggregate(
                    field="amount",
                    function="sum",
                    windows=["7d"],
                    name="total_spend",
                ),
                Aggregate(
                    field="amount",
                    function="mean",
                    windows=["14d"],
                    name="avg_spend",
                ),
            ],
        )
        def multi_metric_feature(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "event_time", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[multi_metric_feature],
            offline_store=store,
        )

        results = defs.build(preview=False)
        assert "multi_metric_feature" in results.paths

        df = store.read("multi_metric_feature")
        assert "total_spend_1d_7d" in df.columns
        assert "avg_spend_1d_14d" in df.columns
