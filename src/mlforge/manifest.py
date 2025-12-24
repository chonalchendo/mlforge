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

if TYPE_CHECKING:
    from mlforge.core import Feature


@dataclass
class ColumnMetadata:
    """
    Metadata for a single column in a feature.

    For columns derived from Rolling metrics, captures the source column,
    aggregation type, and window size. For other columns, captures dtype.

    Attributes:
        name: Column name in the output
        dtype: Data type string (e.g., "Int64", "Float64")
        input: Source column name for aggregations
        agg: Aggregation type (count, mean, sum, etc.)
        window: Time window for rolling aggregations (e.g., "7d")
    """

    name: str
    dtype: str | None = None
    input: str | None = None
    agg: str | None = None
    window: str | None = None

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
        columns: List of column metadata
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
        if self.tags:
            result["tags"] = self.tags
        if self.description:
            result["description"] = self.description
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureMetadata:
        """Create from dictionary."""
        columns = [ColumnMetadata.from_dict(c) for c in data.get("columns", [])]
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


def derive_column_metadata(
    feature: Feature,
    schema: dict[str, str],
) -> list[ColumnMetadata]:
    """
    Derive column metadata from feature definition and result schema.

    For features with Rolling metrics, parses column names to extract
    the input column, aggregation type, and window size. For other
    features, captures basic dtype information.

    Args:
        feature: The Feature definition object
        schema: Dictionary mapping column names to dtype strings

    Returns:
        List of ColumnMetadata for each column in the schema
    """
    columns: list[ColumnMetadata] = []

    for col_name, dtype in schema.items():
        # Skip key and timestamp columns from detailed parsing
        if col_name in feature.keys:
            columns.append(ColumnMetadata(name=col_name, dtype=dtype))
            continue
        if feature.timestamp and col_name == feature.timestamp:
            columns.append(ColumnMetadata(name=col_name, dtype=dtype))
            continue

        # Try to parse as Rolling column: {tag}__{column}__{agg}__{interval}__{window}
        match = _ROLLING_COLUMN_PATTERN.match(col_name)
        if match:
            # Extract tag__column and get just the column name (last part)
            tag_and_column = match.group(1)
            input_col = tag_and_column.split("__")[-1]

            columns.append(
                ColumnMetadata(
                    name=col_name,
                    dtype=dtype,
                    input=input_col,
                    agg=match.group(2),
                    window=match.group(4),  # Window is now the 4th group
                )
            )
            continue

        # Default: just dtype info
        columns.append(ColumnMetadata(name=col_name, dtype=dtype))

    return columns


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
        return FeatureMetadata.from_dict(data)
    except (json.JSONDecodeError, KeyError):
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
        return Manifest.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None
