"""
Validators for feature data quality checks.

Validators are functions that check column values and return ValidationResult
indicating whether the check passed or failed. They run on the output of
feature functions before metrics are applied.

Example:
    @feature(
        source="data/transactions.parquet",
        keys=["user_id"],
        validators={
            "amount": [not_null(), greater_than(0)],
            "user_id": [not_null()],
        },
    )
    def user_transactions(df): ...
"""

from dataclasses import dataclass
from typing import Callable

import polars as pl


@dataclass
class ValidationResult:
    """
    Result of running a validator on a column.

    Attributes:
        passed: Whether the validation check passed
        message: Human-readable description of failure (None if passed)
        failed_count: Number of rows that failed validation (None if passed)
    """

    passed: bool
    message: str | None = None
    failed_count: int | None = None


type ValidatorFunc = Callable[[pl.Series], ValidationResult]


@dataclass
class Validator:
    """
    Container for a validator function with metadata.

    Attributes:
        name: Display name for the validator (used in error messages)
        fn: The validation function that checks a Series
    """

    name: str
    fn: ValidatorFunc

    def __call__(self, series: pl.Series) -> ValidationResult:
        """Execute the validator on a Series."""
        return self.fn(series)


def not_null() -> Validator:
    """
    Validate that a column contains no null values.

    Returns:
        Validator that fails if any null values are found

    Example:
        validators={"user_id": [not_null()]}
    """

    def validate(series: pl.Series) -> ValidationResult:
        null_count = series.null_count()
        if null_count > 0:
            return ValidationResult(
                passed=False,
                message=f"{null_count:,} null values found",
                failed_count=null_count,
            )
        return ValidationResult(passed=True)

    return Validator(name="not_null", fn=validate)


def unique() -> Validator:
    """
    Validate that all values in a column are unique (no duplicates).

    Returns:
        Validator that fails if any duplicate values are found

    Example:
        validators={"transaction_id": [unique()]}
    """

    def validate(series: pl.Series) -> ValidationResult:
        total_count = series.len()
        unique_count = series.n_unique()
        duplicate_count = total_count - unique_count
        if duplicate_count > 0:
            return ValidationResult(
                passed=False,
                message=f"{duplicate_count:,} duplicate values found",
                failed_count=duplicate_count,
            )
        return ValidationResult(passed=True)

    return Validator(name="unique", fn=validate)


def greater_than(value: float) -> Validator:
    """
    Validate that all values are strictly greater than a threshold.

    Args:
        value: The threshold value (exclusive lower bound)

    Returns:
        Validator that fails if any values are <= threshold

    Example:
        validators={"amount": [greater_than(0)]}
    """

    def validate(series: pl.Series) -> ValidationResult:
        failed_count = int((series <= value).sum())
        if failed_count > 0:
            return ValidationResult(
                passed=False,
                message=f"{failed_count:,} values <= {value}",
                failed_count=failed_count,
            )
        return ValidationResult(passed=True)

    return Validator(name=f"greater_than({value})", fn=validate)


def less_than(value: float) -> Validator:
    """
    Validate that all values are strictly less than a threshold.

    Args:
        value: The threshold value (exclusive upper bound)

    Returns:
        Validator that fails if any values are >= threshold

    Example:
        validators={"discount_rate": [less_than(1.0)]}
    """

    def validate(series: pl.Series) -> ValidationResult:
        failed_count = int((series >= value).sum())
        if failed_count > 0:
            return ValidationResult(
                passed=False,
                message=f"{failed_count:,} values >= {value}",
                failed_count=failed_count,
            )
        return ValidationResult(passed=True)

    return Validator(name=f"less_than({value})", fn=validate)


