#!/usr/bin/env python3
"""Real-time recommendation scoring with online features.

Usage:
    docker-compose up -d
    mlforge build --profile online --online
    uv run python src/recommendation/serve.py
"""

import polars as pl

from mlforge.online import RedisStore
from recommendation.definitions import defs


def main() -> None:
    store = RedisStore(host="localhost", port=6379, prefix="reco")

    if not store.ping():
        print("Error: Cannot connect to Redis. Start with: docker-compose up -d")
        return

    print("Connected to Redis\n")

    user_id = "user_001"
    candidate_items = ["item_001", "item_002", "item_003", "item_004", "item_005"]

    # Get user features
    user_features = defs.get_online_features(
        features=["user_engagement"],
        entity_df=pl.DataFrame({"user_id": [user_id]}),
        store=store,
    )

    # Get item features
    item_features = defs.get_online_features(
        features=["item_popularity"],
        entity_df=pl.DataFrame({"item_id": candidate_items}),
        store=store,
    )

    print(f"User: {user_id}")
    print(user_features)
    print()

    print("Items:")
    print(item_features)
    print()

    # Score: user engagement * item popularity
    user_engagement = 1.0
    if "user__click_count__sum__1d__7d" in user_features.columns:
        val = user_features["user__click_count__sum__1d__7d"][0]
        if val is not None:
            user_engagement = float(val) + 1

    scores = []
    for row in item_features.iter_rows(named=True):
        item_popularity = 1.0
        if row.get("item__purchase_count__sum__1d__7d") is not None:
            item_popularity = float(row["item__purchase_count__sum__1d__7d"]) + 1
        scores.append((row["item_id"], user_engagement * item_popularity))

    print("Recommendations:")
    for rank, (item_id, score) in enumerate(sorted(scores, key=lambda x: -x[1]), 1):
        print(f"  {rank}. {item_id} (score: {score:.2f})")


if __name__ == "__main__":
    main()
