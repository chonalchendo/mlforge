"""Tests for Entity class and entity-based feature definitions."""

import tempfile
from pathlib import Path

import polars as pl
import pytest
from pydantic import ValidationError

from mlforge import Definitions, Entity, Feature, LocalStore, feature


# =============================================================================
# Entity Class Validation Tests
# =============================================================================


def test_entity_simple_join_key():
    """Entity with simple string join_key."""
    entity = Entity(name="user", join_key="user_id")

    assert entity.name == "user"
    assert entity.join_key == "user_id"
    assert entity.from_columns is None
    assert entity.key_columns == ["user_id"]
    assert entity.requires_generation is False


def test_entity_composite_join_key():
    """Entity with composite join_key (list of columns)."""
    entity = Entity(
        name="user_merchant",
        join_key=["user_id", "merchant_id"],
    )

    assert entity.name == "user_merchant"
    assert entity.join_key == ["user_id", "merchant_id"]
    assert entity.key_columns == ["user_id", "merchant_id"]
    assert entity.requires_generation is False


def test_entity_with_from_columns():
    """Entity with from_columns for surrogate key generation."""
    entity = Entity(
        name="user",
        join_key="user_id",
        from_columns=["first_name", "last_name", "dob"],
    )

    assert entity.name == "user"
    assert entity.join_key == "user_id"
    assert entity.from_columns == ["first_name", "last_name", "dob"]
    assert entity.requires_generation is True


def test_entity_is_frozen():
    """Entity should be immutable (frozen)."""
    entity = Entity(name="user", join_key="user_id")

    with pytest.raises(ValidationError):
        entity.name = "changed"  # type: ignore[misc]


def test_entity_rejects_empty_name():
    """Entity name cannot be empty."""
    with pytest.raises(
        ValidationError, match="String should have at least 1 character"
    ):
        Entity(name="", join_key="user_id")


def test_entity_rejects_empty_join_key_string():
    """Entity join_key string cannot be empty."""
    with pytest.raises(ValidationError, match="join_key cannot be empty"):
        Entity(name="user", join_key="")


def test_entity_rejects_empty_join_key_list():
    """Entity join_key list cannot be empty."""
    with pytest.raises(ValidationError, match="join_key list cannot be empty"):
        Entity(name="user", join_key=[])


def test_entity_rejects_empty_string_in_join_key_list():
    """Entity join_key list cannot contain empty strings."""
    with pytest.raises(
        ValidationError, match="join_key list cannot contain empty strings"
    ):
        Entity(name="user", join_key=["user_id", ""])


def test_entity_rejects_empty_from_columns_list():
    """Entity from_columns cannot be empty list."""
    with pytest.raises(
        ValidationError, match="from_columns cannot be empty list"
    ):
        Entity(name="user", join_key="user_id", from_columns=[])


def test_entity_rejects_empty_string_in_from_columns():
    """Entity from_columns cannot contain empty strings."""
    with pytest.raises(
        ValidationError, match="from_columns cannot contain empty strings"
    ):
        Entity(name="user", join_key="user_id", from_columns=["first", ""])


def test_entity_rejects_from_columns_with_composite_key():
    """Cannot use from_columns with composite join_key."""
    with pytest.raises(
        ValidationError,
        match="Cannot use from_columns with composite join_key",
    ):
        Entity(
            name="user",
            join_key=["user_id", "merchant_id"],
            from_columns=["first", "last"],
        )


# =============================================================================
# Feature Decorator with Entities Tests
# =============================================================================


def test_feature_decorator_with_entities():
    """Feature decorator accepts entities parameter."""
    user = Entity(name="user", join_key="user_id")

    @feature(source="data.parquet", entities=[user])
    def user_spend(df):
        return df

    assert isinstance(user_spend, Feature)
    assert user_spend.entities == [user]
    assert user_spend.keys == ["user_id"]  # Derived from entity


def test_feature_decorator_with_multiple_entities():
    """Feature decorator derives keys from multiple entities."""
    user = Entity(name="user", join_key="user_id")
    merchant = Entity(name="merchant", join_key="merchant_id")

    @feature(source="data.parquet", entities=[user, merchant])
    def user_merchant_spend(df):
        return df

    assert user_merchant_spend.entities == [user, merchant]
    assert user_merchant_spend.keys == ["user_id", "merchant_id"]


def test_feature_decorator_with_composite_entity_key():
    """Feature decorator handles composite entity keys."""
    user_merchant = Entity(
        name="user_merchant",
        join_key=["user_id", "merchant_id"],
    )

    @feature(source="data.parquet", entities=[user_merchant])
    def user_merchant_spend(df):
        return df

    assert user_merchant_spend.keys == ["user_id", "merchant_id"]


def test_feature_decorator_deduplicates_keys():
    """Feature decorator removes duplicate keys from entities."""
    user = Entity(name="user", join_key="user_id")
    user_orders = Entity(name="user_orders", join_key="user_id")  # Same key

    @feature(source="data.parquet", entities=[user, user_orders])
    def user_stuff(df):
        return df

    # Should deduplicate
    assert user_stuff.keys == ["user_id"]


def test_feature_decorator_requires_keys_or_entities():
    """Feature decorator requires either keys or entities."""
    with pytest.raises(
        ValueError, match="Either 'keys' or 'entities' must be provided"
    ):

        @feature(source="data.parquet")
        def no_keys_feature(df):
            return df


def test_feature_decorator_keys_still_works():
    """Feature decorator still works with keys parameter (backward compat)."""

    @feature(source="data.parquet", keys=["user_id"])
    def old_style_feature(df):
        return df

    assert old_style_feature.keys == ["user_id"]
    assert old_style_feature.entities is None


# =============================================================================
# Engine Entity Key Generation Tests
# =============================================================================


