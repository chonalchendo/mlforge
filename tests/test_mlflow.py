"""Tests for MLflow integration."""

import json

import mlflow
import polars as pl
import pytest

import mlforge
from mlforge import LocalStore
from mlforge.integrations import mlflow as mlflow_integration
from mlforge.manifest import FeatureMetadata
from mlforge.results import PolarsResult


@pytest.fixture
def mlflow_tracking_uri(temp_dir):
    """Set up MLflow to use a temporary file-based tracking URI."""
    tracking_uri = f"file://{temp_dir}/mlruns"
    mlflow.set_tracking_uri(tracking_uri)
    yield tracking_uri
    # Reset to default after test
    mlflow.set_tracking_uri("")


@pytest.fixture
def sample_store_with_metadata(temp_dir):
    """LocalStore with a feature that has metadata."""
    store = LocalStore(temp_dir / "feature_store")

    # Create sample feature data
    df = pl.DataFrame(
        {
            "user_id": ["alice", "bob", "charlie"],
            "feature_timestamp": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "amount_sum_7d": [100.0, 200.0, 300.0],
            "amount_mean_7d": [10.0, 20.0, 30.0],
        }
    )

    # Write feature
    store.write("user_spend", PolarsResult(df), feature_version="1.2.0")

    # Write metadata
    metadata = FeatureMetadata(
        name="user_spend",
        version="1.2.0",
        path=str(store.path_for("user_spend")),
        entity="user",
        keys=["user_id"],
        source="data/transactions.parquet",
        row_count=3,
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-15T10:30:00Z",
        content_hash="abc123def456",
        schema_hash="xyz789ghi012",
        config_hash="config123456",
        timestamp="feature_timestamp",
        interval="7d",
    )
    store.write_metadata("user_spend", metadata)

    return store


# =============================================================================
# log_features_to_mlflow Tests
# =============================================================================


def test_log_features_to_mlflow_logs_tags(
    mlflow_tracking_uri, sample_store_with_metadata
):
    # Given an active MLflow run
    with mlflow.start_run() as run:
        # When logging features
        mlflow_integration.log_features_to_mlflow(
            features=["user_spend"],
            store=sample_store_with_metadata,
        )

    # Then tags should be logged
    run_data = mlflow.get_run(run.info.run_id)
    assert run_data.data.tags["mlforge.version"] == mlforge.__version__
    assert run_data.data.tags["mlforge.features"] == "user_spend"
    assert run_data.data.tags["mlforge.feature_count"] == "1"


def test_log_features_to_mlflow_logs_params(
    mlflow_tracking_uri, sample_store_with_metadata
):
    # Given an active MLflow run
    with mlflow.start_run() as run:
        # When logging features
        mlflow_integration.log_features_to_mlflow(
            features=["user_spend"],
            store=sample_store_with_metadata,
        )

    # Then params should be logged
    run_data = mlflow.get_run(run.info.run_id)
    params = run_data.data.params
    assert params["mlforge.feature.user_spend.version"] == "1.2.0"
    assert "mlforge.feature.user_spend.schema_hash" in params
    assert params["mlforge.feature.user_spend.row_count"] == "3"


def test_log_features_to_mlflow_logs_metrics(
    mlflow_tracking_uri, sample_store_with_metadata
):
    # Given an active MLflow run
    with mlflow.start_run() as run:
        # When logging features
        mlflow_integration.log_features_to_mlflow(
            features=["user_spend"],
            store=sample_store_with_metadata,
        )

    # Then metrics should be logged
    run_data = mlflow.get_run(run.info.run_id)
    metrics = run_data.data.metrics
    assert metrics["mlforge.user_spend.row_count"] == 3


def test_log_features_to_mlflow_logs_artifacts(
    mlflow_tracking_uri, sample_store_with_metadata
):
    # Given an active MLflow run
    with mlflow.start_run() as run:
        # When logging features
        mlflow_integration.log_features_to_mlflow(
            features=["user_spend"],
            store=sample_store_with_metadata,
        )

    # Then artifacts should be logged
    artifacts = mlflow.artifacts.list_artifacts(
        run_id=run.info.run_id, artifact_path="mlforge"
    )
    artifact_paths = [a.path for a in artifacts]
    assert "mlforge/features.json" in artifact_paths
    assert "mlforge/user_spend.json" in artifact_paths


def test_log_features_to_mlflow_no_active_run_raises_error(
    mlflow_tracking_uri, sample_store_with_metadata
):
    # Given no active MLflow run
    # When/Then logging should raise MlflowError
    from mlforge.errors import MlflowError

    with pytest.raises(MlflowError, match="No active MLflow run"):
        mlflow_integration.log_features_to_mlflow(
            features=["user_spend"],
            store=sample_store_with_metadata,
        )


def test_log_features_to_mlflow_with_run_id(
    mlflow_tracking_uri, sample_store_with_metadata
):
    # Given a completed MLflow run
    with mlflow.start_run() as run:
        pass  # Just create the run

    # When logging features with explicit run_id
    mlflow_integration.log_features_to_mlflow(
        features=["user_spend"],
        store=sample_store_with_metadata,
        run_id=run.info.run_id,
    )

    # Then tags should be logged to that run
    run_data = mlflow.get_run(run.info.run_id)
    assert run_data.data.tags["mlforge.features"] == "user_spend"


