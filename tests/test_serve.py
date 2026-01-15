"""Tests for REST API serving module."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import mlforge
from mlforge.core import Definitions, Feature
from mlforge.online import OnlineStore
from mlforge.serve import create_app


class MockOnlineStore(OnlineStore):
    """Mock online store for testing."""

    def __init__(
        self, data: dict[str, dict[str, dict[str, Any]]] | None = None
    ):
        """Initialize with optional test data.

        Args:
            data: Nested dict of feature_name -> entity_key_hash -> values
        """
        self._data = data or {}
        self._healthy = True

    def write(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
        values: dict[str, Any],
    ) -> None:
        if feature_name not in self._data:
            self._data[feature_name] = {}
        key = self._hash_keys(entity_keys)
        self._data[feature_name][key] = values

    def write_batch(
        self,
        feature_name: str,
        records: list[dict[str, Any]],
        entity_key_columns: list[str],
    ) -> int:
        for record in records:
            entity_keys = {col: str(record[col]) for col in entity_key_columns}
            values = {
                k: v for k, v in record.items() if k not in entity_key_columns
            }
            self.write(feature_name, entity_keys, values)
        return len(records)

    def read(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> dict[str, Any] | None:
        if feature_name not in self._data:
            return None
        key = self._hash_keys(entity_keys)
        return self._data[feature_name].get(key)

    def read_batch(
        self,
        feature_name: str,
        entity_keys: list[dict[str, str]],
    ) -> list[dict[str, Any] | None]:
        return [self.read(feature_name, keys) for keys in entity_keys]

    def delete(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> bool:
        if feature_name not in self._data:
            return False
        key = self._hash_keys(entity_keys)
        if key in self._data[feature_name]:
            del self._data[feature_name][key]
            return True
        return False

    def exists(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> bool:
        return self.read(feature_name, entity_keys) is not None

    def ping(self) -> bool:
        return self._healthy

    def _hash_keys(self, entity_keys: dict[str, str]) -> str:
        """Create a simple hash key from entity keys."""
        return "|".join(f"{k}={v}" for k, v in sorted(entity_keys.items()))


@pytest.fixture
def mock_store():
    """Create a mock online store with test data."""
    store = MockOnlineStore()
    store.write(
        "user_spend",
        {"user_id": "u123"},
        {"amt_sum_7d": 1250.50, "amt_mean_7d": 62.52},
    )
    store.write(
        "user_spend",
        {"user_id": "u456"},
        {"amt_sum_7d": 800.00, "amt_mean_7d": 40.00},
    )
    return store


@pytest.fixture
def mock_feature():
    """Create a mock feature."""

    def fn(df):
        return df

    fn.__name__ = "user_spend"

    return Feature(
        fn=fn,
        name="user_spend",
        source="data/transactions.parquet",
        keys=["user_id"],
        entities=None,
        tags=["spending"],
        timestamp="transaction_date",
        description="User spending aggregates",
        interval="7d",
        metrics=None,
        validators=None,
        engine=None,
    )


@pytest.fixture
def mock_definitions(mock_store, mock_feature, temp_store):
    """Create mock definitions with a feature and online store."""
    defs = MagicMock(spec=Definitions)
    defs.name = "test-project"
    defs.features = {"user_spend": mock_feature}
    defs.online_store = mock_store
    defs.offline_store = temp_store
    return defs


@pytest.fixture
def client(mock_definitions):
    """Create test client with mock definitions."""
    app = create_app(
        definitions=mock_definitions,
        enable_metrics=True,
        enable_docs=True,
    )
    return TestClient(app)


@pytest.fixture
def client_no_store(mock_feature, temp_store):
    """Create test client without online store."""
    defs = MagicMock(spec=Definitions)
    defs.name = "test-project"
    defs.features = {"user_spend": mock_feature}
    defs.online_store = None
    defs.offline_store = temp_store

    app = create_app(definitions=defs, enable_metrics=False, enable_docs=False)
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_returns_healthy_status(self, client):
        """Health endpoint should return healthy status."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == mlforge.__version__
        assert data["online_store"] == "MockOnlineStore"
        assert data["online_store_healthy"] is True

    def test_health_degraded_when_store_unhealthy(self, mock_definitions):
        """Health should be degraded when online store is unhealthy."""
        mock_definitions.online_store._healthy = False

        app = create_app(definitions=mock_definitions)
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "degraded"
        assert data["online_store_healthy"] is False

    def test_health_without_online_store(self, client_no_store):
        """Health should work without online store configured."""
        response = client_no_store.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["online_store"] is None
        assert data["online_store_healthy"] is None


