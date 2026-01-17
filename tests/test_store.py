import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
import pytest

from mlforge import GCSStore, LocalStore, S3Store
from mlforge.results import PolarsResult

# =============================================================================
# LocalStore Tests
# =============================================================================


def test_local_store_creates_directory():
    # Given a non-existent directory path
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "new_store"

        # When creating LocalStore
        LocalStore(store_path)

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


def test_local_store_path_for_returns_versioned_parquet_path():
    # Given a LocalStore with a feature
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)

        # Write a feature first to set up the version
        df = pl.DataFrame({"id": [1]})
        store.write("my_feature", PolarsResult(df), feature_version="1.0.0")

        # When getting path for a feature (latest)
        path = store.path_for("my_feature")

        # Then it should return versioned parquet file path
        assert path == Path(tmpdir) / "my_feature" / "1.0.0" / "data.parquet"
        assert path.suffix == ".parquet"


def test_local_store_path_for_specific_version():
    # Given a LocalStore with a feature
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)

        # Write a feature
        df = pl.DataFrame({"id": [1]})
        store.write("my_feature", PolarsResult(df), feature_version="1.0.0")

        # When getting path for specific version
        path = store.path_for("my_feature", feature_version="1.0.0")

        # Then it should return that version's path
        assert path == Path(tmpdir) / "my_feature" / "1.0.0" / "data.parquet"


def test_local_store_write_creates_versioned_parquet_file():
    # Given a DataFrame to store
    df = pl.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)

        # When writing the feature with version
        store.write("test_feature", PolarsResult(df), feature_version="1.0.0")

        # Then the parquet file should exist in versioned directory
        expected_path = Path(tmpdir) / "test_feature" / "1.0.0" / "data.parquet"
        assert expected_path.exists()


def test_local_store_write_creates_latest_pointer():
    # Given a DataFrame to store
    df = pl.DataFrame({"id": [1]})

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)

        # When writing the feature
        store.write("test_feature", PolarsResult(df), feature_version="1.0.0")

        # Then the _latest.json pointer should exist
        pointer_path = Path(tmpdir) / "test_feature" / "_latest.json"
        assert pointer_path.exists()

        # And latest version should be correct
        assert store.get_latest_version("test_feature") == "1.0.0"


def test_local_store_read_returns_dataframe():
    # Given a stored feature
    df = pl.DataFrame({"id": [1, 2], "value": [100, 200]})

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)
        store.write("stored_feature", PolarsResult(df), feature_version="1.0.0")

        # When reading the feature (latest)
        result = store.read("stored_feature")

        # Then it should return the same DataFrame
        assert result.equals(df)


def test_local_store_read_specific_version():
    # Given a feature with multiple versions
    df_v1 = pl.DataFrame({"id": [1], "version": [1]})
    df_v2 = pl.DataFrame({"id": [1], "version": [2]})

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)
        store.write("feature", PolarsResult(df_v1), feature_version="1.0.0")
        store.write("feature", PolarsResult(df_v2), feature_version="2.0.0")

        # When reading specific version
        result = store.read("feature", feature_version="1.0.0")

        # Then it should return that version
        assert result["version"][0] == 1


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
        store.write(
            "existing_feature", PolarsResult(df), feature_version="1.0.0"
        )

        # When checking existence (any version)
        exists = store.exists("existing_feature")

        # Then it should return True
        assert exists is True


def test_local_store_exists_with_specific_version():
    # Given a stored feature
    df = pl.DataFrame({"id": [1]})

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)
        store.write("feature", PolarsResult(df), feature_version="1.0.0")

        # When checking specific version
        assert store.exists("feature", feature_version="1.0.0") is True
        assert store.exists("feature", feature_version="2.0.0") is False


def test_local_store_exists_returns_false_for_missing():
    # Given a LocalStore with no features
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)

        # When checking existence
        exists = store.exists("missing_feature")

        # Then it should return False
        assert exists is False


def test_local_store_list_versions():
    # Given a feature with multiple versions
    df = pl.DataFrame({"id": [1]})

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)
        store.write("feature", PolarsResult(df), feature_version="1.0.0")
        store.write("feature", PolarsResult(df), feature_version="1.1.0")
        store.write("feature", PolarsResult(df), feature_version="2.0.0")

        # When listing versions
        versions = store.list_versions("feature")

        # Then it should return sorted versions
        assert versions == ["1.0.0", "1.1.0", "2.0.0"]


