"""
Source abstraction for mlforge.

This module provides a unified interface for specifying data sources with
automatic location inference and format detection.

Usage:
    import mlforge as mlf

    # Simple case
    source = mlf.Source("data/transactions.parquet")

    # With format options
    source = mlf.Source("data/events.csv", format=mlf.CSVFormat(delimiter="|"))
"""

from mlforge.sources.base import Location, Source
from mlforge.sources.formats import (
    CSVFormat,
    DeltaFormat,
    Format,
    ParquetFormat,
)

__all__ = [
    "Source",
    "Location",
    "Format",
    "ParquetFormat",
    "CSVFormat",
    "DeltaFormat",
]
