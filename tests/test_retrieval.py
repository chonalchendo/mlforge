import tempfile
from datetime import datetime
from typing import Any

import polars as pl

from mlforge import (
    LocalStore,
    entity_key,
    get_online_features,
    get_training_data,
)
from mlforge.online import OnlineStore
from mlforge.results import PolarsResult


def test_asof_join_point_in_time():
    """Verify point-in-time join returns correct historical values."""

    # Create a temp feature store
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(path=tmpdir)

        # Feature data: user_id with values at specific timestamps
        # user_1 had spend_mean of 100 on Jan 1, then 200 on Jan 15
        feature_df = pl.DataFrame(
            {
                "user_id": ["user_1", "user_1", "user_2"],
                "user_spend_mean_30d": [100.0, 200.0, 50.0],
                "feature_timestamp": [
                    datetime(2024, 1, 1),
                    datetime(2024, 1, 15),
                    datetime(2024, 1, 10),
                ],
            }
        )
        store.write(
            "user_spend_mean_30d",
            PolarsResult(feature_df),
            feature_version="1.0.0",
        )

        # Entity data: transactions at various times
        entity_df = pl.DataFrame(
            {
                "user_id": ["user_1", "user_1", "user_1", "user_2"],
                "transaction_id": ["t1", "t2", "t3", "t4"],
                "event_time": [
                    datetime(2024, 1, 5),  # should get 100 (Jan 1 value)
                    datetime(
                        2024, 1, 15
                    ),  # should get 200 (Jan 15 value, exact match)
                    datetime(2024, 1, 20),  # should get 200 (Jan 15 value)
                    datetime(
                        2024, 1, 5
                    ),  # should get null (no data before Jan 10)
                ],
            }
        )

        result = get_training_data(
            features=["user_spend_mean_30d"],
            entity_df=entity_df,
            store=store,
            timestamp="event_time",
        )

        # Verify results
        result_sorted = result.sort("transaction_id")

        assert result_sorted["user_spend_mean_30d"].to_list() == [
            100.0,
            200.0,
            200.0,
            None,
        ]


def test_asof_join_no_future_leakage():
    """Verify we never join future feature values."""

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(path=tmpdir)

        # Feature only available on Jan 15
        feature_df = pl.DataFrame(
            {
                "user_id": ["user_1"],
                "some_feature": [999.0],
                "feature_timestamp": [datetime(2024, 1, 15)],
            }
        )
        store.write(
            "some_feature", PolarsResult(feature_df), feature_version="1.0.0"
        )

        # Transaction on Jan 10 - before feature exists
        entity_df = pl.DataFrame(
            {
                "user_id": ["user_1"],
                "event_time": [datetime(2024, 1, 10)],
            }
        )

        result = get_training_data(
            features=["some_feature"],
            entity_df=entity_df,
            store=store,
            timestamp="event_time",
        )

        # Should be null - no future leakage
        assert result["some_feature"].to_list() == [None]


def test_standard_join_without_timestamp():
    """Verify standard join works when no timestamp provided."""

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(path=tmpdir)

        feature_df = pl.DataFrame(
            {
                "user_id": ["user_1", "user_2"],
                "user_total_spend": [500.0, 300.0],
            }
        )
        store.write(
            "user_total_spend",
            PolarsResult(feature_df),
            feature_version="1.0.0",
        )

        entity_df = pl.DataFrame(
            {
                "user_id": ["user_1", "user_2", "user_3"],
                "label": [1, 0, 1],
            }
        )

        result = get_training_data(
            features=["user_total_spend"],
            entity_df=entity_df,
            store=store,
        )

        assert result["user_total_spend"].to_list() == [500.0, 300.0, None]


# =============================================================================
# Mock Online Store for Testing
# =============================================================================


