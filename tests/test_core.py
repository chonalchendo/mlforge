import tempfile
from pathlib import Path
from types import ModuleType

import polars as pl
import pytest

from mlforge import Definitions, Entity, Feature, LocalStore, Source, feature


def test_feature_decorator_creates_feature_object():
    # Given a function decorated with @feature
    @feature(keys=["user_id"], source="data/users.parquet")
    def user_age(df):
        return df.with_columns(pl.lit(25).alias("age"))

    # When checking the result type
    # Then it should be a Feature instance
    assert isinstance(user_age, Feature)


def test_feature_decorator_sets_name_from_function():
    # Given a decorated function
    @feature(keys=["user_id"], source="data.parquet")
    def my_feature(df):
        return df

    # When checking the name
    # Then it should match the function name
    assert my_feature.name == "my_feature"


def test_feature_decorator_stores_metadata():
    # Given a feature with all metadata
    @feature(
        keys=["user_id", "product_id"],
        source="data/events.parquet",
        timestamp="event_time",
        description="User-product interactions",
    )
    def interactions(df):
        return df

    # When checking the metadata
    # Then all values should be stored
    assert interactions.keys == ["user_id", "product_id"]
    assert interactions.source == "data/events.parquet"
    assert interactions.timestamp == "event_time"
    assert interactions.description == "User-product interactions"


def test_feature_decorator_stores_tags():
    # Given a feature with tags
    @feature(
        keys=["user_id"],
        source="data/users.parquet",
        tags=["user", "profile"],
        description="User profile features",
    )
    def user_profile(df):
        return df

    # When checking the tags
    # Then tags should be stored
    assert user_profile.tags == ["user", "profile"]


def test_feature_decorator_defaults_tags_to_none():
    # Given a feature without tags
    @feature(keys=["id"], source="data.parquet")
    def no_tags_feature(df):
        return df

    # When checking the tags
    # Then tags should be None
    assert no_tags_feature.tags is None


def test_feature_is_callable():
    # Given a feature that transforms data
    @feature(keys=["id"], source="data.parquet")
    def double_value(df):
        return df.with_columns((pl.col("value") * 2).alias("doubled"))

    df = pl.DataFrame({"id": [1, 2], "value": [10, 20]})

    # When calling the feature
    result = double_value(df)

    # Then it should execute the transformation
    assert result["doubled"].to_list() == [20, 40]


def test_definitions_init_with_empty_features():
    # Given an empty features list
    with tempfile.TemporaryDirectory() as tmpdir:
        # When creating Definitions
        defs = Definitions(
            name="test", features=[], offline_store=LocalStore(tmpdir)
        )

        # Then it should have no features
        assert len(defs.features) == 0


def test_definitions_register_single_feature():
    # Given a single feature
    @feature(keys=["id"], source="data.parquet")
    def test_feature(df):
        return df

    # When creating Definitions with that feature
    with tempfile.TemporaryDirectory() as tmpdir:
        defs = Definitions(
            name="test",
            features=[test_feature],
            offline_store=LocalStore(tmpdir),
        )

        # Then the feature should be registered
        assert "test_feature" in defs.features
        assert defs.features["test_feature"] == test_feature


def test_definitions_register_module_with_features():
    # Given a module containing features
    module = ModuleType("test_module")

    @feature(keys=["id"], source="data.parquet")
    def feature_one(df):
        return df

    @feature(keys=["id"], source="data.parquet")
    def feature_two(df):
        return df

    module.feature_one = feature_one  # type: ignore[attr-defined]
    module.feature_two = feature_two  # type: ignore[attr-defined]
    module.not_a_feature = "ignored"  # type: ignore[attr-defined]

    # When creating Definitions with that module
    with tempfile.TemporaryDirectory() as tmpdir:
        defs = Definitions(
            name="test", features=[module], offline_store=LocalStore(tmpdir)
        )

        # Then both features should be registered
        assert len(defs.features) == 2
        assert "feature_one" in defs.features
        assert "feature_two" in defs.features


