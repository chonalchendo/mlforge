"""
Tests for timestamp handling.

Tests the Timestamp class, format auto-detection, and column parsing.
"""

from datetime import datetime

import polars as pl
import pytest

from mlforge.errors import TimestampParseError
from mlforge.timestamps import (
    COMMON_FORMATS,
    Timestamp,
    detect_datetime_format,
    normalize_timestamp,
    parse_timestamp_column,
)


class TestTimestamp:
    """Tests for Timestamp class."""

    def test_create_simple_timestamp(self):
        """Create timestamp with just column name."""
        ts = Timestamp(column="event_time")
        assert ts.column == "event_time"
        assert ts.format is None
        assert ts.alias is None
        assert ts.output_column == "event_time"

    def test_create_timestamp_with_format(self):
        """Create timestamp with explicit format."""
        ts = Timestamp(column="trans_date", format="%Y-%m-%d %H:%M:%S")
        assert ts.column == "trans_date"
        assert ts.format == "%Y-%m-%d %H:%M:%S"
        assert ts.output_column == "trans_date"

    def test_create_timestamp_with_alias(self):
        """Create timestamp with alias."""
        ts = Timestamp(column="trans_date", alias="event_time")
        assert ts.column == "trans_date"
        assert ts.alias == "event_time"
        assert ts.output_column == "event_time"

    def test_create_timestamp_with_format_and_alias(self):
        """Create timestamp with both format and alias."""
        ts = Timestamp(
            column="trans_date",
            format="%Y-%m-%d",
            alias="event_time",
        )
        assert ts.column == "trans_date"
        assert ts.format == "%Y-%m-%d"
        assert ts.alias == "event_time"
        assert ts.output_column == "event_time"

    def test_empty_column_raises_error(self):
        """Empty column name should raise error."""
        with pytest.raises(ValueError):
            Timestamp(column="")

    def test_timestamp_is_immutable(self):
        """Timestamp should be immutable (frozen)."""
        ts = Timestamp(column="event_time")
        with pytest.raises(Exception):  # Pydantic raises ValidationError
            ts.column = "other"  # type: ignore


class TestDetectDatetimeFormat:
    """Tests for detect_datetime_format function."""

    def test_detect_iso8601_format(self):
        """Should detect ISO 8601 format."""
        samples = ["2024-01-15T10:30:00", "2024-01-16T11:45:00"]
        fmt = detect_datetime_format(samples)
        assert fmt == "%Y-%m-%dT%H:%M:%S"

    def test_detect_iso_with_space(self):
        """Should detect ISO format with space separator."""
        samples = ["2024-01-15 10:30:00", "2024-01-16 11:45:00"]
        fmt = detect_datetime_format(samples)
        assert fmt == "%Y-%m-%d %H:%M:%S"

    def test_detect_date_only(self):
        """Should detect date-only format."""
        samples = ["2024-01-15", "2024-01-16", "2024-01-17"]
        fmt = detect_datetime_format(samples)
        assert fmt == "%Y-%m-%d"

    def test_detect_european_format(self):
        """Should detect European date format."""
        samples = ["15/01/2024", "16/01/2024"]
        fmt = detect_datetime_format(samples)
        assert fmt == "%d/%m/%Y"

    def test_detect_us_format(self):
        """Should detect US date format."""
        # Note: US format is tried after European, so use unambiguous dates
        samples = ["12/31/2024", "12/25/2024"]
        fmt = detect_datetime_format(samples)
        assert fmt == "%m/%d/%Y"

    def test_detect_with_microseconds(self):
        """Should detect format with microseconds."""
        samples = ["2024-01-15T10:30:00.123456", "2024-01-16T11:45:00.654321"]
        fmt = detect_datetime_format(samples)
        assert fmt == "%Y-%m-%dT%H:%M:%S.%f"

    def test_empty_samples_returns_none(self):
        """Empty sample list should return None."""
        assert detect_datetime_format([]) is None

    def test_null_samples_filtered(self):
        """Null values in samples should be filtered out."""
        samples: list[str] = ["", "2024-01-15", "", "2024-01-16"]
        fmt = detect_datetime_format(samples)
        assert fmt == "%Y-%m-%d"

    def test_all_null_samples_returns_none(self):
        """All empty samples should return None."""
        samples: list[str] = ["", "", ""]
        assert detect_datetime_format(samples) is None

    def test_unrecognized_format_returns_none(self):
        """Unrecognized format should return None."""
        samples = ["not-a-date", "also-not-a-date"]
        assert detect_datetime_format(samples) is None

    def test_mixed_formats_returns_none(self):
        """Mixed formats that don't all parse should return None."""
        samples = ["2024-01-15", "15/01/2024"]  # ISO and European mixed
        # Neither format will parse both values
        assert detect_datetime_format(samples) is None


