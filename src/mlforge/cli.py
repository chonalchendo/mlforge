from typing import Annotated

import cyclopts

import mlforge.errors as errors
import mlforge.loader as loader
import mlforge.logging as log

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
            name="--target", help="Path to definitions.py file. Automatically handled."
        ),
    ] = None,
    features: Annotated[
        str | None,
        cyclopts.Parameter(name="--features", help="Comma-separated feature names"),
    ] = None,
    tags: Annotated[
        str | None,
        cyclopts.Parameter(name="--tags", help="Comma-separated feature tags"),
    ] = None,
    force: Annotated[
        bool,
        cyclopts.Parameter(name=["--force", "-f"], help="Overwrite existing features."),
    ] = False,
    no_preview: Annotated[
        bool,
        cyclopts.Parameter(name="--no-preview", help="Disable feature preview output"),
    ] = False,
    preview_rows: Annotated[
        int,
        cyclopts.Parameter(
            name="--preview-rows",
            help="Number of preview rows to display. Defaults to 5.",
        ),
    ] = 5,
):
    """
    Materialize features to offline storage.

    Loads feature definitions, computes features from source data,
    and persists results to the configured storage backend.

    Args:
        target: Path to definitions file. Defaults to "definitions.py".
        features: Comma-separated list of feature names. Defaults to None (all).
        tags: Comma-separated list of feature tags. Defualts to None.
        force: Overwrite existing features. Defaults to False.
        no_preview: Disable feature preview output. Defaults to False.
        preview_rows: Number of preview rows to display. Defaults to 5.

    Raises:
        SystemExit: If loading definitions or materialization fails
    """
    if tags and features:
        raise ValueError(
            "Tags and features cannot be specified at the same time. Choose one or the other."
        )

    try:
        defs = loader.load_definitions(target)
        feature_names = [f.strip() for f in features.split(",")] if features else None
        tag_names = [t.strip() for t in tags.split(",")] if tags else None

        results = defs.build(
            feature_names=feature_names,
            tag_names=tag_names,
            force=force,
            preview=not no_preview,
            preview_rows=preview_rows,
        )

        log.print_build_results(results)
        log.print_success(f"Built {len(results)} features")

    except (errors.DefinitionsLoadError, errors.FeatureMaterializationError) as e:
        log.print_error(str(e))
        raise SystemExit(1)


@app.command
def validate(
    target: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--target", help="Path to definitions.py file. Automatically handled."
        ),
    ] = None,
    features: Annotated[
        str | None,
        cyclopts.Parameter(name="--features", help="Comma-separated feature names"),
    ] = None,
    tags: Annotated[
        str | None,
        cyclopts.Parameter(name="--tags", help="Comma-separated feature tags"),
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

    Raises:
        SystemExit: If loading definitions fails or any validation fails
    """
    if tags and features:
        raise ValueError(
            "Tags and features cannot be specified at the same time. Choose one or the other."
        )

    try:
        defs = loader.load_definitions(target)
        feature_names = [f.strip() for f in features.split(",")] if features else None
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

    except errors.DefinitionsLoadError as e:
        log.print_error(str(e))
        raise SystemExit(1)


@app.command
def list_(
    target: Annotated[
        str | None,
        cyclopts.Parameter(help="Path to definitions.py file - automatically handled."),
    ] = None,
    tags: Annotated[
        str | None, cyclopts.Parameter(help="Comma-separated list of feature tags.")
    ] = None,
):
    """
    Display all registered features in a table.

    Loads feature definitions and prints their metadata including
    names, keys, sources, and descriptions.
    """

    defs = loader.load_definitions(target)
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
):
    """
    Display detailed metadata for a specific feature.

    Shows feature configuration, storage details, column information,
    and last build timestamp from the feature's metadata file.

    Args:
        feature_name: Name of the feature to inspect
        target: Path to definitions file. Defaults to "definitions.py".

    Raises:
        SystemExit: If feature metadata is not found
    """
    try:
        defs = loader.load_definitions(target)
        metadata = defs.offline_store.read_metadata(feature_name)

        if not metadata:
            log.print_error(
                f"No metadata found for feature '{feature_name}'. "
                "Run 'mlforge build' to generate metadata."
            )
            raise SystemExit(1)

        log.print_feature_metadata(feature_name, metadata)

    except errors.DefinitionsLoadError as e:
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
):
    """
    Display or regenerate the feature manifest.

    Without --regenerate, shows a summary of all feature metadata.
    With --regenerate, rebuilds manifest.json from individual .meta.json files.

    Args:
        target: Path to definitions file. Defaults to "definitions.py".
        regenerate: Rebuild manifest from metadata files. Defaults to False.

    Raises:
        SystemExit: If loading definitions fails
    """
    try:
        defs = loader.load_definitions(target)
        metadata_list = defs.offline_store.list_metadata()

        if not metadata_list:
            log.print_warning("No feature metadata found. Run 'mlforge build' first.")
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

    except errors.DefinitionsLoadError as e:
        log.print_error(str(e))
        raise SystemExit(1)
