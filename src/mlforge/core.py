from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Literal, Protocol

import polars as pl
from loguru import logger

import mlforge.engines as engines
import mlforge.entities as entities_
import mlforge.errors as errors
import mlforge.incremental as incremental
import mlforge.logging as log
import mlforge.manifest as manifest
import mlforge.metrics as metrics_
import mlforge.profiles as profiles_
import mlforge.results as results_
import mlforge.retrieval as retrieval_
import mlforge.sources as sources
import mlforge.stores as stores
import mlforge.timestamps as timestamps_
import mlforge.types as types_
import mlforge.utils as utils
import mlforge.validation as validation_
import mlforge.validators as validators_
import mlforge.version as version

WindowFunc = Literal["1h", "1d", "7d", "30d"]


class FeatureFunction(Protocol):
    """
    Protocol defining the signature for feature transformation functions.

    Engine-agnostic: accepts Polars DataFrame, DuckDB Relation, or PySpark DataFrame.
    The actual type depends on which engine executes the feature.
    """

    __name__: str

    def __call__(self, df: Any) -> Any: ...


@dataclass
class BuildResult:
    """
    Result of a build operation containing paths and statistics.

    Attributes:
        paths: Dictionary mapping feature names to storage paths
        built: Number of features that were built
        skipped: Number of features skipped (already exist)
        failed: Number of features that failed validation
    """

    paths: dict[str, Path | str]
    built: int
    skipped: int
    failed: int


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
    entities: list[entities_.Entity] | None
    tags: list[str] | None
    timestamp: str | timestamps_.Timestamp | None
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

    @property
    def timestamp_column(self) -> str | None:
        """Return the timestamp column name, extracting from Timestamp if needed."""
        return timestamps_.normalize_timestamp(self.timestamp)

    def __call__(self, *args, **kwargs) -> pl.DataFrame:
        """
        Execute the feature transformation function.

        All arguments are passed through to the underlying feature function.

        Returns:
            DataFrame with computed feature columns
        """
        return self.fn(*args, **kwargs)


