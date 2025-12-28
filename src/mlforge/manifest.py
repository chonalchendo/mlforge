"""
Manifest module for feature metadata tracking.

Provides dataclasses for storing feature metadata and utilities for
reading/writing metadata files. Per-feature .meta.json files are written
during build, with an optional consolidated manifest.json.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from mlforge.core import Feature


@dataclass
class ColumnMetadata:
    """
    Metadata for a single column in a feature.

    For columns derived from Rolling metrics, captures the source column,
    aggregation type, and window size. For other columns, captures dtype.
    For base columns, captures validator information.

    Attributes:
        name: Column name in the output
        dtype: Data type string (e.g., "Int64", "Float64")
        input: Source column name for aggregations
        agg: Aggregation type (count, mean, sum, etc.)
        window: Time window for rolling aggregations (e.g., "7d")
        validators: List of validator specifications applied to this column
    """

    name: str
    dtype: str | None = None
    input: str | None = None
    agg: str | None = None
    window: str | None = None
    validators: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ColumnMetadata:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            dtype=data.get("dtype"),
            input=data.get("input"),
            agg=data.get("agg"),
            window=data.get("window"),
            validators=data.get("validators"),
        )


@dataclass
class FeatureMetadata:
    """
    Metadata for a single materialized feature.

    Captures all information about a feature from both its definition
    and the results of building it.

    Attributes:
        name: Feature identifier
        path: Storage path for the parquet file
        entity: Primary entity key (first key in keys list)
        keys: All entity key columns
        source: Source data file path
        row_count: Number of rows in materialized feature
        last_updated: ISO 8601 timestamp of last build
        timestamp: Timestamp column for temporal features
        interval: Time interval for rolling aggregations
        columns: Base column metadata (from feature function before metrics)
        features: Generated feature column metadata (from metrics)
        tags: Feature grouping tags
        description: Human-readable description
    """

    name: str
    path: str
    entity: str
    keys: list[str]
    source: str
    row_count: int
    last_updated: str
    timestamp: str | None = None
    interval: str | None = None
    columns: list[ColumnMetadata] = field(default_factory=list)
    features: list[ColumnMetadata] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "name": self.name,
            "path": self.path,
            "entity": self.entity,
            "keys": self.keys,
            "source": self.source,
            "row_count": self.row_count,
            "last_updated": self.last_updated,
        }
        if self.timestamp:
            result["timestamp"] = self.timestamp
        if self.interval:
            result["interval"] = self.interval
        if self.columns:
            result["columns"] = [col.to_dict() for col in self.columns]
        if self.features:
            result["features"] = [col.to_dict() for col in self.features]
        if self.tags:
            result["tags"] = self.tags
        if self.description:
            result["description"] = self.description
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureMetadata:
        """Create from dictionary."""
        columns = [ColumnMetadata.from_dict(c) for c in data.get("columns", [])]
        features = [ColumnMetadata.from_dict(c) for c in data.get("features", [])]
        return cls(
            name=data["name"],
            path=data["path"],
            entity=data["entity"],
            keys=data["keys"],
            source=data["source"],
            row_count=data["row_count"],
            last_updated=data["last_updated"],
            timestamp=data.get("timestamp"),
            interval=data.get("interval"),
            columns=columns,
            features=features,
            tags=data.get("tags", []),
            description=data.get("description"),
        )


@dataclass
class Manifest:
    """
    Consolidated manifest containing all feature metadata.

    Aggregates individual feature metadata into a single view.
    Generated on demand from per-feature .meta.json files.

    Attributes:
        version: Schema version for compatibility
        generated_at: ISO 8601 timestamp when manifest was generated
        features: Mapping of feature names to their metadata
    """

    version: str = "1.0"
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    features: dict[str, FeatureMetadata] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "features": {name: meta.to_dict() for name, meta in self.features.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Manifest:
        """Create from dictionary."""
        features = {
            name: FeatureMetadata.from_dict(meta)
            for name, meta in data.get("features", {}).items()
        }
        return cls(
            version=data.get("version", "1.0"),
            generated_at=data.get("generated_at", ""),
            features=features,
        )

    def add_feature(self, metadata: FeatureMetadata) -> None:
        """Add or update a feature in the manifest."""
        self.features[metadata.name] = metadata

    def remove_feature(self, name: str) -> None:
        """Remove a feature from the manifest."""
        self.features.pop(name, None)

    def get_feature(self, name: str) -> FeatureMetadata | None:
        """Get metadata for a specific feature."""
        return self.features.get(name)


# Regex pattern to parse Rolling column names: {tag}__{column}__{agg}__{interval}__{window}
_ROLLING_COLUMN_PATTERN = re.compile(r"^(.+)__(\w+)__(\d+[dhmsw])__(\d+[dhmsw])$")

# Regex pattern to parse validator names with parameters
_VALIDATOR_PATTERN = re.compile(r"^(\w+)(?:\((.*)\))?$")


def _parse_validator_name(validator_name: str) -> dict[str, Any]:
    """
    Parse validator name into structured format.

    Converts validator names like "greater_than_or_equal(0)" into
    structured dictionaries like {"validator": "greater_than_or_equal", "value": 0}.

    Args:
        validator_name: Validator name string (e.g., "not_null" or "greater_than(5)")

    Returns:
        Dictionary with validator name and parameters

    Examples:
        >>> _parse_validator_name("not_null")
        {"validator": "not_null"}
        >>> _parse_validator_name("greater_than_or_equal(0)")
        {"validator": "greater_than_or_equal", "value": 0}
    """
    match = _VALIDATOR_PATTERN.match(validator_name)
    if not match:
        return {"validator": validator_name}

    name, params_str = match.groups()
    result: dict[str, Any] = {"validator": name}

    if not params_str:
        return result

    # Parse parameters based on validator type
    params_str = params_str.strip()

    # Handle numeric parameters
    if name in {
        "greater_than",
        "less_than",
        "greater_than_or_equal",
        "less_than_or_equal",
    }:
        try:
            # Try to parse as int first, then float
            result["value"] = (
                int(params_str) if "." not in params_str else float(params_str)
            )
        except ValueError:
            result["value"] = params_str

    # Handle range parameters
    elif name == "in_range":
        parts = [p.strip() for p in params_str.split(",")]
        if len(parts) >= 2:
            try:
                result["min"] = (
                    int(parts[0]) if "." not in parts[0] else float(parts[0])
                )
                result["max"] = (
                    int(parts[1]) if "." not in parts[1] else float(parts[1])
                )
            except ValueError:
                result["params"] = params_str

    # Handle string parameters (regex, is_in)
    elif name == "matches_regex":
        # Remove quotes if present
        result["pattern"] = params_str.strip("'\"")

    else:
        # For unknown validators, just store the raw parameter string
        result["params"] = params_str

    return result


def _derive_with_base_schema(
    feature: Feature,
    schema: dict[str, str],
    base_schema: dict[str, str],
) -> tuple[list[ColumnMetadata], list[ColumnMetadata]]:
    """
    Derive column metadata when base schema is available (recommended path).

    Uses base_schema to accurately separate base columns from generated feature columns.
    This is the preferred method as it doesn't rely on regex pattern matching.

    Args:
        feature: The Feature definition object
        schema: Final schema after metrics are applied
        base_schema: Schema before metrics were applied

    Returns:
        Tuple of (base_columns, feature_columns)
    """
    base_columns: list[ColumnMetadata] = []
    feature_columns: list[ColumnMetadata] = []

    # Add all base columns from base_schema
    for col_name, dtype in base_schema.items():
        # Check if this column has validators and parse them
        validator_specs = None
        if feature.validators and col_name in feature.validators:
            validator_specs = [
                _parse_validator_name(v.name) for v in feature.validators[col_name]
            ]

        base_columns.append(
            ColumnMetadata(name=col_name, dtype=dtype, validators=validator_specs)
        )

    # Add generated feature columns from final schema (only columns not in base_schema)
    for col_name, dtype in schema.items():
        # Skip if this is a base column
        if col_name in base_schema:
            continue

        # Try to parse as Rolling column: {tag}__{column}__{agg}__{interval}__{window}
        match = _ROLLING_COLUMN_PATTERN.match(col_name)
        if match:
            # Extract tag__column and get just the column name (last part)
            tag_and_column = match.group(1)
            input_col = tag_and_column.split("__")[-1]

            feature_columns.append(
                ColumnMetadata(
                    name=col_name,
                    dtype=dtype,
                    input=input_col,
                    agg=match.group(2),
                    window=match.group(4),
                )
            )

    return base_columns, feature_columns


def _derive_legacy(
    feature: Feature,
    schema: dict[str, str],
) -> tuple[list[ColumnMetadata], list[ColumnMetadata]]:
    """
    Derive column metadata without base schema (legacy path for backward compatibility).

    Uses regex pattern matching to categorize columns as base vs feature columns.
    Less accurate than _derive_with_base_schema but maintains backward compatibility.

    Args:
        feature: The Feature definition object
        schema: Final schema (only available schema)

    Returns:
        Tuple of (base_columns, feature_columns)
    """
    base_columns: list[ColumnMetadata] = []
    feature_columns: list[ColumnMetadata] = []

    # Process all columns from schema and categorize them
    for col_name, dtype in schema.items():
        # Check if this column has validators and parse them
        validator_specs = None
        if feature.validators and col_name in feature.validators:
            validator_specs = [
                _parse_validator_name(v.name) for v in feature.validators[col_name]
            ]

        # Try to parse as Rolling column: {tag}__{column}__{agg}__{interval}__{window}
        match = _ROLLING_COLUMN_PATTERN.match(col_name)
        if match:
            # Extract tag__column and get just the column name (last part)
            tag_and_column = match.group(1)
            input_col = tag_and_column.split("__")[-1]

            feature_columns.append(
                ColumnMetadata(
                    name=col_name,
                    dtype=dtype,
                    input=input_col,
                    agg=match.group(2),
                    window=match.group(4),
                    validators=validator_specs,
                )
            )
        else:
            # Not a rolling column, so it's a base column
            base_columns.append(
                ColumnMetadata(name=col_name, dtype=dtype, validators=validator_specs)
            )

    return base_columns, feature_columns


def derive_column_metadata(
    feature: Feature,
    schema: dict[str, str],
    base_schema: dict[str, str] | None = None,
) -> tuple[list[ColumnMetadata], list[ColumnMetadata]]:
    """
    Derive column metadata from feature definition and result schema.

    Separates base columns (keys, timestamp, other non-metric columns) from
    generated feature columns (rolling metrics). Uses base_schema when available
    for accurate separation, falls back to regex parsing for backward compatibility.

    Args:
        feature: The Feature definition object
        schema: Dictionary mapping column names to dtype strings (final schema after metrics)
        base_schema: Dictionary mapping column names to dtype strings (before metrics).
            When provided, enables accurate column separation. Defaults to None.

    Returns:
        Tuple of (base_columns, feature_columns) where:
            - base_columns: Keys, timestamp, and other non-metric columns with validators
            - feature_columns: Rolling metric columns with aggregation metadata
    """
    if base_schema:
        return _derive_with_base_schema(feature, schema, base_schema)
    return _derive_legacy(feature, schema)


def _get_rolling_output_columns(feature: Feature) -> set[str]:
    """Get all expected output columns from Rolling metrics."""
    columns: set[str] = set()
    if not feature.metrics:
        return columns

    for metric in feature.metrics:
        # Currently only Rolling is supported
        if hasattr(metric, "output_columns"):
            columns.update(metric.output_columns())
    return columns


def write_metadata_file(path: Path, metadata: FeatureMetadata) -> None:
    """
    Write feature metadata to a JSON file.

    Args:
        path: Path to write the .meta.json file
        metadata: FeatureMetadata to serialize
    """
    with open(path, "w") as f:
        json.dump(metadata.to_dict(), f, indent=2)


def read_metadata_file(path: Path) -> FeatureMetadata | None:
    """
    Read feature metadata from a JSON file.

    Args:
        path: Path to the .meta.json file

    Returns:
        FeatureMetadata if file exists and is valid, None otherwise
    """
    if not path.exists():
        return None

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in {path}: {e}")
        return None

    try:
        return FeatureMetadata.from_dict(data)
    except KeyError as e:
        logger.warning(f"Schema mismatch in {path}: missing key {e}")
        return None


def write_manifest_file(path: Path | str, manifest: Manifest) -> None:
    """
    Write consolidated manifest to a JSON file.

    Args:
        path: Path to write the manifest.json file
        manifest: Manifest to serialize
    """
    with open(path, "w") as f:
        json.dump(manifest.to_dict(), f, indent=2)


def read_manifest_file(path: Path) -> Manifest | None:
    """
    Read consolidated manifest from a JSON file.

    Args:
        path: Path to the manifest.json file

    Returns:
        Manifest if file exists and is valid, None otherwise
    """
    if not path.exists():
        return None

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in {path}: {e}")
        return None

    try:
        return Manifest.from_dict(data)
    except KeyError as e:
        logger.warning(f"Schema mismatch in {path}: missing key {e}")
        return None