class TestFeaturesListEndpoint:
    """Tests for GET /features endpoint."""

    def test_list_features(self, client):
        """Should list all available features."""
        response = client.get("/features")
        assert response.status_code == 200

        data = response.json()
        assert "features" in data
        assert len(data["features"]) == 1

        feature = data["features"][0]
        assert feature["name"] == "user_spend"
        assert feature["keys"] == ["user_id"]


class TestFeatureMetadataEndpoint:
    """Tests for GET /features/{name} endpoint."""

    def test_get_feature_metadata(self, client):
        """Should return feature metadata."""
        response = client.get("/features/user_spend")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "user_spend"
        assert data["keys"] == ["user_id"]
        assert data["timestamp"] == "transaction_date"
        assert data["interval"] == "7d"
        assert data["description"] == "User spending aggregates"
        assert data["tags"] == ["spending"]

    def test_feature_not_found(self, client):
        """Should return 404 for unknown feature."""
        response = client.get("/features/unknown_feature")
        assert response.status_code == 404

        data = response.json()["detail"]
        assert data["error"] == "FeatureNotFound"
        assert "unknown_feature" in data["message"]
        assert "user_spend" in data["details"]["available_features"]


class TestOnlineFeaturesEndpoint:
    """Tests for POST /features/online endpoint."""

    def test_get_online_features(self, client):
        """Should retrieve features for entity."""
        response = client.post(
            "/features/online",
            json={
                "features": ["user_spend"],
                "entity_keys": {"user_id": "u123"},
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert "features" in data
        assert "user_spend" in data["features"]
        assert data["features"]["user_spend"]["amt_sum_7d"] == 1250.50
        assert data["features"]["user_spend"]["amt_mean_7d"] == 62.52

        assert "metadata" in data
        assert "user_spend" in data["metadata"]

    def test_entity_not_found(self, client):
        """Should return null for missing entity."""
        response = client.post(
            "/features/online",
            json={
                "features": ["user_spend"],
                "entity_keys": {"user_id": "unknown"},
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["features"]["user_spend"] is None

    def test_unknown_feature(self, client):
        """Should return 404 for unknown feature."""
        response = client.post(
            "/features/online",
            json={
                "features": ["unknown_feature"],
                "entity_keys": {"user_id": "u123"},
            },
        )
        assert response.status_code == 404

        data = response.json()["detail"]
        assert data["error"] == "FeatureNotFound"

    def test_no_online_store(self, client_no_store):
        """Should return 503 when no online store configured."""
        response = client_no_store.post(
            "/features/online",
            json={
                "features": ["user_spend"],
                "entity_keys": {"user_id": "u123"},
            },
        )
        assert response.status_code == 503

        data = response.json()["detail"]
        assert data["error"] == "OnlineStoreUnavailable"


class TestBatchFeaturesEndpoint:
    """Tests for POST /features/batch endpoint."""

    def test_batch_features(self, client):
        """Should retrieve features for multiple entities."""
        response = client.post(
            "/features/batch",
            json={
                "features": ["user_spend"],
                "entity_keys": [
                    {"user_id": "u123"},
                    {"user_id": "u456"},
                ],
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data["results"]) == 2

        # First result
        assert data["results"][0]["entity_keys"] == {"user_id": "u123"}
        assert (
            data["results"][0]["features"]["user_spend"]["amt_sum_7d"]
            == 1250.50
        )
        assert data["results"][0]["error"] is None

        # Second result
        assert data["results"][1]["entity_keys"] == {"user_id": "u456"}
        assert (
            data["results"][1]["features"]["user_spend"]["amt_sum_7d"] == 800.00
        )

    def test_batch_with_missing_entities(self, client):
        """Should handle missing entities in batch."""
        response = client.post(
            "/features/batch",
            json={
                "features": ["user_spend"],
                "entity_keys": [
                    {"user_id": "u123"},
                    {"user_id": "unknown"},
                ],
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data["results"]) == 2

        # First result found
        assert data["results"][0]["features"]["user_spend"] is not None
        assert data["results"][0]["error"] is None

        # Second result not found
        assert data["results"][1]["features"]["user_spend"] is None
        assert data["results"][1]["error"] == "Entity not found"

    def test_batch_unknown_feature(self, client):
        """Should return 404 for unknown feature in batch."""
        response = client.post(
            "/features/batch",
            json={
                "features": ["unknown_feature"],
                "entity_keys": [{"user_id": "u123"}],
            },
        )
        assert response.status_code == 404

    def test_batch_no_online_store(self, client_no_store):
        """Should return 503 when no online store configured."""
        response = client_no_store.post(
            "/features/batch",
            json={
                "features": ["user_spend"],
                "entity_keys": [{"user_id": "u123"}],
            },
        )
        assert response.status_code == 503

    def test_batch_size_limit(self, client):
        """Should reject batch requests exceeding size limit."""
        response = client.post(
            "/features/batch",
            json={
                "features": ["user_spend"],
                "entity_keys": [{"user_id": f"u{i}"} for i in range(1001)],
            },
        )
        assert response.status_code == 422  # Validation error

        data = response.json()
        assert "1000" in str(data)  # Should mention the limit


class TestOnlineStoreErrors:
    """Tests for online store error handling."""

    def test_store_error_single(self, mock_definitions):
        """Should return 503 when store raises exception."""
        mock_definitions.online_store.read = MagicMock(
            side_effect=ConnectionError("Redis connection lost")
        )

        app = create_app(definitions=mock_definitions)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/features/online",
            json={
                "features": ["user_spend"],
                "entity_keys": {"user_id": "u123"},
            },
        )
        assert response.status_code == 503

        data = response.json()["detail"]
        assert data["error"] == "OnlineStoreError"
        assert "user_spend" in data["message"]

    def test_store_error_batch(self, mock_definitions):
        """Should return 503 when store raises exception in batch."""
        mock_definitions.online_store.read_batch = MagicMock(
            side_effect=TimeoutError("Redis timeout")
        )

        app = create_app(definitions=mock_definitions)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/features/batch",
            json={
                "features": ["user_spend"],
                "entity_keys": [{"user_id": "u123"}],
            },
        )
        assert response.status_code == 503

        data = response.json()["detail"]
        assert data["error"] == "OnlineStoreError"


class TestMetricsEndpoint:
    """Tests for GET /metrics endpoint."""

    def test_metrics_endpoint(self, client):
        """Metrics endpoint should return Prometheus format."""
        # Make some requests first to generate metrics
        client.get("/health")
        client.post(
            "/features/online",
            json={
                "features": ["user_spend"],
                "entity_keys": {"user_id": "u123"},
            },
        )

        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

        # Check for our custom metrics
        content = response.text
        assert "mlforge_feature_retrieval" in content

    def test_metrics_disabled(self, client_no_store):
        """Metrics should return 404 when disabled."""
        response = client_no_store.get("/metrics")
        assert response.status_code == 404


class TestCORS:
    """Tests for CORS configuration."""

    def test_cors_headers(self, mock_definitions):
        """Should include CORS headers when configured."""
        app = create_app(
            definitions=mock_definitions,
            cors_origins=["http://localhost:3000"],
        )
        client = TestClient(app)

        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert (
            response.headers.get("access-control-allow-origin")
            == "http://localhost:3000"
        )


class TestOpenAPIDocs:
    """Tests for OpenAPI documentation."""

    def test_docs_enabled(self, client):
        """Should serve docs when enabled."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_docs_disabled(self, client_no_store):
        """Should not serve docs when disabled."""
        response = client_no_store.get("/docs")
        assert response.status_code == 404

    def test_openapi_json(self, client):
        """Should serve OpenAPI JSON."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        data = response.json()
        assert data["info"]["title"] == "mlforge"
        assert "/features/online" in data["paths"]
