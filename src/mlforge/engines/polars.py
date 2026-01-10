"""
Polars-based execution engine.

This module provides the PolarsEngine implementation for in-memory
feature computation using Polars DataFrames.
"""

import warnings
from typing import TYPE_CHECKING, override

import polars as pl

import mlforge.compilers as compilers
import mlforge.engines.base as base
import mlforge.errors as errors
import mlforge.results as results_
import mlforge.sources as sources
import mlforge.timestamps as timestamps
import mlforge.utils as utils
import mlforge.validation as validation

if TYPE_CHECKING:
    import mlforge.core as core

# Threshold for warning about large dataset performance
# When row_count * unique_entities exceeds this, warn about using DuckDB
LARGE_DATASET_THRESHOLD = 10_000_000


class PolarsEngine(base.Engine):
    """
    Polars-based execution engine.

    Executes features using Polars for in-memory computation. Supports
    both simple transformations and complex rolling aggregations.

    Attributes:
        _compiler: Polars compiler for metric specifications
    """

    def __init__(self) -> None:
        """Initialize Polars engine with compiler."""
        self._compiler = compilers.PolarsCompiler()

    @override
    def execute(self, feature: "core.Feature") -> results_.ResultKind:
        """
        Execute a feature using Polars.

        Loads source data, applies the feature transformation function,
        validates entity keys and timestamps, then computes any specified
        metrics over rolling windows.

        Args:
            feature: Feature definition to execute

        Returns:
            PolarsResult wrapping the computed DataFrame

        Raises:
            ValueError: If entity keys or timestamp columns are missing
        """
        # load data from source
        source_df = self._load_source(feature.source_obj)

        # Generate surrogate keys for entities that require it
        if feature.entities:
            source_df = self._apply_entity_keys(source_df, feature.entities)

        # process dataframe with function code
        processed_df = feature(source_df)
        columns = processed_df.collect_schema().names()

        # Capture base schema before metrics are applied
        base_schema = {
            name: str(dtype)
            for name, dtype in processed_df.collect_schema().items()
        }

        missing_keys = [key for key in feature.keys if key not in columns]
        if missing_keys:
            raise ValueError(
                f"Entity keys {missing_keys} not found in dataframe"
            )

        # run validators on processed dataframe (before metrics)
        if feature.validators:
            self._run_validators(feature.name, processed_df, feature.validators)

        if not feature.metrics:
            return results_.PolarsResult(processed_df, base_schema=base_schema)

        # Parse timestamp column (auto-detect format if needed)
        if feature.timestamp is None:
            raise ValueError(
                "Timestamp is required when using metrics. "
                "Please set timestamp parameter in @feature decorator."
            )

        # Collect LazyFrame for timestamp parsing
        if isinstance(processed_df, pl.LazyFrame):
            processed_df = processed_df.collect()

        processed_df, ts_column = timestamps.parse_timestamp_column(
            processed_df, feature.timestamp
        )

        if ts_column not in processed_df.columns:
            raise ValueError(
                f"Timestamp column '{ts_column}' not found in dataframe"
            )

        if not feature.interval:
            raise ValueError(
                "Aggregation interval is not specified. Please set interval parameter in @feature decorator."
            )

        # Warn if dataset is large - Polars is not optimized for rolling windows on large data
        self._warn_if_large_dataset(feature.name, processed_df, feature.keys)

        # Use first tag if available, otherwise fall back to feature name
        tag = feature.tags[0] if feature.tags else feature.name

        ctx = compilers.ComputeContext(
            keys=feature.keys,
            timestamp=ts_column,
            interval=feature.interval,
            dataframe=processed_df,
            tag=tag,
        )

        # compute metrics and join results
        results: list[pl.DataFrame | pl.LazyFrame] = []
        for metric in feature.metrics:
            metric.validate(columns)
            result = self._compiler.compile(metric, ctx)
            results.append(result)

        if len(results) == 1:
            return results_.PolarsResult(
                results.pop(0), base_schema=base_schema
            )

        # join results
        result: pl.DataFrame | pl.LazyFrame = results.pop(0)
        for df in results:
            result = result.join(df, on=[*ctx.keys, ctx.timestamp], how="outer")

        return results_.PolarsResult(result, base_schema=base_schema)

    def _load_source(self, source: sources.Source) -> pl.DataFrame:
        """
        Load source data from Source object.

        Args:
            source: Source object specifying path and format

        Returns:
            DataFrame containing source data

        Raises:
            ValueError: If file format is not supported
        """
        path = source.path
        fmt = source.format

        match fmt:
            case sources.ParquetFormat():
                kwargs = {}
                if fmt.columns:
                    kwargs["columns"] = fmt.columns
                if fmt.row_groups:
                    kwargs["row_groups"] = fmt.row_groups
                return pl.read_parquet(path, **kwargs)

            case sources.CSVFormat():
                return pl.read_csv(
                    path,
                    separator=fmt.delimiter,
                    has_header=fmt.has_header,
                    quote_char=fmt.quote_char,
                    skip_rows=fmt.skip_rows,
                )

            case sources.DeltaFormat():
                kwargs = {}
                if fmt.version is not None:
                    kwargs["version"] = fmt.version
                return pl.read_delta(path, **kwargs)

            case _:
                raise ValueError(
                    f"Unsupported source format: {type(fmt).__name__}"
                )

    def _apply_entity_keys(
        self,
        df: pl.DataFrame,
        entities: list,
    ) -> pl.DataFrame:
        """
        Generate surrogate keys for entities that require it.

        For each entity with from_columns specified, generates a surrogate
        key column using the surrogate_key() function.

        Args:
            df: Source DataFrame
            entities: List of Entity objects

        Returns:
            DataFrame with generated key columns added
        """
        for entity in entities:
            if entity.requires_generation:
                # Entity has from_columns - generate surrogate key
                df = df.with_columns(
                    utils.surrogate_key(*entity.from_columns).alias(
                        entity.join_key
                    )
                )
        return df

    def _warn_if_large_dataset(
        self,
        feature_name: str,
        df: pl.DataFrame | pl.LazyFrame,
        keys: list[str],
    ) -> None:
        """
        Warn if dataset is large and rolling windows may be slow.

        Polars is not optimized for rolling window aggregations on large datasets
        because it cannot push filter predicates into joins. DuckDB's SQL optimizer
        handles this much better.

        Args:
            feature_name: Name of the feature being processed
            df: DataFrame to check
            keys: Entity key columns
        """
        # Collect LazyFrame if needed to check size
        if isinstance(df, pl.LazyFrame):
            check_df = df.collect()
        else:
            check_df = df

        row_count = check_df.height

        # Estimate complexity: rows * unique entities (approximates join explosion)
        # For a single key, use n_unique; for multiple keys, use the product
        unique_entities = 1
        for key in keys:
            unique_entities *= check_df[key].n_unique()

        estimated_complexity = row_count * unique_entities

        if estimated_complexity > LARGE_DATASET_THRESHOLD:
            warnings.warn(
                f"Feature '{feature_name}' has {row_count:,} rows and {unique_entities:,} "
                f"unique entities. Polars may be slow for rolling window aggregations "
                f"on large datasets. Consider using engine='duckdb' for better performance. "
                f"Set default_engine='duckdb' in Definitions or engine='duckdb' in @feature.",
                UserWarning,
                stacklevel=4,
            )

    def _run_validators(
        self,
        feature_name: str,
        df: pl.DataFrame | pl.LazyFrame,
        validators: dict,
    ) -> None:
        """
        Run validators on the processed DataFrame.

        Args:
            feature_name: Name of the feature being validated
            df: DataFrame to validate
            validators: Mapping of column names to validator lists

        Raises:
            FeatureValidationError: If any validation fails
        """
        # Collect LazyFrame if needed for validation
        if isinstance(df, pl.LazyFrame):
            df = df.collect()

        results = validation.validate_dataframe(df, validators)
        failures = [
            (
                r.column,
                r.validator_name,
                r.result.message or "Validation failed",
            )
            for r in results
            if not r.result.passed
        ]

        if failures:
            raise errors.FeatureValidationError(
                feature_name=feature_name,
                failures=failures,
            )
