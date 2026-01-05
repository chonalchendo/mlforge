"""
mlforge: A simple feature store SDK.

This package provides tools for defining, materializing, and retrieving
features for machine learning workflows.

Usage:
    import mlforge as mlf

    @mlf.feature(keys=["user_id"], source="data.parquet")
    def my_feature(df):
        return df

    # With Source abstraction (v0.6.0+)
    @mlf.feature(
        keys=["user_id"],
        source=mlf.Source("data/events.csv", format=mlf.CSVFormat(delimiter="|")),
    )
    def user_events(df):
        return df

    defs = mlf.Definitions(
        name="my-project",
        features=[my_feature],
        offline_store=mlf.LocalStore("./store")
    )

Public API:
    feature: Decorator for defining features
    Feature: Container class for feature definitions
    Definitions: Central registry for features
    Entity: Entity definition with optional surrogate key generation
    LocalStore: Local filesystem storage backend
    S3Store: Amazon S3 storage backend
    RedisStore: Redis online store for real-time serving
    Rolling: Rolling window aggregation metric
    Source: Data source abstraction with location/format detection
    ParquetFormat, CSVFormat, DeltaFormat: Format configuration classes
    entity_key: Create reusable entity key transforms
    surrogate_key: Generate surrogate keys from columns
    get_training_data: Retrieve features with point-in-time correctness
    get_online_features: Retrieve features from online store for inference
    Validators: not_null, unique, greater_than, less_than, in_range, etc.
"""

from importlib.metadata import version as _get_version

__version__ = _get_version("mlforge-sdk")

from mlforge.core import Definitions, Feature, feature
from mlforge.entities import Entity
from mlforge.metrics import Rolling
from mlforge.online import OnlineStore, RedisStore
from mlforge.retrieval import get_online_features, get_training_data
from mlforge.sources import CSVFormat, DeltaFormat, ParquetFormat, Source
from mlforge.store import LocalStore, S3Store
from mlforge.types import DataType, TypeKind
from mlforge.utils import entity_key, surrogate_key
from mlforge.validators import (
    greater_than,
    greater_than_or_equal,
    in_range,
    is_in,
    less_than,
    less_than_or_equal,
    matches_regex,
    not_null,
    unique,
)

__all__ = [
    "__version__",
    "feature",
    "Feature",
    "Definitions",
    "Entity",
    "LocalStore",
    "S3Store",
    "OnlineStore",
    "RedisStore",
    "entity_key",
    "surrogate_key",
    "get_training_data",
    "get_online_features",
    "Rolling",
    "Source",
    "ParquetFormat",
    "CSVFormat",
    "DeltaFormat",
    "DataType",
    "TypeKind",
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
    "unique",
    "is_in",
    "in_range",
    "matches_regex",
    "not_null",
]
