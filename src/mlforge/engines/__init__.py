"""
Computation engines for feature materialization.

This package provides different execution backends for computing features.
Supports Polars (default) and DuckDB (for large datasets).

Usage:
    from mlforge.engines import PolarsEngine, DuckDBEngine, Engine

    # Polars engine (default)
    engine = PolarsEngine()
    result = engine.execute(feature)

    # DuckDB engine (for large datasets)
    engine = DuckDBEngine()
    result = engine.execute(feature)
"""

import duckdb as duckdb_

from mlforge.engines.base import Engine
from mlforge.engines.duckdb import DuckDBEngine
from mlforge.engines.polars import PolarsEngine

# Type alias for all supported engines
EngineKind = PolarsEngine | DuckDBEngine


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
    "get_duckdb_connection",
]
