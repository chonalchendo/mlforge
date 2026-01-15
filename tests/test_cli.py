"""Unit tests for CLI commands."""

from unittest.mock import Mock, patch

import pytest

from mlforge.cli import (
    build,
    entities,
    feature,
    features,
    manifest,
    source,
    sources,
    sync,
    versions,
)
from mlforge.cli import entity as inspect_entity
from mlforge.errors import FeatureMaterializationError, SourceDataChangedError


@pytest.fixture
def definitions_file(temp_dir, sample_parquet_file):
    """Create a valid definitions file for testing."""
    definitions_file = temp_dir / "definitions.py"
    store_path = temp_dir / "store"
    definitions_file.write_text(
        f"""
from mlforge import Definitions, LocalStore, feature
import polars as pl

@feature(keys=["id"], source="{sample_parquet_file}")
def test_feature(df):
    return df.select(["id", "value"])

defs = Definitions(
    name="test-project",
    features=[test_feature],
    offline_store=LocalStore("{store_path}")
)
"""
    )
    return definitions_file


def test_build_command_with_default_target(
    definitions_file, temp_dir, monkeypatch
):
    # Given a definitions file in the working directory
    monkeypatch.chdir(temp_dir)
    (temp_dir / "definitions.py").write_text(definitions_file.read_text())

    # When running build command with no target specified
    with patch("mlforge.logging.print_build_summary") as mock_summary:
        build(
            target=None,
            features=None,
            tags=None,
            force=False,
            preview=False,
            preview_rows=5,
        )

    # Then it should build successfully
    mock_summary.assert_called_once()


def test_build_command_with_custom_target(definitions_file):
    # Given a custom definitions file path
    target = str(definitions_file)

    # When running build with custom target
    with patch("mlforge.logging.print_build_summary") as mock_summary:
        build(
            target=target,
            features=None,
            tags=None,
            force=False,
            preview=False,
            preview_rows=5,
        )

    # Then it should build successfully
    mock_summary.assert_called_once()


def test_build_command_with_specific_features(definitions_file):
    # Given a definitions file with multiple features
    target = str(definitions_file)

    # When building specific features by name
    with patch("mlforge.logging.print_build_summary") as mock_summary:
        build(
            target=target,
            features="test_feature",
            tags=None,
            force=False,
            preview=False,
            preview_rows=5,
        )

    # Then it should build only those features
    mock_summary.assert_called_once()


def test_build_command_with_force_flag(definitions_file):
    # Given a definitions file
    target = str(definitions_file)

    # When building with force flag
    with patch("mlforge.logging.print_build_summary") as mock_summary:
        build(
            target=target,
            features=None,
            tags=None,
            force=True,
            preview=False,
            preview_rows=5,
        )

    # Then it should overwrite existing features
    mock_summary.assert_called_once()


def test_build_command_with_preview_enabled(definitions_file):
    # Given a definitions file
    target = str(definitions_file)

    # When building with preview enabled
    with patch("mlforge.logging.print_build_summary") as mock_summary:
        build(
            target=target,
            features=None,
            tags=None,
            force=False,
            preview=True,
            preview_rows=3,
        )

    # Then it should complete and show summary
    mock_summary.assert_called_once()


def test_build_command_handles_load_error(temp_dir):
    # Given an invalid definitions file
    invalid_file = temp_dir / "invalid.py"
    invalid_file.write_text("invalid python code")

    # When/Then building should raise SystemExit on load error
    with pytest.raises(SystemExit) as exc_info:
        build(
            target=str(invalid_file),
            features=None,
            tags=None,
            force=False,
            preview=False,
            preview_rows=5,
        )

    assert exc_info.value.code == 1


def test_build_command_handles_materialization_error(definitions_file):
    # Given a definitions file
    target = str(definitions_file)

    # When materialization fails
    with (
        patch("mlforge.loader.load_definitions") as mock_load,
        pytest.raises(SystemExit) as exc_info,
    ):
        mock_defs = Mock()
        mock_defs.build.side_effect = FeatureMaterializationError(
            feature_name="test_feature", message="Materialization failed"
        )
        mock_load.return_value = mock_defs

        build(
            target=target,
            features=None,
            tags=None,
            force=False,
            preview=False,
            preview_rows=5,
        )

    # Then it should exit with error code
    assert exc_info.value.code == 1


def test_build_command_splits_feature_names(temp_dir, sample_parquet_file):
    # Given a definitions file with multiple features
    definitions_file = temp_dir / "definitions.py"
    store_path = temp_dir / "store"
    definitions_file.write_text(
        f"""
from mlforge import Definitions, LocalStore, feature
import polars as pl

@feature(keys=["id"], source="{sample_parquet_file}")
def feature1(df):
    return df.select(["id"])

@feature(keys=["id"], source="{sample_parquet_file}")
def feature2(df):
    return df.select(["id"])

@feature(keys=["id"], source="{sample_parquet_file}")
def feature3(df):
    return df.select(["id"])

defs = Definitions(
    name="test-project",
    features=[feature1, feature2, feature3],
    offline_store=LocalStore("{store_path}")
)
"""
    )

    # When building specific features with comma-separated names
    with patch("mlforge.logging.print_build_summary") as mock_summary:
        build(
            target=str(definitions_file),
            features="feature1,feature2",
            tags=None,
            force=False,
            preview=False,
            preview_rows=5,
        )

    # Then it should build only the specified features
    mock_summary.assert_called_once()
    # Verify summary indicates 2 features were built
    call_kwargs = mock_summary.call_args[1]
    assert call_kwargs["built"] == 2


