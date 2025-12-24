from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import polars as pl


class EngineResult(ABC):
    """
    Abstract wrapper for engine-specific computation results.

    Provides a uniform interface for writing results to storage,
    converting to Polars for inspection, and extracting metadata.
    """

    @abstractmethod
    def write_parquet(self, path: Path) -> None:
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


class PolarsResult(EngineResult):
    """
    Polars-based result wrapper.

    Lazily evaluates Polars LazyFrames to avoid unnecessary computation
    until data is needed for writing or inspection.

    Attributes:
        _lf: LazyFrame containing the computation graph
        _df: Materialized DataFrame (cached after first collect)
    """

    def __init__(self, lf: pl.LazyFrame | pl.DataFrame):
        """
        Initialize Polars result wrapper.

        Args:
            lf: Polars LazyFrame or eager DataFrame
        """
        if isinstance(lf, pl.DataFrame):
            self._lf = lf.lazy()
            self._df = lf
        else:
            self._lf = lf
            self._df: pl.DataFrame | None = None

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

    def write_parquet(self, path: Path) -> None:
        self._collect().write_parquet(path)

    def to_polars(self) -> pl.DataFrame:
        return self._collect()

    def row_count(self) -> int:
        return self._collect().height

    def schema(self) -> dict[str, str]:
        return {name: str(dtype) for name, dtype in self._lf.collect_schema().items()}


# class DuckDBResult(EngineResult):
#     def __init__(self, relation):
#         self._relation = relation

#     def write_parquet(self, path: Path) -> None:
#         self._relation.write_parquet(str(path))

#     def to_polars(self) -> pl.DataFrame:
#         return self._relation.pl()

#     def row_count(self) -> int:
#         return self._relation.count("*").fetchone()[0]

#     def schema(self) -> dict[str, str]:
#         return {
#             name: str(dtype)
#             for name, dtype in zip(self._relation.columns, self._relation.types)
#         }


ResultKind = PolarsResult
