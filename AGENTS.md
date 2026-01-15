# AGENTS.md

Instructions for AI coding agents working on mlforge.

> **Development Status**: v0.Y.Z is pre-release. No backward-compatibility concerns until v1.0.0.

## Project Overview

mlforge is a Python feature store SDK for ML pipelines. Core capabilities:

| Component | Purpose |
|-----------|---------|
| `@feature` decorator | Define features with transformations, validators, metrics |
| `Entity` | Entity definition with optional surrogate key generation |
| `Source` | Data source abstraction (local/S3/GCS, auto-format detection) |
| `Timestamp` | Timestamp handling with auto-format detection |
| `Definitions` | Registry for features, builds, and retrieval |
| `LocalStore` / `S3Store` / `GCSStore` | Versioned offline storage |
| `RedisStore` | Online store for real-time inference |
| `get_training_data` | Point-in-time correct feature retrieval |
| `get_online_features` | Real-time feature serving from Redis |

## Build/Test Commands

All commands require `uv run` prefix:

```bash
# Run all checks (required before commits)
uv run just check

# Individual checks
uv run just check-code       # ruff linting
uv run just check-type       # ty type checking
uv run just check-format     # format check
uv run just check-security   # bandit security scan
uv run just check-test       # pytest (parallel)
uv run just check-coverage   # pytest with 80% minimum coverage

# Format code
uv run just format

# Run specific tests
uv run pytest tests/test_core.py -v
uv run pytest tests/ -k "test_feature"
```

## Key Files

| File | Purpose |
|------|---------|
| `src/mlforge/core.py` | Feature, Definitions, @feature decorator |
| `src/mlforge/entities.py` | Entity with surrogate key generation |
| `src/mlforge/sources/base.py` | Source abstraction (local/s3/gcs) |
| `src/mlforge/timestamps.py` | Timestamp parsing and detection |
| `src/mlforge/store.py` | Store ABC, LocalStore, S3Store, GCSStore |
| `src/mlforge/online.py` | OnlineStore, RedisStore |
| `src/mlforge/retrieval.py` | get_training_data, point-in-time joins |
| `src/mlforge/version.py` | Semantic versioning and change detection |
| `src/mlforge/metrics.py` | Rolling window aggregations |
| `src/mlforge/validators.py` | Data quality validators |
| `src/mlforge/cli.py` | CLI commands |
| `src/mlforge/profiles.py` | YAML-based profile configuration |
| `src/mlforge/engines/` | Polars and DuckDB engine implementations |
| `src/mlforge/errors.py` | Custom exception classes |

## CLI Commands

```bash
# Project setup
uv run mlforge init <name> [--online redis] [--store s3] [--profile]

# Build features
uv run mlforge build [--features NAME] [--tags TAG] [--online] [--profile NAME]

# Discovery
uv run mlforge list features|entities|sources|versions
uv run mlforge inspect feature|entity|source <name>

# Version management
uv run mlforge diff <feature> [v1] [v2]      # Compare versions
uv run mlforge rollback <feature> [version]  # Rollback to version

# Validation and sync
uv run mlforge validate [--features NAME]
uv run mlforge sync [--dry-run]
```

## Code Style

### Python Version and Types
- Python >= 3.13 required
- Full type annotations on all functions
- Use `str | None` not `Optional[str]`
- Use `list[str]` not `List[str]`

### Import Conventions

```python
# CORRECT: Import mlforge modules as namespaces
import mlforge.core as core
import mlforge.errors as errors

# WRONG: Don't import individual classes from mlforge
from mlforge.core import Feature  # Don't do this

# OK: Standard library direct imports
from pathlib import Path
```

### Naming

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `LocalStore`, `FeatureMetadata` |
| Functions | snake_case | `get_training_data` |
| Constants | UPPER_SNAKE | `DEFAULT_TTL` |
| Private | _underscore | `_compute_hash` |

### Error Handling

```python
raise errors.FeatureMaterializationError(
    feature_name=feature.name,
    message="Feature function returned None",
    hint="Make sure your feature function returns a DataFrame.",
)
```

### Docstrings (Google-style)

```python
def function_name(param1: str, param2: int | None = None) -> bool:
    """Short summary in imperative mood.

    Args:
        param1: Description
        param2: Description. Defaults to None.

    Returns:
        Description of return value

    Raises:
        ValueError: When param1 is empty
    """
```

## Testing

- Test files mirror source: `src/mlforge/core.py` → `tests/test_core.py`
- Fixtures in `tests/conftest.py`: `temp_dir`, `temp_store`, `sample_dataframe`, `sample_parquet_file`
- Coverage minimum: 80%
- Engine parity tests validate Polars vs DuckDB produce identical output

## Example Projects

Located in `examples/`:
- `transactions/` - Basic feature store with LocalStore
- `transactions-online/` - With Redis online store
- `fraud-detection/` - Multiple entities use case
- `recommendation/` - Rolling metrics

## Dependencies

**Core**: polars, pyarrow, pydantic, cyclopts, loguru, omegaconf, s3fs

**Optional**: duckdb, redis, gcsfs

**Dev**: pytest, ruff, ty, bandit, mkdocs

## Commit Messages

Use conventional commits with emoji:
- `✨ feat:` new feature
- `🐛 fix:` bug fix
- `📝 docs:` documentation
- `♻️ refactor:` restructuring
- `✅ test:` tests
- `🔧 chore:` maintenance

## Design Principles

1. Simple interfaces, hidden complexity
2. Comments explain *why*, not *what*
3. General enough without over-engineering
4. No shallow modules (interface as complex as implementation)
5. No pass-through methods that just forward calls

## CI/CD Integration

- **Version bumping**: Handled by `.github/workflows/bump.yaml` on push to main
- **Commitizen config**: `update_changelog_on_bump = false` (changelog is manual)
- **Version detection**: Automatic from conventional commits (feat=MINOR, fix=PATCH)
- **Tagging**: Automatic after version bump on main

## Branch Strategy

```
main (protected)
  └── release/X.Y.Z
        ├── feature/name
        ├── refactor/name
        └── fix/name
```

- **PRs**: Only from `release/*` branches to `main`
- **Features**: Merge to release branch, not directly to main
- **Parallel dev**: Use git worktrees (`../mlforge-{feature}/`)