def test_list_features_command_with_default_target(
    definitions_file, temp_dir, monkeypatch
):
    # Given a definitions file in the working directory
    monkeypatch.chdir(temp_dir)
    (temp_dir / "definitions.py").write_text(definitions_file.read_text())

    # When running list features command with no target
    with patch("mlforge.logging.print_features_table") as mock_print:
        features(target=None, tags=None)

    # Then it should display features
    mock_print.assert_called_once()


def test_list_features_command_with_custom_target(definitions_file):
    # Given a custom definitions file
    target = str(definitions_file)

    # When running list features with custom target
    with patch("mlforge.logging.print_features_table") as mock_print:
        features(target=target, tags=None)

    # Then it should load and display features
    mock_print.assert_called_once()


def test_list_features_command_displays_all_features(definitions_file):
    # Given a definitions file with features
    target = str(definitions_file)

    # When listing features
    with patch("mlforge.logging.print_features_table") as mock_print:
        features(target=target, tags=None)

    # Then it should pass the features dictionary
    mock_print.assert_called_once()
    features_dict = mock_print.call_args[0][0]
    assert isinstance(features_dict, dict)
    assert "test_feature" in features_dict


def test_launcher_sets_up_logging_with_verbose_flag():
    # Given verbose flag is enabled
    # When launching with verbose flag
    with (
        patch("mlforge.logging.setup_logging") as mock_setup,
        patch("mlforge.cli.app"),
        patch("sys.argv", ["mlforge", "build", "-v"]),
    ):
        from mlforge.cli import main

        main()

    # Then it should enable debug logging
    mock_setup.assert_called_once_with(verbose=True)


def test_main_sets_up_logging_without_verbose_flag():
    # Given verbose flag is not provided
    # When launching without verbose
    with (
        patch("mlforge.logging.setup_logging") as mock_setup,
        patch("mlforge.cli.app"),
        patch("sys.argv", ["mlforge", "build"]),
    ):
        from mlforge.cli import main

        main()

    # Then it should use default logging level
    mock_setup.assert_called_once_with(verbose=False)


def test_main_dispatches_to_app():
    # Given command tokens
    # When launching with tokens
    with (
        patch("mlforge.logging.setup_logging"),
        patch("mlforge.cli.app") as mock_app,
        patch("sys.argv", ["mlforge", "build", "--target", "definitions.py"]),
    ):
        from mlforge.cli import main

        main()

    # Then it should dispatch to app
    mock_app.assert_called_once()


def test_build_command_with_tags(temp_dir, sample_parquet_file):
    # Given a definitions file with tagged features
    definitions_file = temp_dir / "definitions.py"
    store_path = temp_dir / "store"
    definitions_file.write_text(
        f"""
from mlforge import Definitions, LocalStore, feature
import polars as pl

@feature(keys=["id"], source="{sample_parquet_file}", tags=["user"])
def user_feature(df):
    return df.select(["id"])

@feature(keys=["id"], source="{sample_parquet_file}", tags=["transaction"])
def transaction_feature(df):
    return df.select(["id"])

defs = Definitions(
    name="test-project",
    features=[user_feature, transaction_feature],
    offline_store=LocalStore("{store_path}")
)
"""
    )

    # When building with specific tags
    with patch("mlforge.logging.print_build_summary") as mock_summary:
        build(
            target=str(definitions_file),
            features=None,
            tags="user",
            force=False,
            preview=False,
            preview_rows=5,
        )

    # Then it should build only tagged features
    mock_summary.assert_called_once()


def test_build_command_raises_on_tags_and_features_both_specified():
    # Given both tags and features specified
    # When/Then calling build should raise ValueError
    with pytest.raises(
        ValueError, match="Tags and features cannot be specified"
    ):
        build(
            target=None,
            features="feature1",
            tags="tag1",
            force=False,
            preview=False,
            preview_rows=5,
        )


def test_list_features_command_filters_by_tags(temp_dir, sample_parquet_file):
    # Given a definitions file with tagged features
    definitions_file = temp_dir / "definitions.py"
    store_path = temp_dir / "store"
    definitions_file.write_text(
        f"""
from mlforge import Definitions, LocalStore, feature
import polars as pl

@feature(keys=["id"], source="{sample_parquet_file}", tags=["user"])
def user_feature(df):
    return df.select(["id"])

@feature(keys=["id"], source="{sample_parquet_file}", tags=["transaction"])
def transaction_feature(df):
    return df.select(["id"])

defs = Definitions(
    name="test-project",
    features=[user_feature, transaction_feature],
    offline_store=LocalStore("{store_path}")
)
"""
    )

    # When listing with tag filter
    with patch("mlforge.logging.print_features_table") as mock_print:
        features(target=str(definitions_file), tags="user")

    # Then it should display only features with that tag
    mock_print.assert_called_once()
    features_dict = mock_print.call_args[0][0]
    assert "user_feature" in features_dict
    assert "transaction_feature" not in features_dict


