"""
Version management for feature store.

Provides types and functions for:
- Semantic version parsing and bumping
- Hash computation for change detection
- Version directory path construction
- Change type detection

This module centralizes all versioning logic to avoid information leakage
(the same decision appearing in multiple places).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mlforge.manifest import ColumnMetadata


class ChangeType(Enum):
    """
    Type of change detected between feature versions.

    Used to determine semantic version bumps:
    - INITIAL: First build → 1.0.0
    - MAJOR: Breaking change → X+1.0.0
    - MINOR: Additive change → X.Y+1.0
    - PATCH: Data refresh → X.Y.Z+1
    """

    INITIAL = "initial"
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"

    def is_breaking(self) -> bool:
        """Check if this change type represents a breaking change."""
        return self == ChangeType.MAJOR


@dataclass
class ChangeSummary:
    """
    Summary of changes that triggered a version bump.

    Stored in FeatureMetadata.change_summary for auditability.

    Attributes:
        change_type: Type of version bump applied
        reason: Human-readable reason code
        details: List of specific changes (e.g., column names added/removed)
    """

    change_type: ChangeType
    reason: str
    details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "bump_type": self.change_type.value,
            "reason": self.reason,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChangeSummary:
        """Create from dictionary."""
        return cls(
            change_type=ChangeType(data["bump_type"]),
            reason=data["reason"],
            details=data.get("details", []),
        )


# =============================================================================
# Version Parsing and Bumping
# =============================================================================

_VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def parse_version(version_str: str) -> tuple[int, int, int]:
    """
    Parse semantic version string to tuple.

    Args:
        version_str: Version string like "1.2.3"

    Returns:
        Tuple of (major, minor, patch)

    Raises:
        ValueError: If version string is invalid

    Example:
        >>> parse_version("1.2.3")
        (1, 2, 3)
    """
    match = _VERSION_PATTERN.match(version_str)
    if not match:
        raise ValueError(
            f"Invalid version format: '{version_str}'. Expected 'X.Y.Z' (e.g., '1.0.0')"
        )
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def format_version(major: int, minor: int, patch: int) -> str:
    """
    Format version tuple to string.

    Args:
        major: Major version number
        minor: Minor version number
        patch: Patch version number

    Returns:
        Version string like "1.2.3"
    """
    return f"{major}.{minor}.{patch}"


def bump_version(current: str, change_type: ChangeType) -> str:
    """
    Increment version by change type.

    Args:
        current: Current version string (e.g., "1.2.3")
        change_type: Type of version increment

    Returns:
        New version string

    Raises:
        ValueError: If change_type is INITIAL (use "1.0.0" directly)

    Example:
        >>> bump_version("1.2.3", ChangeType.MINOR)
        "1.3.0"
        >>> bump_version("1.2.3", ChangeType.MAJOR)
        "2.0.0"
    """
    if change_type == ChangeType.INITIAL:
        raise ValueError(
            "Cannot bump INITIAL change type. Use '1.0.0' directly."
        )

    major, minor, patch = parse_version(current)

    match change_type:
        case ChangeType.MAJOR:
            return format_version(major + 1, 0, 0)
        case ChangeType.MINOR:
            return format_version(major, minor + 1, 0)
        case ChangeType.PATCH:
            return format_version(major, minor, patch + 1)
        case _:
            raise ValueError(f"Unexpected change type: {change_type}")


def sort_versions(versions: list[str]) -> list[str]:
    """
    Sort version strings semantically.

    Args:
        versions: List of version strings

    Returns:
        Sorted list (oldest to newest)

    Example:
        >>> sort_versions(["1.10.0", "1.2.0", "2.0.0"])
        ["1.2.0", "1.10.0", "2.0.0"]
    """
    return sorted(versions, key=lambda v: parse_version(v))


def is_valid_version(version_str: str) -> bool:
    """
    Check if a string is a valid semantic version.

    Args:
        version_str: String to validate

    Returns:
        True if valid version format, False otherwise
    """
    return _VERSION_PATTERN.match(version_str) is not None


# =============================================================================
# Path Construction (Information Hiding)
# =============================================================================


def versioned_data_path(
    store_root: Path, feature_name: str, version: str
) -> Path:
    """
    Get path to versioned feature data file.

    Args:
        store_root: Root path of the feature store
        feature_name: Name of the feature
        version: Semantic version string (e.g., "1.0.0")

    Returns:
        Path to data.parquet file

    Example:
        >>> versioned_data_path(Path("./store"), "user_spend", "1.0.0")
        Path("./store/user_spend/1.0.0/data.parquet")
    """
    return store_root / feature_name / version / "data.parquet"


def versioned_metadata_path(
    store_root: Path, feature_name: str, version: str
) -> Path:
    """
    Get path to versioned feature metadata file.

    Args:
        store_root: Root path of the feature store
        feature_name: Name of the feature
        version: Semantic version string

    Returns:
        Path to .meta.json file
    """
    return store_root / feature_name / version / ".meta.json"


def latest_pointer_path(store_root: Path, feature_name: str) -> Path:
    """
    Get path to _latest.json pointer file.

    Args:
        store_root: Root path of the feature store
        feature_name: Name of the feature

    Returns:
        Path to _latest.json file within feature directory
    """
    return store_root / feature_name / "_latest.json"


def feature_versions_dir(store_root: Path, feature_name: str) -> Path:
    """
    Get path to feature's version directory (parent of all versions).

    Args:
        store_root: Root path of the feature store
        feature_name: Name of the feature

    Returns:
        Path to feature directory containing version subdirectories
    """
    return store_root / feature_name


# =============================================================================
# Hash Computation
# =============================================================================


def compute_schema_hash(columns: list[ColumnMetadata]) -> str:
    """
    Compute hash of column names and dtypes for schema change detection.

    Captures structural schema changes (columns added/removed, dtype changes).

    Args:
        columns: List of ColumnMetadata from feature result

    Returns:
        Hex string hash (first 12 characters of SHA256)
    """
    # Sort columns by name for consistent hashing
    sorted_cols = sorted(columns, key=lambda c: c.name)

    # Include only name and dtype (not input/agg/window which are config)
    schema_data = [(c.name, c.dtype) for c in sorted_cols]

    serialized = json.dumps(schema_data, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()[:12]


def compute_config_hash(
    keys: list[str],
    timestamp: str | None,
    interval: str | None,
    metrics_config: list[dict[str, Any]] | None,
) -> str:
    """
    Compute hash of feature configuration for config change detection.

    Captures configuration changes that affect computation (keys, timing, metrics).

    Args:
        keys: Entity key columns
        timestamp: Timestamp column name
        interval: Rolling interval string
        metrics_config: Serialized metrics configuration

    Returns:
        Hex string hash (first 12 characters of SHA256)
    """
    config_data = {
        "keys": sorted(keys),
        "timestamp": timestamp,
        "interval": interval,
        "metrics": metrics_config or [],
    }

    serialized = json.dumps(config_data, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()[:12]


def compute_content_hash(path: Path) -> str:
    """
    Compute hash of parquet file content for data change detection.

    Uses file-based hashing for efficiency with large files.

    Args:
        path: Path to parquet file

    Returns:
        Hex string hash (first 12 characters of SHA256)

    Raises:
        FileNotFoundError: If path doesn't exist
    """
    hasher = hashlib.sha256()

    with open(path, "rb") as f:
        # Read in chunks for memory efficiency
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)

    return hasher.hexdigest()[:12]


def compute_source_hash(path: Path | str) -> str:
    """
    Compute hash of source data file for reproducibility verification.

    Uses file-based hashing for efficiency with large files. This hash
    is stored in metadata and used by `mlforge sync` to verify that
    teammates have the same source data before rebuilding.

    Args:
        path: Path to source data file (parquet, csv, etc.)

    Returns:
        Hex string hash (first 12 characters of SHA256)

    Raises:
        FileNotFoundError: If path doesn't exist
    """
    if isinstance(path, str):
        path = Path(path)

    hasher = hashlib.sha256()

    with open(path, "rb") as f:
        # Read in chunks for memory efficiency
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)

    return hasher.hexdigest()[:12]


# =============================================================================
# Change Detection
# =============================================================================


def detect_change_type(
    previous_columns: list[str] | None,
    current_columns: list[str],
    previous_schema_hash: str | None,
    current_schema_hash: str,
    previous_config_hash: str | None,
    current_config_hash: str,
) -> ChangeType:
    """
    Determine version bump type based on schema and config changes.

    Change detection logic (from roadmap):
    - No previous version → INITIAL (1.0.0)
    - Columns removed → MAJOR (breaking)
    - Dtype changed → MAJOR (breaking, detected via schema_hash)
    - Columns added → MINOR (additive)
    - Config changed → MINOR
    - Same schema/config → PATCH (data refresh)

    Args:
        previous_columns: Column names from previous version (None if first build)
        current_columns: Column names from current build
        previous_schema_hash: Schema hash from previous version
        current_schema_hash: Schema hash from current build
        previous_config_hash: Config hash from previous version
        current_config_hash: Config hash from current build

    Returns:
        ChangeType indicating required version bump

    Example:
        >>> detect_change_type(None, ["a", "b"], None, "abc123", None, "def456")
        ChangeType.INITIAL
        >>> detect_change_type(
        ...     ["a", "b", "c"], ["a", "b"], "abc", "def", "123", "123"
        ... )
        ChangeType.MAJOR  # Column removed
    """
    # First build - no previous version
    if previous_columns is None or previous_schema_hash is None:
        return ChangeType.INITIAL

    previous_set = set(previous_columns)
    current_set = set(current_columns)

    # Check for removed columns (breaking change)
    removed_columns = previous_set - current_set
    if removed_columns:
        return ChangeType.MAJOR

    # Check for schema hash change (dtype changes are breaking)
    # Note: We already checked for removed columns, so if schema_hash differs
    # and no columns removed, it must be dtype change or column addition
    if previous_schema_hash != current_schema_hash:
        # Added columns (additive change)
        added_columns = current_set - previous_set
        if added_columns:
            return ChangeType.MINOR
        # Same columns but different hash = dtype changed (breaking)
        return ChangeType.MAJOR

    # Check for config changes (interval, metrics, etc.)
    if previous_config_hash != current_config_hash:
        return ChangeType.MINOR

    # Same schema and config = data refresh only
    return ChangeType.PATCH


def build_change_summary(
    change_type: ChangeType,
    previous_columns: list[str] | None,
    current_columns: list[str],
) -> ChangeSummary:
    """
    Build structured change summary for metadata.

    Args:
        change_type: Detected change type
        previous_columns: Previous version columns
        current_columns: Current version columns

    Returns:
        ChangeSummary with bump_type, reason, and details
    """
    if change_type == ChangeType.INITIAL:
        return ChangeSummary(
            change_type=ChangeType.INITIAL,
            reason="first_build",
            details=[],
        )

    previous_set = set(previous_columns or [])
    current_set = set(current_columns)

    removed = sorted(previous_set - current_set)
    added = sorted(current_set - previous_set)

    if removed:
        return ChangeSummary(
            change_type=ChangeType.MAJOR,
            reason="columns_removed",
            details=removed,
        )

    if added:
        return ChangeSummary(
            change_type=ChangeType.MINOR,
            reason="columns_added",
            details=added,
        )

    if change_type == ChangeType.MINOR:
        return ChangeSummary(
            change_type=ChangeType.MINOR,
            reason="config_changed",
            details=[],
        )

    if change_type == ChangeType.MAJOR:
        return ChangeSummary(
            change_type=ChangeType.MAJOR,
            reason="dtype_changed",
            details=[],
        )

    return ChangeSummary(
        change_type=ChangeType.PATCH,
        reason="data_refresh",
        details=[],
    )


# =============================================================================
# Version Discovery
# =============================================================================


def list_versions(store_root: Path, feature_name: str) -> list[str]:
    """
    List all versions of a feature, sorted semantically.

    Scans the feature directory for version subdirectories.

    Args:
        store_root: Root path of the feature store
        feature_name: Name of the feature

    Returns:
        Sorted list of version strings (oldest to newest), empty if none

    Example:
        >>> list_versions(Path("./store"), "user_spend")
        ["1.0.0", "1.0.1", "1.1.0"]
    """
    feature_dir = feature_versions_dir(store_root, feature_name)

    if not feature_dir.exists():
        return []

    versions = []
    for path in feature_dir.iterdir():
        if path.is_dir() and is_valid_version(path.name):
            versions.append(path.name)

    return sort_versions(versions)


def get_latest_version(store_root: Path, feature_name: str) -> str | None:
    """
    Get latest version from _latest.json pointer.

    Args:
        store_root: Root path of the feature store
        feature_name: Name of the feature

    Returns:
        Latest version string, or None if no versions exist
    """
    pointer_path = latest_pointer_path(store_root, feature_name)

    if not pointer_path.exists():
        return None

    with open(pointer_path) as f:
        data = json.load(f)

    return data.get("version")


def write_latest_pointer(
    store_root: Path, feature_name: str, version: str
) -> None:
    """
    Write _latest.json pointer file.

    Args:
        store_root: Root path of the feature store
        feature_name: Name of the feature
        version: Version to mark as latest
    """
    pointer_path = latest_pointer_path(store_root, feature_name)
    pointer_path.parent.mkdir(parents=True, exist_ok=True)

    with open(pointer_path, "w") as f:
        json.dump({"version": version}, f, indent=2)


def resolve_version(
    store_root: Path,
    feature_name: str,
    version: str | None,
) -> str | None:
    """
    Resolve version string to actual version.

    Args:
        store_root: Root path of the feature store
        feature_name: Name of the feature
        version: Explicit version or None for latest

    Returns:
        Resolved version string, or None if feature doesn't exist
    """
    if version is not None:
        return version
    return get_latest_version(store_root, feature_name)


# =============================================================================
# Version Diff Types
# =============================================================================


@dataclass
class ColumnInfo:
    """
    Information about a column in a schema.

    Attributes:
        name: Column name
        dtype: Data type string
    """

    name: str
    dtype: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary."""
        return {"name": self.name, "dtype": self.dtype}