class MockOnlineStore(OnlineStore):
    """In-memory online store for testing."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, Any]]] = {}

    def write(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
        values: dict[str, Any],
    ) -> None:
        if feature_name not in self._data:
            self._data[feature_name] = {}
        key = self._make_key(entity_keys)
        self._data[feature_name][key] = values

    def write_batch(
        self,
        feature_name: str,
        records: list[dict[str, Any]],
        entity_key_columns: list[str],
    ) -> int:
        for record in records:
            entity_keys = {col: str(record[col]) for col in entity_key_columns}
            values = {
                k: v for k, v in record.items() if k not in entity_key_columns
            }
            self.write(feature_name, entity_keys, values)
        return len(records)

    def read(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> dict[str, Any] | None:
        if feature_name not in self._data:
            return None
        key = self._make_key(entity_keys)
        return self._data[feature_name].get(key)

    def read_batch(
        self,
        feature_name: str,
        entity_keys: list[dict[str, str]],
    ) -> list[dict[str, Any] | None]:
        return [self.read(feature_name, keys) for keys in entity_keys]

    def delete(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> bool:
        if feature_name not in self._data:
            return False
        key = self._make_key(entity_keys)
        if key in self._data[feature_name]:
            del self._data[feature_name][key]
            return True
        return False

    def exists(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> bool:
        if feature_name not in self._data:
            return False
        key = self._make_key(entity_keys)
        return key in self._data[feature_name]

    def _make_key(self, entity_keys: dict[str, str]) -> str:
        return "|".join(f"{k}={v}" for k, v in sorted(entity_keys.items()))


# =============================================================================
# get_online_features Tests
# =============================================================================


def test_get_online_features_single_feature():
    """Retrieve a single feature for multiple entities."""
    # Given an entity transform
    with_user_key = entity_key("user_id", alias="user_key")

    # Pre-compute hashed keys for known users
    users_df = pl.DataFrame({"user_id": ["user_123", "user_456", "user_789"]})
    hashed = users_df.pipe(with_user_key)
    key_123 = hashed.filter(pl.col("user_id") == "user_123")["user_key"][0]
    key_456 = hashed.filter(pl.col("user_id") == "user_456")["user_key"][0]

    # And an online store with feature data stored under hashed keys
    store = MockOnlineStore()
    store.write("user_spend", {"user_key": key_123}, {"total": 100.0})
    store.write("user_spend", {"user_key": key_456}, {"total": 200.0})
    # user_789 is NOT in the store

    # When retrieving features
    request_df = pl.DataFrame({"user_id": ["user_123", "user_456", "user_789"]})
    result = get_online_features(
        features=["user_spend"],
        entity_df=request_df,
        store=store,
        entities=[with_user_key],
    )

    # Then features are joined correctly
    assert "total" in result.columns
    assert len(result) == 3
    # Check values by original user_id
    assert result.filter(pl.col("user_id") == "user_123")["total"][0] == 100.0
    assert result.filter(pl.col("user_id") == "user_456")["total"][0] == 200.0
    assert result.filter(pl.col("user_id") == "user_789")["total"][0] is None


def test_get_online_features_multiple_features():
    """Multiple features are joined correctly."""
    # Given an entity transform
    with_user_key = entity_key("user_id", alias="user_key")

    # Pre-compute hashed key
    key_123 = pl.DataFrame({"user_id": ["user_123"]}).pipe(with_user_key)[
        "user_key"
    ][0]

    # And an online store with multiple features
    store = MockOnlineStore()
    store.write("user_spend", {"user_key": key_123}, {"spend": 100.0})
    store.write("user_risk", {"user_key": key_123}, {"risk_score": 0.5})

    # When retrieving multiple features
    request_df = pl.DataFrame({"user_id": ["user_123"]})
    result = get_online_features(
        features=["user_spend", "user_risk"],
        entity_df=request_df,
        store=store,
        entities=[with_user_key],
    )

    # Then both feature columns are present
    assert "spend" in result.columns
    assert "risk_score" in result.columns
    assert result["spend"][0] == 100.0
    assert result["risk_score"][0] == 0.5


def test_get_online_features_missing_entities_return_none():
    """Missing entities return None values."""
    # Given an entity transform
    with_user_key = entity_key("user_id", alias="user_key")

    # Pre-compute hashed key for user_123 only
    key_123 = pl.DataFrame({"user_id": ["user_123"]}).pipe(with_user_key)[
        "user_key"
    ][0]

    # And an online store with partial data (only user_123)
    store = MockOnlineStore()
    store.write("user_spend", {"user_key": key_123}, {"total": 100.0})
    # user_456 is NOT in the store

    # When retrieving features for both existing and missing entities
    request_df = pl.DataFrame({"user_id": ["user_123", "user_456"]})
    result = get_online_features(
        features=["user_spend"],
        entity_df=request_df,
        store=store,
        entities=[with_user_key],
    )

    # Then missing entities have None values
    assert result.filter(pl.col("user_id") == "user_123")["total"][0] == 100.0
    assert result.filter(pl.col("user_id") == "user_456")["total"][0] is None


def test_get_online_features_with_entity_transform():
    """Entity transforms are applied before lookup."""
    # Given an online store with hashed user keys
    store = MockOnlineStore()

    # Create entity transform that hashes the user_id
    with_user_key = entity_key("first_name", "last_name", alias="user_key")

    # Pre-compute what the hash would be and store under that key
    test_df = pl.DataFrame({"first_name": ["John"], "last_name": ["Doe"]})
    transformed = test_df.pipe(with_user_key)
    user_key_value = transformed["user_key"][0]

    store.write("user_spend", {"user_key": user_key_value}, {"total": 500.0})

    # When retrieving features with entity transform
    request_df = pl.DataFrame({"first_name": ["John"], "last_name": ["Doe"]})
    result = get_online_features(
        features=["user_spend"],
        entity_df=request_df,
        store=store,
        entities=[with_user_key],
    )

    # Then entity transform is applied and features are joined
    assert "total" in result.columns
    assert result["total"][0] == 500.0


def test_get_online_features_preserves_entity_df_columns():
    """Original entity_df columns are preserved in result."""
    # Given an entity transform
    with_user_key = entity_key("user_id", alias="user_key")

    # Pre-compute hashed key
    key_123 = pl.DataFrame({"user_id": ["user_123"]}).pipe(with_user_key)[
        "user_key"
    ][0]

    # And an online store with feature data
    store = MockOnlineStore()
    store.write("user_spend", {"user_key": key_123}, {"total": 100.0})

    # When retrieving features for a request with extra columns
    request_df = pl.DataFrame(
        {
            "request_id": ["req_1"],
            "user_id": ["user_123"],
            "timestamp": [datetime(2024, 1, 1)],
        }
    )
    result = get_online_features(
        features=["user_spend"],
        entity_df=request_df,
        store=store,
        entities=[with_user_key],
    )

    # Then all original columns are preserved
    assert "request_id" in result.columns
    assert "user_id" in result.columns
    assert "timestamp" in result.columns
    assert "total" in result.columns
    assert "user_key" in result.columns  # Entity transform adds this column


def test_get_online_features_empty_entity_df():
    """Empty entity_df returns empty result."""
    store = MockOnlineStore()
    with_user_id = entity_key("user_id", alias="user_id")

    # When retrieving features for empty DataFrame
    request_df = pl.DataFrame({"user_id": []}).cast({"user_id": pl.Utf8})
    result = get_online_features(
        features=["user_spend"],
        entity_df=request_df,
        store=store,
        entities=[with_user_id],
    )

    # Then result is empty
    assert len(result) == 0


def test_get_online_features_duplicate_entities():
    """Duplicate entities in entity_df are handled correctly."""
    # Given an entity transform
    with_user_key = entity_key("user_id", alias="user_key")

    # Pre-compute hashed key
    key_123 = pl.DataFrame({"user_id": ["user_123"]}).pipe(with_user_key)[
        "user_key"
    ][0]

    # And an online store with feature data
    store = MockOnlineStore()
    store.write("user_spend", {"user_key": key_123}, {"total": 100.0})

    # When retrieving features with duplicate entity rows
    request_df = pl.DataFrame(
        {
            "request_id": ["req_1", "req_2", "req_3"],
            "user_id": ["user_123", "user_123", "user_123"],
        }
    )
    result = get_online_features(
        features=["user_spend"],
        entity_df=request_df,
        store=store,
        entities=[with_user_key],
    )

    # Then all rows get the feature value
    assert len(result) == 3
    assert result["total"].to_list() == [100.0, 100.0, 100.0]


def test_get_online_features_raises_without_entities():
    """Raises ValueError when no entity transforms provided."""
    store = MockOnlineStore()
    request_df = pl.DataFrame({"user_id": ["user_123"]})

    # When retrieving features without entities parameter
    # Then ValueError is raised
    import pytest

    with pytest.raises(ValueError, match="Cannot determine entity keys"):
        get_online_features(
            features=["user_spend"],
            entity_df=request_df,
            store=store,
            entities=None,
        )


def test_get_online_features_raises_for_invalid_entity_transform():
    """Raises ValueError for entity transform without metadata."""
    store = MockOnlineStore()
    request_df = pl.DataFrame({"user_id": ["user_123"]})

    # Create a plain function without entity_key metadata
    def bad_transform(df: pl.DataFrame) -> pl.DataFrame:
        return df

    # When retrieving features with invalid entity transform
    # Then ValueError is raised
    import pytest

    with pytest.raises(ValueError, match="missing metadata"):
        get_online_features(
            features=["user_spend"],
            entity_df=request_df,
            store=store,
            entities=[bad_transform],  # type: ignore
        )


def test_get_online_features_raises_for_missing_columns():
    """Raises ValueError when entity_df missing required columns."""
    store = MockOnlineStore()
    with_user_id = entity_key("user_id", "account_id", alias="user_key")

    # When retrieving features with missing columns
    request_df = pl.DataFrame({"user_id": ["user_123"]})  # missing account_id

    # Then ValueError is raised
    import pytest

    with pytest.raises(ValueError, match="missing"):
        get_online_features(
            features=["user_spend"],
            entity_df=request_df,
            store=store,
            entities=[with_user_id],
        )
