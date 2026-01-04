# Feature: Online Feature Retrieval

**Version:** v0.5.0
**Status:** Planned
**Effort:** Low-Medium
**Breaking Changes:** No

## Summary

High-level `get_online_features()` function for retrieving multiple features from an online store during ML inference. Mirrors the `get_training_data()` API but for real-time serving, enabling batch feature retrieval with entity key transforms.

## Motivation

- **Complete the inference loop**: `redis-online` enables writing features to Redis, but reading requires low-level `RedisStore.read_batch()` calls
- **Consistent API**: Inference code should mirror training code - `get_training_data()` for training, `get_online_features()` for inference
- **Entity key transforms**: Reuse the same `entity_key()` transforms for inference as training
- **Batch efficiency**: Join multiple features from online store in a single call

## Design Principles

- **Mirror offline API**: Similar signature to `get_training_data()` for consistency
- **Entity transforms reuse**: Same `entity_key()` functions work for both offline and online retrieval
- **Batch-first**: Designed for batch inference, not single-entity lookups (use `store.read()` for that)
- **No point-in-time**: Online stores only hold latest values, no temporal joins needed

## API Design

### Python API

```python
from mlforge.online import RedisStore, get_online_features
from transactions.entities import with_user_id, with_merchant_id

# Initialize store
store = RedisStore(host="localhost", port=6379)

# Inference request DataFrame
request_df = pl.DataFrame({
    "request_id": ["req_1", "req_2", "req_3"],
    "user_id": ["user_123", "user_456", "user_789"],
    "merchant_id": ["merch_A", "merch_B", "merch_C"],
})

# Retrieve features for inference
features_df = get_online_features(
    features=["user_spend_30d_interval", "merchant_risk"],
    entity_df=request_df,
    entities=[with_user_id, with_merchant_id],
    store=store,
)

# Result: request_df with feature columns joined
# | request_id | user_id  | merchant_id | amount__sum__30d | risk_score |
# |------------|----------|-------------|------------------|------------|
# | req_1      | user_123 | merch_A     | 1500.0           | 0.85       |
# | req_2      | user_456 | merch_B     | 2300.0           | 0.12       |
# | req_3      | user_789 | merch_C     | None             | 0.45       |
```

### Function Signature

```python
def get_online_features(
    features: list[str],
    entity_df: pl.DataFrame,
    store: OnlineStore,
    entities: list[EntityKeyTransform] | None = None,
) -> pl.DataFrame:
    """
    Retrieve features from an online store for inference.

    Args:
        features: List of feature names to retrieve
        entity_df: DataFrame with entity keys (e.g., inference requests)
        store: Online store instance (e.g., RedisStore)
        entities: Optional entity key transforms to apply before lookup

    Returns:
        entity_df with feature columns joined (None for missing entities)

    Raises:
        ValueError: If entity transform is missing metadata
    """
```

### Comparison with Offline Retrieval

| Aspect | `get_training_data()` | `get_online_features()` |
|--------|----------------------|------------------------|
| Store type | Offline (LocalStore, S3Store) | Online (RedisStore) |
| Versioning | Yes (`("feature", "1.0.0")`) | No (always latest) |
| Point-in-time | Yes (via `timestamp`) | No (latest only) |
| Join strategy | asof/left join | Direct key lookup |
| Use case | Training data prep | Real-time inference |

## Implementation Details

### Key Files

| File | Changes |
|------|---------|
| `src/mlforge/online.py` | Add `get_online_features()` function |
| `src/mlforge/__init__.py` | Export `get_online_features` |

### Algorithm

1. Apply entity key transforms to `entity_df` (same as `get_training_data()`)
2. For each feature:
   a. Extract unique entity key combinations from `entity_df`
   b. Build entity key dicts for each combination
   c. Call `store.read_batch()` to fetch values
   d. Convert results to DataFrame and join back to `entity_df`
3. Return enriched DataFrame

### Example Implementation

```python
def get_online_features(
    features: list[str],
    entity_df: pl.DataFrame,
    store: OnlineStore,
    entities: list[EntityKeyTransform] | None = None,
) -> pl.DataFrame:
    result = entity_df

    # Apply entity key transforms
    for entity_fn in entities or []:
        if not hasattr(entity_fn, "_entity_key_columns"):
            raise ValueError(
                f"Entity transform '{entity_fn.__name__}' is missing metadata. "
                f"Use mlforge.entity_key() to create entity transforms."
            )
        result = result.pipe(entity_fn)

    for feature_name in features:
        # Get entity keys for this feature (from store metadata or feature definition)
        # For simplicity, assume first entity transform's keys
        # In practice, may need to look up feature metadata
        entity_key_columns = _get_entity_keys_for_feature(feature_name, entities)

        # Extract unique entity combinations
        unique_entities = result.select(entity_key_columns).unique()
        entity_dicts = [
            {col: str(row[col]) for col in entity_key_columns}
            for row in unique_entities.iter_rows(named=True)
        ]

        # Batch read from online store
        values = store.read_batch(feature_name, entity_dicts)

        # Build feature DataFrame
        feature_rows = []
        for entity_dict, value in zip(entity_dicts, values):
            if value is not None:
                feature_rows.append({**entity_dict, **value})

        if feature_rows:
            feature_df = pl.DataFrame(feature_rows)
            result = result.join(feature_df, on=entity_key_columns, how="left")

    return result
```

