# Generate MkDocs Documentation

Generate comprehensive documentation for this Python package using MkDocs with the Material theme.

## Workflow

### Step 1: Discover the Codebase

Before writing any documentation, explore the repository:

1. Read `pyproject.toml` to understand:
   - Package name and description
   - Version
   - Dependencies
   - Entry points / CLI commands

2. Explore `src/` directory structure:
   - List all modules and submodules
   - Identify public API (classes, functions, decorators)
   - Note what's exported in `__init__.py` files

3. Read the source code to understand:
   - Core abstractions and their relationships
   - Function signatures and type hints
   - Existing docstrings
   - Usage patterns

4. Check for existing docs:
   - README.md content
   - Existing `docs/` folder
   - Existing `mkdocs.yml`

### Step 2: Plan Documentation Structure

Based on your findings, create a documentation plan:

1. **Identify key concepts** that need explaining
2. **Map user journeys** (install → define → build → retrieve)
3. **List all public APIs** that need reference docs
4. **Note CLI commands** that need documenting

### Step 3: Setup MkDocs

Create or update `mkdocs.yml` with:

- Site name and description from pyproject.toml
- Material theme with light/dark mode
- mkdocstrings plugin for API reference
- Navigation structure based on your plan

**Theme configuration:**

```yaml
theme:
  name: material
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - content.code.copy
    - content.code.annotate
  palette:
    - scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
```

**Required plugins:**

```yaml
plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            show_source: true
            show_root_heading: true
            heading_level: 2
```

**Markdown extensions for rich content:**

```yaml
markdown_extensions:
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true
  - admonition
  - pymdownx.details
  - attr_list
  - md_in_html
```

### Step 4: Add Dependencies

Add to `pyproject.toml` dev dependencies if not present:

```toml
[dependency-groups]
docs = [
    "mkdocs>=1.6",
    "mkdocs-material>=9.5",
    "mkdocstrings[python]>=0.24",
]
```

### Step 5: Generate Documentation

Create documentation files based on what you discovered:

**Required pages:**

- `docs/index.md` - Overview with quick example from actual code
- `docs/getting-started/installation.md` - Based on actual dependencies
- `docs/getting-started/quickstart.md` - Working tutorial using real API
- `docs/cli.md` - Document actual CLI commands found in pyproject.toml

**User guide pages:**

- One page per major concept/workflow you identified
- Use real function names and signatures from source
- Include working code examples

**API reference pages:**

- One page per module with public API
- Use mkdocstrings to auto-generate from docstrings:

```markdown
::: package_name.module_name
```

### Step 6: Verify

1. Run `uv run mkdocs build --strict` to check for errors
2. Run `uv run mkdocs serve` to preview

## Guidelines

- **Accuracy over completeness** - Only document what actually exists
- **Working examples** - All code snippets should be copy-pasteable
- **Concise** - Keep quickstart under 5 minutes
- **Cross-link** - Connect related concepts

### Styling

Use admonitions for tips, warnings, and notes:

```markdown
!!! tip "Point-in-time correctness"
    mlforge automatically handles point-in-time joins to prevent data leakage
    in your training sets.

!!! warning
    Ensure your entity DataFrame has a timestamp column.

!!! note
    This feature requires v0.2.0 or later.
```

Use tabs for showing alternatives:

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

Use collapsible sections for optional details:

```markdown
??? info "Advanced configuration"
    You can customise the storage backend by...
```

Code blocks should always have:
- Language identifier for syntax highlighting
- Copy button enabled (via theme config)

```markdown
```python
from mlforge import feature
```
```

## Output

- `mkdocs.yml` - Configuration based on actual project structure
- `docs/` - Complete documentation tree
- Updated `pyproject.toml` with doc dependencies if needed