def test_list_features_command_warns_on_unknown_tags(
    temp_dir, sample_parquet_file
):
    # Given a definitions file with features
    definitions_file = temp_dir / "definitions.py"
    store_path = temp_dir / "store"
    definitions_file.write_text(
        f"""
from mlforge import Definitions, LocalStore, feature
import polars as pl

@feature(keys=["id"], source="{sample_parquet_file}", tags=["user"])
def user_feature(df):
    return df.select(["id"])

defs = Definitions(
    name="test-project",
    features=[user_feature],
    offline_store=LocalStore("{store_path}")
)
"""
    )

    # When listing with unknown tag it should warn (not raise)
    with patch("mlforge.logging.print_warning") as mock_warning:
        features(target=str(definitions_file), tags="nonexistent")

    mock_warning.assert_called_once()


def test_inspect_feature_command_displays_metadata(definitions_file):
    # Given a built feature with metadata
    target = str(definitions_file)

    # First build the feature to generate metadata
    with patch("mlforge.logging.print_build_summary"):
        build(
            target=target,
            features=None,
            tags=None,
            force=False,
            preview=False,
            preview_rows=5,
        )

    # When inspecting the feature
    with patch("mlforge.logging.print_feature_metadata") as mock_print:
        feature(feature_name="test_feature", target=target)

    # Then it should display the metadata
    mock_print.assert_called_once()
    call_args = mock_print.call_args[0]
    assert call_args[0] == "test_feature"
    assert call_args[1] is not None


def test_inspect_feature_command_handles_missing_metadata(definitions_file):
    # Given a feature that hasn't been built yet
    target = str(definitions_file)

    # When/Then inspecting should exit with error
    with pytest.raises(SystemExit) as exc_info:
        feature(feature_name="test_feature", target=target)

    assert exc_info.value.code == 1


def test_manifest_command_displays_summary(definitions_file):
    # Given a built feature
    target = str(definitions_file)

    # First build the feature
    with patch("mlforge.logging.print_build_summary"):
        build(
            target=target,
            features=None,
            tags=None,
            force=False,
            preview=False,
            preview_rows=5,
        )

    # When running manifest command
    with patch("mlforge.logging.print_manifest_summary") as mock_print:
        manifest(target=target, regenerate=False)

    # Then it should display the summary
    mock_print.assert_called_once()


def test_manifest_command_regenerates_file(definitions_file, temp_dir):
    # Given a built feature
    target = str(definitions_file)

    # First build the feature
    with patch("mlforge.logging.print_build_summary"):
        build(
            target=target,
            features=None,
            tags=None,
            force=False,
            preview=False,
            preview_rows=5,
        )

    # When regenerating manifest
    with patch("mlforge.logging.print_success") as mock_success:
        manifest(target=target, regenerate=True)

    # Then it should create manifest.json
    mock_success.assert_called_once()
    manifest_path = temp_dir / "store" / "manifest.json"
    assert manifest_path.exists()


def test_manifest_command_handles_no_metadata(definitions_file):
    # Given no built features
    target = str(definitions_file)

    # When running manifest command
    with patch("mlforge.logging.print_warning") as mock_warning:
        manifest(target=target, regenerate=False)

    # Then it should show a warning
    mock_warning.assert_called_once()


# =============================================================================
# Sync Command Tests
# =============================================================================


def test_sync_command_dry_run_shows_needs_sync(definitions_file):
    # Given a built feature with missing data
    target = str(definitions_file)

    # First build the feature
    with patch("mlforge.logging.print_build_summary"):
        build(
            target=target,
            features=None,
            tags=None,
            force=False,
            preview=False,
            preview_rows=5,
        )

    # Mock sync to return needs_sync
    with (
        patch("mlforge.loader.load_definitions") as mock_load,
        patch("mlforge.logging.print_info") as mock_info,
    ):
        mock_defs = Mock()
        mock_defs.offline_store = Mock(spec=["path"])
        mock_defs.offline_store.__class__.__name__ = "LocalStore"
        mock_defs.sync.return_value = {
            "needs_sync": ["test_feature"],
            "source_changed": [],
            "synced": [],
        }
        # Make isinstance check pass for LocalStore
        from mlforge.store import LocalStore

        mock_defs.offline_store = Mock(spec=LocalStore)
        mock_load.return_value = mock_defs

        sync(target=target, features=None, dry_run=True, force=False)

    # Then it should show what needs syncing
    assert mock_info.call_count >= 1


def test_sync_command_syncs_missing_features(definitions_file):
    # Given a feature that needs syncing
    target = str(definitions_file)

    with (
        patch("mlforge.loader.load_definitions") as mock_load,
        patch("mlforge.logging.print_success") as mock_success,
    ):
        mock_defs = Mock()
        from mlforge.store import LocalStore

        mock_defs.offline_store = Mock(spec=LocalStore)
        mock_defs.sync.return_value = {
            "needs_sync": ["test_feature"],
            "source_changed": [],
            "synced": ["test_feature"],
        }
        mock_load.return_value = mock_defs

        sync(target=target, features=None, dry_run=False, force=False)

    # Then it should report success
    mock_success.assert_called_once()
    assert "1" in mock_success.call_args[0][0]


