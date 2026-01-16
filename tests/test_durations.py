"""
Tests for the durations module.

Tests duration parsing and conversion to various formats.
"""

import mlforge.durations as durations


class TestParseDuration:
    """Tests for parse_duration function."""

    def test_parse_days(self):
        """Should parse day durations."""
        result = durations.parse_duration("7d")
        assert result.value == 7
        assert result.unit == "d"

    def test_parse_hours(self):
        """Should parse hour durations."""
        result = durations.parse_duration("24h")
        assert result.value == 24
        assert result.unit == "h"

    def test_parse_minutes(self):
        """Should parse minute durations."""
        result = durations.parse_duration("30m")
        assert result.value == 30
        assert result.unit == "m"

    def test_parse_seconds(self):
        """Should parse second durations."""
        result = durations.parse_duration("60s")
        assert result.value == 60
        assert result.unit == "s"

    def test_parse_weeks(self):
        """Should parse week durations."""
        result = durations.parse_duration("2w")
        assert result.value == 2
        assert result.unit == "w"

    def test_parse_months(self):
        """Should parse month durations (two-char suffix)."""
        result = durations.parse_duration("6mo")
        assert result.value == 6
        assert result.unit == "mo"

    def test_parse_years(self):
        """Should parse year durations."""
        result = durations.parse_duration("1y")
        assert result.value == 1
        assert result.unit == "y"

    def test_parse_no_suffix_defaults_to_days(self):
        """Should default to days when no suffix provided."""
        result = durations.parse_duration("7")
        assert result.value == 7
        assert result.unit == "d"


class TestToDuckDBInterval:
    """Tests for to_duckdb_interval conversion."""

    def test_days(self):
        """Should convert days to DuckDB interval."""
        result = durations.parse_duration("7d").to_duckdb_interval()
        assert result == "INTERVAL '7' DAY"

    def test_hours(self):
        """Should convert hours to DuckDB interval."""
        result = durations.parse_duration("24h").to_duckdb_interval()
        assert result == "INTERVAL '24' HOUR"

    def test_minutes(self):
        """Should convert minutes to DuckDB interval."""
        result = durations.parse_duration("30m").to_duckdb_interval()
        assert result == "INTERVAL '30' MINUTE"

    def test_seconds(self):
        """Should convert seconds to DuckDB interval."""
        result = durations.parse_duration("60s").to_duckdb_interval()
        assert result == "INTERVAL '60' SECOND"

    def test_weeks_converted_to_days(self):
        """Should convert weeks to days for DuckDB."""
        result = durations.parse_duration("2w").to_duckdb_interval()
        assert result == "INTERVAL '14' DAY"

    def test_months(self):
        """Should convert months to DuckDB interval."""
        result = durations.parse_duration("6mo").to_duckdb_interval()
        assert result == "INTERVAL '6' MONTH"

    def test_years(self):
        """Should convert years to DuckDB interval."""
        result = durations.parse_duration("1y").to_duckdb_interval()
        assert result == "INTERVAL '1' YEAR"


class TestToSparkInterval:
    """Tests for to_spark_interval conversion."""

    def test_days(self):
        """Should convert days to Spark interval."""
        result = durations.parse_duration("7d").to_spark_interval()
        assert result == "INTERVAL 7 DAYS"

    def test_hours(self):
        """Should convert hours to Spark interval."""
        result = durations.parse_duration("24h").to_spark_interval()
        assert result == "INTERVAL 24 HOURS"

    def test_weeks_converted_to_days(self):
        """Should convert weeks to days for Spark."""
        result = durations.parse_duration("2w").to_spark_interval()
        assert result == "INTERVAL 14 DAYS"

    def test_months(self):
        """Should convert months to Spark interval."""
        result = durations.parse_duration("6mo").to_spark_interval()
        assert result == "INTERVAL 6 MONTHS"


class TestToPolarsKwargs:
    """Tests for to_polars_kwargs conversion."""

    def test_days(self):
        """Should convert days to Polars kwargs."""
        result = durations.parse_duration("7d").to_polars_kwargs()
        assert result == {"days": 7}

    def test_hours(self):
        """Should convert hours to Polars kwargs."""
        result = durations.parse_duration("24h").to_polars_kwargs()
        assert result == {"hours": 24}

    def test_weeks(self):
        """Should convert weeks to Polars kwargs."""
        result = durations.parse_duration("2w").to_polars_kwargs()
        assert result == {"weeks": 2}

    def test_months_approximated(self):
        """Should approximate months as 30 days for Polars."""
        result = durations.parse_duration("2mo").to_polars_kwargs()
        assert result == {"days": 60}

    def test_years_approximated(self):
        """Should approximate years as 365 days for Polars."""
        result = durations.parse_duration("1y").to_polars_kwargs()
        assert result == {"days": 365}


class TestToTruncUnit:
    """Tests for to_trunc_unit conversion."""

    def test_days(self):
        """Should convert days to trunc unit."""
        assert durations.parse_duration("7d").to_trunc_unit() == "day"

    def test_hours(self):
        """Should convert hours to trunc unit."""
        assert durations.parse_duration("24h").to_trunc_unit() == "hour"

    def test_minutes(self):
        """Should convert minutes to trunc unit."""
        assert durations.parse_duration("30m").to_trunc_unit() == "minute"

    def test_seconds(self):
        """Should convert seconds to trunc unit."""
        assert durations.parse_duration("60s").to_trunc_unit() == "second"

    def test_weeks(self):
        """Should convert weeks to trunc unit."""
        assert durations.parse_duration("2w").to_trunc_unit() == "week"

    def test_months(self):
        """Should convert months to trunc unit."""
        assert durations.parse_duration("6mo").to_trunc_unit() == "month"

    def test_years(self):
        """Should convert years to trunc unit."""
        assert durations.parse_duration("1y").to_trunc_unit() == "year"
