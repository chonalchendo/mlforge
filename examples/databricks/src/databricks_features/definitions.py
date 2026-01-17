"""Definitions registry for Databricks feature store.

The Definitions object is the central registry that connects features
to storage backends. It uses profile-based configuration from mlforge.yaml
to switch between local development and Databricks deployment.

Profiles:
    dev        - LocalStore for local development (default)
    databricks - UnityCatalogStore + DatabricksOnlineStore for production
"""

import mlforge as mlf

from databricks_features import features

# The Definitions object loads store configuration from mlforge.yaml.
# Profile can be overridden via CLI: mlforge build --profile databricks
defs = mlf.Definitions(
    name="Databricks Credit Card Features",
    features=[features],
)