def test_sync_command_with_all_up_to_date(definitions_file):
    # Given all features are up to date
    target = str(definitions_file)

    with (
        patch("mlforge.loader.load_definitions") as mock_load,
        patch("mlforge.logging.print_success") as mock_success,
    ):
        mock_defs = Mock()
        from mlforge.store import LocalStore

        mock_defs.offline_store = Mock(spec=LocalStore)
        mock_defs.sync.return_value = {
            "needs_sync": [],
            "source_changed": [],
            "synced": [],
        }
        mock_load.return_value = mock_defs

        sync(target=target, features=None, dry_run=False, force=False)

    # Then it should report all up to date
    mock_success.assert_called_once()
    assert "up to date" in mock_success.call_args[0][0]


def test_sync_command_rejects_non_local_store(definitions_file):
    # Given a definitions file with S3Store
    target = str(definitions_file)

    with (
        patch("mlforge.loader.load_definitions") as mock_load,
        pytest.raises(SystemExit) as exc_info,
    ):
        mock_defs = Mock()
        # Use a non-LocalStore mock
        mock_defs.offline_store = Mock()
        mock_defs.offline_store.__class__.__name__ = "S3Store"
        mock_load.return_value = mock_defs

        sync(target=target, features=None, dry_run=False, force=False)

    assert exc_info.value.code == 1


def test_sync_command_handles_source_changed_error(definitions_file):
    # Given a feature with changed source data
    target = str(definitions_file)

    with (
        patch("mlforge.loader.load_definitions") as mock_load,
        pytest.raises(SystemExit) as exc_info,
    ):
        mock_defs = Mock()
        from mlforge.store import LocalStore

        mock_defs.offline_store = Mock(spec=LocalStore)
        mock_defs.sync.side_effect = SourceDataChangedError(
            feature_name="test_feature",
            expected_hash="abc123",
            current_hash="def456",
            source_path="data/source.parquet",
        )
        mock_load.return_value = mock_defs

        sync(target=target, features=None, dry_run=False, force=False)

    assert exc_info.value.code == 1


def test_sync_command_with_specific_features(definitions_file):
    # Given specific features to sync
    target = str(definitions_file)

    with (
        patch("mlforge.loader.load_definitions") as mock_load,
        patch("mlforge.logging.print_success"),
    ):
        mock_defs = Mock()
        from mlforge.store import LocalStore

        mock_defs.offline_store = Mock(spec=LocalStore)
        mock_defs.sync.return_value = {
            "needs_sync": ["test_feature"],
            "source_changed": [],
            "synced": ["test_feature"],
        }
        mock_load.return_value = mock_defs

        sync(target=target, features="test_feature", dry_run=False, force=False)

    # Then it should pass feature names to sync
    mock_defs.sync.assert_called_once_with(
        feature_names=["test_feature"],
        dry_run=False,
        force=False,
    )


def test_sync_command_dry_run_shows_source_changed(definitions_file):
    # Given a feature with changed source data in dry run mode
    target = str(definitions_file)

    with (
        patch("mlforge.loader.load_definitions") as mock_load,
        patch("mlforge.logging.print_info"),
        patch("mlforge.logging.print_warning") as mock_warning,
    ):
        mock_defs = Mock()
        from mlforge.store import LocalStore

        mock_defs.offline_store = Mock(spec=LocalStore)
        mock_defs.sync.return_value = {
            "needs_sync": ["test_feature"],
            "source_changed": ["test_feature"],
            "synced": [],
        }
        mock_load.return_value = mock_defs

        sync(target=target, features=None, dry_run=True, force=False)

    # Then it should warn about source changes
    assert mock_warning.call_count >= 1


# =============================================================================
# List Entities Command Tests
# =============================================================================


@pytest.fixture
def definitions_file_with_entities(temp_dir, sample_parquet_file):
    """Create a definitions file with entities for testing."""
    definitions_file = temp_dir / "definitions.py"
    store_path = temp_dir / "store"
    definitions_file.write_text(
        f"""
from mlforge import Definitions, LocalStore, feature, Entity

user = Entity(name="user", join_key="user_id")
merchant = Entity(name="merchant", join_key="merchant_id", from_columns=["name", "category"])

@feature(keys=["user_id"], source="{sample_parquet_file}", entities=[user])
def user_feature(df):
    return df.select(["id"]).rename({{"id": "user_id"}})

@feature(keys=["merchant_id"], source="{sample_parquet_file}", entities=[merchant])
def merchant_feature(df):
    return df.select(["id"]).rename({{"id": "merchant_id"}})

defs = Definitions(
    name="test-project",
    features=[user_feature, merchant_feature],
    offline_store=LocalStore("{store_path}")
)
"""
    )
    return definitions_file


def test_list_entities_command(definitions_file_with_entities):
    # Given a definitions file with entities
    target = str(definitions_file_with_entities)

    # When listing entities
    with patch("mlforge.logging.print_entities_table") as mock_print:
        entities(target=target)

    # Then it should display entities
    mock_print.assert_called_once()
    entities_dict = mock_print.call_args[0][0]
    assert "user" in entities_dict
    assert "merchant" in entities_dict


def test_list_entities_command_no_entities(definitions_file):
    # Given a definitions file without explicit entities
    target = str(definitions_file)

    # When listing entities and none found
    with patch("mlforge.logging.print_warning") as mock_warning:
        entities(target=target)

    # Then it should show a warning
    mock_warning.assert_called_once()