def test_definitions_register_rejects_duplicate_names():
    # Given two features with the same name
    @feature(keys=["id"], source="data.parquet")
    def duplicate(df):
        return df

    @feature(keys=["id"], source="data.parquet")
    def duplicate(df):  # noqa: F811
        return df

    # When/Then registering should raise ValueError
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(
            ValueError, match="Duplicate feature name: duplicate"
        ):
            Definitions(
                name="test",
                features=[duplicate, duplicate],
                offline_store=LocalStore(tmpdir),
            )


def test_definitions_register_rejects_invalid_type():
    # Given an invalid object type
    invalid_obj = {"not": "a feature"}

    # When/Then registering should raise TypeError
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(TypeError, match="Expected Feature or module"):
            Definitions(
                name="test",
                features=[invalid_obj],  # type: ignore[list-item]
                offline_store=LocalStore(tmpdir),
            )


def test_definitions_list_features_returns_all():
    # Given multiple registered features
    @feature(keys=["id"], source="data.parquet")
    def feature_a(df):
        return df

    @feature(keys=["id"], source="data.parquet")
    def feature_b(df):
        return df

    with tempfile.TemporaryDirectory() as tmpdir:
        defs = Definitions(
            name="test",
            features=[feature_a, feature_b],
            offline_store=LocalStore(tmpdir),
        )

        # When listing features
        features = defs.list_features()

        # Then all features should be returned
        assert len(features) == 2
        assert feature_a in features
        assert feature_b in features


def test_definitions_list_features_filters_by_tags():
    # Given features with different tags
    @feature(keys=["id"], source="data.parquet", tags=["user", "profile"])
    def user_feature(df):
        return df

    @feature(keys=["id"], source="data.parquet", tags=["transaction"])
    def transaction_feature(df):
        return df

    @feature(keys=["id"], source="data.parquet", tags=["user", "activity"])
    def activity_feature(df):
        return df

    with tempfile.TemporaryDirectory() as tmpdir:
        defs = Definitions(
            name="test",
            features=[user_feature, transaction_feature, activity_feature],
            offline_store=LocalStore(tmpdir),
        )

        # When listing features with specific tags
        features = defs.list_features(tags=["user"])

        # Then only features with matching tags should be returned
        assert len(features) == 2
        assert user_feature in features
        assert activity_feature in features
        assert transaction_feature not in features


def test_definitions_list_tags_returns_all_unique_tags():
    # Given features with various tags
    @feature(keys=["id"], source="data.parquet", tags=["user", "profile"])
    def feature_a(df):
        return df

    @feature(keys=["id"], source="data.parquet", tags=["user", "activity"])
    def feature_b(df):
        return df

    @feature(keys=["id"], source="data.parquet")
    def feature_c(df):
        return df

    with tempfile.TemporaryDirectory() as tmpdir:
        defs = Definitions(
            name="test",
            features=[feature_a, feature_b, feature_c],
            offline_store=LocalStore(tmpdir),
        )

        # When listing tags
        tags = defs.list_tags()

        # Then all unique tags should be returned
        assert "user" in tags
        assert "profile" in tags
        assert "activity" in tags


def test_materialize_executes_feature_function():
    # Given a feature that adds a column
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"user_id": [1, 2]}).write_parquet(source_path)

        @feature(keys=["user_id"], source=str(source_path))
        def add_constant(df):
            return df.with_columns(pl.lit(42).alias("constant"))

        # When materializing with source data
        defs = Definitions(
            name="test",
            features=[add_constant],
            offline_store=LocalStore(tmpdir),
        )
        defs.build(preview=False)

        # Then the feature should be computed and stored
        store = LocalStore(tmpdir)
        result = store.read("add_constant")
        assert "constant" in result.columns
        assert result["constant"].to_list() == [42, 42]


