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

- `TARGET` (optional): Path to definitions file. Auto-discovers `definitions.py` if not specified.

#### Options

- `--features NAMES`: Comma-separated list of feature names to build. Defaults to all features.
- `--tags TAGS`: Comma-separated list of feature tags to build. Mutually exclusive with `--features`.
- `--force`, `-f`: Overwrite existing features. Defaults to `False`.
- `--no-preview`: Disable feature preview output. Defaults to `False` (preview enabled).
- `--preview-rows N`: Number of preview rows to display. Defaults to `5`.
- `--verbose`, `-v`: Enable debug logging. Defaults to `False`.

#### Examples

Build all features:

```bash
mlforge build definitions.py
```

Build all features (auto-discovers definitions.py):

```bash
mlforge build
```

Build specific features:

```bash
mlforge build definitions.py --features user_age,user_tenure
```

Build features by tag:

```bash
mlforge build --tags user_metrics,demographics
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

### inspect

Display detailed metadata for a specific feature.

```bash
mlforge inspect FEATURE_NAME [TARGET]
```

#### Arguments

- `FEATURE_NAME` (required): Name of the feature to inspect
- `TARGET` (optional): Path to definitions file. Auto-discovers `definitions.py` if not specified.

#### Examples

Inspect a specific feature:

```bash
mlforge inspect user_spend
```

Inspect with custom definitions file:

```bash
mlforge inspect user_spend definitions.py
```

#### Output

Displays detailed feature metadata including:

- Feature configuration (entity, keys, timestamp, interval)
- Storage details (path, source, row count)
- Column information with types and aggregations
- Tags and description
- Last build timestamp

Example output:

```
┌─ Feature: user_spend ──────────────────────────────────────┐
│ Total spend features for users                              │
│                                                              │
│ Path: ./feature_store/user_spend.parquet                   │
│ Source: data/transactions.parquet                           │
│ Entity: user_id                                              │
│ Keys: user_id                                                │
│ Timestamp: transaction_date                                  │
│ Interval: 1d                                                 │
│ Tags: users, spending                                        │
│ Row Count: 50,000                                            │
│ Last Updated: 2024-01-16T08:30:00Z                          │
└──────────────────────────────────────────────────────────────┘

Columns
┌──────────────────────────┬────────┬────────┬─────────────┬────────┐
│ Name                     │ Type   │ Input  │ Aggregation │ Window │
├──────────────────────────┼────────┼────────┼─────────────┼────────┤
│ user_id                  │ Utf8   │ -      │ -           │ -      │
│ transaction_date         │ Date   │ -      │ -           │ -      │
│ amt__sum__7d             │ Float64│ amt    │ sum         │ 7d     │
│ amt__count__7d           │ UInt32 │ amt    │ count       │ 7d     │
│ amt__mean__30d           │ Float64│ amt    │ mean        │ 30d    │
└──────────────────────────┴────────┴────────┴─────────────┴────────┘
```

#### Error Handling

**No metadata found**: If the feature hasn't been built yet:

```bash
$ mlforge inspect user_spend
Error: No metadata found for feature 'user_spend'.
Run 'mlforge build' to generate metadata.
```

### manifest

Display or regenerate the feature store manifest.

```bash
mlforge manifest [TARGET] [OPTIONS]
```

#### Arguments

- `TARGET` (optional): Path to definitions file. Auto-discovers `definitions.py` if not specified.

#### Options

- `--regenerate`: Rebuild manifest.json from individual .meta.json files. Defaults to `False`.

#### Examples

Display manifest summary:

```bash
mlforge manifest
```

Regenerate consolidated manifest file:

```bash
mlforge manifest --regenerate
```

With custom definitions file:

```bash
mlforge manifest definitions.py --regenerate
```

#### Output

**Without `--regenerate`** - Displays a summary table:

```
Feature Store Manifest
┌──────────────────┬──────────┬────────┬─────────┬─────────────────────┐
│ Feature          │ Entity   │ Rows   │ Columns │ Last Updated        │
├──────────────────┼──────────┼────────┼─────────┼─────────────────────┤
│ merchant_spend   │ merchant │ 15,482 │ 8       │ 2024-01-16T08:30:00│
│ user_spend       │ user_id  │ 50,000 │ 12      │ 2024-01-16T08:25:00│
│ account_spend    │ account  │ 8,234  │ 10      │ 2024-01-16T08:28:00│
└──────────────────┴──────────┴────────┴─────────┴─────────────────────┘
```

**With `--regenerate`** - Creates `manifest.json` and displays confirmation:

```bash
$ mlforge manifest --regenerate
Regenerated manifest.json with 3 features
```

The consolidated manifest is written to:

- **LocalStore**: `<store_path>/manifest.json`
- **S3Store**: `s3://<bucket>/<prefix>/manifest.json`

