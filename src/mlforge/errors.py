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
        self,
        message: str,
        cause: Exception | None = None,
        hint: str | None = None,
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
            parts.append(
                f"\nCaused by: {type(self.cause).__name__}: {self.cause}"
            )

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

    def __init__(
        self, feature_name: str, message: str, hint: str | None = None
    ):
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


class FeatureSpecError(Exception):
    """
    Raised when feature specification is invalid.

    Typically occurs when requested columns don't exist in the feature.

    Attributes:
        feature_name: Name of the feature
        message: Error description
        available_columns: List of valid column names (if known)
    """

    def __init__(
        self,
        feature_name: str,
        message: str,
        available_columns: list[str] | None = None,
    ):
        """
        Initialize feature spec error.

        Args:
            feature_name: Name of the feature
            message: Error description
            available_columns: Valid columns for this feature. Defaults to None.
        """
        self.feature_name = feature_name
        self.message = message
        self.available_columns = available_columns
        super().__init__(message)

    def __str__(self) -> str:
        """
        Format error message with available columns.

        Returns:
            Formatted error message
        """
        parts = [f"FeatureSpecError: {self.message}"]
        if self.available_columns:
            parts.append("\nAvailable columns:")
            for col in self.available_columns:
                parts.append(f"  - {col}")
        return "\n".join(parts)


class VersionError(Exception):
    """Base class for version-related errors."""

    pass


class InvalidVersionError(VersionError):
    """
    Raised when version string format is invalid.

    Attributes:
        version: The invalid version string
        hint: Suggestion for how to fix the error
    """

    def __init__(self, version: str, hint: str | None = None):
        """
        Initialize invalid version error.

        Args:
            version: The invalid version string
            hint: Resolution suggestion. Defaults to None.
        """
        self.version = version
        self.hint = hint
        super().__init__(f"Invalid version: '{version}'")

    def __str__(self) -> str:
        """
        Format error message with guidance.

        Returns:
            Formatted error message
        """
        parts = [f"Invalid version format: '{self.version}'"]
        parts.append("Expected format: 'X.Y.Z' (e.g., '1.0.0', '2.1.3')")
        if self.hint:
            parts.append(f"Hint: {self.hint}")
        return "\n".join(parts)


class VersionNotFoundError(VersionError):
    """
    Raised when requested version doesn't exist.

    Attributes:
        feature_name: Name of the feature
        version: The requested version that wasn't found
        available: List of available versions (if known)
    """

    def __init__(
        self,
        feature_name: str,
        version: str,
        available: list[str] | None = None,
    ):
        """
        Initialize version not found error.

        Args:
            feature_name: Name of the feature
            version: The requested version that wasn't found
            available: List of available versions. Defaults to None.
        """
        self.feature_name = feature_name
        self.version = version
        self.available = available
        super().__init__(
            f"Version '{version}' not found for feature '{feature_name}'"
        )

    def __str__(self) -> str:
        """
        Format error message with available versions.

        Returns:
            Formatted error message
        """
        parts = [
            f"Version '{self.version}' not found for feature '{self.feature_name}'."
        ]
        if self.available:
            parts.append(f"Available versions: {', '.join(self.available)}")
        else:
            parts.append("No versions available. Run 'mlforge build' first.")
        return "\n".join(parts)


class AlreadyAtVersionError(VersionError):
    """
    Raised when attempting to rollback to the current version.

    Attributes:
        feature_name: Name of the feature
        version: The version that is already current
    """

    def __init__(self, feature_name: str, version: str):
        """
        Initialize already at version error.

        Args:
            feature_name: Name of the feature
            version: The version that is already current
        """
        self.feature_name = feature_name
        self.version = version
        super().__init__(
            f"Feature '{feature_name}' is already at version '{version}'"
        )

    def __str__(self) -> str:
        """
        Format error message.

        Returns:
            Formatted error message
        """
        return (
            f"Version '{self.version}' is already the latest version "
            f"for feature '{self.feature_name}'.\n\nNothing to rollback."
        )


class TimestampParseError(Exception):
    """Raised when timestamp parsing or auto-detection fails."""

    def __init__(
        self,
        column: str,
        sample_values: list[str],
        message: str | None = None,
    ):
        self.column = column
        self.sample_values = sample_values
        self.message = message
        super().__init__(
            message or f"Could not parse timestamp column '{column}'"
        )

    def __str__(self) -> str:
        """Format error with sample values and format suggestions."""
        if self.message:
            parts = [f"TimestampParseError: {self.message}"]
        else:
            parts = [
                f"TimestampParseError: Could not auto-detect datetime format "
                f"for column '{self.column}'."
            ]

        if self.sample_values:
            samples_str = ", ".join(repr(v) for v in self.sample_values[:5])
            parts.append(f"\nSample values: [{samples_str}]")

        parts.append(f"""
Try specifying format explicitly:
    timestamp=mlf.Timestamp(column="{self.column}", format="%Y-%m-%d %H:%M:%S")

Common formats:
    "%Y-%m-%d %H:%M:%S"    -> 2024-01-15 14:30:00
    "%Y-%m-%dT%H:%M:%S"    -> 2024-01-15T14:30:00
    "%Y-%m-%d"             -> 2024-01-15""")

        return "\n".join(parts)


class ProfileError(Exception):
    """
    Raised when profile loading or validation fails.

    Provides context about what went wrong with profile configuration,
    including missing environment variables, invalid store types, and
    profile not found errors.

    Attributes:
        message: Primary error message
        hint: Suggestion for how to fix the error
    """

    def __init__(self, message: str, hint: str | None = None):
        """
        Initialize profile error.

        Args:
            message: Primary error message
            hint: Resolution suggestion. Defaults to None.
        """
        self.message = message
        self.hint = hint
        super().__init__(message)

    def __str__(self) -> str:
        """
        Format error message with hint.

        Returns:
            Formatted error message
        """
        parts = [f"ProfileError: {self.message}"]
        if self.hint:
            parts.append(f"\nHint: {self.hint}")
        return "\n".join(parts)


class SourceDataChangedError(Exception):
    """
    Raised when source data has changed since the feature was built.

    This error is raised during `mlforge sync` when the current source data
    hash doesn't match the stored source_hash in metadata. This indicates
    that rebuilding would produce different results.

    Attributes:
        feature_name: Name of the feature
        expected_hash: The source hash stored in metadata
        current_hash: The hash of the current source data
        source_path: Path to the source data file
    """

    def __init__(
        self,
        feature_name: str,
        expected_hash: str,
        current_hash: str,
        source_path: str,
    ):
        """
        Initialize source data changed error.

        Args:
            feature_name: Name of the feature
            expected_hash: The source hash stored in metadata
            current_hash: The hash of the current source data
            source_path: Path to the source data file
        """
        self.feature_name = feature_name
        self.expected_hash = expected_hash
        self.current_hash = current_hash
        self.source_path = source_path
        super().__init__(
            f"Source data has changed for feature '{feature_name}'"
        )

    def __str__(self) -> str:
        """
        Format error message with hash details and guidance.

        Returns:
            Formatted error message
        """
        return (
            f"Error: Source data has changed for '{self.feature_name}' "
            f"since v{self.feature_name} was built.\n\n"
            f"  Expected: {self.expected_hash}\n"
            f"  Current:  {self.current_hash}\n"
            f"  Source:   {self.source_path}\n\n"
            "This means rebuilding will produce different results than "
            "your teammate's build.\n\n"
            "Options:\n"
            "  - Use --force to rebuild anyway (will auto-version based on changes)\n"
            "  - Ensure you have the same source data as your teammate"
        )