def test_materialize_writes_to_store():
    # Given a simple feature
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1, 2, 3]}).write_parquet(source_path)

        @feature(keys=["id"], source=str(source_path))
        def simple_feature(df):
            return df

        store = LocalStore(tmpdir)
        defs = Definitions(
            name="test", features=[simple_feature], offline_store=store
        )

        # When materializing
        results = defs.build(preview=False)

        # Then the feature should exist in the store
        assert store.exists("simple_feature")
        assert "simple_feature" in results.paths


def test_materialize_skips_existing_without_force():
    # Given a feature that's already materialized
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1]}).write_parquet(source_path)

        @feature(keys=["id"], source=str(source_path))
        def existing_feature(df):
            return df.with_columns(pl.lit(1).alias("version"))

        store = LocalStore(tmpdir)
        defs = Definitions(
            name="test", features=[existing_feature], offline_store=store
        )

        # When materializing twice without force
        defs.build(preview=False)
        defs.build(preview=False)

        # Then the feature should only be computed once
        result = store.read("existing_feature")
        assert result["version"].to_list() == [1]


def test_materialize_overwrites_with_force():
    # Given a feature that changes between runs
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1]}).write_parquet(source_path)

        @feature(keys=["id"], source=str(source_path))
        def versioned_feature(df):
            return df.with_columns(pl.lit(2).alias("version"))

        store = LocalStore(tmpdir)

        # First materialize with version 1
        from mlforge.results import PolarsResult

        store.write(
            "versioned_feature",
            PolarsResult(pl.DataFrame({"id": [1], "version": [1]})),
            feature_version="1.0.0",
        )

        # When materializing with force=True
        defs = Definitions(
            name="test", features=[versioned_feature], offline_store=store
        )
        defs.build(
            feature_names=["versioned_feature"], force=True, preview=False
        )

        # Then it should overwrite with new version
        result = store.read("versioned_feature")
        assert result["version"].to_list() == [2]


def test_materialize_raises_on_unknown_feature():
    # Given definitions with specific features
    @feature(keys=["id"], source="data.parquet")
    def known_feature(df):
        return df

    with tempfile.TemporaryDirectory() as tmpdir:
        defs = Definitions(
            name="test",
            features=[known_feature],
            offline_store=LocalStore(tmpdir),
        )

        # When/Then requesting unknown feature should raise
        with pytest.raises(ValueError, match="Unknown feature: unknown"):
            defs.build(feature_names=["unknown"], preview=False)


def test_materialize_raises_on_unknown_tag():
    # Given definitions with features having specific tags
    @feature(keys=["id"], source="data.parquet", tags=["user"])
    def tagged_feature(df):
        return df

    with tempfile.TemporaryDirectory() as tmpdir:
        defs = Definitions(
            name="test",
            features=[tagged_feature],
            offline_store=LocalStore(tmpdir),
        )

        # When/Then requesting unknown tag should raise
        with pytest.raises(ValueError, match="Unknown tags: \\['unknown'\\]"):
            defs.build(tag_names=["unknown"], preview=False)


def test_materialize_filters_by_tag_names():
    # Given features with different tags
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1, 2]}).write_parquet(source_path)

        @feature(keys=["id"], source=str(source_path), tags=["user"])
        def user_feature(df):
            return df.with_columns(pl.lit("user").alias("type"))

        @feature(keys=["id"], source=str(source_path), tags=["transaction"])
        def transaction_feature(df):
            return df.with_columns(pl.lit("transaction").alias("type"))

        store = LocalStore(tmpdir)
        defs = Definitions(
            name="test",
            features=[user_feature, transaction_feature],
            offline_store=store,
        )

        # When materializing by tag
        results = defs.build(tag_names=["user"], preview=False)

        # Then only features with that tag should be materialized
        assert "user_feature" in results.paths
        assert "transaction_feature" not in results.paths
        assert store.exists("user_feature")
        assert not store.exists("transaction_feature")


