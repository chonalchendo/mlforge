"""Definitions for fraud detection feature store."""

import mlforge as mlf

from fraud_detection import features

defs = mlf.Definitions(
    name="Fraud Detection Features",
    features=[features],
)