# =============================================================================
# List Sources Command Tests
# =============================================================================


def test_list_sources_command(definitions_file):
    # Given a definitions file with sources
    target = str(definitions_file)

    # When listing sources
    with patch("mlforge.logging.print_sources_table") as mock_print:
        sources(target=target)

    # Then it should display sources
    mock_print.assert_called_once()
    sources_dict = mock_print.call_args[0][0]
    assert len(sources_dict) >= 1


# =============================================================================
# List Versions Command Tests
# =============================================================================


def test_list_versions_command(definitions_file):
    # Given a built feature
    target = str(definitions_file)

    # First build the feature
    with patch("mlforge.logging.print_build_summary"):
        build(
            target=target,
            features=None,
            tags=None,
            force=False,
            preview=False,
            preview_rows=5,
        )

    # When listing versions
    with patch("mlforge.logging.print_versions_table") as mock_print:
        versions(feature_name="test_feature", target=target)

    # Then it should display versions
    mock_print.assert_called_once()
    call_args = mock_print.call_args[0]
    assert call_args[0] == "test_feature"


def test_list_versions_command_no_versions(definitions_file):
    # Given a feature that hasn't been built
    target = str(definitions_file)

    # When listing versions
    with patch("mlforge.logging.print_warning") as mock_warning:
        versions(feature_name="test_feature", target=target)

    # Then it should show a warning
    mock_warning.assert_called_once()


# =============================================================================
# Inspect Entity Command Tests
# =============================================================================


def test_inspect_entity_command(definitions_file_with_entities):
    # Given a definitions file with entities
    target = str(definitions_file_with_entities)

    # When inspecting an entity
    with patch("mlforge.logging.print_entity_detail") as mock_print:
        inspect_entity(entity_name="user", target=target)

    # Then it should display entity details
    mock_print.assert_called_once()
    call_args = mock_print.call_args[0]
    assert call_args[0].name == "user"


def test_inspect_entity_command_not_found(definitions_file):
    # Given a definitions file
    target = str(definitions_file)

    # When inspecting a non-existent entity
    with pytest.raises(SystemExit) as exc_info:
        inspect_entity(entity_name="nonexistent", target=target)

    assert exc_info.value.code == 1


# =============================================================================
# Inspect Source Command Tests
# =============================================================================


def test_inspect_source_command(definitions_file):
    # Given a definitions file with a source
    target = str(definitions_file)

    # When inspecting a source (source name is derived from file stem)
    with patch("mlforge.logging.print_source_detail") as mock_print:
        # Get the source name from the sample parquet file
        with patch("mlforge.loader.load_definitions") as mock_load:
            mock_defs = Mock()
            mock_source = Mock()
            mock_source.name = "test_source"
            mock_source.path = "/path/to/source.parquet"
            mock_source.format = Mock()
            mock_source.location = "local"
            mock_defs.get_source.return_value = mock_source
            mock_defs.features_using_source.return_value = ["test_feature"]
            mock_load.return_value = mock_defs

            source(source_name="test_source", target=target)

    # Then it should display source details
    mock_print.assert_called_once()


def test_inspect_source_command_not_found(definitions_file):
    # Given a definitions file
    target = str(definitions_file)

    # When inspecting a non-existent source
    with pytest.raises(SystemExit) as exc_info:
        source(source_name="nonexistent", target=target)

    assert exc_info.value.code == 1


# =============================================================================
# Init Command Tests
# =============================================================================


def test_init_creates_project_structure(temp_dir, monkeypatch):
    """Should create project directory structure."""
    from mlforge.cli import init

    monkeypatch.chdir(temp_dir)

    # When running init command
    with patch("mlforge.logging.print_success"):
        init(name="test-project")

    # Then it should create the expected structure
    project = temp_dir / "test-project"
    assert project.exists()
    assert (project / "src" / "test_project" / "__init__.py").exists()
    assert (project / "src" / "test_project" / "definitions.py").exists()
    assert (project / "src" / "test_project" / "features.py").exists()
    assert (project / "src" / "test_project" / "entities.py").exists()
    assert (project / "pyproject.toml").exists()
    assert (project / "README.md").exists()
    assert (project / ".gitignore").exists()
    assert (project / "data" / ".gitkeep").exists()
    assert (project / "feature_store" / ".gitignore").exists()


def test_init_definitions_content(temp_dir, monkeypatch):
    """Should create definitions.py with correct content."""
    from mlforge.cli import init

    monkeypatch.chdir(temp_dir)

    with patch("mlforge.logging.print_success"):
        init(name="my-project")

    definitions = (
        temp_dir / "my-project" / "src" / "my_project" / "definitions.py"
    ).read_text()

    assert 'name="my-project"' in definitions
    assert "from my_project import features" in definitions
    assert "mlf.LocalStore" in definitions


def test_init_with_online_redis(temp_dir, monkeypatch):
    """Should include Redis config when --online redis."""
    from mlforge.cli import init

    monkeypatch.chdir(temp_dir)

    with patch("mlforge.logging.print_success"):
        init(name="test-project", online="redis")

    definitions = (
        temp_dir / "test-project" / "src" / "test_project" / "definitions.py"
    ).read_text()

    assert "RedisStore" in definitions
    assert 'host="localhost"' in definitions
    assert "port=6379" in definitions