def test_local_store_get_latest_version():
    # Given a feature with multiple versions
    df = pl.DataFrame({"id": [1]})

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)
        store.write("feature", PolarsResult(df), feature_version="1.0.0")
        store.write("feature", PolarsResult(df), feature_version="2.0.0")

        # When getting latest version
        latest = store.get_latest_version("feature")

        # Then it should return the latest (most recently written)
        assert latest == "2.0.0"


def test_local_store_write_creates_gitignore():
    # Given a LocalStore
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)
        df = pl.DataFrame({"id": [1]})

        # When writing a feature
        store.write("my_feature", PolarsResult(df), feature_version="1.0.0")

        # Then .gitignore should be created in feature directory
        gitignore_path = Path(tmpdir) / "my_feature" / ".gitignore"
        assert gitignore_path.exists()

        # And content should ignore data.parquet
        content = gitignore_path.read_text()
        assert "*/data.parquet" in content


def test_local_store_write_does_not_overwrite_gitignore():
    # Given a LocalStore with existing .gitignore
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)
        df = pl.DataFrame({"id": [1]})

        # Create feature directory with custom .gitignore
        feature_dir = Path(tmpdir) / "my_feature"
        feature_dir.mkdir(parents=True)
        gitignore_path = feature_dir / ".gitignore"
        gitignore_path.write_text("custom content")

        # When writing a feature
        store.write("my_feature", PolarsResult(df), feature_version="1.0.0")

        # Then .gitignore should not be overwritten
        assert gitignore_path.read_text() == "custom content"


def test_local_store_handles_nested_directory_path():
    # Given a nested directory path
    with tempfile.TemporaryDirectory() as tmpdir:
        nested_path = Path(tmpdir) / "level1" / "level2" / "store"

        # When creating LocalStore
        LocalStore(nested_path)

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
        store.write("schema_test", PolarsResult(df), feature_version="1.0.0")
        result = store.read("schema_test")

        # Then schema should be preserved
        assert result.schema == df.schema


def test_local_store_handles_empty_dataframe():
    # Given an empty DataFrame
    df = pl.DataFrame(
        {"id": [], "value": []}, schema={"id": pl.Int64, "value": pl.Int64}
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)

        # When writing and reading
        store.write("empty", PolarsResult(df), feature_version="1.0.0")
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


# =============================================================================
# S3Store Tests
# =============================================================================


def test_s3_store_initialization_success(mocker):
    # Given a mock S3FileSystem that confirms bucket exists
    mock_s3 = MagicMock()
    mock_s3.exists.return_value = True
    mocker.patch("mlforge.stores.s3.s3fs.S3FileSystem", return_value=mock_s3)

    # When creating S3Store
    store = S3Store(bucket="test-bucket", prefix="features")

    # Then it should initialize successfully
    assert store.bucket == "test-bucket"
    assert store.prefix == "features"
    mock_s3.exists.assert_called_once_with("test-bucket")


def test_s3_store_initialization_strips_prefix_slashes(mocker):
    # Given a mock S3FileSystem
    mock_s3 = MagicMock()
    mock_s3.exists.return_value = True
    mocker.patch("mlforge.stores.s3.s3fs.S3FileSystem", return_value=mock_s3)

    # When creating S3Store with slashes in prefix
    store = S3Store(bucket="test-bucket", prefix="/features/")

    # Then slashes should be stripped
    assert store.prefix == "features"


def test_s3_store_initialization_raises_on_missing_bucket(mocker):
    # Given a mock S3FileSystem that reports bucket doesn't exist
    mock_s3 = MagicMock()
    mock_s3.exists.return_value = False
    mocker.patch("mlforge.stores.s3.s3fs.S3FileSystem", return_value=mock_s3)

    # When/Then creating S3Store should raise ValueError
    with pytest.raises(
        ValueError,
        match="Bucket 'nonexistent-bucket' does not exist or is not accessible",
    ):
        S3Store(bucket="nonexistent-bucket")


def test_s3_store_initialization_with_empty_prefix(mocker):
    # Given a mock S3FileSystem
    mock_s3 = MagicMock()
    mock_s3.exists.return_value = True
    mocker.patch("mlforge.stores.s3.s3fs.S3FileSystem", return_value=mock_s3)

    # When creating S3Store with empty prefix
    store = S3Store(bucket="test-bucket", prefix="")

    # Then prefix should be empty string
    assert store.prefix == ""


