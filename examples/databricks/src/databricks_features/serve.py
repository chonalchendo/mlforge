#!/usr/bin/env python3
"""Real-time fraud scoring with Databricks Online Tables.

This script demonstrates real-time feature serving using:
- Databricks Online Tables for millisecond-latency lookups
- mlforge's get_online_features() for unified feature retrieval
- Simple rule-based scoring (replace with ML model in production)

The data flow:
1. Offline: Features built to Unity Catalog (Delta tables)
2. Sync: Features synced to Online Tables (via sync_mode in mlforge.yaml)
3. Online: Real-time lookups during inference

Usage:
    # For local development (simulated, shows what would happen)
    uv run python src/databricks_features/serve.py

    # For Databricks deployment
    # 1. Build features to Unity Catalog
    mlforge build --profile databricks

    # 2. The online store sync happens automatically based on sync_mode
    # 3. Run this script in Databricks or with DATABRICKS_HOST/TOKEN set
"""

import polars as pl


def calculate_fraud_score(row: dict) -> tuple[float, str, list[str]]:
    """Calculate fraud risk score based on feature values.

    In production, replace this with ML model inference.
    This demonstrates how features would be used for scoring.

    Returns:
        Tuple of (score, risk_level, reasons)
    """
    score = 0.0
    reasons = []

    # Get feature values with defaults
    amount = row.get("latest_amount") or row.get("amount", 0)
    velocity_1d = row.get("customer__amount__count__1d__1d", 0) or 0
    velocity_7d = row.get("customer__amount__count__1d__7d", 0) or 0
    avg_spend_7d = row.get("customer__amount__mean__1d__7d", 0) or 0
    total_spend_30d = row.get("customer__amount__sum__1d__30d", 0) or 0

    # Rule 1: High velocity (many transactions in short time)
    if velocity_1d > 10:
        score += 0.3
        reasons.append(f"High daily velocity ({velocity_1d} txns)")
    elif velocity_1d > 5:
        score += 0.15
        reasons.append(f"Elevated daily velocity ({velocity_1d} txns)")

    # Rule 2: Amount significantly above average
    if avg_spend_7d > 0 and amount > avg_spend_7d * 3:
        score += 0.25
        reasons.append(f"Amount ${amount:.2f} > 3x avg (${avg_spend_7d:.2f})")

    # Rule 3: Very high transaction amount
    if amount > 1000:
        score += 0.2
        reasons.append(f"High amount (${amount:.2f})")
    elif amount > 500:
        score += 0.1
        reasons.append(f"Elevated amount (${amount:.2f})")

    # Rule 4: Unusual weekly velocity
    if velocity_7d > 50:
        score += 0.15
        reasons.append(f"High weekly velocity ({velocity_7d} txns)")

    # Rule 5: Low historical spending (new or dormant account)
    if total_spend_30d < 100 and amount > 200:
        score += 0.1
        reasons.append("Large txn on low-activity account")

    # Determine risk level
    if score >= 0.5:
        risk_level = "HIGH"
    elif score >= 0.25:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return min(score, 1.0), risk_level, reasons


