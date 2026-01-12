"""
REST API server for real-time feature serving.

This module provides a FastAPI-based HTTP interface for retrieving features
from the online store. It wraps the core mlforge functionality in a web API
suitable for microservices and non-Python clients.

Example:
    Start the server via CLI:

        mlforge serve --definitions src/features/definitions.py --port 8000

    Or programmatically:

        from mlforge.serve import create_app
        from mlforge import Definitions

        defs = Definitions(...)
        app = create_app(defs)
"""

from datetime import datetime, timezone
from typing import Any, Protocol, cast

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

import mlforge
import mlforge.core as core

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

MAX_BATCH_SIZE = 1000


class Pingable(Protocol):
    """Protocol for objects with a ping method."""

    def ping(self) -> bool: ...


# -----------------------------------------------------------------------------
# Request/Response Models
# -----------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    online_store: str | None
    online_store_healthy: bool | None


class FeatureInfo(BaseModel):
    """Feature summary for list endpoint."""

    name: str
    keys: list[str]


class FeaturesListResponse(BaseModel):
    """Response for GET /features."""

    features: list[FeatureInfo]


class FeatureDetailResponse(BaseModel):
    """Response for GET /features/{name}."""

    name: str
    keys: list[str]
    timestamp: str | None = None
    interval: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class OnlineFeaturesRequest(BaseModel):
    """Request for POST /features/online."""

    features: list[str]
    entity_keys: dict[str, str]


class OnlineFeaturesResponse(BaseModel):
    """Response for POST /features/online."""

    features: dict[str, dict[str, Any] | None]
    metadata: dict[str, dict[str, Any]]


class BatchFeaturesRequest(BaseModel):
    """Request for POST /features/batch."""

    features: list[str]
    entity_keys: list[dict[str, str]]

    @field_validator("entity_keys")
    @classmethod
    def validate_batch_size(
        cls, v: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        """Validate batch size does not exceed maximum."""
        if len(v) > MAX_BATCH_SIZE:
            raise ValueError(
                f"Batch size {len(v)} exceeds maximum of {MAX_BATCH_SIZE}"
            )
        return v


class BatchResultItem(BaseModel):
    """Single result in batch response."""

    entity_keys: dict[str, str]
    features: dict[str, dict[str, Any] | None]
    error: str | None = None


class BatchFeaturesResponse(BaseModel):
    """Response for POST /features/batch."""

    results: list[BatchResultItem]
    metadata: dict[str, dict[str, Any]]


# -----------------------------------------------------------------------------
# Metrics (optional Prometheus integration)
# -----------------------------------------------------------------------------

_metrics: "MetricsState | None" = None


class MetricsState:
    """Container for Prometheus metrics (singleton to avoid duplicate registration)."""

    def __init__(self) -> None:
        from prometheus_client import Counter, Histogram

        self.feature_retrieval_latency = Histogram(
            "mlforge_feature_retrieval_latency_seconds",
            "Feature retrieval latency from online store",
            ["feature"],
        )
        self.feature_retrieval_total = Counter(
            "mlforge_feature_retrieval_total",
            "Total feature retrieval count",
            ["feature", "status"],
        )


def _get_metrics() -> MetricsState:
    """Get or create singleton metrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsState()
    return _metrics


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _get_defs(request: Request) -> core.Definitions:
    """Get definitions from app state."""
    return request.app.state.definitions


def _get_metrics_state(request: Request) -> "MetricsState | None":
    """Get metrics from app state."""
    return request.app.state.metrics


def _validate_features_request(
    defs: core.Definitions, feature_names: list[str]
) -> None:
    """Validate feature names exist and online store is configured."""
    unknown = [f for f in feature_names if f not in defs.features]
    if unknown:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "FeatureNotFound",
                "message": f"Unknown features: {unknown}",
                "details": {
                    "unknown_features": unknown,
                    "available_features": list(defs.features.keys()),
                },
            },
        )

    if defs.online_store is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "OnlineStoreUnavailable",
                "message": "No online store configured",
            },
        )


def _build_feature_metadata(
    defs: core.Definitions, feature_names: list[str]
) -> dict[str, dict[str, Any]]:
    """Build metadata dict for requested features."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        name: {"keys": defs.features[name].keys, "retrieved_at": now}
        for name in feature_names
    }


def _read_feature(
    store: Any,
    feature_name: str,
    entity_keys: dict[str, str],
    metrics: "MetricsState | None",
) -> dict[str, Any] | None:
    """Read a single feature from the online store with error handling."""
    try:
        if metrics:
            with metrics.feature_retrieval_latency.labels(
                feature=feature_name
            ).time():
                values = store.read(feature_name, entity_keys)
        else:
            values = store.read(feature_name, entity_keys)

        if metrics:
            status = "success" if values is not None else "not_found"
            metrics.feature_retrieval_total.labels(
                feature=feature_name, status=status
            ).inc()

        return values
    except Exception as e:
        if metrics:
            metrics.feature_retrieval_total.labels(
                feature=feature_name, status="error"
            ).inc()
        raise HTTPException(
            status_code=503,
            detail={
                "error": "OnlineStoreError",
                "message": f"Failed to retrieve feature '{feature_name}': {e}",
            },
        ) from e


