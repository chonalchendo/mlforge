from pathlib import Path


def find_project_root(start_path: Path | None = None) -> Path:
    """Find project root by looking for common project markers."""
    if start_path is None:
        start_path = Path.cwd()

    markers = ["pyproject.toml", "setup.py", "setup.cfg", ".git"]

    current = start_path.resolve()
    for parent in [current, *current.parents]:
        if any((parent / marker).exists() for marker in markers):
            return parent

    return start_path.resolve()


def find_definitions_file(
    filename: str = "definitions.py", root: Path | None = None
) -> Path | None:
    """Recursively search for definitions file starting from project root."""
    if root is None:
        root = find_project_root()

    skip_dirs = {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".tox",
        "dist",
        "build",
    }

    for path in root.rglob(filename):
        if not any(part in skip_dirs for part in path.parts):
            return path.resolve()

    return None
