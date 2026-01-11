"""Definitions for recommendation feature store."""

import mlforge as mlf

from recommendation import item_features, user_features

defs = mlf.Definitions(
    name="Recommendation Features",
    features=[user_features, item_features],
)
