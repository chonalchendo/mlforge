from abc import ABC, abstractmethod
from pathlib import Path
from typing import override

import polars as pl


class Store(ABC):
    """
    Abstract base class for offline feature storage backends.

    Defines the interface that all storage implementations must provide
    for persisting and retrieving materialized features.
    """

    @abstractmethod
    def write(self, feature_name: str, df: pl.DataFrame) -> None:
        """
        Persist a materialized feature to storage.

        Args:
            feature_name: Unique identifier for the feature
            df: Materialized feature data to store
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
    def path_for(self, feature_name: str) -> Path:
        """
        Get the storage path for a feature.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Path where the feature is or would be stored
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
    def write(self, feature_name: str, df: pl.DataFrame) -> None:
        """
        Write feature data to parquet file.

        Args:
            feature_name: Unique identifier for the feature
            df: Feature data to persist
        """
        df.write_parquet(self.path_for(feature_name))

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


type OfflineStoreKind = LocalStore