def test_log_features_to_mlflow_feature_not_found(
    mlflow_tracking_uri, sample_store_with_metadata
):
    # Given a store with user_spend but not merchant_spend
    from mlforge.errors import MlflowError

    with mlflow.start_run():
        # When/Then logging a non-existent feature should raise error
        with pytest.raises(MlflowError, match="not found in store"):
            mlflow_integration.log_features_to_mlflow(
                features=["merchant_spend"],
                store=sample_store_with_metadata,
            )


def test_log_features_to_mlflow_multiple_features(
    mlflow_tracking_uri, temp_dir
):
    # Given a store with multiple features
    store = LocalStore(temp_dir / "feature_store")

    for name, version in [("user_spend", "1.0.0"), ("merchant_spend", "2.0.0")]:
        df = pl.DataFrame({"id": [1, 2], "value": [10.0, 20.0]})
        store.write(name, PolarsResult(df), feature_version=version)
        metadata = FeatureMetadata(
            name=name,
            version=version,
            path=str(store.path_for(name)),
            entity="test",
            keys=["id"],
            source="data/test.parquet",
            row_count=2,
            updated_at="2024-01-01T00:00:00Z",
            schema_hash="hash123",
            config_hash="config123",
        )
        store.write_metadata(name, metadata)

    # When logging multiple features
    with mlflow.start_run() as run:
        mlflow_integration.log_features_to_mlflow(
            features=["user_spend", "merchant_spend"],
            store=store,
        )

    # Then both features should be logged
    run_data = mlflow.get_run(run.info.run_id)
    assert run_data.data.tags["mlforge.features"] == "user_spend,merchant_spend"
    assert run_data.data.tags["mlforge.feature_count"] == "2"
    assert run_data.data.params["mlforge.feature.user_spend.version"] == "1.0.0"
    assert (
        run_data.data.params["mlforge.feature.merchant_spend.version"]
        == "2.0.0"
    )


# =============================================================================
# autolog Tests
# =============================================================================


def test_autolog_enables_autologging():
    # Given autolog is disabled by default
    assert not mlflow_integration.is_autolog_enabled()

    # When enabling autolog
    mlflow_integration.autolog()

    # Then it should be enabled
    assert mlflow_integration.is_autolog_enabled()

    # Cleanup
    mlflow_integration.autolog(disable=True)


def test_autolog_disable_disables_autologging():
    # Given autolog is enabled
    mlflow_integration.autolog()
    assert mlflow_integration.is_autolog_enabled()

    # When disabling autolog
    mlflow_integration.autolog(disable=True)

    # Then it should be disabled
    assert not mlflow_integration.is_autolog_enabled()


def test_disable_autolog_context_manager():
    # Given autolog is enabled
    mlflow_integration.autolog()
    assert mlflow_integration.is_autolog_enabled()

    # When using disable_autolog context manager
    with mlflow_integration.disable_autolog():
        # Then it should be disabled inside the context
        assert not mlflow_integration.is_autolog_enabled()

    # And re-enabled after the context
    assert mlflow_integration.is_autolog_enabled()

    # Cleanup
    mlflow_integration.autolog(disable=True)


def test_disable_autolog_context_manager_restores_state():
    # Given autolog is disabled
    mlflow_integration.autolog(disable=True)
    assert not mlflow_integration.is_autolog_enabled()

    # When using disable_autolog context manager
    with mlflow_integration.disable_autolog():
        assert not mlflow_integration.is_autolog_enabled()

    # Then it should still be disabled (original state)
    assert not mlflow_integration.is_autolog_enabled()


# =============================================================================
# Artifact Content Tests
# =============================================================================


def test_features_json_artifact_content(
    mlflow_tracking_uri, sample_store_with_metadata, temp_dir
):
    # Given an active MLflow run
    with mlflow.start_run() as run:
        mlflow_integration.log_features_to_mlflow(
            features=["user_spend"],
            store=sample_store_with_metadata,
        )

    # When downloading and reading the features.json artifact
    artifact_path = mlflow.artifacts.download_artifacts(
        run_id=run.info.run_id,
        artifact_path="mlforge/features.json",
    )
    with open(artifact_path) as f:
        content = json.load(f)

    # Then it should contain expected structure
    assert content["mlforge_version"] == mlforge.__version__
    assert "logged_at" in content
    assert len(content["features"]) == 1
    assert content["features"][0]["name"] == "user_spend"
    assert content["features"][0]["version"] == "1.2.0"


def test_feature_json_artifact_content(
    mlflow_tracking_uri, sample_store_with_metadata
):
    # Given an active MLflow run
    with mlflow.start_run() as run:
        mlflow_integration.log_features_to_mlflow(
            features=["user_spend"],
            store=sample_store_with_metadata,
        )

    # When downloading and reading the feature-specific artifact
    artifact_path = mlflow.artifacts.download_artifacts(
        run_id=run.info.run_id,
        artifact_path="mlforge/user_spend.json",
    )
    with open(artifact_path) as f:
        content = json.load(f)

    # Then it should contain full feature metadata
    assert content["name"] == "user_spend"
    assert content["version"] == "1.2.0"
    assert content["keys"] == ["user_id"]
    assert content["row_count"] == 3
