from typing import Annotated

import cyclopts
from loguru import logger

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
        str | None, cyclopts.Parameter(name="--target", help="Path to definitions file")
    ] = None,
    features: Annotated[
        str | None,
        cyclopts.Parameter(name="--features", help="Comma-separated feature names"),
    ] = None,
    force: Annotated[bool, cyclopts.Parameter(["--force", "-f"])] = False,
    no_preview: Annotated[bool, cyclopts.Parameter("--no-preview")] = False,
    preview_rows: Annotated[int, cyclopts.Parameter("--preview-rows")] = 5,
):
    """
    Materialize features to offline storage.

    Loads feature definitions, computes features from source data,
    and persists results to the configured storage backend.

    Args:
        target: Path to definitions file. Defaults to "definitions.py".
        features: Comma-separated list of feature names. Defaults to None (all).
        force: Overwrite existing features. Defaults to False.
        no_preview: Disable feature preview output. Defaults to False.
        preview_rows: Number of preview rows to display. Defaults to 5.

    Raises:
        SystemExit: If loading definitions or materialization fails
    """
    try:
        defs = load_definitions(target)
        feature_names = features.split(",") if features else None

        results = defs.materialize(
            feature_names=feature_names,
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
        str | None, cyclopts.Parameter(help="definitions module:object")
    ] = None,
):
    """
    Display all registered features in a table.

    Loads feature definitions and prints their metadata including
    names, keys, sources, and descriptions.

    Args:
        target: Path to definitions file. Defaults to "definitions.py".
    """
    logger.debug(f"Loading definitions from {target or 'default'}")
    defs = load_definitions(target)
    print_features_table(defs.features)
