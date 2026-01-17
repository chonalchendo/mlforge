#!/usr/bin/env python3
"""
Read features from Redis online store.

This script demonstrates two ways to read features from Redis:

1. Low-level API: Using RedisStore.read() and read_batch() directly
2. High-level API: Using get_online_features() for batch inference

Run after building features with `mlforge build --online`.

Usage:
    uv run python src/transactions_online/read_features.py
"""

import polars as pl

from mlforge import get_online_features
from mlforge.stores import RedisStore
from transactions_online.features import user


def main() -> None:
    # Connect to Redis
    store = RedisStore(host="localhost", port=6379)

    # Verify connection
    if not store.ping():
        print("Error: Cannot connect to Redis. Is it running?")
        print("Start Redis with: docker-compose up -d")
        return

    print("Connected to Redis successfully!\n")

    feature_name = "user_spend"

    # Check if features exist
    sample_keys = store._client.keys(f"{store.prefix}:{feature_name}:*")
    if not sample_keys:
        print(f"No features found for '{feature_name}' in Redis.")
        print(
            "Run 'mlforge build --online' first to populate the online store."
        )
        return

    print(f"Found {len(sample_keys)} entities in online store\n")

    # =========================================================================
    # Method 1: Low-level API (RedisStore.read)
    # =========================================================================
    print("=" * 60)
    print("Method 1: Low-level API (RedisStore.read)")
    print("=" * 60)

    # Get a sample key and read directly
    sample_key = sample_keys[0]
    print(f"Sample key: {sample_key}")

    value = store._client.get(sample_key)
    print(f"Raw value: {value}\n")

    # =========================================================================
    # Method 2: High-level API (get_online_features)
    # =========================================================================
    print("=" * 60)
    print("Method 2: High-level API (get_online_features)")
    print("=" * 60)

    # Simulate an inference request with user data
    # These are the raw user attributes that will be hashed by the entity transform
    request_df = pl.DataFrame(
        {
            "request_id": ["req_001", "req_002", "req_003"],
            "first": ["Jennifer", "Stephanie", "Edward"],
            "last": ["Banks", "Gill", "Sanchez"],
            "dob": ["1988-03-09", "1978-06-22", "1962-01-19"],
        }
    )

    print("\nInference request:")
    print(request_df)

    # Retrieve features using the high-level API
    # This applies the entity transform and joins features from Redis
    result = get_online_features(
        features=["user_spend"],
        entity_df=request_df,
        store=store,
        entities=[user],
    )

    print("\nResult with features joined:")
    print(result)

    # Show which columns are feature columns
    original_cols = set(request_df.columns)
    feature_cols = [
        c for c in result.columns if c not in original_cols and c != "user_id"
    ]
    print(f"\nFeature columns added: {feature_cols}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Feature: {feature_name}")
    print(f"Total entities in online store: {len(sample_keys)}")
    print("\nFor real-time inference, use get_online_features():")
    print("""
    from mlforge import get_online_features
    from mlforge.stores import RedisStore
    from transactions_online.features import user

    store = RedisStore(host="localhost")

    result = get_online_features(
        features=["user_spend"],
        entity_df=request_df,
        store=store,
        entities=[user],
    )
    """)


if __name__ == "__main__":
    main()
