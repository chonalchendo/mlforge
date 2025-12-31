import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, override

import polars as pl
import s3fs
from loguru import logger

import mlforge.manifest as manifest
import mlforge.results as results
import mlforge.version as version


class Store(ABC):
    """
    Abstract base class for offline feature storage backends.

    Defines the interface that all storage implementations must provide
    for persisting and retrieving materialized features with versioning.

    v0.5.0: Added version parameter to read/write/exists methods and
    new list_versions/get_latest_version methods.
    """

    @abstractmethod
    def write(
        self,
        feature_name: str,
        result: results.ResultKind,
        feature_version: str,
    ) -> dict[str, Any]:
        """
        Persist a materialized feature to storage.

        Args:
            feature_name: Unique identifier for the feature
            result: Result kind containing data to write
            feature_version: Semantic version string (e.g., "1.0.0")

        Returns:
            Metadata dictionary with path, row_count, schema
        """
        ...

    @abstractmethod
    def read(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> pl.DataFrame:
        """
        Retrieve a materialized feature from storage.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version to read. If None, reads latest.

        Returns:
            Feature data as a DataFrame

        Raises:
            FileNotFoundError: If the feature/version has not been materialized
        """
        ...

    @abstractmethod
    def exists(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> bool:
        """
        Check whether a feature version has been materialized.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version to check. If None, checks any version.

        Returns:
            True if feature exists in storage, False otherwise
        """
        ...

    @abstractmethod
    def list_versions(self, feature_name: str) -> list[str]:
        """
        List all versions of a feature.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Sorted list of version strings (oldest to newest)
        """
        ...

    @abstractmethod
    def get_latest_version(self, feature_name: str) -> str | None:
        """
        Get the latest version of a feature.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Latest version string, or None if no versions exist
        """
        ...

    @abstractmethod
    def path_for(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> Path | str:
        """
        Get the storage path for a feature version.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version. If None, uses latest.

        Returns:
            Path or str where the feature is or would be stored
        """
        ...

    @abstractmethod
    def metadata_path_for(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> Path | str:
        """
        Get the storage path for a feature version's metadata file.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version. If None, uses latest.

        Returns:
            Path where the feature's .meta.json is or would be stored
        """
        ...

    @abstractmethod
    def write_metadata(
        self,
        feature_name: str,
        metadata: manifest.FeatureMetadata,
    ) -> None:
        """
        Write feature metadata to storage.

        Uses metadata.version to determine storage path.

        Args:
            feature_name: Unique identifier for the feature
            metadata: FeatureMetadata object to persist
        """
        ...

    @abstractmethod
    def read_metadata(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> manifest.FeatureMetadata | None:
        """
        Read feature metadata from storage.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version. If None, reads latest.

        Returns:
            FeatureMetadata if exists, None otherwise
        """
        ...

    @abstractmethod
    def list_metadata(self) -> list[manifest.FeatureMetadata]:
        """
        List metadata for latest version of all features in the store.

        Returns:
            List of FeatureMetadata for all features (latest versions only)
        """
        ...


class LocalStore(Store):
    """
    Local filesystem storage backend using Parquet format.

    Stores features in versioned directories:
        feature_store/
        ├── user_spend/
        │   ├── 1.0.0/
        │   │   ├── data.parquet
        │   │   └── .meta.json
        │   ├── 1.1.0/
        │   │   └── ...
        │   └── _latest.json

    Attributes:
        path: Root directory for storing feature files

    Example:
        store = LocalStore("./feature_store")
        store.write("user_age", result, version="1.0.0")
        age_df = store.read("user_age")  # reads latest
        age_df = store.read("user_age", version="1.0.0")  # reads specific
    """

    def __init__(self, path: str | Path = "./feature_store"):
        """
        Initialize local storage backend.

        Args:
            path: Directory path for feature storage. Defaults to "./feature_store".
        """
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)

    @override
    def path_for(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> Path:
        """
        Get file path for a feature version.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version. If None, uses latest.

        Returns:
            Path to the feature's parquet file
        """
        resolved = version.resolve_version(self.path, feature_name, feature_version)

        if resolved is None:
            # No versions exist yet - return path for hypothetical 1.0.0
            return version.versioned_data_path(self.path, feature_name, "1.0.0")

        return version.versioned_data_path(self.path, feature_name, resolved)

    @override
    def write(
        self,
        feature_name: str,
        result: results.ResultKind,
        feature_version: str,
    ) -> dict[str, Any]:
        """
        Write feature data to versioned parquet file.

        Args:
            feature_name: Unique identifier for the feature
            result: Engine result containing feature data and metadata
            feature_version: Semantic version string (e.g., "1.0.0")

        Returns:
            Metadata dictionary with path, row count, and schema
        """
        path = version.versioned_data_path(self.path, feature_name, feature_version)
        path.parent.mkdir(parents=True, exist_ok=True)

        result.write_parquet(path)

        # Update _latest.json pointer
        version.write_latest_pointer(self.path, feature_name, feature_version)

        # Create .gitignore in feature directory (if not present)
        version.write_feature_gitignore(self.path, feature_name)

        return {
            "path": str(path),
            "row_count": result.row_count(),
            "schema": result.schema(),
        }

    @override
    def read(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> pl.DataFrame:
        """
        Read feature data from versioned parquet file.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version to read. If None, reads latest.

        Returns:
            Feature data as a DataFrame

        Raises:
            FileNotFoundError: If the feature/version doesn't exist
        """
        resolved = version.resolve_version(self.path, feature_name, feature_version)

        if resolved is None:
            raise FileNotFoundError(
                f"Feature '{feature_name}' not found. Run 'mlforge build' first."
            )

        path = version.versioned_data_path(self.path, feature_name, resolved)

        if not path.exists():
            raise FileNotFoundError(
                f"Feature '{feature_name}' version '{resolved}' not found."
            )

        return pl.read_parquet(path)

    @override
    def exists(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> bool:
        """
        Check if feature version exists.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version to check. If None, checks any version.

        Returns:
            True if the feature/version exists, False otherwise
        """
        if feature_version is None:
            # Check if any version exists
            return len(self.list_versions(feature_name)) > 0

        path = version.versioned_data_path(self.path, feature_name, feature_version)
        return path.exists()

    @override
    def list_versions(self, feature_name: str) -> list[str]:
        """
        List all versions of a feature.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Sorted list of version strings (oldest to newest)
        """
        return version.list_versions(self.path, feature_name)

    @override
    def get_latest_version(self, feature_name: str) -> str | None:
        """
        Get the latest version of a feature.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Latest version string, or None if no versions exist
        """
        return version.get_latest_version(self.path, feature_name)

    @override
    def metadata_path_for(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> Path:
        """
        Get file path for a feature version's metadata.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version. If None, uses latest.

        Returns:
            Path to the feature's .meta.json file
        """
        resolved = version.resolve_version(self.path, feature_name, feature_version)

        if resolved is None:
            # No versions exist yet
            return version.versioned_metadata_path(self.path, feature_name, "1.0.0")

        return version.versioned_metadata_path(self.path, feature_name, resolved)

    @override
    def write_metadata(
        self,
        feature_name: str,
        metadata: manifest.FeatureMetadata,
    ) -> None:
        """
        Write feature metadata to versioned JSON file.

        Uses metadata.version to determine storage path.

        Args:
            feature_name: Unique identifier for the feature
            metadata: FeatureMetadata object to persist
        """
        path = version.versioned_metadata_path(
            self.path, feature_name, metadata.version
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_metadata_file(path, metadata)

    @override
    def read_metadata(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> manifest.FeatureMetadata | None:
        """
        Read feature metadata from versioned JSON file.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version. If None, reads latest.

        Returns:
            FeatureMetadata if exists and valid, None otherwise
        """
        resolved = version.resolve_version(self.path, feature_name, feature_version)

        if resolved is None:
            return None

        path = version.versioned_metadata_path(self.path, feature_name, resolved)
        return manifest.read_metadata_file(path)

    @override
    def list_metadata(self) -> list[manifest.FeatureMetadata]:
        """
        List metadata for latest version of all features.

        Scans for feature directories and reads their latest metadata.

        Returns:
            List of FeatureMetadata for all features (latest versions only)
        """
        metadata_list: list[manifest.FeatureMetadata] = []

        # Scan for feature directories (contain version subdirectories)
        for feature_dir in self.path.iterdir():
            if not feature_dir.is_dir() or feature_dir.name.startswith("_"):
                continue

            latest = self.get_latest_version(feature_dir.name)
            if latest:
                meta = self.read_metadata(feature_dir.name, latest)
                if meta:
                    metadata_list.append(meta)

        return metadata_list


class S3Store(Store):
    """
    Amazon S3 storage backend using Parquet format.

    Stores features in versioned directories within an S3 bucket:
        s3://bucket/prefix/
        ├── user_spend/
        │   ├── 1.0.0/
        │   │   ├── data.parquet
        │   │   └── .meta.json
        │   ├── 1.1.0/
        │   │   └── ...
        │   └── _latest.json

    Uses AWS credentials from environment variables
    (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION).

    Attributes:
        bucket: S3 bucket name for storing features
        prefix: Optional path prefix within the bucket
        region: AWS region (optional)

    Example:
        store = S3Store(bucket="mlforge-features", prefix="prod/features")
        store.write("user_age", result, version="1.0.0")
        age_df = store.read("user_age")  # reads latest
    """

    def __init__(
        self, bucket: str, prefix: str = "", region: str | None = None
    ) -> None:
        """
        Initialize S3 storage backend.

        Args:
            bucket: S3 bucket name for feature storage
            prefix: Path prefix within bucket. Defaults to empty string.
            region: AWS region. Defaults to None (uses AWS_DEFAULT_REGION).

        Raises:
            ValueError: If bucket doesn't exist or is not accessible
        """
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.region = region
        self._s3 = s3fs.S3FileSystem()  # Uses AWS env vars automatically

        if not self._s3.exists(self.bucket):
            raise ValueError(
                f"Bucket '{self.bucket}' does not exist or is not accessible. "
                f"Ensure the bucket is created and credentials have appropriate permissions."
            )

    def _base_path(self) -> str:
        """Get base S3 path (bucket/prefix)."""
        if self.prefix:
            return f"s3://{self.bucket}/{self.prefix}"
        return f"s3://{self.bucket}"

    def _versioned_data_path(self, feature_name: str, feature_version: str) -> str:
        """Get S3 path for versioned feature data."""
        return f"{self._base_path()}/{feature_name}/{feature_version}/data.parquet"

    def _versioned_metadata_path(self, feature_name: str, feature_version: str) -> str:
        """Get S3 path for versioned feature metadata."""
        return f"{self._base_path()}/{feature_name}/{feature_version}/.meta.json"

    def _latest_pointer_path(self, feature_name: str) -> str:
        """Get S3 path for _latest.json pointer."""
        return f"{self._base_path()}/{feature_name}/_latest.json"

    def _feature_dir_path(self, feature_name: str) -> str:
        """Get S3 path for feature directory."""
        return f"{self._base_path()}/{feature_name}"

    def _write_latest_pointer(self, feature_name: str, feature_version: str) -> None:
        """Write _latest.json pointer to S3."""
        path = self._latest_pointer_path(feature_name)
        with self._s3.open(path, "w") as f:
            json.dump({"version": feature_version}, f, indent=2)

    def _read_latest_pointer(self, feature_name: str) -> str | None:
        """Read _latest.json pointer from S3."""
        path = self._latest_pointer_path(feature_name)
        if not self._s3.exists(path):
            return None

        try:
            with self._s3.open(path, "r") as f:
                data = json.load(f)
            return data.get("version")
        except (json.JSONDecodeError, KeyError):
            return None

    @override
    def list_versions(self, feature_name: str) -> list[str]:
        """
        List all versions of a feature in S3.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Sorted list of version strings (oldest to newest)
        """
        feature_dir = self._feature_dir_path(feature_name)

        # Remove s3:// prefix for ls
        feature_dir_key = feature_dir.replace("s3://", "")

        try:
            # List directories in the feature directory
            items = self._s3.ls(feature_dir_key, detail=False)
        except FileNotFoundError:
            return []

        versions = []
        for item in items:
            # Extract the directory name (version)
            name = item.split("/")[-1]
            if version.is_valid_version(name):
                versions.append(name)

        return version.sort_versions(versions)

    @override
    def get_latest_version(self, feature_name: str) -> str | None:
        """
        Get the latest version of a feature from S3.

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
        Get S3 URI for a feature version.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version. If None, uses latest.

        Returns:
            S3 URI where the feature is or would be stored
        """
        resolved = self._resolve_version(feature_name, feature_version)

        if resolved is None:
            # No versions exist yet
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
        Write feature data to versioned S3 parquet file.

        Args:
            feature_name: Unique identifier for the feature
            result: Engine result containing feature data and metadata
            feature_version: Semantic version string (e.g., "1.0.0")

        Returns:
            Metadata dictionary with S3 URI, row count, and schema
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
    ) -> pl.DataFrame:
        """
        Read feature data from versioned S3 parquet file.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version to read. If None, reads latest.

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

        if not self._s3.exists(path):
            raise FileNotFoundError(
                f"Feature '{feature_name}' version '{resolved}' not found."
            )

        return pl.read_parquet(path)

    @override
    def exists(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> bool:
        """
        Check if feature version exists in S3.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version to check. If None, checks any version.

        Returns:
            True if the feature/version exists, False otherwise
        """
        if feature_version is None:
            # Check if any version exists
            return len(self.list_versions(feature_name)) > 0

        path = self._versioned_data_path(feature_name, feature_version)
        return self._s3.exists(path)

    @override
    def metadata_path_for(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> str:
        """
        Get S3 URI for a feature version's metadata.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version. If None, uses latest.

        Returns:
            S3 URI where the feature's metadata is or would be stored
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
        Write feature metadata to versioned S3 JSON file.

        Uses metadata.version to determine storage path.

        Args:
            feature_name: Unique identifier for the feature
            metadata: FeatureMetadata object to persist
        """
        path = self._versioned_metadata_path(feature_name, metadata.version)
        with self._s3.open(path, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

    @override
    def read_metadata(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> manifest.FeatureMetadata | None:
        """
        Read feature metadata from versioned S3 JSON file.

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

        if not self._s3.exists(path):
            return None

        try:
            with self._s3.open(path, "r") as f:
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
        List metadata for latest version of all features in S3.

        Scans for feature directories and reads their latest metadata.

        Returns:
            List of FeatureMetadata for all features (latest versions only)
        """
        metadata_list: list[manifest.FeatureMetadata] = []

        # List all directories at the base path
        base_key = self._base_path().replace("s3://", "")

        try:
            items = self._s3.ls(base_key, detail=False)
        except FileNotFoundError:
            return []

        for item in items:
            feature_name = item.split("/")[-1]

            # Skip hidden/metadata directories
            if feature_name.startswith("_"):
                continue

            latest = self.get_latest_version(feature_name)
            if latest:
                meta = self.read_metadata(feature_name, latest)
                if meta:
                    metadata_list.append(meta)

        return metadata_list


type OfflineStoreKind = LocalStore | S3Store
