from typing import Annotated

import cyclopts
from loguru import logger

from mlforge.discovery import find_definitions_file
from mlforge.errors import DefinitionsLoadError, FeatureMaterializationError
from mlforge.loader import load_definitions
from mlforge.logging import (
    print_build_results,
    print_error,
    print_features_table,
    print_success,
    setup_logging,
)

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
    setup_logging(verbose=verbose)
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

    if target is None:
        discovered = find_definitions_file()
        if discovered is None:
            print_error("Could not find definitions.py. Specify --target explicitly.")
            raise SystemExit(1)
        target = str(discovered)
        logger.debug(f"Auto-discovered definitions file: {target}")

    try:
        defs = load_definitions(target)
        feature_names = [f.strip() for f in features.split(",")] if features else None
        tag_names = [t.strip() for t in tags.split(",")] if tags else None

        results = defs.materialize(
            feature_names=feature_names,
            tag_names=tag_names,
            force=force,
            preview=not no_preview,
            preview_rows=preview_rows,
        )

        print_build_results(results)
        print_success(f"Built {len(results)} features")

    except (DefinitionsLoadError, FeatureMaterializationError) as e:
        print_error(str(e))
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
    if target is None:
        discovered = find_definitions_file()
        if discovered is None:
            print_error("Could not find definitions.py. Specify --target explicitly.")
            raise SystemExit(1)
        target = str(discovered)
        logger.debug(f"Auto-discovered definitions file: {target}")

    defs = load_definitions(target)
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

    print_features_table(features)
