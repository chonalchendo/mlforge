"""Tests for incremental build functionality."""

from datetime import datetime, timedelta, timezone

import polars as pl
import pytest

from mlforge.incremental import (
    calculate_lookback_days,
    filter_by_timestamp,
    merge_incremental,
    parse_date,
    parse_duration,
    resolve_date_range,
)
from mlforge.manifest import IncrementalMetadata

# =============================================================================
# parse_duration tests
# =============================================================================


class TestParseDuration:
    """Tests for parse_duration function."""

    def test_parse_days(self):
        """Parse duration in days."""
        assert parse_duration("7d") == timedelta(days=7)
        assert parse_duration("30d") == timedelta(days=30)
        assert parse_duration("1d") == timedelta(days=1)

    def test_parse_hours(self):
        """Parse duration in hours."""
        assert parse_duration("24h") == timedelta(hours=24)
        assert parse_duration("12h") == timedelta(hours=12)
        assert parse_duration("1h") == timedelta(hours=1)

    def test_parse_minutes(self):
        """Parse duration in minutes."""
        assert parse_duration("30m") == timedelta(minutes=30)
        assert parse_duration("60m") == timedelta(minutes=60)

    def test_parse_weeks(self):
        """Parse duration in weeks."""
        assert parse_duration("1w") == timedelta(weeks=1)
        assert parse_duration("2w") == timedelta(weeks=2)

    def test_parse_case_insensitive(self):
        """Parse duration with uppercase."""
        assert parse_duration("7D") == timedelta(days=7)
        assert parse_duration("24H") == timedelta(hours=24)

    def test_parse_with_whitespace(self):
        """Parse duration with surrounding whitespace."""
        assert parse_duration(" 7d ") == timedelta(days=7)

    def test_invalid_format_raises(self):
        """Invalid duration format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("invalid")

    def test_missing_unit_raises(self):
        """Missing unit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("7")

    def test_missing_value_raises(self):
        """Missing value raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("d")


# =============================================================================
# parse_date tests
# =============================================================================


class TestParseDate:
    """Tests for parse_date function."""

    def test_parse_date_only(self):
        """Parse date without time."""
        result = parse_date("2026-01-15")
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15
        assert result.tzinfo == timezone.utc

    def test_parse_datetime(self):
        """Parse date with time."""
        result = parse_date("2026-01-15T10:30:00")
        assert result.year == 2026
        assert result.hour == 10
        assert result.minute == 30

    def test_parse_datetime_with_z(self):
        """Parse date with Z suffix."""
        result = parse_date("2026-01-15T10:30:00Z")
        assert result.tzinfo == timezone.utc

    def test_parse_with_whitespace(self):
        """Parse date with surrounding whitespace."""
        result = parse_date(" 2026-01-15 ")
        assert result.day == 15

    def test_invalid_format_raises(self):
        """Invalid date format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("not-a-date")

    def test_invalid_date_raises(self):
        """Invalid date values raise ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("2026-13-45")


# =============================================================================
# resolve_date_range tests
# =============================================================================


class TestResolveDateRange:
    """Tests for resolve_date_range function."""

    def test_explicit_start_end(self):
        """Explicit start and end parameters."""
        start_dt, end_dt = resolve_date_range(
            start="2026-01-01",
            end="2026-01-15",
        )
        assert start_dt is not None
        assert end_dt is not None
        assert start_dt.day == 1
        assert end_dt.day == 15

    def test_explicit_start_only(self):
        """Explicit start without end."""
        start_dt, end_dt = resolve_date_range(start="2026-01-01")
        assert start_dt is not None
        assert end_dt is None
        assert start_dt.day == 1

    def test_explicit_end_only(self):
        """Explicit end without start."""
        start_dt, end_dt = resolve_date_range(end="2026-01-15")
        assert start_dt is None
        assert end_dt is not None
        assert end_dt.day == 15

    def test_last_duration(self):
        """--last parameter calculates start from now."""
        start_dt, end_dt = resolve_date_range(last="7d")
        assert start_dt is not None
        assert end_dt is not None
        # Start should be approximately 7 days ago
        diff = end_dt - start_dt
        assert diff.days == 7

    def test_last_and_start_raises(self):
        """Cannot specify both --last and --start."""
        with pytest.raises(ValueError, match="Cannot specify --last together"):
            resolve_date_range(start="2026-01-01", last="7d")

    def test_last_and_end_raises(self):
        """Cannot specify both --last and --end."""
        with pytest.raises(ValueError, match="Cannot specify --last together"):
            resolve_date_range(end="2026-01-15", last="7d")

    def test_previous_meta_continues(self):
        """Previous metadata continues from last processed."""
        prev_meta = IncrementalMetadata(
            last_build_at="2026-01-10T12:00:00Z",
            processed_until="2026-01-10T00:00:00Z",
            timestamp_column="event_time",
        )
        start_dt, end_dt = resolve_date_range(previous_meta=prev_meta)
        assert start_dt is not None
        assert start_dt.day == 10
        assert end_dt is not None

    def test_no_parameters_returns_none(self):
        """No parameters returns (None, None) for full refresh."""
        start_dt, end_dt = resolve_date_range()
        assert start_dt is None
        assert end_dt is None


# =============================================================================
# filter_by_timestamp tests
# =============================================================================


class TestFilterByTimestamp:
    """Tests for filter_by_timestamp function."""

    @pytest.fixture
    def timestamped_df(self):
        """DataFrame with timestamp column."""
        return pl.DataFrame(
            {
                "user_id": ["a", "b", "c", "d", "e"],
                "event_time": [
                    datetime(2026, 1, 1, tzinfo=timezone.utc),
                    datetime(2026, 1, 5, tzinfo=timezone.utc),
                    datetime(2026, 1, 10, tzinfo=timezone.utc),
                    datetime(2026, 1, 15, tzinfo=timezone.utc),
                    datetime(2026, 1, 20, tzinfo=timezone.utc),
                ],
                "amount": [100, 200, 300, 400, 500],
            }
        )

    def test_filter_with_start(self, timestamped_df):
        """Filter with start date only."""
        start = datetime(2026, 1, 10, tzinfo=timezone.utc)
        result = filter_by_timestamp(timestamped_df, "event_time", start=start)
        assert len(result) == 3
        assert result["user_id"].to_list() == ["c", "d", "e"]

    def test_filter_with_end(self, timestamped_df):
        """Filter with end date only (exclusive)."""
        end = datetime(2026, 1, 10, tzinfo=timezone.utc)
        result = filter_by_timestamp(timestamped_df, "event_time", end=end)
        assert len(result) == 2
        assert result["user_id"].to_list() == ["a", "b"]

    def test_filter_with_start_and_end(self, timestamped_df):
        """Filter with both start and end."""
        start = datetime(2026, 1, 5, tzinfo=timezone.utc)
        end = datetime(2026, 1, 15, tzinfo=timezone.utc)
        result = filter_by_timestamp(
            timestamped_df, "event_time", start=start, end=end
        )
        assert len(result) == 2
        assert result["user_id"].to_list() == ["b", "c"]

    def test_filter_with_lookback(self, timestamped_df):
        """Filter includes lookback period."""
        start = datetime(2026, 1, 10, tzinfo=timezone.utc)
        result = filter_by_timestamp(
            timestamped_df,
            "event_time",
            start=start,
            lookback_days=5,
        )
        # Should include Jan 5 (lookback) through end
        assert len(result) == 4
        assert result["user_id"].to_list() == ["b", "c", "d", "e"]

    def test_filter_no_bounds(self, timestamped_df):
        """Filter with no bounds returns all data."""
        result = filter_by_timestamp(timestamped_df, "event_time")
        assert len(result) == len(timestamped_df)

    def test_filter_missing_column_raises(self, timestamped_df):
        """Missing timestamp column raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            filter_by_timestamp(timestamped_df, "nonexistent")


