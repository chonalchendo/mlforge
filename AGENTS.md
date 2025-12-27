# AGENTS.md

Instructions for AI coding agents working on the mlforge codebase.

## Project Overview

mlforge is a Python feature store SDK. Key components:
- `@feature` decorator for defining features
- `Definitions` class for registering and building features
- `LocalStore` for Parquet persistence
- `get_training_data` for point-in-time correct retrieval

## Build/Lint/Test Commands

All commands use `just` (rust-just) with `uv` for package management.

### Running Tests

```bash
# Run all tests (parallel)
just check-test

# Run tests with coverage (80% minimum required)
just check-coverage

# Run a single test file
uv run pytest tests/test_core.py

# Run a single test function
uv run pytest tests/test_core.py::test_feature_decorator

# Run tests matching a pattern
uv run pytest tests/ -k "test_feature"

# Run with verbose output
uv run pytest tests/test_core.py -v
```

### Linting and Type Checking

```bash
# Run ALL checks (required before commits)
just check

# Individual checks
just check-code      # ruff linting
just check-type      # ty type checking
just check-format    # ruff format check
just check-security  # bandit security scan
```

### Formatting

```bash
# Auto-format code
uv run ruff format src tests

# Fix linting issues
uv run ruff check --fix src tests
```

## Code Style Guidelines

### Python Version and Types

- Python >= 3.13 required
- Full type annotations on all functions and methods
- Use `|` for union types: `str | None` not `Optional[str]`
- Use modern generic syntax: `list[str]` not `List[str]`

### Import Conventions

```python
# CORRECT: Import mlforge modules as namespaces
import mlforge.core as core
import mlforge.errors as errors
import mlforge.store as store

# WRONG: Don't import individual classes/functions from mlforge
from mlforge.core import Feature  # Don't do this

# OK: Standard library can use direct imports
from pathlib import Path
from typing import Any, Callable
```

- All imports at file top, never inside functions
- Group imports: stdlib, third-party, local (mlforge)

### Naming Conventions

- Classes: `PascalCase` (e.g., `LocalStore`, `FeatureMetadata`)
- Functions/methods: `snake_case` (e.g., `get_training_data`)
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_single_leading_underscore`
- Type aliases: `PascalCase` (e.g., `WindowFunc`, `EngineKind`)

### Error Handling

Define custom exceptions in `errors.py` with:
- Descriptive message
- Optional `cause` for chained exceptions
- Optional `hint` for user guidance

```python
# Example error pattern
raise errors.FeatureMaterializationError(
    feature_name=feature.name,
    message="Feature function returned None",
    hint="Make sure your feature function returns a DataFrame.",
)
```

### Documentation

Use Google-style docstrings:

```python
def function_name(param1: str, param2: int | None = None) -> bool:
    """
    Short one-line summary (imperative mood).

    Longer description if needed.

    Args:
        param1: Description of param1
        param2: Description of param2. Defaults to None.

    Returns:
        Description of return value

    Raises:
        ValueError: When param1 is empty

    Example:
        result = function_name("test", 42)
    """
```

### Code Organization

- Keep interfaces simple, hide complexity in implementation
- Each feature needs corresponding tests in `tests/`
- Shared fixtures go in `tests/conftest.py`
- Prefer composition over inheritance

## Key Files

| File | Purpose |
|------|---------|
| `src/mlforge/core.py` | Feature, Definitions, @feature decorator |
| `src/mlforge/store.py` | Store ABC, LocalStore |
| `src/mlforge/retrieval.py` | get_training_data, point-in-time joins |
| `src/mlforge/utils.py` | entity_key, surrogate_key |
| `src/mlforge/errors.py` | Custom exception classes |
| `src/mlforge/cli.py` | CLI commands |
| `src/mlforge/validators.py` | Data validation functions |

## Dependency Management

```bash
# Add production dependency
uv add package-name

# Add to dev group
uv add package-name --group check

# Sync environment
uv sync
```

## Commit Messages

Use conventional commits:
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation only
- `refactor:` code restructuring
- `test:` adding/updating tests
- `chore:` maintenance

## Design Principles

When writing or reviewing code, consider:

1. Is the interface simple relative to functionality?
2. Is complexity hidden inside, not pushed to callers?
3. Would a new reader understand this quickly?
4. Are comments explaining *why*, not *what*?
5. Is this general enough without over-engineering?

## Red Flags to Avoid

- Shallow modules (interface as complex as implementation)
- Information leakage (same decision in multiple places)
- Pass-through methods that just forward calls
- Special-case logic mixed with general code
- Vague or hard-to-pick names (indicates muddled responsibilities)
