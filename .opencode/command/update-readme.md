# Update README

Update the project README.md to accurately reflect the current state of the codebase.

## Workflow

### Step 1: Discover Current State

1. Read `pyproject.toml` for:
   - Package name and description
   - Version
   - Dependencies
   - CLI entry points
   - Python version requirements

2. Explore `src/` to identify:
   - Public API (decorators, classes, functions)
   - Module structure
   - What's exported in `__init__.py`

3. Read source code for:
   - Function signatures and parameters
   - Actual usage patterns
   - Type hints

4. Check existing `README.md` for:
   - What's outdated
   - What's missing
   - What's accurate

### Step 2: Update README Sections

**Required sections:**

1. **Title + badges** — Package name, PyPI version, Python versions, license
2. **One-liner** — What this package does in one sentence
3. **Installation** — pip/uv commands with correct package name
4. **Quick example** — Minimal working code showing core workflow
5. **Features** — Brief list of key capabilities
6. **Documentation link** — Link to full docs site

**Optional sections (if relevant):**

- CLI usage
- Configuration
- Contributing
- License

### Step 3: Write Content

**Badges:**

```markdown
[![PyPI version](https://badge.fury.io/py/PACKAGE_NAME.svg)](https://pypi.org/project/PACKAGE_NAME/)
[![Python versions](https://img.shields.io/pypi/pyversions/PACKAGE_NAME.svg)](https://pypi.org/project/PACKAGE_NAME/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
```

**Installation:**

```markdown
## Installation

```bash
pip install PACKAGE_NAME
```
```

**Quick example:**

- Use real function names from source
- Keep it minimal — show core workflow only
- Must be copy-pasteable and working

### Step 4: Verify

- All code examples use actual API
- Links are correct
- No references to non-existent features
- Badge URLs use correct package name

## Guidelines

- **Concise** — README is an entry point, not full docs
- **Accurate** — Only document what exists
- **Working examples** — All code must run
- **No aspirational features** — Only current functionality
