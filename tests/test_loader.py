import tempfile
from pathlib import Path

import polars as pl
import pytest

from mlforge import Definitions, LocalStore, feature
from mlforge.errors import DefinitionsLoadError
from mlforge.loader import load_definitions


def test_load_definitions_from_file():
    # Given a Python file with a Definitions instance
    with tempfile.TemporaryDirectory() as tmpdir:
        definitions_file = Path(tmpdir) / "defs.py"
        store_path = Path(tmpdir) / "store"
        definitions_file.write_text(
            f"""
from mlforge import Definitions, LocalStore

defs = Definitions(
    name="test-project",
    features=[],
    offline_store=LocalStore("{store_path}")
)
"""
        )

        # When loading definitions
        result = load_definitions(str(definitions_file))

        # Then it should return the Definitions instance
        assert isinstance(result, Definitions)
        assert result.name == "test-project"


def test_load_definitions_with_features():
    # Given a file with features
    with tempfile.TemporaryDirectory() as tmpdir:
        definitions_file = Path(tmpdir) / "defs.py"
        store_path = Path(tmpdir) / "store"
        definitions_file.write_text(
            f"""
from mlforge import Definitions, LocalStore, feature
import polars as pl

@feature(keys=["id"], source="data.parquet")
def my_feature(df):
    return df

defs = Definitions(
    name="test",
    features=[my_feature],
    offline_store=LocalStore("{store_path}")
)
"""
        )

        # When loading definitions
        result = load_definitions(str(definitions_file))

        # Then features should be registered
        assert len(result.features) == 1
        assert "my_feature" in result.features


def test_load_definitions_defaults_to_definitions_py():
    # Given a definitions.py file in current directory
    with tempfile.TemporaryDirectory() as tmpdir:
        definitions_file = Path(tmpdir) / "definitions.py"
        store_path = Path(tmpdir) / "store"
        definitions_file.write_text(
            f"""
from mlforge import Definitions, LocalStore

defs = Definitions(name="default", features=[], offline_store=LocalStore("{store_path}"))
"""
        )

        # When loading without specifying target
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            result = load_definitions()

            # Then it should load definitions.py
            assert result.name == "default"
        finally:
            os.chdir(original_cwd)


def test_load_definitions_raises_on_missing_file():
    # Given a non-existent file path
    # When/Then loading should raise FileNotFoundError
    with pytest.raises(FileNotFoundError, match="File not found"):
        load_definitions("nonexistent.py")


def test_load_definitions_raises_on_non_python_file():
    # Given a non-Python file
    with tempfile.TemporaryDirectory() as tmpdir:
        txt_file = Path(tmpdir) / "definitions.txt"
        txt_file.write_text("not python")

        # When/Then loading should raise ValueError
        with pytest.raises(ValueError, match="Expected a Python file"):
            load_definitions(str(txt_file))


def test_load_definitions_raises_on_syntax_error():
    # Given a file with syntax errors
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_file = Path(tmpdir) / "bad.py"
        bad_file.write_text("this is not valid python syntax ][")

        # When/Then loading should raise DefinitionsLoadError
        with pytest.raises(DefinitionsLoadError, match="Failed to load"):
            load_definitions(str(bad_file))


def test_load_definitions_raises_on_import_error():
    # Given a file with import errors
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_file = Path(tmpdir) / "imports.py"
        bad_file.write_text("import nonexistent_module")

        # When/Then loading should raise DefinitionsLoadError
        with pytest.raises(DefinitionsLoadError, match="Failed to load"):
            load_definitions(str(bad_file))


def test_load_definitions_raises_when_no_definitions_found():
    # Given a file with no Definitions instance
    with tempfile.TemporaryDirectory() as tmpdir:
        empty_file = Path(tmpdir) / "empty.py"
        empty_file.write_text(
            """
x = 42
def some_function():
    pass
"""
        )

        # When/Then loading should raise DefinitionsLoadError with hint
        with pytest.raises(
            DefinitionsLoadError, match="No Definitions instance found"
        ) as exc_info:
            load_definitions(str(empty_file))

        assert "defs = Definitions" in str(exc_info.value)


def test_load_definitions_raises_on_multiple_definitions():
    # Given a file with multiple Definitions instances
    with tempfile.TemporaryDirectory() as tmpdir:
        multi_file = Path(tmpdir) / "multi.py"
        store_path1 = Path(tmpdir) / "store1"
        store_path2 = Path(tmpdir) / "store2"
        multi_file.write_text(
            f"""
from mlforge import Definitions, LocalStore

defs1 = Definitions(name="first", features=[], offline_store=LocalStore("{store_path1}"))
defs2 = Definitions(name="second", features=[], offline_store=LocalStore("{store_path2}"))
"""
        )

        # When/Then loading should raise DefinitionsLoadError
        with pytest.raises(
            DefinitionsLoadError, match="Multiple Definitions found"
        ) as exc_info:
            load_definitions(str(multi_file))

        assert "exactly one" in str(exc_info.value)


def test_load_definitions_handles_relative_imports():
    # Given a file that imports local modules
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create helper module
        helper_file = Path(tmpdir) / "helper.py"
        helper_file.write_text(
            """
from mlforge import feature

@feature(keys=["id"], source="data.parquet")
def helper_feature(df):
    return df
"""
        )

        # Create definitions file that imports helper
        definitions_file = Path(tmpdir) / "definitions.py"
        store_path = Path(tmpdir) / "store"
        definitions_file.write_text(
            f"""
from mlforge import Definitions, LocalStore
from helper import helper_feature

defs = Definitions(
    name="test",
    features=[helper_feature],
    offline_store=LocalStore("{store_path}")
)
"""
        )

        # When loading definitions
        result = load_definitions(str(definitions_file))

        # Then it should resolve relative imports
        assert "helper_feature" in result.features


def test_load_definitions_provides_traceback_on_error():
    # Given a file that raises an error during execution
    with tempfile.TemporaryDirectory() as tmpdir:
        error_file = Path(tmpdir) / "error.py"
        store_path = Path(tmpdir) / "store"
        error_file.write_text(
            f"""
from mlforge import Definitions, LocalStore

def will_fail():
    raise RuntimeError("Something went wrong")

will_fail()

defs = Definitions(name="test", features=[], offline_store=LocalStore("{store_path}"))
"""
        )

        # When/Then loading should provide helpful error with traceback
        with pytest.raises(DefinitionsLoadError) as exc_info:
            load_definitions(str(error_file))

        error_str = str(exc_info.value)
        assert "RuntimeError" in error_str
        assert "Something went wrong" in error_str


def test_load_definitions_works_with_pathlib():
    # Given a Path object
    with tempfile.TemporaryDirectory() as tmpdir:
        definitions_file = Path(tmpdir) / "defs.py"
        store_path = Path(tmpdir) / "store"
        definitions_file.write_text(
            f"""
from mlforge import Definitions, LocalStore

defs = Definitions(name="pathlib-test", features=[], offline_store=LocalStore("{store_path}"))
"""
        )

        # When loading with Path object
        result = load_definitions(str(definitions_file))

        # Then it should work correctly
        assert result.name == "pathlib-test"
