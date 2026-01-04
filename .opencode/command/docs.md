---
description: Generate or update documentation
---

/docs $ARGUMENTS

Generate or update project documentation.

## Usage

```
/docs                    # Auto-detect what needs updating
/docs generate           # Generate full MkDocs documentation
/docs update             # Update docs for recent code changes
/docs readme             # Update README.md
/docs docstrings         # Update Python docstrings
/docs api <module>       # Generate API docs for specific module
```

---

## Mode: auto (default)

When no argument provided, auto-detect what needs updating:

1. Check `git diff` for changed files
2. If `src/` changed -> update docstrings + API docs
3. If major feature added -> suggest full docs update
4. If only minor changes -> update affected docs only

---

## Mode: generate

Generate comprehensive MkDocs documentation from scratch.

### Workflow

1. **Discover codebase**:
   - Read `pyproject.toml` for package info
   - Explore `src/` for modules and public API
   - Check existing `docs/` and `mkdocs.yml`

2. **Plan documentation structure**:
   - Identify key concepts
   - Map user journeys
   - List public APIs for reference docs

3. **Setup MkDocs** (if needed):
   - Create/update `mkdocs.yml`
   - Configure Material theme
   - Setup mkdocstrings plugin

4. **Generate documentation**:
   - `docs/index.md` - Overview
   - `docs/getting-started/` - Installation, quickstart
   - `docs/user-guide/` - Concept guides
   - `docs/api/` - API reference
   - `docs/cli.md` - CLI reference

5. **Verify**: `uv run mkdocs build --strict`

### MkDocs Configuration

```yaml
theme:
  name: material
  features:
    - navigation.tabs
    - navigation.sections
    - content.code.copy
  palette:
    - scheme: default
      toggle:
        icon: material/brightness-7
    - scheme: slate
      toggle:
        icon: material/brightness-4

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            show_source: true
            heading_level: 2

markdown_extensions:
  - pymdownx.highlight
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true
  - admonition
  - pymdownx.details
```

---

## Mode: update

Update existing documentation to reflect code changes.

### Workflow

1. **Identify changes**:
   ```bash
   git diff --name-only $(git merge-base HEAD main) -- src/
   ```

2. **Map changes to docs**:
   | Code Change | Docs Affected |
   |-------------|---------------|
   | New function | API docs, possibly user guide |
   | Changed signature | All examples using it |
   | New CLI command | `docs/cli.md` |
   | Renamed module | Navigation, imports in examples |

3. **Update affected files**:
   - Update code examples
   - Add migration notes for breaking changes
   - Update API reference

4. **Verify**:
   ```bash
   uv run mkdocs build --strict
   grep -r "old_name" docs/  # Check for stale references
   ```

---

## Mode: readme

Update README.md to reflect current codebase.

### Workflow

1. **Discover current state**:
   - Read `pyproject.toml` for version, deps
   - Explore `src/` for public API
   - Check what's exported in `__init__.py`

2. **Update sections**:
   - Badges (version, Python, license)
   - One-liner description
   - Installation instructions
   - Quick example (must be working code)
   - Features list
   - Documentation link

3. **Verify**:
   - All code examples use actual API
   - Links are correct
   - No aspirational features

### README Structure

```markdown
# Package Name

[![PyPI](https://badge.fury.io/py/PACKAGE.svg)](https://pypi.org/project/PACKAGE/)
[![Python](https://img.shields.io/pypi/pyversions/PACKAGE.svg)](https://pypi.org/project/PACKAGE/)

One-line description.

## Installation

pip install package-name

## Quick Start

[Minimal working example]

## Features

- Feature 1
- Feature 2

## Documentation

[Link to full docs]
```

---

## Mode: docstrings

Update Python docstrings for changed code.

### Workflow

1. **Identify changed files**:
   ```bash
   git diff --name-only HEAD~1 -- 'src/mlforge/*.py'
   ```

2. **For each changed file**:
   - Review diff to see what changed
   - Update/add docstrings for modified functions
   - Follow Google-style format

3. **Verify**: `just check`

### Docstring Format (Google-style)

```python
def function(param1: str, param2: int = 0) -> bool:
    """Short summary (one line, <80 chars).

    Longer description if needed.

    Args:
        param1: Description of param1
        param2: Description with default note

    Returns:
        Description of return value

    Raises:
        ValueError: When param1 is empty

    Example:
        >>> function("test", 42)
        True
    """
```

### Quality Principles

**Explain WHY, not WHAT**:
```python
# Bad - narrates the obvious
def process(user):
    """Process the user."""

# Good - explains the non-obvious
def process(user):
    """Process user for notification queue.

    Skips recently active users (<5 min) due to eventual consistency
    with the activity pipeline.
    """
```

**Keep it simple** - If hard to describe, code may need refactoring.

**Never repeat the code**:
```python
# Bad
def increment_count(count):
    """Increment the count by one and return it."""
    return count + 1

# Good - adds non-obvious info
def increment_count(count):
    """Increment count, capping at MAX_INT to prevent overflow."""
    return min(count + 1, MAX_INT)
```

**Interface docs describe behavior, not implementation**:
```python
# Bad - exposes internals
def get(self, key: str) -> Any:
    """Uses LRU with doubly-linked list for O(1) access."""

# Good - describes what callers care about
def get(self, key: str) -> Any:
    """Retrieve value from cache.

    Returns None if key not present or evicted.
    Accessing a key refreshes its LRU position.
    """
```

---

## Mode: api

Generate API documentation for a specific module.

### Usage

```
/docs api core        # docs/api/core.md
/docs api store       # docs/api/store.md
/docs api retrieval   # docs/api/retrieval.md
```

### Workflow

1. Read `src/mlforge/<module>.py`
2. Generate/update `docs/api/<module>.md`
3. Use mkdocstrings directive:
   ```markdown
   # Module Name

   ::: mlforge.module_name
   ```
4. Update `mkdocs.yml` navigation if new page

---

## Guidelines

- **Accuracy over completeness** - Only document what exists
- **Working examples** - All code must be copy-pasteable
- **Concise** - README and quickstart should be brief
- **Cross-link** - Connect related concepts

### Admonitions

```markdown
!!! tip "Title"
    Helpful tip content

!!! warning
    Warning content

!!! note
    Note content

!!! danger "Breaking Change"
    Important breaking change info
```

### Code Tabs

```markdown
=== "pip"
    ```bash
    pip install mlforge
    ```

=== "uv"
    ```bash
    uv add mlforge
    ```
```

### Collapsible Sections

```markdown
??? info "Advanced configuration"
    You can customise the storage backend by...
```
