"""
DuckDB-based execution engine.

This module provides the DuckDBEngine implementation for feature computation
using DuckDB, optimized for large datasets that may not fit in memory.
"""

from typing import TYPE_CHECKING, override

import polars as pl

import mlforge.compilers as compilers
import mlforge.engines as engines
import mlforge.errors as errors
import mlforge.results as results_
import mlforge.sources as sources
import mlforge.utils as utils
import mlforge.validation as validation

from .base import Engine

if TYPE_CHECKING:
    import duckdb

    import mlforge.core as core


class DuckDBEngine(Engine):
    """
    DuckDB-based execution engine.

    Executes features using DuckDB for computation, optimized for large
    datasets. Supports both simple transformations and complex rolling
    aggregations using native SQL window functions.

    The engine maintains API compatibility with PolarsEngine - user feature
    functions still receive and return Polars DataFrames. DuckDB is used
    internally for efficient source loading and metrics computation.

    Attributes:
        _compiler: DuckDB compiler for metric specifications
        _conn: DuckDB connection instance
    """

    def __init__(self) -> None:
        """Initialize DuckDB engine with compiler and connection."""
        self._compiler = compilers.DuckDBCompiler()
        self._conn: "duckdb.DuckDBPyConnection" = (
            engines.get_duckdb_connection()
        )

    @override
    def execute(self, feature: "core.Feature") -> results_.ResultKind:
        """
        Execute a feature using DuckDB.

        Loads source data using DuckDB, converts to Polars for the user's
        feature transformation function, then uses DuckDB for metrics
        computation.

        Args:
            feature: Feature definition to execute

        Returns:
            DuckDBResult wrapping the computed relation

        Raises:
            ValueError: If entity keys or timestamp columns are missing
        """
        engines.get_duckdb_connection()  # Ensure DuckDB is available

        # Load data from source using DuckDB
        source_relation = self._load_source(feature.source_obj)

        # Convert to Polars for user's feature function
        # This maintains API compatibility - users write Polars code
        source_df = source_relation.pl()

        # Generate surrogate keys for entities that require it
        if feature.entities:
            source_df = self._apply_entity_keys(source_df, feature.entities)

        # Process dataframe with user's function code
        processed_df = feature(source_df)

        # Handle LazyFrame if returned
        if isinstance(processed_df, pl.LazyFrame):
            processed_df = processed_df.collect()

        columns = list(processed_df.columns)

        # Capture base schema before metrics are applied
        base_schema = {
            name: str(dtype) for name, dtype in processed_df.schema.items()
        }

        # Validate entity keys exist
        missing_keys = [key for key in feature.keys if key not in columns]
        if missing_keys:
            raise ValueError(
                f"Entity keys {missing_keys} not found in dataframe"
            )

        # Run validators on processed dataframe (before metrics)
        # Validators expect Polars DataFrames
        if feature.validators:
            self._run_validators(feature.name, processed_df, feature.validators)

        # If no metrics, return the processed DataFrame as DuckDB relation
        if not feature.metrics:
            # Convert back to DuckDB relation for consistent return type
            relation = self._conn.from_arrow(processed_df.to_arrow())
            return results_.DuckDBResult(relation, base_schema=base_schema)

        # Validate timestamp column exists
        if feature.timestamp not in columns:
            raise ValueError(
                f"Timestamp column '{feature.timestamp}' not found in dataframe"
            )

        # Validate interval is set
        if not feature.interval:
            raise ValueError(
                "Aggregation interval is not specified. "
                "Please set interval parameter in @feature decorator."
            )

        # Use first tag if available, otherwise fall back to feature name
        tag = feature.tags[0] if feature.tags else feature.name

        # Convert processed DataFrame to DuckDB relation for metrics computation
        processed_relation = self._conn.from_arrow(processed_df.to_arrow())

        # Create DuckDB compute context
        ctx = compilers.DuckDBComputeContext(
            keys=feature.keys,
            timestamp=feature.timestamp,
            interval=feature.interval,
            relation=processed_relation,
            tag=tag,
            connection=self._conn,
        )

        # Compute metrics and join results
        results: list["duckdb.DuckDBPyRelation"] = []
        for metric in feature.metrics:
            metric.validate(columns)
            result = self._compiler.compile(metric, ctx)
            results.append(result)

        if len(results) == 1:
            return results_.DuckDBResult(
                results.pop(0), base_schema=base_schema
            )

        # Join multiple metric results
        # Use the first result as base and join others
        final_result = results.pop(0)
        join_cols = [*feature.keys, feature.timestamp]

        for relation in results:
            # Create join SQL
            final_result = self._join_relations(
                final_result, relation, join_cols
            )

        return results_.DuckDBResult(final_result, base_schema=base_schema)

    def _load_source(self, source: sources.Source) -> "duckdb.DuckDBPyRelation":
        """
        Load source data from Source object using DuckDB.

        Args:
            source: Source object specifying path and format

        Returns:
            DuckDB relation containing source data

        Raises:
            ValueError: If file format is not supported
        """
        path = source.path
        fmt = source.format

        match fmt:
            case sources.ParquetFormat():
                # DuckDB read_parquet doesn't support row_groups directly
                # but does support column selection via SQL
                relation = self._conn.read_parquet(path)
                if fmt.columns:
                    cols = ", ".join(f'"{c}"' for c in fmt.columns)
                    relation = self._conn.sql(
                        f"SELECT {cols} FROM relation"  # nosec B608
                    )
                return relation

            case sources.CSVFormat():
                return self._conn.read_csv(
                    path,
                    delimiter=fmt.delimiter,
                    header=fmt.has_header,
                    quotechar=fmt.quote_char,
                    skiprows=fmt.skip_rows if fmt.skip_rows > 0 else None,
                )

            case sources.DeltaFormat():
                # DuckDB can read Delta tables via delta extension
                # Note: Version selection not yet supported in DuckDB delta_scan
                return self._conn.sql(
                    f"SELECT * FROM delta_scan('{path}')"  # nosec B608
                )

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
            df: Source DataFrame (Polars)
            entities: List of Entity objects

        Returns:
            DataFrame with generated key columns added
        """
        for entity in entities:
            if entity.requires_generation:
                # Entity has from_columns - generate surrogate key
                df = df.with_columns(
                    utils.surrogate_key(*entity.from_columns).alias(
                        entity.join_key  # type: ignore[arg-type]
                    )
                )
        return df

    def _run_validators(
        self,
        feature_name: str,
        df: pl.DataFrame,
        validators: dict,
    ) -> None:
        """
        Run validators on the processed DataFrame.

        Args:
            feature_name: Name of the feature being validated
            df: Polars DataFrame to validate
            validators: Mapping of column names to validator lists

        Raises:
            FeatureValidationError: If any validation fails
        """
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

    def _join_relations(
        self,
        left: "duckdb.DuckDBPyRelation",
        right: "duckdb.DuckDBPyRelation",
        join_cols: list[str],
    ) -> "duckdb.DuckDBPyRelation":
        """
        Join two DuckDB relations on specified columns.

        Uses FULL OUTER JOIN to preserve all rows.

        Args:
            left: Left relation
            right: Right relation
            join_cols: Columns to join on

        Returns:
            Joined relation
        """
        # Register both relations as temporary views
        self._conn.register("__left__", left)
        self._conn.register("__right__", right)

        # Build join condition
        join_condition = " AND ".join(
            [f'__left__."{col}" = __right__."{col}"' for col in join_cols]
        )

        # Get columns from each relation, excluding join columns from right
        left_cols = left.columns
        right_cols = [c for c in right.columns if c not in join_cols]

        # Build SELECT clause with COALESCE for join columns
        select_parts = []
        for col in join_cols:
            select_parts.append(
                f'COALESCE(__left__."{col}", __right__."{col}") AS "{col}"'
            )
        for col in left_cols:
            if col not in join_cols:
                select_parts.append(f'__left__."{col}"')
        for col in right_cols:
            select_parts.append(f'__right__."{col}"')

        select_clause = ", ".join(select_parts)

        # SQL is constructed from trusted feature definition values, not user input
        sql = f"""
        SELECT {select_clause}
        FROM __left__
        FULL OUTER JOIN __right__ ON {join_condition}
        """  # nosec B608

        return self._conn.sql(sql)
