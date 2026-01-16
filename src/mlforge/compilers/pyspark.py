"""
PySpark-based metric compiler.

This module provides the PySparkCompiler implementation that translates
high-level metric specifications into PySpark window functions.

The compiler uses backward-looking windows for point-in-time correctness:
- Feature at time T aggregates events from (T - window, T]
- This ensures no data leakage from future events
"""

from typing import TYPE_CHECKING, Callable

from loguru import logger

import mlforge.metrics as metrics

if TYPE_CHECKING:
    from pyspark.sql import DataFrame as SparkDataFrame
    from pyspark.sql import SparkSession


class PySparkComputeContext:
    """
    Execution context for PySpark metric compilation.

    Carries necessary DataFrame and metadata for computing metrics
    over rolling time windows using PySpark.

    Attributes:
        keys: Entity key columns for grouping
        interval: Time interval for rolling computations (e.g., "1h", "1d")
        timestamp: Timestamp column name
        dataframe: Source Spark DataFrame to compute metrics on
        tag: Prefix for naming output columns
        spark: SparkSession instance
    """

    def __init__(
        self,
        keys: list[str],
        interval: str,
        timestamp: str,
        dataframe: "SparkDataFrame",
        tag: str,
        spark: "SparkSession",
    ):
        self.keys = keys
        self.interval = interval
        self.timestamp = timestamp
        self.dataframe = dataframe
        self.tag = tag
        self.spark = spark


