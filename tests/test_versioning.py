"""Tests for version module."""

import json
import tempfile
from pathlib import Path

import polars as pl
import pytest

import mlforge.version as version
from mlforge.manifest import ColumnMetadata


class TestChangeType:
    """Tests for ChangeType enum."""

    def test_change_type_values(self):
        assert version.ChangeType.INITIAL.value == "initial"
        assert version.ChangeType.MAJOR.value == "major"
        assert version.ChangeType.MINOR.value == "minor"
        assert version.ChangeType.PATCH.value == "patch"

    def test_is_breaking(self):
        assert version.ChangeType.MAJOR.is_breaking() is True
        assert version.ChangeType.MINOR.is_breaking() is False
        assert version.ChangeType.PATCH.is_breaking() is False
        assert version.ChangeType.INITIAL.is_breaking() is False


class TestChangeSummary:
    """Tests for ChangeSummary dataclass."""

    def test_to_dict(self):
        summary = version.ChangeSummary(
            change_type=version.ChangeType.MINOR,
            reason="columns_added",
            details=["col_a", "col_b"],
        )

        result = summary.to_dict()

        assert result == {
            "bump_type": "minor",
            "reason": "columns_added",
            "details": ["col_a", "col_b"],
        }

    def test_from_dict(self):
        data = {
            "bump_type": "major",
            "reason": "columns_removed",
            "details": ["old_col"],
        }

        summary = version.ChangeSummary.from_dict(data)

        assert summary.change_type == version.ChangeType.MAJOR
        assert summary.reason == "columns_removed"
        assert summary.details == ["old_col"]

    def test_from_dict_missing_details(self):
        data = {"bump_type": "patch", "reason": "data_refresh"}

        summary = version.ChangeSummary.from_dict(data)

        assert summary.details == []


class TestVersionParsing:
    """Tests for version parsing and formatting."""

    def test_parse_version_valid(self):
        assert version.parse_version("1.0.0") == (1, 0, 0)
        assert version.parse_version("10.20.30") == (10, 20, 30)
        assert version.parse_version("0.0.1") == (0, 0, 1)

    def test_parse_version_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid version format"):
            version.parse_version("1.0")

    def test_parse_version_invalid_prefix(self):
        with pytest.raises(ValueError, match="Invalid version format"):
            version.parse_version("v1.0.0")

    def test_parse_version_invalid_chars(self):
        with pytest.raises(ValueError, match="Invalid version format"):
            version.parse_version("1.0.0-beta")

    def test_format_version(self):
        assert version.format_version(1, 2, 3) == "1.2.3"
        assert version.format_version(0, 0, 0) == "0.0.0"

    def test_is_valid_version(self):
        assert version.is_valid_version("1.0.0") is True
        assert version.is_valid_version("10.20.30") is True
        assert version.is_valid_version("v1.0.0") is False
        assert version.is_valid_version("1.0") is False
        assert version.is_valid_version("") is False


class TestVersionBumping:
    """Tests for version bumping."""

    def test_bump_version_major(self):
        assert version.bump_version("1.2.3", version.ChangeType.MAJOR) == "2.0.0"

    def test_bump_version_minor(self):
        assert version.bump_version("1.2.3", version.ChangeType.MINOR) == "1.3.0"

    def test_bump_version_patch(self):
        assert version.bump_version("1.2.3", version.ChangeType.PATCH) == "1.2.4"

    def test_bump_version_major_resets_minor_patch(self):
        assert version.bump_version("1.5.9", version.ChangeType.MAJOR) == "2.0.0"

    def test_bump_version_minor_resets_patch(self):
        assert version.bump_version("1.5.9", version.ChangeType.MINOR) == "1.6.0"

    def test_bump_version_initial_raises(self):
        with pytest.raises(ValueError, match="Cannot bump INITIAL"):
            version.bump_version("1.0.0", version.ChangeType.INITIAL)


class TestVersionSorting:
    """Tests for version sorting."""

    def test_sort_versions(self):
        versions = ["1.10.0", "1.2.0", "2.0.0", "1.0.0"]
        result = version.sort_versions(versions)
        assert result == ["1.0.0", "1.2.0", "1.10.0", "2.0.0"]

    def test_sort_versions_empty(self):
        assert version.sort_versions([]) == []

    def test_sort_versions_single(self):
        assert version.sort_versions(["1.0.0"]) == ["1.0.0"]

    def test_sort_versions_with_patches(self):
        versions = ["1.0.2", "1.0.10", "1.0.1"]
        result = version.sort_versions(versions)
        assert result == ["1.0.1", "1.0.2", "1.0.10"]