def test_materialize_raises_on_none_return():
    # Given a feature that returns None
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1]}).write_parquet(source_path)

        @feature(keys=["id"], source=str(source_path))
        def returns_none(df):
            return None

        defs = Definitions(
            name="test",
            features=[returns_none],
            offline_store=LocalStore(tmpdir),
        )

        # When/Then materializing should raise AttributeError (from engine trying to access schema)
        with pytest.raises(AttributeError):
            defs.build(preview=False)


def test_materialize_raises_on_wrong_return_type():
    # Given a feature that returns wrong type
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1]}).write_parquet(source_path)

        @feature(keys=["id"], source=str(source_path))
        def returns_string(df):
            return "not a dataframe"

        defs = Definitions(
            name="test",
            features=[returns_string],
            offline_store=LocalStore(tmpdir),
        )

        # When/Then materializing should raise AttributeError (from engine trying to access schema)
        with pytest.raises(AttributeError):
            defs.build(preview=False)


def test_polars_result_base_schema():
    # Given a PolarsResult with base_schema
    from mlforge.results import PolarsResult

    df = pl.DataFrame({"id": [1, 2], "value": [10, 20]})
    base_schema = {"id": "Int64", "value": "Int64"}

    # When creating result with base_schema
    result_with_schema = PolarsResult(df, base_schema=base_schema)

    # Then base_schema should be retrievable
    assert result_with_schema.base_schema() == base_schema

    # When creating result without base_schema
    result_without_schema = PolarsResult(df)

    # Then base_schema should return None
    assert result_without_schema.base_schema() is None


# =============================================================================
# Sync Tests
# =============================================================================


def test_sync_returns_empty_when_all_features_have_data():
    # Given a feature that has been built (data exists)
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1, 2]}).write_parquet(source_path)

        @feature(keys=["id"], source=str(source_path))
        def synced_feature(df):
            return df

        store = LocalStore(tmpdir)
        defs = Definitions(
            name="test", features=[synced_feature], offline_store=store
        )

        # Build the feature first
        defs.build(preview=False)

        # When syncing
        result = defs.sync()

        # Then nothing needs syncing
        assert result["needs_sync"] == []
        assert result["synced"] == []


def test_sync_identifies_missing_data():
    # Given a feature with metadata but no data file
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1, 2]}).write_parquet(source_path)

        @feature(keys=["id"], source=str(source_path))
        def missing_data_feature(df):
            return df

        store = LocalStore(tmpdir)
        defs = Definitions(
            name="test", features=[missing_data_feature], offline_store=store
        )

        # Build the feature first
        defs.build(preview=False)

        # Delete the data file (simulate git pulling metadata without data)
        data_path = (
            Path(tmpdir) / "missing_data_feature" / "1.0.0" / "data.parquet"
        )
        data_path.unlink()

        # When syncing with dry_run
        result = defs.sync(dry_run=True)

        # Then it should identify the feature as needing sync
        assert "missing_data_feature" in result["needs_sync"]
        assert result["synced"] == []  # dry_run doesn't sync


def test_sync_rebuilds_missing_data():
    # Given a feature with metadata but no data file
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1, 2]}).write_parquet(source_path)

        @feature(keys=["id"], source=str(source_path))
        def rebuild_feature(df):
            return df

        store = LocalStore(tmpdir)
        defs = Definitions(
            name="test", features=[rebuild_feature], offline_store=store
        )

        # Build the feature first
        defs.build(preview=False)

        # Delete the data file
        data_path = Path(tmpdir) / "rebuild_feature" / "1.0.0" / "data.parquet"
        data_path.unlink()

        # When syncing (not dry_run)
        result = defs.sync()

        # Then it should rebuild the feature
        assert "rebuild_feature" in result["needs_sync"]
        assert "rebuild_feature" in result["synced"]
        assert data_path.exists()