class PySparkCompiler:
    """
    PySpark-based metric compiler.

    Translates high-level metric specifications into PySpark window functions
    for efficient computation with point-in-time correct backward-looking windows.
    """

    def compile(
        self, metric: metrics.MetricKind, ctx: PySparkComputeContext
    ) -> "SparkDataFrame":
        """
        Compile a metric specification into a PySpark computation.

        Args:
            metric: Metric specification to compile
            ctx: Execution context with DataFrame and metadata

        Returns:
            Spark DataFrame with computed metrics
        """
        method: Callable = getattr(
            self, f"compile_{type(metric).__name__.lower()}"
        )
        return method(metric, ctx)

    def compile_rolling(
        self, metric: metrics.Rolling, ctx: PySparkComputeContext
    ) -> "SparkDataFrame":
        """
        Compile backward-looking rolling window aggregations using PySpark.

        Uses a date spine approach for point-in-time correctness:
        1. Generate all time buckets in the data range per entity
        2. For each bucket, aggregate events in the backward-looking window
        3. Window: (bucket - window_size, bucket + interval]

        This ensures features at time T only include data available at time T.

        Args:
            metric: Rolling window specification
            ctx: Execution context

        Returns:
            Spark DataFrame with all window aggregations joined on entity keys and timestamp
        """

        windows = metric.converted_windows
        logger.debug(
            f"PySpark Rolling aggregations (backward-looking): over {windows} "
            f"(interval={ctx.interval})"
        )

        # Compute aggregations for each window
        window_results: list["SparkDataFrame"] = []
        for window in windows:
            result = self._compute_window_aggregations(
                source_df=ctx.dataframe,
                metric=metric,
                window=window,
                ctx=ctx,
            )
            window_results.append(result)

        return self._join_on_keys(window_results, ctx.keys, ctx.timestamp)

    def _compute_window_aggregations(
        self,
        source_df: "SparkDataFrame",
        metric: metrics.Rolling,
        window: str,
        ctx: PySparkComputeContext,
    ) -> "SparkDataFrame":
        """
        Compute backward-looking aggregations using date spine approach.

        Uses a date spine approach for point-in-time correctness:
        1. Generate all time buckets in the data range per entity
        2. For each bucket, aggregate events in the backward-looking window
        3. Window: (bucket - window_size, bucket + interval]

        This matches the behavior of Polars and DuckDB engines exactly.

        Args:
            source_df: Source data with events
            metric: Rolling metric specification
            window: Window size (e.g., "7d")
            ctx: Execution context

        Returns:
            Spark DataFrame with aggregated metrics for this window
        """
        from pyspark.sql import functions as F

        ts_col = ctx.timestamp
        interval_expr = self._duration_to_interval_expr(ctx.interval)
        window_expr = self._duration_to_interval_expr(window)

        # Step 1: Compute per-entity date bounds (truncated to interval)
        trunc_unit = self._interval_to_trunc_unit(ctx.interval)

        entity_bounds = source_df.groupBy(*ctx.keys).agg(
            F.date_trunc(trunc_unit, F.min(ts_col)).alias("__min_date__"),
            F.date_trunc(trunc_unit, F.max(ts_col)).alias("__max_date__"),
        )

        # Step 2: Generate date spine per entity using sequence
        spine = entity_bounds.select(
            *ctx.keys,
            F.explode(
                F.sequence(
                    F.col("__min_date__"),
                    F.col("__max_date__"),
                    interval_expr,
                )
            ).alias("__bucket__"),
        )

        # Step 3: Join spine with source data
        joined = spine.join(source_df, on=ctx.keys, how="left")

        # Step 4: Filter to window boundaries
        # Window: (bucket - window, bucket + interval]
        # This matches DuckDB's: event_time > bucket - window AND event_time <= bucket + interval
        filtered = joined.filter(
            (F.col(ts_col) > (F.col("__bucket__") - window_expr))
            & (F.col(ts_col) <= (F.col("__bucket__") + interval_expr))
        )

        # Step 5: Build aggregation expressions
        agg_exprs = []
        for col, agg_types in metric.aggregations.items():
            for agg_type in agg_types:
                output_name = (
                    f"{ctx.tag}__{col}__{agg_type}__{ctx.interval}__{window}"
                )
                expr = self._get_agg_expr(col, agg_type).alias(output_name)
                agg_exprs.append(expr)

        # Step 6: Aggregate
        result = (
            filtered.groupBy(*ctx.keys, "__bucket__")
            .agg(*agg_exprs)
            .withColumnRenamed("__bucket__", ts_col)
            .orderBy(*ctx.keys, ts_col)
        )

        return result

    def _get_agg_expr(self, col: str, agg: str):
        """
        Get Spark aggregation expression.

        Args:
            col: Column name to aggregate
            agg: Aggregation type name

        Returns:
            Spark Column expression for the aggregation
        """
        from pyspark.sql import functions as F

        match agg:
            case "sum":
                return F.sum(col)
            case "mean":
                return F.avg(col)
            case "count":
                return F.count(col)
            case "min":
                return F.min(col)
            case "max":
                return F.max(col)
            case "std":
                return F.stddev(col)
            case "median":
                return F.percentile_approx(col, 0.5)
            case _:
                raise ValueError(f"Unsupported aggregation: {agg}")

    def _duration_to_interval_expr(self, duration: str):
        """
        Convert duration string to Spark interval expression.

        Args:
            duration: Duration string (e.g., "7d", "24h", "30m")

        Returns:
            Spark interval expression
        """
        from pyspark.sql import functions as F

        if duration.endswith("d"):
            days = int(duration[:-1])
            return F.expr(f"INTERVAL {days} DAYS")
        elif duration.endswith("h"):
            hours = int(duration[:-1])
            return F.expr(f"INTERVAL {hours} HOURS")
        elif duration.endswith("m"):
            minutes = int(duration[:-1])
            return F.expr(f"INTERVAL {minutes} MINUTES")
        elif duration.endswith("s"):
            seconds = int(duration[:-1])
            return F.expr(f"INTERVAL {seconds} SECONDS")
        elif duration.endswith("w"):
            weeks = int(duration[:-1])
            return F.expr(f"INTERVAL {weeks * 7} DAYS")
        elif duration.endswith("mo"):
            months = int(duration[:-2])
            return F.expr(f"INTERVAL {months} MONTHS")
        elif duration.endswith("y"):
            years = int(duration[:-1])
            return F.expr(f"INTERVAL {years} YEARS")
        else:
            # Assume days if no suffix
            return F.expr(f"INTERVAL {duration} DAYS")

    def _interval_to_trunc_unit(self, interval: str) -> str:
        """
        Convert interval string to date_trunc unit.

        Args:
            interval: Interval string (e.g., "1d", "1h")

        Returns:
            date_trunc unit string (e.g., "day", "hour")
        """
        if interval.endswith("d"):
            return "day"
        elif interval.endswith("h"):
            return "hour"
        elif interval.endswith("m"):
            return "minute"
        elif interval.endswith("s"):
            return "second"
        elif interval.endswith("w"):
            return "week"
        elif interval.endswith("mo"):
            return "month"
        elif interval.endswith("y"):
            return "year"
        else:
            return "day"

    def _join_on_keys(
        self,
        dfs: list["SparkDataFrame"],
        entity_keys: list[str],
        timestamp_col: str,
    ) -> "SparkDataFrame":
        """
        Join multiple DataFrames on entity keys and timestamp.

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
        join_cols = [*entity_keys, timestamp_col]
        for df in dfs[1:]:
            result = result.join(df, on=join_cols, how="outer")

        return result
