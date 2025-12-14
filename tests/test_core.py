import tempfile
from pathlib import Path
from types import ModuleType

import polars as pl
import pytest

from mlforge import Definitions, Feature, LocalStore, feature
from mlforge.errors import FeatureMaterializationError


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
        defs = Definitions(name="test", features=[], offline_store=LocalStore(tmpdir))

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
            name="test", features=[test_feature], offline_store=LocalStore(tmpdir)
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
        with pytest.raises(ValueError, match="Duplicate feature name: duplicate"):
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
            name="test", features=[add_constant], offline_store=LocalStore(tmpdir)
        )
        defs.materialize(preview=False)

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
        defs = Definitions(name="test", features=[simple_feature], offline_store=store)

        # When materializing
        results = defs.materialize(preview=False)

        # Then the feature should exist in the store
        assert store.exists("simple_feature")
        assert "simple_feature" in results


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
        defs.materialize(preview=False)
        defs.materialize(preview=False)

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
        store.write("versioned_feature", pl.DataFrame({"id": [1], "version": [1]}))

        # When materializing with force=True
        defs = Definitions(
            name="test", features=[versioned_feature], offline_store=store
        )
        defs.materialize(feature_names=["versioned_feature"], force=True, preview=False)

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
            name="test", features=[known_feature], offline_store=LocalStore(tmpdir)
        )

        # When/Then requesting unknown feature should raise
        with pytest.raises(ValueError, match="Unknown feature: unknown"):
            defs.materialize(feature_names=["unknown"], preview=False)


def test_materialize_raises_on_none_return():
    # Given a feature that returns None
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1]}).write_parquet(source_path)

        @feature(keys=["id"], source=str(source_path))
        def returns_none(df):
            return None  # type: ignore[return-value]

        defs = Definitions(
            name="test", features=[returns_none], offline_store=LocalStore(tmpdir)
        )

        # When/Then materializing should raise FeatureMaterializationError
        with pytest.raises(
            FeatureMaterializationError, match="Feature function returned None"
        ):
            defs.materialize(preview=False)


def test_materialize_raises_on_wrong_return_type():
    # Given a feature that returns wrong type
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1]}).write_parquet(source_path)

        @feature(keys=["id"], source=str(source_path))
        def returns_string(df):
            return "not a dataframe"  # type: ignore[return-value]

        defs = Definitions(
            name="test", features=[returns_string], offline_store=LocalStore(tmpdir)
        )

        # When/Then materializing should raise FeatureMaterializationError
        with pytest.raises(FeatureMaterializationError, match="Expected DataFrame"):
            defs.materialize(preview=False)


def test_load_source_parquet():
    # Given a parquet source file
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        expected = pl.DataFrame({"col": [1, 2, 3]})
        expected.write_parquet(source_path)

        defs = Definitions(name="test", features=[], offline_store=LocalStore(tmpdir))

        # When loading the source
        result = defs._load_source(str(source_path))

        # Then it should return the DataFrame
        assert result.equals(expected)


def test_load_source_csv():
    # Given a CSV source file
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.csv"
        expected = pl.DataFrame({"col": [1, 2, 3]})
        expected.write_csv(source_path)

        defs = Definitions(name="test", features=[], offline_store=LocalStore(tmpdir))

        # When loading the source
        result = defs._load_source(str(source_path))

        # Then it should return the DataFrame
        assert result.equals(expected)


def test_load_source_unsupported_format():
    # Given an unsupported file format
    with tempfile.TemporaryDirectory() as tmpdir:
        defs = Definitions(name="test", features=[], offline_store=LocalStore(tmpdir))

        # When/Then loading should raise ValueError
        with pytest.raises(ValueError, match="Unsupported source format: .json"):
            defs._load_source("data.json")