def test_sync_detects_source_data_change():
    # Given a feature built with original source data
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1, 2]}).write_parquet(source_path)

        @feature(keys=["id"], source=str(source_path))
        def source_change_feature(df):
            return df

        store = LocalStore(tmpdir)
        defs = Definitions(
            name="test", features=[source_change_feature], offline_store=store
        )

        # Build the feature
        defs.build(preview=False)

        # Delete data file
        data_path = (
            Path(tmpdir) / "source_change_feature" / "1.0.0" / "data.parquet"
        )
        data_path.unlink()

        # Change the source data
        pl.DataFrame({"id": [1, 2, 3, 4]}).write_parquet(source_path)

        # When syncing with dry_run
        result = defs.sync(dry_run=True)

        # Then it should detect the source change
        assert "source_change_feature" in result["needs_sync"]
        assert "source_change_feature" in result["source_changed"]


def test_sync_force_rebuilds_despite_source_change():
    # Given a feature with changed source data
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1, 2]}).write_parquet(source_path)

        @feature(keys=["id"], source=str(source_path))
        def force_rebuild_feature(df):
            return df

        store = LocalStore(tmpdir)
        defs = Definitions(
            name="test", features=[force_rebuild_feature], offline_store=store
        )

        # Build the feature
        defs.build(preview=False)

        # Delete data file
        data_path = (
            Path(tmpdir) / "force_rebuild_feature" / "1.0.0" / "data.parquet"
        )
        data_path.unlink()

        # Change the source data
        pl.DataFrame({"id": [1, 2, 3, 4]}).write_parquet(source_path)

        # When syncing with force=True
        result = defs.sync(force=True)

        # Then it should rebuild despite source change
        assert "force_rebuild_feature" in result["synced"]
        assert data_path.exists()


def test_sync_with_specific_feature_names():
    # Given multiple features
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1, 2]}).write_parquet(source_path)

        @feature(keys=["id"], source=str(source_path))
        def feature_a(df):
            return df

        @feature(keys=["id"], source=str(source_path))
        def feature_b(df):
            return df

        store = LocalStore(tmpdir)
        defs = Definitions(
            name="test", features=[feature_a, feature_b], offline_store=store
        )

        # Build both features
        defs.build(preview=False)

        # Delete data for both
        for name in ["feature_a", "feature_b"]:
            data_path = Path(tmpdir) / name / "1.0.0" / "data.parquet"
            data_path.unlink()

        # When syncing only feature_a
        result = defs.sync(feature_names=["feature_a"])

        # Then only feature_a should be synced
        assert "feature_a" in result["synced"]
        assert "feature_b" not in result["synced"]


# =============================================================================
# Tests for Definitions discovery methods (list_entities, list_sources, etc.)
# =============================================================================


def test_definitions_list_entities_returns_unique_names():
    # Given features with entities
    user = Entity(
        name="user", join_key="user_id", from_columns=["first", "last"]
    )
    merchant = Entity(name="merchant", join_key="merchant_id")

    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame(
            {"first": ["a"], "last": ["b"], "merchant": ["m"]}
        ).write_parquet(source_path)

        @feature(keys=["user_id"], source=str(source_path), entities=[user])
        def user_feature(df):
            return df

        @feature(
            keys=["merchant_id"], source=str(source_path), entities=[merchant]
        )
        def merchant_feature(df):
            return df

        defs = Definitions(
            name="test",
            features=[user_feature, merchant_feature],
            offline_store=LocalStore(tmpdir),
        )

        # When listing entities
        entities = defs.list_entities()

        # Then all unique entity names should be returned sorted
        assert entities == ["merchant", "user"]


def test_definitions_list_entities_empty_when_no_entities():
    # Given features without entities
    with tempfile.TemporaryDirectory() as tmpdir:

        @feature(keys=["id"], source="data.parquet")
        def simple_feature(df):
            return df

        defs = Definitions(
            name="test",
            features=[simple_feature],
            offline_store=LocalStore(tmpdir),
        )

        # When listing entities
        entities = defs.list_entities()

        # Then empty list should be returned
        assert entities == []