# =============================================================================
# merge_incremental tests
# =============================================================================


class TestMergeIncremental:
    """Tests for merge_incremental function."""

    def test_merge_appends_new_rows(self):
        """New rows are appended."""
        existing = pl.DataFrame(
            {
                "user_id": ["a", "b"],
                "event_time": [
                    datetime(2026, 1, 1, tzinfo=timezone.utc),
                    datetime(2026, 1, 2, tzinfo=timezone.utc),
                ],
                "amount": [100, 200],
            }
        )
        new_data = pl.DataFrame(
            {
                "user_id": ["c"],
                "event_time": [datetime(2026, 1, 3, tzinfo=timezone.utc)],
                "amount": [300],
            }
        )
        result = merge_incremental(
            existing, new_data, keys=["user_id"], timestamp_col="event_time"
        )
        assert len(result) == 3
        assert set(result["user_id"].to_list()) == {"a", "b", "c"}

    def test_merge_updates_existing_rows(self):
        """Existing rows are updated with newer data."""
        existing = pl.DataFrame(
            {
                "user_id": ["a", "b"],
                "event_time": [
                    datetime(2026, 1, 1, tzinfo=timezone.utc),
                    datetime(2026, 1, 2, tzinfo=timezone.utc),
                ],
                "amount": [100, 200],
            }
        )
        new_data = pl.DataFrame(
            {
                "user_id": ["a"],  # Update for user a
                "event_time": [datetime(2026, 1, 5, tzinfo=timezone.utc)],
                "amount": [150],
            }
        )
        result = merge_incremental(
            existing, new_data, keys=["user_id"], timestamp_col="event_time"
        )
        assert len(result) == 2
        # User a should have the newer amount
        user_a = result.filter(pl.col("user_id") == "a")
        assert user_a["amount"].to_list()[0] == 150

    def test_merge_without_timestamp(self):
        """Merge without timestamp - new data wins."""
        existing = pl.DataFrame(
            {
                "user_id": ["a", "b"],
                "amount": [100, 200],
            }
        )
        new_data = pl.DataFrame(
            {
                "user_id": ["a", "c"],
                "amount": [150, 300],
            }
        )
        result = merge_incremental(existing, new_data, keys=["user_id"])
        assert len(result) == 3
        # User a should have the new amount (150)
        user_a = result.filter(pl.col("user_id") == "a")
        assert user_a["amount"].to_list()[0] == 150


