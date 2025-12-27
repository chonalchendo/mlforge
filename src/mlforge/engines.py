from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, override

import polars as pl

import mlforge.compilers as compilers
import mlforge.errors as errors
import mlforge.results as results_
import mlforge.validation as validation

if TYPE_CHECKING:
    import mlforge.core as core


class Engine(ABC):
    """
    Abstract base class for feature computation engines.

    Engines are responsible for loading source data, executing feature
    transformations, and computing metrics.
    """

    @abstractmethod
    def execute(self, feature: "core.Feature") -> results_.ResultKind:
        """
        Execute a feature computation.

        Args:
            feature: Feature definition to execute

        Returns:
            Engine-specific result wrapper containing computed data
        """
        ...


class PolarsEngine(Engine):
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
        source_df = self._load_source(feature.source)

        # process dataframe with function code
        processed_df = feature(source_df)
        columns = processed_df.collect_schema().names()

        # Capture base schema before metrics are applied
        base_schema = {
            name: str(dtype) for name, dtype in processed_df.collect_schema().items()
        }

        missing_keys = [key for key in feature.keys if key not in columns]
        if missing_keys:
            raise ValueError(f"Entity keys {missing_keys} not found in dataframe")

        # run validators on processed dataframe (before metrics)
        if feature.validators:
            self._run_validators(feature.name, processed_df, feature.validators)

        if not feature.metrics:
            return results_.PolarsResult(processed_df, base_schema=base_schema)

        if feature.timestamp not in columns:
            raise ValueError(
                f"Timestamp column '{feature.timestamp}' not found in dataframe"
            )

        if not feature.interval:
            raise ValueError(
                "Aggregation interval is not specified. Please set interval parameter in @feature decorator."
            )

        # Use first tag if available, otherwise fall back to feature name
        tag = feature.tags[0] if feature.tags else feature.name

        ctx = compilers.ComputeContext(
            keys=feature.keys,
            timestamp=feature.timestamp,
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
            return results_.PolarsResult(results.pop(0), base_schema=base_schema)

        # join results
        result: pl.DataFrame | pl.LazyFrame = results.pop(0)
        for df in results:
            result = result.join(df, on=[*ctx.keys, ctx.timestamp], how="outer")

        return results_.PolarsResult(result, base_schema=base_schema)

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
            (r.column, r.validator_name, r.result.message or "Validation failed")
            for r in results
            if not r.result.passed
        ]

        if failures:
            raise errors.FeatureValidationError(
                feature_name=feature_name,
                failures=failures,
            )


EngineKind = PolarsEngine
