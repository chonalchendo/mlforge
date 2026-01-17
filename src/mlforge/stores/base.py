"""
Abstract base classes for feature stores.

This module defines the Store and OnlineStore ABCs that all storage
implementations must inherit from.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import polars as pl

import mlforge.manifest as manifest
import mlforge.results as results


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
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        """
        Retrieve a materialized feature from storage.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version to read. If None, reads latest.
            columns: Specific columns to read. If None, reads all columns.
                Uses Parquet column projection for efficiency.

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


class OnlineStore(ABC):
    """
    Abstract base class for online feature storage backends.

    Online stores provide low-latency read/write access to feature values
    for real-time ML inference. Unlike offline stores (which store full
    feature history), online stores typically only hold the latest values.

    Key design:
        - Simple key-value model: entity keys -> feature values
        - JSON serialization for human-readable debugging
        - Batch operations for efficient bulk access
    """

    @abstractmethod
    def write(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
        values: dict[str, Any],
    ) -> None:
        """
        Write feature values for a single entity.

        Args:
            feature_name: Name of the feature
            entity_keys: Entity key columns and values (e.g., {"user_id": "123"})
            values: Feature column values (e.g., {"amount__sum__7d": 1500.0})
        """
        ...

    @abstractmethod
    def write_batch(
        self,
        feature_name: str,
        records: list[dict[str, Any]],
        entity_key_columns: list[str],
    ) -> int:
        """
        Write feature values for multiple entities.

        Args:
            feature_name: Name of the feature
            records: List of records, each containing entity keys and feature values
            entity_key_columns: Column names that form the entity key

        Returns:
            Number of records written
        """
        ...

    @abstractmethod
    def read(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> dict[str, Any] | None:
        """
        Read feature values for a single entity.

        Args:
            feature_name: Name of the feature
            entity_keys: Entity key columns and values

        Returns:
            Feature values dict, or None if not found
        """
        ...

    @abstractmethod
    def read_batch(
        self,
        feature_name: str,
        entity_keys: list[dict[str, str]],
    ) -> list[dict[str, Any] | None]:
        """
        Read feature values for multiple entities.

        Args:
            feature_name: Name of the feature
            entity_keys: List of entity key dicts

        Returns:
            List of feature value dicts (None for missing entities)
        """
        ...

    @abstractmethod
    def delete(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> bool:
        """
        Delete feature values for a single entity.

        Args:
            feature_name: Name of the feature
            entity_keys: Entity key columns and values

        Returns:
            True if deleted, False if not found
        """
        ...

    @abstractmethod
    def exists(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> bool:
        """
        Check if feature values exist for an entity.

        Args:
            feature_name: Name of the feature
            entity_keys: Entity key columns and values

        Returns:
            True if exists, False otherwise
        """
        ...