def test_s3_store_path_for_returns_versioned_s3_uri(mocker):
    # Given an S3Store with a feature
    mock_s3 = MagicMock()
    mock_s3.exists.return_value = True
    mocker.patch("mlforge.stores.s3.s3fs.S3FileSystem", return_value=mock_s3)
    store = S3Store(bucket="my-bucket", prefix="prod/features")

    # Mock the latest pointer read
    mock_s3.open.return_value.__enter__ = lambda s: s
    mock_s3.open.return_value.__exit__ = MagicMock(return_value=False)
    mock_s3.open.return_value.read.return_value = '{"version": "1.0.0"}'

    # When getting path for a feature
    path = store.path_for("user_age", feature_version="1.0.0")

    # Then it should return versioned S3 URI
    assert path == "s3://my-bucket/prod/features/user_age/1.0.0/data.parquet"
    assert isinstance(path, str)


def test_s3_store_path_for_with_empty_prefix(mocker):
    # Given an S3Store with empty prefix
    mock_s3 = MagicMock()
    mock_s3.exists.return_value = True
    mocker.patch("mlforge.stores.s3.s3fs.S3FileSystem", return_value=mock_s3)
    store = S3Store(bucket="my-bucket", prefix="")

    # When getting path for specific version
    path = store.path_for("user_age", feature_version="1.0.0")

    # Then it should return versioned S3 URI
    assert path == "s3://my-bucket/user_age/1.0.0/data.parquet"


def test_s3_store_write_calls_polars_write_parquet(mocker, sample_dataframe):
    # Given an S3Store and mock write_parquet
    mock_s3 = MagicMock()
    mock_s3.exists.return_value = True
    mocker.patch("mlforge.stores.s3.s3fs.S3FileSystem", return_value=mock_s3)
    mock_write = mocker.patch.object(pl.DataFrame, "write_parquet")
    store = S3Store(bucket="test-bucket", prefix="features")

    # When writing a feature with version
    store.write(
        "test_feature", PolarsResult(sample_dataframe), feature_version="1.0.0"
    )

    # Then it should call write_parquet with correct versioned S3 path
    expected_path = "s3://test-bucket/features/test_feature/1.0.0/data.parquet"
    mock_write.assert_called_once_with(expected_path)


def test_s3_store_list_versions(mocker):
    # Given an S3Store with multiple versions
    mock_s3 = MagicMock()
    mock_s3.exists.return_value = True
    mock_s3.ls.return_value = [
        "test-bucket/features/feature/1.0.0",
        "test-bucket/features/feature/1.1.0",
        "test-bucket/features/feature/2.0.0",
        "test-bucket/features/feature/_latest.json",
    ]
    mocker.patch("mlforge.stores.s3.s3fs.S3FileSystem", return_value=mock_s3)
    store = S3Store(bucket="test-bucket", prefix="features")

    # When listing versions
    versions = store.list_versions("feature")

    # Then it should return sorted versions (excluding _latest.json)
    assert versions == ["1.0.0", "1.1.0", "2.0.0"]


def test_s3_store_stores_region_attribute(mocker):
    # Given a mock S3FileSystem
    mock_s3 = MagicMock()
    mock_s3.exists.return_value = True
    mocker.patch("mlforge.stores.s3.s3fs.S3FileSystem", return_value=mock_s3)

    # When creating S3Store with region
    store = S3Store(bucket="test-bucket", region="us-west-2")

    # Then region should be stored
    assert store.region == "us-west-2"


def test_s3_store_region_defaults_to_none(mocker):
    # Given a mock S3FileSystem
    mock_s3 = MagicMock()
    mock_s3.exists.return_value = True
    mocker.patch("mlforge.stores.s3.s3fs.S3FileSystem", return_value=mock_s3)

    # When creating S3Store without region
    store = S3Store(bucket="test-bucket")

    # Then region should be None
    assert store.region is None


# =============================================================================
# GCSStore Tests
# =============================================================================


