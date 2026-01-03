from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import override

import polars as pl


class EngineResult(ABC):
    """
    Abstract wrapper for engine-specific computation results.

    Provides a uniform interface for writing results to storage,
    converting to Polars for inspection, and extracting metadata.
    """

    @abstractmethod
    def write_parquet(self, path: Path | str) -> None:
        """
        Write result to parquet file.

        Args:
            path: Destination file path
        """
        pass

    @abstractmethod
    def to_polars(self) -> pl.DataFrame:
        """
        Convert to Polars DataFrame for inspection.

        Returns:
            DataFrame containing the result data
        """
        pass

    @abstractmethod
    def row_count(self) -> int:
        """
        Get number of rows in result.

        Returns:
            Row count for metadata tracking
        """
        pass

    @abstractmethod
    def schema(self) -> dict[str, str]:
        """
        Get result schema.

        Returns:
            Mapping of column names to type strings
        """
        pass

    @abstractmethod
    def base_schema(self) -> dict[str, str] | None:
        """
        Get the base schema before metrics were applied.

        Returns:
            Schema of base DataFrame or None if not available
        """
        pass


class PolarsResult(EngineResult):
    """
    Polars-based result wrapper.

    Lazily evaluates Polars LazyFrames to avoid unnecessary computation
    until data is needed for writing or inspection.

    Attributes:
        _lf: LazyFrame containing the computation graph
        _df: Materialized DataFrame (cached after first collect)
        _base_schema: Schema of base DataFrame before metrics (optional)
    """

    def __init__(
        self,
        lf: pl.LazyFrame | pl.DataFrame,
        base_schema: dict[str, str] | None = None,
    ):
        """
        Initialize Polars result wrapper.

        Args:
            lf: Polars LazyFrame or eager DataFrame
            base_schema: Schema of base DataFrame before metrics were applied
        """
        if isinstance(lf, pl.DataFrame):
            self._lf = lf.lazy()
            self._df = lf
        else:
            self._lf = lf
            self._df: pl.DataFrame | None = None
        self._base_schema = base_schema

    def _collect(self) -> pl.DataFrame:
        """
        Materialize lazy computation if needed.

        Caches result to avoid recomputation on subsequent calls.

        Returns:
            Materialized DataFrame
        """
        if self._df is None:
            self._df = self._lf.collect()
        return self._df

    @override
    def write_parquet(self, path: Path | str) -> None:
        self._collect().write_parquet(path)

    @override
    def to_polars(self) -> pl.DataFrame:
        return self._collect()

    @override
    def row_count(self) -> int:
        return self._collect().height

    @override
    def schema(self) -> dict[str, str]:
        return {
            name: str(dtype)
            for name, dtype in self._lf.collect_schema().items()
        }

    @override
    def base_schema(self) -> dict[str, str] | None:
        """
        Get the base schema before metrics were applied.

        Returns:
            Schema of base DataFrame or None if not available
        """
        return self._base_schema


def _import_duckdb():
    """
    Import DuckDB with helpful error message if not installed.

    Returns:
        The duckdb module

    Raises:
        ImportError: If duckdb is not installed
    """
    try:
        import duckdb

        return duckdb
    except ImportError:
        raise ImportError(
            "DuckDB is required for the duckdb engine. "
            "Install with: pip install mlforge[duckdb]"
        ) from None


class DuckDBResult(EngineResult):
    """
    DuckDB-based result wrapper.

    Wraps a DuckDB Relation for lazy evaluation and provides methods
    for writing to parquet and converting to Polars.

    Attributes:
        _relation: DuckDB Relation containing the computation
        _df: Materialized Polars DataFrame (cached after first conversion)
        _base_schema: Schema of base DataFrame before metrics (optional)
    """

    def __init__(
        self,
        relation,  # duckdb.DuckDBPyRelation - not typed to avoid import
        base_schema: dict[str, str] | None = None,
    ):
        """
        Initialize DuckDB result wrapper.

        Args:
            relation: DuckDB Relation object
            base_schema: Schema of base DataFrame before metrics were applied
        """
        self._relation = relation
        self._df: pl.DataFrame | None = None
        self._base_schema = base_schema

    def _to_polars_cached(self) -> pl.DataFrame:
        """
        Convert to Polars DataFrame with caching.

        Caches result to avoid recomputation on subsequent calls.

        Returns:
            Materialized Polars DataFrame
        """
        if self._df is None:
            # Use Arrow as intermediate format for efficient conversion
            self._df = self._relation.pl()
        return self._df

    @override
    def write_parquet(self, path: Path | str) -> None:
        """Write result to parquet file using DuckDB's native writer."""
        self._relation.write_parquet(str(path))

    @override
    def to_polars(self) -> pl.DataFrame:
        """Convert to Polars DataFrame for inspection."""
        return self._to_polars_cached()

    @override
    def row_count(self) -> int:
        """Get number of rows in result."""
        # Use cached DataFrame if available, otherwise query DuckDB
        if self._df is not None:
            return self._df.height
        # Execute a count query
        result = self._relation.aggregate("count(*) as cnt").fetchone()
        return result[0] if result else 0

    @override
    def schema(self) -> dict[str, str]:
        """Get result schema from DuckDB relation."""
        return {
            name: str(dtype)
            for name, dtype in zip(self._relation.columns, self._relation.types)
        }

    @override
    def base_schema(self) -> dict[str, str] | None:
        """
        Get the base schema before metrics were applied.

        Returns:
            Schema of base DataFrame or None if not available
        """
        return self._base_schema


ResultKind = PolarsResult | DuckDBResult
