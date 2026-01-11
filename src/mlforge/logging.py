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
    from mlforge.entities import Entity
    from mlforge.manifest import FeatureMetadata
    from mlforge.sources.base import Source
    from mlforge.validation import FeatureValidationResult
    from mlforge.version import RollbackResult, VersionDiff


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
            feature.source_path,
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


def print_info(message: str) -> None:
    """
    Print an info message with info symbol.

    Args:
        message: Info message to display
    """
    console.print(f"[blue]i[/blue] {message}")


def print_feature_metadata(
    feature_name: str, metadata: "FeatureMetadata"
) -> None:
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
            f"[bold]Version:[/bold] {metadata.version}",
            f"[bold]Path:[/bold] {metadata.path}",
            f"[bold]Source:[/bold] {metadata.source}",
            f"[bold]Entity:[/bold] {metadata.entity}",
            f"[bold]Keys:[/bold] {', '.join(metadata.keys)}",
            f"[bold]Timestamp:[/bold] {metadata.timestamp or '-'}",
            f"[bold]Interval:[/bold] {metadata.interval or '-'}",
            f"[bold]Tags:[/bold] {', '.join(metadata.tags) if metadata.tags else '-'}",
            f"[bold]Row Count:[/bold] {metadata.row_count:,}",
            f"[bold]Created:[/bold] {metadata.created_at[:19] if metadata.created_at else '-'}",
            f"[bold]Updated:[/bold] {metadata.updated_at[:19] if metadata.updated_at else '-'}",
        ]
    )

    # Add hash info if available
    if metadata.schema_hash or metadata.config_hash or metadata.content_hash:
        info_lines.append("")
        info_lines.append("[bold]Hashes:[/bold]")
        if metadata.schema_hash:
            info_lines.append(f"  Schema: {metadata.schema_hash}")
        if metadata.config_hash:
            info_lines.append(f"  Config: {metadata.config_hash}")
        if metadata.content_hash:
            info_lines.append(f"  Content: {metadata.content_hash}")

    # Add change summary if available
    if metadata.change_summary:
        info_lines.append("")
        info_lines.append("[bold]Change Summary:[/bold]")
        info_lines.append(
            f"  Type: {metadata.change_summary.get('bump_type', '-')}"
        )
        info_lines.append(
            f"  Reason: {metadata.change_summary.get('reason', '-')}"
        )
        details = metadata.change_summary.get("details", [])
        if details:
            info_lines.append(f"  Details: {', '.join(details)}")

    console.print(
        Panel("\n".join(info_lines), title=f"Feature: {feature_name}")
    )

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
    table.add_column("Version", style="magenta")
    table.add_column("Entity", style="green")
    table.add_column("Rows", justify="right")
    table.add_column("Columns", justify="right")
    table.add_column("Updated", style="dim")

    for meta in sorted(metadata_list, key=lambda m: m.name):
        table.add_row(
            meta.name,
            meta.version,
            meta.entity,
            f"{meta.row_count:,}",
            str(len(meta.columns)),
            meta.updated_at[:19] if meta.updated_at else "-",
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


def print_versions_table(
    feature_name: str,
    versions: list[str],
    latest: str | None,
) -> None:
    """
    Display all versions of a feature in a formatted table.

    Args:
        feature_name: Name of the feature
        versions: List of version strings (sorted oldest to newest)
        latest: The current latest version (marked with indicator)
    """
    table = table_.Table(title=f"Versions: {feature_name}")
    table.add_column("Version", style="cyan")
    table.add_column("Status", justify="center")

    for ver in versions:
        if ver == latest:
            status = "[green]latest[/green]"
        else:
            status = ""
        table.add_row(ver, status)

    console.print(table)
    console.print(f"\n[dim]{len(versions)} version(s) total[/dim]")


def print_entities_table(entities: dict[str, "Entity | None"]) -> None:
    """
    Display entities in a formatted table.

    Args:
        entities: Dictionary mapping entity names to Entity objects
    """
    table = table_.Table(title="Entities")
    table.add_column("Name", style="cyan")
    table.add_column("Join Key", style="green")
    table.add_column("From Columns", style="dim")

    for name, entity in entities.items():
        if entity is None:
            table.add_row(name, "-", "-")
            continue
        join_key = ", ".join(entity.key_columns)
        from_cols = (
            ", ".join(entity.from_columns) if entity.from_columns else "-"
        )
        table.add_row(name, join_key, from_cols)

    console.print(table)
    console.print(f"\n[dim]{len(entities)} entities found[/dim]")


def print_sources_table(sources: dict[str, "Source | None"]) -> None:
    """
    Display sources in a formatted table.

    Args:
        sources: Dictionary mapping source names to Source objects
    """
    table = table_.Table(title="Sources")
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="dim")
    table.add_column("Format", style="green")
    table.add_column("Location", style="magenta")

    for name, source in sources.items():
        if source is None:
            table.add_row(name, "-", "-", "-")
            continue
        fmt = (
            type(source.format).__name__.replace("Format", "").lower()
            if source.format
            else "-"
        )
        table.add_row(name, source.path, fmt, source.location)

    console.print(table)
    console.print(f"\n[dim]{len(sources)} sources found[/dim]")


