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

## Coding Standards

### Standards 

- Python ≥ 3.13 with full type annotations
- Follow existing patterns and maintain consistency
- Prioritize readable, understandable code - clarity over cleverness
- Avoid obfuscated or confusing patterns even if they're shorter
- Each feature needs corresponding tests
- imports for mlforge should be imported as modules. For example: "import mlforge.core as core"
- DO NOT import individual classes and functions unless it's for Python standard libraries.
- ALWAYS place imports at the top of a file, never include inside a function or class.

### Design Principles

Think about each of these principles when writing new code and reviewing old pieces of code.

| # | Principle | Question |
|---|-----------|----------|
| 1 | Complexity is incremental | Is this change adding subtle complexity? |
| 2 | Working code isn't enough | Is this clear and maintainable, or just "working"? |
| 3 | Continual investment | Did we leave this cleaner than we found it? |
| 4 | Deep modules | Is the interface small relative to functionality? |
| 5 | Simple common usage | Is the common case trivial to write? |
| 6 | Simple interface over impl | Is complexity hidden inside, not pushed to callers? |
| 7 | General-purpose depth | Is this general enough without over-engineering? |
| 8 | Separate concerns | Are special cases leaking into general code? |
| 9 | Layer abstraction | Does each layer provide a meaningful transformation? |
| 10 | Pull complexity down | Are callers doing work the module should handle? |
| 11 | Define errors out | Can we change the design so this error can't happen? |
| 12 | Design it twice | Did we consider alternatives? |
| 13 | Non-obvious comments | Do comments explain *why*, not *what*? |
| 14 | Design for reading | Would a new reader understand this quickly? |
| 15 | Abstractions over features | Are we building composable blocks or tangled features? |

### Code Red Flags

Think about each of these red flags when writing new code and reviewing old pieces of code.

| # | Red Flag | Question |
|---|----------|----------|
| 1 | Shallow Module | Is the interface as complex as the implementation? |
| 2 | Information Leakage | Does this decision appear in multiple places? |
| 3 | Temporal Decomposition | Is this organized by *when* instead of *what info*? |
| 4 | Overexposure | Must common cases know about rare features? |
| 5 | Pass-Through Method | Does this just forward to another method? |
| 6 | Repetition | Have I seen this pattern elsewhere? |
| 7 | Special-General Mixture | Is special-case logic polluting general code? |
| 8 | Conjoined Methods | Can I understand this without reading another method? |
| 9 | Comment Repeats Code | Does this comment add any information? |
| 10 | Implementation in Interface Docs | Do these docs expose internals? |
| 11 | Vague Name | Would a new reader know what this is? |
| 12 | Hard to Pick Name | Why is naming this so difficult? |
| 13 | Hard to Describe | Why does explaining this require so much text? |
| 14 | Non-Obvious Code | Can I understand this without tracing execution? |

---

### Red Flag → Root Cause Mapping

Think about these red flag causes when writing new code and reviewing current code.

| Red Flag | Often Indicates |
|----------|-----------------|
| Shallow Module | Module boundary in wrong place |
| Information Leakage | Missing abstraction to centralize decision |
| Temporal Decomposition | Organized by workflow instead of information |
| Overexposure | Interface not designed for common case |
| Pass-Through | Unnecessary layer; should merge or differentiate |
| Repetition | Missing helper/abstraction |
| Special-General Mixture | Concerns not separated |
| Conjoined Methods | Should be merged or restructured |
| Comment Repeats Code | Bad naming or unnecessary comment |
| Implementation Docs | Leaky abstraction |
| Vague Name | Unclear purpose; may need redesign |
| Hard to Pick Name | Muddled responsibilities |
| Hard to Describe | Doing too much; needs decomposition |
| Non-Obvious Code | Needs refactoring or better naming |


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
- **prek** — git hooks
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

