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
- `--version VERSION`: Explicit version override (e.g., '2.0.0'). If not specified, auto-detects based on schema changes.
- `--force`, `-f`: Overwrite existing features. Defaults to `False`.
- `--online`: Build to online store (e.g., Redis) instead of offline store. Defaults to `False`.
- `--preview`: Show feature data preview after building. Defaults to `False`.
- `--preview-rows N`: Number of preview rows to display (when using `--preview`). Defaults to `5`.
- `--profile NAME`: Profile name from mlforge.yaml to use for stores.
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

Build with data preview:

```bash
mlforge build definitions.py --preview
```

Custom preview size (requires --preview):

```bash
mlforge build definitions.py --preview-rows 10
```

Build to online store (Redis):

```bash
mlforge build --online
```

This extracts the latest value per entity and writes to the configured online store.

Build with explicit version:

```bash
mlforge build --version 2.0.0
```

Build with a specific profile from mlforge.yaml:

```bash
mlforge build --profile production
```

#### Output

The command displays minimal, clean output:

1. Progress status for each feature (Building/Built/Skipped)
2. Summary with counts and duration

Example output (default):

```
Building user_total_spend...
Built user_total_spend v1.0.0 → feature_store/user_total_spend/1.0.0/data.parquet
Skipped user_avg_spend v1.0.0 (exists)

Finished in 2.34s (1 built, 1 skipped)
```

Example output with `--preview`:

```
Building user_total_spend...
Built user_total_spend v1.0.0 → feature_store/user_total_spend/1.0.0/data.parquet
┌─────────┬─────────────┐
│ user_id │ total_spend │
├─────────┼─────────────┤
│ u1      │ 150.0       │
│ u2      │ 250.0       │
│ u3      │ 100.0       │
└─────────┴─────────────┘
5,000 rows total

Finished in 2.34s (1 built)
```

Example output with `--verbose` (debug logging):

```
2024-01-15 10:30:00.123 | DEBUG | mlforge.loader:load_definitions:57 - Auto-discovered definitions file...
2024-01-15 10:30:00.124 | DEBUG | mlforge.core:_add_feature:1242 - Registered feature: user_total_spend
Building user_total_spend...
2024-01-15 10:30:01.456 | DEBUG | mlforge.compilers.duckdb:compile_rolling:123 - Generated SQL: WITH ...
Built user_total_spend v1.0.0 → feature_store/user_total_spend/1.0.0/data.parquet

Finished in 2.34s (1 built)
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

Inspect features, entities, or sources in detail.

```bash
mlforge inspect <subcommand> NAME [OPTIONS]
```

#### Subcommands

- `feature FEATURE_NAME`: Inspect a feature's detailed metadata
- `entity ENTITY_NAME`: Inspect an entity's configuration
- `source SOURCE_NAME`: Inspect a source's configuration

#### inspect feature

Display detailed metadata for a specific feature.

```bash
mlforge inspect feature FEATURE_NAME [OPTIONS]
```

**Arguments:**

- `FEATURE_NAME` (required): Name of the feature to inspect

**Options:**

- `--target PATH`: Path to definitions.py file.
- `--version VERSION`: Specific version to inspect. Defaults to latest.
- `--profile NAME`: Profile name from mlforge.yaml.

**Examples:**

```bash
mlforge inspect feature user_spend
mlforge inspect feature user_spend --version 1.0.0
```

**Output:**

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

**Error Handling:**

```bash
$ mlforge inspect feature user_spend
Error: No metadata found for feature 'user_spend'.
Run 'mlforge build' to generate metadata.
```

#### inspect entity

Display detailed information for an entity.

```bash
mlforge inspect entity ENTITY_NAME [OPTIONS]
```

**Arguments:**

- `ENTITY_NAME` (required): Name of the entity to inspect

**Options:**

- `--target PATH`: Path to definitions.py file.
- `--profile NAME`: Profile name from mlforge.yaml.

**Examples:**

```bash
mlforge inspect entity user
```

**Output:**

Shows entity configuration including join key, source columns for surrogate key generation, and which features use this entity.

#### inspect source

Display detailed information for a source.

```bash
mlforge inspect source SOURCE_NAME [OPTIONS]
```

**Arguments:**

- `SOURCE_NAME` (required): Name of the source to inspect

**Options:**

- `--target PATH`: Path to definitions.py file.
- `--profile NAME`: Profile name from mlforge.yaml.

**Examples:**

```bash
mlforge inspect source transactions
```

**Output:**

Shows source configuration including path, format, location, and which features use this source.

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

### init

Initialize a new mlforge project with boilerplate structure.

```bash
mlforge init NAME [OPTIONS]
```

#### Arguments

- `NAME` (required): Name of the project to create

#### Options

- `--online TYPE`: Include online store config (`redis` or `valkey`)
- `--engine ENGINE`: Default compute engine (`duckdb`)
- `--store TYPE`: Offline store type (`local` or `s3`). Defaults to `local`.
- `--profile`: Include mlforge.yaml with environment profiles

#### Examples

Create a basic project:

```bash
mlforge init my-features
```

Create with Redis online store:

```bash
mlforge init my-features --online redis
```

Create with DuckDB engine and S3 storage:

```bash
mlforge init my-features --engine duckdb --store s3
```

Create with environment profiles:

```bash
mlforge init my-features --profile
```

#### Output

Creates the following structure:

```
my-features/
├── src/
│   └── my_features/
│       ├── __init__.py
│       ├── definitions.py
│       ├── features.py
│       └── entities.py
├── data/
├── feature_store/
├── pyproject.toml
├── README.md
├── .gitignore
└── mlforge.yaml  # if --profile used
```

---

### profile

Display current profile configuration from mlforge.yaml.

```bash
mlforge profile [OPTIONS]
```

#### Options

- `--profile NAME`: Profile name to display. Defaults to current profile.
- `--validate`: Test connectivity to configured stores.

#### Examples

Show current profile:

```bash
mlforge profile
```

Show a specific profile:

```bash
mlforge profile --profile production
```

Validate store connectivity:

```bash
mlforge profile --validate
```

#### Output

```
Profile: dev (from mlforge.yaml default)

