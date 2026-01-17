import time
from pathlib import Path
from typing import Annotated

import cyclopts

import mlforge.errors as errors
import mlforge.loader as loader
import mlforge.logging as log
import mlforge.profiles as profiles_
import mlforge.stores as stores

app = cyclopts.App(name="mlforge", help="A simple feature store SDK")

# =============================================================================
# Project initialization templates
# =============================================================================

DEFINITIONS_TEMPLATE = '''"""Definitions for {name}."""

import mlforge as mlf
from {module_name} import features

defs = mlf.Definitions(
    name="{name}",
    features=[features],
    offline_store=mlf.LocalStore(path="./feature_store"),{online_store}{engine}
)
'''

DEFINITIONS_ONLINE_REDIS = """
    online_store=mlf.RedisStore(host="localhost", port=6379),"""

DEFINITIONS_ONLINE_VALKEY = """
    online_store=mlf.ValkeyStore(host="localhost", port=6379),"""

DEFINITIONS_ENGINE_DUCKDB = """
    engine="duckdb","""

DEFINITIONS_S3_STORE = '''"""Definitions for {name}."""

import mlforge as mlf
from {module_name} import features

defs = mlf.Definitions(
    name="{name}",
    features=[features],
    offline_store=mlf.S3Store(
        bucket="my-bucket",
        prefix="features",
    ),{online_store}{engine}
)
'''

FEATURES_TEMPLATE = '''"""Feature definitions for {name}."""

import mlforge as mlf
import polars as pl


# Example feature - replace with your own
@mlf.feature(
    source="data/example.parquet",
    keys=["entity_id"],
    timestamp="event_time",
    interval="1d",
)
def example_feature(df: pl.DataFrame) -> pl.DataFrame:
    """Example feature - replace with your implementation."""
    return df.select("entity_id", "event_time", "value")
'''

ENTITIES_TEMPLATE = '''"""Entity definitions for {name}."""

import mlforge as mlf  # noqa: F401

# Example entity - replace with your own
# user = mlf.Entity(
#     name="user",
#     join_key="user_id",
#     from_columns=["first_name", "last_name"],
# )
'''

PYPROJECT_TEMPLATE = """[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "{mlforge_dep}",
    "polars>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "ruff>=0.4.0",
]

[tool.ruff]
line-length = 88
target-version = "py313"
"""

README_TEMPLATE = """# {name}

Feature store built with [mlforge](https://github.com/chonalchendo/mlforge).

## Setup

```bash
uv sync
```

## Build Features

```bash
mlforge build --target src/{module_name}/definitions.py
```

## List Features

```bash
mlforge list features --target src/{module_name}/definitions.py
```
"""

GITIGNORE_TEMPLATE = """# Python
__pycache__/
*.py[cod]
.venv/

# mlforge
feature_store/*.parquet

# IDE
.idea/
.vscode/
"""

FEATURE_STORE_GITIGNORE = """# Ignore parquet files but keep directory
*.parquet
!.gitignore
"""

MLFORGE_YAML_TEMPLATE = """default_profile: dev

profiles:
  dev:
    offline_store:
      KIND: local
      path: ./feature_store

  production:
    offline_store:
      KIND: s3
      bucket: ${{oc.env:S3_BUCKET}}
      prefix: features
"""

# Sub-apps for command groups
list_app = cyclopts.App(
    name="list", help="List features, entities, sources, or versions."
)
app.command(list_app)

inspect_app = cyclopts.App(
    name="inspect", help="Inspect features, entities, or sources."
)
app.command(inspect_app)


def main() -> None:
    """
    Entry point for the CLI.

    Configures logging before dispatching commands. Use --verbose/-v
    for debug logging.
    """
    import sys

    # Check for verbose flag before dispatching
    verbose = "-v" in sys.argv or "--verbose" in sys.argv

    # Remove verbose flags from argv so they don't confuse subcommands
    sys.argv = [
        arg
        for arg in sys.argv
        if arg not in ("-v", "--verbose", "--no-verbose")
    ]

    log.setup_logging(verbose=verbose)
    app()


