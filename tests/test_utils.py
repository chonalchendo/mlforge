import polars as pl
import pytest

from mlforge.utils import surrogate_key


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