### Entity Key Resolution

The function needs to know which entity keys to use for each feature. Options:

1. **Infer from entity transforms**: Use `_entity_key_columns` from the entity transform
2. **Store metadata lookup**: Query the offline store for feature metadata
3. **Explicit mapping**: User provides feature-to-entity mapping

Recommended: Option 1 (infer from transforms) for simplicity. The entity transforms already know their key columns.

## Definition of Done

### Code
- [ ] `get_online_features()` function implemented in `online.py`
- [ ] Type hints on all parameters and return
- [ ] Docstring following Google style
- [ ] Exported from `__init__.py`
- [ ] No ruff/ty errors

### Tests
- [ ] Unit tests in `tests/test_online.py`
- [ ] Test with single feature
- [ ] Test with multiple features
- [ ] Test with entity transforms
- [ ] Test with missing entities (returns None)
- [ ] Coverage >= 80%

### Documentation
- [ ] API docs updated
- [ ] User guide section for online retrieval
- [ ] CHANGELOG entry added

### Verification
- [ ] Works in `examples/transactions-online`
- [ ] Code review completed

## Dependencies

- **Depends on:** Redis Online Store (must be complete first)
- **Blocked by:** None

## Testing Strategy

### Unit Tests

```python
def test_get_online_features_single_feature():
    """Retrieve a single feature for multiple entities."""
    store = MockOnlineStore()
    store.write("user_spend", {"user_id": "123"}, {"total": 100.0})

    request_df = pl.DataFrame({"user_id": ["123", "456"]})
    result = get_online_features(
        features=["user_spend"],
        entity_df=request_df,
        store=store,
    )

    assert "total" in result.columns
    assert result.filter(pl.col("user_id") == "123")["total"][0] == 100.0
    assert result.filter(pl.col("user_id") == "456")["total"][0] is None

def test_get_online_features_with_entity_transform():
    """Entity transforms are applied before lookup."""
    store = MockOnlineStore()
    store.write("user_spend", {"user_key": "user_123"}, {"total": 100.0})

    @entity_key(columns=["user_id"], alias="user_key")
    def with_user_key(df):
        return df.with_columns(pl.col("user_id").alias("user_key"))

    request_df = pl.DataFrame({"user_id": ["123"]})
    result = get_online_features(
        features=["user_spend"],
        entity_df=request_df,
        entities=[with_user_key],
        store=store,
    )

    assert "total" in result.columns

def test_get_online_features_multiple_features():
    """Multiple features are joined correctly."""
    store = MockOnlineStore()
    store.write("user_spend", {"user_id": "123"}, {"spend": 100.0})
    store.write("user_risk", {"user_id": "123"}, {"risk": 0.5})

    request_df = pl.DataFrame({"user_id": ["123"]})
    result = get_online_features(
        features=["user_spend", "user_risk"],
        entity_df=request_df,
        store=store,
    )

    assert "spend" in result.columns
    assert "risk" in result.columns
```

### Integration Test (with Redis)

```python
@pytest.mark.integration
def test_get_online_features_redis():
    """Full integration with real Redis."""
    store = RedisStore(host="localhost")

    # Write test data
    store.write("user_spend", {"user_id": "test_user"}, {"amount": 500.0})

    # Retrieve
    request_df = pl.DataFrame({"user_id": ["test_user", "missing_user"]})
    result = get_online_features(
        features=["user_spend"],
        entity_df=request_df,
        store=store,
    )

    assert result.filter(pl.col("user_id") == "test_user")["amount"][0] == 500.0
    assert result.filter(pl.col("user_id") == "missing_user")["amount"][0] is None
```

### Example Verification

```bash
cd examples/transactions-online

# Ensure Redis is running and features are built
docker-compose up -d
uv run mlforge build --online

# Run the read_features.py script (update to use get_online_features)
uv run python src/transactions_online/read_features.py
```

## Future Considerations

- **Feature metadata from online store**: Store feature schemas in Redis for runtime validation
- **Async support**: `async def get_online_features_async()` for high-throughput serving
- **Caching**: Optional in-memory cache for frequently accessed features
- **Metrics**: Track latency, hit rate, and feature freshness
