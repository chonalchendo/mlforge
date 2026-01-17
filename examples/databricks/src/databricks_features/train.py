#!/usr/bin/env python3
"""Train fraud detection model using mlforge features.

This script demonstrates:
1. Loading transactions with fraud labels
2. Retrieving point-in-time correct training features
3. Training a RandomForest classifier
4. Evaluating model performance
5. Analyzing feature importance

The key benefit of mlforge is ensuring no data leakage - features are
computed as-of the transaction time, not using future data.

Usage:
    # First build features
    mlforge build

    # Then train model
    uv run python src/databricks_features/train.py
"""

from pathlib import Path

import polars as pl
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

from databricks_features.definitions import defs
from databricks_features.generate_data import generate_transactions


def main() -> None:
    data_path = Path("data/transactions.parquet")

    # Generate data if needed
    if not data_path.exists():
        print("Generating sample data...")
        df = generate_transactions(n_rows=5000)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(data_path)

    # Load transactions with fraud labels
    print("Loading transaction data...")
    transactions_df = pl.read_parquet(data_path)

    # Create entity DataFrame for training
    # Each row represents a transaction to score, with features computed
    # as-of the transaction_time (point-in-time correctness)
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
        pl.col("amount"),  # Keep for feature engineering
    )

    print(f"Total transactions: {entity_df.shape[0]:,}")
    print(f"Fraud rate: {entity_df['label'].mean():.2%}")

    # Get point-in-time correct training data
    print("\nRetrieving training features...")
    training_df = defs.get_training_data(
        features=[
            "customer_spend",
            "merchant_spend",
            "customer_velocity",
        ],
        entity_df=entity_df,
        timestamp="label_time",
    )

    print(f"Training data shape: {training_df.shape}")

    # Identify feature columns (rolling aggregations contain __)
    feature_cols = [c for c in training_df.columns if "__" in c]
    print(f"Number of features: {len(feature_cols)}")

    # Add raw amount as a feature
    if "amount" in training_df.columns:
        feature_cols.append("amount")

    # Prepare data for training
    training_df = training_df.fill_null(0)  # Fill nulls from rolling windows

    X = training_df.select(feature_cols).to_numpy()
    y = training_df["label"].to_numpy()

    # Train/test split with stratification
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"\nTraining set: {len(X_train):,} samples")
    print(f"Test set: {len(X_test):,} samples")
    print(f"Training fraud rate: {y_train.mean():.2%}")
    print(f"Test fraud rate: {y_test.mean():.2%}")

    # Train RandomForest
    print("\nTraining RandomForest classifier...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_leaf=10,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",  # Handle imbalanced classes
    )
    model.fit(X_train, y_train)

    # Evaluate
    print("\n" + "=" * 60)
    print("Model Performance")
    print("=" * 60)

    train_acc = model.score(X_train, y_train)
    test_acc = model.score(X_test, y_test)
    print(f"Train accuracy: {train_acc:.3f}")
    print(f"Test accuracy:  {test_acc:.3f}")

    # ROC AUC
    y_prob = model.predict_proba(X_test)[:, 1]
    roc_auc = roc_auc_score(y_test, y_prob)
    print(f"ROC AUC: {roc_auc:.3f}")

    # Classification report
    y_pred = model.predict(X_test)
    print("\nClassification Report:")
    print(
        classification_report(
            y_test, y_pred, target_names=["Legitimate", "Fraud"]
        )
    )

    # Feature importance
    print("=" * 60)
    print("Top 15 Feature Importances")
    print("=" * 60)

    importances = sorted(
        zip(feature_cols, model.feature_importances_, strict=False),
        key=lambda x: -x[1],
    )

    for name, importance in importances[:15]:
        bar = "#" * int(importance * 100)
        print(f"  {name:45} {importance:.4f} {bar}")

    # Feature category analysis
    print("\n" + "=" * 60)
    print("Feature Importance by Category")
    print("=" * 60)

    categories = {
        "customer_spend": 0.0,
        "merchant_spend": 0.0,
        "customer_velocity": 0.0,
        "raw_features": 0.0,
    }

    for name, importance in importances:
        if name == "amount":
            categories["raw_features"] += importance
        elif "customer__" in name and "velocity" not in name.lower():
            # Check if it's a spending feature vs velocity
            if "count__1d" in name or "count__7d" in name:
                categories["customer_velocity"] += importance
            else:
                categories["customer_spend"] += importance
        elif "merchant__" in name:
            categories["merchant_spend"] += importance
        else:
            categories["raw_features"] += importance

    for category, total_importance in sorted(
        categories.items(), key=lambda x: -x[1]
    ):
        bar = "#" * int(total_importance * 50)
        print(f"  {category:25} {total_importance:.4f} {bar}")

    print(
        """
Model insights:
- Rolling aggregations capture behavioral patterns over time
- Velocity features (transaction counts) are key fraud signals
- Merchant-level features provide context about typical transaction patterns
- Point-in-time correctness ensures no data leakage from future transactions

To deploy this model:
1. Build features to Databricks: mlforge build --profile databricks
2. Sync to Online Tables for real-time serving
3. Use get_online_features() for inference (see serve.py)
"""
    )


if __name__ == "__main__":
    main()
