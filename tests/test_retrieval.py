import tempfile
from datetime import datetime

import polars as pl

from mlforge import LocalStore, get_training_data
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
        store.write("user_spend_mean_30d", PolarsResult(feature_df))

        # Entity data: transactions at various times
        entity_df = pl.DataFrame(
            {
                "user_id": ["user_1", "user_1", "user_1", "user_2"],
                "transaction_id": ["t1", "t2", "t3", "t4"],
                "event_time": [
                    datetime(2024, 1, 5),  # should get 100 (Jan 1 value)
                    datetime(2024, 1, 15),  # should get 200 (Jan 15 value, exact match)
                    datetime(2024, 1, 20),  # should get 200 (Jan 15 value)
                    datetime(2024, 1, 5),  # should get null (no data before Jan 10)
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
        store.write("some_feature", PolarsResult(feature_df))

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
        store.write("user_total_spend", PolarsResult(feature_df))

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
