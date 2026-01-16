"""
Computation engines for feature materialization.

This package provides different execution backends for computing features.
Supports Polars (default), DuckDB (for large datasets), and PySpark (for
distributed computing).

Usage:
    from mlforge.engines import PolarsEngine, DuckDBEngine, PySparkEngine, Engine

    # Polars engine (default)
    engine = PolarsEngine()
    result = engine.execute(feature)

    # DuckDB engine (for large datasets)
    engine = DuckDBEngine()
    result = engine.execute(feature)

    # PySpark engine (for distributed computing)
    engine = PySparkEngine()
    result = engine.execute(feature)
"""

import duckdb as duckdb_

from mlforge.engines.base import Engine
from mlforge.engines.duckdb import DuckDBEngine
from mlforge.engines.polars import PolarsEngine
from mlforge.engines.pyspark import PySparkEngine

# Type alias for all supported engines
EngineKind = PolarsEngine | DuckDBEngine | PySparkEngine


def get_duckdb_connection() -> duckdb_.DuckDBPyConnection:
    """
    Create a DuckDB connection with helpful error message if not installed.

    Returns:
        A new DuckDB connection instance

    Raises:
        ImportError: If duckdb is not installed
    """
    return duckdb_.connect()


__all__ = [
    "DuckDBEngine",
    "Engine",
    "EngineKind",
    "PolarsEngine",
    "PySparkEngine",
    "get_duckdb_connection",
]
