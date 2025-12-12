"""Shared test fixtures for mlforge tests."""

import tempfile
from pathlib import Path

import polars as pl
import pytest

from mlforge import LocalStore


@pytest.fixture
def temp_dir():
    """Temporary directory that's cleaned up after test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_store(temp_dir):
    """LocalStore instance in a temporary directory."""
    return LocalStore(temp_dir)


@pytest.fixture
def sample_dataframe():
    """Standard sample DataFrame for testing."""
    return pl.DataFrame(
        {
            "id": [1, 2, 3],
            "user_id": ["alice", "bob", "charlie"],
            "value": [100.0, 200.0, 300.0],
        }
    )


@pytest.fixture
def sample_parquet_file(temp_dir, sample_dataframe):
    """Sample parquet file with test data."""
    file_path = temp_dir / "sample.parquet"
    sample_dataframe.write_parquet(file_path)
    return file_path
