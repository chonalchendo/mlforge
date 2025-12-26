"""Tests for mlforge.validation module."""

import polars as pl

import mlforge.validation as validation
import mlforge.validators as validators


class TestValidateDataframe:
    def test_returns_results_for_each_validator(self):
        # Given a DataFrame and multiple validators
        df = pl.DataFrame({"col1": [1, 2, 3], "col2": [4, 5, 6]})
        validator_dict = {
            "col1": [validators.not_null(), validators.greater_than(0)],
            "col2": [validators.not_null()],
        }

        # When validating
        results = validation.validate_dataframe(df, validator_dict)

        # Then we should get 3 results (2 for col1, 1 for col2)
        assert len(results) == 3

    def test_skips_missing_columns(self):
        # Given a DataFrame and validators for a missing column
        df = pl.DataFrame({"col1": [1, 2, 3]})
        validator_dict = {
            "col1": [validators.not_null()],
            "missing_col": [validators.not_null()],
        }

        # When validating
        results = validation.validate_dataframe(df, validator_dict)

        # Then only col1 should be validated
        assert len(results) == 1
        assert results[0].column == "col1"

    def test_captures_validation_failures(self):
        # Given a DataFrame with null values
        df = pl.DataFrame({"col1": [1, None, 3]})
        validator_dict = {"col1": [validators.not_null()]}

        # When validating
        results = validation.validate_dataframe(df, validator_dict)

        # Then the failure should be captured
        assert len(results) == 1
        assert results[0].result.passed is False
        assert results[0].result.failed_count == 1

    def test_captures_validation_passes(self):
        # Given a DataFrame with valid data
        df = pl.DataFrame({"col1": [1, 2, 3]})
        validator_dict = {"col1": [validators.not_null()]}

        # When validating
        results = validation.validate_dataframe(df, validator_dict)

        # Then the pass should be captured
        assert len(results) == 1
        assert results[0].result.passed is True


class TestColumnValidationResult:
    def test_stores_column_and_validator_info(self):
        # Given a column validation result
        result = validation.ColumnValidationResult(
            column="user_id",
            validator_name="not_null",
            result=validators.ValidationResult(passed=True),
        )

        # Then it should store the info
        assert result.column == "user_id"
        assert result.validator_name == "not_null"
        assert result.result.passed is True


class TestFeatureValidationResult:
    def test_passed_when_all_pass(self):
        # Given all passing results
        result = validation.FeatureValidationResult(
            feature_name="test_feature",
            column_results=[
                validation.ColumnValidationResult(
                    column="col1",
                    validator_name="not_null",
                    result=validators.ValidationResult(passed=True),
                ),
                validation.ColumnValidationResult(
                    column="col2",
                    validator_name="not_null",
                    result=validators.ValidationResult(passed=True),
                ),
            ],
        )

        # Then it should pass
        assert result.passed is True
        assert result.failure_count == 0
        assert result.failures == []

    def test_fails_when_any_fail(self):
        # Given mixed results
        result = validation.FeatureValidationResult(
            feature_name="test_feature",
            column_results=[
                validation.ColumnValidationResult(
                    column="col1",
                    validator_name="not_null",
                    result=validators.ValidationResult(passed=True),
                ),
                validation.ColumnValidationResult(
                    column="col2",
                    validator_name="not_null",
                    result=validators.ValidationResult(passed=False, message="failed"),
                ),
            ],
        )

        # Then it should fail
        assert result.passed is False
        assert result.failure_count == 1
        assert len(result.failures) == 1
        assert result.failures[0].column == "col2"

    def test_empty_results_passes(self):
        # Given no results
        result = validation.FeatureValidationResult(
            feature_name="test_feature", column_results=[]
        )

        # Then it should pass (vacuously true)
        assert result.passed is True


class TestValidateFeature:
    def test_returns_feature_validation_result(self):
        # Given a DataFrame and validators
        df = pl.DataFrame({"col1": [1, 2, 3]})
        validator_dict = {"col1": [validators.not_null()]}

        # When validating a feature
        result = validation.validate_feature("test_feature", df, validator_dict)

        # Then we should get a FeatureValidationResult
        assert isinstance(result, validation.FeatureValidationResult)
        assert result.feature_name == "test_feature"
        assert result.passed is True

    def test_aggregates_multiple_failures(self):
        # Given a DataFrame with multiple issues
        df = pl.DataFrame({"col1": [None, -1, 3], "col2": [1, None, 3]})
        validator_dict = {
            "col1": [validators.not_null(), validators.greater_than(0)],
            "col2": [validators.not_null()],
        }

        # When validating
        result = validation.validate_feature("test_feature", df, validator_dict)

        # Then failures should be aggregated
        assert result.passed is False
        assert (
            result.failure_count == 3
        )  # 1 null in col1, 1 <= 0 in col1, 1 null in col2
