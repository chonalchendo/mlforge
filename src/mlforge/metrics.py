from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

AggregationType = Literal["count", "mean", "sum", "min", "max", "std", "median"]

type Aggregations = dict[str, list[AggregationType]]


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


@dataclass
class Rolling:
    """
    Rolling window aggregation metric.

    Computes aggregations over multiple time windows. Commonly used
    for features like "sum of transactions in last 7 days" or
    "average spend in last 30 days".

    Attributes:
        windows: Time windows to compute over (e.g., ["7d", "30d"] or [timedelta(days=7)])
        aggregations: Mapping of columns to aggregation types
        closed: Which boundary of window to include. Defaults to "left".

    Example:
        Rolling(
            windows=["7d", "30d"],
            aggregations={"amount": ["sum", "mean"]},
            closed="left"
        )

        # Or with timedelta:
        Rolling(
            windows=[timedelta(days=7), timedelta(days=30)],
            aggregations={"amount": ["sum", "mean"]},
            closed="left"
        )
    """

    windows: list[str | timedelta]
    aggregations: Aggregations
    closed: Literal["left", "right", "both", "none"] = "left"

    @property
    def converted_windows(self) -> list[str]:
        """Convert any timedelta windows to Polars duration strings."""
        return [
            timedelta_to_polars_duration(w) if isinstance(w, timedelta) else w
            for w in self.windows
        ]

    def output_columns(self) -> list[str]:
        """
        Get expected output column names.

        Returns:
            List of column names this metric will produce
        """
        columns: list[str] = []
        for col, aggs in self.aggregations.items():
            for agg in aggs:
                for window in self.windows:
                    columns.append(f"{col}__{agg}__{window}")
        return columns

    def validate(self, available_columns: list[str]) -> None:
        """
        Validate that referenced columns exist in dataframe.

        Args:
            available_columns: Column names present in the dataframe

        Raises:
            ValueError: If any aggregation column is not found
        """
        for col in self.aggregations.keys():
            if col not in available_columns:
                raise ValueError(
                    f"Rolling spec references column '{col}' but it's not in the dataframe. Available: {available_columns}"
                )


MetricKind = Rolling