@dataclass
class ColumnModification:
    """
    Information about a column whose dtype changed.

    Attributes:
        name: Column name
        dtype_from: Original data type
        dtype_to: New data type
    """

    name: str
    dtype_from: str
    dtype_to: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "dtype_from": self.dtype_from,
            "dtype_to": self.dtype_to,
        }


@dataclass
class SchemaChanges:
    """
    Schema changes between two versions.

    Attributes:
        added: Columns added in the new version
        removed: Columns removed from the old version
        modified: Columns with changed dtypes
    """

    added: list[ColumnInfo] = field(default_factory=list)
    removed: list[ColumnInfo] = field(default_factory=list)
    modified: list[ColumnModification] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[dict[str, str]]]:
        """Convert to dictionary."""
        return {
            "added": [c.to_dict() for c in self.added],
            "removed": [c.to_dict() for c in self.removed],
            "modified": [c.to_dict() for c in self.modified],
        }

    def has_changes(self) -> bool:
        """Check if there are any schema changes."""
        return bool(self.added or self.removed or self.modified)


@dataclass
class ConfigChange:
    """
    A single configuration change.

    Attributes:
        key: Configuration key that changed
        value_from: Original value
        value_to: New value
    """

    key: str
    value_from: Any
    value_to: Any


@dataclass
class DataStatistics:
    """
    Data statistics comparison between two versions.

    Attributes:
        row_count_from: Row count in first version
        row_count_to: Row count in second version
        unique_entities_from: Unique entity count in first version
        unique_entities_to: Unique entity count in second version
        date_range_from: (min_date, max_date) tuple for first version
        date_range_to: (min_date, max_date) tuple for second version
    """

    row_count_from: int
    row_count_to: int
    unique_entities_from: int | None = None
    unique_entities_to: int | None = None
    date_range_from: tuple[str, str] | None = None
    date_range_to: tuple[str, str] | None = None

    def row_count_change_pct(self) -> float | None:
        """Calculate percentage change in row count."""
        if self.row_count_from == 0:
            return None
        return (
            (self.row_count_to - self.row_count_from) / self.row_count_from
        ) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "row_count": {
                "from": self.row_count_from,
                "to": self.row_count_to,
            }
        }
        pct = self.row_count_change_pct()
        if pct is not None:
            result["row_count"]["change_pct"] = round(pct, 1)

        if (
            self.unique_entities_from is not None
            and self.unique_entities_to is not None
        ):
            result["unique_entities"] = {
                "from": self.unique_entities_from,
                "to": self.unique_entities_to,
            }

        if self.date_range_from is not None and self.date_range_to is not None:
            result["date_range"] = {
                "from": {
                    "min": self.date_range_from[0],
                    "max": self.date_range_from[1],
                },
                "to": {
                    "min": self.date_range_to[0],
                    "max": self.date_range_to[1],
                },
            }

        return result


