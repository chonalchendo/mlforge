"""
MLflow integration for logging feature metadata to ML experiments.

Enables tracking which feature versions were used to train a model,
improving reproducibility and lineage.

Example:
    import mlforge as mlf
    import mlflow

    with mlflow.start_run():
        # Get training data
        training_data = defs.get_training_data(
            features=["user_spend", "merchant_spend"],
            entity_df=labels,
        )

        # Log feature metadata to MLflow
        mlf.log_features_to_mlflow(
            features=["user_spend", "merchant_spend"],
            store=defs.offline_store,
        )

        # Train model...
        model.fit(training_data)
"""

from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import mlforge
import mlforge.errors as errors

if TYPE_CHECKING:
    import mlforge.stores as stores

# Global state for auto-logging
_autolog_enabled = False


def _require_mlflow() -> Any:
    """
    Import mlflow with helpful error message if not installed.

    Returns:
        The mlflow module

    Raises:
        ImportError: If mlflow is not installed
    """
    try:
        import mlflow

        return mlflow
    except ImportError as e:
        raise ImportError(
            "mlflow is required for MLflow integration. "
            "Install it with: pip install mlforge[mlflow]"
        ) from e


def autolog(disable: bool = False) -> None:
    """
    Enable or disable MLflow auto-logging.

    When enabled, get_training_data() automatically logs feature metadata
    to the active MLflow run.

    Args:
        disable: If True, disable auto-logging. Defaults to False.

    Example:
        import mlforge as mlf

        # Enable auto-logging
        mlf.mlflow.autolog()

        # Disable auto-logging
        mlf.mlflow.autolog(disable=True)
    """
    global _autolog_enabled
    _autolog_enabled = not disable


def is_autolog_enabled() -> bool:
    """
    Check if auto-logging is enabled.

    Returns:
        True if auto-logging is enabled, False otherwise
    """
    return _autolog_enabled


@contextmanager
def disable_autolog():
    """
    Context manager to temporarily disable auto-logging.

    Useful when you want to call get_training_data() without logging
    to MLflow, even when auto-logging is globally enabled.

    Example:
        import mlforge as mlf

        mlf.mlflow.autolog()  # Enable globally

        with mlf.mlflow.disable_autolog():
            # This won't log to MLflow
            data = defs.get_training_data(...)

        # This will log to MLflow
        data = defs.get_training_data(...)

    Yields:
        None
    """
    global _autolog_enabled
    previous_state = _autolog_enabled
    _autolog_enabled = False
    try:
        yield
    finally:
        _autolog_enabled = previous_state


def log_features_to_mlflow(
    features: list[str],
    store: stores.Store,
    run_id: str | None = None,
) -> None:
    """
    Log feature metadata to MLflow.

    Logs feature versions, schemas, and statistics to an MLflow run
    as parameters, tags, metrics, and artifacts.

    Args:
        features: List of feature names to log.
        store: Offline store containing the features.
        run_id: MLflow run ID. If None, uses the active run.

    Raises:
        MlflowError: If no active run and run_id not provided.

    Example:
        import mlflow
        import mlforge as mlf

        with mlflow.start_run():
            mlf.log_features_to_mlflow(
                features=["user_spend", "merchant_spend"],
                store=defs.offline_store,
            )
    """
    mlflow = _require_mlflow()

    # Get the run to log to
    if run_id:
        # Verify the run exists
        try:
            mlflow.get_run(run_id)
        except Exception as e:
            raise errors.MlflowError(
                f"Run '{run_id}' not found.",
                hint="Verify the run ID is correct and the tracking URI is set.",
            ) from e
        target_run_id = run_id
    else:
        active_run = mlflow.active_run()
        if active_run is None:
            raise errors.MlflowError(
                "No active MLflow run found.",
                hint=(
                    "Start a run with mlflow.start_run() or provide a run_id.\n\n"
                    "    import mlflow\n\n"
                    "    with mlflow.start_run():\n"
                    "        mlf.log_features_to_mlflow(...)"
                ),
            )
        target_run_id = active_run.info.run_id

    # Collect metadata for all features
    feature_metadata_list = []
    for feature_name in features:
        metadata = store.read_metadata(feature_name)
        if metadata is None:
            raise errors.MlflowError(
                f"Feature '{feature_name}' not found in store.",
                hint=f"Run 'mlforge build' to materialize '{feature_name}' first.",
            )
        feature_metadata_list.append(metadata)

    # Log to MLflow - use active run directly or resume specified run
    active_run = mlflow.active_run()
    if active_run and active_run.info.run_id == target_run_id:
        # Already in the target run, log directly
        _log_tags(mlflow, features)
        _log_params(mlflow, feature_metadata_list)
        _log_metrics(mlflow, feature_metadata_list)
        _log_artifacts(mlflow, feature_metadata_list)
    else:
        # Need to start/resume a run
        with mlflow.start_run(run_id=target_run_id):
            _log_tags(mlflow, features)
            _log_params(mlflow, feature_metadata_list)
            _log_metrics(mlflow, feature_metadata_list)
            _log_artifacts(mlflow, feature_metadata_list)


def _log_tags(mlflow: Any, features: list[str]) -> None:
    """Log mlforge tags to the active MLflow run."""
    mlflow.set_tag("mlforge.version", mlforge.__version__)
    mlflow.set_tag("mlforge.features", ",".join(features))
    mlflow.set_tag("mlforge.feature_count", str(len(features)))


def _log_params(mlflow: Any, metadata_list: list[Any]) -> None:
    """Log feature parameters to the active MLflow run."""
    for metadata in metadata_list:
        prefix = f"mlforge.feature.{metadata.name}"
        mlflow.log_param(f"{prefix}.version", metadata.version)
        mlflow.log_param(f"{prefix}.schema_hash", metadata.schema_hash[:12])
        mlflow.log_param(f"{prefix}.row_count", metadata.row_count)


def _log_metrics(mlflow: Any, metadata_list: list[Any]) -> None:
    """Log feature metrics to the active MLflow run."""
    for metadata in metadata_list:
        prefix = f"mlforge.{metadata.name}"
        mlflow.log_metric(f"{prefix}.row_count", metadata.row_count)
        # Column count = base columns + feature columns
        column_count = len(metadata.columns) + len(metadata.features)
        mlflow.log_metric(f"{prefix}.column_count", column_count)


def _log_artifacts(mlflow: Any, metadata_list: list[Any]) -> None:
    """Log feature metadata as JSON artifacts to the active MLflow run."""
    logged_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Build features summary
    features_summary: dict[str, Any] = {
        "mlforge_version": mlforge.__version__,
        "logged_at": logged_at,
        "features": [],
    }

    for metadata in metadata_list:
        features_summary["features"].append(
            {
                "name": metadata.name,
                "version": metadata.version,
                "schema_hash": metadata.schema_hash,
                "config_hash": metadata.config_hash,
                "row_count": metadata.row_count,
            }
        )

    # Write artifacts to temp directory and log
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write features.json summary
        features_path = tmpdir_path / "features.json"
        features_path.write_text(json.dumps(features_summary, indent=2))
        mlflow.log_artifact(str(features_path), "mlforge")

        # Write individual feature metadata files
        for metadata in metadata_list:
            feature_path = tmpdir_path / f"{metadata.name}.json"
            feature_path.write_text(json.dumps(metadata.to_dict(), indent=2))
            mlflow.log_artifact(str(feature_path), "mlforge")
