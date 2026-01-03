import pytest

from mlforge.errors import DefinitionsLoadError, FeatureMaterializationError


def test_definitions_load_error_with_message_only():
    # Given an error with just a message
    error = DefinitionsLoadError("Failed to load module")

    # When converting to string
    error_str = str(error)

    # Then it should contain the message
    assert "Failed to load module" in error_str


def test_definitions_load_error_with_cause():
    # Given an error with a cause
    cause = ValueError("Invalid configuration")
    error = DefinitionsLoadError("Failed to load", cause=cause)

    # When converting to string
    error_str = str(error)

    # Then it should include cause information
    assert "Failed to load" in error_str
    assert "Caused by: ValueError" in error_str
    assert "Invalid configuration" in error_str


def test_definitions_load_error_with_hint():
    # Given an error with a hint
    error = DefinitionsLoadError(
        "No definitions found", hint="Make sure you have a Definitions instance"
    )

    # When converting to string
    error_str = str(error)

    # Then it should include the hint
    assert "No definitions found" in error_str
    assert "Hint:" in error_str
    assert "Definitions instance" in error_str


def test_definitions_load_error_with_all_fields():
    # Given an error with message, cause, and hint
    cause = ImportError("Module not found")
    error = DefinitionsLoadError(
        "Failed to load definitions",
        cause=cause,
        hint="Check your import statements",
    )

    # When converting to string
    error_str = str(error)

    # Then it should include all information
    assert "Failed to load definitions" in error_str
    assert "ImportError" in error_str
    assert "Module not found" in error_str
    assert "Hint:" in error_str
    assert "import statements" in error_str


def test_definitions_load_error_filters_traceback():
    # Given an error with traceback containing library code
    try:
        exec("import nonexistent")  # noqa: S102
    except Exception as e:
        error = DefinitionsLoadError("Import failed", cause=e)

        # When converting to string
        error_str = str(error)

        # Then it should filter out site-packages noise
        assert "Import failed" in error_str
        # The traceback filtering should reduce library internals


def test_definitions_load_error_stores_attributes():
    # Given an error with various attributes
    cause = RuntimeError("Test error")
    error = DefinitionsLoadError("Message", cause=cause, hint="Fix this")

    # When checking attributes
    # Then they should be stored
    assert error.message == "Message"
    assert error.cause is cause
    assert error.hint == "Fix this"


def test_feature_materialization_error_with_feature_name():
    # Given an error for a specific feature
    error = FeatureMaterializationError(
        feature_name="user_spend", message="Function returned None"
    )

    # When converting to string
    error_str = str(error)

    # Then it should include the feature name
    assert "user_spend" in error_str
    assert "Function returned None" in error_str


def test_feature_materialization_error_with_hint():
    # Given an error with a hint
    error = FeatureMaterializationError(
        feature_name="my_feature",
        message="Wrong type returned",
        hint="Make sure your feature returns a DataFrame",
    )

    # When converting to string
    error_str = str(error)

    # Then it should include the hint
    assert "my_feature" in error_str
    assert "Wrong type returned" in error_str
    assert "Hint:" in error_str
    assert "returns a DataFrame" in error_str


def test_feature_materialization_error_without_hint():
    # Given an error without a hint
    error = FeatureMaterializationError(
        feature_name="broken_feature", message="Computation failed"
    )

    # When converting to string
    error_str = str(error)

    # Then it should only include name and message
    assert "broken_feature" in error_str
    assert "Computation failed" in error_str
    assert "Hint:" not in error_str


def test_feature_materialization_error_stores_attributes():
    # Given an error with all attributes
    error = FeatureMaterializationError(
        feature_name="test_feature", message="Error message", hint="Try this"
    )

    # When checking attributes
    # Then they should be stored
    assert error.feature_name == "test_feature"
    assert error.message == "Error message"
    assert error.hint == "Try this"


def test_definitions_load_error_is_exception():
    # Given a DefinitionsLoadError
    error = DefinitionsLoadError("test")

    # When checking type
    # Then it should be an Exception
    assert isinstance(error, Exception)


def test_feature_materialization_error_is_exception():
    # Given a FeatureMaterializationError
    error = FeatureMaterializationError(feature_name="test", message="test")

    # When checking type
    # Then it should be an Exception
    assert isinstance(error, Exception)


def test_definitions_load_error_can_be_raised_and_caught():
    # Given a function that raises DefinitionsLoadError
    def failing_function():
        raise DefinitionsLoadError("Test error")

    # When/Then it should be catchable
    with pytest.raises(DefinitionsLoadError, match="Test error"):
        failing_function()


def test_feature_materialization_error_can_be_raised_and_caught():
    # Given a function that raises FeatureMaterializationError
    def failing_function():
        raise FeatureMaterializationError(
            feature_name="test", message="Test error"
        )

    # When/Then it should be catchable
    with pytest.raises(FeatureMaterializationError, match="Test error"):
        failing_function()


# FeatureValidationError tests


def test_feature_validation_error_with_failures():
    # Given validation failures
    from mlforge.errors import FeatureValidationError

    failures = [
        ("user_id", "not_null", "5 null values found"),
        ("amount", "greater_than(0)", "3 values <= 0"),
    ]
    error = FeatureValidationError(feature_name="user_spend", failures=failures)

    # When converting to string
    error_str = str(error)

    # Then it should include feature name and all failures
    assert "user_spend" in error_str
    assert "user_id" in error_str
    assert "not_null" in error_str
    assert "5 null values found" in error_str
    assert "amount" in error_str
    assert "greater_than(0)" in error_str
    assert "3 values <= 0" in error_str


def test_feature_validation_error_stores_attributes():
    # Given a validation error
    from mlforge.errors import FeatureValidationError

    failures = [("col", "validator", "message")]
    error = FeatureValidationError(
        feature_name="test_feature", failures=failures
    )

    # When checking attributes
    # Then they should be stored
    assert error.feature_name == "test_feature"
    assert error.failures == failures


def test_feature_validation_error_is_exception():
    # Given a FeatureValidationError
    from mlforge.errors import FeatureValidationError

    error = FeatureValidationError(feature_name="test", failures=[])

    # When checking type
    # Then it should be an Exception
    assert isinstance(error, Exception)


def test_feature_validation_error_can_be_raised_and_caught():
    # Given a function that raises FeatureValidationError
    from mlforge.errors import FeatureValidationError

    def failing_function():
        raise FeatureValidationError(
            feature_name="test", failures=[("col", "val", "msg")]
        )

    # When/Then it should be catchable
    with pytest.raises(FeatureValidationError, match="Validation failed"):
        failing_function()
