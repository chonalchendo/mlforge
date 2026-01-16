"""
Polars-based metric compiler.

This module provides the PolarsCompiler implementation that translates
high-level metric specifications into Polars expressions.

The compiler uses backward-looking windows for point-in-time correctness:
- Feature at time T aggregates events from (T - window, T]
- This ensures no data leakage from future events
"""

from typing import Callable

import polars as pl
from loguru import logger

import mlforge.compilers.base as base
import mlforge.durations as durations
import mlforge.metrics as metrics


class PolarsCompiler:
    """
    Polars-based metric compiler.

    Translates high-level metric specifications into Polars expressions
    for efficient computation with point-in-time correct backward-looking windows.
    """

    # Mapping from aggregation names to Polars expressions
    AGG_MAP: dict[str, Callable[[str], pl.Expr]] = {
        "count": lambda c: pl.col(c).count(),
        "sum": lambda c: pl.col(c).sum(),
        "mean": lambda c: pl.col(c).mean(),
        "min": lambda c: pl.col(c).min(),
        "max": lambda c: pl.col(c).max(),
        "std": lambda c: pl.col(c).std(),
        "median": lambda c: pl.col(c).median(),
    }

    def compile(
        self, metric: metrics.MetricKind, ctx: base.ComputeContext
    ) -> pl.DataFrame | pl.LazyFrame:
        """
        Compile a metric specification into a Polars computation.

        Args:
            metric: Metric specification to compile
            ctx: Execution context with dataframe and metadata

        Returns:
            DataFrame with computed metrics
        """
        method: Callable = getattr(
            self, f"compile_{type(metric).__name__.lower()}"
        )
        return method(metric, ctx)

    def compile_rolling(
        self, metric: metrics.Rolling, ctx: base.ComputeContext
    ) -> pl.DataFrame | pl.LazyFrame:
        """
        Compile backward-looking rolling window aggregations.

        Uses Polars' native group_by_dynamic with negative offset for
        point-in-time correct backward-looking windows:
        - Window: (bucket - window, bucket]
        - This ensures features at time T only include data up to time T

        Args:
            metric: Rolling window specification
            ctx: Execution context

        Returns:
            DataFrame with all window aggregations joined on entity keys and timestamp
        """
        cols = list(metric.aggregations.keys())
        windows = metric.converted_windows
        logger.debug(
            f"Rolling aggregations (backward-looking): {cols} over {windows} "
            f"(interval={ctx.interval})"
        )

        # Ensure data is sorted by entity keys and timestamp (required for group_by_dynamic)
        df = ctx.dataframe.sort([*ctx.keys, ctx.timestamp])

        # Compute aggregations for each window
        window_results: list[pl.DataFrame | pl.LazyFrame] = []
        for window in windows:
            result = self._compute_window_aggregations_dynamic(
                source_df=df,
                metric=metric,
                window=window,
                ctx=ctx,
            )
            window_results.append(result)

        return self._join_on_keys(window_results, ctx.keys, ctx.timestamp)

    def _compute_window_aggregations_dynamic(
        self,
        source_df: pl.DataFrame | pl.LazyFrame,
        metric: metrics.Rolling,
        window: str,
        ctx: base.ComputeContext,
    ) -> pl.DataFrame | pl.LazyFrame:
        """
        Compute backward-looking aggregations using date spine approach.

        Uses a date spine approach for point-in-time correctness:
        1. Generate all time buckets in the data range per entity
        2. For each bucket, aggregate events in the backward-looking window
        3. Window: (bucket - window_size, bucket + interval]

        This ensures features at time T only include data available at time T,
        preventing data leakage and matching DuckDB's behavior exactly.

        Args:
            source_df: Source data with events
            metric: Rolling metric specification
            window: Window size (e.g., "7d")
            ctx: Execution context

        Returns:
            DataFrame with aggregated metrics for this window
        """
        # Step 1: Compute per-entity date bounds (truncated to interval)
        entity_bounds = source_df.group_by(ctx.keys).agg(
            [
                pl.col(ctx.timestamp)
                .min()
                .dt.truncate(ctx.interval)
                .alias("__min_date__"),
                pl.col(ctx.timestamp)
                .max()
                .dt.truncate(ctx.interval)
                .alias("__max_date__"),
            ]
        )

        # Step 2: Generate date spine per entity using datetime_ranges
        spine = (
            entity_bounds.with_columns(
                pl.datetime_ranges(
                    pl.col("__min_date__"),
                    pl.col("__max_date__"),
                    ctx.interval,
                ).alias("__bucket__")
            )
            .explode("__bucket__")
            .select([*ctx.keys, "__bucket__"])
        )

        # Step 3: Join spine with source data
        joined = spine.join(source_df, on=ctx.keys, how="left")

        # Step 4: Filter to window boundaries
        # Window: (bucket - window, bucket + interval]
        # This matches DuckDB's: event_time > bucket - window AND event_time <= bucket + interval
        window_kwargs = durations.parse_duration(window).to_polars_kwargs()
        interval_kwargs = durations.parse_duration(
            ctx.interval
        ).to_polars_kwargs()
        window_duration = pl.duration(**window_kwargs)  # type: ignore[arg-type]
        interval_duration = pl.duration(**interval_kwargs)  # type: ignore[arg-type]

        filtered = joined.filter(
            (pl.col(ctx.timestamp) > (pl.col("__bucket__") - window_duration))
            & (
                pl.col(ctx.timestamp)
                <= (pl.col("__bucket__") + interval_duration)
            )
        )

        # Step 5: Build aggregation expressions and aggregate
        agg_exprs = []
        for col, agg_types in metric.aggregations.items():
            for agg_type in agg_types:
                output_name = (
                    f"{ctx.tag}__{col}__{agg_type}__{ctx.interval}__{window}"
                )
                expr = self.AGG_MAP[agg_type](col).alias(output_name)
                agg_exprs.append(expr)

        result = (
            filtered.group_by([*ctx.keys, "__bucket__"])
            .agg(agg_exprs)
            .rename({"__bucket__": ctx.timestamp})
            .sort([*ctx.keys, ctx.timestamp])
        )

        return result

    def _join_on_keys(
        self,
        dfs: list[pl.DataFrame | pl.LazyFrame],
        entity_keys: list[str],
        timestamp_col: str,
    ) -> pl.LazyFrame | pl.DataFrame:
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
                df, on=[*entity_keys, timestamp_col], how="full", coalesce=True
            )
        return result
