"""Tests for manifest module."""

import json
import tempfile
from pathlib import Path

import polars as pl

from mlforge import Definitions, LocalStore, feature
from mlforge.manifest import (
    ColumnMetadata,
    FeatureMetadata,
    Manifest,
    derive_column_metadata,
    read_metadata_file,
    write_metadata_file,
)
from mlforge.metrics import Rolling


def test_column_metadata_to_dict_excludes_none_values():
    # Given a column with some None values
    col = ColumnMetadata(name="user_id", dtype="Int64")

    # When converting to dict
    result = col.to_dict()

    # Then None values should be excluded
    assert result == {"name": "user_id", "dtype": "Int64"}
    assert "input" not in result
    assert "agg" not in result
    assert "window" not in result


def test_column_metadata_to_dict_includes_all_values():
    # Given a column with all values set
    col = ColumnMetadata(
        name="amt__sum__7d",
        dtype="Float64",
        input="amt",
        agg="sum",
        window="7d",
    )

    # When converting to dict
    result = col.to_dict()

    # Then all values should be included
    assert result == {
        "name": "amt__sum__7d",
        "dtype": "Float64",
        "input": "amt",
        "agg": "sum",
        "window": "7d",
    }


def test_column_metadata_from_dict_creates_column():
    # Given a dictionary
    data = {"name": "user_id", "dtype": "Utf8"}

    # When creating from dict
    col = ColumnMetadata.from_dict(data)

    # Then it should create the correct object
    assert col.name == "user_id"
    assert col.dtype == "Utf8"
    assert col.input is None


def test_feature_metadata_to_dict_includes_required_fields():
    # Given feature metadata
    meta = FeatureMetadata(
        name="user_spend",
        path="/store/user_spend.parquet",
        entity="user_id",
        keys=["user_id"],
        source="data/transactions.parquet",
        row_count=1000,
        last_updated="2024-01-16T08:30:00Z",
    )

    # When converting to dict
    result = meta.to_dict()

    # Then required fields should be present
    assert result["name"] == "user_spend"
    assert result["path"] == "/store/user_spend.parquet"
    assert result["entity"] == "user_id"
    assert result["keys"] == ["user_id"]
    assert result["source"] == "data/transactions.parquet"
    assert result["row_count"] == 1000


def test_feature_metadata_to_dict_excludes_none_optional_fields():
    # Given feature metadata without optional fields
    meta = FeatureMetadata(
        name="test",
        path="/store/test.parquet",
        entity="id",
        keys=["id"],
        source="data.parquet",
        row_count=100,
        last_updated="2024-01-01T00:00:00Z",
    )

    # When converting to dict
    result = meta.to_dict()

    # Then optional None fields should be excluded
    assert "timestamp" not in result
    assert "interval" not in result
    assert "description" not in result


def test_feature_metadata_from_dict_roundtrip():
    # Given feature metadata with all fields
    original = FeatureMetadata(
        name="user_spend",
        path="/store/user_spend.parquet",
        entity="user_id",
        keys=["user_id", "merchant_id"],
        source="data/transactions.parquet",
        row_count=5000,
        last_updated="2024-01-16T08:30:00Z",
        timestamp="transaction_date",
        interval="1d",
        columns=[ColumnMetadata(name="amt", dtype="Float64")],
        tags=["users", "spending"],
        description="User spending features",
    )

    # When converting to dict and back
    data = original.to_dict()
    restored = FeatureMetadata.from_dict(data)

    # Then it should match the original
    assert restored.name == original.name
    assert restored.keys == original.keys
    assert restored.timestamp == original.timestamp
    assert restored.tags == original.tags
    assert len(restored.columns) == 1


def test_manifest_add_feature():
    # Given an empty manifest
    manifest = Manifest()

    # When adding a feature
    meta = FeatureMetadata(
        name="test_feature",
        path="/store/test.parquet",
        entity="id",
        keys=["id"],
        source="data.parquet",
        row_count=100,
        last_updated="2024-01-01T00:00:00Z",
    )
    manifest.add_feature(meta)

    # Then it should be retrievable
    assert "test_feature" in manifest.features
    assert manifest.get_feature("test_feature") == meta


def test_manifest_remove_feature():
    # Given a manifest with a feature
    manifest = Manifest()
    meta = FeatureMetadata(
        name="to_remove",
        path="/store/to_remove.parquet",
        entity="id",
        keys=["id"],
        source="data.parquet",
        row_count=100,
        last_updated="2024-01-01T00:00:00Z",
    )
    manifest.add_feature(meta)

    # When removing the feature
    manifest.remove_feature("to_remove")

    # Then it should be gone
    assert manifest.get_feature("to_remove") is None