def test_init_with_online_valkey(temp_dir, monkeypatch):
    """Should include Valkey config when --online valkey."""
    from mlforge.cli import init

    monkeypatch.chdir(temp_dir)

    with patch("mlforge.logging.print_success"):
        init(name="test-project", online="valkey")

    definitions = (
        temp_dir / "test-project" / "src" / "test_project" / "definitions.py"
    ).read_text()

    assert "ValkeyStore" in definitions


def test_init_with_engine_duckdb(temp_dir, monkeypatch):
    """Should include duckdb engine when --engine duckdb."""
    from mlforge.cli import init

    monkeypatch.chdir(temp_dir)

    with patch("mlforge.logging.print_success"):
        init(name="test-project", engine="duckdb")

    definitions = (
        temp_dir / "test-project" / "src" / "test_project" / "definitions.py"
    ).read_text()
    pyproject = (temp_dir / "test-project" / "pyproject.toml").read_text()

    assert 'engine="duckdb"' in definitions
    assert "mlforge[duckdb]>=0.6.0" in pyproject


def test_init_with_store_s3(temp_dir, monkeypatch):
    """Should configure S3Store when --store s3."""
    from mlforge.cli import init

    monkeypatch.chdir(temp_dir)

    with patch("mlforge.logging.print_success"):
        init(name="test-project", store="s3")

    definitions = (
        temp_dir / "test-project" / "src" / "test_project" / "definitions.py"
    ).read_text()

    assert "S3Store" in definitions
    assert 'bucket="my-bucket"' in definitions
    assert 'prefix="features"' in definitions


def test_init_with_profile(temp_dir, monkeypatch):
    """Should create mlforge.yaml when --profile."""
    from mlforge.cli import init

    monkeypatch.chdir(temp_dir)

    with patch("mlforge.logging.print_success"):
        init(name="test-project", with_profile=True)

    assert (temp_dir / "test-project" / "mlforge.yaml").exists()
    config = (temp_dir / "test-project" / "mlforge.yaml").read_text()
    assert "default_profile: dev" in config
    assert "profiles:" in config


def test_init_existing_directory_fails(temp_dir, monkeypatch):
    """Should fail if directory exists."""
    from mlforge.cli import init

    monkeypatch.chdir(temp_dir)
    (temp_dir / "existing").mkdir()

    with pytest.raises(SystemExit) as exc_info:
        init(name="existing")

    assert exc_info.value.code == 1


def test_init_invalid_online_option(temp_dir, monkeypatch):
    """Should fail with invalid online option."""
    from mlforge.cli import init

    monkeypatch.chdir(temp_dir)

    with pytest.raises(SystemExit) as exc_info:
        init(name="test-project", online="invalid")

    assert exc_info.value.code == 1


def test_init_invalid_engine_option(temp_dir, monkeypatch):
    """Should fail with invalid engine option."""
    from mlforge.cli import init

    monkeypatch.chdir(temp_dir)

    with pytest.raises(SystemExit) as exc_info:
        init(name="test-project", engine="invalid")

    assert exc_info.value.code == 1


def test_init_invalid_store_option(temp_dir, monkeypatch):
    """Should fail with invalid store option."""
    from mlforge.cli import init

    monkeypatch.chdir(temp_dir)

    with pytest.raises(SystemExit) as exc_info:
        init(name="test-project", store="invalid")

    assert exc_info.value.code == 1


def test_init_hyphenated_name_converts_to_underscore(temp_dir, monkeypatch):
    """Should convert hyphenated names to underscores for module."""
    from mlforge.cli import init

    monkeypatch.chdir(temp_dir)

    with patch("mlforge.logging.print_success"):
        init(name="my-cool-project")

    # Module name should use underscores
    assert (
        temp_dir / "my-cool-project" / "src" / "my_cool_project" / "__init__.py"
    ).exists()

    # But project name should remain hyphenated in config
    pyproject = (temp_dir / "my-cool-project" / "pyproject.toml").read_text()
    assert 'name = "my-cool-project"' in pyproject


def test_init_all_options_combined(temp_dir, monkeypatch):
    """Should handle all options together."""
    from mlforge.cli import init

    monkeypatch.chdir(temp_dir)

    with patch("mlforge.logging.print_success"):
        init(
            name="full-project",
            online="redis",
            engine="duckdb",
            store="s3",
            with_profile=True,
        )

    project = temp_dir / "full-project"
    definitions = (
        project / "src" / "full_project" / "definitions.py"
    ).read_text()

    assert "S3Store" in definitions
    assert "RedisStore" in definitions
    assert 'engine="duckdb"' in definitions
    assert (project / "mlforge.yaml").exists()


# =============================================================================
# diff command tests
# =============================================================================


