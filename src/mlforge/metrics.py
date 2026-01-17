"""
Metric type definitions and utilities.

This module defines the MetricKind type alias and provides utilities
for working with metrics like duration conversion.
"""

from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mlforge.aggregates import Aggregate


def timedelta_to_polars_duration(td: timedelta) -> str:
    """
    Convert Python timedelta to Polars duration string format.

    Args:
        td: Python timedelta object

    Returns:
        Polars duration string (e.g., "7d", "2h", "30m")

    Example:
        timedelta_to_polars_duration(timedelta(days=7)) -> "7d"
        timedelta_to_polars_duration(timedelta(hours=2)) -> "2h"
    """
    total_seconds = int(td.total_seconds())

    # Try to express in the largest unit possible
    if total_seconds % 86400 == 0:  # Days
        return f"{total_seconds // 86400}d"
    elif total_seconds % 3600 == 0:  # Hours
        return f"{total_seconds // 3600}h"
    elif total_seconds % 60 == 0:  # Minutes
        return f"{total_seconds // 60}m"
    else:  # Seconds
        return f"{total_seconds}s"


# Type alias for all supported metric kinds
# Using a type alias pattern that works with runtime imports
if TYPE_CHECKING:
    from mlforge.aggregates import Aggregate

    MetricKind = Aggregate
else:
    # At runtime, lazily import when accessed
    def __getattr__(name: str):
        if name == "MetricKind":
            from mlforge.aggregates import Aggregate

            return Aggregate
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
