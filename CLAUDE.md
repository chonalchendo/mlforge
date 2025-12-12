# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

mlforge is a Python feature store SDK focused on simplicity. It provides:
- `@feature` decorator for defining features
- `entity_key` utility for surrogate key generation
- `Definitions` class for registering features
- `LocalStore` for persisting features to Parquet
- `get_training_data` for point-in-time correct feature retrieval
- CLI for building and listing features

## Quick Reference
```bash
# Build features
uv run mlforge build definitions.py

# List features
uv run mlforge list definitions.py

# Run all checks
just check
```

## Key Files

- `src/mlforge/core.py` — Feature, Definitions, feature decorator
- `src/mlforge/store.py` — Store ABC, LocalStore
- `src/mlforge/retrieval.py` — get_training_data, point-in-time joins
- `src/mlforge/utils.py` — entity_key, surrogate_key
- `src/mlforge/cli.py` — CLI commands

## References

Automatically use context7 for code generation and library documentation.

## Documentation

### Style Guide
- Use Google-style docstrings (see context7 for full reference)
- When reviewing code, always review the documentation to make sure it reflects what the code is doing

### Docstring Format

**Functions:**
```python
def function_name(param1: str, param2: int | None = None) -> bool:
    """
    Short one-line summary of function purpose.
    
    Longer description if needed, explaining behavior,
    edge cases, or important details.
    
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

**Classes:**
```python
class ClassName:
    """
    Short one-line summary of class purpose.
    
    Longer description if needed.
    
    Attributes:
        attr1: Description of attr1
        attr2: Description of attr2
    
    Example:
        obj = ClassName(attr1="value")
        obj.method()
    """
```

### Rules
- Always include Args, Returns, Raises sections when applicable
- Keep the one-line summary under 80 characters
- Use imperative mood: "Return the result" not "Returns the result"
- Document exceptions that callers should handle
- Include Example section for non-obvious usage
- Type hints in signature, not in docstring
- Don't document private methods unless complex
- Update docstrings when changing function behavior

## Development Tools

### Commands
All commands run via `just`:

| Command | Description |
|---------|-------------|
| `just check` | Run all checks (code, type, format, security, coverage) |
| `just check-code` | Lint with ruff |
| `just check-type` | Type check with ty |
| `just check-format` | Check formatting with ruff |
| `just check-security` | Security scan with bandit |
| `just check-coverage` | Run tests with coverage (80% minimum) |
| `just check-test` | Run tests without coverage |

### Tools
- **ruff** — linting and formatting
- **ty** — type checking
- **pytest** — testing
- **bandit** — security scanning
- **pre-commit** — git hooks
- **commitizen** — conventional commits, changelog, version bumping

### Dependency Management

This project uses `uv` for dependency management with dependency groups.

**Dependency Groups:**
- **Production** (no group) — Runtime dependencies (polars, cyclopts, loguru, etc.)
- **dev** — Development tools (rust-just)
- **commit** — Commit management (commitizen, prek)
- **check** — Quality & testing (ruff, ty, bandit, pytest, pytest-cov, pytest-mock, pytest-xdist)

**Adding Dependencies:**
```bash
# Add a production dependency
uv add package-name

# Add to a specific group
uv add package-name --group dev
uv add package-name --group commit
uv add package-name --group check

# Sync environment after adding dependencies
uv sync
```

**Important:**
- Always run `uv sync` after adding dependencies to ensure they're installed
- Default groups (dev, commit, check) are installed automatically with `uv sync`

### Before Committing
Always run `just check` before committing. All checks must pass.

### Commit Messages
Use conventional commits (commitizen):
- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation only
- `refactor:` — code change that neither fixes a bug nor adds a feature
- `test:` — adding or updating tests
- `chore:` — maintenance tasks