# =============================================================================
# calculate_lookback_days tests
# =============================================================================


class TestCalculateLookbackDays:
    """Tests for calculate_lookback_days function."""

    def test_7d_interval(self):
        """7d interval returns 7 days lookback."""
        assert calculate_lookback_days("7d") == 7

    def test_30d_interval(self):
        """30d interval returns 30 days lookback."""
        assert calculate_lookback_days("30d") == 30

    def test_1h_interval(self):
        """1h interval returns 0 days (less than a day)."""
        assert calculate_lookback_days("1h") == 0

    def test_no_interval(self):
        """No interval returns 0."""
        assert calculate_lookback_days(None) == 0

    def test_invalid_interval(self):
        """Invalid interval returns 0 with warning."""
        assert calculate_lookback_days("invalid") == 0


# =============================================================================
# IncrementalMetadata tests
# =============================================================================


class TestIncrementalMetadata:
    """Tests for IncrementalMetadata dataclass."""

    def test_to_dict(self):
        """Convert to dictionary."""
        meta = IncrementalMetadata(
            last_build_at="2026-01-15T10:00:00Z",
            processed_until="2026-01-15T00:00:00Z",
            timestamp_column="event_time",
            lookback_days=7,
        )
        result = meta.to_dict()
        assert result["last_build_at"] == "2026-01-15T10:00:00Z"
        assert result["processed_until"] == "2026-01-15T00:00:00Z"
        assert result["timestamp_column"] == "event_time"
        assert result["lookback_days"] == 7

    def test_from_dict(self):
        """Create from dictionary."""
        data = {
            "last_build_at": "2026-01-15T10:00:00Z",
            "processed_until": "2026-01-15T00:00:00Z",
            "timestamp_column": "event_time",
            "lookback_days": 7,
        }
        meta = IncrementalMetadata.from_dict(data)
        assert meta.last_build_at == "2026-01-15T10:00:00Z"
        assert meta.processed_until == "2026-01-15T00:00:00Z"
        assert meta.timestamp_column == "event_time"
        assert meta.lookback_days == 7

    def test_from_dict_default_lookback(self):
        """Create from dictionary with default lookback."""
        data = {
            "last_build_at": "2026-01-15T10:00:00Z",
            "processed_until": "2026-01-15T00:00:00Z",
            "timestamp_column": "event_time",
        }
        meta = IncrementalMetadata.from_dict(data)
        assert meta.lookback_days == 0
