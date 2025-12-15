from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable, Protocol

import polars as pl
from loguru import logger

import mlforge.errors as errors
import mlforge.logging as log
import mlforge.store as store


class FeatureFunction(Protocol):
    """Protocol defining the signature for feature transformation functions."""

    __name__: str

    def __call__(self, df: pl.DataFrame) -> pl.DataFrame: ...


@dataclass
class Feature:
    """
    Container for a feature definition and its transformation function.

    Features are created using the @feature decorator and contain metadata
    about the feature's source, keys, and timestamp requirements.

    Attributes:
        name: Feature name derived from the decorated function
        source: Path to the data source file (parquet/csv)
        keys: Column names that uniquely identify entities
        tags: Feature tags to group features together
        timestamp: Column name for temporal features, enables point-in-time joins
        description: Human-readable feature description
        fn: The transformation function that computes the feature

    Example:
        @feature(keys=["user_id"], source="data/users.parquet")
        def user_age(df):
            return df.with_columns(...)
    """

    name: str
    source: str
    keys: list[str]
    tags: list[str] | None
    timestamp: str | None
    description: str | None
    fn: Callable[..., pl.DataFrame]

    def __call__(self, *args, **kwargs) -> pl.DataFrame:
        """
        Execute the feature transformation function.

        All arguments are passed through to the underlying feature function.

        Returns:
            DataFrame with computed feature columns
        """
        return self.fn(*args, **kwargs)


def feature(
    keys: list[str],
    source: str,
    tags: list[str] | None = None,
    timestamp: str | None = None,
    description: str | None = None,
) -> Callable[[FeatureFunction], Feature]:
    """
    Decorator that marks a function as a feature definition.

    Transforms a function into a Feature object that can be registered
    with Definitions and materialized to storage.

    Args:
        keys: Column names that uniquely identify entities
        source: Path to source data file (parquet or csv)
        tags: Tags to group feature with our features. Defaults to None.
        timestamp: Column name for temporal features. Defaults to None.
        description: Human-readable feature description. Defaults to None.

    Returns:
        Decorator function that converts a function into a Feature

    Example:
        @feature(
            keys=["user_id"],
            source="data/transactions.parquet",
            tags=['users'],
            timestamp="transaction_time",
            description="User spending statistics"
        )
        def user_spend_stats(df):
            return df.group_by("user_id").agg(
                pl.col("amount").mean().alias("avg_spend")
            )
    """

    def decorator(fn: FeatureFunction) -> Feature:
        return Feature(
            name=fn.__name__,
            keys=keys,
            source=source,
            tags=tags,
            timestamp=timestamp,
            description=description,
            fn=fn,
        )

    return decorator