class TestPathConstruction:
    """Tests for path construction functions."""

    def test_versioned_data_path(self):
        path = version.versioned_data_path(Path("/store"), "user_spend", "1.0.0")
        assert path == Path("/store/user_spend/1.0.0/data.parquet")

    def test_versioned_metadata_path(self):
        path = version.versioned_metadata_path(Path("/store"), "user_spend", "1.0.0")
        assert path == Path("/store/user_spend/1.0.0/.meta.json")

    def test_latest_pointer_path(self):
        path = version.latest_pointer_path(Path("/store"), "user_spend")
        assert path == Path("/store/user_spend/_latest.json")

    def test_feature_versions_dir(self):
        path = version.feature_versions_dir(Path("/store"), "user_spend")
        assert path == Path("/store/user_spend")


class TestHashComputation:
    """Tests for hash computation functions."""

    def test_compute_schema_hash_deterministic(self):
        cols = [
            ColumnMetadata(name="id", dtype="Int64"),
            ColumnMetadata(name="value", dtype="Float64"),
        ]
        hash1 = version.compute_schema_hash(cols)
        hash2 = version.compute_schema_hash(cols)
        assert hash1 == hash2

    def test_compute_schema_hash_order_independent(self):
        cols1 = [
            ColumnMetadata(name="a", dtype="Int64"),
            ColumnMetadata(name="b", dtype="Float64"),
        ]
        cols2 = [
            ColumnMetadata(name="b", dtype="Float64"),
            ColumnMetadata(name="a", dtype="Int64"),
        ]
        assert version.compute_schema_hash(cols1) == version.compute_schema_hash(cols2)

    def test_compute_schema_hash_differs_on_dtype_change(self):
        cols1 = [ColumnMetadata(name="id", dtype="Int64")]
        cols2 = [ColumnMetadata(name="id", dtype="Int32")]
        assert version.compute_schema_hash(cols1) != version.compute_schema_hash(cols2)

    def test_compute_schema_hash_differs_on_column_change(self):
        cols1 = [ColumnMetadata(name="a", dtype="Int64")]
        cols2 = [ColumnMetadata(name="b", dtype="Int64")]
        assert version.compute_schema_hash(cols1) != version.compute_schema_hash(cols2)

    def test_compute_config_hash_deterministic(self):
        hash1 = version.compute_config_hash(
            keys=["user_id"],
            timestamp="event_time",
            interval="1d",
            metrics_config=[{"type": "Rolling"}],
        )
        hash2 = version.compute_config_hash(
            keys=["user_id"],
            timestamp="event_time",
            interval="1d",
            metrics_config=[{"type": "Rolling"}],
        )
        assert hash1 == hash2

    def test_compute_config_hash_differs_on_key_change(self):
        hash1 = version.compute_config_hash(
            keys=["user_id"],
            timestamp=None,
            interval=None,
            metrics_config=None,
        )
        hash2 = version.compute_config_hash(
            keys=["merchant_id"],
            timestamp=None,
            interval=None,
            metrics_config=None,
        )
        assert hash1 != hash2

    def test_compute_content_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "data.parquet"
            df = pl.DataFrame({"id": [1, 2, 3]})
            df.write_parquet(path)

            hash_result = version.compute_content_hash(path)

            assert isinstance(hash_result, str)
            assert len(hash_result) == 12  # First 12 chars of SHA256

    def test_compute_content_hash_deterministic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "data.parquet"
            df = pl.DataFrame({"id": [1, 2, 3]})
            df.write_parquet(path)

            hash1 = version.compute_content_hash(path)
            hash2 = version.compute_content_hash(path)

            assert hash1 == hash2

    def test_compute_source_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "source.parquet"
            df = pl.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})
            df.write_parquet(path)

            hash_result = version.compute_source_hash(path)

            assert isinstance(hash_result, str)
            assert len(hash_result) == 12  # First 12 chars of SHA256

    def test_compute_source_hash_deterministic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "source.parquet"
            df = pl.DataFrame({"id": [1, 2, 3]})
            df.write_parquet(path)

            hash1 = version.compute_source_hash(path)
            hash2 = version.compute_source_hash(path)

            assert hash1 == hash2

    def test_compute_source_hash_accepts_string_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "source.parquet"
            df = pl.DataFrame({"id": [1, 2, 3]})
            df.write_parquet(path)

            # Pass as string instead of Path
            hash_result = version.compute_source_hash(str(path))

            assert isinstance(hash_result, str)
            assert len(hash_result) == 12

    def test_compute_source_hash_differs_on_content_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "source.parquet"

            # Write first version
            df1 = pl.DataFrame({"id": [1, 2, 3]})
            df1.write_parquet(path)
            hash1 = version.compute_source_hash(path)

            # Write different content
            df2 = pl.DataFrame({"id": [1, 2, 3, 4]})
            df2.write_parquet(path)
            hash2 = version.compute_source_hash(path)

            assert hash1 != hash2