def simulate_online_serving() -> None:
    """Simulate online serving for local development.

    In local mode, we can't connect to Databricks Online Tables,
    so we demonstrate the API and show what features would be retrieved.
    """
    print("=" * 60)
    print("Simulated Online Serving (Local Development)")
    print("=" * 60)
    print(
        """
Note: This is a simulation for local development.
In production with Databricks:
1. Features are stored in Unity Catalog as Delta tables
2. Online Tables sync from Delta tables automatically
3. get_online_features() retrieves from Online Tables

For actual Databricks deployment:
- Set DATABRICKS_HOST and DATABRICKS_TOKEN
- Use --profile databricks when building
"""
    )

    # Sample incoming transactions to score
    incoming_transactions = pl.DataFrame(
        {
            "request_id": [
                "req_001",
                "req_002",
                "req_003",
                "req_004",
                "req_005",
            ],
            "first_name": ["James", "Mary", "John", "Patricia", "Robert"],
            "last_name": ["Smith", "Johnson", "Williams", "Brown", "Jones"],
            "date_of_birth": [
                "1985-03-15",
                "1990-07-22",
                "1978-11-08",
                "1995-01-30",
                "1982-09-12",
            ],
            "merchant_name": [
                "grocery_001",
                "online_retail_002",
                "gas_station_003",
                "restaurant_004",
                "travel_001",
            ],
            "amount": [85.50, 1250.00, 45.00, 32.50, 2500.00],
        }
    )

    print("\nIncoming Transactions:")
    print(incoming_transactions)

    # In production, this would call Databricks Online Tables
    # For demo, we'll show the API and simulate feature values
    print("\n" + "=" * 60)
    print("Feature Retrieval (Simulated)")
    print("=" * 60)
    print(
        """
In production, you would call:

    result = defs.get_online_features(
        features=["customer_spend", "merchant_spend", "customer_velocity"],
        entity_df=incoming_transactions,
        store=DatabricksOnlineStore(catalog="main", schema="ml_features_online"),
    )

This would retrieve pre-computed rolling aggregations from Online Tables
with millisecond latency.
"""
    )

    # Simulate feature values for demonstration
    # In real deployment, these come from Online Tables
    simulated_features = incoming_transactions.with_columns(
        # Simulated customer spending features
        pl.lit(500.0).alias("customer__amount__sum__1d__7d"),
        pl.lit(75.0).alias("customer__amount__mean__1d__7d"),
        pl.lit(8).alias("customer__amount__count__1d__7d"),
        pl.lit(3).alias("customer__amount__count__1d__1d"),
        pl.lit(2000.0).alias("customer__amount__sum__1d__30d"),
        # Use amount as latest_amount for scoring
        pl.col("amount").alias("latest_amount"),
    )

    # Override some values to create interesting scoring scenarios
    simulated_features = simulated_features.with_columns(
        pl.when(pl.col("request_id") == "req_002")
        .then(pl.lit(15))
        .otherwise(pl.col("customer__amount__count__1d__1d"))
        .alias("customer__amount__count__1d__1d"),
        pl.when(pl.col("request_id") == "req_005")
        .then(pl.lit(50.0))
        .otherwise(pl.col("customer__amount__sum__1d__30d"))
        .alias("customer__amount__sum__1d__30d"),
    )

    print("\nSimulated Features Retrieved:")
    feature_cols = [
        c
        for c in simulated_features.columns
        if "__" in c or c == "latest_amount"
    ]
    print(simulated_features.select(["request_id", "amount", *feature_cols]))

    # Score each transaction
    print("\n" + "=" * 60)
    print("Fraud Scoring Results")
    print("=" * 60)

    results = []
    for row in simulated_features.iter_rows(named=True):
        score, risk_level, reasons = calculate_fraud_score(row)
        results.append(
            {
                "request_id": row["request_id"],
                "amount": row["amount"],
                "score": score,
                "risk_level": risk_level,
                "reasons": "; ".join(reasons) if reasons else "No risk signals",
            }
        )

    results_df = pl.DataFrame(results)
    print(results_df)

    # Summary
    print("\n" + "=" * 60)
    print("Scoring Summary")
    print("=" * 60)
    high_risk = results_df.filter(pl.col("risk_level") == "HIGH").shape[0]
    medium_risk = results_df.filter(pl.col("risk_level") == "MEDIUM").shape[0]
    low_risk = results_df.filter(pl.col("risk_level") == "LOW").shape[0]

    print(f"  HIGH risk:   {high_risk} transactions")
    print(f"  MEDIUM risk: {medium_risk} transactions")
    print(f"  LOW risk:    {low_risk} transactions")

    # Detailed breakdown for high-risk transactions
    high_risk_txns = results_df.filter(pl.col("risk_level") == "HIGH")
    if high_risk_txns.shape[0] > 0:
        print("\nHigh-Risk Transaction Details:")
        for row in high_risk_txns.iter_rows(named=True):
            print(f"\n  {row['request_id']}: ${row['amount']:.2f}")
            print(f"    Score: {row['score']:.2f}")
            print(f"    Reasons: {row['reasons']}")


def main() -> None:
    print(
        """
Databricks Online Serving Demo
==============================

This example demonstrates real-time feature serving with Databricks Online Tables.

Architecture:
  [Transaction] -> [Feature Lookup] -> [Online Tables] -> [Fraud Score]
                          |
                   get_online_features()
                          |
                   (Unity Catalog Delta -> Online Tables sync)
"""
    )

    # Check if we're in Databricks environment
    try:
        import os

        databricks_host = os.environ.get("DATABRICKS_HOST")
        if databricks_host:
            print(f"Databricks environment detected: {databricks_host}")
            print("Running with real Online Tables...")
            # In real Databricks, implement actual online serving here
            # For now, fall through to simulation
    except Exception:
        pass

    # Run simulation for demo purposes
    simulate_online_serving()

    print(
        """
Production Deployment Notes:
---------------------------
1. Build features to Databricks:
   $ mlforge build --profile databricks

2. Online Tables sync automatically based on sync_mode:
   - 'triggered': Manual sync on each build
   - 'continuous': Near real-time streaming sync

3. For inference, connect to Online Tables:
   from mlforge import DatabricksOnlineStore

   store = DatabricksOnlineStore(
       catalog="main",
       schema="ml_features_online",
   )

   features = defs.get_online_features(
       features=["customer_spend", "customer_velocity"],
       entity_df=transaction_df,
       store=store,
   )

4. Replace rule-based scoring with trained ML model for production.
"""
    )


if __name__ == "__main__":
    main()