@app.command
def build(
    target: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--target",
            help="Path to definitions.py file. Automatically handled.",
        ),
    ] = None,
    features: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--features", help="Comma-separated feature names"
        ),
    ] = None,
    tags: Annotated[
        str | None,
        cyclopts.Parameter(name="--tags", help="Comma-separated feature tags"),
    ] = None,
    version: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--version",
            help="Explicit version override (e.g., '2.0.0'). If not specified, auto-detects.",
        ),
    ] = None,
    force: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--force", "-f"], help="Overwrite existing features."
        ),
    ] = False,
    preview: Annotated[
        bool,
        cyclopts.Parameter(
            name="--preview", help="Show feature data preview after building"
        ),
    ] = False,
    preview_rows: Annotated[
        int,
        cyclopts.Parameter(
            name="--preview-rows",
            help="Number of preview rows to display. Defaults to 5.",
        ),
    ] = 5,
    online: Annotated[
        bool,
        cyclopts.Parameter(
            name="--online",
            help="Write to online store instead of offline store.",
        ),
    ] = False,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name from mlforge.yaml to use for stores.",
        ),
    ] = None,
    start: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--start",
            help="Start of date range for incremental build (e.g., '2026-01-01').",
        ),
    ] = None,
    end: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--end",
            help="End of date range for incremental build (e.g., '2026-01-15').",
        ),
    ] = None,
    last: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--last",
            help="Process data from last N period (e.g., '7d', '24h').",
        ),
    ] = None,
    full_refresh: Annotated[
        bool,
        cyclopts.Parameter(
            name="--full-refresh",
            help="Force full rebuild, ignoring incremental state.",
        ),
    ] = False,
):
    """
    Materialize features to offline storage with versioning.

    Loads feature definitions, computes features from source data,
    and persists results to the configured storage backend. Automatically
    determines version based on schema and configuration changes.

    Supports incremental builds that only process new data since the last
    build, significantly improving build times for large datasets.

    With --online flag, writes to the online store (e.g., Redis) instead
    of the offline store. Extracts the latest value per entity for
    real-time feature serving.

    Args:
        target: Path to definitions file. Defaults to "definitions.py".
        features: Comma-separated list of feature names. Defaults to None (all).
        tags: Comma-separated list of feature tags. Defaults to None.
        version: Explicit version override. If not specified, auto-detects.
        force: Overwrite existing features. Defaults to False.
        preview: Show feature data preview after building. Defaults to False.
        preview_rows: Number of preview rows to display. Defaults to 5.
        online: Write to online store instead of offline. Defaults to False.
        profile: Profile name from mlforge.yaml. Defaults to None (uses env var or config default).
        start: Start of date range for incremental build.
        end: End of date range for incremental build.
        last: Process data from last N period (e.g., '7d', '24h').
        full_refresh: Force full rebuild, ignoring incremental state.

    Raises:
        SystemExit: If loading definitions or materialization fails
    """
    if tags and features:
        raise ValueError(
            "Tags and features cannot be specified at the same time. Choose one or the other."
        )

    try:
        defs = loader.load_definitions(target, profile=profile)
        feature_names = (
            [f.strip() for f in features.split(",")] if features else None
        )
        tag_names = [t.strip() for t in tags.split(",")] if tags else None

        start_time = time.perf_counter()

        result = defs.build(
            feature_names=feature_names,
            tag_names=tag_names,
            feature_version=version,
            force=force,
            preview=preview,
            preview_rows=preview_rows,
            online=online,
            start=start,
            end=end,
            last=last,
            full_refresh=full_refresh,
        )

        duration = time.perf_counter() - start_time

        if online:
            # Online build - show record counts
            total_records = sum(int(str(v)) for v in result.paths.values())
            log.print_success(
                f"Wrote {total_records} records to online store "
                f"({result.built} features)"
            )
        else:
            # Offline build - show summary
            log.print_build_summary(
                built=result.built,
                skipped=result.skipped,
                failed=result.failed,
                duration=duration,
            )

    except (
        errors.DefinitionsLoadError,
        errors.FeatureMaterializationError,
        errors.ProfileError,
    ) as e:
        log.print_error(str(e))
        raise SystemExit(1)


@app.command
def validate(
    target: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--target",
            help="Path to definitions.py file. Automatically handled.",
        ),
    ] = None,
    features: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--features", help="Comma-separated feature names"
        ),
    ] = None,
    tags: Annotated[
        str | None,
        cyclopts.Parameter(name="--tags", help="Comma-separated feature tags"),
    ] = None,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name from mlforge.yaml to use for stores.",
        ),
    ] = None,
):
    """
    Run validation checks on features without building.

    Loads feature definitions, runs feature transformations, and validates
    outputs against defined validators. Does not compute metrics or persist data.

    Args:
        target: Path to definitions file. Defaults to "definitions.py".
        features: Comma-separated list of feature names. Defaults to None (all).
        tags: Comma-separated list of feature tags. Defaults to None.
        profile: Profile name from mlforge.yaml. Defaults to None (uses env var or config default).

    Raises:
        SystemExit: If loading definitions fails or any validation fails
    """
    if tags and features:
        raise ValueError(
            "Tags and features cannot be specified at the same time. Choose one or the other."
        )

    try:
        defs = loader.load_definitions(target, profile=profile)
        feature_names = (
            [f.strip() for f in features.split(",")] if features else None
        )
        tag_names = [t.strip() for t in tags.split(",")] if tags else None

        results = defs.validate(
            feature_names=feature_names,
            tag_names=tag_names,
        )

        if not results:
            log.print_warning("No features with validators found.")
            return

        log.print_validation_results(results)

        # Count results
        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed)
        total_features = len(defs.list_features())
        skipped = total_features - len(results)

        log.print_validation_summary(passed, failed, skipped)

        if failed > 0:
            raise SystemExit(1)

    except (errors.DefinitionsLoadError, errors.ProfileError) as e:
        log.print_error(str(e))
        raise SystemExit(1)