def test_gcs_store_initialization_success(mocker):
    # Given a mock GCSFileSystem that confirms bucket exists
    mock_gcs = MagicMock()
    mock_gcs.exists.return_value = True
    mocker.patch.dict(
        "sys.modules",
        {"gcsfs": MagicMock(GCSFileSystem=MagicMock(return_value=mock_gcs))},
    )

    # When creating GCSStore
    store = GCSStore(bucket="test-bucket", prefix="features")

    # Then it should initialize successfully
    assert store.bucket == "test-bucket"
    assert store.prefix == "features"
    mock_gcs.exists.assert_called_once_with("test-bucket")


def test_gcs_store_initialization_strips_prefix_slashes(mocker):
    # Given a mock GCSFileSystem
    mock_gcs = MagicMock()
    mock_gcs.exists.return_value = True
    mocker.patch.dict(
        "sys.modules",
        {"gcsfs": MagicMock(GCSFileSystem=MagicMock(return_value=mock_gcs))},
    )

    # When creating GCSStore with slashes in prefix
    store = GCSStore(bucket="test-bucket", prefix="/features/")

    # Then slashes should be stripped
    assert store.prefix == "features"


def test_gcs_store_initialization_raises_on_missing_bucket(mocker):
    # Given a mock GCSFileSystem that reports bucket doesn't exist
    mock_gcs = MagicMock()
    mock_gcs.exists.return_value = False
    mocker.patch.dict(
        "sys.modules",
        {"gcsfs": MagicMock(GCSFileSystem=MagicMock(return_value=mock_gcs))},
    )

    # When/Then creating GCSStore should raise ValueError
    with pytest.raises(
        ValueError,
        match="Bucket 'nonexistent-bucket' does not exist or is not accessible",
    ):
        GCSStore(bucket="nonexistent-bucket")


def test_gcs_store_initialization_with_empty_prefix(mocker):
    # Given a mock GCSFileSystem
    mock_gcs = MagicMock()
    mock_gcs.exists.return_value = True
    mocker.patch.dict(
        "sys.modules",
        {"gcsfs": MagicMock(GCSFileSystem=MagicMock(return_value=mock_gcs))},
    )

    # When creating GCSStore with empty prefix
    store = GCSStore(bucket="test-bucket", prefix="")

    # Then prefix should be empty string
    assert store.prefix == ""


def test_gcs_store_path_for_returns_versioned_gcs_uri(mocker):
    # Given a GCSStore with a feature
    mock_gcs = MagicMock()
    mock_gcs.exists.return_value = True
    mocker.patch.dict(
        "sys.modules",
        {"gcsfs": MagicMock(GCSFileSystem=MagicMock(return_value=mock_gcs))},
    )
    store = GCSStore(bucket="my-bucket", prefix="prod/features")

    # When getting path for a feature
    path = store.path_for("user_age", feature_version="1.0.0")

    # Then it should return versioned GCS URI
    assert path == "gs://my-bucket/prod/features/user_age/1.0.0/data.parquet"
    assert isinstance(path, str)


def test_gcs_store_path_for_with_empty_prefix(mocker):
    # Given a GCSStore with empty prefix
    mock_gcs = MagicMock()
    mock_gcs.exists.return_value = True
    mocker.patch.dict(
        "sys.modules",
        {"gcsfs": MagicMock(GCSFileSystem=MagicMock(return_value=mock_gcs))},
    )
    store = GCSStore(bucket="my-bucket", prefix="")

    # When getting path for specific version
    path = store.path_for("user_age", feature_version="1.0.0")

    # Then it should return versioned GCS URI
    assert path == "gs://my-bucket/user_age/1.0.0/data.parquet"


def test_gcs_store_write_calls_polars_write_parquet(mocker, sample_dataframe):
    # Given a GCSStore and mock write_parquet
    mock_gcs = MagicMock()
    mock_gcs.exists.return_value = True
    mocker.patch.dict(
        "sys.modules",
        {"gcsfs": MagicMock(GCSFileSystem=MagicMock(return_value=mock_gcs))},
    )
    mock_write = mocker.patch.object(pl.DataFrame, "write_parquet")
    store = GCSStore(bucket="test-bucket", prefix="features")

    # When writing a feature with version
    store.write(
        "test_feature", PolarsResult(sample_dataframe), feature_version="1.0.0"
    )

    # Then it should call write_parquet with correct versioned GCS path
    expected_path = "gs://test-bucket/features/test_feature/1.0.0/data.parquet"
    mock_write.assert_called_once_with(expected_path)


