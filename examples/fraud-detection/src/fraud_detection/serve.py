#!/usr/bin/env python3
"""Real-time fraud scoring with online features.

Usage:
    docker-compose up -d
    mlforge build --profile online --online
    uv run python src/fraud_detection/serve.py
"""

import polars as pl

from mlforge.online import RedisStore
from fraud_detection.definitions import defs


def main() -> None:
    store = RedisStore(host="localhost", port=6379, prefix="fraud")

    if not store.ping():
        print("Error: Cannot connect to Redis. Start with: docker-compose up -d")
        return

    print("Connected to Redis\n")

    # Sample transactions to score
    request_df = pl.DataFrame({
        "request_id": ["txn_001", "txn_002", "txn_003"],
        "first": ["Jennifer", "Stephanie", "Edward"],
        "last": ["Banks", "Gill", "Sanchez"],
        "dob": ["1988-03-09", "1978-06-22", "1962-01-19"],
        "merchant": [
            "fraud_Rippin, Kub and Mann",
            "fraud_Swaniawski, Nishi",
            "fraud_Kirlin and Sons",
        ],
        "cc_num": ["2703186189652095", "4390609500176731", "3573030041201292"],
        "amt": [125.50, 850.00, 45.00],
    })

    # Get features for all entities in one call
    result = defs.get_online_features(
        features=["user_spend", "merchant_spend", "card_velocity"],
        entity_df=request_df,
        store=store,
    )

    print("Transactions with features:")
    print(result)
    print()

    # Score each transaction
    print("Fraud Scores:")
    print("-" * 40)

    for row in result.iter_rows(named=True):
        amt = row["amt"]
        card_velocity_1d = row.get("card__amt__count__1d__1d", 0) or 0
        card_velocity_7d = row.get("card__amt__count__1d__7d", 0) or 0

        risk_score = 0.0
        if amt > 500:
            risk_score += 0.3
        if card_velocity_1d > 5:
            risk_score += 0.4
        if card_velocity_7d > 20:
            risk_score += 0.2

        risk_level = "HIGH" if risk_score > 0.5 else "MEDIUM" if risk_score > 0.2 else "LOW"
        print(f"{row['request_id']}: ${amt:.2f} -> {risk_level} ({risk_score:.2f})")


if __name__ == "__main__":
    main()