@list_app.command
def features(
    target: Annotated[
        str | None,
        cyclopts.Parameter(
            help="Path to definitions.py file - automatically handled."
        ),
    ] = None,
    tags: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--tags", help="Comma-separated list of feature tags."
        ),
    ] = None,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name from mlforge.yaml to use for stores.",
        ),
    ] = None,
):
    """
    List all registered features.

    Loads feature definitions and prints their metadata including
    names, keys, sources, and descriptions.
    """
    try:
        defs = loader.load_definitions(target, profile=profile)
    except (errors.DefinitionsLoadError, errors.ProfileError) as e:
        log.print_error(str(e))
        raise SystemExit(1)
    feature_dict = defs.features

    if tags:
        tag_set = {t.strip() for t in tags.split(",")}
        feature_dict = {
            name: feature
            for name, feature in feature_dict.items()
            if feature.tags and tag_set.intersection(feature.tags)
        }

        if not feature_dict:
            log.print_warning(f"No features found with tags: {tags}")
            return

    log.print_features_table(feature_dict)


@list_app.command
def entities(
    target: Annotated[
        str | None,
        cyclopts.Parameter(
            help="Path to definitions.py file - automatically handled."
        ),
    ] = None,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name from mlforge.yaml to use for stores.",
        ),
    ] = None,
):
    """
    List all entities used by features.

    Shows entity names, join keys, and source columns for surrogate key generation.
    """
    try:
        defs = loader.load_definitions(target, profile=profile)
    except (errors.DefinitionsLoadError, errors.ProfileError) as e:
        log.print_error(str(e))
        raise SystemExit(1)

    entity_names = defs.list_entities()
    if not entity_names:
        log.print_warning("No entities found.")
        return

    entities_dict = {name: defs.get_entity(name) for name in entity_names}
    log.print_entities_table(entities_dict)


@list_app.command
def sources(
    target: Annotated[
        str | None,
        cyclopts.Parameter(
            help="Path to definitions.py file - automatically handled."
        ),
    ] = None,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name from mlforge.yaml to use for stores.",
        ),
    ] = None,
):
    """
    List all sources used by features.

    Shows source names, paths, formats, and storage locations.
    """
    try:
        defs = loader.load_definitions(target, profile=profile)
    except (errors.DefinitionsLoadError, errors.ProfileError) as e:
        log.print_error(str(e))
        raise SystemExit(1)

    source_names = defs.list_sources()
    if not source_names:
        log.print_warning("No sources found.")
        return

    sources_dict = {name: defs.get_source(name) for name in source_names}
    log.print_sources_table(sources_dict)


@inspect_app.command
def feature(
    feature_name: Annotated[
        str,
        cyclopts.Parameter(help="Name of the feature to inspect"),
    ],
    target: Annotated[
        str | None,
        cyclopts.Parameter(name="--target", help="Path to definitions.py file"),
    ] = None,
    version: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--version",
            help="Specific version to inspect. Defaults to latest.",
        ),
    ] = None,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name from mlforge.yaml to use for stores.",
        ),
    ] = None,
):
    """
    Inspect a feature's detailed metadata.

    Shows feature configuration, storage details, column information,
    version info, and hashes from the feature's metadata file.

    Args:
        feature_name: Name of the feature to inspect
        target: Path to definitions file. Defaults to "definitions.py".
        version: Specific version to inspect. Defaults to latest.
        profile: Profile name from mlforge.yaml. Defaults to None (uses env var or config default).

    Raises:
        SystemExit: If feature metadata is not found
    """
    try:
        defs = loader.load_definitions(target, profile=profile)
        metadata = defs.offline_store.read_metadata(feature_name, version)

        if not metadata:
            version_str = f" version '{version}'" if version else ""
            log.print_error(
                f"No metadata found for feature '{feature_name}'{version_str}. "
                "Run 'mlforge build' to generate metadata."
            )
            raise SystemExit(1)

        log.print_feature_metadata(feature_name, metadata)

    except (errors.DefinitionsLoadError, errors.ProfileError) as e:
        log.print_error(str(e))
        raise SystemExit(1)


@inspect_app.command
def entity(
    entity_name: Annotated[
        str,
        cyclopts.Parameter(help="Name of the entity to inspect"),
    ],
    target: Annotated[
        str | None,
        cyclopts.Parameter(name="--target", help="Path to definitions.py file"),
    ] = None,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name from mlforge.yaml to use for stores.",
        ),
    ] = None,
):
    """
    Inspect an entity's details.

    Shows entity configuration including join key, source columns,
    and which features use this entity.

    Args:
        entity_name: Name of the entity to inspect
        target: Path to definitions file. Defaults to "definitions.py".
        profile: Profile name from mlforge.yaml. Defaults to None (uses env var or config default).

    Raises:
        SystemExit: If entity is not found
    """
    try:
        defs = loader.load_definitions(target, profile=profile)
        ent = defs.get_entity(entity_name)

        if ent is None:
            log.print_error(f"Entity '{entity_name}' not found.")
            raise SystemExit(1)

        used_in = defs.features_using_entity(entity_name)
        log.print_entity_detail(ent, used_in)

    except (errors.DefinitionsLoadError, errors.ProfileError) as e:
        log.print_error(str(e))
        raise SystemExit(1)


