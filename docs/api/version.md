# Version API

The version module provides types and functions for semantic versioning, change detection, and Git integration.

## Enums

::: mlforge.version.ChangeType

## Data Classes

::: mlforge.version.ChangeSummary

## Version Parsing and Bumping

::: mlforge.version.parse_version

::: mlforge.version.format_version

::: mlforge.version.bump_version

::: mlforge.version.sort_versions

::: mlforge.version.is_valid_version

## Path Construction

::: mlforge.version.versioned_data_path

::: mlforge.version.versioned_metadata_path

::: mlforge.version.latest_pointer_path

::: mlforge.version.feature_versions_dir

## Hash Computation

::: mlforge.version.compute_schema_hash

::: mlforge.version.compute_config_hash

::: mlforge.version.compute_content_hash

::: mlforge.version.compute_source_hash

## Change Detection

::: mlforge.version.detect_change_type

::: mlforge.version.build_change_summary

## Version Discovery

::: mlforge.version.list_versions

::: mlforge.version.get_latest_version

::: mlforge.version.write_latest_pointer

::: mlforge.version.resolve_version

## Git Integration

::: mlforge.version.write_feature_gitignore
