import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import override

import polars as pl
import s3fs

import mlforge.manifest as manifest
import mlforge.results as results


class Store(ABC):
    """
    Abstract base class for offline feature storage backends.

    Defines the interface that all storage implementations must provide
    for persisting and retrieving materialized features.
    """

    @abstractmethod
    def write(self, feature_name: str, result: results.ResultKind) -> dict:
        """
        Persist a materialized feature to storage.

        Args:
            feature_name: Unique identifier for the feature
            result: Result kind that store information needed to write data

        Returns:
            Metadata information about written data
        """
        ...

    @abstractmethod
    def read(self, feature_name: str) -> pl.DataFrame:
        """
        Retrieve a materialized feature from storage.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Feature data as a DataFrame

        Raises:
            FileNotFoundError: If the feature has not been materialized
        """
        ...

    @abstractmethod
    def exists(self, feature_name: str) -> bool:
        """
        Check whether a feature has been materialized.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            True if feature exists in storage, False otherwise
        """
        ...

    @abstractmethod
    def path_for(self, feature_name: str) -> Path | str:
        """
        Get the storage path for a feature.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Path or str where the feature is or would be stored.
            Returns Path or str.
        """
        ...

    @abstractmethod
    def metadata_path_for(self, feature_name: str) -> Path | str:
        """
        Get the storage path for a feature's metadata file.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Path where the feature's .meta.json is or would be stored
        """
        ...

    @abstractmethod
    def write_metadata(
        self, feature_name: str, metadata: manifest.FeatureMetadata
    ) -> None:
        """
        Write feature metadata to storage.

        Args:
            feature_name: Unique identifier for the feature
            metadata: FeatureMetadata object to persist
        """
        ...

    @abstractmethod
    def read_metadata(self, feature_name: str) -> manifest.FeatureMetadata | None:
        """
        Read feature metadata from storage.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            FeatureMetadata if exists, None otherwise
        """
        ...

    @abstractmethod
    def list_metadata(self) -> list[manifest.FeatureMetadata]:
        """
        List all feature metadata in the store.

        Scans the store for all .meta.json files and returns their contents.

        Returns:
            List of FeatureMetadata for all features with metadata
        """
        ...


class LocalStore(Store):
    """
    Local filesystem storage backend using Parquet format.

    Stores each feature as a separate .parquet file in a designated
    directory. Creates the directory if it doesn't exist.

    Attributes:
        path: Root directory for storing feature files

    Example:
        store = LocalStore("./feature_store")
        store.write("user_age", age_df)
        age_df = store.read("user_age")
    """

    def __init__(self, path: str | Path = "./feature_store"):
        """
        Initialize local storage backend.

        Args:
            path: Directory path for feature storage. Defaults to "./feature_store".
        """
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self._metadata_path = self.path / "_metadata"
        self._metadata_path.mkdir(parents=True, exist_ok=True)

    @override
    def path_for(self, feature_name: str) -> Path:
        """
        Get file path for a feature.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Path to the feature's parquet file
        """
        return self.path / f"{feature_name}.parquet"

    @override
    def write(self, feature_name: str, result: results.ResultKind) -> dict:
        """
        Write feature data to parquet file.

        Args:
            feature_name: Unique identifier for the feature
            result: Engine result containing feature data and metadata

        Returns:
            Metadata dictionary with path, row count, and schema
        """
        path = self.path_for(feature_name)
        result.write_parquet(path)
        return {
            "path": str(path),
            "row_count": result.row_count(),
            "schema": result.schema(),
        }

    @override
    def read(self, feature_name: str) -> pl.DataFrame:
        """
        Read feature data from parquet file.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Feature data as a DataFrame

        Raises:
            FileNotFoundError: If the feature file doesn't exist
        """
        return pl.read_parquet(self.path_for(feature_name))

    @override
    def exists(self, feature_name: str) -> bool:
        """
        Check if feature file exists.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            True if the feature's parquet file exists, False otherwise
        """
        return self.path_for(feature_name).exists()

    @override
    def metadata_path_for(self, feature_name: str) -> Path:
        """
        Get file path for a feature's metadata.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Path to the feature's .meta.json file
        """
        return self._metadata_path / f"{feature_name}.meta.json"

    @override
    def write_metadata(
        self, feature_name: str, metadata: manifest.FeatureMetadata
    ) -> None:
        """
        Write feature metadata to local JSON file.

        Args:
            feature_name: Unique identifier for the feature
            metadata: FeatureMetadata object to persist
        """
        path = self.metadata_path_for(feature_name)
        manifest.write_metadata_file(path, metadata)

    @override
    def read_metadata(self, feature_name: str) -> manifest.FeatureMetadata | None:
        """
        Read feature metadata from local JSON file.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            FeatureMetadata if file exists and is valid, None otherwise
        """
        path = self.metadata_path_for(feature_name)
        return manifest.read_metadata_file(path)

    @override
    def list_metadata(self) -> list[manifest.FeatureMetadata]:
        """
        List all feature metadata in the store.

        Scans for all .meta.json files in the store directory.

        Returns:
            List of FeatureMetadata for all features with metadata
        """
        metadata_list: list[manifest.FeatureMetadata] = []
        for path in self._metadata_path.glob("*.meta.json"):
            meta = manifest.read_metadata_file(path)
            if meta:
                metadata_list.append(meta)
        return metadata_list


