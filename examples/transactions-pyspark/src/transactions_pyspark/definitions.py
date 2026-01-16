"""
PySpark feature store definitions.

This module creates the Definitions object that registers all
PySpark features and configures the offline store.
"""

import mlforge as mlf

from transactions_pyspark import features

# Create Definitions with PySpark as default engine
defs = mlf.Definitions(
    name="transactions-pyspark",
    features=[features],
    offline_store=mlf.LocalStore("feature_store"),
    default_engine="pyspark",
)
