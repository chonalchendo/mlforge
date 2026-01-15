# Retrieval API

The retrieval module provides functions for retrieving features for both training (offline) and inference (online) use cases.

## FeatureSpec

Use `FeatureSpec` to select specific columns from a feature or pin to a specific version:

::: mlforge.retrieval.FeatureSpec

## Recommended: Definitions Methods

For most use cases, use the methods on `Definitions` which automatically handle entity key coordination:

::: mlforge.core.Definitions.get_training_data
    options:
      show_root_heading: false

::: mlforge.core.Definitions.get_online_features
    options:
      show_root_heading: false

## Standalone Functions

For advanced use cases or when you don't have a Definitions object:

### Offline Retrieval (Training)

::: mlforge.retrieval.get_training_data

### Online Retrieval (Inference)

::: mlforge.retrieval.get_online_features

## Helper Functions

::: mlforge.retrieval.join_online_feature_by_keys
