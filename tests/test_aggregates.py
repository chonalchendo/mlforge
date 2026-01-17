"""Tests for the Aggregate API."""

import pytest
from pydantic import ValidationError

from mlforge import Aggregate


class TestAggregate:
    """Tests for Aggregate class."""

    def test_aggregate_basic(self):
        """Aggregate with required fields."""
        agg = Aggregate(
            field="amount",
            function="sum",
            windows=["7d", "30d"],
        )
        assert agg.field == "amount"
        assert agg.function == "sum"
        assert agg.windows == ["7d", "30d"]
        assert agg.name is None
        assert agg.description is None
        assert agg.unit is None

    def test_aggregate_with_all_fields(self):
        """Aggregate with all optional fields."""
        agg = Aggregate(
            field="amount",
            function="sum",
            windows=["7d"],
            name="total_spend",
            description="Total amount spent by user",
            unit="USD",
        )
        assert agg.field == "amount"
        assert agg.function == "sum"
        assert agg.name == "total_spend"
        assert agg.description == "Total amount spent by user"
        assert agg.unit == "USD"

    def test_aggregate_column_alias(self):
        """Column property returns field value."""
        agg = Aggregate(field="amt", function="sum", windows=["7d"])
        assert agg.column == "amt"

    def test_aggregate_is_immutable(self):
        """Aggregate should be frozen (immutable)."""
        agg = Aggregate(field="amount", function="sum", windows=["7d"])
        with pytest.raises(ValidationError):
            agg.field = "other"


class TestAggregateValidation:
    """Tests for Pydantic validation."""

    def test_valid_functions(self):
        """All valid function types should work."""
        valid_functions = [
            "sum",
            "count",
            "mean",
            "min",
            "max",
            "std",
            "median",
        ]
        for func in valid_functions:
            agg = Aggregate(field="amount", function=func, windows=["7d"])  # type: ignore
            assert agg.function == func

    def test_invalid_function_raises(self):
        """Invalid function should raise ValidationError."""
        with pytest.raises(ValidationError, match="Input should be"):
            Aggregate(field="amount", function="average", windows=["7d"])  # type: ignore

    def test_valid_window_formats(self):
        """All valid window formats should work."""
        valid_windows = ["30s", "5m", "24h", "7d", "2w"]
        agg = Aggregate(field="amount", function="sum", windows=valid_windows)
        assert agg.windows == valid_windows

    def test_valid_window_formats_months_years(self):
        """Months and years window formats should work."""
        agg = Aggregate(
            field="amount", function="sum", windows=["1mo", "3mo", "1y"]
        )
        assert agg.windows == ["1mo", "3mo", "1y"]

    def test_invalid_window_format_raises(self):
        """Invalid window format should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid window format"):
            Aggregate(field="amount", function="sum", windows=["7 days"])

    def test_invalid_window_format_no_unit(self):
        """Window without unit should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid window format"):
            Aggregate(field="amount", function="sum", windows=["7"])

    def test_invalid_window_format_bad_unit(self):
        """Window with invalid unit should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid window format"):
            Aggregate(field="amount", function="sum", windows=["7x"])

    def test_empty_windows_raises(self):
        """Empty windows list should raise ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            Aggregate(field="amount", function="sum", windows=[])

    def test_empty_field_raises(self):
        """Empty field should raise ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            Aggregate(field="", function="sum", windows=["7d"])

    def test_whitespace_field_raises(self):
        """Whitespace-only field should raise ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            Aggregate(field="   ", function="sum", windows=["7d"])


class TestOutputColumns:
    """Tests for output column naming."""

    def test_output_columns_with_name(self):
        """Output columns when name is provided."""
        agg = Aggregate(
            field="amount",
            function="sum",
            windows=["7d", "30d"],
            name="total_spend",
        )
        columns = agg.output_columns(interval="1d")
        assert columns == ["total_spend_1d_7d", "total_spend_1d_30d"]

    def test_output_columns_without_name(self):
        """Output columns when no name provided - uses field_function pattern."""
        agg = Aggregate(
            field="amount",
            function="sum",
            windows=["7d"],
        )
        columns = agg.output_columns(interval="1d")
        assert columns == ["amount_sum_1d_7d"]

    def test_output_columns_different_functions(self):
        """Different functions produce different column names."""
        for func in ["sum", "count", "mean", "min", "max"]:
            agg = Aggregate(field="amt", function=func, windows=["7d"])  # type: ignore
            columns = agg.output_columns(interval="1d")
            assert columns == [f"amt_{func}_1d_7d"]

    def test_output_columns_requires_interval(self):
        """Output columns raises error without interval."""
        agg = Aggregate(field="amount", function="sum", windows=["7d"])
        with pytest.raises(ValueError, match="Interval required"):
            agg.output_columns()

    def test_output_columns_uses_internal_interval(self):
        """Output columns can use internally set interval."""
        agg = Aggregate(
            field="amount",
            function="sum",
            windows=["7d"],
            name="total",
        )
        agg._interval = "1d"
        columns = agg.output_columns()
        assert columns == ["total_1d_7d"]


class TestValidateColumn:
    """Tests for column validation."""

    def test_validate_column_exists(self):
        """Validate passes when column exists."""
        agg = Aggregate(field="amount", function="sum", windows=["7d"])
        agg.validate_column(
            ["user_id", "amount", "timestamp"]
        )  # Should not raise

    def test_validate_column_missing(self):
        """Validate raises when column is missing."""
        agg = Aggregate(field="nonexistent", function="sum", windows=["7d"])
        with pytest.raises(ValueError, match="not in the dataframe"):
            agg.validate_column(["user_id", "amount"])


class TestToDict:
    """Tests for serialization."""

    def test_to_dict_all_fields(self):
        """Serialize aggregate with all fields."""
        agg = Aggregate(
            field="amount",
            function="sum",
            windows=["7d", "30d"],
            name="total_spend",
            description="Total amount spent",
            unit="USD",
        )
        result = agg.to_dict()
        assert result == {
            "type": "Aggregate",
            "field": "amount",
            "function": "sum",
            "windows": ["7d", "30d"],
            "name": "total_spend",
            "description": "Total amount spent",
            "unit": "USD",
        }

    def test_to_dict_minimal(self):
        """Serialize aggregate with minimal fields."""
        agg = Aggregate(field="amount", function="count", windows=["7d"])
        result = agg.to_dict()
        assert result == {
            "type": "Aggregate",
            "field": "amount",
            "function": "count",
            "windows": ["7d"],
        }
        assert "name" not in result
        assert "description" not in result
        assert "unit" not in result
