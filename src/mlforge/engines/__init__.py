"""
Computation engines for feature materialization.

This package provides different execution backends for computing features.
Supports Polars (default), DuckDB (for large datasets), and PySpark (for
distributed computing on Databricks via Databricks Connect).

Usage:
    from mlforge.engines import PolarsEngine, DuckDBEngine, PySparkEngine, Engine

    # Polars engine (default, local)
    engine = PolarsEngine()
    result = engine.execute(feature)

    # DuckDB engine (for large datasets, local)
    engine = DuckDBEngine()
    result = engine.execute(feature)

    # PySpark engine (for Databricks via Databricks Connect)
    engine = PySparkEngine()
    result = engine.execute(feature)

    # For ad-hoc SQL queries on Databricks (not feature building):
    from mlforge.engines import DatabricksSQLEngine
    engine = DatabricksSQLEngine(host="...", http_path="...", token="...")
    result = engine.query("SELECT * FROM catalog.schema.table")
"""

import duckdb as duckdb_

from mlforge.engines.base import Engine
from mlforge.engines.databricks_sql import DatabricksSQLEngine
from mlforge.engines.duckdb import DuckDBEngine
from mlforge.engines.polars import PolarsEngine
from mlforge.engines.pyspark import PySparkEngine

# Type alias for all supported engines (for feature building)
EngineKind = PolarsEngine | DuckDBEngine | PySparkEngine

# Keep DatabricksEngine as alias for backward compatibility
DatabricksEngine = DatabricksSQLEngine


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
    "DatabricksEngine",  # Backward-compatible alias
    "DatabricksSQLEngine",
    "DuckDBEngine",
    "Engine",
    "EngineKind",
    "PolarsEngine",
    "PySparkEngine",
    "get_duckdb_connection",
]
