"""
Duration parsing utilities for mlforge.

This module provides centralized duration string parsing used by all compilers.
Duration strings follow Polars conventions (e.g., "7d", "24h", "30m").

Supported units:
- s: seconds
- m: minutes
- h: hours
- d: days
- w: weeks
- mo: months
- y: years
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedDuration:
    """
    Parsed duration with value and unit.

    Attributes:
        value: Numeric value of the duration
        unit: Unit character(s) (s, m, h, d, w, mo, y)
    """

    value: int
    unit: str

    def to_polars_kwargs(self) -> dict[str, int]:
        """
        Convert to kwargs for pl.duration().

        Returns:
            Dict suitable for pl.duration(**kwargs)
        """
        match self.unit:
            case "s":
                return {"seconds": self.value}
            case "m":
                return {"minutes": self.value}
            case "h":
                return {"hours": self.value}
            case "d":
                return {"days": self.value}
            case "w":
                return {"weeks": self.value}
            case "mo":
                # Polars doesn't support months, approximate with 30 days
                return {"days": self.value * 30}
            case "y":
                # Polars doesn't support years, approximate with 365 days
                return {"days": self.value * 365}
            case _:
                return {"days": self.value}

    def to_duckdb_interval(self) -> str:
        """
        Convert to DuckDB INTERVAL syntax.

        Returns:
            DuckDB INTERVAL string (e.g., "INTERVAL '7' DAY")
        """
        match self.unit:
            case "s":
                return f"INTERVAL '{self.value}' SECOND"
            case "m":
                return f"INTERVAL '{self.value}' MINUTE"
            case "h":
                return f"INTERVAL '{self.value}' HOUR"
            case "d":
                return f"INTERVAL '{self.value}' DAY"
            case "w":
                # Convert weeks to days for DuckDB
                return f"INTERVAL '{self.value * 7}' DAY"
            case "mo":
                return f"INTERVAL '{self.value}' MONTH"
            case "y":
                return f"INTERVAL '{self.value}' YEAR"
            case _:
                return f"INTERVAL '{self.value}' DAY"

    def to_spark_interval(self) -> str:
        """
        Convert to Spark SQL INTERVAL syntax.

        Returns:
            Spark INTERVAL string (e.g., "INTERVAL 7 DAYS")
        """
        match self.unit:
            case "s":
                return f"INTERVAL {self.value} SECONDS"
            case "m":
                return f"INTERVAL {self.value} MINUTES"
            case "h":
                return f"INTERVAL {self.value} HOURS"
            case "d":
                return f"INTERVAL {self.value} DAYS"
            case "w":
                # Convert weeks to days for Spark
                return f"INTERVAL {self.value * 7} DAYS"
            case "mo":
                return f"INTERVAL {self.value} MONTHS"
            case "y":
                return f"INTERVAL {self.value} YEARS"
            case _:
                return f"INTERVAL {self.value} DAYS"

    def to_trunc_unit(self) -> str:
        """
        Convert to date_trunc unit string.

        Returns:
            Truncation unit (e.g., "day", "hour")
        """
        match self.unit:
            case "s":
                return "second"
            case "m":
                return "minute"
            case "h":
                return "hour"
            case "d":
                return "day"
            case "w":
                return "week"
            case "mo":
                return "month"
            case "y":
                return "year"
            case _:
                return "day"


def parse_duration(duration: str) -> ParsedDuration:
    """
    Parse a duration string into value and unit.

    Args:
        duration: Duration string (e.g., "7d", "24h", "30m", "1mo")

    Returns:
        ParsedDuration with value and unit

    Examples:
        parse_duration("7d")   -> ParsedDuration(7, "d")
        parse_duration("24h")  -> ParsedDuration(24, "h")
        parse_duration("1mo")  -> ParsedDuration(1, "mo")
    """
    # Check for two-character suffixes first (mo)
    if duration.endswith("mo"):
        return ParsedDuration(int(duration[:-2]), "mo")

    # Check single-character suffixes
    if duration[-1] in ("s", "m", "h", "d", "w", "y"):
        return ParsedDuration(int(duration[:-1]), duration[-1])

    # Assume days if no suffix
    return ParsedDuration(int(duration), "d")
