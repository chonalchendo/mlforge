from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, override

import polars as pl

import mlforge.compilers as compilers
import mlforge.results as results_

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

        missing_keys = [key for key in feature.keys if key not in columns]
        if missing_keys:
            raise ValueError(f"Entity keys {missing_keys} not found in dataframe")

        if not feature.metrics:
            return results_.PolarsResult(processed_df)

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
        results: list[pl.DataFrame] = []
        for metric in feature.metrics:
            metric.validate(columns)
            result = self._compiler.compile(metric, ctx)
            results.append(result)

        if len(results) == 1:
            return results_.PolarsResult(results.pop(0))

        # join results
        result: pl.DataFrame = results.pop(0)
        for df in results:
            result = result.join(df, on=[*ctx.keys, ctx.timestamp], how="outer")

        return results_.PolarsResult(result)

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


EngineKind = PolarsEngine