def print_entity_detail(entity: "Entity", used_in: list[str]) -> None:
    """
    Display detailed entity information.

    Args:
        entity: Entity object to display
        used_in: List of feature names using this entity
    """
    table = table_.Table(title=f"Entity: {entity.name}")
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    join_key = ", ".join(entity.key_columns)
    from_cols = ", ".join(entity.from_columns) if entity.from_columns else "-"

    table.add_row("Name", entity.name)
    table.add_row("Join Key", join_key)
    table.add_row("From Columns", from_cols)
    table.add_row("Used In", ", ".join(used_in) if used_in else "-")

    console.print(table)


def print_source_detail(source: "Source", used_in: list[str]) -> None:
    """
    Display detailed source information.

    Args:
        source: Source object to display
        used_in: List of feature names using this source
    """
    table = table_.Table(title=f"Source: {source.name}")
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    fmt = (
        type(source.format).__name__.replace("Format", "").lower()
        if source.format
        else "-"
    )

    table.add_row("Name", source.name)
    table.add_row("Path", source.path)
    table.add_row("Format", fmt)
    table.add_row("Location", source.location)
    table.add_row("Used In", ", ".join(used_in) if used_in else "-")

    console.print(table)


def print_version_diff(diff: "VersionDiff") -> None:
    """
    Display version diff in a formatted layout.

    Shows schema changes, config changes, and data statistics between
    two versions of a feature.

    Args:
        diff: VersionDiff object containing the comparison results
    """
    # Header
    console.print(
        f"\nComparing [cyan]{diff.feature}[/cyan]: "
        f"[magenta]{diff.version_from}[/magenta] -> "
        f"[magenta]{diff.version_to}[/magenta]\n"
    )

    # Change type with color
    change_type = diff.change_type.value.upper()
    if change_type == "MAJOR":
        change_style = "[red]MAJOR[/red] (breaking change)"
    elif change_type == "MINOR":
        change_style = "[yellow]MINOR[/yellow] (additive change)"
    else:
        change_style = "[green]PATCH[/green] (data refresh)"

    console.print(f"Change Type: {change_style}\n")

    # Schema changes table
    if diff.schema_changes.has_changes():
        table = table_.Table(title="Schema Changes")
        table.add_column("Column", style="cyan")
        table.add_column(f"v{diff.version_from}", style="dim")
        table.add_column(f"v{diff.version_to}", style="dim")
        table.add_column("Change", justify="center")

        for col in diff.schema_changes.removed:
            table.add_row(col.name, col.dtype, "-", "[red]REMOVED[/red]")

        for col in diff.schema_changes.added:
            table.add_row(col.name, "-", col.dtype, "[green]ADDED[/green]")

        for col in diff.schema_changes.modified:
            table.add_row(
                col.name,
                col.dtype_from,
                col.dtype_to,
                "[yellow]MODIFIED[/yellow]",
            )

        console.print(table)
    else:
        console.print("[dim]Schema Changes: None[/dim]")

    # Config changes
    if diff.config_changes:
        console.print("\n[bold]Config Changes:[/bold]")
        for change in diff.config_changes:
            console.print(
                f"  {change.key}: [dim]{change.value_from}[/dim] -> "
                f"[dim]{change.value_to}[/dim]"
            )
    else:
        console.print("\n[dim]Config Changes: None[/dim]")

    # Data statistics
    if diff.data_statistics:
        stats = diff.data_statistics
        console.print("\n[bold]Data Statistics:[/bold]")

        # Row count with percentage change
        pct = stats.row_count_change_pct()
        if pct is not None and pct != 0:
            pct_str = f" ({pct:+.1f}%)"
            if pct > 0:
                pct_str = f"[green]{pct_str}[/green]"
            else:
                pct_str = f"[red]{pct_str}[/red]"
        else:
            pct_str = ""

        console.print(
            f"  Row count: {stats.row_count_from:,} -> "
            f"{stats.row_count_to:,}{pct_str}"
        )


def print_version_diff_json(diff: "VersionDiff") -> None:
    """
    Display version diff as JSON.

    Args:
        diff: VersionDiff object containing the comparison results
    """
    import json

    console.print(json.dumps(diff.to_dict(), indent=2))


def print_rollback_result(result: "RollbackResult") -> None:
    """
    Display rollback result.

    Args:
        result: RollbackResult object with rollback details
    """
    if result.dry_run:
        console.print("\n[bold]Rollback preview[/bold] (dry run)\n")
    else:
        console.print("\n[bold]Rollback complete[/bold]\n")

    console.print(f"Feature: [cyan]{result.feature}[/cyan]")
    console.print(
        f"Version: [dim]{result.version_from}[/dim] -> "
        f"[magenta]{result.version_to}[/magenta]"
    )

    if result.dry_run:
        console.print("\n[dim]No changes made (dry run).[/dim]")
    else:
        console.print(
            f"\nTo undo: [dim]mlforge rollback {result.feature} "
            f"{result.version_from}[/dim]"
        )


def print_rollback_confirmation(
    feature: str,
    current_version: str,
    target_version: str,
) -> None:
    """
    Display rollback confirmation prompt info.

    Args:
        feature: Feature name
        current_version: Current version
        target_version: Target version to rollback to
    """
    console.print(
        f"\nRolling back [cyan]{feature}[/cyan] to version {target_version}\n"
    )
    console.print(f"  Current version: [dim]{current_version}[/dim]")
    console.print(f"  Target version:  [magenta]{target_version}[/magenta]")
    console.print("\nThis will:")
    console.print(f"  - Update _latest.json to point to {target_version}")
    console.print(f"  - NOT delete version {current_version} (data preserved)")
    console.print("  - NOT rebuild the feature")
