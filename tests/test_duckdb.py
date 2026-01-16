"""
Tests for DuckDB compute backend.

Tests the DuckDBEngine, DuckDBCompiler, and DuckDBResult classes.
"""

from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

import mlforge.errors as errors
from mlforge import Definitions, LocalStore, Rolling, Source, feature
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

    def test_duration_to_interval_days(self):
        """Compiler should convert day durations correctly."""
        compiler = DuckDBCompiler()

        assert compiler._duration_to_interval("7d") == "INTERVAL '7' DAY"
        assert compiler._duration_to_interval("30d") == "INTERVAL '30' DAY"

    def test_duration_to_interval_hours(self):
        """Compiler should convert hour durations correctly."""
        compiler = DuckDBCompiler()

        assert compiler._duration_to_interval("24h") == "INTERVAL '24' HOUR"
        assert compiler._duration_to_interval("1h") == "INTERVAL '1' HOUR"

    def test_duration_to_interval_weeks(self):
        """Compiler should convert week durations to days."""
        compiler = DuckDBCompiler()

        assert compiler._duration_to_interval("1w") == "INTERVAL '7' DAY"
        assert compiler._duration_to_interval("2w") == "INTERVAL '14' DAY"

    def test_duration_to_interval_minutes(self):
        """Compiler should convert minute durations correctly."""
        compiler = DuckDBCompiler()

        assert compiler._duration_to_interval("30m") == "INTERVAL '30' MINUTE"
        assert compiler._duration_to_interval("5m") == "INTERVAL '5' MINUTE"

    def test_duration_to_interval_seconds(self):
        """Compiler should convert second durations correctly."""
        compiler = DuckDBCompiler()

        assert compiler._duration_to_interval("60s") == "INTERVAL '60' SECOND"
        assert compiler._duration_to_interval("1s") == "INTERVAL '1' SECOND"

    def test_duration_to_interval_months(self):
        """Compiler should convert month durations correctly."""
        compiler = DuckDBCompiler()

        assert compiler._duration_to_interval("1mo") == "INTERVAL '1' MONTH"
        assert compiler._duration_to_interval("6mo") == "INTERVAL '6' MONTH"

    def test_duration_to_interval_years(self):
        """Compiler should convert year durations correctly."""
        compiler = DuckDBCompiler()

        assert compiler._duration_to_interval("1y") == "INTERVAL '1' YEAR"
        assert compiler._duration_to_interval("2y") == "INTERVAL '2' YEAR"

    def test_duration_to_interval_default(self):
        """Compiler should default to days for unknown suffixes."""
        compiler = DuckDBCompiler()

        assert compiler._duration_to_interval("7") == "INTERVAL '7' DAY"

    def test_interval_to_trunc_unit_day(self):
        """Compiler should convert day intervals to DATE_TRUNC unit."""
        compiler = DuckDBCompiler()

        assert compiler._interval_to_trunc_unit("1d") == "day"
        assert compiler._interval_to_trunc_unit("7d") == "day"

    def test_interval_to_trunc_unit_hour(self):
        """Compiler should convert hour intervals to DATE_TRUNC unit."""
        compiler = DuckDBCompiler()

        assert compiler._interval_to_trunc_unit("1h") == "hour"
        assert compiler._interval_to_trunc_unit("24h") == "hour"

    def test_interval_to_trunc_unit_minute(self):
        """Compiler should convert minute intervals to DATE_TRUNC unit."""
        compiler = DuckDBCompiler()

        assert compiler._interval_to_trunc_unit("1m") == "minute"
        assert compiler._interval_to_trunc_unit("30m") == "minute"

    def test_interval_to_trunc_unit_second(self):
        """Compiler should convert second intervals to DATE_TRUNC unit."""
        compiler = DuckDBCompiler()

        assert compiler._interval_to_trunc_unit("1s") == "second"
        assert compiler._interval_to_trunc_unit("60s") == "second"

    def test_interval_to_trunc_unit_week(self):
        """Compiler should convert week intervals to DATE_TRUNC unit."""
        compiler = DuckDBCompiler()

        assert compiler._interval_to_trunc_unit("1w") == "week"
        assert compiler._interval_to_trunc_unit("2w") == "week"

    def test_interval_to_trunc_unit_month(self):
        """Compiler should convert month intervals to DATE_TRUNC unit."""
        compiler = DuckDBCompiler()

        assert compiler._interval_to_trunc_unit("1mo") == "month"
        assert compiler._interval_to_trunc_unit("6mo") == "month"

    def test_interval_to_trunc_unit_year(self):
        """Compiler should convert year intervals to DATE_TRUNC unit."""
        compiler = DuckDBCompiler()

        assert compiler._interval_to_trunc_unit("1y") == "year"
        assert compiler._interval_to_trunc_unit("2y") == "year"

    def test_interval_to_trunc_unit_default(self):
        """Compiler should default to day for unknown suffixes."""
        compiler = DuckDBCompiler()

        assert compiler._interval_to_trunc_unit("unknown") == "day"

    def test_build_rolling_sql_generates_valid_sql(self):
        """Compiler should generate valid SQL for rolling aggregations."""
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

        metric = Rolling(
            windows=["7d"],
            aggregations={"amount": ["sum", "mean"]},
        )

        sql = compiler._build_rolling_sql(metric, ctx)

        # Verify SQL contains expected elements for GROUP BY approach
        assert "SELECT" in sql
        assert "user_id" in sql
        assert "event_time" in sql
        assert "SUM" in sql
        assert "AVG" in sql
        assert "GROUP BY" in sql
        assert "DATE_TRUNC" in sql  # Time bucket truncation

    def test_compile_rolling_produces_result(self):
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

        metric = Rolling(
            windows=["7d"],
            aggregations={"amount": ["sum"]},
        )

        result = compiler.compile(metric, ctx)

        # Convert to Polars to verify
        result_df = result.pl()
        assert "user_id" in result_df.columns
        assert "event_time" in result_df.columns
        assert "test__amount__sum__1d__7d" in result_df.columns

    def test_compile_rolling_multiple_windows(self):
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
        metric = Rolling(
            windows=["7d", "14d"],
            aggregations={"amount": ["sum"]},
        )

        result = compiler.compile(metric, ctx)

        # Convert to Polars to verify
        result_df = result.pl()
        assert "user_id" in result_df.columns
        assert "event_time" in result_df.columns
        assert "test__amount__sum__1d__7d" in result_df.columns
        assert "test__amount__sum__1d__14d" in result_df.columns


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
        """Engine should execute a feature with rolling metrics."""

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            timestamp="event_time",
            interval="1d",
            engine="duckdb",
            metrics=[
                Rolling(
                    windows=["7d"],
                    aggregations={"amount": ["sum", "mean"]},
                )
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
        assert "user_spend__amount__sum__1d__7d" in df.columns
        assert "user_spend__amount__mean__1d__7d" in df.columns


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
            metrics=[Rolling(windows=["7d"], aggregations={"amount": ["sum"]})],
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
            metrics=[Rolling(windows=["7d"], aggregations={"amount": ["sum"]})],
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
        """DuckDB engine should handle multiple Rolling metrics correctly."""

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            timestamp="event_time",
            interval="1d",
            engine="duckdb",
            metrics=[
                Rolling(windows=["7d"], aggregations={"amount": ["sum"]}),
                Rolling(windows=["14d"], aggregations={"amount": ["mean"]}),
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
        assert "multi_metric_feature__amount__sum__1d__7d" in df.columns
        assert "multi_metric_feature__amount__mean__1d__14d" in df.columns
