from pathlib import Path
from typing import Annotated

import cyclopts

import mlforge.errors as errors
import mlforge.loader as loader
import mlforge.logging as log
import mlforge.profiles as profiles_
import mlforge.store as store_

app = cyclopts.App(name="mlforge", help="A simple feature store SDK")


@app.meta.default
def launcher(
    *tokens: str,
    verbose: Annotated[
        bool, cyclopts.Parameter(name=["--verbose", "-v"], help="Debug logging")
    ] = False,
) -> None:
    """
    CLI entry point that configures logging and dispatches commands.

    Args:
        *tokens: Command tokens to execute
        verbose: Enable debug logging. Defaults to False.
    """
    log.setup_logging(verbose=verbose)
    app(tokens)


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
    no_preview: Annotated[
        bool,
        cyclopts.Parameter(
            name="--no-preview", help="Disable feature preview output"
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
):
    """
    Materialize features to offline storage with versioning.

    Loads feature definitions, computes features from source data,
    and persists results to the configured storage backend. Automatically
    determines version based on schema and configuration changes.

    With --online flag, writes to the online store (e.g., Redis) instead
    of the offline store. Extracts the latest value per entity for
    real-time feature serving.

    Args:
        target: Path to definitions file. Defaults to "definitions.py".
        features: Comma-separated list of feature names. Defaults to None (all).
        tags: Comma-separated list of feature tags. Defaults to None.
        version: Explicit version override. If not specified, auto-detects.
        force: Overwrite existing features. Defaults to False.
        no_preview: Disable feature preview output. Defaults to False.
        preview_rows: Number of preview rows to display. Defaults to 5.
        online: Write to online store instead of offline. Defaults to False.
        profile: Profile name from mlforge.yaml. Defaults to None (uses env var or config default).

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

        results = defs.build(
            feature_names=feature_names,
            tag_names=tag_names,
            feature_version=version,
            force=force,
            preview=not no_preview,
            preview_rows=preview_rows,
            online=online,
        )

        if online:
            # Online build returns int counts
            total_records = sum(
                int(v) if isinstance(v, int) else 0 for v in results.values()
            )
            log.print_success(
                f"Wrote {total_records} records to online store "
                f"({len(results)} features)"
            )
        else:
            # Offline build returns paths - convert to dict[str, Path | str]
            offline_results: dict[str, Path | str] = {
                k: v if isinstance(v, (Path, str)) else str(v)
                for k, v in results.items()
            }
            log.print_build_results(offline_results)
            log.print_success(f"Built {len(results)} features")

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


@app.command
def list_(
    target: Annotated[
        str | None,
        cyclopts.Parameter(
            help="Path to definitions.py file - automatically handled."
        ),
    ] = None,
    tags: Annotated[
        str | None,
        cyclopts.Parameter(help="Comma-separated list of feature tags."),
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
    Display all registered features in a table.

    Loads feature definitions and prints their metadata including
    names, keys, sources, and descriptions.
    """
    try:
        defs = loader.load_definitions(target, profile=profile)
    except (errors.DefinitionsLoadError, errors.ProfileError) as e:
        log.print_error(str(e))
        raise SystemExit(1)
    features = defs.features

    if tags:
        tag_set = {t.strip() for t in tags.split(",")}
        features = {
            name: feature
            for name, feature in features.items()
            if feature.tags and tag_set.intersection(feature.tags)
        }

        if not features:
            raise ValueError(f"Unknown tags: {tags}")

    log.print_features_table(features)


@app.command
def inspect(
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
    Display detailed metadata for a specific feature version.

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


@app.command
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
        if not isinstance(defs.offline_store, store_.LocalStore):
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
