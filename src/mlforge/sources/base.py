"""
Source class for data source abstraction.

The Source class provides a unified interface for specifying data sources with
automatic location inference (local, S3, GCS) and format detection (Parquet, CSV, Delta).

Design principles:
- Location inferred from path prefix (s3://, gs://, or local)
- Format auto-detected from file extension
- Simple common case: Source("path.parquet") just works
- Typed format options for IDE autocomplete

Usage:
    import mlforge as mlf

    # Simple case - auto-detect everything
    transactions = mlf.Source("data/transactions.parquet")

    # S3 source
    s3_transactions = mlf.Source("s3://bucket/transactions.parquet")

    # GCS source
    gcs_transactions = mlf.Source("gs://bucket/transactions.parquet")

    # CSV with format options
    csv_events = mlf.Source(
        path="data/events.csv",
        format=mlf.CSVFormat(delimiter="|", has_header=True),
    )
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from mlforge.sources.formats import (
    CSVFormat,
    DeltaFormat,
    Format,
    ParquetFormat,
)


# Valid location types
Location = Literal["local", "s3", "gcs"]


def _infer_location(path: str) -> Location:
    """
    Infer storage location from path prefix.

    Args:
        path: File or directory path

    Returns:
        Location type: "local", "s3", or "gcs"
    """
    if path.startswith("s3://"):
        return "s3"
    elif path.startswith("gs://"):
        return "gcs"
    return "local"


def _infer_name(path: str) -> str:
    """
    Infer source name from path stem.

    Args:
        path: File or directory path

    Returns:
        Name derived from path (e.g., "transactions" from "data/transactions.parquet")
    """
    # Handle cloud paths by extracting the last segment
    if path.startswith("s3://") or path.startswith("gs://"):
        # Remove trailing slash and get last segment
        clean_path = path.rstrip("/")
        last_segment = clean_path.split("/")[-1]
        # Remove extension if present
        return Path(last_segment).stem

    return Path(path).stem


def _detect_format(path: str) -> Format:
    """
    Auto-detect format from file extension.

    Args:
        path: File path with extension

    Returns:
        Appropriate Format instance

    Raises:
        ValueError: If format cannot be determined from extension
    """
    # Handle trailing slashes (common for Delta tables)
    clean_path = path.rstrip("/")
    ext = Path(clean_path).suffix.lower()

    match ext:
        case ".parquet":
            return ParquetFormat()
        case ".csv":
            return CSVFormat()
        case "":
            # No extension - could be Delta table directory
            # Default to DeltaFormat for directories
            return DeltaFormat()
        case _:
            msg = (
                f"Cannot auto-detect format for extension '{ext}'. "
                f"Use format parameter to specify explicitly "
                f"(e.g., format=ParquetFormat() or format=CSVFormat())."
            )
            raise ValueError(msg)


@dataclass(frozen=True)
class Source:
    """
    Data source with location and format auto-detection.

    The Source class simplifies data source configuration by:
    - Inferring storage location from path prefix (s3://, gs://, local)
    - Auto-detecting format from file extension (.parquet, .csv)
    - Providing typed format options for IDE autocomplete

    Attributes:
        path: File or directory path (local, s3://, or gs://)
        name: Optional name (auto-derived from path stem if not provided)
        format: Optional format configuration (auto-detected if not provided)

    Example:
        # Simple case - everything auto-detected
        source = Source("data/transactions.parquet")
        assert source.location == "local"
        assert source.name == "transactions"
        assert source.format == ParquetFormat()

        # S3 with explicit name
        source = Source("s3://bucket/data.parquet", name="my_data")

        # CSV with format options
        source = Source(
            path="data/events.csv",
            format=CSVFormat(delimiter="|"),
        )
    """

    path: str
    name: str = field(default="")
    format: Format | None = field(default=None)

    def __post_init__(self) -> None:
        """Auto-detect name and format if not provided."""
        # Use object.__setattr__ because dataclass is frozen
        if not self.name:
            object.__setattr__(self, "name", _infer_name(self.path))

        # Auto-detect format only if not explicitly provided
        if self.format is None:
            object.__setattr__(self, "format", _detect_format(self.path))

    @property
    def location(self) -> Location:
        """
        Storage location inferred from path.

        Returns:
            "local", "s3", or "gcs"
        """
        return _infer_location(self.path)

    @property
    def is_local(self) -> bool:
        """Check if source is local filesystem."""
        return self.location == "local"

    @property
    def is_s3(self) -> bool:
        """Check if source is Amazon S3."""
        return self.location == "s3"

    @property
    def is_gcs(self) -> bool:
        """Check if source is Google Cloud Storage."""
        return self.location == "gcs"

    @property
    def is_parquet(self) -> bool:
        """Check if source format is Parquet."""
        return isinstance(self.format, ParquetFormat)

    @property
    def is_csv(self) -> bool:
        """Check if source format is CSV."""
        return isinstance(self.format, CSVFormat)

    @property
    def is_delta(self) -> bool:
        """Check if source format is Delta Lake."""
        return isinstance(self.format, DeltaFormat)