@inspect_app.command
def source(
    source_name: Annotated[
        str,
        cyclopts.Parameter(help="Name of the source to inspect"),
    ],
    target: Annotated[
        str | None,
        cyclopts.Parameter(name="--target", help="Path to definitions.py file"),
    ] = None,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name from mlforge.yaml to use for stores.",
        ),
    ] = None,
):
    """
    Inspect a source's details.

    Shows source configuration including path, format, location,
    and which features use this source.

    Args:
        source_name: Name of the source to inspect
        target: Path to definitions file. Defaults to "definitions.py".
        profile: Profile name from mlforge.yaml. Defaults to None (uses env var or config default).

    Raises:
        SystemExit: If source is not found
    """
    try:
        defs = loader.load_definitions(target, profile=profile)
        src = defs.get_source(source_name)

        if src is None:
            log.print_error(f"Source '{source_name}' not found.")
            raise SystemExit(1)

        used_in = defs.features_using_source(source_name)
        log.print_source_detail(src, used_in)

    except (errors.DefinitionsLoadError, errors.ProfileError) as e:
        log.print_error(str(e))
        raise SystemExit(1)


@list_app.command
def versions(
    feature_name: Annotated[
        str,
        cyclopts.Parameter(help="Name of the feature to list versions for"),
    ],
    target: Annotated[
        str | None,
        cyclopts.Parameter(name="--target", help="Path to definitions.py file"),
    ] = None,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name from mlforge.yaml to use for stores.",
        ),
    ] = None,
):
    """
    List all versions of a feature.

    Shows all available versions with the latest version marked.

    Args:
        feature_name: Name of the feature to list versions for
        target: Path to definitions file. Defaults to "definitions.py".
        profile: Profile name from mlforge.yaml. Defaults to None (uses env var or config default).

    Raises:
        SystemExit: If loading definitions fails
    """
    try:
        defs = loader.load_definitions(target, profile=profile)
        version_list = defs.offline_store.list_versions(feature_name)

        if not version_list:
            log.print_warning(
                f"No versions found for feature '{feature_name}'."
            )
            return

        latest = defs.offline_store.get_latest_version(feature_name)
        log.print_versions_table(feature_name, version_list, latest)

    except (errors.DefinitionsLoadError, errors.ProfileError) as e:
        log.print_error(str(e))
        raise SystemExit(1)


@app.command
def manifest(
    target: Annotated[
        str | None,
        cyclopts.Parameter(help="Path to definitions.py file"),
    ] = None,
    regenerate: Annotated[
        bool,
        cyclopts.Parameter(
            name="--regenerate",
            help="Regenerate consolidated manifest.json from .meta.json files",
        ),
    ] = False,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name from mlforge.yaml to use for stores.",
        ),
    ] = None,
):
    """
    Display or regenerate the feature manifest.

    Without --regenerate, shows a summary of all feature metadata.
    With --regenerate, rebuilds manifest.json from individual .meta.json files.

    Args:
        target: Path to definitions file. Defaults to "definitions.py".
        regenerate: Rebuild manifest from metadata files. Defaults to False.
        profile: Profile name from mlforge.yaml. Defaults to None (uses env var or config default).

    Raises:
        SystemExit: If loading definitions fails
    """
    try:
        defs = loader.load_definitions(target, profile=profile)
        metadata_list = defs.offline_store.list_metadata()

        if not metadata_list:
            log.print_warning(
                "No feature metadata found. Run 'mlforge build' first."
            )
            return

        if regenerate:
            from datetime import datetime, timezone
            from pathlib import Path

            from mlforge.manifest import Manifest, write_manifest_file

            manifest_obj = Manifest(
                generated_at=datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
            for meta in metadata_list:
                manifest_obj.add_feature(meta)

            # Write to store root
            if hasattr(defs.offline_store, "path"):
                path = defs.offline_store.path
                if isinstance(path, str):
                    manifest_path = f"{path}/manifest.json"
                elif isinstance(path, Path):
                    manifest_path = path / "manifest.json"
            else:
                manifest_path = Path("manifest.json")

            write_manifest_file(manifest_path, manifest_obj)
            log.print_success(
                f"Regenerated manifest.json with {len(metadata_list)} features"
            )
        else:
            log.print_manifest_summary(metadata_list)

    except (errors.DefinitionsLoadError, errors.ProfileError) as e:
        log.print_error(str(e))
        raise SystemExit(1)


@app.command
def sync(
    target: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--target",
            help="Path to definitions.py file. Automatically handled.",
        ),
    ] = None,
    features: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--features", help="Comma-separated feature names"
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        cyclopts.Parameter(
            name="--dry-run", help="Show what would be synced without doing it"
        ),
    ] = False,
    force: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--force", "-f"],
            help="Rebuild even if source data has changed since original build",
        ),
    ] = False,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name from mlforge.yaml to use for stores.",
        ),
    ] = None,
):
    """
    Rebuild features that have metadata but no data.

    This command is useful when you've pulled feature metadata from Git
    but don't have the data files locally. It will rebuild the features
    from source data to recreate the missing parquet files.

    Only works with LocalStore - for cloud storage (S3, etc.), data is
    already shared and doesn't need syncing.

    Args:
        target: Path to definitions file. Defaults to "definitions.py".
        features: Comma-separated list of feature names. Defaults to None (all).
        dry_run: Show what would be synced without doing it. Defaults to False.
        force: Rebuild even if source data has changed. Defaults to False.
        profile: Profile name from mlforge.yaml. Defaults to None (uses env var or config default).

    Raises:
        SystemExit: If store is not LocalStore or sync fails
    """
    try:
        defs = loader.load_definitions(target, profile=profile)

        # Verify store is LocalStore
        if not isinstance(defs.offline_store, stores.LocalStore):
            log.print_error(
                "mlforge sync only works with LocalStore. "
                "For cloud storage (S3, etc.), data is already shared."
            )
            raise SystemExit(1)

        feature_names = (
            [f.strip() for f in features.split(",")] if features else None
        )

        results = defs.sync(
            feature_names=feature_names,
            dry_run=dry_run,
            force=force,
        )

        if dry_run:
            if results["needs_sync"]:
                log.print_info("Features that need syncing:")
                for name in results["needs_sync"]:
                    log.print_info(f"  - {name}")
                if results.get("source_changed"):
                    log.print_warning("Features with changed source data:")
                    for name in results["source_changed"]:
                        log.print_warning(f"  - {name}")
            else:
                log.print_success("All features are up to date.")
        else:
            if results["synced"]:
                log.print_success(f"Synced {len(results['synced'])} features")
            elif results["needs_sync"]:
                log.print_warning(
                    "Some features could not be synced (source data changed)"
                )
            else:
                log.print_success("All features are up to date.")

    except (
        errors.DefinitionsLoadError,
        errors.ProfileError,
        errors.SourceDataChangedError,
    ) as e:
        log.print_error(str(e))
        raise SystemExit(1)


