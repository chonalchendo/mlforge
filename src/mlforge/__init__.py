"""
mlforge: A simple feature store SDK.

Build, version, and serve ML features with point-in-time correctness.

Getting Started:
    # Initialize a project
    $ mlforge init my-features --profile
    $ cd my-features

    # Define features in src/my_features/features.py
    # Build features
    $ mlforge build --target src/my_features/definitions.py

    # Retrieve for training
    from my_features.definitions import defs
    training_df = defs.get_training_data(
        features=["user_spend"],
        entity_df=labels_df,
        timestamp="label_time",
    )

Feature Definition:
    import mlforge as mlf
    import polars as pl

    @mlf.feature(
        keys=["user_id"],
        source="data/transactions.parquet",
        timestamp="event_time",
        metrics=[mlf.Rolling(windows=["7d", "30d"], aggregations={"amount": ["sum"]})],
    )
    def user_spend(df: pl.DataFrame) -> pl.DataFrame:
        return df.select(["user_id", "event_time", "amount"])

Public API:
    Definitions: Central registry for features with get_training_data/get_online_features
    feature: Decorator for defining features
    Feature: Container class for feature definitions
    FeatureSpec: Column selection and version pinning for feature retrieval
    Entity: Entity definition with optional surrogate key generation
    Rolling: Rolling window aggregation metric

    Offline Stores:
        LocalStore: Local filesystem storage
        S3Store: Amazon S3 storage
        GCSStore: Google Cloud Storage
        UnityCatalogStore: Databricks Unity Catalog storage

    Online Stores:
        RedisStore: Redis for real-time serving
        DynamoDBStore: AWS DynamoDB for serverless serving
        DatabricksOnlineStore: Databricks Online Tables for Databricks-native serving
        OnlineStore: Abstract base class

    Source Configuration:
        Source: Data source abstraction
        ParquetFormat, CSVFormat, DeltaFormat: Format configurations
        Timestamp: Timestamp configuration

    Utilities:
        surrogate_key: Generate surrogate keys from columns

    Validators:
        not_null, unique, greater_than, less_than, in_range, is_in, matches_regex

    Integrations:
        mlflow: MLflow integration module (mlf.mlflow.autolog(), etc.)
        log_features_to_mlflow: Log feature metadata to MLflow runs
"""

from importlib.metadata import version as _get_version

__version__ = _get_version("mlforge-sdk")

from mlforge.core import Definitions, Feature, feature
from mlforge.entities import Entity

# MLflow integration - exposed as mlf.mlflow module and direct function
from mlforge.integrations import mlflow
from mlforge.integrations.mlflow import log_features_to_mlflow
from mlforge.metrics import Rolling
from mlforge.retrieval import FeatureSpec
from mlforge.sources import CSVFormat, DeltaFormat, ParquetFormat, Source
from mlforge.stores import (
    DatabricksOnlineStore,
    DynamoDBStore,
    GCSStore,
    LocalStore,
    OnlineStore,
    RedisStore,
    S3Store,
    UnityCatalogStore,
)
from mlforge.timestamps import Timestamp
from mlforge.types import DataType, TypeKind
from mlforge.utils import surrogate_key
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
    "FeatureSpec",
    "Definitions",
    "Entity",
    "LocalStore",
    "S3Store",
    "GCSStore",
    "UnityCatalogStore",
    "OnlineStore",
    "RedisStore",
    "DynamoDBStore",
    "DatabricksOnlineStore",
    "Timestamp",
    "surrogate_key",
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
    "mlflow",
    "log_features_to_mlflow",
]
