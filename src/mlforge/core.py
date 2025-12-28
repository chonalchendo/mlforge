from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Literal, Protocol

import polars as pl
from loguru import logger

import mlforge.engines as engines
import mlforge.errors as errors
import mlforge.logging as log
import mlforge.manifest as manifest
import mlforge.metrics as metrics_
import mlforge.store as store
import mlforge.validation as validation_
import mlforge.validators as validators_

WindowFunc = Literal["1h", "1d", "7d", "30d"]


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
        interval: Time interval for rolling aggregations (e.g., "1h", "1d")
        metrics: Aggregation metrics to compute over rolling windows
        fn: The transformation function that computes the feature

    Example:
        @feature(keys=["user_id"], source="data/users.parquet")
        def user_age(df):
            return df.with_columns(...)
    """

    fn: FeatureFunction
    name: str
    source: str
    keys: list[str]
    tags: list[str] | None
    timestamp: str | None
    description: str | None
    interval: str | None
    metrics: list[metrics_.MetricKind] | None
    validators: dict[str, list[validators_.Validator]] | None

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
    description: str | None = None,
    tags: list[str] | None = None,
    timestamp: str | None = None,
    interval: str | timedelta | None = None,
    metrics: list[metrics_.MetricKind] | None = None,
    validators: dict[str, list[validators_.Validator]] | None = None,
) -> Callable[[FeatureFunction], Feature]:
    """
    Decorator that marks a function as a feature definition.

    Transforms a function into a Feature object that can be registered
    with Definitions and materialized to storage.

    Args:
        keys: Column names that uniquely identify entities
        source: Path to source data file (parquet or csv)
        description: Human-readable feature description. Defaults to None.
        tags: Tags to group feature with other features. Defaults to None.
        timestamp: Column name for temporal features. Defaults to None.
        interval: Time interval for rolling computations (e.g., "1d" or timedelta(days=1)). Defaults to None.
        metrics: Aggregation metrics like Rolling for time-based features. Defaults to None.
        validators: Column validators to run before metrics are computed. Defaults to None.
            Mapping of column names to lists of validator functions.

    Returns:
        Decorator function that converts a function into a Feature

    Example:
        @feature(
            keys=["user_id"],
            source="data/transactions.parquet",
            tags=['users'],
            timestamp="transaction_time",
            description="User spending statistics",
            interval=timedelta(days=1),
            validators={
                "amount": [not_null(), greater_than(0)],
                "user_id": [not_null()],
            },
        )
        def user_spend_stats(df):
            return df.group_by("user_id").agg(
                pl.col("amount").mean().alias("avg_spend")
            )
    """
    # Convert timedelta to string if provided
    interval_str = (
        metrics_.timedelta_to_polars_duration(interval)
        if isinstance(interval, timedelta)
        else interval
    )

    def decorator(fn: FeatureFunction) -> Feature:
        return Feature(
            fn=fn,
            name=fn.__name__,
            description=description,
            source=source,
            keys=keys,
            tags=tags,
            timestamp=timestamp,
            interval=interval_str,
            metrics=metrics,
            validators=validators,
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
        engine: Literal["polars"] = "polars",
    ) -> None:
        """
        Initialize a feature store registry.

        Args:
            name: Project name
            features: List of Feature objects or modules containing features
            offline_store: Storage backend for materialized features
            engine: Execution engine for feature computation. Defaults to "polars".

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
        self._engine: engines.EngineKind = self._get_engine(engine)

        for item in features or []:
            self._register(item)

    def _get_engine(self, engine: str) -> engines.EngineKind:
        """
        Resolve engine name to engine instance.

        Args:
            engine: Engine identifier string

        Returns:
            Initialized engine instance

        Raises:
            ValueError: If engine name is not recognized
        """
        match engine:
            case "polars":
                from mlforge.engines import PolarsEngine

                return PolarsEngine()
            case _:
                raise ValueError(f"Unknown engine: {engine}")

    def build(
        self,
        feature_names: list[str] | None = None,
        tag_names: list[str] | None = None,
        force: bool = False,
        preview: bool = True,
        preview_rows: int = 5,
    ) -> dict[str, Path | str]:
        """
        Compute and persist features to offline storage.

        Loads source data, applies feature transformations, validates results,
        and writes to the configured storage backend. Features that fail
        validation are skipped, but other features continue to build.

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
            paths = defs.build(
                feature_names=["user_age", "user_spend"],
                force=True
            )
        """
        selected_features = self._resolve_features_to_build(feature_names, tag_names)
        results: dict[str, Path | str] = {}
        failed_features: list[str] = []

        for feature in selected_features:
            if not force and self.offline_store.exists(feature.name):
                logger.debug(f"Skipping {feature.name} (already exists)")
                continue

            try:
                result = self._engine.execute(feature)
            except errors.FeatureValidationError as e:
                logger.error(str(e))
                failed_features.append(feature.name)
                continue

            result_df = result.to_polars()
            self._validate_result(feature.name, result_df)

            write_metadata = self.offline_store.write(feature.name, result)
            result_path = self.offline_store.path_for(feature.name)

            # Build and write feature metadata
            feature_metadata = self._build_feature_metadata(
                feature=feature,
                write_metadata=write_metadata,
                schema=result.schema(),
                base_schema=result.base_schema(),
            )
            self.offline_store.write_metadata(feature.name, feature_metadata)

            if preview:
                log.print_feature_preview(
                    feature.name, result_df, max_rows=preview_rows
                )

            results[feature.name] = result_path

        if failed_features:
            logger.warning(
                f"Build completed with validation failures: {failed_features}"
            )

        return results

    def validate(
        self,
        feature_names: list[str] | None = None,
        tag_names: list[str] | None = None,
    ) -> list[validation_.FeatureValidationResult]:
        """
        Run validation checks on features without building.

        Loads source data, applies feature transformations, and runs validators
        on the output. Does not compute metrics or write to storage.

        Args:
            feature_names: Specific features to validate. Defaults to None (all).
            tag_names: Specific features to validate by tag. Defaults to None (all).

        Returns:
            List of FeatureValidationResult objects, one per validated feature.
            Features without validators are skipped.

        Raises:
            ValueError: If specified feature name is not registered

        Example:
            results = defs.validate(feature_names=["user_spend"])
            for result in results:
                if not result.passed:
                    print(f"{result.feature_name} failed validation")
        """
        selected_features = self._resolve_features_to_build(feature_names, tag_names)
        results: list[validation_.FeatureValidationResult] = []

        for feature in selected_features:
            if not feature.validators:
                logger.debug(f"Skipping {feature.name} (no validators)")
                continue

            try:
                # Load and process data (without metrics)
                source_df = self._engine._load_source(feature.source)
                processed_df = feature(source_df)

                # Collect if LazyFrame
                if isinstance(processed_df, pl.LazyFrame):
                    processed_df = processed_df.collect()

                # Run validators
                result = validation_.validate_feature(
                    feature.name, processed_df, feature.validators
                )
                results.append(result)

            except Exception as e:
                logger.error(f"Error validating {feature.name}: {e}")
                # Create a failed result for the feature
                results.append(
                    validation_.FeatureValidationResult(
                        feature_name=feature.name,
                        column_results=[
                            validation_.ColumnValidationResult(
                                column="<error>",
                                validator_name="execution",
                                result=validators_.ValidationResult(
                                    passed=False,
                                    message=str(e),
                                ),
                            )
                        ],
                    )
                )

        return results

    def _validate_result(self, feature_name: str, result_df: Any) -> None:
        """
        Validate that a feature function returned a valid DataFrame.

        Args:
            feature_name: Name of the feature being validated
            result_df: Result from feature function

        Raises:
            FeatureMaterializationError: If result is None or not a DataFrame
        """
        if result_df is None:
            raise errors.FeatureMaterializationError(
                feature_name=feature_name,
                message="Feature function returned None",
                hint="Make sure your feature function returns a DataFrame.",
            )

        if not isinstance(result_df, pl.DataFrame):
            raise errors.FeatureMaterializationError(
                feature_name=feature_name,
                message=f"Expected DataFrame, got {type(result_df).__name__}",
            )

    def _resolve_features_to_build(
        self,
        feature_names: list[str] | None,
        tag_names: list[str] | None,
    ) -> list[Feature]:
        """
        Resolve which features to build based on parameters.

        Args:
            feature_names: Specific feature names to build, or None for all
            tag_names: Feature tags to filter by, or None

        Returns:
            List of Feature objects to materialize

        Raises:
            ValueError: If both feature_names and tag_names are specified,
                       or if any feature/tag name is invalid
        """
        if feature_names and tag_names:
            raise ValueError(
                "Cannot specify both --features and --tags. Choose one or the other."
            )

        if feature_names:
            return [self._get_feature(name) for name in feature_names]

        if tag_names:
            self._validate_tags(tag_names)
            return self.list_features(tags=tag_names)

        return self.list_features()

    def _validate_tags(self, tag_names: list[str]) -> None:
        """
        Validate that all tag names exist in registered features.

        Args:
            tag_names: List of tag names to validate

        Raises:
            ValueError: If any tag is not found in registered features
        """
        available_tags = set(self.list_tags())
        invalid_tags = [t for t in tag_names if t not in available_tags]
        if invalid_tags:
            logger.debug(f"Invalid tags: {invalid_tags}. Available: {available_tags}")
            raise ValueError(
                f"Unknown tags: {invalid_tags}. Available: {sorted(available_tags)}"
            )

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
        """
        Return all tags from registered features.

        Returns:
            Flat list of tag strings. May contain duplicates if the same
            tag is used by multiple features.

        Example:
            tags = defs.list_tags()  # ["users", "transactions", "users"]
            unique_tags = set(defs.list_tags())  # {"users", "transactions"}
        """
        features = self.list_features()
        return [tag for feat in features if feat.tags for tag in feat.tags]

    def _get_feature(self, name: str) -> Feature:
        """
        Get a feature by name.

        Args:
            name: Feature name to retrieve

        Returns:
            Feature object

        Raises:
            ValueError: If feature name is not registered
        """
        if name not in self.features:
            raise ValueError(f"Unknown feature: {name}")
        return self.features[name]

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

    def _build_feature_metadata(
        self,
        feature: Feature,
        write_metadata: dict,
        schema: dict[str, str],
        base_schema: dict[str, str] | None = None,
    ) -> manifest.FeatureMetadata:
        """
        Build FeatureMetadata from feature definition and write results.

        Args:
            feature: The Feature definition object
            write_metadata: Metadata returned from store.write()
            schema: Column name to dtype mapping from result (final schema after metrics)
            base_schema: Column name to dtype mapping before metrics were applied

        Returns:
            FeatureMetadata object ready for persistence
        """
        base_columns, feature_columns = manifest.derive_column_metadata(
            feature, schema, base_schema
        )
        return manifest.FeatureMetadata(
            name=feature.name,
            path=write_metadata["path"],
            entity=feature.keys[0],
            keys=feature.keys,
            source=feature.source,
            row_count=write_metadata["row_count"],
            last_updated=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            timestamp=feature.timestamp,
            interval=feature.interval,
            columns=base_columns,
            features=feature_columns,
            tags=feature.tags or [],
            description=feature.description,
        )