@app.command
def profile(
    profile_name: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name to display. Defaults to current profile.",
        ),
    ] = None,
    validate_: Annotated[
        bool,
        cyclopts.Parameter(
            name="--validate",
            help="Validate connectivity to configured stores.",
        ),
    ] = False,
):
    """
    Display current profile configuration.

    Shows the active profile and its store configurations. Use --validate
    to test connectivity to configured stores.

    Args:
        profile_name: Profile name to display. Defaults to current profile.
        validate_: Test connectivity to stores. Defaults to False.

    Raises:
        SystemExit: If profile not found or validation fails
    """
    try:
        # Get profile info (single load_config call)
        info = profiles_.get_profile_info()
        if info is None:
            log.print_warning(
                f"No {profiles_.CONFIG_FILENAME} found in current directory."
            )
            log.print_info(
                "Create mlforge.yaml to configure environment profiles."
            )
            return

        current_name, source, config = info
        target_name = profile_name or current_name

        # Determine source description
        if profile_name:
            source_str = "explicitly requested"
        elif source == "env":
            source_str = "from MLFORGE_PROFILE env var"
        else:
            source_str = f"from {profiles_.CONFIG_FILENAME} default"

        # Load and display profile
        profile_config = profiles_.load_profile(target_name)
        log.print_info(f"Profile: {target_name} ({source_str})")
        log.print_info("")
        profiles_.print_store_config(profile_config)

        if validate_:
            profiles_.validate_stores(profile_config)

    except errors.ProfileError as e:
        log.print_error(str(e))
        raise SystemExit(1)