@dataclass
class VersionDiff:
    """
    Complete diff between two feature versions.

    Attributes:
        feature: Feature name
        version_from: First version compared
        version_to: Second version compared
        change_type: Type of change (NONE, PATCH, MINOR, MAJOR)
        schema_changes: Schema differences
        config_changes: Configuration differences
        data_statistics: Data statistics comparison
    """

    feature: str
    version_from: str
    version_to: str
    change_type: ChangeType
    schema_changes: SchemaChanges
    config_changes: list[ConfigChange] = field(default_factory=list)
    data_statistics: DataStatistics | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        result: dict[str, Any] = {
            "feature": self.feature,
            "version_from": self.version_from,
            "version_to": self.version_to,
            "change_type": self.change_type.value.upper(),
            "schema_changes": self.schema_changes.to_dict(),
            "config_changes": {
                c.key: {"from": c.value_from, "to": c.value_to}
                for c in self.config_changes
            },
        }
        if self.data_statistics:
            result["data_statistics"] = self.data_statistics.to_dict()
        return result


@dataclass
class RollbackResult:
    """
    Result of a rollback operation.

    Attributes:
        feature: Feature name
        version_from: Version before rollback
        version_to: Version after rollback (target)
        success: Whether rollback succeeded
        dry_run: Whether this was a dry run
    """

    feature: str
    version_from: str
    version_to: str
    success: bool
    dry_run: bool