Offline Store:
  Type: local
  Path: ./feature_store

Online Store: not configured
```

With `--validate`:

```
Validating stores...
  offline_store: local - OK
  online_store: redis - OK

Profile valid.
```

---

### diff

Compare two versions of a feature.

```bash
mlforge diff FEATURE_NAME [VERSION1] [VERSION2] [OPTIONS]
```

#### Arguments

- `FEATURE_NAME` (required): Name of the feature to compare
- `VERSION1` (optional): First version. If omitted, compares latest with previous.
- `VERSION2` (optional): Second version. If omitted, compares VERSION1 with latest.

#### Options

- `--target PATH`: Path to definitions.py file.
- `--format FORMAT`: Output format (`table` or `json`). Defaults to `table`.
- `--quiet`: Quiet mode (exit code only).
- `--profile NAME`: Profile name from mlforge.yaml.

#### Examples

Compare latest with previous version:

```bash
mlforge diff user_spend
```

Compare specific versions:

```bash
mlforge diff user_spend 1.0.0 2.0.0
```

Compare a version with latest:

```bash
mlforge diff user_spend 1.0.0
```

JSON output for scripting:

```bash
mlforge diff user_spend --format json
```

#### Exit Codes

- `0`: No differences (same version)
- `1`: PATCH differences (data only)
- `2`: MINOR differences (additive changes)
- `3`: MAJOR differences (breaking changes)
- `4`: Error

---

### rollback

Rollback a feature to a previous version.

```bash
mlforge rollback FEATURE_NAME [VERSION] [OPTIONS]
```

Updates `_latest.json` to point to the target version. Does NOT delete any version data.

#### Arguments

- `FEATURE_NAME` (required): Name of the feature to rollback
- `VERSION` (optional): Version to rollback to

#### Options

- `--previous`: Rollback to the version before latest
- `--dry-run`: Show what would happen without making changes
- `--force`, `-f`: Skip confirmation prompt
- `--target PATH`: Path to definitions.py file.
- `--profile NAME`: Profile name from mlforge.yaml.

#### Examples

Rollback to specific version:

```bash
mlforge rollback user_spend 1.0.0
```

Rollback to previous version:

```bash
mlforge rollback user_spend --previous
```

Preview without making changes:

```bash
mlforge rollback user_spend 1.0.0 --dry-run
```

Skip confirmation:

```bash
mlforge rollback user_spend 1.0.0 --force
```

#### Exit Codes

- `0`: Rollback successful
- `1`: Version not found
- `2`: Already at target version
- `3`: User cancelled
- `4`: Error

---

### list

List features, entities, sources, or versions.

```bash
mlforge list <subcommand> [OPTIONS]
```

#### Subcommands

- `features`: List all registered features
- `entities`: List all entities used by features
- `sources`: List all sources used by features
- `versions FEATURE_NAME`: List all versions of a specific feature

#### list features

Display all registered features in a table.

```bash
mlforge list features [OPTIONS]
```

**Options:**

- `--target PATH`: Path to definitions.py file. Auto-discovers if not specified.
- `--tags TAGS`: Comma-separated list of tags to filter features by.
- `--profile NAME`: Profile name from mlforge.yaml.

**Examples:**

```bash
mlforge list features
mlforge list features --tags user_metrics
```

**Output:**

```
┌──────────────────────┬──────────────────┬──────────────────────────┬──────────────┬───────────────────────────┐
│ Name                 │ Keys             │ Source                   │ Tags         │ Description               │
├──────────────────────┼──────────────────┼──────────────────────────┼──────────────┼───────────────────────────┤
│ user_total_spend     │ [user_id]        │ data/transactions.parquet│ user_metrics │ Total spend by user       │
│ merchant_total_spend │ [merchant_id]    │ data/transactions.parquet│ -            │ Total spend by merchant   │
└──────────────────────┴──────────────────┴──────────────────────────┴──────────────┴───────────────────────────┘
```

#### list entities

List all entities used by features.

```bash
mlforge list entities [OPTIONS]
```

**Options:**

- `--target PATH`: Path to definitions.py file.
- `--profile NAME`: Profile name from mlforge.yaml.

**Examples:**

```bash
mlforge list entities
```

**Output:**

```
┌──────────┬──────────────┬───────────────────────────┐
│ Name     │ Join Key     │ From Columns              │
├──────────┼──────────────┼───────────────────────────┤
│ user     │ user_id      │ [first, last, dob]        │
│ merchant │ merchant_id  │ -                         │
└──────────┴──────────────┴───────────────────────────┘
```

#### list sources

List all sources used by features.

```bash
mlforge list sources [OPTIONS]
```

**Options:**

- `--target PATH`: Path to definitions.py file.
- `--profile NAME`: Profile name from mlforge.yaml.

**Examples:**

```bash
mlforge list sources
```

#### list versions

List all versions of a feature.

```bash
mlforge list versions FEATURE_NAME [OPTIONS]
```

**Arguments:**

- `FEATURE_NAME` (required): Name of the feature to list versions for

**Options:**

- `--target PATH`: Path to definitions.py file.
- `--profile NAME`: Profile name from mlforge.yaml.

**Examples:**

```bash
mlforge list versions user_spend
```

**Output:**

```
Versions of user_spend
┌─────────┬─────────────────────┬────────────┐
│ Version │ Created             │ Rows       │
├─────────┼─────────────────────┼────────────┤
│ 1.0.0   │ 2024-01-10T08:00:00│ 50,000     │
│ 1.1.0   │ 2024-01-15T10:30:00│ 52,500     │
│ 2.0.0   │ 2024-01-20T14:00:00│ 55,000     │
└─────────┴─────────────────────┴────────────┘

Latest: 2.0.0
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

- `MLFORGE_PROFILE`: Override the default profile from mlforge.yaml. Takes precedence over `default_profile` in the config file but can be overridden by `--profile` command-line option.

```bash
# Use production profile for all commands
export MLFORGE_PROFILE=production
mlforge build
```

Profile resolution order (highest to lowest priority):

1. `--profile` command-line option
2. `MLFORGE_PROFILE` environment variable
3. `default_profile` from mlforge.yaml

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
