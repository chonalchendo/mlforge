"""Unit tests for CLI commands."""

from unittest.mock import Mock, patch

import pytest

from mlforge.cli import build, list_
from mlforge.errors import FeatureMaterializationError


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


def test_build_command_with_default_target(definitions_file, temp_dir, monkeypatch):
    # Given a definitions file in the working directory
    monkeypatch.chdir(temp_dir)
    (temp_dir / "definitions.py").write_text(definitions_file.read_text())

    # When running build command with no target specified
    with (
        patch("mlforge.logging.print_build_results"),
        patch("mlforge.logging.print_success") as mock_success,
    ):
        build(
            target=None,
            features=None,
            tags=None,
            force=False,
            no_preview=True,
            preview_rows=5,
        )

    # Then it should build successfully
    mock_success.assert_called_once()


def test_build_command_with_custom_target(definitions_file):
    # Given a custom definitions file path
    target = str(definitions_file)

    # When running build with custom target
    with (
        patch("mlforge.logging.print_build_results"),
        patch("mlforge.logging.print_success") as mock_success,
    ):
        build(
            target=target,
            features=None,
            tags=None,
            force=False,
            no_preview=True,
            preview_rows=5,
        )

    # Then it should build successfully
    mock_success.assert_called_once()


def test_build_command_with_specific_features(definitions_file):
    # Given a definitions file with multiple features
    target = str(definitions_file)

    # When building specific features by name
    with (
        patch("mlforge.logging.print_build_results"),
        patch("mlforge.logging.print_success") as mock_success,
    ):
        build(
            target=target,
            features="test_feature",
            tags=None,
            force=False,
            no_preview=True,
            preview_rows=5,
        )

    # Then it should build only those features
    mock_success.assert_called_once()


def test_build_command_with_force_flag(definitions_file):
    # Given a definitions file
    target = str(definitions_file)

    # When building with force flag
    with (
        patch("mlforge.logging.print_build_results"),
        patch("mlforge.logging.print_success") as mock_success,
    ):
        build(
            target=target,
            features=None,
            tags=None,
            force=True,
            no_preview=True,
            preview_rows=5,
        )

    # Then it should overwrite existing features
    mock_success.assert_called_once()


def test_build_command_with_preview_enabled(definitions_file):
    # Given a definitions file
    target = str(definitions_file)

    # When building with preview enabled
    with (
        patch("mlforge.logging.print_build_results") as mock_results,
        patch("mlforge.logging.print_success"),
    ):
        build(
            target=target,
            features=None,
            tags=None,
            force=False,
            no_preview=False,
            preview_rows=3,
        )

    # Then it should show preview of results
    mock_results.assert_called_once()


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
            no_preview=True,
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
        mock_defs.materialize.side_effect = FeatureMaterializationError(
            feature_name="test_feature", message="Materialization failed"
        )
        mock_load.return_value = mock_defs

        build(
            target=target,
            features=None,
            tags=None,
            force=False,
            no_preview=True,
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
    with (
        patch("mlforge.logging.print_build_results"),
        patch("mlforge.logging.print_success") as mock_success,
    ):
        build(
            target=str(definitions_file),
            features="feature1,feature2",
            tags=None,
            force=False,
            no_preview=True,
            preview_rows=5,
        )

    # Then it should build only the specified features
    mock_success.assert_called_once()
    # Verify success message indicates 2 features were built
    call_args = mock_success.call_args[0][0]
    assert "2" in call_args


def test_list_command_with_default_target(definitions_file, temp_dir, monkeypatch):
    # Given a definitions file in the working directory
    monkeypatch.chdir(temp_dir)
    (temp_dir / "definitions.py").write_text(definitions_file.read_text())

    # When running list command with no target
    with patch("mlforge.logging.print_features_table") as mock_print:
        list_(target=None, tags=None)

    # Then it should display features
    mock_print.assert_called_once()


def test_list_command_with_custom_target(definitions_file):
    # Given a custom definitions file
    target = str(definitions_file)

    # When running list with custom target
    with patch("mlforge.logging.print_features_table") as mock_print:
        list_(target=target, tags=None)

    # Then it should load and display features
    mock_print.assert_called_once()


def test_list_command_displays_all_features(definitions_file):
    # Given a definitions file with features
    target = str(definitions_file)

    # When listing features
    with patch("mlforge.logging.print_features_table") as mock_print:
        list_(target=target, tags=None)

    # Then it should pass the features dictionary
    mock_print.assert_called_once()
    features_dict = mock_print.call_args[0][0]
    assert isinstance(features_dict, dict)
    assert "test_feature" in features_dict


def test_launcher_sets_up_logging_with_verbose_flag():
    # Given verbose flag is enabled
    # When launching with verbose
    with patch("mlforge.logging.setup_logging") as mock_setup, patch("mlforge.cli.app"):
        from mlforge.cli import launcher

        launcher(verbose=True)

    # Then it should enable debug logging
    mock_setup.assert_called_once_with(verbose=True)


def test_launcher_sets_up_logging_without_verbose_flag():
    # Given verbose flag is disabled
    # When launching without verbose
    with patch("mlforge.logging.setup_logging") as mock_setup, patch("mlforge.cli.app"):
        from mlforge.cli import launcher

        launcher(verbose=False)

    # Then it should use default logging level
    mock_setup.assert_called_once_with(verbose=False)


def test_launcher_dispatches_tokens_to_app():
    # Given command tokens
    tokens = ("build", "--target", "definitions.py")

    # When launching with tokens
    with patch("mlforge.logging.setup_logging"), patch("mlforge.cli.app") as mock_app:
        from mlforge.cli import launcher

        launcher(*tokens, verbose=False)

    # Then it should dispatch tokens to app
    mock_app.assert_called_once_with(tokens)


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
    with (
        patch("mlforge.logging.print_build_results"),
        patch("mlforge.logging.print_success") as mock_success,
    ):
        build(
            target=str(definitions_file),
            features=None,
            tags="user",
            force=False,
            no_preview=True,
            preview_rows=5,
        )

    # Then it should build only tagged features
    mock_success.assert_called_once()


def test_build_command_raises_on_tags_and_features_both_specified():
    # Given both tags and features specified
    # When/Then calling build should raise ValueError
    with pytest.raises(ValueError, match="Tags and features cannot be specified"):
        build(
            target=None,
            features="feature1",
            tags="tag1",
            force=False,
            no_preview=True,
            preview_rows=5,
        )


def test_list_command_filters_by_tags(temp_dir, sample_parquet_file):
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
        list_(target=str(definitions_file), tags="user")

    # Then it should display only features with that tag
    mock_print.assert_called_once()
    features_dict = mock_print.call_args[0][0]
    assert "user_feature" in features_dict
    assert "transaction_feature" not in features_dict


def test_list_command_raises_on_unknown_tags(temp_dir, sample_parquet_file):
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

    # When/Then listing with unknown tag should raise ValueError
    with pytest.raises(ValueError, match="Unknown tags"):
        list_(target=str(definitions_file), tags="nonexistent")