class Definitions:
    """
    Central registry for feature store projects.

    Manages feature registration, discovery from modules, and materialization
    to offline storage. Acts as the main entry point for defining and building
    features.

    Attributes:
        name: Project identifier
        offline_store: Storage backend instance for persisting features
        features: Dictionary mapping feature names to Feature objects

    Example:
        from mlforge import Definitions, LocalStore
        import my_features

        defs = Definitions(
            name="my-project",
            features=[my_features],
            offline_store=LocalStore("./feature_store")
        )
    """

    def __init__(
        self,
        name: str,
        features: list[Feature | ModuleType],
        offline_store: store.OfflineStoreKind,
    ) -> None:
        """
        Initialize a feature store registry.

        Args:
            name: Project name
            features: List of Feature objects or modules containing features
            offline_store: Storage backend for materialized features

        Example:
            defs = Definitions(
                name="fraud-detection",
                features=[user_features, transaction_features],
                offline_store=LocalStore("./features")
            )
        """
        self.name = name
        self.offline_store = offline_store
        self.features: dict[str, Feature] = {}

        for item in features or []:
            self._register(item)

    def _register(self, obj: Feature | ModuleType) -> None:
        """
        Register a Feature or discover features from a module.

        Args:
            obj: Feature instance or module containing Feature objects

        Raises:
            TypeError: If obj is neither a Feature nor a module
        """
        if isinstance(obj, Feature):
            self._add_feature(obj)
        elif isinstance(obj, ModuleType):
            self._register_module(obj)
        else:
            raise TypeError(f"Expected Feature or module, got {type(obj).__name__}")

    def _add_feature(self, feature: Feature) -> None:
        """
        Add a single feature to the registry.

        Args:
            feature: Feature instance to register

        Raises:
            ValueError: If a feature with the same name already exists
        """
        if feature.name in self.features:
            raise ValueError(f"Duplicate feature name: {feature.name}")

        logger.debug(f"Registered feature: {feature.name}")
        self.features[feature.name] = feature

    def _register_module(self, module: ModuleType) -> None:
        """
        Discover and register all Features in a module.

        Args:
            module: Python module to scan for Feature objects
        """
        features_found = 0

        for obj in vars(module).values():
            if isinstance(obj, Feature):
                self._add_feature(obj)
                features_found += 1

        if features_found == 0:
            logger.warning(f"No features found in module: {module.__name__}")

    def list_features(self, tags: list[str] | None = None) -> list[Feature]:
        """
        Return all registered features.

        Args:
            tags: Pass a list of tags to return the features for. Defaults to None.

        Returns:
            List of all Feature objects in the registry
        """
        features = list(self.features.values())

        if not tags:
            return features

        return [
            feat
            for feat in features
            if feat.tags and any(tag in tags for tag in feat.tags)
        ]

    def list_tags(self) -> list[str]:
        features = self.list_features()
        return [tag for feat in features if feat.tags for tag in feat.tags]

    def materialize(
        self,
        feature_names: list[str] | None = None,
        tag_names: list[str] | None = None,
        force: bool = False,
        preview: bool = True,
        preview_rows: int = 5,
    ) -> dict[str, Path]:
        """
        Compute and persist features to offline storage.

        Loads source data, applies feature transformations, validates results,
        and writes to the configured storage backend.

        Args:
            feature_names: Specific features to materialize. Defaults to None (all).
            tag_names: Specific features to materialize by tag. Defaults to None (all).
            force: Overwrite existing features. Defaults to False.
            preview: Display preview of materialized data. Defaults to True.
            preview_rows: Number of preview rows to show. Defaults to 5.

        Returns:
            Dictionary mapping feature names to their storage file paths

        Raises:
            ValueError: If specified feature name is not registered
            FeatureMaterializationError: If feature function fails or returns invalid data

        Example:
            paths = defs.materialize(
                feature_names=["user_age", "user_spend"],
                force=True
            )
        """

        if not feature_names or not tag_names:
            # build all defined in definitions if none are specified
            to_build = self.list_features()

        if feature_names:
            # build features specified by --features parameter
            to_build = []
            for name in feature_names:
                if name not in self.features:
                    raise ValueError(f"Unknown feature: {name}")
                to_build.append(self.features[name])

        if tag_names:
            # build features specificed by --tags parameter
            to_build = []
            # validate tags exist
            for tag in tag_names:
                print(tag)
                if tag not in self.list_tags():
                    print(self.list_tags())
                    raise ValueError(f"Unknown tag: {tag}")
            features = self.list_features(tags=tag_names)
            for feature in features:
                to_build.append(feature)

        results = {}

        for feature in to_build:
            output_path = self.offline_store.path_for(feature.name)

            if not force and self.offline_store.exists(feature.name):
                logger.debug(f"Skipping {feature.name} (already exists)")
                continue

            logger.info(f"Materializing {feature.name}")

            source_df = self._load_source(feature.source)
            result_df = feature(source_df)

            if result_df is None:
                raise errors.FeatureMaterializationError(
                    feature_name=feature.name,
                    message="Feature function returned None",
                    hint="Make sure your feature function returns a DataFrame.",
                )

            if not isinstance(result_df, pl.DataFrame):
                raise errors.FeatureMaterializationError(
                    feature_name=feature.name,
                    message=f"Expected DataFrame, got {type(result_df).__name__}",
                )

            self.offline_store.write(feature.name, result_df)
            results[feature.name] = Path(str(output_path))

            if preview:
                log.print_feature_preview(
                    feature.name, result_df, max_rows=preview_rows
                )

        return results

    def _load_source(self, source: str) -> pl.DataFrame:
        """
        Load source data from file path.

        Args:
            source: Path to source data file

        Returns:
            DataFrame containing source data

        Raises:
            ValueError: If file format is not supported (only .parquet and .csv)
        """
        path = Path(source)

        match path.suffix:
            case ".parquet":
                return pl.read_parquet(path)
            case ".csv":
                return pl.read_csv(path)
            case _:
                raise ValueError(f"Unsupported source format: {path.suffix}")