@app.command
def init(
    name: Annotated[
        str,
        cyclopts.Parameter(help="Name of the project to create"),
    ],
    online: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--online",
            help="Include online store config (redis, valkey)",
        ),
    ] = None,
    engine: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--engine",
            help="Default compute engine (duckdb)",
        ),
    ] = None,
    store: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--store",
            help="Offline store type (local, s3). Defaults to local.",
        ),
    ] = None,
    with_profile: Annotated[
        bool,
        cyclopts.Parameter(
            name="--profile",
            help="Include mlforge.yaml with environment profiles",
        ),
    ] = False,
):
    """
    Initialize a new mlforge project.

    Creates a project directory with boilerplate structure including
    source files, pyproject.toml, README, and configuration files.

    Args:
        name: Name of the project to create
        online: Include online store config (redis, valkey)
        engine: Default compute engine (duckdb)
        store: Offline store type (local, s3). Defaults to local.
        with_profile: Include mlforge.yaml with environment profiles

    Raises:
        SystemExit: If directory already exists or invalid options provided
    """
    project_dir = Path(name)
    module_name = name.replace("-", "_")

    # Validate directory doesn't exist
    if project_dir.exists():
        log.print_error(f"Directory '{name}' already exists")
        raise SystemExit(1)

    # Validate options
    if online and online not in ("redis", "valkey"):
        log.print_error(
            f"Invalid online store: '{online}'. Use 'redis' or 'valkey'."
        )
        raise SystemExit(1)

    if engine and engine != "duckdb":
        log.print_error(f"Invalid engine: '{engine}'. Use 'duckdb'.")
        raise SystemExit(1)

    if store and store not in ("local", "s3"):
        log.print_error(f"Invalid store: '{store}'. Use 'local' or 's3'.")
        raise SystemExit(1)

    # Create directory structure
    src_dir = project_dir / "src" / module_name
    src_dir.mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "feature_store").mkdir()

    # Build definitions content
    online_store = ""
    if online == "redis":
        online_store = DEFINITIONS_ONLINE_REDIS
    elif online == "valkey":
        online_store = DEFINITIONS_ONLINE_VALKEY

    engine_str = DEFINITIONS_ENGINE_DUCKDB if engine == "duckdb" else ""

    if store == "s3":
        definitions_content = DEFINITIONS_S3_STORE.format(
            name=name,
            module_name=module_name,
            online_store=online_store,
            engine=engine_str,
        )
    else:
        definitions_content = DEFINITIONS_TEMPLATE.format(
            name=name,
            module_name=module_name,
            online_store=online_store,
            engine=engine_str,
        )

    # Determine mlforge dependency
    mlforge_dep = "mlforge>=0.6.0"
    if engine == "duckdb":
        mlforge_dep = "mlforge[duckdb]>=0.6.0"

    # Write source files
    (src_dir / "__init__.py").write_text("")
    (src_dir / "definitions.py").write_text(definitions_content)
    (src_dir / "features.py").write_text(FEATURES_TEMPLATE.format(name=name))
    (src_dir / "entities.py").write_text(ENTITIES_TEMPLATE.format(name=name))

    # Write project files
    (project_dir / "pyproject.toml").write_text(
        PYPROJECT_TEMPLATE.format(name=name, mlforge_dep=mlforge_dep)
    )
    (project_dir / "README.md").write_text(
        README_TEMPLATE.format(name=name, module_name=module_name)
    )
    (project_dir / ".gitignore").write_text(GITIGNORE_TEMPLATE)
    (project_dir / "data" / ".gitkeep").write_text("")
    (project_dir / "feature_store" / ".gitignore").write_text(
        FEATURE_STORE_GITIGNORE
    )

    # Write profile config if requested
    if with_profile:
        (project_dir / "mlforge.yaml").write_text(MLFORGE_YAML_TEMPLATE)

    log.print_success(f"Created project '{name}'")
    log.console.print("")
    log.console.print("Next steps:")
    log.console.print(f"  cd {name}")
    log.console.print("  uv sync")
    log.console.print(
        f"  mlforge build --target src/{module_name}/definitions.py"
    )


@app.command
def diff(
    feature_name: Annotated[
        str,
        cyclopts.Parameter(help="Name of the feature to compare"),
    ],
    version1: Annotated[
        str | None,
        cyclopts.Parameter(help="First version to compare"),
    ] = None,
    version2: Annotated[
        str | None,
        cyclopts.Parameter(help="Second version to compare"),
    ] = None,
    target: Annotated[
        str | None,
        cyclopts.Parameter(name="--target", help="Path to definitions.py file"),
    ] = None,
    format_: Annotated[
        str,
        cyclopts.Parameter(
            name="--format",
            help="Output format (table, json)",
        ),
    ] = "table",
    quiet: Annotated[
        bool,
        cyclopts.Parameter(
            name="--quiet",
            help="Quiet mode (exit code only)",
        ),
    ] = False,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name from mlforge.yaml to use for stores.",
        ),
    ] = None,
):
    """
    Compare two versions of a feature.

    Shows schema changes, config changes, and data statistics between versions.

    Examples:
        mlforge diff user_spend 1.0.0 2.0.0  # Compare specific versions
        mlforge diff user_spend 1.0.0        # Compare with latest
        mlforge diff user_spend              # Compare latest with previous

    Exit codes:
        0: No differences (same version)
        1: PATCH differences (data only)
        2: MINOR differences (additive)
        3: MAJOR differences (breaking)
        4: Error

    Args:
        feature_name: Name of the feature to compare
        version1: First version to compare. If not specified, compares latest with previous.
        version2: Second version to compare. If not specified, compares version1 with latest.
        target: Path to definitions file. Defaults to "definitions.py".
        format_: Output format (table, json). Defaults to "table".
        quiet: Quiet mode (exit code only). Defaults to False.
        profile: Profile name from mlforge.yaml. Defaults to None.

    Raises:
        SystemExit: With exit code based on diff result or error
    """
    import mlforge.version as version

    try:
        defs = loader.load_definitions(target, profile=profile)

        # Get store root path - must be LocalStore
        if not isinstance(defs.offline_store, stores.LocalStore):
            log.print_error("diff command requires LocalStore")
            raise SystemExit(4)

        store_root = defs.offline_store.path

        # Resolve versions
        if version1 is None and version2 is None:
            # Compare latest with previous
            latest = defs.offline_store.get_latest_version(feature_name)
            if latest is None:
                log.print_error(
                    f"No versions found for feature '{feature_name}'"
                )
                raise SystemExit(4)

            prev = version.get_previous_version(store_root, feature_name)
            if prev is None:
                log.print_error(
                    f"Only one version exists for '{feature_name}'. "
                    "Need at least 2 versions to compare."
                )
                raise SystemExit(4)

            version_from: str = prev
            version_to: str = latest
        elif version1 is not None and version2 is None:
            # Compare version1 with latest
            latest = defs.offline_store.get_latest_version(feature_name)
            if latest is None:
                log.print_error(
                    f"No versions found for feature '{feature_name}'"
                )
                raise SystemExit(4)
            version_from = version1
            version_to = latest
        elif version1 is not None and version2 is not None:
            # Compare version1 with version2
            version_from = version1
            version_to = version2
        else:
            # version1 is None but version2 is not - invalid
            log.print_error("Cannot specify version2 without version1")
            raise SystemExit(4)

        # Perform diff
        diff_result = version.diff_versions(
            store_root, feature_name, version_from, version_to
        )

        # Output result
        if not quiet:
            if format_ == "json":
                log.print_version_diff_json(diff_result)
            else:
                log.print_version_diff(diff_result)

        # Exit code based on change type
        change_type = diff_result.change_type
        if change_type == version.ChangeType.MAJOR:
            raise SystemExit(3)
        elif change_type == version.ChangeType.MINOR:
            raise SystemExit(2)
        elif change_type == version.ChangeType.PATCH:
            raise SystemExit(1)
        else:
            raise SystemExit(0)

    except errors.VersionNotFoundError as e:
        log.print_error(str(e))
        raise SystemExit(4)
    except (errors.DefinitionsLoadError, errors.ProfileError) as e:
        log.print_error(str(e))
        raise SystemExit(4)


