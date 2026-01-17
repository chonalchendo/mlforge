"""
Local filesystem storage backend.

Stores features in versioned directories as Parquet files.
"""

from pathlib import Path
from typing import Any, override

import polars as pl

import mlforge.manifest as manifest
import mlforge.results as results
import mlforge.version as version
from mlforge.stores.base import Store


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
        resolved = version.resolve_version(
            self.path, feature_name, feature_version
        )

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
        path = version.versioned_data_path(
            self.path, feature_name, feature_version
        )
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
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        """
        Read feature data from versioned parquet file.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version to read. If None, reads latest.
            columns: Specific columns to read. If None, reads all columns.

        Returns:
            Feature data as a DataFrame

        Raises:
            FileNotFoundError: If the feature/version doesn't exist
        """
        resolved = version.resolve_version(
            self.path, feature_name, feature_version
        )

        if resolved is None:
            raise FileNotFoundError(
                f"Feature '{feature_name}' not found. Run 'mlforge build' first."
            )

        path = version.versioned_data_path(self.path, feature_name, resolved)

        if not path.exists():
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

        path = version.versioned_data_path(
            self.path, feature_name, feature_version
        )
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
        resolved = version.resolve_version(
            self.path, feature_name, feature_version
        )

        if resolved is None:
            # No versions exist yet
            return version.versioned_metadata_path(
                self.path, feature_name, "1.0.0"
            )

        return version.versioned_metadata_path(
            self.path, feature_name, resolved
        )

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
        resolved = version.resolve_version(
            self.path, feature_name, feature_version
        )

        if resolved is None:
            return None

        path = version.versioned_metadata_path(
            self.path, feature_name, resolved
        )
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
