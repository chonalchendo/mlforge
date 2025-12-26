import traceback


class DefinitionsLoadError(Exception):
    """
    Raised when loading definitions fails.

    Provides enhanced error context including the underlying cause,
    filtered traceback, and helpful hints for resolution.

    Attributes:
        message: Primary error message
        cause: The underlying exception that triggered this error
        hint: Suggestion for how to fix the error
    """

    def __init__(
        self, message: str, cause: Exception | None = None, hint: str | None = None
    ):
        """
        Initialize definitions load error.

        Args:
            message: Primary error message
            cause: Underlying exception. Defaults to None.
            hint: Resolution suggestion. Defaults to None.
        """
        self.message = message
        self.cause = cause
        self.hint = hint
        super().__init__(message)

    def __str__(self) -> str:
        """
        Format error message with cause, traceback, and hint.

        Returns:
            Formatted multi-line error message
        """
        parts = [self.message]

        if self.cause:
            # Get the actual traceback for the cause
            parts.append(f"\nCaused by: {type(self.cause).__name__}: {self.cause}")

            # Include the relevant part of the traceback
            tb_lines = traceback.format_exception(
                type(self.cause), self.cause, self.cause.__traceback__
            )
            # Filter to show only lines from user code, not library internals
            user_tb = [line for line in tb_lines if "site-packages" not in line]
            if user_tb:
                parts.append("\nTraceback:")
                parts.append("".join(user_tb[-4:]))  # last few frames

        if self.hint:
            parts.append(f"\nHint: {self.hint}")

        return "\n".join(parts)


class FeatureMaterializationError(Exception):
    """
    Raised when feature materialization fails.

    Provides context about which feature failed and why, along with
    actionable hints for resolution.

    Attributes:
        feature_name: Name of the feature that failed to materialize
        message: Error description
        hint: Suggestion for how to fix the error
    """

    def __init__(self, feature_name: str, message: str, hint: str | None = None):
        """
        Initialize feature materialization error.

        Args:
            feature_name: Name of the feature that failed
            message: Error description
            hint: Resolution suggestion. Defaults to None.
        """
        self.feature_name = feature_name
        self.message = message
        self.hint = hint
        super().__init__(message)

    def __str__(self) -> str:
        """
        Format error message with feature name and hint.

        Returns:
            Formatted error message
        """
        parts = [f"Failed to materialize '{self.feature_name}': {self.message}"]

        if self.hint:
            parts.append(f"\nHint: {self.hint}")

        return "\n".join(parts)


class FeatureValidationError(Exception):
    """
    Raised when feature validation fails.

    Contains detailed information about which validators failed on which
    columns, allowing for comprehensive error reporting.

    Attributes:
        feature_name: Name of the feature that failed validation
        failures: List of (column, validator_name, message) tuples
    """

    def __init__(
        self,
        feature_name: str,
        failures: list[tuple[str, str, str]],
    ):
        """
        Initialize feature validation error.

        Args:
            feature_name: Name of the feature that failed validation
            failures: List of (column, validator_name, message) tuples
        """
        self.feature_name = feature_name
        self.failures = failures
        super().__init__(f"Validation failed for '{feature_name}'")

    def __str__(self) -> str:
        """
        Format error message with all validation failures.

        Returns:
            Formatted multi-line error message
        """
        parts = [f"Validation failed for '{self.feature_name}':"]
        for column, validator_name, message in self.failures:
            parts.append(f"  - Column '{column}' ({validator_name}): {message}")
        return "\n".join(parts)