def test_definitions_list_sources_returns_unique_names():
    # Given features with Source objects
    transactions = Source("data/transactions.parquet")
    events = Source("data/events.parquet")

    with tempfile.TemporaryDirectory() as tmpdir:

        @feature(keys=["id"], source=transactions)
        def txn_feature(df):
            return df

        @feature(keys=["id"], source=events)
        def event_feature(df):
            return df

        @feature(keys=["id"], source=transactions)  # Same source as txn_feature
        def another_txn_feature(df):
            return df

        defs = Definitions(
            name="test",
            features=[txn_feature, event_feature, another_txn_feature],
            offline_store=LocalStore(tmpdir),
        )

        # When listing sources
        sources = defs.list_sources()

        # Then unique source names should be returned sorted
        assert sources == ["events", "transactions"]


def test_definitions_list_sources_handles_string_sources():
    # Given features with legacy string sources
    with tempfile.TemporaryDirectory() as tmpdir:

        @feature(keys=["id"], source="data/transactions.parquet")
        def txn_feature(df):
            return df

        @feature(keys=["id"], source="other/events.csv")
        def event_feature(df):
            return df

        defs = Definitions(
            name="test",
            features=[txn_feature, event_feature],
            offline_store=LocalStore(tmpdir),
        )

        # When listing sources
        sources = defs.list_sources()

        # Then source names derived from path stems should be returned
        assert sources == ["events", "transactions"]


def test_definitions_get_entity_returns_entity():
    # Given a feature with an entity
    user = Entity(
        name="user", join_key="user_id", from_columns=["first", "last"]
    )

    with tempfile.TemporaryDirectory() as tmpdir:

        @feature(keys=["user_id"], source="data.parquet", entities=[user])
        def user_feature(df):
            return df

        defs = Definitions(
            name="test",
            features=[user_feature],
            offline_store=LocalStore(tmpdir),
        )

        # When getting entity by name
        result = defs.get_entity("user")

        # Then the entity should be returned
        assert result is not None
        assert result.name == "user"
        assert result.join_key == "user_id"
        assert result.from_columns == ["first", "last"]


def test_definitions_get_entity_returns_none_when_not_found():
    # Given a feature with an entity
    user = Entity(name="user", join_key="user_id")

    with tempfile.TemporaryDirectory() as tmpdir:

        @feature(keys=["user_id"], source="data.parquet", entities=[user])
        def user_feature(df):
            return df

        defs = Definitions(
            name="test",
            features=[user_feature],
            offline_store=LocalStore(tmpdir),
        )

        # When getting non-existent entity
        result = defs.get_entity("merchant")

        # Then None should be returned
        assert result is None


def test_definitions_get_source_returns_source():
    # Given a feature with a Source object
    transactions = Source("data/transactions.parquet")

    with tempfile.TemporaryDirectory() as tmpdir:

        @feature(keys=["id"], source=transactions)
        def txn_feature(df):
            return df

        defs = Definitions(
            name="test",
            features=[txn_feature],
            offline_store=LocalStore(tmpdir),
        )

        # When getting source by name
        result = defs.get_source("transactions")

        # Then the source should be returned
        assert result is not None
        assert result.name == "transactions"
        assert result.path == "data/transactions.parquet"


def test_definitions_get_source_returns_none_when_not_found():
    # Given a feature with a source
    with tempfile.TemporaryDirectory() as tmpdir:

        @feature(keys=["id"], source="data/transactions.parquet")
        def txn_feature(df):
            return df

        defs = Definitions(
            name="test",
            features=[txn_feature],
            offline_store=LocalStore(tmpdir),
        )

        # When getting non-existent source
        result = defs.get_source("events")

        # Then None should be returned
        assert result is None


