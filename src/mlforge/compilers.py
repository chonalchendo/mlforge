from dataclasses import dataclass

import polars as pl
from loguru import logger

import mlforge.metrics as metrics


@dataclass
class ComputeContext:
    """
    Execution context for metric compilation.

    Carries necessary dataframe and metadata for computing metrics
    over rolling time windows.

    Attributes:
        keys: Entity key columns for grouping
        interval: Time interval for rolling computations (e.g., "1h", "1d")
        timestamp: Timestamp column name
        dataframe: Source dataframe to compute metrics on
        tag: Prefix for naming output columns
    """

    keys: list[str]
    interval: str
    timestamp: str
    dataframe: pl.DataFrame
    tag: str


class PolarsCompiler:
    """
    Polars-based metric compiler.

    Translates high-level metric specifications into Polars expressions
    for efficient computation.
    """

    def compile(self, metric: metrics.MetricKind, ctx: ComputeContext) -> pl.DataFrame:
        """
        Compile a metric specification into a Polars computation.

        Args:
            metric: Metric specification to compile
            ctx: Execution context with dataframe and metadata

        Returns:
            DataFrame with computed metrics
        """
        method = getattr(self, f"compile_{type(metric).__name__.lower()}")
        return method(metric, ctx)

    def compile_rolling(
        self, metric: metrics.Rolling, ctx: ComputeContext
    ) -> pl.DataFrame:
        """
        Compile rolling window aggregations.

        Computes aggregations over multiple time windows using Polars
        group_by_dynamic, then joins results with standardized column names.

        Args:
            metric: Rolling window specification
            ctx: Execution context

        Returns:
            DataFrame with all window aggregations joined on entity keys and timestamp
        """
        agg_exprs = self._build_agg_expressions(metric.aggregations)

        window_results: list[pl.DataFrame] = []
        for window in metric.windows:
            logger.debug(f"Calculating for window: {window}")
            result = (
                ctx.dataframe.sort(ctx.timestamp)
                .group_by_dynamic(
                    ctx.timestamp,
                    every=ctx.interval,
                    period=window,
                    by=ctx.keys,
                    closed=metric.closed,
                )
                .agg(agg_exprs)
            )

            result = self._add_window_suffix(
                df=result,
                aggregations=metric.aggregations,
                window=window,
                tag=ctx.tag,
                interval=ctx.interval,
            )

            window_results.append(result)

        return self._join_on_keys(window_results, ctx.keys, ctx.timestamp)

    def _build_agg_expressions(
        self, aggregations: metrics.Aggregations
    ) -> list[pl.Expr]:
        """
        Build Polars aggregation expressions from specifications.

        Args:
            aggregations: Mapping of column names to aggregation types

        Returns:
            List of Polars expressions for computing aggregations
        """
        agg_map = {
            "count": lambda c: pl.col(c).count(),
            "sum": lambda c: pl.col(c).sum(),
            "mean": lambda c: pl.col(c).mean(),
            "min": lambda c: pl.col(c).min(),
            "max": lambda c: pl.col(c).max(),
            "std": lambda c: pl.col(c).std(),
            "median": lambda c: pl.col(c).median(),
        }

        exprs: list[pl.Expr] = []
        for col, agg_types in aggregations.items():
            logger.debug(f"Creating aggreagations for: {col}")
            for agg_type in agg_types:
                logger.debug(f"Creating aggregation type: {agg_type}")
                expr = agg_map[agg_type](col).alias(f"{col}__{agg_type}")
                exprs.append(expr)

        return exprs

    def _add_window_suffix(
        self,
        df: pl.LazyFrame,
        aggregations: metrics.Aggregations,
        window: str,
        tag: str,
        interval: str,
    ) -> pl.LazyFrame:
        """
        Rename aggregation columns with window and interval suffixes.

        Creates standardized column names: {tag}__{col}__{agg}__{window}__{interval}

        Args:
            df: DataFrame with aggregation columns
            aggregations: Aggregation specifications used for column names
            window: Time window (e.g., "7d")
            tag: Feature tag prefix
            interval: Computation interval (e.g., "1d")

        Returns:
            DataFrame with renamed columns
        """
        renames = {
            f"{col}__{agg}": f"{tag}__{col}__{agg}__{window}__{interval}"
            for col, aggs in aggregations.items()
            for agg in aggs
        }
        return df.rename(renames)

    def _join_on_keys(
        self,
        dfs: list[pl.LazyFrame],
        entity_keys: list[str],
        timestamp_col: str,
    ) -> pl.LazyFrame:
        """
        Join multiple dataframes on entity keys and timestamp.

        Uses outer joins to preserve all rows across different windows.

        Args:
            dfs: DataFrames to join
            entity_keys: Columns to join on
            timestamp_col: Timestamp column to include in join

        Returns:
            Single DataFrame with all inputs joined
        """
        if len(dfs) == 1:
            return dfs[0]

        result = dfs[0]
        for df in dfs[1:]:
            result = result.join(
                df, on=[*entity_keys, timestamp_col], how="outer", coalesce=True
            )
        return result
