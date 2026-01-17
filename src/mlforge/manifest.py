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

import mlforge.types as types_

if TYPE_CHECKING:
    from mlforge.core import Feature


@dataclass
class IncrementalMetadata:
    """
    Metadata for incremental build state tracking.

    Tracks when data was last processed to enable incremental builds
    that only process new data since the last build.

    Attributes:
        last_build_at: ISO 8601 timestamp when the incremental build ran
        processed_until: ISO 8601 timestamp of the latest data processed
        timestamp_column: Name of the timestamp column used for filtering
        lookback_days: Number of days to look back for rolling window features
    """

    last_build_at: str
    processed_until: str
    timestamp_column: str
    lookback_days: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "last_build_at": self.last_build_at,
            "processed_until": self.processed_until,
            "timestamp_column": self.timestamp_column,
            "lookback_days": self.lookback_days,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IncrementalMetadata:
        """Create from dictionary."""
        return cls(
            last_build_at=data["last_build_at"],
            processed_until=data["processed_until"],
            timestamp_column=data["timestamp_column"],
            lookback_days=data.get("lookback_days", 0),
        )


@dataclass
class ColumnMetadata:
    """
    Metadata for a single column in a feature.

    For columns derived from Aggregate metrics, captures the source column,
    aggregation type, window size, and optional description/unit.
    For other columns, captures dtype.
    For base columns, captures validator information.

    Attributes:
        name: Column name in the output
        dtype: Data type string (e.g., "Int64", "Float64")
        input: Source column name for aggregations
        agg: Aggregation type (count, mean, sum, etc.)
        window: Time window for rolling aggregations (e.g., "7d")
        description: Human-readable description of what this metric represents
        unit: Unit of measurement (e.g., "USD", "count", "transactions")
        validators: List of validator specifications applied to this column
    """

    name: str
    dtype: str | None = None
    input: str | None = None
    agg: str | None = None
    window: str | None = None
    description: str | None = None
    unit: str | None = None
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
            description=data.get("description"),
            unit=data.get("unit"),
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
        updated_at: ISO 8601 timestamp of last build (renamed from last_updated in v0.5.0)
        version: Semantic version string (v0.5.0)
        created_at: ISO 8601 timestamp when version was first created (v0.5.0)
        content_hash: Hash of data.parquet for integrity verification (v0.5.0)
        schema_hash: Hash of column names + dtypes for change detection (v0.5.0)
        config_hash: Hash of keys, timestamp, interval, metrics config (v0.5.0)
        source_hash: Hash of source data file for reproducibility verification (v0.5.0)
        timestamp: Timestamp column for temporal features
        interval: Time interval for rolling aggregations
        columns: Base column metadata (from feature function before metrics)
        features: Generated feature column metadata (from metrics)
        tags: Feature grouping tags
        description: Human-readable description
        change_summary: Documents why version was bumped (v0.5.0)
    """

    name: str
    path: str
    entity: str
    keys: list[str]
    source: str
    row_count: int
    updated_at: str

    # v0.5.0: New required fields for versioning
    version: str = "1.0.0"
    created_at: str = ""
    content_hash: str = ""
    schema_hash: str = ""
    config_hash: str = ""
    source_hash: str = ""

    # Existing optional fields
    timestamp: str | None = None
    interval: str | None = None
    columns: list[ColumnMetadata] = field(default_factory=list)
    features: list[ColumnMetadata] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str | None = None

    # v0.5.0: New optional field
    change_summary: dict[str, Any] | None = None

    # v0.8.0: Incremental build tracking
    incremental: IncrementalMetadata | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "name": self.name,
            "version": self.version,
            "path": self.path,
            "entity": self.entity,
            "keys": self.keys,
            "source": self.source,
            "row_count": self.row_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "content_hash": self.content_hash,
            "schema_hash": self.schema_hash,
            "config_hash": self.config_hash,
            "source_hash": self.source_hash,
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
        if self.change_summary:
            result["change_summary"] = self.change_summary
        if self.incremental:
            result["incremental"] = self.incremental.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureMetadata:
        """Create from dictionary."""
        columns = [ColumnMetadata.from_dict(c) for c in data.get("columns", [])]
        features = [
            ColumnMetadata.from_dict(c) for c in data.get("features", [])
        ]

        # Handle backward compatibility: last_updated → updated_at
        updated_at = data.get("updated_at") or data.get("last_updated", "")

        # Parse incremental metadata if present
        incremental_data = data.get("incremental")
        incremental = (
            IncrementalMetadata.from_dict(incremental_data)
            if incremental_data
            else None
        )

        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            path=data["path"],
            entity=data["entity"],
            keys=data["keys"],
            source=data["source"],
            row_count=data["row_count"],
            created_at=data.get("created_at", ""),
            updated_at=updated_at,
            content_hash=data.get("content_hash", ""),
            schema_hash=data.get("schema_hash", ""),
            config_hash=data.get("config_hash", ""),
            source_hash=data.get("source_hash", ""),
            timestamp=data.get("timestamp"),
            interval=data.get("interval"),
            columns=columns,
            features=features,
            tags=data.get("tags", []),
            description=data.get("description"),
            change_summary=data.get("change_summary"),
            incremental=incremental,
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
            "features": {
                name: meta.to_dict() for name, meta in self.features.items()
            },
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


# Regex pattern to parse legacy Rolling column names: {tag}__{column}__{agg}__{interval}__{window}
_ROLLING_COLUMN_PATTERN = re.compile(
    r"^(.+)__(\w+)__(\d+[dhmsw])__(\d+[dhmsw])$"
)

# Regex patterns for new Aggregate column naming:
# Pattern 1: {name}_{interval}_{window} (when name provided)
# Pattern 2: {column}_{function}_{interval}_{window} (when no name)
# We detect aggregates by the presence of interval_window suffix pattern
_AGGREGATE_COLUMN_PATTERN = re.compile(r"^(.+)_(\d+[dhmsw])_(\d+[dhmsw])$")

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


def _build_aggregate_metadata_map(
    feature: Feature,
) -> dict[str, tuple[str, str, str | None, str | None]]:
    """
    Build a mapping from output column names to aggregate metadata.

    Args:
        feature: The Feature definition with metrics

    Returns:
        Dict mapping column name to (input_col, agg_type, description, unit)
    """
    from mlforge.aggregates import Aggregate

    result: dict[str, tuple[str, str, str | None, str | None]] = {}

    if not feature.metrics or not feature.interval:
        return result

    for metric in feature.metrics:
        if isinstance(metric, Aggregate):
            # Set interval for column name generation
            metric._interval = feature.interval
            output_cols = metric.output_columns(feature.interval)

            for col_name in output_cols:
                result[col_name] = (
                    metric.field,
                    metric.function,
                    metric.description,
                    metric.unit,
                )

    return result


def _derive_with_base_schema(
    feature: Feature,
    schema: dict[str, str],
    base_schema: dict[str, str],
    schema_source: str = "polars",
) -> tuple[list[ColumnMetadata], list[ColumnMetadata]]:
    """
    Derive column metadata when base schema is available (recommended path).

    Uses base_schema to accurately separate base columns from generated feature columns.
    This is the preferred method as it doesn't rely on regex pattern matching.

    Args:
        feature: The Feature definition object
        schema: Final schema after metrics are applied (engine-specific types)
        base_schema: Schema before metrics were applied (always Polars types,
            since user feature functions return Polars DataFrames)
        schema_source: Engine source for type normalization of final schema
            ("polars" or "duckdb")

    Returns:
        Tuple of (base_columns, feature_columns)
    """
    base_columns: list[ColumnMetadata] = []
    feature_columns: list[ColumnMetadata] = []

    # base_schema is always from Polars (user functions return Polars DataFrames)
    # Final schema uses the engine-specific converter
    final_schema_converter = (
        types_.from_polars_string
        if schema_source == "polars"
        else types_.from_duckdb
    )

    # Build mapping from column name to aggregate metadata
    aggregate_metadata = _build_aggregate_metadata_map(feature)

    # Add all base columns from base_schema (always Polars types)
    for col_name, dtype in base_schema.items():
        # Check if this column has validators and parse them
        validator_specs = None
        if feature.validators and col_name in feature.validators:
            validator_specs = [
                _parse_validator_name(v.name)
                for v in feature.validators[col_name]
            ]

        # Convert to canonical type string (base_schema is always Polars)
        canonical_dtype = types_.from_polars_string(dtype).to_canonical_string()

        base_columns.append(
            ColumnMetadata(
                name=col_name,
                dtype=canonical_dtype,
                validators=validator_specs,
            )
        )

    # Add generated feature columns from final schema (only columns not in base_schema)
    for col_name, dtype in schema.items():
        # Skip if this is a base column
        if col_name in base_schema:
            continue

        # Convert to canonical type string (use engine-specific converter)
        canonical_dtype = final_schema_converter(dtype).to_canonical_string()

        # Check if we have aggregate metadata for this column (preferred)
        if col_name in aggregate_metadata:
            input_col, agg_type, description, unit = aggregate_metadata[
                col_name
            ]
            # Extract window from column name pattern
            match = _AGGREGATE_COLUMN_PATTERN.match(col_name)
            window = match.group(3) if match else None

            feature_columns.append(
                ColumnMetadata(
                    name=col_name,
                    dtype=canonical_dtype,
                    input=input_col,
                    agg=agg_type,
                    window=window,
                    description=description,
                    unit=unit,
                )
            )
        # Fall back to legacy Rolling pattern: {tag}__{column}__{agg}__{interval}__{window}
        elif match := _ROLLING_COLUMN_PATTERN.match(col_name):
            # Extract tag__column and get just the column name (last part)
            tag_and_column = match.group(1)
            input_col = tag_and_column.split("__")[-1]

            feature_columns.append(
                ColumnMetadata(
                    name=col_name,
                    dtype=canonical_dtype,
                    input=input_col,
                    agg=match.group(2),
                    window=match.group(4),
                )
            )
        # Try new Aggregate pattern: {name}_{interval}_{window} or {col}_{agg}_{interval}_{window}
        elif match := _AGGREGATE_COLUMN_PATTERN.match(col_name):
            # Can't determine input/agg from pattern alone without aggregate metadata
            # Just store what we can parse
            feature_columns.append(
                ColumnMetadata(
                    name=col_name,
                    dtype=canonical_dtype,
                    window=match.group(3),
                )
            )

    return base_columns, feature_columns


def _derive_legacy(
    feature: Feature,
    schema: dict[str, str],
    schema_source: str = "polars",
) -> tuple[list[ColumnMetadata], list[ColumnMetadata]]:
    """
    Derive column metadata without base schema (legacy path for backward compatibility).

    Uses regex pattern matching to categorize columns as base vs feature columns.
    Less accurate than _derive_with_base_schema but maintains backward compatibility.

    Args:
        feature: The Feature definition object
        schema: Final schema (only available schema)
        schema_source: Engine source for type normalization ("polars" or "duckdb")

    Returns:
        Tuple of (base_columns, feature_columns)
    """
    base_columns: list[ColumnMetadata] = []
    feature_columns: list[ColumnMetadata] = []

    # Normalize types based on engine source
    converter = (
        types_.from_polars_string
        if schema_source == "polars"
        else types_.from_duckdb
    )

    # Build mapping from column name to aggregate metadata
    aggregate_metadata = _build_aggregate_metadata_map(feature)

    # Process all columns from schema and categorize them
    for col_name, dtype in schema.items():
        # Check if this column has validators and parse them
        validator_specs = None
        if feature.validators and col_name in feature.validators:
            validator_specs = [
                _parse_validator_name(v.name)
                for v in feature.validators[col_name]
            ]

        # Convert to canonical type string
        canonical_dtype = converter(dtype).to_canonical_string()

        # Check if we have aggregate metadata for this column (preferred)
        if col_name in aggregate_metadata:
            input_col, agg_type, description, unit = aggregate_metadata[
                col_name
            ]
            # Extract window from column name pattern
            match = _AGGREGATE_COLUMN_PATTERN.match(col_name)
            window = match.group(3) if match else None

            feature_columns.append(
                ColumnMetadata(
                    name=col_name,
                    dtype=canonical_dtype,
                    input=input_col,
                    agg=agg_type,
                    window=window,
                    description=description,
                    unit=unit,
                    validators=validator_specs,
                )
            )
        # Try to parse as legacy Rolling column: {tag}__{column}__{agg}__{interval}__{window}
        elif match := _ROLLING_COLUMN_PATTERN.match(col_name):
            # Extract tag__column and get just the column name (last part)
            tag_and_column = match.group(1)
            input_col = tag_and_column.split("__")[-1]

            feature_columns.append(
                ColumnMetadata(
                    name=col_name,
                    dtype=canonical_dtype,
                    input=input_col,
                    agg=match.group(2),
                    window=match.group(4),
                    validators=validator_specs,
                )
            )
        # Try new Aggregate pattern: {name}_{interval}_{window}
        elif match := _AGGREGATE_COLUMN_PATTERN.match(col_name):
            # Can't determine input/agg from pattern alone without aggregate metadata
            feature_columns.append(
                ColumnMetadata(
                    name=col_name,
                    dtype=canonical_dtype,
                    window=match.group(3),
                    validators=validator_specs,
                )
            )
        else:
            # Not a metric column, so it's a base column
            base_columns.append(
                ColumnMetadata(
                    name=col_name,
                    dtype=canonical_dtype,
                    validators=validator_specs,
                )
            )

    return base_columns, feature_columns


def derive_column_metadata(
    feature: Feature,
    schema: dict[str, str],
    base_schema: dict[str, str] | None = None,
    schema_source: str = "polars",
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
        schema_source: Engine source for type normalization ("polars" or "duckdb")

    Returns:
        Tuple of (base_columns, feature_columns) where:
            - base_columns: Keys, timestamp, and other non-metric columns with validators
            - feature_columns: Rolling metric columns with aggregation metadata
    """
    if base_schema:
        return _derive_with_base_schema(
            feature, schema, base_schema, schema_source
        )
    return _derive_legacy(feature, schema, schema_source)


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