def test_definitions_get_source_converts_string_to_source():
    # Given a feature with a legacy string source
    with tempfile.TemporaryDirectory() as tmpdir:

        @feature(keys=["id"], source="data/transactions.parquet")
        def txn_feature(df):
            return df

        defs = Definitions(
            name="test",
            features=[txn_feature],
            offline_store=LocalStore(tmpdir),
        )

        # When getting source by name
        result = defs.get_source("transactions")

        # Then a Source object should be returned
        assert result is not None
        assert isinstance(result, Source)
        assert result.path == "data/transactions.parquet"


def test_definitions_features_using_entity():
    # Given features with different entities
    user = Entity(name="user", join_key="user_id")
    merchant = Entity(name="merchant", join_key="merchant_id")

    with tempfile.TemporaryDirectory() as tmpdir:

        @feature(keys=["user_id"], source="data.parquet", entities=[user])
        def user_spend(df):
            return df

        @feature(keys=["user_id"], source="data.parquet", entities=[user])
        def user_transactions(df):
            return df

        @feature(
            keys=["merchant_id"], source="data.parquet", entities=[merchant]
        )
        def merchant_spend(df):
            return df

        defs = Definitions(
            name="test",
            features=[user_spend, user_transactions, merchant_spend],
            offline_store=LocalStore(tmpdir),
        )

        # When finding features using user entity
        user_features = defs.features_using_entity("user")

        # Then features using user should be returned
        assert "user_spend" in user_features
        assert "user_transactions" in user_features
        assert "merchant_spend" not in user_features


def test_definitions_features_using_entity_returns_empty_when_not_found():
    # Given features with entities
    user = Entity(name="user", join_key="user_id")

    with tempfile.TemporaryDirectory() as tmpdir:

        @feature(keys=["user_id"], source="data.parquet", entities=[user])
        def user_feature(df):
            return df

        defs = Definitions(
            name="test",
            features=[user_feature],
            offline_store=LocalStore(tmpdir),
        )

        # When finding features using non-existent entity
        result = defs.features_using_entity("merchant")

        # Then empty list should be returned
        assert result == []


def test_definitions_features_using_source():
    # Given features with different sources
    transactions = Source("data/transactions.parquet")
    events = Source("data/events.parquet")

    with tempfile.TemporaryDirectory() as tmpdir:

        @feature(keys=["id"], source=transactions)
        def txn_feature_a(df):
            return df

        @feature(keys=["id"], source=transactions)
        def txn_feature_b(df):
            return df

        @feature(keys=["id"], source=events)
        def event_feature(df):
            return df

        defs = Definitions(
            name="test",
            features=[txn_feature_a, txn_feature_b, event_feature],
            offline_store=LocalStore(tmpdir),
        )

        # When finding features using transactions source
        txn_features = defs.features_using_source("transactions")

        # Then features using transactions should be returned
        assert "txn_feature_a" in txn_features
        assert "txn_feature_b" in txn_features
        assert "event_feature" not in txn_features


def test_definitions_features_using_source_returns_empty_when_not_found():
    # Given features with sources
    with tempfile.TemporaryDirectory() as tmpdir:

        @feature(keys=["id"], source="data/transactions.parquet")
        def txn_feature(df):
            return df

        defs = Definitions(
            name="test",
            features=[txn_feature],
            offline_store=LocalStore(tmpdir),
        )

        # When finding features using non-existent source
        result = defs.features_using_source("events")

        # Then empty list should be returned
        assert result == []


def test_definitions_features_using_source_handles_string_sources():
    # Given features with legacy string sources
    with tempfile.TemporaryDirectory() as tmpdir:

        @feature(keys=["id"], source="data/transactions.parquet")
        def txn_feature_a(df):
            return df

        @feature(keys=["id"], source="data/transactions.parquet")
        def txn_feature_b(df):
            return df

        defs = Definitions(
            name="test",
            features=[txn_feature_a, txn_feature_b],
            offline_store=LocalStore(tmpdir),
        )

        # When finding features using source name
        txn_features = defs.features_using_source("transactions")

        # Then features using that source should be returned
        assert "txn_feature_a" in txn_features
        assert "txn_feature_b" in txn_features
