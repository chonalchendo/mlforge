from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Literal, Protocol

import duckdb
import polars as pl
from loguru import logger

import mlforge.engines as engines
import mlforge.errors as errors
import mlforge.logging as log
import mlforge.manifest as manifest
import mlforge.metrics as metrics_
import mlforge.online as online
import mlforge.sources as sources
import mlforge.store as store
import mlforge.types as types_
import mlforge.validation as validation_
import mlforge.validators as validators_
import mlforge.version as version

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
        engine: Compute engine to use for this feature ("polars" or "duckdb")
        fn: The transformation function that computes the feature

    Example:
        @feature(keys=["user_id"], source="data/users.parquet")
        def user_age(df):
            return df.with_columns(...)

        @feature(keys=["user_id"], source="data/transactions.parquet", engine="duckdb")
        def user_spend(df):
            return df.select("user_id", "amount")
    """

    fn: FeatureFunction
    name: str
    source: str | sources.Source
    keys: list[str]
    tags: list[str] | None
    timestamp: str | None
    description: str | None
    interval: str | None
    metrics: list[metrics_.MetricKind] | None
    validators: dict[str, list[validators_.Validator]] | None
    engine: str | None

    @property
    def source_path(self) -> str:
        """Get the source path, whether source is a string or Source object."""
        if isinstance(self.source, sources.Source):
            return self.source.path
        return self.source

    @property
    def source_obj(self) -> sources.Source:
        """Get source as a Source object, converting string if needed."""
        if isinstance(self.source, sources.Source):
            return self.source
        return sources.Source(self.source)

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
    source: str | sources.Source,
    description: str | None = None,
    tags: list[str] | None = None,
    timestamp: str | None = None,
    interval: str | timedelta | None = None,
    metrics: list[metrics_.MetricKind] | None = None,
    validators: dict[str, list[validators_.Validator]] | None = None,
    engine: Literal["polars", "duckdb"] | None = None,
) -> Callable[[FeatureFunction], Feature]:
    """
    Decorator that marks a function as a feature definition.

    Transforms a function into a Feature object that can be registered
    with Definitions and materialized to storage.

    Args:
        keys: Column names that uniquely identify entities
        source: Path to source data file or Source object. Can be:
            - A string path: "data/transactions.parquet"
            - A Source object: Source("s3://bucket/data.parquet")
            - A Source with format options: Source("data.csv", format=CSVFormat(delimiter="|"))
        description: Human-readable feature description. Defaults to None.
        tags: Tags to group feature with other features. Defaults to None.
        timestamp: Column name for temporal features. Defaults to None.
        interval: Time interval for rolling computations (e.g., "1d" or timedelta(days=1)). Defaults to None.
        metrics: Aggregation metrics like Rolling for time-based features. Defaults to None.
        validators: Column validators to run before metrics are computed. Defaults to None.
            Mapping of column names to lists of validator functions.
        engine: Compute engine to use for this feature. Defaults to None (uses Definitions default).
            Options: "polars" (default), "duckdb" (for large datasets).

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

        # Use DuckDB for large dataset processing
        @feature(
            keys=["user_id"],
            source="data/large_transactions.parquet",
            engine="duckdb",
        )
        def user_large_spend(df):
            return df.select("user_id", "amount")

        # Use Source with format options
        @feature(
            keys=["user_id"],
            source=Source("data/events.csv", format=CSVFormat(delimiter="|")),
        )
        def user_events(df):
            return df
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
            engine=engine,
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
        online_store: Optional online store for real-time feature serving
        features: Dictionary mapping feature names to Feature objects
        default_engine: Default compute engine for features without explicit engine. Defaults to duckdb.

    Example:
        from mlforge import Definitions, LocalStore
        from mlforge.online import RedisStore
        import my_features

        defs = Definitions(
            name="my-project",
            features=[my_features],
            offline_store=LocalStore("./feature_store"),
            online_store=RedisStore(host="localhost"),
        )

        # Build to offline store (default)
        defs.build(feature_names=["user_spend"])

        # Build to online store
        defs.build(feature_names=["user_spend"], online=True)
    """

    def __init__(
        self,
        name: str,
        features: list[Feature | ModuleType],
        offline_store: store.OfflineStoreKind,
        online_store: online.OnlineStoreKind | None = None,
        default_engine: Literal["polars", "duckdb"] = "duckdb",
    ) -> None:
        """
        Initialize a feature store registry.

        Args:
            name: Project name
            features: List of Feature objects or modules containing features
            offline_store: Storage backend for materialized features
            online_store: Optional online store for real-time serving. Defaults to None.
            default_engine: Default execution engine for features without explicit engine.
                Defaults to "duckdb" which is optimized for large datasets with rolling
                windows. Use "polars" for small datasets or when you prefer staying in
                the Polars ecosystem. Individual features can override this via the
                engine parameter in the @feature decorator.

        Example:
            defs = Definitions(
                name="fraud-detection",
                features=[user_features, transaction_features],
                offline_store=LocalStore("./features"),
                online_store=RedisStore(host="localhost"),
            )

            # Use Polars for small datasets
            defs = Definitions(
                name="fraud-detection",
                features=[user_features],
                offline_store=LocalStore("./features"),
                default_engine="polars"
            )
        """
        self.name = name
        self.offline_store = offline_store
        self.online_store = online_store
        self.features: dict[str, Feature] = {}
        self.default_engine = default_engine
        self._engines: dict[str, engines.EngineKind] = {}

        for item in features or []:
            self._register(item)

    def _get_engine(self, engine: str) -> engines.EngineKind:
        """
        Get or create an engine instance by name.

        Engines are cached to avoid recreating them for each feature.

        Args:
            engine: Engine identifier string ("polars" or "duckdb")

        Returns:
            Initialized engine instance

        Raises:
            ValueError: If engine name is not recognized
        """
        if engine in self._engines:
            return self._engines[engine]

        match engine:
            case "polars":
                from mlforge.engines import PolarsEngine

                self._engines[engine] = PolarsEngine()
            case "duckdb":
                from mlforge.engines import DuckDBEngine

                self._engines[engine] = DuckDBEngine()
            case _:
                raise ValueError(f"Unknown engine: {engine}")

        return self._engines[engine]

    def _get_engine_for_feature(self, feature: Feature) -> engines.EngineKind:
        """
        Get the appropriate engine for a feature.

        Uses the feature's engine if specified, otherwise falls back to
        the Definitions default engine.

        Args:
            feature: Feature to get engine for

        Returns:
            Engine instance for the feature
        """
        engine_name = feature.engine or self.default_engine
        return self._get_engine(engine_name)

    def build(
        self,
        feature_names: list[str] | None = None,
        tag_names: list[str] | None = None,
        feature_version: str | None = None,
        force: bool = False,
        preview: bool = True,
        preview_rows: int = 5,
        online: bool = False,
    ) -> dict[str, Path | str | int]:
        """
        Compute and persist features to offline storage with versioning.

        Loads source data, applies feature transformations, validates results,
        and writes to the configured storage backend. Automatically determines
        the appropriate version based on schema and configuration changes.

        Args:
            feature_names: Specific features to materialize. Defaults to None (all).
            tag_names: Specific features to materialize by tag. Defaults to None (all).
            feature_version: Explicit version override (e.g., "2.0.0"). If None, auto-detects.
            force: Overwrite existing features. Defaults to False.
            preview: Display preview of materialized data. Defaults to True.
            preview_rows: Number of preview rows to show. Defaults to 5.
            online: Write to online store instead of offline. Defaults to False.
                Requires online_store to be configured. Extracts latest values
                per entity and writes to the online store.

        Returns:
            Dictionary mapping feature names to their storage file paths (offline)
            or record counts (online)

        Raises:
            ValueError: If specified feature name is not registered, or if
                online=True but no online_store is configured
            FeatureMaterializationError: If feature function fails or returns invalid data

        Example:
            # Auto-versioning (default)
            paths = defs.build(feature_names=["user_age", "user_spend"])

            # Explicit version
            paths = defs.build(feature_names=["user_spend"], feature_version="2.0.0")

            # Build to online store
            counts = defs.build(feature_names=["user_spend"], online=True)
        """
        if online:
            online_results = self._build_online(
                feature_names, tag_names, preview, preview_rows
            )
            # Cast int to Path | str | int union for consistent return type
            return {k: v for k, v in online_results.items()}

        selected_features = self._resolve_features_to_build(
            feature_names, tag_names
        )
        results: dict[str, Path | str | int] = {}
        failed_features: list[str] = []

        for feature in selected_features:
            # Get previous metadata for change detection
            previous_meta = self.offline_store.read_metadata(feature.name)

            # Determine target version
            if feature_version is not None:
                # Explicit version override
                target_version = feature_version
                change_summary = version.ChangeSummary(
                    change_type=version.ChangeType.PATCH,
                    reason="explicit_version",
                    details=[],
                )
            else:
                # Auto-detect version
                target_version, change_summary = self._determine_version(
                    feature, previous_meta
                )

            # Check if this version already exists (unless force)
            if not force and self.offline_store.exists(
                feature.name, target_version
            ):
                logger.debug(
                    f"Skipping {feature.name} v{target_version} (already exists)"
                )
                continue

            try:
                engine = self._get_engine_for_feature(feature)
                result = engine.execute(feature)
            except errors.FeatureValidationError as e:
                logger.error(str(e))
                failed_features.append(feature.name)
                continue

            result_df = result.to_polars()
            self._validate_result(feature.name, result_df)

            # Write with version
            write_metadata = self.offline_store.write(
                feature.name, result, feature_version=target_version
            )

            # Compute hashes for metadata
            # Use base_schema (before metrics) for consistent hash computation
            # Use canonical types for consistent hashing across engines
            base_schema_canonical = (
                result.base_schema_canonical() or result.schema_canonical()
            )
            schema_columns = [
                manifest.ColumnMetadata(name=k, dtype=v.to_canonical_string())
                for k, v in base_schema_canonical.items()
            ]
            schema_hash = version.compute_schema_hash(schema_columns)
            config_hash = version.compute_config_hash(
                keys=feature.keys,
                timestamp=feature.timestamp,
                interval=feature.interval,
                metrics_config=self._serialize_metrics_config(feature.metrics),
            )
            content_hash = version.compute_content_hash(
                Path(write_metadata["path"])
            )
            source_hash = version.compute_source_hash(feature.source_path)

            # Build and write feature metadata
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            feature_metadata = self._build_feature_metadata(
                feature=feature,
                write_metadata=write_metadata,
                schema=result.schema(),
                base_schema=result.base_schema(),
                schema_source=result._schema_source(),
                target_version=target_version,
                created_at=previous_meta.created_at if previous_meta else now,
                updated_at=now,
                content_hash=content_hash,
                schema_hash=schema_hash,
                config_hash=config_hash,
                source_hash=source_hash,
                change_summary=change_summary,
            )
            self.offline_store.write_metadata(feature.name, feature_metadata)

            result_path = self.offline_store.path_for(
                feature.name, target_version
            )

            if preview:
                log.print_feature_preview(
                    f"{feature.name} v{target_version}",
                    result_df,
                    max_rows=preview_rows,
                )

            results[feature.name] = result_path

        if failed_features:
            logger.warning(
                f"Build completed with validation failures: {failed_features}"
            )

        return results

    def _build_online(
        self,
        feature_names: list[str] | None,
        tag_names: list[str] | None,
        preview: bool,
        preview_rows: int,
    ) -> dict[str, int]:
        """
        Build features to the online store.

        Extracts the latest value per entity from each feature and writes
        to the configured online store. Requires timestamp column to determine
        "latest" values.

        Args:
            feature_names: Specific features to materialize
            tag_names: Specific features to materialize by tag
            preview: Display preview of data being written
            preview_rows: Number of preview rows to show

        Returns:
            Dictionary mapping feature names to record counts written

        Raises:
            ValueError: If no online_store is configured
        """
        if self.online_store is None:
            raise ValueError(
                "Cannot build to online store: no online_store configured. "
                "Pass online_store=RedisStore(...) to Definitions()."
            )

        selected_features = self._resolve_features_to_build(
            feature_names, tag_names
        )
        results: dict[str, int] = {}

        for feature in selected_features:
            # Execute feature computation
            engine = self._get_engine_for_feature(feature)
            result = engine.execute(feature)
            result_df = result.to_polars()

            # Extract latest values per entity
            latest_df = self._extract_latest_per_entity(feature, result_df)

            if preview:
                log.print_feature_preview(
                    f"{feature.name} (online)",
                    latest_df,
                    max_rows=preview_rows,
                )

            # Write to online store
            records = latest_df.to_dicts()
            count = self.online_store.write_batch(
                feature_name=feature.name,
                records=records,
                entity_key_columns=feature.keys,
            )

            logger.info(
                f"Wrote {count} records to online store: {feature.name}"
            )
            results[feature.name] = count

        return results

    def _extract_latest_per_entity(
        self,
        feature: Feature,
        df: pl.DataFrame,
    ) -> pl.DataFrame:
        """
        Extract the latest row per entity from a feature DataFrame.

        If the feature has a timestamp column, sorts by timestamp descending
        and takes the first row per entity key combination. The timestamp
        column is dropped from the output since online stores only need
        entity keys and feature values.

        Args:
            feature: Feature definition with keys and timestamp info
            df: Feature DataFrame with computed values

        Returns:
            DataFrame with one row per unique entity (without timestamp)
        """
        if feature.timestamp:
            # Sort by timestamp descending, take first per entity
            result = (
                df.sort(feature.timestamp, descending=True)
                .group_by(feature.keys)
                .first()
                .drop(feature.timestamp)
            )
        else:
            # No timestamp - take last row per entity
            result = df.group_by(feature.keys).last()

        return result

    def _determine_version(
        self,
        feature: Feature,
        previous_meta: manifest.FeatureMetadata | None,
    ) -> tuple[str, version.ChangeSummary]:
        """
        Determine next version based on change detection.

        Args:
            feature: Feature being built
            previous_meta: Metadata from previous version (None if first build)

        Returns:
            Tuple of (version_string, ChangeSummary)
        """
        if previous_meta is None:
            # First build
            return "1.0.0", version.build_change_summary(
                version.ChangeType.INITIAL, None, []
            )

        # Load and process to get current schema (before metrics)
        engine = self._get_engine_for_feature(feature)
        source_df = engine._load_source(feature.source_obj)

        if isinstance(source_df, duckdb.DuckDBPyRelation):
            source_df_ = source_df.to_arrow_table()
            source_df = pl.from_arrow(source_df_)

        preview_df = feature(source_df)

        if isinstance(preview_df, pl.LazyFrame):
            preview_df = preview_df.collect()

        current_columns = list(preview_df.columns)
        previous_columns = [c.name for c in previous_meta.columns]

        # Compute current hashes using canonical types for cross-engine consistency
        current_schema_columns = [
            manifest.ColumnMetadata(
                name=c,
                dtype=types_.from_polars(
                    preview_df.schema[c]
                ).to_canonical_string(),
            )
            for c in current_columns
        ]
        current_schema_hash = version.compute_schema_hash(
            current_schema_columns
        )
        current_config_hash = version.compute_config_hash(
            keys=feature.keys,
            timestamp=feature.timestamp,
            interval=feature.interval,
            metrics_config=self._serialize_metrics_config(feature.metrics),
        )

        # Detect change type
        change_type = version.detect_change_type(
            previous_columns=previous_columns,
            current_columns=current_columns,
            previous_schema_hash=previous_meta.schema_hash,
            current_schema_hash=current_schema_hash,
            previous_config_hash=previous_meta.config_hash,
            current_config_hash=current_config_hash,
        )

        # Determine target version
        if change_type == version.ChangeType.INITIAL:
            target_version = "1.0.0"
        else:
            target_version = version.bump_version(
                previous_meta.version, change_type
            )

        change_summary = version.build_change_summary(
            change_type, previous_columns, current_columns
        )

        return target_version, change_summary

    def _serialize_metrics_config(
        self, metrics: list[metrics_.MetricKind] | None
    ) -> list[dict[str, Any]]:
        """
        Serialize metrics configuration for hashing.

        Args:
            metrics: List of metric configurations

        Returns:
            List of serialized metric dictionaries
        """
        if not metrics:
            return []

        configs = []
        for metric in metrics:
            if hasattr(metric, "to_dict"):
                configs.append(metric.to_dict())
            else:
                # Fallback: use repr
                configs.append({"repr": repr(metric)})
        return configs

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
        selected_features = self._resolve_features_to_build(
            feature_names, tag_names
        )
        results: list[validation_.FeatureValidationResult] = []

        for feature in selected_features:
            if not feature.validators:
                logger.debug(f"Skipping {feature.name} (no validators)")
                continue

            try:
                # Load and process data (without metrics)
                engine = self._get_engine_for_feature(feature)
                source_df = engine._load_source(feature.source_obj)
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

    def sync(
        self,
        feature_names: list[str] | None = None,
        dry_run: bool = False,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Rebuild features that have metadata but no data.

        Scans the store for features with metadata (.meta.json) but no data
        (data.parquet missing). For each such feature, verifies source data
        hasn't changed, then rebuilds the feature.

        This is used for the Git workflow where teammates share metadata
        but not data files. After pulling metadata, running sync will
        rebuild the features locally from source data.

        Args:
            feature_names: Specific features to sync. Defaults to None (all).
            dry_run: If True, only report what would be synced. Defaults to False.
            force: If True, rebuild even if source data hash differs. Defaults to False.

        Returns:
            Dictionary with:
                - needs_sync: List of feature names that need syncing
                - source_changed: List of feature names with changed source data
                - synced: List of feature names that were synced (empty if dry_run)

        Raises:
            SourceDataChangedError: If source data has changed and force=False

        Example:
            # Check what needs syncing
            result = defs.sync(dry_run=True)
            print(result["needs_sync"])

            # Rebuild missing data
            result = defs.sync()
            print(f"Synced {len(result['synced'])} features")
        """
        needs_sync: list[str] = []
        source_changed: list[str] = []
        synced: list[str] = []

        # Get list of features to check
        features_to_check = (
            [self._get_feature(name) for name in feature_names]
            if feature_names
            else self.list_features()
        )

        for feature in features_to_check:
            # Read metadata for latest version
            metadata = self.offline_store.read_metadata(feature.name)
            if metadata is None:
                # No metadata - nothing to sync
                continue

            latest_version = self.offline_store.get_latest_version(feature.name)
            if latest_version is None:
                continue

            # Check if data file exists
            if self.offline_store.exists(feature.name, latest_version):
                # Data exists - nothing to sync
                continue

            # Metadata exists but data doesn't - needs sync
            needs_sync.append(feature.name)

            # Check source hash
            if metadata.source_hash:
                try:
                    current_source_hash = version.compute_source_hash(
                        feature.source_path
                    )
                    if current_source_hash != metadata.source_hash:
                        source_changed.append(feature.name)
                        if not force and not dry_run:
                            raise errors.SourceDataChangedError(
                                feature_name=feature.name,
                                expected_hash=metadata.source_hash,
                                current_hash=current_source_hash,
                                source_path=feature.source_path,
                            )
                except FileNotFoundError:
                    # Source file not found - can't sync
                    logger.warning(
                        f"Source file not found for {feature.name}: {feature.source_path}"
                    )
                    continue

        if dry_run:
            return {
                "needs_sync": needs_sync,
                "source_changed": source_changed,
                "synced": [],
            }

        # Rebuild features that need syncing
        for feature_name in needs_sync:
            if feature_name in source_changed and not force:
                # Skip - source changed and not forcing
                continue

            # Get the version from metadata
            metadata = self.offline_store.read_metadata(feature_name)
            if metadata is None:
                continue

            # Rebuild with the same version
            try:
                self.build(
                    feature_names=[feature_name],
                    feature_version=metadata.version,
                    force=True,
                    preview=False,
                )
                synced.append(feature_name)
                logger.info(f"Synced {feature_name} v{metadata.version}")
            except Exception as e:
                logger.error(f"Failed to sync {feature_name}: {e}")

        return {
            "needs_sync": needs_sync,
            "source_changed": source_changed,
            "synced": synced,
        }

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
            logger.debug(
                f"Invalid tags: {invalid_tags}. Available: {available_tags}"
            )
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
            raise TypeError(
                f"Expected Feature or module, got {type(obj).__name__}"
            )

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
        write_metadata: dict[str, Any],
        schema: dict[str, str],
        base_schema: dict[str, str] | None = None,
        schema_source: str = "polars",
        target_version: str = "1.0.0",
        created_at: str = "",
        updated_at: str = "",
        content_hash: str = "",
        schema_hash: str = "",
        config_hash: str = "",
        source_hash: str = "",
        change_summary: version.ChangeSummary | None = None,
    ) -> manifest.FeatureMetadata:
        """
        Build FeatureMetadata from feature definition and write results.

        Args:
            feature: The Feature definition object
            write_metadata: Metadata returned from store.write()
            schema: Column name to dtype mapping from result (final schema after metrics)
            base_schema: Column name to dtype mapping before metrics were applied
            schema_source: Engine source for type normalization ("polars" or "duckdb")
            target_version: Semantic version string
            created_at: ISO 8601 timestamp when version was created
            updated_at: ISO 8601 timestamp of this build
            content_hash: Hash of parquet file content
            schema_hash: Hash of column schema
            config_hash: Hash of feature configuration
            source_hash: Hash of source data file for reproducibility
            change_summary: Summary of changes from previous version

        Returns:
            FeatureMetadata object ready for persistence
        """
        base_columns, feature_columns = manifest.derive_column_metadata(
            feature, schema, base_schema, schema_source
        )

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        return manifest.FeatureMetadata(
            name=feature.name,
            version=target_version,
            path=write_metadata["path"],
            entity=feature.keys[0],
            keys=feature.keys,
            source=feature.source_path,
            row_count=write_metadata["row_count"],
            created_at=created_at or now,
            updated_at=updated_at or now,
            content_hash=content_hash,
            schema_hash=schema_hash,
            config_hash=config_hash,
            source_hash=source_hash,
            timestamp=feature.timestamp,
            interval=feature.interval,
            columns=base_columns,
            features=feature_columns,
            tags=feature.tags or [],
            description=feature.description,
            change_summary=change_summary.to_dict() if change_summary else None,
        )