def test_manifest_to_dict_roundtrip():
    # Given a manifest with features
    manifest = Manifest(version="1.0", generated_at="2024-01-16T08:30:00Z")
    manifest.add_feature(
        FeatureMetadata(
            name="feature1",
            path="/store/feature1.parquet",
            entity="id",
            keys=["id"],
            source="data.parquet",
            row_count=100,
            last_updated="2024-01-01T00:00:00Z",
        )
    )

    # When converting to dict and back
    data = manifest.to_dict()
    restored = Manifest.from_dict(data)

    # Then it should match
    assert restored.version == manifest.version
    assert "feature1" in restored.features


def test_write_and_read_metadata_file():
    # Given feature metadata
    meta = FeatureMetadata(
        name="test_feature",
        path="/store/test.parquet",
        entity="id",
        keys=["id"],
        source="data.parquet",
        row_count=100,
        last_updated="2024-01-01T00:00:00Z",
        tags=["test"],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.meta.json"

        # When writing and reading
        write_metadata_file(path, meta)
        restored = read_metadata_file(path)

        # Then it should match
        assert restored is not None
        assert restored.name == meta.name
        assert restored.tags == meta.tags


def test_read_metadata_file_returns_none_for_nonexistent():
    # Given a nonexistent path
    path = Path("/nonexistent/path.meta.json")

    # When reading
    result = read_metadata_file(path)

    # Then it should return None
    assert result is None


def test_read_metadata_file_handles_corrupt_json(tmp_path):
    # Given a file with invalid JSON
    path = tmp_path / "corrupt.meta.json"
    path.write_text("{invalid json content")

    # When reading
    result = read_metadata_file(path)

    # Then it should return None and log warning
    assert result is None


def test_read_metadata_file_handles_schema_mismatch(tmp_path):
    # Given a JSON file missing required keys
    path = tmp_path / "mismatch.meta.json"
    path.write_text(
        '{"name": "test"}'
    )  # Missing required fields like path, entity, etc.

    # When reading
    result = read_metadata_file(path)

    # Then it should return None and log warning
    assert result is None


def test_derive_column_metadata_for_simple_columns():
    # Given a simple feature
    @feature(keys=["user_id"], source="data.parquet")
    def simple_feature(df):
        return df

    schema = {"user_id": "Utf8", "value": "Float64"}

    # When deriving column metadata
    base_columns, feature_columns = derive_column_metadata(simple_feature, schema)

    # Then it should have basic dtype info in base columns
    assert len(base_columns) == 2
    assert len(feature_columns) == 0
    assert any(c.name == "user_id" and c.dtype == "Utf8" for c in base_columns)
    assert any(c.name == "value" and c.dtype == "Float64" for c in base_columns)


def test_derive_column_metadata_for_rolling_columns():
    # Given a feature with Rolling metrics
    @feature(
        keys=["user_id"],
        source="data.parquet",
        timestamp="event_time",
        interval="1d",
        metrics=[
            Rolling(windows=["7d", "30d"], aggregations={"amt": ["sum", "count"]})
        ],
    )
    def rolling_feature(df):
        return df

    # Schema with pattern: {tag}__{column}__{agg}__{interval}__{window}
    schema = {
        "user_id": "Utf8",
        "event_time": "Datetime",
        "rolling_feature__amt__sum__1d__7d": "Float64",
        "rolling_feature__amt__count__1d__7d": "Int64",
        "rolling_feature__amt__sum__1d__30d": "Float64",
        "rolling_feature__amt__count__1d__30d": "Int64",
    }

    # When deriving column metadata
    base_columns, feature_columns = derive_column_metadata(rolling_feature, schema)

    # Then base columns should contain keys and timestamp
    assert len(base_columns) == 2
    assert any(c.name == "user_id" for c in base_columns)
    assert any(c.name == "event_time" for c in base_columns)

    # And feature columns should contain rolling metrics
    assert len(feature_columns) == 4
    sum_7d = next(
        (c for c in feature_columns if c.name == "rolling_feature__amt__sum__1d__7d"),
        None,
    )
    assert sum_7d is not None
    assert sum_7d.input == "amt"
    assert sum_7d.agg == "sum"
    assert sum_7d.window == "7d"


def test_derive_column_metadata_with_validators():
    # Given a feature with validators
    from mlforge.validators import greater_than, not_null

    @feature(
        keys=["user_id"],
        source="data.parquet",
        validators={
            "user_id": [not_null()],
            "amount": [not_null(), greater_than(0)],
        },
    )
    def validated_feature(df):
        return df

    schema = {"user_id": "Utf8", "amount": "Float64"}

    # When deriving column metadata
    base_columns, feature_columns = derive_column_metadata(validated_feature, schema)

    # Then base columns should include validators as structured dicts
    assert len(base_columns) == 2
    assert len(feature_columns) == 0

    user_id_col = next((c for c in base_columns if c.name == "user_id"), None)
    assert user_id_col is not None
    assert user_id_col.validators == [{"validator": "not_null"}]

    amount_col = next((c for c in base_columns if c.name == "amount"), None)
    assert amount_col is not None
    assert amount_col.validators == [
        {"validator": "not_null"},
        {"validator": "greater_than", "value": 0},
    ]


def test_feature_metadata_serializes_columns_and_features():
    # Given metadata with both base columns and feature columns
    meta = FeatureMetadata(
        name="test_feature",
        path="store/test.parquet",
        entity="user_id",
        keys=["user_id"],
        source="data.parquet",
        row_count=100,
        last_updated="2024-01-01T00:00:00Z",
        columns=[
            ColumnMetadata(name="user_id", dtype="Utf8"),
            ColumnMetadata(
                name="amount",
                dtype="Float64",
                validators=[{"validator": "not_null"}],
            ),
        ],
        features=[
            ColumnMetadata(
                name="test_feature__amt__sum__1d__7d",
                dtype="Float64",
                input="amt",
                agg="sum",
                window="7d",
            )
        ],
    )

    # When converting to dict
    result = meta.to_dict()

    # Then both columns and features should be present
    assert "columns" in result
    assert "features" in result
    assert len(result["columns"]) == 2
    assert len(result["features"]) == 1
    assert result["columns"][1]["validators"] == [{"validator": "not_null"}]
    assert result["features"][0]["input"] == "amt"


def test_build_creates_metadata_file():
    # Given a feature and store
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]}).write_parquet(
            source_path
        )

        @feature(keys=["id"], source=str(source_path), description="Test feature")
        def test_feature(df):
            return df

        store = LocalStore(tmpdir)
        defs = Definitions(name="test", features=[test_feature], offline_store=store)

        # When building
        defs.build(preview=False)

        # Then metadata file should exist
        meta_path = Path(tmpdir) / "_metadata" / "test_feature.meta.json"
        assert meta_path.exists()

        # And contain correct data
        with open(meta_path) as f:
            data = json.load(f)
        assert data["name"] == "test_feature"
        assert data["row_count"] == 3
        assert data["description"] == "Test feature"
        assert "columns" in data
        # Features should not be present if empty
        assert "features" not in data or len(data.get("features", [])) == 0