# =============================================================================
# Version Diff Functions
# =============================================================================


def diff_versions(
    store_root: Path,
    feature_name: str,
    version_from: str,
    version_to: str,
    read_metadata_func: Any = None,
) -> VersionDiff:
    """
    Compare two versions of a feature.

    Args:
        store_root: Root path of the feature store
        feature_name: Name of the feature to compare
        version_from: First version to compare
        version_to: Second version to compare
        read_metadata_func: Function to read metadata (for testing)

    Returns:
        VersionDiff containing schema, config, and data differences

    Raises:
        VersionNotFoundError: If either version doesn't exist
    """
    import mlforge.errors as errors
    import mlforge.manifest as manifest

    read_meta = read_metadata_func or manifest.read_metadata_file

    # Read metadata for both versions
    meta_from_path = versioned_metadata_path(
        store_root, feature_name, version_from
    )
    meta_to_path = versioned_metadata_path(store_root, feature_name, version_to)

    meta_from = read_meta(meta_from_path)
    if meta_from is None:
        available = list_versions(store_root, feature_name)
        raise errors.VersionNotFoundError(feature_name, version_from, available)

    meta_to = read_meta(meta_to_path)
    if meta_to is None:
        available = list_versions(store_root, feature_name)
        raise errors.VersionNotFoundError(feature_name, version_to, available)

    # Build column maps for comparison
    cols_from = {
        c.name: c.dtype or "" for c in meta_from.columns + meta_from.features
    }
    cols_to = {
        c.name: c.dtype or "" for c in meta_to.columns + meta_to.features
    }

    # Determine schema changes
    added_names = set(cols_to.keys()) - set(cols_from.keys())
    removed_names = set(cols_from.keys()) - set(cols_to.keys())
    common_names = set(cols_from.keys()) & set(cols_to.keys())

    added = [ColumnInfo(name=n, dtype=cols_to[n]) for n in sorted(added_names)]
    removed = [
        ColumnInfo(name=n, dtype=cols_from[n]) for n in sorted(removed_names)
    ]
    modified = [
        ColumnModification(name=n, dtype_from=cols_from[n], dtype_to=cols_to[n])
        for n in sorted(common_names)
        if cols_from[n] != cols_to[n]
    ]

    schema_changes = SchemaChanges(
        added=added, removed=removed, modified=modified
    )

    # Determine config changes
    config_changes: list[ConfigChange] = []
    if meta_from.interval != meta_to.interval:
        config_changes.append(
            ConfigChange(
                key="interval",
                value_from=meta_from.interval,
                value_to=meta_to.interval,
            )
        )
    if meta_from.timestamp != meta_to.timestamp:
        config_changes.append(
            ConfigChange(
                key="timestamp",
                value_from=meta_from.timestamp,
                value_to=meta_to.timestamp,
            )
        )
    if meta_from.keys != meta_to.keys:
        config_changes.append(
            ConfigChange(
                key="keys",
                value_from=meta_from.keys,
                value_to=meta_to.keys,
            )
        )

    # Determine change type
    if removed or modified:
        change_type = ChangeType.MAJOR
    elif added:
        change_type = ChangeType.MINOR
    elif config_changes:
        change_type = ChangeType.MINOR
    elif meta_from.content_hash != meta_to.content_hash:
        change_type = ChangeType.PATCH
    else:
        # No differences - same version essentially
        change_type = ChangeType.PATCH

    # Build data statistics
    data_stats = DataStatistics(
        row_count_from=meta_from.row_count,
        row_count_to=meta_to.row_count,
    )

    return VersionDiff(
        feature=feature_name,
        version_from=version_from,
        version_to=version_to,
        change_type=change_type,
        schema_changes=schema_changes,
        config_changes=config_changes,
        data_statistics=data_stats,
    )


