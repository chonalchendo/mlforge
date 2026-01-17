"""
Aggregate metric definitions for feature computation.

This module provides the Aggregate API for defining rolling window metrics
with explicit naming and metadata.

Example:
    import mlforge as mlf

    @mlf.feature(
        source="data/transactions.parquet",
        keys=["user_id"],
        timestamp="event_time",
        interval="1d",
        metrics=[
            mlf.Aggregate(field="amount", function="sum", windows=["7d", "30d"],
                          name="total_spend", unit="USD"),
            mlf.Aggregate(field="amount", function="count", windows=["7d"],
                          name="txn_count"),
        ],
    )
    def user_spend(df):
        return df.select(["user_id", "event_time", "amount"])
"""

import re
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, PrivateAttr, field_validator

# Supported aggregation functions
AggregateFunction = Literal[
    "sum", "count", "mean", "min", "max", "std", "median"
]

# Pattern for valid window formats: digits followed by unit
# Supports: s (seconds), m (minutes), h (hours), d (days), w (weeks), mo (months), y (years)
_WINDOW_PATTERN = re.compile(r"^\d+(?:mo|[smhdwy])$")


class Aggregate(BaseModel):
    """
    A rolling window aggregation with explicit naming and metadata.

    Computes aggregations over time windows with clear output column naming.
    Each Aggregate produces one output column per window.

    Attributes:
        field: Source column name to aggregate
        function: Aggregation function (sum, count, mean, min, max, std, median)
        windows: Time windows to compute over (e.g., ["7d", "30d"])
        name: Optional name for output column naming
        description: Human-readable description of what this metric represents
        unit: Unit of measurement (e.g., "USD", "count", "transactions")

    Output Column Naming:
        - If `name` provided: `{name}_{interval}_{window}`
        - If no `name`: `{field}_{function}_{interval}_{window}`

    Example:
        mlf.Aggregate(
            field="amount",
            function="sum",
            windows=["7d", "30d"],
            name="total_spend",
            description="Total amount spent by user",
            unit="USD",
        )
    """

    field: str
    function: AggregateFunction
    windows: list[str]
    name: str | None = None
    description: str | None = None
    unit: str | None = None

    # Internal: stores interval for column naming (set by engine during compilation)
    _interval: str | None = PrivateAttr(default=None)

    # Pydantic config
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    @field_validator("windows")
    @classmethod
    def validate_windows(cls, v: list[str]) -> list[str]:
        """Validate that all windows match the expected duration pattern."""
        if not v:
            raise ValueError("windows cannot be empty")

        for window in v:
            if not _WINDOW_PATTERN.match(window):
                raise ValueError(
                    f"Invalid window format '{window}'. "
                    f"Expected pattern like '7d', '30m', '1h', '2w', '1mo', '1y'."
                )
        return v

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        """Validate that field is not empty."""
        if not v or not v.strip():
            raise ValueError("field cannot be empty")
        return v

    @property
    def column(self) -> str:
        """Alias for field - used by compilers."""
        return self.field

    def output_columns(self, interval: str | None = None) -> list[str]:
        """
        Get expected output column names.

        Args:
            interval: Time interval for the feature (e.g., "1d").
                If not provided, uses _interval set during compilation.

        Returns:
            List of column names this metric will produce.

        Raises:
            ValueError: If interval is not set.
        """
        interval = interval or self._interval
        if not interval:
            raise ValueError(
                "Interval required for output column naming. "
                "Either pass interval parameter or ensure Aggregate is used "
                "within a feature that specifies interval."
            )

        columns: list[str] = []

        for window in self.windows:
            if self.name:
                # User provided explicit name: {name}_{interval}_{window}
                col_name = f"{self.name}_{interval}_{window}"
            else:
                # Fallback: {field}_{function}_{interval}_{window}
                col_name = f"{self.field}_{self.function}_{interval}_{window}"
            columns.append(col_name)

        return columns

    def validate_column(self, available_columns: list[str]) -> None:
        """
        Validate that referenced column exists in dataframe.

        Args:
            available_columns: Column names present in the dataframe

        Raises:
            ValueError: If the aggregation column is not found
        """
        if self.field not in available_columns:
            raise ValueError(
                f"Aggregate references column '{self.field}' but it's not in "
                f"the dataframe. Available: {available_columns}"
            )

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize metrics configuration for hashing.

        Used by version.compute_config_hash() to detect configuration changes.

        Returns:
            Dictionary representation of metric configuration
        """
        result: dict[str, Any] = {
            "type": "Aggregate",
            "field": self.field,
            "function": self.function,
            "windows": self.windows,
        }
        if self.name:
            result["name"] = self.name
        if self.description:
            result["description"] = self.description
        if self.unit:
            result["unit"] = self.unit
        return result