def feature(
    source: str | sources.Source,
    keys: list[str] | None = None,
    entities: list[entities_.Entity] | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    timestamp: str | timestamps_.Timestamp | None = None,
    interval: str | timedelta | None = None,
    metrics: list[metrics_.MetricKind] | None = None,
    validators: dict[str, list[validators_.Validator]] | None = None,
    engine: Literal["polars", "duckdb", "pyspark"] | None = None,
) -> Callable[[FeatureFunction], Feature]:
    """
    Decorator that marks a function as a feature definition.

    Transforms a function into a Feature object that can be registered
    with Definitions and materialized to storage.

    Args:
        source: Path to source data file or Source object. Can be:
            - A string path: "data/transactions.parquet"
            - A Source object: Source("s3://bucket/data.parquet")
            - A Source with format options: Source("data.csv", format=CSVFormat(delimiter="|"))
        keys: Column names that uniquely identify entities. Either keys or entities required.
        entities: Entity definitions with optional surrogate key generation.
            When provided, keys are derived from entity join_keys automatically.
        description: Human-readable feature description. Defaults to None.
        tags: Tags to group feature with other features. Defaults to None.
        timestamp: Timestamp configuration for temporal features. Can be:
            - A string column name (format auto-detected)
            - A Timestamp object with explicit format/alias
            Defaults to None.
        interval: Time interval for rolling computations (e.g., "1d" or timedelta(days=1)). Defaults to None.
        metrics: Aggregation metrics like Rolling for time-based features. Defaults to None.
        validators: Column validators to run before metrics are computed. Defaults to None.
            Mapping of column names to lists of validator functions.
        engine: Compute engine to use for this feature. Defaults to None (uses Definitions default).
            Options: "polars" (default), "duckdb" (for large datasets).

    Returns:
        Decorator function that converts a function into a Feature

    Example:
        # Using keys (traditional style)
        @feature(
            keys=["user_id"],
            source="data/transactions.parquet",
            tags=['users'],
            timestamp="transaction_time",
            description="User spending statistics",
        )
        def user_spend_stats(df):
            return df.group_by("user_id").agg(...)

        # Using entities (v0.6.0+) - with automatic surrogate key generation
        user = Entity(name="user", join_key="user_id", from_columns=["first", "last", "dob"])

        @feature(
            source="data/transactions.parquet",
            entities=[user],  # Engine generates user_id from first, last, dob
        )
        def user_spend(df):
            return df.select("user_id", "amount")  # user_id already exists

    Raises:
        ValueError: If neither keys nor entities is provided
    """
    # Validate that either keys or entities is provided
    if keys is None and entities is None:
        raise ValueError("Either 'keys' or 'entities' must be provided")

    # Derive keys from entities if not explicitly provided
    derived_keys: list[str] = []
    if keys is not None:
        derived_keys = keys
    elif entities is not None:
        for entity in entities:
            derived_keys.extend(entity.key_columns)
        # Remove duplicates while preserving order
        seen: set[str] = set()
        derived_keys = [
            k for k in derived_keys if not (k in seen or seen.add(k))
        ]
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
            keys=derived_keys,
            entities=entities,
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
        from mlforge.stores import RedisStore
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

        # Using profiles from mlforge.yaml
        defs = Definitions(
            name="my-project",
            features=[my_features],
            profile="staging",  # Load stores from mlforge.yaml
        )
    """

    def __init__(
        self,
        name: str,
        features: list[Feature | ModuleType],
        offline_store: stores.OfflineStoreKind | None = None,
        online_store: stores.OnlineStore | stores.OnlineStoreKind | None = None,
        profile: str | None = None,
        default_engine: Literal["polars", "duckdb", "pyspark"] = "duckdb",
    ) -> None:
        """
        Initialize a feature store registry.

        Store resolution order:
        1. Explicit offline_store/online_store parameters (highest priority)
        2. Profile from profile parameter
        3. Profile from MLFORGE_PROFILE environment variable
        4. Profile from default_profile in mlforge.yaml

        Args:
            name: Project name
            features: List of Feature objects or modules containing features
            offline_store: Storage backend for materialized features. If None,
                loads from profile configuration.
            online_store: Optional online store for real-time serving. Defaults to None.
                If None and profile has online_store configured, loads from profile.
            profile: Profile name to load from mlforge.yaml. If None, uses
                MLFORGE_PROFILE env var or default_profile from config.
            default_engine: Default execution engine for features without explicit engine.
                Defaults to "duckdb" which is optimized for large datasets with rolling
                windows. Use "polars" for small datasets or when you prefer staying in
                the Polars ecosystem. Individual features can override this via the
                engine parameter in the @feature decorator.

        Example:
            # Explicit stores (traditional)
            defs = Definitions(
                name="fraud-detection",
                features=[user_features, transaction_features],
                offline_store=LocalStore("./features"),
                online_store=RedisStore(host="localhost"),
            )

            # Using profiles from mlforge.yaml
            defs = Definitions(
                name="fraud-detection",
                features=[user_features],
                profile="staging",  # Load from mlforge.yaml
            )

            # Auto-detect profile (uses MLFORGE_PROFILE or default_profile)
            defs = Definitions(
                name="fraud-detection",
                features=[user_features],
                # Stores loaded from mlforge.yaml automatically
            )

        Raises:
            ProfileError: If no offline_store provided and no mlforge.yaml found,
                or if profile not found in config.
        """
        self.name = name
        self.features: dict[str, Feature] = {}
        self.default_engine = default_engine
        self._engines: dict[str, engines.EngineKind] = {}

        # Indexes for O(1) lookups
        self._entities: dict[str, entities_.Entity] = {}
        self._sources: dict[str, sources.Source] = {}
        self._entity_to_features: dict[str, list[str]] = {}
        self._source_to_features: dict[str, list[str]] = {}

        # Resolve stores from profile if not explicitly provided
        resolved_offline: stores.Store
        resolved_online: stores.OnlineStore | None = online_store

        if offline_store is not None:
            # Explicit stores win - use as provided
            resolved_offline = offline_store
        else:
            # Try to load from profile
            profile_config = profiles_.load_profile(profile)
            resolved_offline = profile_config.offline_store.create()
            # Only load online store from profile if not explicitly provided
            if online_store is None and profile_config.online_store is not None:
                resolved_online = profile_config.online_store.create()

        self.offline_store = resolved_offline
        self.online_store = resolved_online

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
            case "pyspark":
                from mlforge.engines import PySparkEngine

                self._engines[engine] = PySparkEngine()
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
        schedule_names: list[str] | None = None,
        feature_version: str | None = None,
        force: bool = False,
        preview: bool = True,
        preview_rows: int = 5,
        online: bool = False,
        start: str | datetime | None = None,
        end: str | datetime | None = None,
        last: str | None = None,
        full_refresh: bool = False,
    ) -> BuildResult:
        """
        Compute and persist features to offline storage with versioning.

        Loads source data, applies feature transformations, validates results,
        and writes to the configured storage backend. Automatically determines
        the appropriate version based on schema and configuration changes.

        Supports incremental builds that only process new data since the last
        build, significantly improving build times for large datasets.

        Args:
            feature_names: Specific features to materialize. Defaults to None (all).
            tag_names: Specific features to materialize by tag. Defaults to None (all).
            schedule_names: Schedule tags to filter by (e.g., ["daily", "hourly"]).
                Features are selected if any of their tags match these schedule names.
                Defaults to None (all).
            feature_version: Explicit version override (e.g., "2.0.0"). If None, auto-detects.
            force: Overwrite existing features. Defaults to False.
            preview: Display preview of materialized data. Defaults to True.
            preview_rows: Number of preview rows to show. Defaults to 5.
            online: Write to online store instead of offline. Defaults to False.
                Requires online_store to be configured. Extracts latest values
                per entity and writes to the online store.
            start: Start of date range for incremental build (e.g., "2026-01-01").
                Only processes data from this timestamp onwards.
            end: End of date range for incremental build (e.g., "2026-01-15").
                Only processes data up to (but not including) this timestamp.
            last: Process data from the last N period (e.g., "7d", "24h").
                Cannot be used with start/end.
            full_refresh: Force full rebuild, ignoring incremental state.
                Defaults to False.

        Returns:
            BuildResult containing paths and build statistics (built, skipped, failed counts)

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

            # Incremental build - process last 7 days
            paths = defs.build(feature_names=["user_spend"], last="7d")

            # Incremental build - specific date range
            paths = defs.build(feature_names=["user_spend"], start="2026-01-01", end="2026-01-15")

            # Force full refresh
            paths = defs.build(feature_names=["user_spend"], full_refresh=True)
        """
        if online:
            online_results = self._build_online(
                feature_names, tag_names, schedule_names, preview, preview_rows
            )
            return BuildResult(
                paths={k: str(v) for k, v in online_results.items()},
                built=len(online_results),
                skipped=0,
                failed=0,
            )

        selected_features = self._resolve_features_to_build(
            feature_names, tag_names, schedule_names
        )
        results: dict[str, Path | str] = {}
        failed_features: list[str] = []
        skipped_count = 0

        for feature in selected_features:
            # Get previous metadata for change detection
            previous_meta = self.offline_store.read_metadata(feature.name)

            # Determine if this is an incremental build
            is_incremental = self._should_build_incrementally(
                feature=feature,
                previous_meta=previous_meta,
                start=start,
                end=end,
                last=last,
                full_refresh=full_refresh,
            )

            # Resolve date range for incremental builds
            incremental_meta: manifest.IncrementalMetadata | None = None
            start_dt: datetime | None = None
            end_dt: datetime | None = None

            if is_incremental:
                prev_incremental = (
                    previous_meta.incremental if previous_meta else None
                )
                start_dt, end_dt = incremental.resolve_date_range(
                    start=start,
                    end=end,
                    last=last,
                    previous_meta=prev_incremental,
                )
                logger.debug(
                    f"Incremental build for {feature.name}: "
                    f"{start_dt} -> {end_dt}"
                )

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

            # For incremental builds, stay on same version (PATCH)
            if is_incremental and previous_meta:
                target_version = previous_meta.version
                change_summary = version.ChangeSummary(
                    change_type=version.ChangeType.PATCH,
                    reason="incremental_build",
                    details=[],
                )

            # Check if this version already exists (unless force or incremental)
            if (
                not force
                and not is_incremental
                and self.offline_store.exists(feature.name, target_version)
            ):
                log.print_skipped(feature.name, target_version)
                skipped_count += 1
                continue

            if is_incremental:
                log.print_building(f"{feature.name} (incremental)")
            else:
                log.print_building(feature.name)

            try:
                engine = self._get_engine_for_feature(feature)
                result = engine.execute(feature)
            except errors.FeatureValidationError as e:
                logger.error(str(e))
                failed_features.append(feature.name)
                continue

            result_df = result.to_polars()

            # Apply incremental filtering if applicable
            if (
                is_incremental
                and feature.timestamp_column
                and (start_dt or end_dt)
            ):
                lookback = incremental.calculate_lookback_days(feature.interval)
                original_count = len(result_df)
                result_df = incremental.filter_by_timestamp(
                    df=result_df,
                    timestamp_col=feature.timestamp_column,
                    start=start_dt,
                    end=end_dt,
                    lookback_days=lookback,
                )
                logger.debug(
                    f"Filtered {feature.name}: {original_count} -> {len(result_df)} rows"
                )

                # Merge with existing data if available
                if previous_meta and self.offline_store.exists(
                    feature.name, previous_meta.version
                ):
                    existing_df = self.offline_store.read(
                        feature.name, previous_meta.version
                    )
                    result_df = incremental.merge_incremental(
                        existing=existing_df,
                        new_data=result_df,
                        keys=feature.keys,
                        timestamp_col=feature.timestamp_column,
                    )
                    logger.debug(
                        f"Merged {feature.name}: {len(existing_df)} existing + "
                        f"new -> {len(result_df)} total rows"
                    )

                # Build incremental metadata
                now_ts = (
                    datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                )
                processed_until = (
                    end_dt.isoformat().replace("+00:00", "Z")
                    if end_dt
                    else now_ts
                )
                incremental_meta = manifest.IncrementalMetadata(
                    last_build_at=now_ts,
                    processed_until=processed_until,
                    timestamp_column=feature.timestamp_column,
                    lookback_days=lookback,
                )

            self._validate_result(feature.name, result_df)

            # For incremental builds, wrap the merged DataFrame in a result
            # to maintain consistent interface with store.write()
            if is_incremental:
                result = results_.PolarsResult(
                    result_df, base_schema=result.base_schema()
                )

            write_metadata = self.offline_store.write(
                feature.name,
                result,
                feature_version=target_version,
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
                timestamp=feature.timestamp_column,
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
                incremental_meta=incremental_meta,
            )
            self.offline_store.write_metadata(feature.name, feature_metadata)

            result_path = self.offline_store.path_for(
                feature.name, target_version
            )

            log.print_built(feature.name, target_version, str(result_path))

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

        return BuildResult(
            paths=results,
            built=len(results),
            skipped=skipped_count,
            failed=len(failed_features),
        )

    def _build_online(
        self,
        feature_names: list[str] | None,
        tag_names: list[str] | None,
        schedule_names: list[str] | None,
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
            schedule_names: Schedule tags to filter by
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
            feature_names, tag_names, schedule_names
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
        ts_col = feature.timestamp_column
        if ts_col:
            # Sort by timestamp descending, take first per entity
            result = (
                df.sort(ts_col, descending=True)
                .group_by(feature.keys)
                .first()
                .drop(ts_col)
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
        # Always use Polars for schema analysis (version detection is engine-agnostic)
        from mlforge.engines import PolarsEngine

        polars_engine = PolarsEngine()
        source_df = polars_engine._load_source(feature.source_obj)

        # Ensure we have a Polars DataFrame
        if not isinstance(source_df, pl.DataFrame):
            raise TypeError("Expected Polars DataFrame from source")

        # Apply entity key generation if needed (using Polars for consistency)
        if feature.entities:
            source_df = utils.apply_entity_keys(source_df, feature.entities)

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
            timestamp=feature.timestamp_column,
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

    def _should_build_incrementally(
        self,
        feature: Feature,
        previous_meta: manifest.FeatureMetadata | None,
        start: str | datetime | None,
        end: str | datetime | None,
        last: str | None,
        full_refresh: bool,
    ) -> bool:
        """
        Determine if a feature should be built incrementally.

        Incremental builds are used when:
        1. full_refresh is False
        2. Incremental parameters are provided (start/end/last)
        3. Feature has a timestamp column
        4. No breaking schema changes

        Args:
            feature: Feature being built
            previous_meta: Metadata from previous build
            start: Start date parameter
            end: End date parameter
            last: Last duration parameter
            full_refresh: Whether full refresh was explicitly requested

        Returns:
            True if incremental build should be used
        """
        # Explicit full refresh requested
        if full_refresh:
            return False

        # No incremental parameters provided
        if start is None and end is None and last is None:
            return False

        # Feature has no timestamp column - can't filter incrementally
        if not feature.timestamp_column:
            logger.warning(
                f"Feature {feature.name} has no timestamp column, "
                "using full refresh"
            )
            return False

        # First build - no previous data to merge with
        if previous_meta is None:
            logger.debug(f"First build for {feature.name}, using full refresh")
            return False

        return True

    def validate(
        self,
        feature_names: list[str] | None = None,
        tag_names: list[str] | None = None,
        schedule_names: list[str] | None = None,
    ) -> list[validation_.FeatureValidationResult]:
        """
        Run validation checks on features without building.

        Loads source data, applies feature transformations, and runs validators
        on the output. Does not compute metrics or write to storage.

        Args:
            feature_names: Specific features to validate. Defaults to None (all).
            tag_names: Specific features to validate by tag. Defaults to None (all).
            schedule_names: Schedule tags to filter by. Defaults to None (all).

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
            feature_names, tag_names, schedule_names
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
        schedule_names: list[str] | None = None,
    ) -> list[Feature]:
        """
        Resolve which features to build based on parameters.

        Args:
            feature_names: Specific feature names to build, or None for all
            tag_names: Feature tags to filter by, or None
            schedule_names: Schedule tags to filter by (e.g., ["daily", "hourly"]).
                Features are selected if any of their tags match these schedule names.

        Returns:
            List of Feature objects to materialize

        Raises:
            ValueError: If multiple selection parameters are specified,
                       or if any feature/tag name is invalid
        """
        # Check mutual exclusivity
        selection_count = sum(
            [bool(feature_names), bool(tag_names), bool(schedule_names)]
        )
        if selection_count > 1:
            raise ValueError(
                "Cannot specify multiple selection criteria. "
                "Choose one of: --features, --tags, or --schedule."
            )

        if feature_names:
            return [self._get_feature(name) for name in feature_names]

        if tag_names:
            self._validate_tags(tag_names)
            return self.list_features(tags=tag_names)

        if schedule_names:
            # Schedule tags (daily, hourly, weekly) are stored in the feature's tags list,
            # so we reuse the existing tag filtering mechanism
            return self.list_features(tags=schedule_names)

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

    def list_entities(self) -> list[str]:
        """
        List all unique entity names from registered features.

        Returns:
            Sorted list of unique entity names

        Example:
            defs = Definitions(features=[user_spend, merchant_spend], offline_store=store)
            entities = defs.list_entities()  # ["merchant", "user"]
        """
        return sorted(self._entities.keys())

    def list_sources(self) -> list[str]:
        """
        List all unique source names from registered features.

        Returns:
            Sorted list of unique source names

        Example:
            defs = Definitions(features=[user_spend, merchant_spend], offline_store=store)
            sources = defs.list_sources()  # ["transactions"]
        """
        return sorted(self._sources.keys())

    def get_entity(self, name: str) -> entities_.Entity | None:
        """
        Get entity by name from registered features.

        Args:
            name: Entity name to retrieve

        Returns:
            Entity object if found, None otherwise

        Example:
            user_entity = defs.get_entity("user")
            if user_entity:
                print(user_entity.join_key)  # "user_id"
        """
        return self._entities.get(name)

    def get_source(self, name: str) -> sources.Source | None:
        """
        Get source by name from registered features.

        Args:
            name: Source name to retrieve

        Returns:
            Source object if found, None otherwise

        Example:
            txn_source = defs.get_source("transactions")
            if txn_source:
                print(txn_source.path)  # "data/transactions.parquet"
        """
        return self._sources.get(name)

    def features_using_entity(self, entity_name: str) -> list[str]:
        """
        List features that use a specific entity.

        Args:
            entity_name: Name of the entity to search for

        Returns:
            List of feature names using the entity

        Example:
            features = defs.features_using_entity("user")  # ["user_spend", "user_transactions"]
        """
        return self._entity_to_features.get(entity_name, [])

    def features_using_source(self, source_name: str) -> list[str]:
        """
        List features that use a specific source.

        Args:
            source_name: Name of the source to search for

        Returns:
            List of feature names using the source

        Example:
            features = defs.features_using_source("transactions")  # ["user_spend", "merchant_spend"]
        """
        return self._source_to_features.get(source_name, [])

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

        # Index entities
        if feature.entities:
            for entity in feature.entities:
                if entity.name not in self._entities:
                    self._entities[entity.name] = entity
                if entity.name not in self._entity_to_features:
                    self._entity_to_features[entity.name] = []
                self._entity_to_features[entity.name].append(feature.name)

        # Index sources
        if feature.source:
            if isinstance(feature.source, sources.Source):
                source_name = feature.source.name
                if source_name not in self._sources:
                    self._sources[source_name] = feature.source
            else:
                # Legacy string source
                source_name = Path(feature.source).stem
                if source_name not in self._sources:
                    self._sources[source_name] = sources.Source(feature.source)

            if source_name not in self._source_to_features:
                self._source_to_features[source_name] = []
            self._source_to_features[source_name].append(feature.name)

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
        incremental_meta: manifest.IncrementalMetadata | None = None,
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
            incremental_meta: Incremental build state tracking (v0.8.0)

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
            timestamp=feature.timestamp_column,
            interval=feature.interval,
            columns=base_columns,
            features=feature_columns,
            tags=feature.tags or [],
            description=feature.description,
            change_summary=change_summary.to_dict() if change_summary else None,
            incremental=incremental_meta,
        )

    # =========================================================================
    # Feature Retrieval Methods
    # =========================================================================

    def get_online_features(
        self,
        features: list[str],
        entity_df: pl.DataFrame,
        store: stores.OnlineStore | None = None,
    ) -> pl.DataFrame:
        """
        Retrieve features from online store for inference.

        Unlike the standalone get_online_features(), this method automatically
        determines the correct entity keys for each feature from the feature
        definitions. This prevents the common error of using wrong entity keys
        when retrieving multiple features with different entities.

        Args:
            features: List of feature names to retrieve
            entity_df: DataFrame with entity source columns (e.g., first, last, dob
                for user entity). The method will generate surrogate keys automatically
                based on each feature's entity definition.
            store: Optional online store override. Defaults to self.online_store.

        Returns:
            entity_df with feature columns joined. Missing entities have None values.

        Raises:
            ValueError: If no online store configured, or if feature name unknown

        Example:
            # Retrieve multiple features with different entities in one call
            result = defs.get_online_features(
                features=["user_spend", "merchant_spend", "card_velocity"],
                entity_df=request_df,
            )

            # Override store (e.g., for testing)
            result = defs.get_online_features(
                features=["user_spend"],
                entity_df=request_df,
                store=test_store,
            )
        """
        online_store = store or self.online_store
        if online_store is None:
            raise ValueError(
                "No online store configured. Either pass store= parameter "
                "or configure online_store in Definitions/mlforge.yaml."
            )

        # Collect all unique entities needed across requested features
        all_entities: list[entities_.Entity] = []
        seen_entity_names: set[str] = set()

        for feature_name in features:
            if feature_name not in self.features:
                raise ValueError(f"Unknown feature: '{feature_name}'")
            feature = self.features[feature_name]
            if feature.entities:
                for entity in feature.entities:
                    if entity.name not in seen_entity_names:
                        all_entities.append(entity)
                        seen_entity_names.add(entity.name)

        # Apply entity key generation (surrogate keys) for all entities
        result = retrieval_._apply_entities(entity_df, all_entities)

        # Join each feature using only its specific entity keys
        for feature_name in features:
            feature = self.features[feature_name]
            if feature.entities:
                entity_key_columns = retrieval_._get_entity_key_columns(
                    feature.entities
                )
            else:
                entity_key_columns = feature.keys

            result = self._join_online_feature_with_keys(
                result, feature_name, online_store, entity_key_columns
            )

        return result

    def _join_online_feature_with_keys(
        self,
        result: pl.DataFrame,
        feature_name: str,
        online_store: stores.OnlineStore,
        entity_key_columns: list[str],
    ) -> pl.DataFrame:
        """
        Join a single feature from online store using specific entity key columns.

        Delegates to the shared join_online_feature_by_keys() helper in retrieval.

        Args:
            result: Current result DataFrame with entity keys
            feature_name: Name of feature to retrieve
            online_store: Online store instance
            entity_key_columns: Specific entity key columns for this feature

        Returns:
            Result DataFrame with feature columns joined
        """
        return retrieval_.join_online_feature_by_keys(
            result, feature_name, online_store, entity_key_columns
        )

    def get_training_data(
        self,
        features: list[retrieval_.FeatureInput],
        entity_df: pl.DataFrame,
        timestamp: str | None = None,
        store: stores.Store | None = None,
    ) -> pl.DataFrame:
        """
        Retrieve features from offline store for training.

        Unlike the standalone get_training_data(), this method automatically
        determines the correct entity keys for each feature from the feature
        definitions.

        Args:
            features: Feature specifications. Can be:
                - "feature_name" - uses latest version
                - ("feature_name", "1.0.0") - uses specific version
            entity_df: DataFrame with entity source columns
            timestamp: Column in entity_df for point-in-time joins.
                If provided, features with timestamps will be asof-joined.
            store: Optional store override. Defaults to self.offline_store.

        Returns:
            entity_df with feature columns joined

        Raises:
            ValueError: If no store configured, or if feature not found

        Example:
            # Point-in-time correct training data
            training_df = defs.get_training_data(
                features=["user_spend", ("merchant_features", "1.0.0")],
                entity_df=transactions,
                timestamp="event_time",
            )
        """
        offline_store = store or self.offline_store
        if offline_store is None:
            raise ValueError(
                "No store configured. Either pass store= parameter "
                "or configure store in Definitions/mlforge.yaml."
            )

        # Collect all entities from requested features
        feature_names = [
            f
            if isinstance(f, str)
            else f.name
            if isinstance(f, retrieval_.FeatureSpec)
            else f[0]
            for f in features
        ]
        all_entities = self._collect_entities_for_features(feature_names)

        # Delegate to standalone function with collected entities
        return retrieval_.get_training_data(
            features=features,
            entity_df=entity_df,
            store=offline_store,
            entities=all_entities,
            timestamp=timestamp,
        )

    def _collect_entities_for_features(
        self,
        feature_names: list[str],
    ) -> list[entities_.Entity]:
        """
        Collect unique entities from a list of features.

        Args:
            feature_names: List of feature names to collect entities from

        Returns:
            List of unique Entity objects
        """
        entities: list[entities_.Entity] = []
        seen: set[str] = set()

        for name in feature_names:
            if name in self.features:
                feature = self.features[name]
                if feature.entities:
                    for entity in feature.entities:
                        if entity.name not in seen:
                            entities.append(entity)
                            seen.add(entity.name)

        return entities