def test_build_updates_metadata_on_rebuild():
    # Given an existing feature
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "data.parquet"
        pl.DataFrame({"id": [1, 2]}).write_parquet(source_path)

        @feature(keys=["id"], source=str(source_path))
        def updatable_feature(df):
            return df

        store = LocalStore(tmpdir)
        defs = Definitions(
            name="test", features=[updatable_feature], offline_store=store
        )

        # When building twice with force
        defs.build(preview=False)

        # Update source data
        pl.DataFrame({"id": [1, 2, 3, 4, 5]}).write_parquet(source_path)
        defs.build(force=True, preview=False)

        # Then metadata should reflect new data
        meta = store.read_metadata("updatable_feature")
        assert meta is not None
        assert meta.row_count == 5


def test_local_store_metadata_path_for():
    # Given a LocalStore
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)

        # When getting metadata path
        path = store.metadata_path_for("my_feature")

        # Then it should return correct path
        assert path == Path(tmpdir) / "_metadata" / "my_feature.meta.json"


def test_local_store_list_metadata_returns_all():
    # Given a store with multiple metadata files
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(tmpdir)

        # Create some metadata files
        for i in range(3):
            meta = FeatureMetadata(
                name=f"feature_{i}",
                path=f"/store/feature_{i}.parquet",
                entity="id",
                keys=["id"],
                source="data.parquet",
                row_count=100 * (i + 1),
                last_updated="2024-01-01T00:00:00Z",
            )
            store.write_metadata(f"feature_{i}", meta)

        # When listing metadata
        metadata_list = store.list_metadata()

        # Then all should be returned
        assert len(metadata_list) == 3
        names = {m.name for m in metadata_list}
        assert names == {"feature_0", "feature_1", "feature_2"}
