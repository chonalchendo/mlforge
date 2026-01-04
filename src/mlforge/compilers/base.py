"""
Base compiler abstractions for metric computation.

This module defines the ComputeContext dataclass that carries execution
context for metric compilation.
"""

from dataclasses import dataclass

import polars as pl


@dataclass
class ComputeContext:
    """
    Execution context for metric compilation.

    Carries necessary dataframe and metadata for computing metrics
    over rolling time windows.

    Attributes:
        keys: Entity key columns for grouping
        interval: Time interval for rolling computations (e.g., "1h", "1d")
        timestamp: Timestamp column name
        dataframe: Source dataframe to compute metrics on
        tag: Prefix for naming output columns
    """

    keys: list[str]
    interval: str
    timestamp: str
    dataframe: pl.DataFrame | pl.LazyFrame
    tag: str