def get_previous_version(store_root: Path, feature_name: str) -> str | None:
    """
    Get the version before the latest.

    Args:
        store_root: Root path of the feature store
        feature_name: Name of the feature

    Returns:
        Previous version string, or None if less than 2 versions exist
    """
    versions = list_versions(store_root, feature_name)
    if len(versions) < 2:
        return None
    return versions[-2]


def rollback_version(
    store_root: Path,
    feature_name: str,
    target_version: str,
    dry_run: bool = False,
) -> RollbackResult:
    """
    Rollback a feature to a previous version.

    Updates _latest.json to point to the target version.
    Does NOT delete any version data.

    Args:
        store_root: Root path of the feature store
        feature_name: Name of the feature to rollback
        target_version: Version to rollback to
        dry_run: If True, don't make changes

    Returns:
        RollbackResult with details of the operation

    Raises:
        VersionNotFoundError: If target version doesn't exist
        AlreadyAtVersionError: If already at target version
    """
    import mlforge.errors as errors

    # Check target version exists
    available = list_versions(store_root, feature_name)
    if target_version not in available:
        raise errors.VersionNotFoundError(
            feature_name, target_version, available
        )

    # Check not already at target version
    current = get_latest_version(store_root, feature_name)
    if current == target_version:
        raise errors.AlreadyAtVersionError(feature_name, target_version)

    # Perform rollback (update _latest.json)
    if not dry_run:
        write_latest_pointer(store_root, feature_name, target_version)

    return RollbackResult(
        feature=feature_name,
        version_from=current or "unknown",
        version_to=target_version,
        success=True,
        dry_run=dry_run,
    )


# =============================================================================
# Git Integration
# =============================================================================

_GITIGNORE_CONTENT = """\
# Auto-generated by mlforge
# Data files are rebuilt from source; commit .meta.json and _latest.json only
*/data.parquet
"""


def write_feature_gitignore(store_root: Path, feature_name: str) -> bool:
    """
    Write .gitignore to feature directory if not already present.

    Creates a .gitignore file that ignores data.parquet files in version
    subdirectories. This allows committing metadata (.meta.json, _latest.json)
    while excluding large data files that can be rebuilt from source.

    Args:
        store_root: Root path of the feature store
        feature_name: Name of the feature

    Returns:
        True if .gitignore was created, False if it already existed
    """
    feature_dir = feature_versions_dir(store_root, feature_name)
    gitignore_path = feature_dir / ".gitignore"

    if gitignore_path.exists():
        return False

    feature_dir.mkdir(parents=True, exist_ok=True)
    gitignore_path.write_text(_GITIGNORE_CONTENT)
    return True