@pytest.fixture
def definitions_with_versions(temp_dir, sample_parquet_file):
    """Create definitions file with two versions of a feature built."""
    import json

    definitions_file = temp_dir / "definitions.py"
    store_path = temp_dir / "store"
    store_path.mkdir()

    definitions_file.write_text(
        f"""
from mlforge import Definitions, LocalStore, feature
import polars as pl

@feature(keys=["id"], source="{sample_parquet_file}")
def test_feature(df):
    return df.select(["id", "value"])

defs = Definitions(
    name="test-project",
    features=[test_feature],
    offline_store=LocalStore("{store_path}")
)
"""
    )

    # Create two versions manually
    feature_dir = store_path / "test_feature"

    # Version 1.0.0
    v1_dir = feature_dir / "1.0.0"
    v1_dir.mkdir(parents=True)
    (v1_dir / ".meta.json").write_text(
        json.dumps(
            {
                "name": "test_feature",
                "version": "1.0.0",
                "path": str(v1_dir / "data.parquet"),
                "entity": "id",
                "keys": ["id"],
                "source": str(sample_parquet_file),
                "row_count": 100,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "content_hash": "abc123",
                "schema_hash": "def456",
                "config_hash": "ghi789",
                "source_hash": "jkl012",
                "columns": [
                    {"name": "id", "dtype": "Int64"},
                    {"name": "value", "dtype": "Float64"},
                ],
                "features": [],
            }
        )
    )

    # Version 2.0.0 (with added column)
    v2_dir = feature_dir / "2.0.0"
    v2_dir.mkdir(parents=True)
    (v2_dir / ".meta.json").write_text(
        json.dumps(
            {
                "name": "test_feature",
                "version": "2.0.0",
                "path": str(v2_dir / "data.parquet"),
                "entity": "id",
                "keys": ["id"],
                "source": str(sample_parquet_file),
                "row_count": 150,
                "created_at": "2024-01-02T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "content_hash": "xyz789",
                "schema_hash": "uvw456",
                "config_hash": "ghi789",
                "source_hash": "jkl012",
                "columns": [
                    {"name": "id", "dtype": "Int64"},
                    {"name": "value", "dtype": "Float64"},
                    {"name": "new_col", "dtype": "String"},
                ],
                "features": [],
            }
        )
    )

    # Write _latest.json pointer
    (feature_dir / "_latest.json").write_text(json.dumps({"version": "2.0.0"}))

    return definitions_file


def test_diff_compares_two_versions(definitions_with_versions):
    """Should compare two specific versions."""
    from mlforge.cli import diff

    with (
        patch("mlforge.logging.print_version_diff") as mock_print,
        pytest.raises(SystemExit) as exc_info,
    ):
        diff(
            feature_name="test_feature",
            version1="1.0.0",
            version2="2.0.0",
            target=str(definitions_with_versions),
        )

    # MINOR change (column added) = exit code 2
    assert exc_info.value.code == 2
    mock_print.assert_called_once()

    # Check the diff result
    diff_result = mock_print.call_args[0][0]
    assert diff_result.feature == "test_feature"
    assert diff_result.version_from == "1.0.0"
    assert diff_result.version_to == "2.0.0"
    assert len(diff_result.schema_changes.added) == 1
    assert diff_result.schema_changes.added[0].name == "new_col"


def test_diff_compares_with_latest(definitions_with_versions):
    """Should compare version with latest when only one version specified."""
    from mlforge.cli import diff

    with (
        patch("mlforge.logging.print_version_diff") as mock_print,
        pytest.raises(SystemExit) as exc_info,
    ):
        diff(
            feature_name="test_feature",
            version1="1.0.0",
            version2=None,
            target=str(definitions_with_versions),
        )

    assert exc_info.value.code == 2
    diff_result = mock_print.call_args[0][0]
    assert diff_result.version_from == "1.0.0"
    assert diff_result.version_to == "2.0.0"


def test_diff_compares_latest_with_previous(definitions_with_versions):
    """Should compare latest with previous when no versions specified."""
    from mlforge.cli import diff

    with (
        patch("mlforge.logging.print_version_diff") as mock_print,
        pytest.raises(SystemExit) as exc_info,
    ):
        diff(
            feature_name="test_feature",
            version1=None,
            version2=None,
            target=str(definitions_with_versions),
        )

    assert exc_info.value.code == 2
    diff_result = mock_print.call_args[0][0]
    assert diff_result.version_from == "1.0.0"
    assert diff_result.version_to == "2.0.0"


def test_diff_json_output(definitions_with_versions):
    """Should output JSON format when requested."""
    from mlforge.cli import diff

    with (
        patch("mlforge.logging.print_version_diff_json") as mock_json,
        pytest.raises(SystemExit),
    ):
        diff(
            feature_name="test_feature",
            version1="1.0.0",
            version2="2.0.0",
            target=str(definitions_with_versions),
            format_="json",
        )

    mock_json.assert_called_once()


def test_diff_quiet_mode(definitions_with_versions):
    """Should not print when quiet mode enabled."""
    from mlforge.cli import diff

    with (
        patch("mlforge.logging.print_version_diff") as mock_print,
        patch("mlforge.logging.print_version_diff_json") as mock_json,
        pytest.raises(SystemExit) as exc_info,
    ):
        diff(
            feature_name="test_feature",
            version1="1.0.0",
            version2="2.0.0",
            target=str(definitions_with_versions),
            quiet=True,
        )

    assert exc_info.value.code == 2
    mock_print.assert_not_called()
    mock_json.assert_not_called()


def test_diff_version_not_found(definitions_with_versions):
    """Should error when version doesn't exist."""
    from mlforge.cli import diff

    with (
        patch("mlforge.logging.print_error"),
        pytest.raises(SystemExit) as exc_info,
    ):
        diff(
            feature_name="test_feature",
            version1="1.0.0",
            version2="9.9.9",
            target=str(definitions_with_versions),
        )

    assert exc_info.value.code == 4