def test_polars_engine_generates_surrogate_key():
    """Polars engine generates surrogate key from from_columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create source data without user_id
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame(
            {
                "first_name": ["Alice", "Bob"],
                "last_name": ["Smith", "Jones"],
                "dob": ["1990-01-01", "1985-05-15"],
                "amount": [100, 200],
            }
        ).write_parquet(source_path)

        # Define entity with surrogate key generation
        user = Entity(
            name="user",
            join_key="user_id",
            from_columns=["first_name", "last_name", "dob"],
        )

        @feature(source=str(source_path), entities=[user])
        def user_spend(df):
            # user_id should already exist (generated by engine)
            return df.select("user_id", "amount")

        store = LocalStore(tmpdir)
        defs = Definitions(
            name="test",
            features=[user_spend],
            offline_store=store,
            default_engine="polars",
        )

        # Build the feature
        defs.build(preview=False)

        # Verify the result has user_id column
        result = store.read("user_spend")
        assert "user_id" in result.columns
        assert "amount" in result.columns
        assert len(result) == 2

        # user_id should be a hash (converted to string from int hash)
        assert result["user_id"].dtype == pl.String
        # Hash values are numeric strings (from Polars .hash() cast to Utf8)
        assert all(
            uid.isdigit() or uid.startswith("-")
            for uid in result["user_id"].to_list()
        )


def test_duckdb_engine_generates_surrogate_key():
    """DuckDB engine generates surrogate key from from_columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create source data without user_id
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame(
            {
                "first_name": ["Alice", "Bob"],
                "last_name": ["Smith", "Jones"],
                "dob": ["1990-01-01", "1985-05-15"],
                "amount": [100, 200],
            }
        ).write_parquet(source_path)

        # Define entity with surrogate key generation
        user = Entity(
            name="user",
            join_key="user_id",
            from_columns=["first_name", "last_name", "dob"],
        )

        @feature(source=str(source_path), entities=[user])
        def user_spend_duckdb(df):
            # user_id should already exist (generated by engine)
            return df.select("user_id", "amount")

        store = LocalStore(tmpdir)
        defs = Definitions(
            name="test",
            features=[user_spend_duckdb],
            offline_store=store,
            default_engine="duckdb",
        )

        # Build the feature
        defs.build(preview=False)

        # Verify the result has user_id column
        result = store.read("user_spend_duckdb")
        assert "user_id" in result.columns
        assert "amount" in result.columns
        assert len(result) == 2

        # user_id should be a hash (converted to string from int hash)
        assert result["user_id"].dtype == pl.String
        # Hash values are numeric strings (from Polars .hash() cast to Utf8)
        assert all(
            uid.isdigit() or uid.startswith("-")
            for uid in result["user_id"].to_list()
        )


def test_engine_passthrough_entity_without_from_columns():
    """Engine passes through when entity has no from_columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create source data WITH user_id already present
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame(
            {
                "user_id": ["u1", "u2"],
                "amount": [100, 200],
            }
        ).write_parquet(source_path)

        # Entity without from_columns - expects user_id in source
        user = Entity(name="user", join_key="user_id")

        @feature(source=str(source_path), entities=[user])
        def user_spend_passthrough(df):
            return df.select("user_id", "amount")

        store = LocalStore(tmpdir)
        defs = Definitions(
            name="test",
            features=[user_spend_passthrough],
            offline_store=store,
        )

        # Build the feature
        defs.build(preview=False)

        # Verify the result preserves original user_id
        result = store.read("user_spend_passthrough")
        assert result["user_id"].to_list() == ["u1", "u2"]


def test_engine_generates_consistent_surrogate_keys():
    """Surrogate keys are deterministic (same input -> same output)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame(
            {
                "first": ["Alice", "Alice", "Bob"],
                "last": ["Smith", "Smith", "Jones"],
                "amount": [100, 200, 300],
            }
        ).write_parquet(source_path)

        user = Entity(
            name="user",
            join_key="user_id",
            from_columns=["first", "last"],
        )

        @feature(source=str(source_path), entities=[user])
        def user_amounts(df):
            return df.select("user_id", "amount")

        store = LocalStore(tmpdir)
        defs = Definitions(
            name="test",
            features=[user_amounts],
            offline_store=store,
        )

        defs.build(preview=False)

        result = store.read("user_amounts")
        user_ids = result["user_id"].to_list()

        # First two rows (Alice Smith) should have same user_id
        assert user_ids[0] == user_ids[1]
        # Third row (Bob Jones) should have different user_id
        assert user_ids[2] != user_ids[0]


def test_feature_with_entity_and_metrics():
    """Entity-based feature works with rolling metrics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame(
            {
                "user_id": ["u1", "u1", "u2"],
                "amount": [100, 200, 300],
                "ts": ["2024-01-01", "2024-01-02", "2024-01-01"],
            }
        ).with_columns(pl.col("ts").str.to_datetime()).write_parquet(
            source_path
        )

        from mlforge import Rolling

        user = Entity(name="user", join_key="user_id")

        @feature(
            source=str(source_path),
            entities=[user],
            timestamp="ts",
            interval="1d",
            metrics=[Rolling(windows=["1d"], aggregations={"amount": ["sum"]})],
        )
        def user_spend_rolling(df):
            return df.select("user_id", "amount", "ts")

        store = LocalStore(tmpdir)
        defs = Definitions(
            name="test",
            features=[user_spend_rolling],
            offline_store=store,
        )

        defs.build(preview=False)

        result = store.read("user_spend_rolling")
        assert "user_id" in result.columns
        # Rolling metric column naming: {tag}_{col}_{agg}_{interval}
        assert any("amount" in col and "sum" in col for col in result.columns)