def greater_than_or_equal(value: float) -> Validator:
    """
    Validate that all values are greater than or equal to a threshold.

    Args:
        value: The threshold value (inclusive lower bound)

    Returns:
        Validator that fails if any values are < threshold

    Example:
        validators={"quantity": [greater_than_or_equal(0)]}
    """

    def validate(series: pl.Series) -> ValidationResult:
        failed_count = int((series < value).sum())
        if failed_count > 0:
            return ValidationResult(
                passed=False,
                message=f"{failed_count:,} values < {value}",
                failed_count=failed_count,
            )
        return ValidationResult(passed=True)

    return Validator(name=f"greater_than_or_equal({value})", fn=validate)


def less_than_or_equal(value: float) -> Validator:
    """
    Validate that all values are less than or equal to a threshold.

    Args:
        value: The threshold value (inclusive upper bound)

    Returns:
        Validator that fails if any values are > threshold

    Example:
        validators={"percentage": [less_than_or_equal(100)]}
    """

    def validate(series: pl.Series) -> ValidationResult:
        failed_count = int((series > value).sum())
        if failed_count > 0:
            return ValidationResult(
                passed=False,
                message=f"{failed_count:,} values > {value}",
                failed_count=failed_count,
            )
        return ValidationResult(passed=True)

    return Validator(name=f"less_than_or_equal({value})", fn=validate)


def in_range(
    min_value: float,
    max_value: float,
    inclusive: bool = True,
) -> Validator:
    """
    Validate that all values fall within a specified range.

    Args:
        min_value: Lower bound of the range
        max_value: Upper bound of the range
        inclusive: If True, bounds are inclusive. Defaults to True.

    Returns:
        Validator that fails if any values are outside the range

    Example:
        validators={
            "age": [in_range(0, 120)],
            "score": [in_range(0, 1, inclusive=True)],
        }
    """

    def validate(series: pl.Series) -> ValidationResult:
        if inclusive:
            outside = (series < min_value) | (series > max_value)
        else:
            outside = (series <= min_value) | (series >= max_value)

        failed_count = int(outside.sum())
        if failed_count > 0:
            bound_type = "inclusive" if inclusive else "exclusive"
            return ValidationResult(
                passed=False,
                message=f"{failed_count:,} values outside [{min_value}, {max_value}] ({bound_type})",
                failed_count=failed_count,
            )
        return ValidationResult(passed=True)

    bound_str = "[]" if inclusive else "()"
    return Validator(
        name=f"in_range{bound_str[0]}{min_value}, {max_value}{bound_str[1]}",
        fn=validate,
    )


def matches_regex(pattern: str) -> Validator:
    """
    Validate that all string values match a regex pattern.

    Args:
        pattern: Regular expression pattern to match

    Returns:
        Validator that fails if any values don't match the pattern

    Example:
        validators={"email": [matches_regex(r"^[\\w.-]+@[\\w.-]+\\.\\w+$")]}
    """

    def validate(series: pl.Series) -> ValidationResult:
        non_matching = ~series.str.contains(pattern)
        failed_count = int(non_matching.sum())
        if failed_count > 0:
            return ValidationResult(
                passed=False,
                message=f"{failed_count:,} values don't match pattern '{pattern}'",
                failed_count=failed_count,
            )
        return ValidationResult(passed=True)

    return Validator(name=f"matches_regex('{pattern}')", fn=validate)


def is_in(allowed_values: list) -> Validator:
    """
    Validate that all values are in a set of allowed values.

    Args:
        allowed_values: List of valid values

    Returns:
        Validator that fails if any values are not in the allowed set

    Example:
        validators={"status": [is_in(["pending", "approved", "rejected"])]}
    """

    def validate(series: pl.Series) -> ValidationResult:
        not_in_set = ~series.is_in(allowed_values)
        failed_count = int(not_in_set.sum())
        if failed_count > 0:
            return ValidationResult(
                passed=False,
                message=f"{failed_count:,} values not in allowed set",
                failed_count=failed_count,
            )
        return ValidationResult(passed=True)

    return Validator(name=f"is_in({allowed_values})", fn=validate)