def test_diff_feature_not_found(definitions_with_versions):
    """Should error when feature doesn't exist."""
    from mlforge.cli import diff

    with (
        patch("mlforge.logging.print_error"),
        pytest.raises(SystemExit) as exc_info,
    ):
        diff(
            feature_name="nonexistent_feature",
            version1="1.0.0",
            version2="2.0.0",
            target=str(definitions_with_versions),
        )

    assert exc_info.value.code == 4


# =============================================================================
# rollback command tests
# =============================================================================


def test_rollback_to_specific_version(definitions_with_versions, temp_dir):
    """Should rollback to specific version."""
    import json

    from mlforge.cli import rollback

    with (
        patch("mlforge.logging.print_rollback_result"),
        patch("mlforge.logging.print_success"),
        pytest.raises(SystemExit) as exc_info,
    ):
        rollback(
            feature_name="test_feature",
            version="1.0.0",
            force=True,
            target=str(definitions_with_versions),
        )

    assert exc_info.value.code == 0

    # Check _latest.json was updated
    store_path = temp_dir / "store"
    latest_file = store_path / "test_feature" / "_latest.json"
    latest_data = json.loads(latest_file.read_text())
    assert latest_data["version"] == "1.0.0"


def test_rollback_with_previous_flag(definitions_with_versions, temp_dir):
    """Should rollback to previous version with --previous flag."""
    import json

    from mlforge.cli import rollback

    with (
        patch("mlforge.logging.print_rollback_result"),
        patch("mlforge.logging.print_success"),
        pytest.raises(SystemExit) as exc_info,
    ):
        rollback(
            feature_name="test_feature",
            previous=True,
            force=True,
            target=str(definitions_with_versions),
        )

    assert exc_info.value.code == 0

    store_path = temp_dir / "store"
    latest_file = store_path / "test_feature" / "_latest.json"
    latest_data = json.loads(latest_file.read_text())
    assert latest_data["version"] == "1.0.0"


def test_rollback_dry_run(definitions_with_versions, temp_dir):
    """Should not make changes in dry run mode."""
    import json

    from mlforge.cli import rollback

    with (
        patch("mlforge.logging.print_rollback_result"),
        pytest.raises(SystemExit) as exc_info,
    ):
        rollback(
            feature_name="test_feature",
            version="1.0.0",
            dry_run=True,
            target=str(definitions_with_versions),
        )

    assert exc_info.value.code == 0

    # Check _latest.json was NOT updated
    store_path = temp_dir / "store"
    latest_file = store_path / "test_feature" / "_latest.json"
    latest_data = json.loads(latest_file.read_text())
    assert latest_data["version"] == "2.0.0"


def test_rollback_preserves_data(definitions_with_versions, temp_dir):
    """Should preserve all version directories after rollback."""
    from mlforge.cli import rollback

    with (
        patch("mlforge.logging.print_rollback_result"),
        patch("mlforge.logging.print_success"),
        pytest.raises(SystemExit),
    ):
        rollback(
            feature_name="test_feature",
            version="1.0.0",
            force=True,
            target=str(definitions_with_versions),
        )

    # Both version directories should still exist
    store_path = temp_dir / "store"
    assert (store_path / "test_feature" / "1.0.0").exists()
    assert (store_path / "test_feature" / "2.0.0").exists()


def test_rollback_version_not_found(definitions_with_versions):
    """Should error when version doesn't exist."""
    from mlforge.cli import rollback

    with (
        patch("mlforge.logging.print_error"),
        pytest.raises(SystemExit) as exc_info,
    ):
        rollback(
            feature_name="test_feature",
            version="9.9.9",
            force=True,
            target=str(definitions_with_versions),
        )

    assert exc_info.value.code == 1


def test_rollback_already_at_version(definitions_with_versions):
    """Should error when already at target version."""
    from mlforge.cli import rollback

    with (
        patch("mlforge.logging.print_error"),
        pytest.raises(SystemExit) as exc_info,
    ):
        rollback(
            feature_name="test_feature",
            version="2.0.0",
            force=True,
            target=str(definitions_with_versions),
        )

    assert exc_info.value.code == 2


def test_rollback_requires_version_or_previous(definitions_with_versions):
    """Should error when neither version nor --previous specified."""
    from mlforge.cli import rollback

    with (
        patch("mlforge.logging.print_error"),
        pytest.raises(SystemExit) as exc_info,
    ):
        rollback(
            feature_name="test_feature",
            force=True,
            target=str(definitions_with_versions),
        )

    assert exc_info.value.code == 4


def test_rollback_cancelled_by_user(definitions_with_versions, monkeypatch):
    """Should exit with code 3 when user cancels."""
    from mlforge.cli import rollback

    # Mock input to return 'n'
    monkeypatch.setattr("builtins.input", lambda _: "n")

    with (
        patch("mlforge.logging.print_rollback_confirmation"),
        patch("mlforge.logging.print_info"),
        pytest.raises(SystemExit) as exc_info,
    ):
        rollback(
            feature_name="test_feature",
            version="1.0.0",
            target=str(definitions_with_versions),
        )

    assert exc_info.value.code == 3
