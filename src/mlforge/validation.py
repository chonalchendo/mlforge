"""
Validation runner for feature data quality checks.

This module provides the infrastructure for running validators against
DataFrames and collecting results. It is used by the build process to
validate feature function outputs before metrics are applied.

Example:
    from mlforge.validation import validate_dataframe
    from mlforge.validators import not_null, greater_than

    validators = {
        "amount": [not_null(), greater_than(0)],
        "user_id": [not_null()],
    }

    results = validate_dataframe(df, validators)
    if not results.passed:
        for failure in results.failures:
            print(f"{failure.column}: {failure.result.message}")
"""

from dataclasses import dataclass, field

import polars as pl
from loguru import logger

import mlforge.validators as validators_


@dataclass
class ColumnValidationResult:
    """
    Result of running a single validator on a single column.

    Attributes:
        column: Name of the column that was validated
        validator_name: Name of the validator that was run
        result: The ValidationResult from the validator
    """

    column: str
    validator_name: str
    result: validators_.ValidationResult


@dataclass
class FeatureValidationResult:
    """
    Aggregated validation results for a feature.

    Attributes:
        feature_name: Name of the feature that was validated
        column_results: List of individual column validation results
    """

    feature_name: str
    column_results: list[ColumnValidationResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return True if all validations passed."""
        return all(r.result.passed for r in self.column_results)

    @property
    def failures(self) -> list[ColumnValidationResult]:
        """Return only the validation results that failed."""
        return [r for r in self.column_results if not r.result.passed]

    @property
    def failure_count(self) -> int:
        """Return the number of failed validations."""
        return len(self.failures)


def validate_dataframe(
    df: pl.DataFrame,
    validators: dict[str, list[validators_.Validator]],
) -> list[ColumnValidationResult]:
    """
    Run validators against DataFrame columns.

    Validators are only run on columns that exist in the DataFrame.
    Missing columns are silently skipped (dbt-style behavior).

    Args:
        df: DataFrame to validate
        validators: Mapping of column names to lists of validators

    Returns:
        List of ColumnValidationResult for each validator run

    Example:
        results = validate_dataframe(
            df,
            {"amount": [not_null(), greater_than(0)]}
        )
        for r in results:
            if not r.result.passed:
                print(f"{r.column} failed {r.validator_name}: {r.result.message}")
    """
    results: list[ColumnValidationResult] = []

    for column, column_validators in validators.items():
        if column not in df.columns:
            logger.debug(f"Skipping validation for missing column: {column}")
            continue

        series = df.get_column(column)
        for validator in column_validators:
            logger.debug(f"Running {validator.name} on column {column}")
            result = validator(series)
            results.append(
                ColumnValidationResult(
                    column=column,
                    validator_name=validator.name,
                    result=result,
                )
            )

    return results


def validate_feature(
    feature_name: str,
    df: pl.DataFrame,
    validators: dict[str, list[validators_.Validator]],
) -> FeatureValidationResult:
    """
    Validate a feature's DataFrame and return aggregated results.

    Args:
        feature_name: Name of the feature being validated
        df: DataFrame output from feature function
        validators: Mapping of column names to lists of validators

    Returns:
        FeatureValidationResult with all validation outcomes

    Example:
        result = validate_feature(
            "user_spend",
            df,
            {"amount": [not_null()]}
        )
        if not result.passed:
            print(f"Feature {result.feature_name} failed validation")
    """
    column_results = validate_dataframe(df, validators)
    return FeatureValidationResult(
        feature_name=feature_name,
        column_results=column_results,
    )
