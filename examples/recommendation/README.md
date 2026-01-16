# Recommendation System Example

A recommendation system using mlforge's feature store for user and item features.

## Overview

This example demonstrates:
- **User features** for personalization (engagement metrics)
- **Item features** for popularity/trending (view and purchase counts)
- **Real-time serving** for candidate scoring
- **Rolling aggregations** at multiple time windows

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Recommendation Pipeline                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │ User Events  │────▶│    User      │────▶│   Online     │    │
│  │   Source     │     │  Engagement  │     │   Store      │    │
│  └──────────────┘     └──────────────┘     │   (Redis)    │    │
│                                            │              │    │
│  ┌──────────────┐     ┌──────────────┐     │              │    │
│  │ Item Events  │────▶│    Item      │────▶│              │    │
│  │   Source     │     │  Popularity  │     └──────────────┘    │
│  └──────────────┘     └──────────────┘            │             │
│                                                   ▼             │
│                                            ┌──────────────┐    │
│                                            │   Ranking    │    │
│                                            │   Service    │    │
│                                            └──────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Features

### User Engagement

Tracks user behavior across multiple time windows:

| Feature | Windows | Description |
|---------|---------|-------------|
| `view_count__sum` | 1d, 7d, 30d | Total page views |
| `click_count__sum` | 1d, 7d, 30d | Total clicks |
| `purchase_count__sum` | 1d, 7d, 30d | Total purchases |

### Item Popularity

Tracks item popularity for trending detection:

| Feature | Windows | Description |
|---------|---------|-------------|
| `view_count__sum` | 1d, 7d, 30d | Total views |
| `purchase_count__sum` | 1d, 7d, 30d | Total purchases |

## Quick Start

### 1. Install Dependencies

From the repository root:

```bash
uv sync
```

### 2. Generate Sample Data

```bash
cd examples/recommendation
uv run python src/recommendation/generate_data.py
```

This creates:
- `data/user_events.parquet` - User interaction events
- `data/item_events.parquet` - Item interaction events

### 3. Build Features (Offline Store)

```bash
mlforge build
```

### 4. List Features

```bash
mlforge list features
```

Output:
```
Features (2):
  - user_engagement [user, engagement]
  - item_popularity [item, popularity]
```

### 5. Real-time Serving (Optional)

Start Redis:

```bash
docker-compose up -d
```

Build to online store:

```bash
mlforge build --profile online --online
```

Run serving example:

```bash
uv run python src/reco/serve.py
```

## Project Structure

```
recommendation/
├── src/reco/
│   ├── __init__.py
│   ├── entities.py        # Entity definitions
│   ├── user_features.py   # User engagement features
│   ├── item_features.py   # Item popularity features
│   ├── definitions.py     # Definitions object
│   ├── generate_data.py   # Sample data generator
│   └── serve.py           # Real-time serving example
├── data/
│   ├── user_events.parquet   # Generated user events
│   └── item_events.parquet   # Generated item events
├── feature_store/         # Built features (gitignored)
├── mlforge.yaml           # Profile configuration
├── docker-compose.yml     # Redis container
├── pyproject.toml
└── README.md
```

## Key Concepts

### 1. Event-Based Features

Transform event types into numeric counts:

```python
@mlf.feature(
    source=user_events,
    entities=[user],
    timestamp=timestamp,
    interval=timedelta(days=1),
    metrics=[engagement_metrics],
)
def user_engagement(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(
        pl.col("user_id"),
        pl.col("event_time"),
        (pl.col("event_type") == "view").cast(pl.Int32).alias("view_count"),
        (pl.col("event_type") == "click").cast(pl.Int32).alias("click_count"),
        (pl.col("event_type") == "purchase").cast(pl.Int32).alias("purchase_count"),
    )
```

### 2. Multiple Feature Modules

Organize features by domain:

```python
# definitions.py
defs = mlf.Definitions(
    name="Recommendation Features",
    features=[user_features, item_features],  # Multiple modules
)
```

### 3. Real-Time Scoring

Combine user and item features for ranking:

```python
def score_candidates(user_id, candidate_items, store):
    user_features = get_online_features(
        features=["user_engagement"],
        entity_df=pl.DataFrame({"user_id": [user_id]}),
        store=store,
        entities=[with_user_id],
    )

    item_features = get_online_features(
        features=["item_popularity"],
        entity_df=pl.DataFrame({"item_id": candidate_items}),
        store=store,
        entities=[with_item_id],
    )

    # Score: user engagement * item popularity
    ...
```

## CLI Commands

```bash
# List all features
mlforge list features

# List by tag
mlforge list features --tags "user"
mlforge list features --tags "item"

# Build user features only
mlforge build --tags "user"

# Build item features only
mlforge build --tags "item"

# Inspect feature
mlforge inspect feature user_engagement
mlforge inspect feature item_popularity

# Show profile
mlforge profile
```

## Extending the Example

### Add User-Item Interaction Features

```python
# In a new file: interaction_features.py
user_item = mlf.Entity(
    name="user_item",
    join_key=["user_id", "item_id"],
)

@mlf.feature(
    source=user_events,
    entities=[user_item],
    timestamp=timestamp,
    interval=timedelta(days=1),
    metrics=[interaction_metrics],
    tags=["interaction"],
)
def user_item_affinity(df: pl.DataFrame) -> pl.DataFrame:
    ...
```

### Add Category Features

```python
category = mlf.Entity(name="category", join_key="category_id")

@mlf.feature(
    source=item_catalog,
    entities=[category],
    tags=["category"],
)
def category_popularity(df: pl.DataFrame) -> pl.DataFrame:
    ...
```

## Cleanup

```bash
# Stop Redis
docker-compose down

# Remove feature store
rm -rf feature_store/

# Remove generated data
rm -rf data/*.parquet

# Remove Docker volumes and images (optional - frees disk space)
docker-compose down -v --rmi local
docker system prune -f
```