class TestChangeDetection:
    """Tests for change type detection."""

    def test_detect_initial_when_no_previous(self):
        result = version.detect_change_type(
            previous_columns=None,
            current_columns=["a", "b"],
            previous_schema_hash=None,
            current_schema_hash="abc123",
            previous_config_hash=None,
            current_config_hash="def456",
        )
        assert result == version.ChangeType.INITIAL

    def test_detect_initial_when_no_previous_schema_hash(self):
        result = version.detect_change_type(
            previous_columns=["a", "b"],
            current_columns=["a", "b"],
            previous_schema_hash=None,
            current_schema_hash="abc123",
            previous_config_hash="123",
            current_config_hash="123",
        )
        assert result == version.ChangeType.INITIAL

    def test_detect_major_on_column_removed(self):
        result = version.detect_change_type(
            previous_columns=["a", "b", "c"],
            current_columns=["a", "b"],
            previous_schema_hash="abc",
            current_schema_hash="def",
            previous_config_hash="123",
            current_config_hash="123",
        )
        assert result == version.ChangeType.MAJOR

    def test_detect_minor_on_column_added(self):
        result = version.detect_change_type(
            previous_columns=["a", "b"],
            current_columns=["a", "b", "c"],
            previous_schema_hash="abc",
            current_schema_hash="def",
            previous_config_hash="123",
            current_config_hash="123",
        )
        assert result == version.ChangeType.MINOR

    def test_detect_major_on_dtype_change(self):
        # Same columns but different schema hash = dtype change
        result = version.detect_change_type(
            previous_columns=["a", "b"],
            current_columns=["a", "b"],
            previous_schema_hash="abc",
            current_schema_hash="def",
            previous_config_hash="123",
            current_config_hash="123",
        )
        assert result == version.ChangeType.MAJOR

    def test_detect_minor_on_config_change(self):
        result = version.detect_change_type(
            previous_columns=["a", "b"],
            current_columns=["a", "b"],
            previous_schema_hash="abc",
            current_schema_hash="abc",
            previous_config_hash="123",
            current_config_hash="456",
        )
        assert result == version.ChangeType.MINOR

    def test_detect_patch_on_data_refresh(self):
        result = version.detect_change_type(
            previous_columns=["a", "b"],
            current_columns=["a", "b"],
            previous_schema_hash="abc",
            current_schema_hash="abc",
            previous_config_hash="123",
            current_config_hash="123",
        )
        assert result == version.ChangeType.PATCH


class TestBuildChangeSummary:
    """Tests for building change summaries."""

    def test_build_summary_initial(self):
        summary = version.build_change_summary(
            version.ChangeType.INITIAL, None, ["a", "b"]
        )
        assert summary.change_type == version.ChangeType.INITIAL
        assert summary.reason == "first_build"
        assert summary.details == []

    def test_build_summary_columns_removed(self):
        summary = version.build_change_summary(
            version.ChangeType.MAJOR, ["a", "b", "c"], ["a", "b"]
        )
        assert summary.change_type == version.ChangeType.MAJOR
        assert summary.reason == "columns_removed"
        assert summary.details == ["c"]

    def test_build_summary_columns_added(self):
        summary = version.build_change_summary(
            version.ChangeType.MINOR, ["a", "b"], ["a", "b", "c"]
        )
        assert summary.change_type == version.ChangeType.MINOR
        assert summary.reason == "columns_added"
        assert summary.details == ["c"]

    def test_build_summary_config_changed(self):
        summary = version.build_change_summary(
            version.ChangeType.MINOR, ["a", "b"], ["a", "b"]
        )
        assert summary.change_type == version.ChangeType.MINOR
        assert summary.reason == "config_changed"
        assert summary.details == []

    def test_build_summary_data_refresh(self):
        summary = version.build_change_summary(
            version.ChangeType.PATCH, ["a", "b"], ["a", "b"]
        )
        assert summary.change_type == version.ChangeType.PATCH
        assert summary.reason == "data_refresh"
        assert summary.details == []