def test_gcs_store_list_versions(mocker):
    # Given a GCSStore with multiple versions
    mock_gcs = MagicMock()
    mock_gcs.exists.return_value = True
    mock_gcs.ls.return_value = [
        "test-bucket/features/feature/1.0.0",
        "test-bucket/features/feature/1.1.0",
        "test-bucket/features/feature/2.0.0",
        "test-bucket/features/feature/_latest.json",
    ]
    mocker.patch.dict(
        "sys.modules",
        {"gcsfs": MagicMock(GCSFileSystem=MagicMock(return_value=mock_gcs))},
    )
    store = GCSStore(bucket="test-bucket", prefix="features")

    # When listing versions
    versions = store.list_versions("feature")

    # Then it should return sorted versions (excluding _latest.json)
    assert versions == ["1.0.0", "1.1.0", "2.0.0"]


def test_gcs_store_exists_with_specific_version(mocker):
    # Given a GCSStore
    mock_gcs = MagicMock()
    mock_gcs.exists.side_effect = lambda p: p in [
        "test-bucket",
        "gs://test-bucket/features/feature/1.0.0/data.parquet",
    ]
    mocker.patch.dict(
        "sys.modules",
        {"gcsfs": MagicMock(GCSFileSystem=MagicMock(return_value=mock_gcs))},
    )
    store = GCSStore(bucket="test-bucket", prefix="features")

    # When checking specific version
    assert store.exists("feature", feature_version="1.0.0") is True
    assert store.exists("feature", feature_version="2.0.0") is False


def test_gcs_store_read_raises_on_missing_feature(mocker):
    # Given a GCSStore with no versions
    mock_gcs = MagicMock()
    mock_gcs.exists.side_effect = (
        lambda p: p == "test-bucket"
    )  # Only bucket exists
    mocker.patch.dict(
        "sys.modules",
        {"gcsfs": MagicMock(GCSFileSystem=MagicMock(return_value=mock_gcs))},
    )
    store = GCSStore(bucket="test-bucket", prefix="features")

    # When/Then reading non-existent feature should raise
    with pytest.raises(FileNotFoundError, match="not found"):
        store.read("nonexistent")


def test_gcs_store_metadata_path_for_returns_versioned_path(mocker):
    # Given a GCSStore
    mock_gcs = MagicMock()
    mock_gcs.exists.return_value = True
    mocker.patch.dict(
        "sys.modules",
        {"gcsfs": MagicMock(GCSFileSystem=MagicMock(return_value=mock_gcs))},
    )
    store = GCSStore(bucket="my-bucket", prefix="features")

    # When getting metadata path for specific version
    path = store.metadata_path_for("user_age", feature_version="1.0.0")

    # Then it should return versioned metadata path
    assert path == "gs://my-bucket/features/user_age/1.0.0/.meta.json"


def test_gcs_store_get_latest_version_returns_none_when_no_pointer(mocker):
    # Given a GCSStore with no latest pointer
    mock_gcs = MagicMock()
    mock_gcs.exists.side_effect = lambda p: p == "test-bucket"
    mocker.patch.dict(
        "sys.modules",
        {"gcsfs": MagicMock(GCSFileSystem=MagicMock(return_value=mock_gcs))},
    )
    store = GCSStore(bucket="test-bucket", prefix="features")

    # When getting latest version
    latest = store.get_latest_version("feature")

    # Then it should return None
    assert latest is None


def test_gcs_store_base_path_with_prefix(mocker):
    # Given a GCSStore with prefix
    mock_gcs = MagicMock()
    mock_gcs.exists.return_value = True
    mocker.patch.dict(
        "sys.modules",
        {"gcsfs": MagicMock(GCSFileSystem=MagicMock(return_value=mock_gcs))},
    )
    store = GCSStore(bucket="my-bucket", prefix="prod/features")

    # When getting base path
    base = store._base_path()

    # Then it should include prefix
    assert base == "gs://my-bucket/prod/features"


def test_gcs_store_base_path_without_prefix(mocker):
    # Given a GCSStore without prefix
    mock_gcs = MagicMock()
    mock_gcs.exists.return_value = True
    mocker.patch.dict(
        "sys.modules",
        {"gcsfs": MagicMock(GCSFileSystem=MagicMock(return_value=mock_gcs))},
    )
    store = GCSStore(bucket="my-bucket", prefix="")

    # When getting base path
    base = store._base_path()

    # Then it should be just the bucket
    assert base == "gs://my-bucket"
