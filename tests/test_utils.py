import polars as pl
import pytest

from mlforge.utils import entity_key, surrogate_key


def test_surrogate_key_creates_hash():
    # Given a DataFrame with columns to hash
    df = pl.DataFrame({"first": ["Alice"], "last": ["Smith"]})

    # When creating a surrogate key
    result = df.with_columns(surrogate_key("first", "last").alias("key"))

    # Then it should produce a hash string
    assert "key" in result.columns
    assert isinstance(result["key"][0], str)
    assert len(result["key"][0]) > 0


def test_surrogate_key_consistent_hash():
    # Given identical data
    df1 = pl.DataFrame({"a": ["foo"], "b": ["bar"]})
    df2 = pl.DataFrame({"a": ["foo"], "b": ["bar"]})

    # When creating surrogate keys
    result1 = df1.with_columns(surrogate_key("a", "b").alias("key"))
    result2 = df2.with_columns(surrogate_key("a", "b").alias("key"))

    # Then hashes should match
    assert result1["key"][0] == result2["key"][0]


def test_surrogate_key_different_values_different_hash():
    # Given different data
    df = pl.DataFrame({"a": ["foo", "bar"], "b": ["baz", "baz"]})

    # When creating surrogate keys
    result = df.with_columns(surrogate_key("a", "b").alias("key"))

    # Then hashes should differ
    assert result["key"][0] != result["key"][1]


def test_surrogate_key_handles_nulls():
    # Given data with null values
    df = pl.DataFrame({"a": ["foo", None], "b": ["bar", "bar"]})

    # When creating surrogate keys
    result = df.with_columns(surrogate_key("a", "b").alias("key"))

    # Then null values should be handled consistently
    assert result["key"][0] != result["key"][1]
    assert isinstance(result["key"][1], str)


def test_surrogate_key_order_matters():
    # Given the same columns in different order
    df = pl.DataFrame({"a": ["foo"], "b": ["bar"]})

    # When creating keys with different column orders
    key_ab = df.with_columns(surrogate_key("a", "b").alias("key"))
    key_ba = df.with_columns(surrogate_key("b", "a").alias("key"))

    # Then hashes should differ
    assert key_ab["key"][0] != key_ba["key"][0]


def test_surrogate_key_requires_at_least_one_column():
    # Given an attempt to create key with no columns
    df = pl.DataFrame({"a": [1]})

    # When/Then it should raise ValueError
    with pytest.raises(
        ValueError, match="surrogate_key requires at least one column"
    ):
        df.with_columns(surrogate_key().alias("key"))


def test_surrogate_key_handles_numeric_types():
    # Given numeric columns
    df = pl.DataFrame({"int_col": [1, 2], "float_col": [1.5, 2.5]})

    # When creating surrogate keys
    result = df.with_columns(surrogate_key("int_col", "float_col").alias("key"))

    # Then it should convert and hash successfully
    assert len(result["key"]) == 2
    assert result["key"][0] != result["key"][1]


def test_entity_key_adds_column():
    # Given a DataFrame
    df = pl.DataFrame({"first": ["Alice"], "last": ["Smith"]})

    # When applying entity_key transform
    transform = entity_key("first", "last", alias="user_id")
    result = df.pipe(transform)

    # Then it should add the key column
    assert "user_id" in result.columns
    assert "first" in result.columns
    assert "last" in result.columns


def test_entity_key_creates_consistent_keys():
    # Given identical data in two DataFrames
    df1 = pl.DataFrame({"a": ["foo"], "b": ["bar"]})
    df2 = pl.DataFrame({"a": ["foo"], "b": ["bar"]})

    transform = entity_key("a", "b", alias="key")

    # When applying the same transform
    result1 = df1.pipe(transform)
    result2 = df2.pipe(transform)

    # Then keys should match
    assert result1["key"][0] == result2["key"][0]


def test_entity_key_has_metadata():
    # Given an entity_key transform
    transform = entity_key("col1", "col2", alias="my_key")

    # When checking metadata
    # Then it should have the required attributes
    assert hasattr(transform, "_entity_key_columns")
    assert hasattr(transform, "_entity_key_alias")
    assert transform._entity_key_columns == ("col1", "col2")
    assert transform._entity_key_alias == "my_key"


def test_entity_key_requires_at_least_one_column():
    # Given no columns
    # When/Then creating entity_key should raise ValueError
    with pytest.raises(
        ValueError, match="entity_key requires at least one column"
    ):
        entity_key(alias="key")


def test_entity_key_requires_alias():
    # Given columns but no alias
    # When/Then creating entity_key should raise ValueError
    with pytest.raises(ValueError, match="entity_key requires an alias"):
        entity_key("col1", "col2", alias="")


def test_entity_key_works_with_pipe():
    # Given a DataFrame and entity_key transform
    df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
    transform = entity_key("a", "b", alias="ab_key")

    # When using pipe
    result = df.pipe(transform)

    # Then it should add the key column
    assert "ab_key" in result.columns
    assert len(result) == 2


def test_entity_key_preserves_original_columns():
    # Given a DataFrame
    df = pl.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6], "z": [7, 8, 9]})

    # When applying entity_key
    transform = entity_key("x", "y", alias="xy_key")
    result = df.pipe(transform)

    # Then all original columns should remain
    assert "x" in result.columns
    assert "y" in result.columns
    assert "z" in result.columns
    assert result["z"].to_list() == [7, 8, 9]


def test_entity_key_works_with_single_column():
    # Given a DataFrame
    df = pl.DataFrame({"user_id": ["alice", "bob"]})

    # When applying entity_key with single column
    transform = entity_key("user_id", alias="key")
    result = df.pipe(transform)

    # Then it should create the key
    assert "key" in result.columns
    assert len(result["key"]) == 2


def test_entity_key_handles_nulls():
    # Given a DataFrame with null values
    df = pl.DataFrame({"a": ["foo", None], "b": ["bar", "baz"]})

    # When applying entity_key
    transform = entity_key("a", "b", alias="key")
    result = df.pipe(transform)

    # Then it should handle nulls consistently
    assert len(result) == 2
    assert result["key"][0] != result["key"][1]


def test_entity_key_different_columns_different_keys():
    # Given a DataFrame
    df = pl.DataFrame({"a": [1], "b": [2], "c": [3]})

    # When creating keys from different column combinations
    transform_ab = entity_key("a", "b", alias="ab_key")
    transform_ac = entity_key("a", "c", alias="ac_key")

    result_ab = df.pipe(transform_ab)
    result_ac = df.pipe(transform_ac)

    # Then keys should differ
    assert result_ab["ab_key"][0] != result_ac["ac_key"][0]