class TestVersionDiscovery:
    """Tests for version discovery functions."""

    def test_list_versions_empty_store(self, temp_dir):
        versions = version.list_versions(temp_dir, "nonexistent")
        assert versions == []

    def test_list_versions_finds_versions(self, temp_dir):
        # Create version directories
        (temp_dir / "feature" / "1.0.0").mkdir(parents=True)
        (temp_dir / "feature" / "1.1.0").mkdir(parents=True)
        (temp_dir / "feature" / "2.0.0").mkdir(parents=True)

        versions = version.list_versions(temp_dir, "feature")
        assert versions == ["1.0.0", "1.1.0", "2.0.0"]

    def test_list_versions_ignores_non_version_dirs(self, temp_dir):
        (temp_dir / "feature" / "1.0.0").mkdir(parents=True)
        (temp_dir / "feature" / "_latest.json").touch()
        (temp_dir / "feature" / "not-a-version").mkdir(parents=True)

        versions = version.list_versions(temp_dir, "feature")
        assert versions == ["1.0.0"]

    def test_get_latest_version_reads_pointer(self, temp_dir):
        (temp_dir / "feature").mkdir()
        version.write_latest_pointer(temp_dir, "feature", "1.2.3")

        latest = version.get_latest_version(temp_dir, "feature")
        assert latest == "1.2.3"

    def test_get_latest_version_returns_none_if_missing(self, temp_dir):
        latest = version.get_latest_version(temp_dir, "nonexistent")
        assert latest is None

    def test_write_latest_pointer_creates_file(self, temp_dir):
        version.write_latest_pointer(temp_dir, "feature", "1.0.0")

        pointer_path = temp_dir / "feature" / "_latest.json"
        assert pointer_path.exists()

        with open(pointer_path) as f:
            data = json.load(f)
        assert data == {"version": "1.0.0"}

    def test_resolve_version_explicit(self, temp_dir):
        result = version.resolve_version(temp_dir, "feature", "1.0.0")
        assert result == "1.0.0"

    def test_resolve_version_latest(self, temp_dir):
        (temp_dir / "feature").mkdir()
        version.write_latest_pointer(temp_dir, "feature", "2.0.0")

        result = version.resolve_version(temp_dir, "feature", None)
        assert result == "2.0.0"

    def test_resolve_version_none_when_no_versions(self, temp_dir):
        result = version.resolve_version(temp_dir, "nonexistent", None)
        assert result is None


class TestGitIntegration:
    """Tests for Git integration functions."""

    def test_write_feature_gitignore_creates_file(self, temp_dir):
        # When writing gitignore for a new feature
        created = version.write_feature_gitignore(temp_dir, "my_feature")

        # Then it should create the file
        assert created is True
        gitignore_path = temp_dir / "my_feature" / ".gitignore"
        assert gitignore_path.exists()

    def test_write_feature_gitignore_content(self, temp_dir):
        # When writing gitignore
        version.write_feature_gitignore(temp_dir, "my_feature")

        # Then content should match expected pattern
        gitignore_path = temp_dir / "my_feature" / ".gitignore"
        content = gitignore_path.read_text()
        assert "*/data.parquet" in content
        assert "Auto-generated by mlforge" in content

    def test_write_feature_gitignore_does_not_overwrite(self, temp_dir):
        # Given an existing gitignore with custom content
        feature_dir = temp_dir / "my_feature"
        feature_dir.mkdir(parents=True)
        gitignore_path = feature_dir / ".gitignore"
        gitignore_path.write_text("custom content")

        # When writing gitignore
        created = version.write_feature_gitignore(temp_dir, "my_feature")

        # Then it should not overwrite
        assert created is False
        assert gitignore_path.read_text() == "custom content"

    def test_write_feature_gitignore_creates_directory(self, temp_dir):
        # When writing gitignore for a feature that doesn't have a directory
        version.write_feature_gitignore(temp_dir, "new_feature")

        # Then the directory should be created
        assert (temp_dir / "new_feature").exists()
        assert (temp_dir / "new_feature" / ".gitignore").exists()
