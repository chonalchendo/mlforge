import importlib.util
import sys
from pathlib import Path

from loguru import logger

from mlforge.core import Definitions
from mlforge.errors import DefinitionsLoadError


def load_definitions(target: str | None = None) -> Definitions:
    """
    Load Definitions from a Python file.

    Dynamically imports a Python file and extracts the Definitions instance.
    Validates that exactly one Definitions object exists in the file.

    Args:
        target: Path to Python file containing Definitions. Defaults to "definitions.py".

    Returns:
        The Definitions instance found in the file

    Raises:
        FileNotFoundError: If the target file doesn't exist
        ValueError: If the target is not a .py file
        DefinitionsLoadError: If file fails to load, contains no Definitions, or contains multiple

    Example:
        defs = load_definitions("my_features/definitions.py")
        defs.materialize()
    """
    if target is None:
        target = "definitions.py"

    path = Path(target)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not path.suffix == ".py":
        raise ValueError(f"Expected a Python file, got: {path}")

    logger.debug(f"Loading definitions from {path}")

    # Add parent directory to path so imports within the file work
    parent = str(path.parent.resolve())
    if parent not in sys.path:
        sys.path.insert(0, parent)

    # Load module from file path
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise DefinitionsLoadError(f"Failed to create module spec for {path}")

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise DefinitionsLoadError(
            f"Failed to load {path}",
            cause=e,
        ) from e

    # Find all Definitions instances in module
    definitions = [obj for obj in vars(module).values() if isinstance(obj, Definitions)]

    if not definitions:
        raise DefinitionsLoadError(
            f"No Definitions instance found in {path}",
            hint="Make sure you have something like:\n\n"
            "  defs = Definitions(name='my-project', features=[...])",
        )

    if len(definitions) > 1:
        raise DefinitionsLoadError(
            f"Multiple Definitions found in {path}",
            hint="Expected exactly one Definitions instance per file.",
        )

    defs = definitions[0]
    logger.debug(f"Loaded '{defs.name}' with {len(defs.features)} features")

    return defs