class S3Store(Store):
    """
    Amazon S3 storage backend using Parquet format.

    Stores each feature as a separate .parquet file in an S3 bucket with
    an optional prefix. Uses AWS credentials from environment variables
    (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION).

    Attributes:
        bucket: S3 bucket name for storing features
        prefix: Optional path prefix within the bucket (without leading/trailing slashes)
        region: AWS region (optional, uses default if not specified)

    Example:
        store = S3Store(bucket="mlforge-features", prefix="prod/features")
        store.write("user_age", age_df)
        age_df = store.read("user_age")
    """

    def __init__(
        self, bucket: str, prefix: str = "", region: str | None = None
    ) -> None:
        """
        Initialize S3 storage backend.

        Args:
            bucket: S3 bucket name for feature storage
            prefix: Path prefix within bucket. Defaults to empty string (bucket root).
            region: AWS region. Defaults to None (uses AWS_DEFAULT_REGION env var).

        Raises:
            ValueError: If bucket doesn't exist or is not accessible with current credentials
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

    @override
    def path_for(self, feature_name: str) -> str:
        """
        Get S3 URI for a feature.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            S3 URI where the feature is or would be stored
        """
        if self.prefix:
            return f"s3://{self.bucket}/{self.prefix}/{feature_name}.parquet"
        return f"s3://{self.bucket}/{feature_name}.parquet"

    @override
    def write(self, feature_name: str, result: results.EngineResult) -> dict:
        """
        Write feature data to S3 as parquet file.

        Args:
            feature_name: Unique identifier for the feature
            result: Engine result containing feature data and metadata

        Returns:
            Metadata dictionary with S3 URI, row count, and schema

        Raises:
            Exception: If S3 write fails due to permissions or connectivity issues
        """
        path = self.path_for(feature_name)
        result.write_parquet(path)
        return {
            "path": str(path),
            "row_count": result.row_count(),
            "schema": result.schema(),
        }

    @override
    def read(self, feature_name: str) -> pl.DataFrame:
        """
        Read feature data from S3 parquet file.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Feature data as a DataFrame

        Raises:
            FileNotFoundError: If the feature file doesn't exist in S3
        """
        return pl.read_parquet(self.path_for(feature_name))

    @override
    def exists(self, feature_name: str) -> bool:
        """
        Check if feature file exists in S3.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            True if the feature's parquet file exists in S3, False otherwise
        """
        path = self.path_for(feature_name)
        return self._s3.exists(path)

    def _s3_metadata_path(self, feature_name: str) -> str:
        """
        Construct full S3 path for a feature's metadata.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Full S3 URI (s3://bucket/prefix/feature_name.meta.json)
        """
        if self.prefix:
            return (
                f"s3://{self.bucket}/{self.prefix}/_metadata/{feature_name}.meta.json"
            )
        return f"s3://{self.bucket}/_metadata/{feature_name}.meta.json"

    @override
    def metadata_path_for(self, feature_name: str) -> str:
        """
        Get S3 URI for a feature's metadata.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            S3 URI where the feature's metadata is or would be stored
        """
        return self._s3_metadata_path(feature_name)

    @override
    def write_metadata(
        self, feature_name: str, metadata: manifest.FeatureMetadata
    ) -> None:
        """
        Write feature metadata to S3 as JSON file.

        Args:
            feature_name: Unique identifier for the feature
            metadata: FeatureMetadata object to persist
        """
        import json

        path = self._s3_metadata_path(feature_name)
        with self._s3.open(path, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

    @override
    def read_metadata(self, feature_name: str) -> manifest.FeatureMetadata | None:
        """
        Read feature metadata from S3 JSON file.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            FeatureMetadata if file exists and is valid, None otherwise
        """
        from loguru import logger

        path = self._s3_metadata_path(feature_name)
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
        List all feature metadata in the S3 store.

        Scans for all .meta.json files in the store prefix.

        Returns:
            List of FeatureMetadata for all features with metadata
        """
        prefix_path = (
            f"{self.bucket}/{self.prefix}/_metadata"
            if self.prefix
            else f"{self.bucket}/_metadata"
        )
        metadata_list: list[manifest.FeatureMetadata] = []

        try:
            files = self._s3.glob(f"{prefix_path}/*.meta.json")
            for file_path in files:
                try:
                    with self._s3.open(file_path, "r") as f:
                        data = json.load(f)
                    meta = manifest.FeatureMetadata.from_dict(data)
                    metadata_list.append(meta)
                except (json.JSONDecodeError, KeyError):
                    continue
        except FileNotFoundError:
            pass

        return metadata_list


type OfflineStoreKind = LocalStore | S3Store
