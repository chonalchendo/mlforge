"""
DuckDB-based metric compiler.

This module provides the DuckDBCompiler implementation that translates
high-level metric specifications into DuckDB SQL for efficient computation.

The compiler uses backward-looking windows for point-in-time correctness:
- Feature at time T aggregates events from (T - window, T + interval]
- This ensures no data leakage from future events
"""

from typing import TYPE_CHECKING, Callable

from loguru import logger

import mlforge.engines as engines
import mlforge.metrics as metrics

if TYPE_CHECKING:
    import duckdb


class DuckDBComputeContext:
    """
    Execution context for DuckDB metric compilation.

    Carries necessary relation and metadata for computing metrics
    over rolling time windows using DuckDB.

    Attributes:
        keys: Entity key columns for grouping
        interval: Time interval for rolling computations (e.g., "1h", "1d")
        timestamp: Timestamp column name
        relation: DuckDB relation to compute metrics on
        tag: Prefix for naming output columns
        connection: DuckDB connection that owns the relation
    """

    def __init__(
        self,
        keys: list[str],
        interval: str,
        timestamp: str,
        relation: "duckdb.DuckDBPyRelation",
        tag: str,
        connection: "duckdb.DuckDBPyConnection | None" = None,
    ):
        self.keys = keys
        self.interval = interval
        self.timestamp = timestamp
        self.relation = relation
        self.tag = tag
        self.connection = connection


