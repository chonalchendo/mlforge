#!/usr/bin/env python3
"""Main demonstration script for Databricks feature store.

This script demonstrates the complete mlforge workflow:
1. Generate synthetic data (if not present)
2. Build features to offline store
3. List and inspect features
4. Retrieve point-in-time correct training data

Usage:
    # Local development (uses LocalStore)
    uv run python src/databricks_features/main.py

    # Databricks (uses Unity Catalog + Online Tables)
    uv run python src/databricks_features/main.py --profile databricks
"""

import argparse
from pathlib import Path

import polars as pl

from databricks_features.definitions import defs
from databricks_features.generate_data import generate_transactions


def ensure_data_exists(data_path: Path) -> None:
    """Generate sample data if it doesn't exist."""
    if not data_path.exists():
        print(f"Generating sample data at {data_path}...")
        df = generate_transactions(n_rows=5000, n_customers=100, n_merchants=50)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(data_path)
        print(f"Generated {df.shape[0]} transactions\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Databricks feature store demo"
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="mlforge profile to use (dev, databricks)",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip feature building (use existing features)",
    )
    args = parser.parse_args()

    data_path = Path("data/transactions.parquet")

    # Step 1: Ensure data exists
    ensure_data_exists(data_path)

    # Step 2: Build features
    if not args.skip_build:
        print("=" * 60)
        print("Building features...")
        print("=" * 60)

        if args.profile:
            print(f"Using profile: {args.profile}")
            # Note: For Databricks, you'd typically run:
            # mlforge build --profile databricks
            # This script uses CLI for building to respect profiles

        # Build all features using the CLI approach
        # In production, you'd use: mlforge build --profile <profile>
        defs.build()
        print("\nFeature build complete!\n")

    # Step 3: List available features
    print("=" * 60)
    print("Available features:")
    print("=" * 60)
    for feature in defs.list_features():
        tags = ", ".join(feature.tags) if feature.tags else "none"
        print(f"  - {feature.name}")
        print(f"      Tags: {tags}")
        print(f"      Description: {feature.description or 'N/A'}")
        print()

    # Step 4: Create entity DataFrame for training data retrieval
    print("=" * 60)
    print("Retrieving training data...")
    print("=" * 60)

    # Load transactions and add labels (simulating fraud labels)
    transactions_df = pl.read_parquet(data_path)

    # Create entity DataFrame with timestamps for point-in-time joins
    # Use the transaction time as the label time (features will be joined
    # as-of this timestamp, ensuring no data leakage)
    entity_df = transactions_df.select(
        "transaction_id",
        "first_name",
        "last_name",
        "date_of_birth",
        "merchant_name",
        pl.col("transaction_time")
        .str.to_datetime("%Y-%m-%d %H:%M:%S")
        .alias("label_time"),
        pl.col("is_fraud").cast(pl.Int32).alias("label"),
    ).sample(fraction=0.1, seed=42)  # Sample 10% for demo

    print(f"Entity DataFrame shape: {entity_df.shape}")
    print(f"Fraud rate: {entity_df['label'].mean():.2%}\n")

    # Step 5: Get point-in-time correct training data
    training_df = defs.get_training_data(
        features=[
            "customer_spend",
            "merchant_spend",
            "customer_velocity",
        ],
        entity_df=entity_df,
        timestamp="label_time",
    )

    print(f"Training DataFrame shape: {training_df.shape}")
    print(f"\nColumns ({len(training_df.columns)}):")

    # Group columns by type
    key_cols = [
        c for c in training_df.columns if c.endswith("_id") or c == "label_time"
    ]
    label_cols = ["label"] if "label" in training_df.columns else []
    feature_cols = [c for c in training_df.columns if "__" in c]

    print(f"  Keys: {key_cols}")
    print(f"  Labels: {label_cols}")
    print(f"  Features: {len(feature_cols)} rolling aggregations")

    # Show sample feature columns
    if feature_cols:
        print("\n  Sample feature columns:")
        for col in sorted(feature_cols)[:10]:
            print(f"    - {col}")
        if len(feature_cols) > 10:
            print(f"    ... and {len(feature_cols) - 10} more")

    # Step 6: Show sample data
    print("\n" + "=" * 60)
    print("Sample training data:")
    print("=" * 60)

    # Select a subset of columns for display
    display_cols = (
        ["customer_id", "label_time", "label"] + sorted(feature_cols)[:5]
        if feature_cols
        else training_df.columns[:8]
    )
    available_cols = [c for c in display_cols if c in training_df.columns]
    print(training_df.select(available_cols).head(5))

    # Step 7: Summary statistics
    print("\n" + "=" * 60)
    print("Feature statistics:")
    print("=" * 60)

    if feature_cols:
        # Show statistics for a few key features
        stats_cols = sorted(feature_cols)[:5]
        stats_df = training_df.select(stats_cols).describe()
        print(stats_df)

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)
    print(
        """
Next steps:
  1. Train a model:     uv run python src/databricks_features/train.py
  2. Online serving:    uv run python src/databricks_features/serve.py
  3. Use Databricks:    mlforge build --profile databricks

For Databricks deployment:
  - Set DATABRICKS_HOST and DATABRICKS_TOKEN environment variables
  - Features will be stored as Delta tables in Unity Catalog
  - Online Tables will be created for real-time serving
"""
    )


if __name__ == "__main__":
    main()