#### Error Handling

**No features found**: If no features have been built:

```bash
$ mlforge manifest
Warning: No feature metadata found. Run 'mlforge build' first.
```

### validate

Run validation on features without building them.

```bash
mlforge validate [TARGET] [OPTIONS]
```

#### Arguments

- `TARGET` (optional): Path to definitions file. Auto-discovers `definitions.py` if not specified.

#### Options

- `--features NAMES`: Comma-separated list of feature names to validate. Defaults to all features.
- `--tags TAGS`: Comma-separated list of feature tags to validate. Mutually exclusive with `--features`.
- `--verbose`, `-v`: Enable debug logging. Defaults to `False`.

#### Examples

Validate all features:

```bash
mlforge validate definitions.py
```

Validate specific features:

```bash
mlforge validate --features merchant_transactions,user_transactions
```

Validate features by tag:

```bash
mlforge validate --tags transactions
```

#### Output

Displays validation results for each feature:

```
Validating merchant_transactions...
✓ All validations passed for merchant_transactions

Validating user_transactions...
✗ Validation failed for user_transactions
  - Column 'amount': 3 values < 0 (greater_than_or_equal(0))

Validated 2 features (1 passed, 1 failed)
```

#### Error Handling

**ValidationError**: If any feature fails validation:

```bash
$ mlforge validate definitions.py
Error: Validation failed for 1 feature(s)
Exit code: 1
```

The command exits with code 1 if any validations fail, making it suitable for CI/CD pipelines.

### sync

Rebuild features from metadata files (for Git-based collaboration).

```bash
mlforge sync [TARGET] [OPTIONS]
```

!!! info "LocalStore Only"
    The sync command only works with `LocalStore`. Cloud stores (S3, etc.) already share data between teammates, so syncing is not needed.

#### Arguments

- `TARGET` (optional): Path to definitions file. Auto-discovers `definitions.py` if not specified.

#### Options

- `--features NAMES`: Comma-separated list of feature names to sync. Defaults to all features with missing data.
- `--dry-run`: Show what would be synced without actually rebuilding. Defaults to `False`.
- `--force`: Rebuild even if source data hash differs. Defaults to `False`.
- `--verbose`, `-v`: Enable debug logging. Defaults to `False`.

#### How It Works

The sync command helps teams collaborate on feature definitions via Git:

1. **Metadata is committed to Git**: `.meta.json` and `_latest.json` files
2. **Data files are ignored**: `data.parquet` files are excluded via auto-generated `.gitignore`
3. **Teammates rebuild locally**: Run `mlforge sync` to recreate data from metadata

For each feature, sync will:

1. Check if metadata exists but data file is missing
2. Compute hash of current source data file
3. Compare with `source_hash` stored in metadata
4. If hashes match → rebuild data from feature function
5. If hashes differ → error (use `--force` to override)

#### Examples

Preview what would be synced:

```bash
mlforge sync --dry-run
```

Sync all features with missing data:

```bash
mlforge sync
```

Sync specific features:

```bash
mlforge sync --features user_spend,merchant_spend
```

Force sync even if source data changed:

```bash
mlforge sync --force
```

With custom definitions file:

```bash
mlforge sync definitions.py --features user_spend
```

#### Output

**Dry-run mode** - Shows what would be synced:

```
[Dry Run] Would sync 2 features:
  - user_spend (v1.2.0)
  - merchant_spend (v2.0.1)

Run without --dry-run to sync
```

**Normal mode** - Rebuilds features and shows progress:

```
Syncing user_spend (v1.2.0)...
✓ Source hash matches (abc123def456)
✓ Rebuilt user_spend

Syncing merchant_spend (v2.0.1)...
✓ Source hash matches (789abc012def)
✓ Rebuilt merchant_spend

Synced 2 features
```

**No features to sync**:

```
No features need syncing
```

#### Error Handling

**Source data changed**: If source hash differs from metadata:

```bash
$ mlforge sync --features user_spend
Error: Source data has changed for feature 'user_spend' (v1.2.0)

Expected hash: abc123def456
Current hash:  xyz789abc012

This means the source data file has been modified since this version
was built. Rebuilding with different source data may produce different
results.

Options:
  - Restore the original source data file
  - Use --force to rebuild anyway (creates new version)
  - Check with your team if source data should have changed
```

**Not a LocalStore**: If using S3Store or other cloud storage:

```bash
$ mlforge sync
Error: Sync only works with LocalStore.
Cloud stores (S3Store) already share data between teammates.
```

**Missing source file**: If the source data file doesn't exist:

```bash
$ mlforge sync --features user_spend
Error: Source file not found: data/transactions.parquet
Cannot verify source hash or rebuild feature.
```

#### Use Cases

**After pulling changes from Git**:

```bash
git pull
mlforge sync
```

**Setting up new development environment**:

```bash
git clone https://github.com/team/ml-features.git
cd ml-features
mlforge sync
```

**Checking if features are out of sync**:

```bash
mlforge sync --dry-run
```

#### When NOT to Use Sync

- **Cloud stores**: Data is already shared via S3/GCS
- **Source data changed intentionally**: Use `mlforge build --force` to create a new version
- **Initial setup**: Use `mlforge build` for first-time feature creation

### list

Display all registered features in a table.

```bash
mlforge list [TARGET] [OPTIONS]
```

#### Arguments

- `TARGET` (optional): Path to definitions file. Auto-discovers `definitions.py` if not specified.

#### Options

- `--tags TAGS`: Comma-separated list of tags to filter features by. Defaults to showing all features.

#### Examples

List all features:

```bash
mlforge list definitions.py
```

List from current directory (auto-discovers definitions.py):

```bash
mlforge list
```

List features by tag:

```bash
mlforge list --tags user_metrics
```

#### Output

Displays a formatted table with feature metadata:

```
┌──────────────────────┬──────────────────┬──────────────────────────┬──────────────┬───────────────────────────┐
│ Name                 │ Keys             │ Source                   │ Tags         │ Description               │
├──────────────────────┼──────────────────┼──────────────────────────┼──────────────┼───────────────────────────┤
│ user_total_spend     │ [user_id]        │ data/transactions.parquet│ user_metrics │ Total spend by user       │
│ user_spend_mean_30d  │ [user_id]        │ data/transactions.parquet│ user_metrics │ 30d rolling avg spend     │
│ merchant_total_spend │ [merchant_id]    │ data/transactions.parquet│ -            │ Total spend by merchant   │
└──────────────────────┴──────────────────┴──────────────────────────┴──────────────┴───────────────────────────┘
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

The `TARGET` parameter specifies a Python file containing a `Definitions` object. If not provided, mlforge will automatically search for `definitions.py` in your project directory.

### Auto-Discovery

When `TARGET` is omitted, mlforge searches for `definitions.py`:

```bash
# Automatically finds definitions.py in current directory or subdirectories
mlforge build
mlforge list
```

The search starts from the project root (identified by `pyproject.toml`, `.git`, etc.) and looks recursively, skipping common directories like `.venv` and `node_modules`.

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
        run: pip install mlforge-sdk
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
