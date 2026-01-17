"""
Incremental build utilities for mlforge.

Provides functions for filtering source data by timestamp range,
merging incremental results with existing data, and parsing date ranges.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import polars as pl
from loguru import logger

if TYPE_CHECKING:
    from mlforge.manifest import IncrementalMetadata


# Pattern for parsing duration strings like "7d", "24h", "30m"
_DURATION_PATTERN = re.compile(r"^(\d+)([dhmsw])$")

# Duration unit to timedelta conversion
_DURATION_UNITS = {
    "w": lambda n: timedelta(weeks=n),
    "d": lambda n: timedelta(days=n),
    "h": lambda n: timedelta(hours=n),
    "m": lambda n: timedelta(minutes=n),
    "s": lambda n: timedelta(seconds=n),
}


def parse_duration(duration: str) -> timedelta:
    """
    Parse a duration string into a timedelta.

    Args:
        duration: Duration string like "7d", "24h", "30m", "1w"

    Returns:
        Equivalent timedelta

    Raises:
        ValueError: If duration format is invalid

    Examples:
        >>> parse_duration("7d")
        timedelta(days=7)
        >>> parse_duration("24h")
        timedelta(hours=24)
    """
    match = _DURATION_PATTERN.match(duration.strip().lower())
    if not match:
        raise ValueError(
            f"Invalid duration format: '{duration}'. "
            "Expected format like '7d', '24h', '30m', '1w'."
        )

    value = int(match.group(1))
    unit = match.group(2)

    return _DURATION_UNITS[unit](value)


def parse_date(date_str: str) -> datetime:
    """
    Parse a date string into a datetime.

    Supports ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).

    Args:
        date_str: Date string to parse

    Returns:
        Parsed datetime (in UTC if no timezone specified)

    Raises:
        ValueError: If date format is invalid
    """
    # Try ISO formats
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            # If no timezone, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    # Try ISO format with timezone
    try:
        return datetime.fromisoformat(date_str.strip())
    except ValueError:
        pass

    raise ValueError(
        f"Invalid date format: '{date_str}'. "
        "Expected ISO 8601 format like '2026-01-15' or '2026-01-15T10:30:00'."
    )


def resolve_date_range(
    start: str | datetime | None = None,
    end: str | datetime | None = None,
    last: str | None = None,
    previous_meta: IncrementalMetadata | None = None,
) -> tuple[datetime | None, datetime | None]:
    """
    Resolve date range from various input formats.

    Priority order:
    1. Explicit start/end parameters
    2. --last duration (calculates start from now)
    3. Previous incremental metadata (continues from last processed)

    Args:
        start: Start of date range (string or datetime)
        end: End of date range (string or datetime)
        last: Duration string like "7d" to process last N period
        previous_meta: Previous build's incremental metadata

    Returns:
        Tuple of (start_dt, end_dt). Either may be None.

    Raises:
        ValueError: If both start/end and last are specified
    """
    # Validate mutually exclusive options
    if last and (start or end):
        raise ValueError(
            "Cannot specify --last together with --start or --end. "
            "Use either --last for relative duration, or --start/--end for explicit range."
        )

    now = datetime.now(timezone.utc)

    # Case 1: Explicit start/end
    if start is not None or end is not None:
        start_dt = parse_date(start) if isinstance(start, str) else start
        end_dt = parse_date(end) if isinstance(end, str) else end
        return start_dt, end_dt

    # Case 2: --last duration
    if last:
        duration = parse_duration(last)
        start_dt = now - duration
        return start_dt, now

    # Case 3: Continue from previous build
    if previous_meta:
        # Start from where we left off
        start_dt = parse_date(previous_meta.processed_until)
        return start_dt, now

    # No range specified - will be full refresh
    return None, None


def filter_by_timestamp(
    df: pl.DataFrame,
    timestamp_col: str,
    start: datetime | None = None,
    end: datetime | None = None,
    lookback_days: int = 0,
) -> pl.DataFrame:
    """
    Filter a DataFrame by timestamp range.

    Applies filters to only include rows within the specified time window.
    For rolling window features, includes a lookback period to ensure
    accurate aggregations at the window boundaries.

    Args:
        df: DataFrame to filter
        timestamp_col: Name of the timestamp column
        start: Start of range (inclusive). If None, no lower bound.
        end: End of range (exclusive). If None, no upper bound.
        lookback_days: Additional days to include before start for rolling windows

    Returns:
        Filtered DataFrame

    Raises:
        ValueError: If timestamp column doesn't exist
    """
    if timestamp_col not in df.columns:
        raise ValueError(
            f"Timestamp column '{timestamp_col}' not found in DataFrame. "
            f"Available columns: {df.columns}"
        )

    # Adjust start for lookback
    effective_start = start
    if start and lookback_days > 0:
        effective_start = start - timedelta(days=lookback_days)
        logger.debug(
            f"Including {lookback_days}d lookback: {effective_start} -> {start}"
        )

    # Check if the DataFrame timestamp column has timezone info
    # If not, we need to convert our datetime filters to naive
    ts_dtype = df.schema[timestamp_col]
    ts_has_tz = (
        hasattr(ts_dtype, "time_zone") and ts_dtype.time_zone is not None
    )

    def to_filter_dt(dt: datetime) -> datetime:
        """Convert datetime to match DataFrame's timezone awareness."""
        if ts_has_tz:
            # DataFrame has timezone - keep our UTC datetime
            return dt
        # DataFrame is timezone-naive - convert to naive
        return dt.replace(tzinfo=None)

    # Apply filters
    if effective_start:
        filter_start = to_filter_dt(effective_start)
        df = df.filter(pl.col(timestamp_col) >= filter_start)
    if end:
        filter_end = to_filter_dt(end)
        df = df.filter(pl.col(timestamp_col) < filter_end)

    return df


def merge_incremental(
    existing: pl.DataFrame,
    new_data: pl.DataFrame,
    keys: list[str],
    timestamp_col: str | None = None,
) -> pl.DataFrame:
    """
    Merge new incremental data with existing feature data.

    For point-in-time features, appends new rows and deduplicates by
    keeping the most recent row per entity key.

    Args:
        existing: Existing feature data
        new_data: New incremental data to merge
        keys: Entity key columns for deduplication
        timestamp_col: Timestamp column for ordering. If None, new data wins.

    Returns:
        Merged DataFrame with duplicates resolved
    """
    # Concatenate existing and new data
    combined = pl.concat([existing, new_data], how="diagonal")

    # Deduplicate: keep latest row per entity key
    if timestamp_col and timestamp_col in combined.columns:
        # Sort by timestamp descending, take first per key
        result = (
            combined.sort(timestamp_col, descending=True)
            .unique(subset=keys, keep="first")
            .sort(timestamp_col)  # Restore chronological order
        )
    else:
        # No timestamp - new data wins (appears last after concat)
        result = combined.unique(subset=keys, keep="last")

    return result


def calculate_lookback_days(interval: str | None) -> int:
    """
    Calculate lookback days needed for rolling window features.

    For accurate rolling aggregations at time boundaries, we need to
    include historical data within the window size.

    Args:
        interval: Rolling interval string (e.g., "7d", "30d")

    Returns:
        Number of lookback days (0 if no interval)
    """
    if not interval:
        return 0

    try:
        duration = parse_duration(interval)
        return duration.days
    except ValueError:
        logger.warning(f"Could not parse interval '{interval}' for lookback")
        return 0
