"""
Metric compilers for feature computation.

This package provides compilers that translate high-level metric specifications
into engine-specific computations.

Usage:
    from mlforge.compilers import PolarsCompiler, ComputeContext

    compiler = PolarsCompiler()
    ctx = ComputeContext(keys=["user_id"], interval="1d", ...)
    result = compiler.compile(metric, ctx)

    # For DuckDB
    from mlforge.compilers import DuckDBCompiler, DuckDBComputeContext

    compiler = DuckDBCompiler()
    ctx = DuckDBComputeContext(keys=["user_id"], interval="1d", ...)
    result = compiler.compile(metric, ctx)
"""

from mlforge.compilers.base import ComputeContext
from mlforge.compilers.duckdb import DuckDBCompiler, DuckDBComputeContext
from mlforge.compilers.polars import PolarsCompiler

__all__ = [
    "ComputeContext",
    "DuckDBCompiler",
    "DuckDBComputeContext",
    "PolarsCompiler",
]
