"""
Google Cloud Storage backend.

Stores features in versioned directories within a GCS bucket as Parquet files.
"""

import json
from typing import Any, override

import polars as pl
from loguru import logger

import mlforge.manifest as manifest
import mlforge.results as results
import mlforge.version as version
from mlforge.stores.base import Store


class GCSStore(Store):
    """
    Google Cloud Storage backend using Parquet format.

    Stores features in versioned directories within a GCS bucket:
        gs://bucket/prefix/
        ├── user_spend/
        │   ├── 1.0.0/
        │   │   ├── data.parquet
        │   │   └── .meta.json
        │   ├── 1.1.0/
        │   │   └── ...
        │   └── _latest.json

    Uses GCP credentials from standard resolution:
    1. GOOGLE_APPLICATION_CREDENTIALS environment variable
    2. Application Default Credentials (ADC)
    3. Service account attached to compute instance

    Attributes:
        bucket: GCS bucket name for storing features
        prefix: Optional path prefix within the bucket

    Example:
        store = GCSStore(bucket="mlforge-features", prefix="prod/features")
        store.write("user_age", result, version="1.0.0")
        age_df = store.read("user_age")  # reads latest
    """

    def __init__(self, bucket: str, prefix: str = "") -> None:
        """
        Initialize GCS storage backend.

        Args:
            bucket: GCS bucket name for feature storage
            prefix: Path prefix within bucket. Defaults to empty string.

        Raises:
            ValueError: If bucket doesn't exist or is not accessible
        """
        try:
            import gcsfs  # type: ignore[import-not-found]
        except ImportError as e:
            raise ImportError(
                "gcsfs is required for GCSStore. "
                "Install it with: pip install mlforge[gcs]"
            ) from e

        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self._gcs = gcsfs.GCSFileSystem()

        if not self._gcs.exists(self.bucket):
            raise ValueError(
                f"Bucket '{self.bucket}' does not exist or is not accessible. "
                f"Ensure the bucket is created and credentials have appropriate permissions."
            )

    def _base_path(self) -> str:
        """Get base GCS path (bucket/prefix)."""
        if self.prefix:
            return f"gs://{self.bucket}/{self.prefix}"
        return f"gs://{self.bucket}"

    def _versioned_data_path(
        self, feature_name: str, feature_version: str
    ) -> str:
        """Get GCS path for versioned feature data."""
        return (
            f"{self._base_path()}/{feature_name}/{feature_version}/data.parquet"
        )

    def _versioned_metadata_path(
        self, feature_name: str, feature_version: str
    ) -> str:
        """Get GCS path for versioned feature metadata."""
        return (
            f"{self._base_path()}/{feature_name}/{feature_version}/.meta.json"
        )

    def _latest_pointer_path(self, feature_name: str) -> str:
        """Get GCS path for _latest.json pointer."""
        return f"{self._base_path()}/{feature_name}/_latest.json"

    def _feature_dir_path(self, feature_name: str) -> str:
        """Get GCS path for feature directory."""
        return f"{self._base_path()}/{feature_name}"

    def _write_latest_pointer(
        self, feature_name: str, feature_version: str
    ) -> None:
        """Write _latest.json pointer to GCS."""
        path = self._latest_pointer_path(feature_name)
        with self._gcs.open(path, "w") as f:
            json.dump({"version": feature_version}, f, indent=2)

    def _read_latest_pointer(self, feature_name: str) -> str | None:
        """Read _latest.json pointer from GCS."""
        path = self._latest_pointer_path(feature_name)
        if not self._gcs.exists(path):
            return None

        try:
            with self._gcs.open(path, "r") as f:
                data = json.load(f)
            return data.get("version")
        except (json.JSONDecodeError, KeyError):
            return None

    @override
    def list_versions(self, feature_name: str) -> list[str]:
        """
        List all versions of a feature in GCS.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Sorted list of version strings (oldest to newest)
        """
        feature_dir = self._feature_dir_path(feature_name)

        # Remove gs:// prefix for ls
        feature_dir_key = feature_dir.replace("gs://", "")

        try:
            items = self._gcs.ls(feature_dir_key, detail=False)
        except FileNotFoundError:
            return []

        versions = []
        for item in items:
            name = item.split("/")[-1]
            if version.is_valid_version(name):
                versions.append(name)

        return version.sort_versions(versions)

    @override
    def get_latest_version(self, feature_name: str) -> str | None:
        """
        Get the latest version of a feature from GCS.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Latest version string, or None if no versions exist
        """
        return self._read_latest_pointer(feature_name)

    def _resolve_version(
        self, feature_name: str, feature_version: str | None
    ) -> str | None:
        """Resolve version to latest if None."""
        if feature_version is not None:
            return feature_version
        return self.get_latest_version(feature_name)

    @override
    def path_for(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> str:
        """
        Get GCS URI for a feature version.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version. If None, uses latest.

        Returns:
            GCS URI where the feature is or would be stored
        """
        resolved = self._resolve_version(feature_name, feature_version)

        if resolved is None:
            return self._versioned_data_path(feature_name, "1.0.0")

        return self._versioned_data_path(feature_name, resolved)

    @override
    def write(
        self,
        feature_name: str,
        result: results.ResultKind,
        feature_version: str,
    ) -> dict[str, Any]:
        """
        Write feature data to versioned GCS parquet file.

        Args:
            feature_name: Unique identifier for the feature
            result: Engine result containing feature data and metadata
            feature_version: Semantic version string (e.g., "1.0.0")

        Returns:
            Metadata dictionary with GCS URI, row count, and schema
        """
        path = self._versioned_data_path(feature_name, feature_version)
        result.write_parquet(path)

        # Update _latest.json pointer
        self._write_latest_pointer(feature_name, feature_version)

        return {
            "path": path,
            "row_count": result.row_count(),
            "schema": result.schema(),
        }

    @override
    def read(
        self,
        feature_name: str,
        feature_version: str | None = None,
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        """
        Read feature data from versioned GCS parquet file.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version to read. If None, reads latest.
            columns: Specific columns to read. If None, reads all columns.

        Returns:
            Feature data as a DataFrame

        Raises:
            FileNotFoundError: If the feature/version doesn't exist
        """
        resolved = self._resolve_version(feature_name, feature_version)

        if resolved is None:
            raise FileNotFoundError(
                f"Feature '{feature_name}' not found. Run 'mlforge build' first."
            )

        path = self._versioned_data_path(feature_name, resolved)

        if not self._gcs.exists(path):
            raise FileNotFoundError(
                f"Feature '{feature_name}' version '{resolved}' not found."
            )

        return pl.read_parquet(path, columns=columns)

    @override
    def exists(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> bool:
        """
        Check if feature version exists in GCS.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version to check. If None, checks any version.

        Returns:
            True if the feature/version exists, False otherwise
        """
        if feature_version is None:
            return len(self.list_versions(feature_name)) > 0

        path = self._versioned_data_path(feature_name, feature_version)
        return self._gcs.exists(path)

    @override
    def metadata_path_for(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> str:
        """
        Get GCS URI for a feature version's metadata.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version. If None, uses latest.

        Returns:
            GCS URI where the feature's metadata is or would be stored
        """
        resolved = self._resolve_version(feature_name, feature_version)

        if resolved is None:
            return self._versioned_metadata_path(feature_name, "1.0.0")

        return self._versioned_metadata_path(feature_name, resolved)

    @override
    def write_metadata(
        self,
        feature_name: str,
        metadata: manifest.FeatureMetadata,
    ) -> None:
        """
        Write feature metadata to versioned GCS JSON file.

        Uses metadata.version to determine storage path.

        Args:
            feature_name: Unique identifier for the feature
            metadata: FeatureMetadata object to persist
        """
        path = self._versioned_metadata_path(feature_name, metadata.version)
        with self._gcs.open(path, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

    @override
    def read_metadata(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> manifest.FeatureMetadata | None:
        """
        Read feature metadata from versioned GCS JSON file.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version. If None, reads latest.

        Returns:
            FeatureMetadata if exists and valid, None otherwise
        """
        resolved = self._resolve_version(feature_name, feature_version)

        if resolved is None:
            return None

        path = self._versioned_metadata_path(feature_name, resolved)

        if not self._gcs.exists(path):
            return None

        try:
            with self._gcs.open(path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {path}: {e}")
            return None

        try:
            return manifest.FeatureMetadata.from_dict(data)
        except KeyError as e:
            logger.warning(f"Schema mismatch in {path}: missing key {e}")
            return None

    @override
    def list_metadata(self) -> list[manifest.FeatureMetadata]:
        """
        List metadata for latest version of all features in GCS.

        Scans for feature directories and reads their latest metadata.

        Returns:
            List of FeatureMetadata for all features (latest versions only)
        """
        metadata_list: list[manifest.FeatureMetadata] = []

        base_key = self._base_path().replace("gs://", "")

        try:
            items = self._gcs.ls(base_key, detail=False)
        except FileNotFoundError:
            return []

        for item in items:
            feature_name = item.split("/")[-1]

            if feature_name.startswith("_"):
                continue

            latest = self.get_latest_version(feature_name)
            if latest:
                meta = self.read_metadata(feature_name, latest)
                if meta:
                    metadata_list.append(meta)

        return metadata_list
