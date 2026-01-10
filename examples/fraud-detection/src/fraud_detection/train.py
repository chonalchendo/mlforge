#!/usr/bin/env python3
"""Train fraud detection model using mlforge features.

Usage:
    mlforge build
    uv run python src/fraud_detection/train.py
"""

import polars as pl
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

from fraud_detection.definitions import defs


def main() -> None:
    # Load transactions with simulated labels
    entity_df = pl.read_parquet("data/transactions.parquet").with_columns(
        pl.col("trans_date_trans_time").str.to_datetime("%Y-%m-%d %H:%M:%S"),
        (pl.col("amt") > 500).cast(pl.Int32).alias("is_fraud"),
    )

    print(f"Transactions: {entity_df.shape[0]}, Fraud rate: {entity_df['is_fraud'].mean():.2%}")

    # Get point-in-time correct training data
    training_df = defs.get_training_data(
        features=["user_spend", "merchant_spend", "card_velocity"],
        entity_df=entity_df,
        timestamp="trans_date_trans_time",
    )

    # Select feature columns (aggregations contain __)
    feature_cols = [c for c in training_df.columns if "__" in c]
    print(f"Features: {len(feature_cols)}")

    # Prepare data
    training_df = training_df.fill_null(0)
    X = training_df.select(feature_cols).to_numpy()
    y = training_df["is_fraud"].to_numpy()

    # Train
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    print(f"Train accuracy: {model.score(X_train, y_train):.3f}")
    print(f"Test accuracy:  {model.score(X_test, y_test):.3f}")

    # Top features
    importances = sorted(zip(feature_cols, model.feature_importances_), key=lambda x: -x[1])
    print("\nTop 5 features:")
    for name, imp in importances[:5]:
        print(f"  {name}: {imp:.4f}")


if __name__ == "__main__":
    main()
