from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import polars as pl
import rich.console as console_
import rich.table as table_
from loguru import logger

if TYPE_CHECKING:
    from pathlib import Path

    from mlforge.core import Feature
    from mlforge.manifest import FeatureMetadata
    from mlforge.validation import FeatureValidationResult


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

    def formatter(record):
        # Build location string and pad to fixed width for aligned messages
        location = f"{record['name']}:{record['function']}:{record['line']}"
        record["extra"]["location"] = f"{location: <45}"
        return (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | <level>{level: <8}</level> | "
            "{extra[location]} - {message}\n"
        )

    logger.add(
        sys.stderr,
        format=formatter,
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


def print_build_results(results: dict[str, Path | str]) -> None:
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


def print_warning(message: str) -> None:
    """
    Print a warning message with warning symbol.

    Args:
        message: Warning message to display
    """
    console.print(f"[yellow]![/yellow] {message}")


def print_feature_metadata(feature_name: str, metadata: "FeatureMetadata") -> None:
    """
    Display detailed feature metadata in a formatted layout.

    Shows feature configuration, storage details, and column information.

    Args:
        feature_name: Name of the feature
        metadata: FeatureMetadata object with all details
    """
    from rich.panel import Panel

    # Build info lines
    info_lines = []
    if metadata.description:
        info_lines.append(f"[italic]{metadata.description}[/italic]\n")

    info_lines.extend(
        [
            f"[bold]Path:[/bold] {metadata.path}",
            f"[bold]Source:[/bold] {metadata.source}",
            f"[bold]Entity:[/bold] {metadata.entity}",
            f"[bold]Keys:[/bold] {', '.join(metadata.keys)}",
            f"[bold]Timestamp:[/bold] {metadata.timestamp or '-'}",
            f"[bold]Interval:[/bold] {metadata.interval or '-'}",
            f"[bold]Tags:[/bold] {', '.join(metadata.tags) if metadata.tags else '-'}",
            f"[bold]Row Count:[/bold] {metadata.row_count:,}",
            f"[bold]Last Updated:[/bold] {metadata.last_updated}",
        ]
    )

    console.print(Panel("\n".join(info_lines), title=f"Feature: {feature_name}"))

    # Display columns table if available
    if metadata.columns:
        table = table_.Table(title="Columns")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="dim")
        table.add_column("Input", style="green")
        table.add_column("Aggregation")
        table.add_column("Window")

        for col in metadata.columns:
            table.add_row(
                col.name,
                col.dtype or "-",
                col.input or "-",
                col.agg or "-",
                col.window or "-",
            )

        console.print(table)


def print_manifest_summary(metadata_list: list["FeatureMetadata"]) -> None:
    """
    Display a summary of all feature metadata.

    Shows a table with key information about each feature in the store.

    Args:
        metadata_list: List of FeatureMetadata objects
    """
    table = table_.Table(title="Feature Store Manifest")
    table.add_column("Feature", style="cyan")
    table.add_column("Entity", style="green")
    table.add_column("Rows", justify="right")
    table.add_column("Columns", justify="right")
    table.add_column("Last Updated", style="dim")

    for meta in sorted(metadata_list, key=lambda m: m.name):
        table.add_row(
            meta.name,
            meta.entity,
            f"{meta.row_count:,}",
            str(len(meta.columns)),
            meta.last_updated[:19] if meta.last_updated else "-",
        )

    console.print(table)
    console.print(f"\n[dim]{len(metadata_list)} features total[/dim]")


def print_validation_results(results: list["FeatureValidationResult"]) -> None:
    """
    Display validation results for all features.

    Shows a summary table with pass/fail status for each feature,
    followed by detailed failure information.

    Args:
        results: List of FeatureValidationResult objects
    """
    # Summary table
    table = table_.Table(title="Validation Results")
    table.add_column("Feature", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Checks", justify="right")
    table.add_column("Failures", justify="right")

    for result in sorted(results, key=lambda r: r.feature_name):
        status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
        table.add_row(
            result.feature_name,
            status,
            str(len(result.column_results)),
            str(result.failure_count),
        )

    console.print(table)

    # Detailed failures
    failed_results = [r for r in results if not r.passed]
    if failed_results:
        console.print("\n[bold red]Validation Failures:[/bold red]")
        for result in failed_results:
            console.print(f"\n  [cyan]{result.feature_name}[/cyan]:")
            for failure in result.failures:
                console.print(
                    f"    [dim]•[/dim] Column '[yellow]{failure.column}[/yellow]' "
                    f"({failure.validator_name}): {failure.result.message}"
                )


def print_validation_summary(passed: int, failed: int, skipped: int) -> None:
    """
    Display a summary of validation results.

    Args:
        passed: Number of features that passed validation
        failed: Number of features that failed validation
        skipped: Number of features skipped (no validators)
    """
    total = passed + failed + skipped
    parts = []

    if passed > 0:
        parts.append(f"[green]{passed} passed[/green]")
    if failed > 0:
        parts.append(f"[red]{failed} failed[/red]")
    if skipped > 0:
        parts.append(f"[dim]{skipped} skipped[/dim]")

    summary = ", ".join(parts)
    console.print(f"\nValidation: {summary} ({total} total)")