class DuckDBCompiler:
    """
    DuckDB-based metric compiler.

    Translates high-level metric specifications into DuckDB SQL
    for efficient computation using backward-looking windows for
    point-in-time correctness.
    """

    # Mapping from mlforge aggregation names to DuckDB SQL functions
    AGG_MAP: dict[str, str] = {
        "count": "COUNT",
        "sum": "SUM",
        "mean": "AVG",
        "min": "MIN",
        "max": "MAX",
        "std": "STDDEV_SAMP",
        "median": "MEDIAN",
    }

    def compile(
        self, metric: metrics.MetricKind, ctx: DuckDBComputeContext
    ) -> "duckdb.DuckDBPyRelation":
        """
        Compile a metric specification into a DuckDB computation.

        Args:
            metric: Metric specification to compile
            ctx: Execution context with relation and metadata

        Returns:
            DuckDB relation with computed metrics
        """
        method: Callable = getattr(
            self, f"compile_{type(metric).__name__.lower()}"
        )
        return method(metric, ctx)

    def compile_rolling(
        self, metric: metrics.Rolling, ctx: DuckDBComputeContext
    ) -> "duckdb.DuckDBPyRelation":
        """
        Compile backward-looking rolling window aggregations using DuckDB SQL.

        Uses a date spine approach for point-in-time correctness:
        1. Generate all time buckets in the data range per entity
        2. For each bucket, aggregate events in the backward-looking window
        3. Window: (bucket - window_size, bucket + interval]

        This ensures features at time T only include data available at time T,
        preventing data leakage.

        Args:
            metric: Rolling window specification
            ctx: Execution context

        Returns:
            DuckDB relation with all window aggregations
        """
        windows = metric.converted_windows
        logger.debug(
            f"DuckDB Rolling aggregations (backward-looking) over {windows} "
            f"(interval={ctx.interval})"
        )

        # Build the SQL query
        sql = self._build_rolling_sql(metric, ctx)
        logger.debug(f"Generated SQL: {sql}")

        # Use the connection from context, or create a new one
        if ctx.connection is not None:
            conn = ctx.connection
        else:
            # Fallback: create new connection and convert relation to Arrow
            conn = engines.get_duckdb_connection()
            # Convert relation to Arrow table and register
            arrow_table = ctx.relation.arrow()
            conn.register("__feature_data__", arrow_table)
            result = conn.sql(sql)
            return result

        # Register the relation with its owning connection
        conn.register("__feature_data__", ctx.relation)
        result = conn.sql(sql)
        return result

    def _build_rolling_sql(
        self, metric: metrics.Rolling, ctx: DuckDBComputeContext
    ) -> str:
        """
        Build SQL query for backward-looking rolling window aggregations.

        Generates SQL that:
        1. Creates a date spine with all time buckets per entity
        2. For each bucket, aggregates events in (bucket - window, bucket + interval]
        3. Joins results for multiple windows

        Args:
            metric: Rolling window specification
            ctx: Execution context

        Returns:
            SQL query string
        """
        windows = metric.converted_windows

        # If single window, use simpler query
        if len(windows) == 1:
            return self._build_single_window_sql(metric, ctx, windows[0])

        # Multiple windows: need to join results
        return self._build_multi_window_sql(metric, ctx, windows)

    def _build_single_window_sql(
        self, metric: metrics.Rolling, ctx: DuckDBComputeContext, window: str
    ) -> str:
        """Build SQL for a single window aggregation with backward-looking semantics."""
        # Column references
        partition_cols_b = ", ".join(f'b."{k}"' for k in ctx.keys)
        partition_cols_select = ", ".join(f'b."{k}" AS "{k}"' for k in ctx.keys)
        bucket_cols = ", ".join(f'"{k}"' for k in ctx.keys)

        # Time intervals
        trunc_unit = self._interval_to_trunc_unit(ctx.interval)
        interval_sql = self._duration_to_interval(ctx.interval)
        window_interval = self._duration_to_interval(window)

        # Build aggregation expressions
        agg_parts = []
        for col, agg_types in metric.aggregations.items():
            for agg_type in agg_types:
                sql_agg = self.AGG_MAP[agg_type]
                output_col = (
                    f"{ctx.tag}__{col}__{agg_type}__{ctx.interval}__{window}"
                )
                agg_parts.append(f'{sql_agg}(d."{col}") AS "{output_col}"')

        agg_clause = ",\n        ".join(agg_parts)

        # Build join conditions for multiple entity keys
        join_conditions = " AND ".join(f'd."{k}" = b."{k}"' for k in ctx.keys)

        # SQL with backward-looking window semantics:
        # - Generate date spine from min to max date per entity
        # - For each bucket, aggregate events where:
        #   event_time > bucket - window AND event_time <= bucket + interval
        sql = f"""
WITH date_range AS (
    -- Get min/max dates per entity
    SELECT
        {bucket_cols},
        DATE_TRUNC('{trunc_unit}', MIN("{ctx.timestamp}")) AS min_date,
        DATE_TRUNC('{trunc_unit}', MAX("{ctx.timestamp}")) AS max_date
    FROM __feature_data__
    GROUP BY {bucket_cols}
),
buckets AS (
    -- Generate all time buckets per entity
    SELECT
        {bucket_cols},
        gs.time_bucket
    FROM date_range dr,
    LATERAL (
        SELECT UNNEST(generate_series(dr.min_date, dr.max_date, {interval_sql})) AS time_bucket
    ) gs
)
SELECT
    {partition_cols_select},
    b.time_bucket AS "{ctx.timestamp}",
    {agg_clause}
FROM buckets b
LEFT JOIN __feature_data__ d ON
    {join_conditions}
    AND d."{ctx.timestamp}" > b.time_bucket - {window_interval}
    AND d."{ctx.timestamp}" <= b.time_bucket + {interval_sql}
GROUP BY {partition_cols_b}, b.time_bucket
ORDER BY {partition_cols_b}, b.time_bucket
"""  # nosec B608
        return sql.strip()

    def _build_multi_window_sql(
        self,
        metric: metrics.Rolling,
        ctx: DuckDBComputeContext,
        windows: list[str],
    ) -> str:
        """Build SQL for multiple window aggregations with backward-looking semantics."""
        # Column references
        partition_cols_b = ", ".join(f'b."{k}"' for k in ctx.keys)
        bucket_cols = ", ".join(f'"{k}"' for k in ctx.keys)

        # Time intervals
        trunc_unit = self._interval_to_trunc_unit(ctx.interval)
        interval_sql = self._duration_to_interval(ctx.interval)

        # Build join conditions for multiple entity keys
        join_conditions = " AND ".join(f'd."{k}" = b."{k}"' for k in ctx.keys)

        # Start with CTEs for date range and buckets
        cte_parts = [
            f"""date_range AS (
    SELECT
        {bucket_cols},
        DATE_TRUNC('{trunc_unit}', MIN("{ctx.timestamp}")) AS min_date,
        DATE_TRUNC('{trunc_unit}', MAX("{ctx.timestamp}")) AS max_date
    FROM __feature_data__
    GROUP BY {bucket_cols}
)""",  # nosec B608
            f"""buckets AS (
    SELECT
        {bucket_cols},
        gs.time_bucket
    FROM date_range dr,
    LATERAL (
        SELECT UNNEST(generate_series(dr.min_date, dr.max_date, {interval_sql})) AS time_bucket
    ) gs
)""",  # nosec B608
        ]

        # Add a CTE for each window
        window_cte_names = []
        for i, window in enumerate(windows):
            window_interval = self._duration_to_interval(window)
            cte_name = f"w{i}"
            window_cte_names.append(cte_name)

            # Build aggregation expressions for this window
            agg_parts = []
            for col, agg_types in metric.aggregations.items():
                for agg_type in agg_types:
                    sql_agg = self.AGG_MAP[agg_type]
                    output_col = f"{ctx.tag}__{col}__{agg_type}__{ctx.interval}__{window}"
                    agg_parts.append(f'{sql_agg}(d."{col}") AS "{output_col}"')

            agg_clause = ", ".join(agg_parts)

            # Backward-looking window: (bucket - window, bucket + interval]
            cte_parts.append(
                f"""{cte_name} AS (
    SELECT
        {partition_cols_b},
        b.time_bucket,
        {agg_clause}
    FROM buckets b
    LEFT JOIN __feature_data__ d ON
        {join_conditions}
        AND d."{ctx.timestamp}" > b.time_bucket - {window_interval}
        AND d."{ctx.timestamp}" <= b.time_bucket + {interval_sql}
    GROUP BY {partition_cols_b}, b.time_bucket
)"""  # nosec B608
            )

        # Build final SELECT joining all window CTEs
        select_parts = [f'w0."{k}"' for k in ctx.keys]
        select_parts.append(f'w0.time_bucket AS "{ctx.timestamp}"')

        for i, window in enumerate(windows):
            for col, agg_types in metric.aggregations.items():
                for agg_type in agg_types:
                    output_col = f"{ctx.tag}__{col}__{agg_type}__{ctx.interval}__{window}"
                    select_parts.append(f'w{i}."{output_col}"')

        select_clause = ",\n    ".join(select_parts)

        # Build JOIN clauses
        join_clauses = []
        for i in range(1, len(windows)):
            join_conds = " AND ".join(
                f'w0."{k}" = w{i}."{k}"' for k in ctx.keys
            )
            join_clauses.append(
                f"LEFT JOIN w{i} ON {join_conds} AND w0.time_bucket = w{i}.time_bucket"
            )

        join_clause = "\n".join(join_clauses)

        # Order by with table alias
        order_cols = ", ".join(f'w0."{k}"' for k in ctx.keys)

        sql = f"""
WITH {", ".join(cte_parts)}
SELECT
    {select_clause}
FROM w0
{join_clause}
ORDER BY {order_cols}, w0.time_bucket
"""  # nosec B608
        return sql.strip()

    def _interval_to_trunc_unit(self, interval: str) -> str:
        """
        Convert interval string to DATE_TRUNC unit.

        Args:
            interval: Interval string (e.g., "1d", "1h")

        Returns:
            DATE_TRUNC unit string (e.g., "day", "hour")
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

    def _duration_to_interval(self, duration: str) -> str:
        """
        Convert Polars duration string to DuckDB INTERVAL syntax.

        Args:
            duration: Polars duration string (e.g., "7d", "24h", "30m")

        Returns:
            DuckDB INTERVAL string (e.g., "INTERVAL '7' DAY")
        """
        # Parse the duration string
        if duration.endswith("d"):
            value = duration[:-1]
            return f"INTERVAL '{value}' DAY"
        elif duration.endswith("h"):
            value = duration[:-1]
            return f"INTERVAL '{value}' HOUR"
        elif duration.endswith("m"):
            value = duration[:-1]
            return f"INTERVAL '{value}' MINUTE"
        elif duration.endswith("s"):
            value = duration[:-1]
            return f"INTERVAL '{value}' SECOND"
        elif duration.endswith("w"):
            # Convert weeks to days
            value = int(duration[:-1]) * 7
            return f"INTERVAL '{value}' DAY"
        elif duration.endswith("mo"):
            value = duration[:-2]
            return f"INTERVAL '{value}' MONTH"
        elif duration.endswith("y"):
            value = duration[:-1]
            return f"INTERVAL '{value}' YEAR"
        else:
            # Assume days if no suffix
            return f"INTERVAL '{duration}' DAY"
