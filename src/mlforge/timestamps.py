"""
Timestamp handling with automatic datetime format detection.

Timestamps can be specified as column names (auto-detect format) or as
Timestamp objects with explicit format/alias configuration.
"""

from datetime import datetime

import polars as pl
from pydantic import BaseModel, Field

import mlforge.errors as errors

# Common datetime formats in order of likelihood
COMMON_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",  # ISO 8601
    "%Y-%m-%d %H:%M:%S",  # ISO with space
    "%Y-%m-%dT%H:%M:%S%z",  # ISO with timezone
    "%Y-%m-%d %H:%M:%S%z",  # ISO with space and timezone
    "%Y-%m-%dT%H:%M:%S.%f",  # ISO with microseconds
    "%Y-%m-%d %H:%M:%S.%f",  # ISO with space and microseconds
    "%Y-%m-%d",  # Date only
    "%d/%m/%Y %H:%M:%S",  # European with time
    "%m/%d/%Y %H:%M:%S",  # US with time
    "%d/%m/%Y",  # European date
    "%m/%d/%Y",  # US date
]


class Timestamp(BaseModel, frozen=True):
    """
    Timestamp configuration with optional format and alias.

    Attributes:
        column: Source column name containing timestamp values
        format: strftime format string for parsing. None = auto-detect
        alias: Output column name. None = keep original column name

    Example:
        # Explicit format
        ts = Timestamp(column="trans_date", format="%Y-%m-%d %H:%M:%S")

        # With alias (rename output column)
        ts = Timestamp(column="trans_date", alias="event_time")
    """

    column: str = Field(..., min_length=1)
    format: str | None = None
    alias: str | None = None

    @property
    def output_column(self) -> str:
        """Return the output column name (alias if set, otherwise column)."""
        return self.alias or self.column


def detect_datetime_format(sample_values: list[str]) -> str | None:
    """
    Detect datetime format from sample values.

    Returns the first format from COMMON_FORMATS that parses all samples.
    """
    valid_samples = [v for v in sample_values if v]
    if not valid_samples:
        return None

    def matches_format(fmt: str) -> bool:
        try:
            for value in valid_samples:
                datetime.strptime(str(value), fmt)
            return True
        except ValueError:
            return False

    for fmt in COMMON_FORMATS:
        if matches_format(fmt):
            return fmt
    return None


def parse_timestamp_column(
    df: pl.DataFrame,
    timestamp: str | Timestamp,
) -> tuple[pl.DataFrame, str]:
    """
    Parse timestamp column, auto-detecting format if needed.

    Handles three cases:
    1. Column is already datetime type - use as-is
    2. String column with explicit format - parse with format
    3. String column without format - auto-detect and parse

    Args:
        df: DataFrame containing the timestamp column
        timestamp: Column name string or Timestamp configuration

    Returns:
        Tuple of (processed DataFrame, output column name)

    Raises:
        TimestampParseError: If auto-detection fails or parsing errors occur
    """
    # Normalize to Timestamp object
    if isinstance(timestamp, str):
        ts = Timestamp(column=timestamp)
    else:
        ts = timestamp

    # Validate column exists
    if ts.column not in df.columns:
        raise errors.TimestampParseError(
            column=ts.column,
            sample_values=[],
            message=f"Column '{ts.column}' not found in DataFrame",
        )

    col_dtype = df.schema[ts.column]
    output_name = ts.output_column

    # Already datetime - just handle alias if needed
    if col_dtype == pl.Datetime or str(col_dtype).startswith("Datetime"):
        if ts.alias and ts.alias != ts.column:
            df = df.with_columns(pl.col(ts.column).alias(ts.alias))
        return df, output_name

    # Must be string type to parse
    if col_dtype not in (pl.Utf8, pl.String):
        raise errors.TimestampParseError(
            column=ts.column,
            sample_values=[],
            message=f"Column '{ts.column}' has type {col_dtype}, expected string or datetime",
        )

    # Auto-detect format if not specified
    fmt = ts.format
    if fmt is None:
        sample = df[ts.column].head(10).to_list()
        fmt = detect_datetime_format(sample)
        if fmt is None:
            raise errors.TimestampParseError(
                column=ts.column,
                sample_values=sample[:5],
            )

    # Parse with detected/specified format
    try:
        df = df.with_columns(
            pl.col(ts.column).str.to_datetime(fmt).alias(output_name)
        )
        return df, output_name
    except Exception as e:
        sample = df[ts.column].head(5).to_list()
        raise errors.TimestampParseError(
            column=ts.column,
            sample_values=sample,
            message=f"Failed to parse with format '{fmt}': {e}",
        )


def normalize_timestamp(timestamp: str | Timestamp | None) -> str | None:
    """
    Extract the output column name from a timestamp specification.

    Used by code that needs just the column name string, not the full
    Timestamp configuration.

    Args:
        timestamp: String column name, Timestamp object, or None

    Returns:
        Output column name string, or None if timestamp is None
    """
    if timestamp is None:
        return None
    if isinstance(timestamp, str):
        return timestamp
    return timestamp.output_column