@app.command
def rollback(
    feature_name: Annotated[
        str,
        cyclopts.Parameter(help="Name of the feature to rollback"),
    ],
    version: Annotated[
        str | None,
        cyclopts.Parameter(help="Version to rollback to"),
    ] = None,
    previous: Annotated[
        bool,
        cyclopts.Parameter(
            name="--previous",
            help="Rollback to the version before latest",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        cyclopts.Parameter(
            name="--dry-run",
            help="Show what would happen without making changes",
        ),
    ] = False,
    force: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--force", "-f"],
            help="Skip confirmation prompt",
        ),
    ] = False,
    target: Annotated[
        str | None,
        cyclopts.Parameter(name="--target", help="Path to definitions.py file"),
    ] = None,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name from mlforge.yaml to use for stores.",
        ),
    ] = None,
):
    """
    Rollback a feature to a previous version.

    Updates _latest.json to point to the target version.
    Does NOT delete any version data.

    Examples:
        mlforge rollback user_spend 1.0.0     # Rollback to specific version
        mlforge rollback user_spend --previous  # Rollback to previous version
        mlforge rollback user_spend 1.0.0 --dry-run  # Preview without changes

    Exit codes:
        0: Rollback successful
        1: Version not found
        2: Already at target version
        3: User cancelled
        4: Error

    Args:
        feature_name: Name of the feature to rollback
        version: Version to rollback to
        previous: Rollback to the version before latest. Defaults to False.
        dry_run: Show what would happen without making changes. Defaults to False.
        force: Skip confirmation prompt. Defaults to False.
        target: Path to definitions file. Defaults to "definitions.py".
        profile: Profile name from mlforge.yaml. Defaults to None.

    Raises:
        SystemExit: With exit code based on result
    """
    import mlforge.version as version_mod

    try:
        defs = loader.load_definitions(target, profile=profile)

        # Get store root path - must be LocalStore
        if not isinstance(defs.offline_store, stores.LocalStore):
            log.print_error("rollback command requires LocalStore")
            raise SystemExit(4)

        store_root = defs.offline_store.path

        # Determine target version
        if previous:
            prev = version_mod.get_previous_version(store_root, feature_name)
            if prev is None:
                log.print_error(
                    f"No previous version found for '{feature_name}'. "
                    "Need at least 2 versions to rollback."
                )
                raise SystemExit(1)
            target_version: str = prev
        elif version is None:
            log.print_error("Must specify either a version or --previous flag")
            raise SystemExit(4)
        else:
            target_version = version

        # Get current version for confirmation
        current_version = defs.offline_store.get_latest_version(feature_name)
        if current_version is None:
            log.print_error(f"No versions found for feature '{feature_name}'")
            raise SystemExit(1)

        # Show confirmation unless force or dry_run
        if not force and not dry_run:
            log.print_rollback_confirmation(
                feature_name, current_version, target_version
            )
            log.console.print("")
            response = input("Proceed? [y/N]: ")
            if response.lower() not in ("y", "yes"):
                log.print_info("Rollback cancelled.")
                raise SystemExit(3)

        # Perform rollback
        result = version_mod.rollback_version(
            store_root, feature_name, target_version, dry_run=dry_run
        )

        log.print_rollback_result(result)

        if result.success:
            if not dry_run:
                log.print_success(
                    f"Rolled back {feature_name} to version {target_version}"
                )
            raise SystemExit(0)

    except errors.VersionNotFoundError as e:
        log.print_error(str(e))
        raise SystemExit(1)
    except errors.AlreadyAtVersionError as e:
        log.print_error(str(e))
        raise SystemExit(2)
    except (errors.DefinitionsLoadError, errors.ProfileError) as e:
        log.print_error(str(e))
        raise SystemExit(4)


