#!/usr/bin/env python3
"""
Read features from Redis online store.

This script demonstrates how to read features from Redis for real-time
inference. Run after building features with `mlforge build --online`.

Usage:
    uv run python src/transactions_online/read_features.py
"""

from mlforge.online import RedisStore


def main() -> None:
    # Connect to Redis
    store = RedisStore(host="localhost", port=6379)

    # Verify connection
    if not store.ping():
        print("Error: Cannot connect to Redis. Is it running?")
        print("Start Redis with: docker-compose up -d")
        return

    print("Connected to Redis successfully!\n")

    # Example user IDs (these are hashed surrogate keys from first+last+dob)
    # In production, you'd compute this from the actual user data
    feature_name = "user_spend"

    # Read single entity
    print("=" * 60)
    print("Single Entity Read")
    print("=" * 60)

    # First, let's find some keys that exist
    # In real usage, you'd know the entity keys from your application
    sample_keys = store._client.keys(f"{store.prefix}:{feature_name}:*")

    if not sample_keys:
        print(f"No features found for '{feature_name}' in Redis.")
        print(
            "Run 'mlforge build --online' first to populate the online store."
        )
        return

    print(f"Found {len(sample_keys)} entities in online store\n")

    # Get a sample key and extract the entity hash
    sample_key = sample_keys[0]
    print(f"Sample key: {sample_key}")

    # Read the value directly
    value = store._client.get(sample_key)
    print(f"Raw value: {value}\n")

    # Batch read example
    print("=" * 60)
    print("Batch Read (first 5 entities)")
    print("=" * 60)

    # Get first 5 keys
    batch_keys = sample_keys[:5]
    pipe = store._client.pipeline()
    for key in batch_keys:
        pipe.get(key)
    results = pipe.execute()

    for key, value in zip(batch_keys, results):
        print(f"\nKey: {key}")
        print(f"Value: {value}")

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Feature: {feature_name}")
    print(f"Total entities in online store: {len(sample_keys)}")
    print(f"Key format: {store.prefix}:{feature_name}:<entity_hash>")
    print("\nIn your inference code, use:")
    print(
        "  store.read(feature_name='user_spend', entity_keys={'user_id': '<id>'})"
    )


if __name__ == "__main__":
    main()
