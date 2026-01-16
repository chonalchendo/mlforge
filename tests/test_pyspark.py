"""
Tests for PySparkEngine implementation.

These tests verify the PySpark engine behaves correctly for:
- Engine instantiation and session management
- Source loading (Parquet, CSV)
- Basic feature execution
- Entity key generation
- Rolling metric computation
- Type system integration

Note: Tests requiring SparkSession are skipped if PySpark/Java is not available.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl
import pytest

# Conditional import - only import at runtime if available
pyspark_sql = pytest.importorskip("pyspark.sql", reason="PySpark not installed")

if TYPE_CHECKING:
    from pyspark.sql import DataFrame as SparkDataFrame
    from pyspark.sql import SparkSession

# Get types from the imported module
SparkDataFrame = pyspark_sql.DataFrame
SparkSession = pyspark_sql.SparkSession


def _java_is_available() -> bool:
    """Check if Java runtime is properly available for PySpark."""
    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


# Check if Java is available for PySpark tests
JAVA_AVAILABLE = _java_is_available()

# Skip marker for tests requiring SparkSession
requires_spark = pytest.mark.skipif(
    not JAVA_AVAILABLE,
    reason="Java runtime not available for PySpark tests",
)


@pytest.fixture(scope="module")
def spark_session():
    """Create local SparkSession for testing."""
    if not JAVA_AVAILABLE:
        pytest.skip("Java runtime not available")

    spark = (
        SparkSession.builder.master("local[2]")
        .appName("mlforge-test")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield spark
    spark.stop()


@pytest.fixture
def sample_transactions_parquet(tmp_path: Path) -> Path:
    """Create sample parquet file for testing."""
    df = pl.DataFrame(
        {
            "user_id": ["alice", "alice", "bob", "bob", "charlie"],
            "amount": [100.0, 200.0, 150.0, 250.0, 300.0],
            "event_time": [
                datetime(2024, 1, 1, 10, 0),
                datetime(2024, 1, 2, 11, 0),
                datetime(2024, 1, 1, 9, 0),
                datetime(2024, 1, 3, 14, 0),
                datetime(2024, 1, 2, 12, 0),
            ],
        }
    )
    path = tmp_path / "transactions.parquet"
    df.write_parquet(path)
    return path


@pytest.fixture
def sample_csv_file(tmp_path: Path) -> Path:
    """Create sample CSV file for testing."""
    csv_content = """user_id,amount,event_time
