"""
mlforge: A simple feature store SDK.

This package provides tools for defining, materializing, and retrieving
features for machine learning workflows.

Public API:
    feature: Decorator for defining features
    Feature: Container class for feature definitions
    Definitions: Central registry for features
    LocalStore: Local filesystem storage backend
    entity_key: Create reusable entity key transforms
    surrogate_key: Generate surrogate keys from columns
    get_training_data: Retrieve features with point-in-time correctness
"""

from mlforge.core import Definitions, Feature, feature
from mlforge.retrieval import get_training_data
from mlforge.store import LocalStore
from mlforge.utils import entity_key, surrogate_key

__all__ = [
    "feature",
    "Feature",
    "Definitions",
    "LocalStore",
    "entity_key",
    "surrogate_key",
    "get_training_data",
]