class TestParseTimestampColumn:
    """Tests for parse_timestamp_column function."""

    def test_parse_string_column_auto_detect(self):
        """Should auto-detect format and parse string column."""
        df = pl.DataFrame(
            {"ts": ["2024-01-15 10:30:00", "2024-01-16 11:45:00"]}
        )
        result_df, col_name = parse_timestamp_column(df, "ts")

        assert col_name == "ts"
        assert result_df["ts"].dtype == pl.Datetime

    def test_parse_string_column_explicit_format(self):
        """Should use explicit format when provided."""
        df = pl.DataFrame(
            {"ts": ["15/01/2024 10:30:00", "16/01/2024 11:45:00"]}
        )
        ts = Timestamp(column="ts", format="%d/%m/%Y %H:%M:%S")
        result_df, col_name = parse_timestamp_column(df, ts)

        assert col_name == "ts"
        assert result_df["ts"].dtype == pl.Datetime

    def test_parse_with_alias(self):
        """Should rename column when alias provided."""
        df = pl.DataFrame({"trans_date": ["2024-01-15", "2024-01-16"]})
        ts = Timestamp(column="trans_date", alias="event_time")
        result_df, col_name = parse_timestamp_column(df, ts)

        assert col_name == "event_time"
        assert "event_time" in result_df.columns
        assert result_df["event_time"].dtype == pl.Datetime

    def test_datetime_column_passthrough(self):
        """Should pass through datetime columns unchanged."""
        df = pl.DataFrame(
            {"ts": [datetime(2024, 1, 15), datetime(2024, 1, 16)]}
        )
        result_df, col_name = parse_timestamp_column(df, "ts")

        assert col_name == "ts"
        assert result_df["ts"].dtype == pl.Datetime
        # Values should be unchanged
        assert result_df["ts"][0] == datetime(2024, 1, 15)

    def test_datetime_column_with_alias(self):
        """Should apply alias to datetime columns."""
        df = pl.DataFrame(
            {"ts": [datetime(2024, 1, 15), datetime(2024, 1, 16)]}
        )
        ts = Timestamp(column="ts", alias="event_time")
        result_df, col_name = parse_timestamp_column(df, ts)

        assert col_name == "event_time"
        assert "event_time" in result_df.columns

    def test_missing_column_raises_error(self):
        """Should raise error when column doesn't exist."""
        df = pl.DataFrame({"other": [1, 2, 3]})

        with pytest.raises(TimestampParseError) as exc_info:
            parse_timestamp_column(df, "nonexistent")

        assert "not found" in str(exc_info.value)
        assert "nonexistent" in str(exc_info.value)

    def test_auto_detect_failure_raises_error(self):
        """Should raise helpful error when auto-detection fails."""
        df = pl.DataFrame({"ts": ["not-a-date", "also-not"]})

        with pytest.raises(TimestampParseError) as exc_info:
            parse_timestamp_column(df, "ts")

        error_msg = str(exc_info.value)
        assert "ts" in error_msg
        assert "Common formats" in error_msg

    def test_wrong_type_raises_error(self):
        """Should raise error for non-string, non-datetime columns."""
        df = pl.DataFrame({"ts": [1, 2, 3]})

        with pytest.raises(TimestampParseError) as exc_info:
            parse_timestamp_column(df, "ts")

        assert "expected string or datetime" in str(exc_info.value)

    def test_parse_failure_with_explicit_format(self):
        """Should raise error when explicit format doesn't match."""
        df = pl.DataFrame({"ts": ["2024-01-15", "2024-01-16"]})
        ts = Timestamp(column="ts", format="%d/%m/%Y")  # Wrong format

        with pytest.raises(TimestampParseError) as exc_info:
            parse_timestamp_column(df, ts)

        assert "Failed to parse" in str(exc_info.value)

    def test_parse_string_input(self):
        """Should accept string instead of Timestamp object."""
        df = pl.DataFrame({"ts": ["2024-01-15", "2024-01-16"]})
        result_df, col_name = parse_timestamp_column(df, "ts")

        assert col_name == "ts"
        assert result_df["ts"].dtype == pl.Datetime


class TestNormalizeTimestamp:
    """Tests for normalize_timestamp function."""

    def test_normalize_none(self):
        """Should return None for None input."""
        assert normalize_timestamp(None) is None

    def test_normalize_string(self):
        """Should return string unchanged."""
        assert normalize_timestamp("event_time") == "event_time"

    def test_normalize_timestamp_without_alias(self):
        """Should return column name for Timestamp without alias."""
        ts = Timestamp(column="trans_date")
        assert normalize_timestamp(ts) == "trans_date"

    def test_normalize_timestamp_with_alias(self):
        """Should return alias for Timestamp with alias."""
        ts = Timestamp(column="trans_date", alias="event_time")
        assert normalize_timestamp(ts) == "event_time"


class TestTimestampParseError:
    """Tests for TimestampParseError."""

    def test_error_message_contains_column_name(self):
        """Error message should contain column name."""
        error = TimestampParseError(column="my_column", sample_values=[])
        assert "my_column" in str(error)

    def test_error_message_contains_samples(self):
        """Error message should contain sample values."""
        error = TimestampParseError(
            column="ts",
            sample_values=["2024-01-15", "invalid"],
        )
        error_str = str(error)
        assert "2024-01-15" in error_str

    def test_error_message_contains_format_suggestions(self):
        """Error message should contain format suggestions."""
        error = TimestampParseError(column="ts", sample_values=[])
        error_str = str(error)
        assert "Common formats" in error_str
        assert "%Y-%m-%d" in error_str

    def test_error_with_custom_message(self):
        """Custom message should be included."""
        error = TimestampParseError(
            column="ts",
            sample_values=[],
            message="Custom error message",
        )
        assert "Custom error message" in str(error)


class TestCommonFormats:
    """Tests for COMMON_FORMATS constant."""

    def test_common_formats_not_empty(self):
        """COMMON_FORMATS should not be empty."""
        assert len(COMMON_FORMATS) > 0

    def test_iso8601_is_first(self):
        """ISO 8601 format should be first (most common)."""
        assert COMMON_FORMATS[0] == "%Y-%m-%dT%H:%M:%S"

    def test_all_formats_are_valid(self):
        """All formats should be valid strftime format strings."""
        test_dt = datetime(2024, 1, 15, 10, 30, 0)
        for fmt in COMMON_FORMATS:
            # Should not raise - formats without timezone
            if "%z" not in fmt:
                test_dt.strftime(fmt)