def _read_feature_batch(
    store: Any,
    feature_name: str,
    entity_keys: list[dict[str, str]],
    metrics: "MetricsState | None",
) -> list[dict[str, Any] | None]:
    """Read a feature batch from the online store with error handling."""
    try:
        if metrics:
            with metrics.feature_retrieval_latency.labels(
                feature=feature_name
            ).time():
                values = store.read_batch(feature_name, entity_keys)
        else:
            values = store.read_batch(feature_name, entity_keys)

        if metrics:
            found = sum(1 for v in values if v is not None)
            metrics.feature_retrieval_total.labels(
                feature=feature_name, status="success"
            ).inc(found)
            metrics.feature_retrieval_total.labels(
                feature=feature_name, status="not_found"
            ).inc(len(values) - found)

        return values
    except Exception as e:
        if metrics:
            metrics.feature_retrieval_total.labels(
                feature=feature_name, status="error"
            ).inc()
        raise HTTPException(
            status_code=503,
            detail={
                "error": "OnlineStoreError",
                "message": f"Failed to retrieve feature '{feature_name}': {e}",
            },
        ) from e


# -----------------------------------------------------------------------------
# Router
# -----------------------------------------------------------------------------

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Health check endpoint with online store connectivity status."""
    defs = _get_defs(request)
    store = defs.online_store

    if store is None:
        return HealthResponse(
            status="healthy",
            version=mlforge.__version__,
            online_store=None,
            online_store_healthy=None,
        )

    healthy = cast(Pingable, store).ping() if hasattr(store, "ping") else True
    return HealthResponse(
        status="healthy" if healthy else "degraded",
        version=mlforge.__version__,
        online_store=type(store).__name__,
        online_store_healthy=healthy,
    )


@router.get("/features", response_model=FeaturesListResponse)
async def list_features(request: Request) -> FeaturesListResponse:
    """List all available features."""
    defs = _get_defs(request)
    return FeaturesListResponse(
        features=[
            FeatureInfo(name=name, keys=f.keys)
            for name, f in defs.features.items()
        ]
    )


@router.get("/features/{feature_name}", response_model=FeatureDetailResponse)
async def get_feature_metadata(
    request: Request, feature_name: str
) -> FeatureDetailResponse:
    """Get detailed metadata for a specific feature."""
    defs = _get_defs(request)

    if feature_name not in defs.features:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "FeatureNotFound",
                "message": f"Feature '{feature_name}' not found",
                "details": {"available_features": list(defs.features.keys())},
            },
        )

    f = defs.features[feature_name]
    return FeatureDetailResponse(
        name=f.name,
        keys=f.keys,
        timestamp=f.timestamp_column,
        interval=f.interval,
        description=f.description,
        tags=f.tags,
    )


@router.post("/features/online", response_model=OnlineFeaturesResponse)
async def get_online_features(
    request: Request, body: OnlineFeaturesRequest
) -> OnlineFeaturesResponse:
    """Get features for a single entity from the online store."""
    defs = _get_defs(request)
    metrics = _get_metrics_state(request)

    _validate_features_request(defs, body.features)

    result_features: dict[str, dict[str, Any] | None] = {}
    for feature_name in body.features:
        result_features[feature_name] = _read_feature(
            defs.online_store, feature_name, body.entity_keys, metrics
        )

    return OnlineFeaturesResponse(
        features=result_features,
        metadata=_build_feature_metadata(defs, body.features),
    )


@router.post("/features/batch", response_model=BatchFeaturesResponse)
async def get_batch_features(
    request: Request, body: BatchFeaturesRequest
) -> BatchFeaturesResponse:
    """Get features for multiple entities in batch."""
    defs = _get_defs(request)
    metrics = _get_metrics_state(request)

    _validate_features_request(defs, body.features)

    # Batch read for each feature
    feature_values: dict[str, list[dict[str, Any] | None]] = {}
    for feature_name in body.features:
        feature_values[feature_name] = _read_feature_batch(
            defs.online_store, feature_name, body.entity_keys, metrics
        )

    # Assemble per-entity results
    results = []
    for i, entity_keys in enumerate(body.entity_keys):
        entity_features = {
            name: feature_values[name][i] for name in body.features
        }
        has_missing = any(v is None for v in entity_features.values())
        results.append(
            BatchResultItem(
                entity_keys=entity_keys,
                features=entity_features,
                error="Entity not found" if has_missing else None,
            )
        )

    return BatchFeaturesResponse(
        results=results,
        metadata=_build_feature_metadata(defs, body.features),
    )


@router.get("/metrics")
async def get_metrics(request: Request) -> Response:
    """Prometheus metrics endpoint."""
    if not request.app.state.enable_metrics:
        raise HTTPException(status_code=404, detail="Metrics disabled")

    from prometheus_client import REGISTRY, generate_latest

    return Response(
        content=generate_latest(REGISTRY),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# -----------------------------------------------------------------------------
# Application Factory
# -----------------------------------------------------------------------------


def create_app(
    definitions: core.Definitions,
    enable_metrics: bool = True,
    enable_docs: bool = True,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """
    Create a FastAPI application for feature serving.

    Args:
        definitions: Definitions instance with features and online store
        enable_metrics: Enable Prometheus metrics at /metrics. Defaults to True.
        enable_docs: Enable OpenAPI docs at /docs. Defaults to True.
        cors_origins: List of allowed CORS origins. Defaults to None (no CORS).

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="mlforge",
        version=mlforge.__version__,
        docs_url="/docs" if enable_docs else None,
        redoc_url="/redoc" if enable_docs else None,
        openapi_url="/openapi.json" if enable_docs else None,
    )

    app.state.definitions = definitions
    app.state.enable_metrics = enable_metrics
    app.state.metrics = _get_metrics() if enable_metrics else None

    if cors_origins:
        app.add_middleware(
            cast(Any, CORSMiddleware),
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization"],
        )

    app.include_router(router)
    return app
