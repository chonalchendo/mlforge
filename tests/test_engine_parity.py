"""
Parity tests comparing Polars and DuckDB engine results.

These tests verify that both engines produce equivalent results for
the same feature definitions.
"""

from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

from mlforge import Definitions, LocalStore, Rolling, feature


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_transactions_parquet(tmp_path: Path) -> Path:
    """Create a sample transactions parquet file for testing."""
    df = pl.DataFrame(
        {
            "user_id": ["u1", "u1", "u1", "u1", "u2", "u2", "u2", "u2"],
            "event_time": [
                datetime(2024, 1, 1, 10, 0),
                datetime(2024, 1, 2, 11, 0),
                datetime(2024, 1, 5, 12, 0),
                datetime(2024, 1, 8, 13, 0),
                datetime(2024, 1, 1, 9, 0),
                datetime(2024, 1, 3, 10, 0),
                datetime(2024, 1, 6, 11, 0),
                datetime(2024, 1, 10, 12, 0),
            ],
            "amount": [100.0, 200.0, 150.0, 300.0, 50.0, 75.0, 125.0, 200.0],
        }
    )
    path = tmp_path / "transactions.parquet"
    df.write_parquet(path)
    return path


# =============================================================================
# Parity Tests
# =============================================================================


class TestEngineParity:
    """Tests comparing Polars and DuckDB engine outputs."""

    def test_simple_feature_parity(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """Simple features should produce identical results."""

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            engine="polars",
        )
        def polars_simple(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "amount")

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            engine="duckdb",
        )
        def duckdb_simple(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[polars_simple, duckdb_simple],
            offline_store=store,
        )

        defs.build(preview=False)

        polars_df = store.read("polars_simple")
        duckdb_df = store.read("duckdb_simple")

        # Sort for comparison
        polars_df = polars_df.sort("user_id", "amount")
        duckdb_df = duckdb_df.sort("user_id", "amount")

        # Compare schemas
        assert polars_df.columns == duckdb_df.columns
        assert polars_df.height == duckdb_df.height

        # Compare values
        assert polars_df["user_id"].to_list() == duckdb_df["user_id"].to_list()
        assert polars_df["amount"].to_list() == duckdb_df["amount"].to_list()

    def test_rolling_sum_semantics(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """
        Test rolling aggregation semantics between engines.

        Both engines should produce identical results with the same:
        - Row count (per-entity date ranges)
        - Aggregation values (backward-looking windows)
        """

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            timestamp="event_time",
            interval="1d",
            engine="polars",
            metrics=[
                Rolling(
                    windows=["7d"],
                    aggregations={"amount": ["sum"]},
                )
            ],
        )
        def polars_rolling(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "event_time", "amount")

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            timestamp="event_time",
            interval="1d",
            engine="duckdb",
            metrics=[
                Rolling(
                    windows=["7d"],
                    aggregations={"amount": ["sum"]},
                )
            ],
        )
        def duckdb_rolling(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "event_time", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[polars_rolling, duckdb_rolling],
            offline_store=store,
        )

        defs.build(preview=False)

        polars_df = store.read("polars_rolling")
        duckdb_df = store.read("duckdb_rolling")

        # Both should have the same base columns
        assert "user_id" in polars_df.columns
        assert "user_id" in duckdb_df.columns
        assert "event_time" in polars_df.columns
        assert "event_time" in duckdb_df.columns

        # Both should produce non-empty results with SAME row count
        assert polars_df.height > 0
        assert duckdb_df.height > 0
        assert polars_df.height == duckdb_df.height, (
            f"Row count mismatch: Polars={polars_df.height}, DuckDB={duckdb_df.height}"
        )

        # Each feature has its own tag in column names
        sum_col_polars = "polars_rolling__amount__sum__1d__7d"
        assert sum_col_polars in polars_df.columns

        sum_col_duckdb = "duckdb_rolling__amount__sum__1d__7d"
        assert sum_col_duckdb in duckdb_df.columns

        # Verify both produce numeric results
        assert polars_df[sum_col_polars].dtype.is_numeric()
        assert duckdb_df[sum_col_duckdb].dtype.is_numeric()

        # Sort both for comparison and verify values match
        polars_sorted = polars_df.sort("user_id", "event_time")
        duckdb_sorted = duckdb_df.sort("user_id", "event_time")

        # Cast timestamps to same type for comparison (DuckDB returns Date, Polars Datetime)
        polars_dates = polars_sorted["event_time"].cast(pl.Date).to_list()
        duckdb_dates = duckdb_sorted["event_time"].cast(pl.Date).to_list()
        assert polars_dates == duckdb_dates, "Timestamps should match"

        # Verify aggregation values match
        polars_sums = polars_sorted[sum_col_polars].to_list()
        duckdb_sums = duckdb_sorted[sum_col_duckdb].to_list()
        assert polars_sums == duckdb_sums, (
            f"Sum values should match: Polars={polars_sums}, DuckDB={duckdb_sums}"
        )

    def test_multiple_aggregations_structure(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """Multiple aggregations should produce correct column structure."""

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            timestamp="event_time",
            interval="1d",
            engine="polars",
            metrics=[
                Rolling(
                    windows=["7d"],
                    aggregations={"amount": ["sum", "mean", "count"]},
                )
            ],
        )
        def polars_multi_agg(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "event_time", "amount")

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            timestamp="event_time",
            interval="1d",
            engine="duckdb",
            metrics=[
                Rolling(
                    windows=["7d"],
                    aggregations={"amount": ["sum", "mean", "count"]},
                )
            ],
        )
        def duckdb_multi_agg(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "event_time", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[polars_multi_agg, duckdb_multi_agg],
            offline_store=store,
        )

        defs.build(preview=False)

        polars_df = store.read("polars_multi_agg")
        duckdb_df = store.read("duckdb_multi_agg")

        # Verify all expected columns exist
        expected_aggs = ["sum", "mean", "count"]
        for agg in expected_aggs:
            polars_col = f"polars_multi_agg__amount__{agg}__1d__7d"
            duckdb_col = f"duckdb_multi_agg__amount__{agg}__1d__7d"
            assert polars_col in polars_df.columns, f"Missing {polars_col}"
            assert duckdb_col in duckdb_df.columns, f"Missing {duckdb_col}"

        # Verify aggregation values are reasonable
        polars_sum_min = polars_df[
            "polars_multi_agg__amount__sum__1d__7d"
        ].min()
        duckdb_sum_min = duckdb_df[
            "duckdb_multi_agg__amount__sum__1d__7d"
        ].min()
        polars_count_min = polars_df[
            "polars_multi_agg__amount__count__1d__7d"
        ].min()
        duckdb_count_min = duckdb_df[
            "duckdb_multi_agg__amount__count__1d__7d"
        ].min()
        assert isinstance(polars_sum_min, (int, float)) and polars_sum_min >= 0
        assert isinstance(duckdb_sum_min, (int, float)) and duckdb_sum_min >= 0
        assert (
            isinstance(polars_count_min, (int, float)) and polars_count_min >= 0
        )
        assert (
            isinstance(duckdb_count_min, (int, float)) and duckdb_count_min >= 0
        )

    def test_multiple_windows_structure(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """Multiple window sizes should produce correct column structure."""

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            timestamp="event_time",
            interval="1d",
            engine="polars",
            metrics=[
                Rolling(
                    windows=["3d", "7d"],
                    aggregations={"amount": ["sum"]},
                )
            ],
        )
        def polars_multi_window(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "event_time", "amount")

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            timestamp="event_time",
            interval="1d",
            engine="duckdb",
            metrics=[
                Rolling(
                    windows=["3d", "7d"],
                    aggregations={"amount": ["sum"]},
                )
            ],
        )
        def duckdb_multi_window(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "event_time", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[polars_multi_window, duckdb_multi_window],
            offline_store=store,
        )

        defs.build(preview=False)

        polars_df = store.read("polars_multi_window")
        duckdb_df = store.read("duckdb_multi_window")

        # Verify all expected columns exist
        for window in ["3d", "7d"]:
            polars_col = f"polars_multi_window__amount__sum__1d__{window}"
            duckdb_col = f"duckdb_multi_window__amount__sum__1d__{window}"
            assert polars_col in polars_df.columns, f"Missing {polars_col}"
            assert duckdb_col in duckdb_df.columns, f"Missing {duckdb_col}"

        # Verify 7d window sums are >= 3d window sums (more data in larger window)
        # This is a logical consistency check
        for df, prefix in [
            (polars_df, "polars_multi_window"),
            (duckdb_df, "duckdb_multi_window"),
        ]:
            sum_3d = df[f"{prefix}__amount__sum__1d__3d"]
            sum_7d = df[f"{prefix}__amount__sum__1d__7d"]
            # 7d should be >= 3d for each row (larger window includes more data)
            assert (sum_7d >= sum_3d).all()

    def test_schema_consistency(
        self, sample_transactions_parquet: Path, tmp_path: Path
    ):
        """Both engines should produce consistent schema types for key columns."""

        @feature(
            keys=["user_id"],
            source=str(sample_transactions_parquet),
            timestamp="event_time",
            interval="1d",
            engine="polars",
            metrics=[
                Rolling(
                    windows=["7d"],
                    aggregations={"amount": ["sum", "mean"]},
                )
            ],
        )
        def polars_schema(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "event_time", "amount")

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
        def duckdb_schema(df: pl.DataFrame) -> pl.DataFrame:
            return df.select("user_id", "event_time", "amount")

        store = LocalStore(str(tmp_path / "store"))
        defs = Definitions(
            name="test",
            features=[polars_schema, duckdb_schema],
            offline_store=store,
        )

        defs.build(preview=False)

        polars_df = store.read("polars_schema")
        duckdb_df = store.read("duckdb_schema")

        # Entity key columns should have same type
        assert polars_df["user_id"].dtype == duckdb_df["user_id"].dtype

        # Timestamp columns should both be temporal types
        # Note: DuckDB DATE_TRUNC returns Date, Polars returns Datetime
        # Both are valid temporal types for time bucketing
        assert polars_df["event_time"].dtype.is_temporal()
        assert duckdb_df["event_time"].dtype.is_temporal()

        # Aggregation columns should be numeric
        polars_sum_col = "polars_schema__amount__sum__1d__7d"
        duckdb_sum_col = "duckdb_schema__amount__sum__1d__7d"

        assert polars_df[polars_sum_col].dtype.is_numeric()
        assert duckdb_df[duckdb_sum_col].dtype.is_numeric()
