"""Tests for mlforge.validators module."""

import polars as pl

import mlforge.validators as validators


class TestNotNull:
    def test_passes_when_no_nulls(self):
        # Given a series with no null values
        series = pl.Series("test", [1, 2, 3, 4])

        # When validating
        result = validators.not_null()(series)

        # Then it should pass
        assert result.passed is True
        assert result.message is None

    def test_fails_when_nulls_present(self):
        # Given a series with null values
        series = pl.Series("test", [1, None, 3, None])

        # When validating
        result = validators.not_null()(series)

        # Then it should fail with count
        assert result.passed is False
        assert result.failed_count == 2
        assert result.message is not None
        assert "2 null values" in result.message


class TestUnique:
    def test_passes_when_all_unique(self):
        # Given a series with unique values
        series = pl.Series("test", [1, 2, 3, 4])

        # When validating
        result = validators.unique()(series)

        # Then it should pass
        assert result.passed is True

    def test_fails_when_duplicates_present(self):
        # Given a series with duplicates
        series = pl.Series("test", [1, 2, 2, 3, 3, 3])

        # When validating
        result = validators.unique()(series)

        # Then it should fail with duplicate count
        assert result.passed is False
        assert result.failed_count == 3  # 6 total - 3 unique = 3 duplicates
        assert result.message is not None
        assert "duplicate" in result.message


class TestGreaterThan:
    def test_passes_when_all_greater(self):
        # Given a series with all values > threshold
        series = pl.Series("test", [5, 10, 15, 20])

        # When validating with threshold 0
        result = validators.greater_than(0)(series)

        # Then it should pass
        assert result.passed is True

    def test_fails_when_values_at_or_below_threshold(self):
        # Given a series with some values <= threshold
        series = pl.Series("test", [5, 0, -5, 10])

        # When validating with threshold 0
        result = validators.greater_than(0)(series)

        # Then it should fail
        assert result.passed is False
        assert result.failed_count == 2  # 0 and -5
        assert result.message is not None
        assert "<= 0" in result.message

    def test_validator_name_includes_value(self):
        # Given a greater_than validator
        validator = validators.greater_than(100)

        # Then name should include the value
        assert validator.name == "greater_than(100)"


class TestLessThan:
    def test_passes_when_all_less(self):
        # Given a series with all values < threshold
        series = pl.Series("test", [1, 2, 3, 4])

        # When validating with threshold 10
        result = validators.less_than(10)(series)

        # Then it should pass
        assert result.passed is True

    def test_fails_when_values_at_or_above_threshold(self):
        # Given a series with some values >= threshold
        series = pl.Series("test", [5, 10, 15, 3])

        # When validating with threshold 10
        result = validators.less_than(10)(series)

        # Then it should fail
        assert result.passed is False
        assert result.failed_count == 2  # 10 and 15


class TestGreaterThanOrEqual:
    def test_passes_when_all_at_or_above(self):
        # Given a series with all values >= threshold
        series = pl.Series("test", [0, 1, 2, 3])

        # When validating with threshold 0
        result = validators.greater_than_or_equal(0)(series)

        # Then it should pass
        assert result.passed is True

    def test_fails_when_values_below_threshold(self):
        # Given a series with some values < threshold
        series = pl.Series("test", [0, -1, -2, 5])

        # When validating with threshold 0
        result = validators.greater_than_or_equal(0)(series)

        # Then it should fail
        assert result.passed is False
        assert result.failed_count == 2  # -1 and -2


class TestLessThanOrEqual:
    def test_passes_when_all_at_or_below(self):
        # Given a series with all values <= threshold
        series = pl.Series("test", [100, 50, 75, 100])

        # When validating with threshold 100
        result = validators.less_than_or_equal(100)(series)

        # Then it should pass
        assert result.passed is True

    def test_fails_when_values_above_threshold(self):
        # Given a series with some values > threshold
        series = pl.Series("test", [100, 101, 50, 150])

        # When validating with threshold 100
        result = validators.less_than_or_equal(100)(series)

        # Then it should fail
        assert result.passed is False
        assert result.failed_count == 2  # 101 and 150


class TestInRange:
    def test_passes_when_all_in_range_inclusive(self):
        # Given a series with all values in range
        series = pl.Series("test", [0, 50, 100])

        # When validating with inclusive range
        result = validators.in_range(0, 100, inclusive=True)(series)

        # Then it should pass
        assert result.passed is True

    def test_fails_when_values_outside_range_inclusive(self):
        # Given a series with some values outside range
        series = pl.Series("test", [-1, 50, 101])

        # When validating with inclusive range
        result = validators.in_range(0, 100, inclusive=True)(series)

        # Then it should fail
        assert result.passed is False
        assert result.failed_count == 2  # -1 and 101

    def test_exclusive_range_excludes_boundaries(self):
        # Given a series with boundary values
        series = pl.Series("test", [0, 50, 100])

        # When validating with exclusive range
        result = validators.in_range(0, 100, inclusive=False)(series)

        # Then boundary values should fail
        assert result.passed is False
        assert result.failed_count == 2  # 0 and 100

    def test_validator_name_shows_brackets(self):
        # Given in_range validators
        inclusive = validators.in_range(0, 100, inclusive=True)
        exclusive = validators.in_range(0, 100, inclusive=False)

        # Then names should show appropriate brackets
        assert "[" in inclusive.name and "]" in inclusive.name
        assert "(" in exclusive.name and ")" in exclusive.name


class TestMatchesRegex:
    def test_passes_when_all_match(self):
        # Given a series where all values match pattern
        series = pl.Series("test", ["abc", "abcd", "ab"])

        # When validating with pattern
        result = validators.matches_regex(r"^ab")(series)

        # Then it should pass
        assert result.passed is True

    def test_fails_when_values_dont_match(self):
        # Given a series with some non-matching values
        series = pl.Series("test", ["abc", "xyz", "ab"])

        # When validating with pattern
        result = validators.matches_regex(r"^ab")(series)

        # Then it should fail
        assert result.passed is False
        assert result.failed_count == 1


class TestIsIn:
    def test_passes_when_all_in_set(self):
        # Given a series with all values in allowed set
        series = pl.Series("test", ["a", "b", "a", "b"])

        # When validating
        result = validators.is_in(["a", "b", "c"])(series)

        # Then it should pass
        assert result.passed is True

    def test_fails_when_values_not_in_set(self):
        # Given a series with some values not in allowed set
        series = pl.Series("test", ["a", "b", "x", "y"])

        # When validating
        result = validators.is_in(["a", "b", "c"])(series)

        # Then it should fail
        assert result.passed is False
        assert result.failed_count == 2


class TestValidatorClass:
    def test_validator_is_callable(self):
        # Given a validator
        validator = validators.not_null()

        # When calling it
        series = pl.Series("test", [1, 2, 3])
        result = validator(series)

        # Then it should return a ValidationResult
        assert isinstance(result, validators.ValidationResult)

    def test_validator_has_name(self):
        # Given validators
        nn = validators.not_null()
        gt = validators.greater_than(5)

        # Then they should have names
        assert nn.name == "not_null"
        assert gt.name == "greater_than(5)"


class TestValidationResult:
    def test_passed_result_has_no_message(self):
        # Given a passed result
        result = validators.ValidationResult(passed=True)

        # Then message and failed_count should be None
        assert result.message is None
        assert result.failed_count is None

    def test_failed_result_has_message_and_count(self):
        # Given a failed result
        result = validators.ValidationResult(
            passed=False, message="5 null values found", failed_count=5
        )

        # Then message and failed_count should be set
        assert result.message == "5 null values found"
        assert result.failed_count == 5
