# CLI Reference

mlforge provides a command-line interface for building and listing features.

## Installation Verification

Check that the CLI is installed:

```bash
mlforge --help
```

## Commands

### build

Materialize features to offline storage.

```bash
mlforge build [TARGET] [OPTIONS]
```

#### Arguments

- `TARGET` (optional): Path to definitions file. Defaults to `definitions.py`.

#### Options

- `--features NAMES`: Comma-separated list of feature names to build. Defaults to all features.
- `--force`, `-f`: Overwrite existing features. Defaults to `False`.
- `--no-preview`: Disable feature preview output. Defaults to `False` (preview enabled).
- `--preview-rows N`: Number of preview rows to display. Defaults to `5`.
- `--verbose`, `-v`: Enable debug logging. Defaults to `False`.

#### Examples

Build all features:

```bash
mlforge build definitions.py
```

Build specific features:

```bash
mlforge build definitions.py --features user_age,user_tenure
```

Force rebuild all features:

```bash
mlforge build definitions.py --force
```

Build with verbose logging:

```bash
mlforge build definitions.py --verbose
```

Build without preview:

```bash
mlforge build definitions.py --no-preview
```

Custom preview size:

```bash
mlforge build definitions.py --preview-rows 10
```

#### Output

The command displays:

1. Progress messages for each feature
2. Preview of materialized data (unless `--no-preview`)
3. Summary of built features
4. Storage paths for each feature

Example output:

```
Materializing user_total_spend
┌─────────┬─────────────┐
│ user_id │ total_spend │
├─────────┼─────────────┤
│ u1      │ 150.0       │
│ u2      │ 250.0       │
│ u3      │ 100.0       │
└─────────┴─────────────┘

Materializing user_avg_spend
┌─────────┬───────────┐
│ user_id │ avg_spend │
├─────────┼───────────┤
│ u1      │ 50.0      │
│ u2      │ 83.3      │
│ u3      │ 100.0     │
└─────────┴───────────┘

Built features:
  user_total_spend -> feature_store/user_total_spend.parquet
  user_avg_spend -> feature_store/user_avg_spend.parquet

Built 2 features
```

#### Error Handling

**DefinitionsLoadError**: If the definitions file cannot be loaded:

```bash
$ mlforge build missing.py
Error: Could not load definitions from missing.py
```

**FeatureMaterializationError**: If a feature function fails:

```bash
$ mlforge build definitions.py
Error: Feature 'user_age' failed: Feature function returned None
Hint: Make sure your feature function returns a DataFrame.
```

### list

Display all registered features in a table.

```bash
mlforge list [TARGET]
```

#### Arguments

- `TARGET` (optional): Path to definitions file. Defaults to `definitions.py`.

#### Examples

List all features:

```bash
mlforge list definitions.py
```

List from current directory:

```bash
mlforge list
```

#### Output

Displays a formatted table with feature metadata:

```
┌──────────────────────┬──────────────────┬──────────────────────────┬───────────────────────────┐
│ Name                 │ Keys             │ Source                   │ Description               │
├──────────────────────┼──────────────────┼──────────────────────────┼───────────────────────────┤
│ user_total_spend     │ [user_id]        │ data/transactions.parquet│ Total spend by user       │
│ user_spend_mean_30d  │ [user_id]        │ data/transactions.parquet│ 30d rolling avg spend     │
│ merchant_total_spend │ [merchant_id]    │ data/transactions.parquet│ Total spend by merchant   │
└──────────────────────┴──────────────────┴──────────────────────────┴───────────────────────────┘
```

## Global Options

These options work with any command:

### --verbose, -v

Enable debug logging:

```bash
mlforge build definitions.py --verbose
mlforge list definitions.py --verbose
```

Debug output includes:

- Module loading details
- Feature registration logs
- Source data loading information
- Storage operations

Example verbose output:

```
DEBUG: Loading definitions from definitions.py
DEBUG: Registered feature: user_total_spend
DEBUG: Registered feature: user_avg_spend
INFO: Materializing user_total_spend
DEBUG: Loading source: data/transactions.parquet
DEBUG: Writing to: feature_store/user_total_spend.parquet
```

## Definitions File

The `TARGET` parameter specifies a Python file containing a `Definitions` object named `defs`.

### Structure

```python
# definitions.py
from mlforge import Definitions, LocalStore
import features

defs = Definitions(
    name="my-project",
    features=[features],
    offline_store=LocalStore("./feature_store")
)
```

### Naming Convention

The `Definitions` object must be named `defs`:

```python
# Good
defs = Definitions(...)

# Bad - won't be found
definitions = Definitions(...)
feature_store = Definitions(...)
```

### Module vs. File Path

You can use either a file path or a module path:

```bash
# File path (recommended)
mlforge build definitions.py
mlforge build path/to/definitions.py

# Module path (if installed)
mlforge build mypackage.definitions
```

## Exit Codes

The CLI uses these exit codes:

- `0`: Success
- `1`: Error (load failure, materialization failure, etc.)

Use in scripts:

```bash
mlforge build definitions.py
if [ $? -eq 0 ]; then
    echo "Build succeeded"
else
    echo "Build failed"
    exit 1
fi
```

## Environment Variables

Currently, mlforge does not use environment variables for configuration. All settings are specified via:

1. Command-line options
2. Definitions file configuration

## Shell Completion

mlforge uses `cyclopts` for CLI parsing. Shell completion may be supported in future versions.

## Integration Examples

### Makefile

```makefile
.PHONY: features
features:
	mlforge build definitions.py --force

.PHONY: list-features
list-features:
	mlforge list definitions.py

.PHONY: build-prod
build-prod:
	mlforge build definitions.py --no-preview
```

### CI/CD Pipeline

```yaml
# .github/workflows/build-features.yml
name: Build Features

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: "3.13"
      - name: Install dependencies
        run: pip install mlforge
      - name: Build features
        run: mlforge build definitions.py --no-preview
```

### Pre-commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash
mlforge build definitions.py --no-preview
if [ $? -ne 0 ]; then
    echo "Feature build failed. Fix errors before committing."
    exit 1
fi
```

## Next Steps

- [Building Features](user-guide/building-features.md) - Detailed build guide
- [Defining Features](user-guide/defining-features.md) - Feature definition reference
- [API Reference](api/core.md) - Python API documentation