# =============================================================================
# serve - REST API server
# =============================================================================


@app.command
def serve(
    target: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--target",
            help="Path to definitions.py file",
        ),
    ] = None,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name from mlforge.yaml to use for stores",
        ),
    ] = None,
    host: Annotated[
        str,
        cyclopts.Parameter(
            name="--host",
            help="Host to bind the server to",
        ),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        cyclopts.Parameter(
            name="--port",
            help="Port to bind the server to",
        ),
    ] = 8000,
    workers: Annotated[
        int,
        cyclopts.Parameter(
            name="--workers",
            help="Number of uvicorn workers",
        ),
    ] = 1,
    no_metrics: Annotated[
        bool,
        cyclopts.Parameter(
            name="--no-metrics",
            help="Disable Prometheus metrics endpoint",
        ),
    ] = False,
    no_docs: Annotated[
        bool,
        cyclopts.Parameter(
            name="--no-docs",
            help="Disable OpenAPI documentation at /docs",
        ),
    ] = False,
    cors_origins: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--cors-origins",
            help="Comma-separated list of allowed CORS origins",
        ),
    ] = None,
):
    """
    Start the REST API server for feature serving.

    Launches a FastAPI server that exposes feature retrieval endpoints.
    Features are served from the configured online store.

    Examples:
        mlforge serve --target src/features/definitions.py

        mlforge serve --profile production --port 8080

        mlforge serve --target definitions.py --cors-origins "http://localhost:3000"
    """
    import uvicorn

    from mlforge.serve import create_app

    try:
        defs = loader.load_definitions(target=target, profile=profile)

        if defs.online_store is None:
            log.print_warning(
                "No online store configured. "
                "Feature retrieval endpoints will return 503."
            )

        origins = cors_origins.split(",") if cors_origins else None

        application = create_app(
            definitions=defs,
            enable_metrics=not no_metrics,
            enable_docs=not no_docs,
            cors_origins=origins,
        )

        log.print_info(f"Starting mlforge server on {host}:{port}")
        log.print_info(
            f"OpenAPI docs: {'enabled' if not no_docs else 'disabled'}"
        )
        log.print_info(
            f"Metrics: {'enabled' if not no_metrics else 'disabled'}"
        )

        uvicorn.run(application, host=host, port=port, workers=workers)

    except (errors.DefinitionsLoadError, errors.ProfileError) as e:
        log.print_error(str(e))
        raise SystemExit(1)


# =============================================================================
# log - Log feature metadata to external systems
# =============================================================================

log_app = cyclopts.App(
    name="log", help="Log feature metadata to external systems"
)
app.command(log_app)


@log_app.command
def mlflow(
    features: Annotated[
        str,
        cyclopts.Parameter(
            name="--features",
            help="Comma-separated list of feature names to log",
        ),
    ],
    run_id: Annotated[
        str,
        cyclopts.Parameter(
            name="--run-id",
            help="MLflow run ID to log to",
        ),
    ],
    target: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--definitions",
            help="Path to definitions.py file",
        ),
    ] = None,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--profile",
            help="Profile name from mlforge.yaml to use for stores",
        ),
    ] = None,
    tracking_uri: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--tracking-uri",
            help="MLflow tracking server URI",
        ),
    ] = None,
):
    """
    Log feature metadata to an MLflow run.

    Logs feature versions, schemas, and statistics as parameters, tags,
    metrics, and artifacts to the specified MLflow run.

    Examples:
        mlforge log mlflow --features user_spend,merchant_spend --run-id abc123

        mlforge log mlflow --features user_spend --run-id abc123 \\
            --definitions src/my_project/definitions.py

        mlforge log mlflow --features user_spend --run-id abc123 \\
            --tracking-uri http://mlflow.example.com:5000
    """
    import mlforge.integrations.mlflow as mlflow_integration

    try:
        # Import mlflow and set tracking URI if provided
        mlflow_module = mlflow_integration._require_mlflow()
        if tracking_uri:
            mlflow_module.set_tracking_uri(tracking_uri)

        # Load definitions to get the store
        defs = loader.load_definitions(target=target, profile=profile)

        # Parse feature list
        feature_list = [f.strip() for f in features.split(",")]

        # Log features to MLflow
        mlflow_integration.log_features_to_mlflow(
            features=feature_list,
            store=defs.offline_store,
            run_id=run_id,
        )

        log.print_success(
            f"Logged {len(feature_list)} feature(s) to MLflow run {run_id}"
        )

    except ImportError as e:
        log.print_error(str(e))
        raise SystemExit(1)
    except errors.MlflowError as e:
        log.print_error(str(e))
        raise SystemExit(1)
    except (errors.DefinitionsLoadError, errors.ProfileError) as e:
        log.print_error(str(e))
        raise SystemExit(1)
