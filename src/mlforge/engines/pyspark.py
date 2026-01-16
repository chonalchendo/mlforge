"""
PySpark-based execution engine.

This module provides the PySparkEngine implementation for distributed
feature computation using Apache Spark.
"""

from typing import TYPE_CHECKING, Any, override

import polars as pl

import mlforge.compilers as compilers
import mlforge.engines.base as base
import mlforge.results as results_
import mlforge.sources as sources
import mlforge.timestamps as timestamps
import mlforge.validation as validation

if TYPE_CHECKING:
    from pyspark.sql import DataFrame as SparkDataFrame
    from pyspark.sql import SparkSession

    import mlforge.core as core


class PySparkEngine(base.Engine):
    """
    PySpark-based execution engine.

    Executes features using Apache Spark for distributed computation.
    Supports both simple transformations and complex rolling aggregations.

    Attributes:
        _spark: SparkSession instance
        _compiler: PySpark compiler for metric specifications
    """

    def __init__(self, spark: "SparkSession | None" = None) -> None:
        """
        Initialize PySpark engine.

        Args:
            spark: SparkSession to use. If None, creates or gets existing session.
                On Databricks, the existing spark session is automatically detected.
        """
        self._spark = (
            spark if spark is not None else self._get_or_create_session()
        )
        self._compiler = compilers.PySparkCompiler()

    def _get_or_create_session(self) -> "SparkSession":
        """
        Get existing SparkSession or create new one.

        Returns:
            Active or newly created SparkSession

        Raises:
            ImportError: If pyspark is not installed
        """
        try:
            from pyspark.sql import SparkSession
        except ImportError:
            raise ImportError(
                "PySpark is required for PySparkEngine.\n\n"
                "Install with:\n"
                "    pip install mlforge[pyspark]\n\n"
                "Or for full Databricks support:\n"
                "    pip install mlforge[databricks]"
            )

        # Check for existing session (e.g., on Databricks)
        existing = SparkSession.getActiveSession()
        if existing is not None:
            return existing

        # Create new session with sensible defaults
        return SparkSession.builder.appName("mlforge").getOrCreate()

    @property
    def spark(self) -> "SparkSession":
        """Get the SparkSession instance."""
        return self._spark

    @override
    def execute(self, feature: "core.Feature") -> results_.ResultKind:
        """
        Execute a feature using PySpark.

        Loads source data, applies the feature transformation function,
        validates entity keys and timestamps, then computes any specified
        metrics over rolling windows.

        Args:
            feature: Feature definition to execute

        Returns:
            PySparkResult wrapping the computed DataFrame

        Raises:
            ValueError: If entity keys or timestamp columns are missing
            TypeError: If feature function has incorrect type hints
        """
        # Validate type hints for PySpark compatibility
        self._validate_type_hints(feature)

        # Load data from source as Spark DataFrame
        source_df = self._load_source(feature.source_obj)

        # Generate surrogate keys for entities that require it
        if feature.entities:
            source_df = self._apply_entity_keys(source_df, feature.entities)

        # Process dataframe with feature function
        processed_df: SparkDataFrame = feature.fn(source_df)
        columns = processed_df.columns

        # Capture base schema before metrics are applied
        base_schema = {
            field.name: str(field.dataType) for field in processed_df.schema
        }

        missing_keys = [key for key in feature.keys if key not in columns]
        if missing_keys:
            raise ValueError(
                f"Entity keys {missing_keys} not found in dataframe"
            )

        # Run validators on processed dataframe (before metrics)
        if feature.validators:
            # Convert to Polars for validation (validators expect Polars DataFrames)
            polars_df = pl.from_pandas(processed_df.toPandas())
            validation.run_validators_or_raise(
                feature.name, polars_df, feature.validators
            )

        if not feature.metrics:
            return results_.PySparkResult(processed_df, base_schema=base_schema)

        # Parse timestamp column (auto-detect format if needed)
        if feature.timestamp is None:
            raise ValueError(
                "Timestamp is required when using metrics. "
                "Please set timestamp parameter in @feature decorator."
            )

        processed_df, ts_column = self._parse_timestamp(
            processed_df, feature.timestamp
        )

        if ts_column not in processed_df.columns:
            raise ValueError(
                f"Timestamp column '{ts_column}' not found in dataframe"
            )

        if not feature.interval:
            raise ValueError(
                "Aggregation interval is not specified. "
                "Please set interval parameter in @feature decorator."
            )

        # Use first tag if available, otherwise fall back to feature name
        tag = feature.tags[0] if feature.tags else feature.name

        ctx = compilers.PySparkComputeContext(
            keys=feature.keys,
            timestamp=ts_column,
            interval=feature.interval,
            dataframe=processed_df,
            tag=tag,
            spark=self._spark,
        )

        # Compute metrics and join results
        results: list[SparkDataFrame] = []
        for metric in feature.metrics:
            metric.validate(columns)
            result = self._compiler.compile(metric, ctx)
            results.append(result)

        if len(results) == 1:
            return results_.PySparkResult(
                results.pop(0), base_schema=base_schema
            )

        # Join results on entity keys and timestamp
        final_result = results.pop(0)
        join_cols = [*ctx.keys, ctx.timestamp]
        for df in results:
            final_result = final_result.join(df, on=join_cols, how="outer")

        return results_.PySparkResult(final_result, base_schema=base_schema)

    def _validate_type_hints(self, feature: "core.Feature") -> None:
        """
        Validate that feature function has correct PySpark type hints.

        Args:
            feature: Feature to validate

        Raises:
            TypeError: If type hints indicate non-PySpark DataFrame types
        """

        hints = getattr(feature.fn, "__annotations__", {})
        if not hints:
            # No type hints - allow for flexibility
            return

        # Check for Polars type hints which indicate wrong engine
        for param, hint in hints.items():
            hint_str = str(hint)
            if "polars" in hint_str.lower() or hint_str in (
                "DataFrame",
                "LazyFrame",
            ):
                if "pyspark" not in hint_str.lower():
                    raise TypeError(
                        f"Feature '{feature.name}' has incorrect type hints for PySparkEngine.\n\n"
                        f"Expected:\n"
                        f"    def {feature.name}(df: pyspark.sql.DataFrame) -> pyspark.sql.DataFrame:\n\n"
                        f"Got:\n"
                        f"    {param}: {hint}\n\n"
                        f"Use pyspark.sql.DataFrame type hints when using PySparkEngine."
                    )

    def _load_source(self, source: sources.Source) -> "SparkDataFrame":
        """
        Load source data as Spark DataFrame.

        Args:
            source: Source object specifying path and format

        Returns:
            Spark DataFrame containing source data

        Raises:
            ValueError: If file format is not supported
        """
        path = source.path
        fmt = source.format

        match fmt:
            case sources.ParquetFormat():
                reader = self._spark.read.parquet(path)
                if fmt.columns:
                    reader = reader.select(*fmt.columns)
                return reader

            case sources.CSVFormat():
                return (
                    self._spark.read.option("header", fmt.has_header)
                    .option("delimiter", fmt.delimiter)
                    .option("quote", fmt.quote_char or '"')
                    .csv(path)
                )

            case sources.DeltaFormat():
                reader = self._spark.read.format("delta")
                if fmt.version is not None:
                    reader = reader.option("versionAsOf", fmt.version)
                return reader.load(path)

            case _:
                raise ValueError(
                    f"Unsupported source format: {type(fmt).__name__}"
                )

    def _apply_entity_keys(
        self,
        df: "SparkDataFrame",
        entities: list,
    ) -> "SparkDataFrame":
        """
        Generate surrogate keys for entities that require it.

        For each entity with from_columns specified, generates a surrogate
        key column using SHA256 hash of concatenated column values.

        Args:
            df: Source Spark DataFrame
            entities: List of Entity objects

        Returns:
            DataFrame with generated key columns added
        """
        from pyspark.sql import functions as F

        for entity in entities:
            if entity.requires_generation:
                # Entity has from_columns - generate surrogate key
                # Concatenate columns with separator and hash
                concat_expr = F.concat_ws(
                    "__",
                    *[F.col(c).cast("string") for c in entity.from_columns],
                )
                df = df.withColumn(entity.join_key, F.sha2(concat_expr, 256))

        return df

    def _parse_timestamp(
        self,
        df: "SparkDataFrame",
        timestamp: str | Any,
    ) -> tuple["SparkDataFrame", str]:
        """
        Parse timestamp column and return column name.

        Args:
            df: Spark DataFrame
            timestamp: Timestamp column name or Timestamp object

        Returns:
            Tuple of (DataFrame with parsed timestamp, timestamp column name)
        """
        from pyspark.sql import functions as F
        from pyspark.sql.types import StringType, TimestampType

        ts_column = timestamps.normalize_timestamp(timestamp)
        if ts_column is None:
            raise ValueError("Timestamp column name could not be determined")

        # Check if column needs parsing
        col_type = df.schema[ts_column].dataType

        if isinstance(col_type, TimestampType):
            # Already a timestamp, no conversion needed
            return df, ts_column

        if isinstance(col_type, StringType):
            # Try to parse string as timestamp
            df = df.withColumn(ts_column, F.to_timestamp(F.col(ts_column)))

        return df, ts_column
