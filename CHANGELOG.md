## v0.5.0 (2025-01-04)

### 💥 Breaking Changes

- **Storage layout**: Features now stored in versioned directories (`feature_store/user_spend/1.0.0/data.parquet`)
- **Metadata schema**: `last_updated` renamed to `updated_at`, new required fields (`version`, `created_at`, `content_hash`, `schema_hash`, `config_hash`)
- **get_training_data()**: Now accepts version tuples `("feature_name", "1.0.0")` for pinned versions

### ✨ Features

- **Feature Versioning**: Automatic semantic versioning with content-hash tracking
  - New version created when feature config, schema, or data changes
  - `mlforge versions <feature>` command to list versions
  - `mlforge sync` command for Git-based collaboration
  - Version pinning in `get_training_data()`

- **DuckDB Compute Engine**: Alternative to Polars for large datasets
  - Pluggable engine architecture (`engine="duckdb"` or `engine="polars"`)
  - SQL-based rolling window aggregations
  - Consistent results across engines

- **Unified Type System**: Canonical types for cross-engine consistency
  - `DataType` and `TypeKind` classes for type representation
  - Consistent schema hashing regardless of engine
  - Type conversion between Polars and DuckDB

- **Redis Online Store**: Real-time feature serving
  - `RedisStore` for low-latency feature lookups
  - `mlforge build --online` to populate Redis
  - `get_online_features()` for inference workloads
  - Batch read/write with Redis pipelines

- **Online Feature Retrieval**: High-level API for inference
  - `get_online_features()` function mirrors `get_training_data()` API
  - Entity key transform support
  - Batch retrieval with automatic joins

### ♻️ Refactorings

- Consolidate DuckDB connection helper into engines module
- Remove unused helper functions
- Restructure compilers into separate module

### 📝💡 Documentation

- Add online stores user guide
- Add versioning documentation
- Update CLI reference with new commands
- Add API docs for online and types modules

### 📌➕⬇️➖⬆️ Dependencies

- Add optional `duckdb>=1.0.0` dependency
- Add optional `redis>=7.1.0` dependency

## v0.4.0 (2025-12-28)

### ✨ Features

- add `__version__` via importlib.metadata
- add `mlforge validate` CLI command for data validation
- integrate validators into build pipeline
- add validators and validation infrastructure (`greater_than_or_equal`, `less_than`, etc.)
- add `inspect` and `manifest` CLI commands for feature metadata
- integrate metadata generation into build process
- add metadata methods to Store ABC and implementations (LocalStore, S3Store)
- add manifest module for feature metadata tracking
- add rolling aggregation metrics with timedelta support
- add metadata files for account, merchant, and user spend intervals (example)
- update transactions example to use S3Store

### 🐛🚑️ Fixes

- correct type annotations for metric compilation results
- add missing colon in clean-example-fs task

### ♻️ Refactorings

- split derive_column_metadata into focused helper functions
- add base_schema() method to EngineResult ABC
- improve JSON error handling with specific logging
- consolidate code review commands into unified agent
- improve logging message alignment and conciseness
- extract helper methods from materialize to reduce complexity

### ✅🤡🧪 Tests

- add tests for FeatureValidationError
- add comprehensive tests for metadata feature

### 📝💡 Documentation

- standardize on namespace import pattern (`import mlforge as mlf`)
- update README to reflect current v0.4.0 feature set
- add comprehensive validator documentation with custom examples
- add comprehensive documentation for metadata feature
- update package name to mlforge-sdk in installation commands
- update transaction example for metadata feature
- update documentation for build() rename and timedelta support

### 🔧🔨📦️ Configuration, Scripts, Packages

- migrate from claude cli to opencode
- gitignore reports directory for analysis artifacts
- add commitizen bump mappings to pyproject.toml

### 📌➕⬇️➖⬆️ Dependencies

- add s3fs for S3 storage support

### 💚👷 CI & Build

- handle no-commits case in bump workflow

## v0.3.0 (2025-12-16)

### ✨ Features

- add trusted publishing to PyPI in publish workflow

### 💄🚸 UI & UIX

- clean up changelog formatting

## v0.2.2 (2025-12-16)
### 📝💡 Documentation
- refactor commit command documentation
### 🚀 Deployments
- add force flag to docs deployment

## v0.2.1 (2025-12-16)
### fix
- sync all dependency groups in setup action
### 💚👷 CI & Build
- update UV sync command to use explicit dependency groups
### 🔧🔨📦️ Configuration, Scripts, Packages
- add version prefix to git tags
### 🚨 Linting
- add newline at end of setup action file
- remove trailing whitespace and add EOF newlines

## v0.2.0 (2025-12-15)
### ✨ Features
- add tags column to feature list table
- add auto-discovery to list command and improve help text
- add tag filtering and auto-discovery to CLI
- add feature tagging support to core
- add project discovery utilities
- implement mlforge feature store SDK
### 🐛🚑️ Fixes
- resolve mkdocstrings warnings for *args/**kwargs
### ♻️ Refactorings
- adopt module-level imports and remove duplicate logic
- consolidate discovery functions into loader module
- consolidate commitizen hooks to use local commands
- consolidate pre-commit hooks to use just commands
- update example project to use mlforge-sdk package name
### ✅🤡🧪 Tests
- add comprehensive tests for tags and auto-discovery features
- add comprehensive unit tests for CLI module
- add comprehensive test suite
### 📝💡 Documentation
- add documentation for feature tags and auto-discovery
- update transactions example to use feature tags
- update README with installation instructions, quick start guide, and feature details
- add workflow for updating README to reflect current codebase
- add comprehensive MkDocs documentation
- add project roadmap
- update Claude Code configuration
- add usage examples
- add project documentation and Claude Code configuration
### 🔧🔨📦️ Configuration, Scripts, Packages
- add Claude Code commands for test and doc updates
### 🚨 Linting
- remove trailing whitespace from Claude command files
