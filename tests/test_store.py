import tempfile
from pathlib import Path

import polars as pl
import pytest

from mlforge import LocalStore


def test_local_store_creates_directory():
    # Given a non-existent directory path
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "new_store"

        # When creating LocalStore
        store = LocalStore(store_path)

        # Then the directory should be created
        assert store_path.exists()
        assert store_path.is_dir()


def test_local_store_accepts_existing_directory():
    # Given an existing directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # When creating LocalStore
        store = LocalStore(tmpdir)

        # Then it should work without errors
        assert store.path == Path(tmpdir)


def test_local_store_path_for_returns_parquet_path():
    # Given a LocalStore
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)

        # When getting path for a feature
        path = store.path_for("my_feature")

        # Then it should return parquet file path
        assert path == Path(tmpdir) / "my_feature.parquet"
        assert path.suffix == ".parquet"


def test_local_store_write_creates_parquet_file():
    # Given a DataFrame to store
    df = pl.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)

        # When writing the feature
        store.write("test_feature", df)

        # Then the parquet file should exist
        expected_path = Path(tmpdir) / "test_feature.parquet"
        assert expected_path.exists()


def test_local_store_read_returns_dataframe():
    # Given a stored feature
    df = pl.DataFrame({"id": [1, 2], "value": [100, 200]})

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)
        store.write("stored_feature", df)

        # When reading the feature
        result = store.read("stored_feature")

        # Then it should return the same DataFrame
        assert result.equals(df)


def test_local_store_read_raises_on_missing_feature():
    # Given a LocalStore with no features
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)

        # When/Then reading non-existent feature should raise
        with pytest.raises(FileNotFoundError):
            store.read("nonexistent")


def test_local_store_exists_returns_true_for_existing():
    # Given a stored feature
    df = pl.DataFrame({"id": [1]})

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)
        store.write("existing_feature", df)

        # When checking existence
        exists = store.exists("existing_feature")

        # Then it should return True
        assert exists is True


def test_local_store_exists_returns_false_for_missing():
    # Given a LocalStore with no features
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)

        # When checking existence
        exists = store.exists("missing_feature")

        # Then it should return False
        assert exists is False


def test_local_store_write_overwrites_existing():
    # Given an existing feature
    df_v1 = pl.DataFrame({"id": [1], "version": [1]})
    df_v2 = pl.DataFrame({"id": [1], "version": [2]})

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)

        # When writing twice to the same feature
        store.write("versioned", df_v1)
        store.write("versioned", df_v2)

        # Then it should overwrite with latest version
        result = store.read("versioned")
        assert result["version"][0] == 2


def test_local_store_handles_nested_directory_path():
    # Given a nested directory path
    with tempfile.TemporaryDirectory() as tmpdir:
        nested_path = Path(tmpdir) / "level1" / "level2" / "store"

        # When creating LocalStore
        store = LocalStore(nested_path)

        # Then all parent directories should be created
        assert nested_path.exists()
        assert nested_path.is_dir()


def test_local_store_preserves_dataframe_schema():
    # Given a DataFrame with specific schema
    df = pl.DataFrame(
        {
            "string_col": ["a", "b"],
            "int_col": [1, 2],
            "float_col": [1.5, 2.5],
            "bool_col": [True, False],
        }
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)

        # When writing and reading
        store.write("schema_test", df)
        result = store.read("schema_test")

        # Then schema should be preserved
        assert result.schema == df.schema


def test_local_store_handles_empty_dataframe():
    # Given an empty DataFrame
    df = pl.DataFrame({"id": [], "value": []}, schema={"id": pl.Int64, "value": pl.Int64})

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)

        # When writing and reading
        store.write("empty", df)
        result = store.read("empty")

        # Then it should preserve the empty DataFrame
        assert len(result) == 0
        assert result.schema == df.schema


def test_local_store_accepts_string_path():
    # Given a string path
    with tempfile.TemporaryDirectory() as tmpdir:
        # When creating LocalStore with string
        store = LocalStore(tmpdir)

        # Then it should work correctly
        assert store.path == Path(tmpdir)


def test_local_store_accepts_path_object():
    # Given a Path object
    with tempfile.TemporaryDirectory() as tmpdir:
        path_obj = Path(tmpdir)

        # When creating LocalStore with Path
        store = LocalStore(path_obj)

        # Then it should work correctly
        assert store.path == path_obj