alice,100.0,2024-01-01 10:00:00
alice,200.0,2024-01-02 11:00:00
bob,150.0,2024-01-01 09:00:00
"""
    path = tmp_path / "transactions.csv"
    path.write_text(csv_content)
    return path


@requires_spark
class TestPySparkEngineInstantiation:
    """Tests for PySparkEngine initialization."""

    def test_engine_with_existing_session(self, spark_session: SparkSession):
        """Engine should use provided SparkSession."""
        from mlforge.engines import PySparkEngine

        engine = PySparkEngine(spark=spark_session)
        assert engine.spark is spark_session

    def test_engine_auto_creates_session(self):
        """Engine should auto-create session if none provided."""
        from mlforge.engines import PySparkEngine

        engine = PySparkEngine()
        assert engine.spark is not None
        assert isinstance(engine.spark, SparkSession)


@requires_spark
class TestPySparkSourceLoading:
    """Tests for source data loading."""

    def test_load_parquet(
        self, spark_session: SparkSession, sample_transactions_parquet: Path
    ):
        """Engine should load parquet files correctly."""
        from mlforge.engines import PySparkEngine
        from mlforge.sources import Source

        engine = PySparkEngine(spark=spark_session)
        source = Source(str(sample_transactions_parquet))

        df = engine._load_source(source)

        assert isinstance(df, SparkDataFrame)
        assert df.count() == 5
        assert "user_id" in df.columns
        assert "amount" in df.columns

    def test_load_csv(self, spark_session: SparkSession, sample_csv_file: Path):
        """Engine should load CSV files correctly."""
        from mlforge.engines import PySparkEngine
        from mlforge.sources import CSVFormat, Source

        engine = PySparkEngine(spark=spark_session)
        source = Source(str(sample_csv_file), format=CSVFormat())

        df = engine._load_source(source)

        assert isinstance(df, SparkDataFrame)
        assert df.count() == 3
        assert "user_id" in df.columns


@requires_spark
class TestPySparkFeatureExecution:
    """Tests for feature execution."""

    def test_simple_feature_execution(
        self, spark_session: SparkSession, sample_transactions_parquet: Path
    ):
        """Engine should execute simple features."""
        from mlforge.core import feature
        from mlforge.engines import PySparkEngine

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
        )
        def user_amounts(df: SparkDataFrame) -> SparkDataFrame:
            return df.select("user_id", "amount")

        engine = PySparkEngine(spark=spark_session)
        result = engine.execute(user_amounts)

        # Convert to Polars for inspection
        polars_df = result.to_polars()

        assert polars_df.height == 5
        assert "user_id" in polars_df.columns
        assert "amount" in polars_df.columns

    def test_feature_with_transformation(
        self, spark_session: SparkSession, sample_transactions_parquet: Path
    ):
        """Engine should apply feature transformations."""
        from pyspark.sql import functions as F

        from mlforge.core import feature
        from mlforge.engines import PySparkEngine

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
        )
        def user_doubled(df: SparkDataFrame) -> SparkDataFrame:
            return df.select("user_id", (F.col("amount") * 2).alias("doubled"))

        engine = PySparkEngine(spark=spark_session)
        result = engine.execute(user_doubled)
        polars_df = result.to_polars()

        assert "doubled" in polars_df.columns
        # Original amounts were [100, 200, 150, 250, 300]
        # Doubled should be [200, 400, 300, 500, 600]
        assert polars_df["doubled"].sum() == 2000.0


@requires_spark
class TestPySparkEntityKeys:
    """Tests for entity key generation."""

    def test_surrogate_key_generation(
        self, spark_session: SparkSession, tmp_path: Path
    ):
        """Engine should generate surrogate keys from source columns."""
        # Create source with composite key columns
        df = pl.DataFrame(
            {
                "first_name": ["Alice", "Bob"],
                "last_name": ["Smith", "Jones"],
                "amount": [100.0, 200.0],
            }
        )
        path = tmp_path / "users.parquet"
        df.write_parquet(path)

        from mlforge.core import feature
        from mlforge.engines import PySparkEngine
        from mlforge.entities import Entity

        user = Entity(
            name="user",
            join_key="user_id",
            from_columns=["first_name", "last_name"],
        )

        @feature(
            entities=[user],
            source=str(path),
        )
        def user_spend(df: SparkDataFrame) -> SparkDataFrame:
            return df.select("user_id", "amount")

        engine = PySparkEngine(spark=spark_session)
        result = engine.execute(user_spend)
        polars_df = result.to_polars()

        assert "user_id" in polars_df.columns
        # Surrogate keys should be unique per (first_name, last_name) combo
        assert polars_df["user_id"].n_unique() == 2


@requires_spark
class TestPySparkResult:
    """Tests for PySparkResult wrapper."""

    def test_result_schema(
        self, spark_session: SparkSession, sample_transactions_parquet: Path
    ):
        """Result should provide correct schema."""
        from mlforge.core import feature
        from mlforge.engines import PySparkEngine

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
        )
        def user_amounts(df: SparkDataFrame) -> SparkDataFrame:
            return df.select("user_id", "amount")

        engine = PySparkEngine(spark=spark_session)
        result = engine.execute(user_amounts)

        schema = result.schema()
        assert "user_id" in schema
        assert "amount" in schema

    def test_result_row_count(
        self, spark_session: SparkSession, sample_transactions_parquet: Path
    ):
        """Result should provide correct row count."""
        from mlforge.core import feature
        from mlforge.engines import PySparkEngine

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
        )
        def user_amounts(df: SparkDataFrame) -> SparkDataFrame:
            return df.select("user_id", "amount")

        engine = PySparkEngine(spark=spark_session)
        result = engine.execute(user_amounts)

        assert result.row_count() == 5

    def test_result_canonical_schema(
        self, spark_session: SparkSession, sample_transactions_parquet: Path
    ):
        """Result should provide canonical schema types."""
        from mlforge.core import feature
        from mlforge.engines import PySparkEngine
        from mlforge.types import TypeKind

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
        )
        def user_amounts(df: SparkDataFrame) -> SparkDataFrame:
            return df.select("user_id", "amount")

        engine = PySparkEngine(spark=spark_session)
        result = engine.execute(user_amounts)

        canonical = result.schema_canonical()
        assert canonical["user_id"].kind == TypeKind.STRING
        assert canonical["amount"].kind == TypeKind.FLOAT64


class TestPySparkTypeConversions:
    """Tests for PySpark type system integration."""

    def test_from_pyspark_basic_types(self):
        """Should convert basic PySpark types to canonical."""
        from pyspark.sql.types import (
            DoubleType,
            LongType,
            StringType,
        )

        from mlforge.types import TypeKind, from_pyspark

        assert from_pyspark(LongType()).kind == TypeKind.INT64
        assert from_pyspark(DoubleType()).kind == TypeKind.FLOAT64
        assert from_pyspark(StringType()).kind == TypeKind.STRING

    def test_from_pyspark_string_basic(self):
        """Should convert PySpark type strings to canonical."""
        from mlforge.types import TypeKind, from_pyspark_string

        assert from_pyspark_string("LongType()").kind == TypeKind.INT64
        assert from_pyspark_string("StringType()").kind == TypeKind.STRING
        assert from_pyspark_string("DoubleType()").kind == TypeKind.FLOAT64

    def test_to_pyspark_basic_types(self):
        """Should convert canonical types to PySpark."""
        from pyspark.sql.types import (
            DoubleType,
            LongType,
            StringType,
        )

        from mlforge.types import DataType, TypeKind, to_pyspark

        assert isinstance(to_pyspark(DataType(TypeKind.INT64)), LongType)
        assert isinstance(to_pyspark(DataType(TypeKind.FLOAT64)), DoubleType)
        assert isinstance(to_pyspark(DataType(TypeKind.STRING)), StringType)


@requires_spark
class TestPySparkCompiler:
    """Tests for PySparkCompiler rolling metrics."""

    def test_rolling_sum(self, spark_session: SparkSession, tmp_path: Path):
        """Compiler should compute rolling sum correctly."""
        # Create test data with known values
        df = pl.DataFrame(
            {
                "user_id": ["alice"] * 5,
                "amount": [10.0, 20.0, 30.0, 40.0, 50.0],
                "event_time": [
                    datetime(2024, 1, 1),
                    datetime(2024, 1, 2),
                    datetime(2024, 1, 3),
                    datetime(2024, 1, 4),
                    datetime(2024, 1, 5),
                ],
            }
        )
        path = tmp_path / "rolling_test.parquet"
        df.write_parquet(path)

        from mlforge.core import feature
        from mlforge.engines import PySparkEngine
        from mlforge.metrics import Rolling

        @feature(
            keys=["user_id"],
            source=str(path),
            timestamp="event_time",
            interval="1d",
            metrics=[Rolling(windows=["3d"], aggregations={"amount": ["sum"]})],
        )
        def user_rolling(df: SparkDataFrame) -> SparkDataFrame:
            return df.select("user_id", "amount", "event_time")

        engine = PySparkEngine(spark=spark_session)
        result = engine.execute(user_rolling)
        polars_df = result.to_polars()

        # Should have rolling sum column
        sum_col = "user_rolling__amount__sum__1d__3d"
        assert sum_col in polars_df.columns

        # Row count should match input
        assert polars_df.height >= 1

    def test_multiple_aggregations(
        self, spark_session: SparkSession, tmp_path: Path
    ):
        """Compiler should compute multiple aggregations."""
        df = pl.DataFrame(
            {
                "user_id": ["alice"] * 3,
                "amount": [10.0, 20.0, 30.0],
                "event_time": [
                    datetime(2024, 1, 1),
                    datetime(2024, 1, 2),
                    datetime(2024, 1, 3),
                ],
            }
        )
        path = tmp_path / "multi_agg.parquet"
        df.write_parquet(path)

        from mlforge.core import feature
        from mlforge.engines import PySparkEngine
        from mlforge.metrics import Rolling

        @feature(
            keys=["user_id"],
            source=str(path),
            timestamp="event_time",
            interval="1d",
            metrics=[
                Rolling(
                    windows=["3d"],
                    aggregations={"amount": ["sum", "mean", "count"]},
                )
            ],
        )
        def user_multi_agg(df: SparkDataFrame) -> SparkDataFrame:
            return df.select("user_id", "amount", "event_time")

        engine = PySparkEngine(spark=spark_session)
        result = engine.execute(user_multi_agg)
        polars_df = result.to_polars()

        # Should have all aggregation columns
        assert "user_multi_agg__amount__sum__1d__3d" in polars_df.columns
        assert "user_multi_agg__amount__mean__1d__3d" in polars_df.columns
        assert "user_multi_agg__amount__count__1d__3d" in polars_df.columns
