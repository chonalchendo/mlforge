import sys
from typing import TYPE_CHECKING

import polars as pl
import rich.console as console_
import rich.table as table_
from loguru import logger

if TYPE_CHECKING:
    from pathlib import Path

    from mlforge.core import Feature


console = console_.Console()


def setup_logging(verbose: bool = False) -> None:
    """
    Configure loguru logging for CLI.

    Sets up colored stderr output with configurable verbosity.
    Should be called once at CLI entry point.

    Args:
        verbose: Enable DEBUG level logging. Defaults to False (INFO level).
    """
    logger.remove()  # remove default handler

    level = "DEBUG" if verbose else "INFO"

    logger.add(
        sys.stderr,
        format="<level>{level: <8}</level> | {message}",
        level=level,
        colorize=True,
    )


def print_features_table(features: dict[str, "Feature"]) -> None:
    """
    Display features in a formatted table.

    Args:
        features: Dictionary mapping feature names to Feature objects
    """
    table = table_.Table(title="Features")
    table.add_column("Name", style="cyan")
    table.add_column("Keys", style="green")
    table.add_column("Source", style="dim")
    table.add_column(header="Tags", style="magenta")
    table.add_column("Description")

    for name, feature in features.items():
        table.add_row(
            name,
            ", ".join(feature.keys),
            str(feature.source),
            ", ".join(feature.tags) if feature.tags else "-",
            feature.description or "-",
        )

    console.print(table)


def print_build_results(results: dict[str, "Path"]) -> None:
    """
    Display materialization results in a formatted table.

    Args:
        results: Dictionary mapping feature names to their storage paths
    """
    table = table_.Table(title="Materialized Features")
    table.add_column("Feature", style="cyan")
    table.add_column("Path", style="green")

    for name, path in results.items():
        table.add_row(name, str(path))

    console.print(table)


def print_success(message: str) -> None:
    """
    Print a success message with checkmark.

    Args:
        message: Success message to display
    """
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """
    Print an error message with X mark.

    Args:
        message: Error message to display
    """
    console.print(f"[red]✗[/red] {message}")


def print_feature_preview(
    feature_name: str, df: pl.DataFrame, max_rows: int = 5
) -> None:
    """
    Display a preview of materialized feature data.

    Shows first N rows in a formatted table along with total row count.

    Args:
        feature_name: Name of the feature being previewed
        df: Feature DataFrame to preview
        max_rows: Number of rows to display. Defaults to 5.
    """
    table = table_.Table(title=f"Preview: {feature_name}", title_style="cyan")

    # Add columns
    for col_name in df.columns:
        table.add_column(col_name, style="dim")

    # Add rows
    for row in df.head(max_rows).iter_rows():
        table.add_row(*[str(v) for v in row])

    # Add row count footer
    console.print(table)
    console.print(f"[dim]{len(df):,} rows total[/dim]\n")
