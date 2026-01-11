#!/usr/bin/env python3
"""Generate sample data for recommendation example.

Creates user_events.parquet and item_events.parquet with realistic
e-commerce event data.

Usage:
    uv run python src/reco/generate_data.py
"""

import random
from datetime import datetime, timedelta

import polars as pl


def generate_user_events(
    n_users: int = 100,
    n_items: int = 50,
    n_events: int = 5000,
    start_date: datetime = datetime(2024, 1, 1),
    end_date: datetime = datetime(2024, 3, 31),
) -> pl.DataFrame:
    """Generate user event data.

    Event types follow a funnel pattern:
    - view: 70% of events
    - click: 25% of events
    - purchase: 5% of events
    """
    random.seed(42)

    user_ids = [f"user_{i:03d}" for i in range(1, n_users + 1)]
    item_ids = [f"item_{i:03d}" for i in range(1, n_items + 1)]

    # Event type distribution (funnel)
    event_types = ["view"] * 70 + ["click"] * 25 + ["purchase"] * 5

    events = []
    for _ in range(n_events):
        # Random timestamp within range
        delta = end_date - start_date
        random_seconds = random.randint(0, int(delta.total_seconds()))
        event_time = start_date + timedelta(seconds=random_seconds)

        events.append(
            {
                "user_id": random.choice(user_ids),
                "item_id": random.choice(item_ids),
                "event_type": random.choice(event_types),
                "event_time": event_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    # Sort by time
    events.sort(key=lambda x: x["event_time"])

    return pl.DataFrame(events)


def generate_item_events(user_events: pl.DataFrame) -> pl.DataFrame:
    """Generate item event data from user events.

    Groups events by item_id for item-centric features.
    """
    return user_events.select(
        pl.col("item_id"),
        pl.col("event_type"),
        pl.col("event_time"),
    )


def main() -> None:
    print("Generating sample data for recommendation example...")

    # Generate user events
    user_events = generate_user_events()
    print(f"Generated {len(user_events)} user events")
    print(f"  Users: {user_events['user_id'].n_unique()}")
    print(f"  Items: {user_events['item_id'].n_unique()}")
    print(f"  Event types: {user_events['event_type'].value_counts()}")

    # Save user events
    user_events.write_parquet("data/user_events.parquet")
    print("\nSaved data/user_events.parquet")

    # Generate item events (same data, different perspective)
    item_events = generate_item_events(user_events)
    item_events.write_parquet("data/item_events.parquet")
    print("Saved data/item_events.parquet")

    # Preview
    print("\n--- Sample User Events ---")
    print(user_events.head(10))


if __name__ == "__main__":
    main()
