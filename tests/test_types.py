"""
Tests for the unified type system.

This module tests:
- Type creation and properties
- Polars type conversion (to/from canonical)
- DuckDB type conversion (to/from canonical)
- Aggregation output types
- Schema normalization and equivalence
- JSON serialization/deserialization
"""

import pytest
import polars as pl

from mlforge.types import (
    DataType,
    TypeKind,
    boolean,
    date,
    datetime,
    decimal,
    duration,
    float32,
    float64,
    from_duckdb,
    from_polars,
    from_polars_string,
    get_aggregation_output_type,
    int8,
    int16,
    int32,
    int64,
    normalize_schema,
    schemas_equivalent,
    string,
    time,
    to_duckdb,
    to_polars,
    uint8,
    uint16,
    uint32,
    uint64,
    unknown,
)


class TestDataType:
    """Tests for DataType class."""

    def test_create_simple_type(self):
        """Create a simple type with default nullable."""
        dt = DataType(TypeKind.INT64)
        assert dt.kind == TypeKind.INT64
        assert dt.nullable is True
        assert dt.timezone is None
        assert dt.precision is None
        assert dt.scale is None

    def test_create_non_nullable_type(self):
        """Create a non-nullable type."""
        dt = DataType(TypeKind.STRING, nullable=False)
        assert dt.kind == TypeKind.STRING
        assert dt.nullable is False

    def test_create_datetime_with_timezone(self):
        """Create datetime with timezone."""
        dt = DataType(TypeKind.DATETIME, timezone="UTC")
        assert dt.kind == TypeKind.DATETIME
        assert dt.timezone == "UTC"

    def test_create_decimal_with_precision(self):
        """Create decimal with precision and scale."""
        dt = DataType(TypeKind.DECIMAL, precision=38, scale=10)
        assert dt.kind == TypeKind.DECIMAL
        assert dt.precision == 38
        assert dt.scale == 10

    def test_datatype_is_hashable(self):
        """DataType should be hashable for use in sets and dict keys."""
        dt1 = DataType(TypeKind.INT64)
        dt2 = DataType(TypeKind.INT64)
        dt3 = DataType(TypeKind.STRING)

        # Same types should have same hash
        assert hash(dt1) == hash(dt2)

        # Can be used in sets
        type_set = {dt1, dt2, dt3}
        assert len(type_set) == 2

        # Can be used as dict keys
        type_dict = {dt1: "int", dt3: "str"}
        assert type_dict[dt2] == "int"

    def test_datatype_is_immutable(self):
        """DataType should be immutable (frozen dataclass)."""
        dt = DataType(TypeKind.INT64)
        with pytest.raises(Exception):  # FrozenInstanceError
            dt.kind = TypeKind.STRING  # type: ignore

    def test_datatype_equality(self):
        """DataType equality should work correctly."""
        dt1 = DataType(TypeKind.INT64)
        dt2 = DataType(TypeKind.INT64)
        dt3 = DataType(TypeKind.INT64, nullable=False)
        dt4 = DataType(TypeKind.STRING)

        assert dt1 == dt2
        assert dt1 != dt3  # Different nullable
        assert dt1 != dt4  # Different kind


class TestCanonicalString:
    """Tests for canonical string representation."""

    def test_simple_type_to_string(self):
        """Simple types should convert to lowercase kind."""
        assert DataType(TypeKind.INT64).to_canonical_string() == "int64"
        assert DataType(TypeKind.FLOAT64).to_canonical_string() == "float64"
        assert DataType(TypeKind.STRING).to_canonical_string() == "string"
        assert DataType(TypeKind.BOOLEAN).to_canonical_string() == "boolean"
        assert DataType(TypeKind.DATE).to_canonical_string() == "date"

    def test_datetime_with_timezone_to_string(self):
        """Datetime with timezone should include timezone in brackets."""
        dt = DataType(TypeKind.DATETIME, timezone="UTC")
        assert dt.to_canonical_string() == "datetime[UTC]"

        dt2 = DataType(TypeKind.DATETIME, timezone="America/New_York")
        assert dt2.to_canonical_string() == "datetime[America/New_York]"

    def test_datetime_without_timezone_to_string(self):
        """Datetime without timezone should be plain datetime."""
        dt = DataType(TypeKind.DATETIME)
        assert dt.to_canonical_string() == "datetime"

    def test_decimal_with_precision_to_string(self):
        """Decimal with precision should include precision in brackets."""
        dt = DataType(TypeKind.DECIMAL, precision=38, scale=10)
        assert dt.to_canonical_string() == "decimal[38,10]"

        dt2 = DataType(TypeKind.DECIMAL, precision=18)
        assert dt2.to_canonical_string() == "decimal[18]"

    def test_from_canonical_string(self):
        """Parse canonical string representation."""
        assert DataType.from_canonical_string("int64") == DataType(
            TypeKind.INT64
        )
        assert DataType.from_canonical_string("datetime[UTC]") == DataType(
            TypeKind.DATETIME, timezone="UTC"
        )
        assert DataType.from_canonical_string("decimal[38,10]") == DataType(
            TypeKind.DECIMAL, precision=38, scale=10
        )


class TestJsonSerialization:
    """Tests for JSON serialization/deserialization."""

    def test_simple_type_to_json(self):
        """Simple types should serialize to minimal JSON."""
        dt = DataType(TypeKind.INT64)
        json_dict = dt.to_json()
        assert json_dict == {"kind": "int64"}

    def test_non_nullable_to_json(self):
        """Non-nullable types should include nullable=False."""
        dt = DataType(TypeKind.INT64, nullable=False)
        json_dict = dt.to_json()
        assert json_dict == {"kind": "int64", "nullable": False}

    def test_datetime_with_timezone_to_json(self):
        """Datetime with timezone should include timezone."""
        dt = DataType(TypeKind.DATETIME, timezone="UTC")
        json_dict = dt.to_json()
        assert json_dict == {"kind": "datetime", "timezone": "UTC"}

    def test_decimal_to_json(self):
        """Decimal should include precision and scale."""
        dt = DataType(TypeKind.DECIMAL, precision=38, scale=10)
        json_dict = dt.to_json()
        assert json_dict == {
            "kind": "decimal",
            "precision": 38,
            "scale": 10,
        }

    def test_json_roundtrip(self):
        """Types should survive JSON roundtrip."""
        types = [
            DataType(TypeKind.INT64),
            DataType(TypeKind.STRING, nullable=False),
            DataType(TypeKind.DATETIME, timezone="UTC"),
            DataType(TypeKind.DECIMAL, precision=38, scale=10),
        ]
        for dt in types:
            json_dict = dt.to_json()
            restored = DataType.from_json(json_dict)
            assert restored == dt


class TestTypePredicates:
    """Tests for type predicate methods."""

    def test_is_numeric(self):
        """is_numeric should return True for numeric types."""
        numeric_types = [
            TypeKind.INT8,
            TypeKind.INT16,
            TypeKind.INT32,
            TypeKind.INT64,
            TypeKind.UINT8,
            TypeKind.UINT16,
            TypeKind.UINT32,
            TypeKind.UINT64,
            TypeKind.FLOAT32,
            TypeKind.FLOAT64,
            TypeKind.DECIMAL,
        ]
        for kind in numeric_types:
            assert DataType(kind).is_numeric() is True

        non_numeric = [TypeKind.STRING, TypeKind.BOOLEAN, TypeKind.DATE]
        for kind in non_numeric:
            assert DataType(kind).is_numeric() is False

    def test_is_integer(self):
        """is_integer should return True for integer types."""
        integer_types = [
            TypeKind.INT8,
            TypeKind.INT16,
            TypeKind.INT32,
            TypeKind.INT64,
            TypeKind.UINT8,
            TypeKind.UINT16,
            TypeKind.UINT32,
            TypeKind.UINT64,
        ]
        for kind in integer_types:
            assert DataType(kind).is_integer() is True

        non_integer = [TypeKind.FLOAT32, TypeKind.FLOAT64, TypeKind.STRING]
        for kind in non_integer:
            assert DataType(kind).is_integer() is False

    def test_is_floating(self):
        """is_floating should return True for floating point types."""
        assert DataType(TypeKind.FLOAT32).is_floating() is True
        assert DataType(TypeKind.FLOAT64).is_floating() is True
        assert DataType(TypeKind.INT64).is_floating() is False

    def test_is_temporal(self):
        """is_temporal should return True for temporal types."""
        temporal_types = [
            TypeKind.DATE,
            TypeKind.DATETIME,
            TypeKind.TIME,
            TypeKind.DURATION,
        ]
        for kind in temporal_types:
            assert DataType(kind).is_temporal() is True

        assert DataType(TypeKind.STRING).is_temporal() is False


class TestConvenienceConstructors:
    """Tests for convenience constructor functions."""

    def test_integer_constructors(self):
        """Integer convenience constructors should work."""
        assert int8() == DataType(TypeKind.INT8)
        assert int16() == DataType(TypeKind.INT16)
        assert int32() == DataType(TypeKind.INT32)
        assert int64() == DataType(TypeKind.INT64)
        assert uint8() == DataType(TypeKind.UINT8)
        assert uint16() == DataType(TypeKind.UINT16)
        assert uint32() == DataType(TypeKind.UINT32)
        assert uint64() == DataType(TypeKind.UINT64)

    def test_float_constructors(self):
        """Float convenience constructors should work."""
        assert float32() == DataType(TypeKind.FLOAT32)
        assert float64() == DataType(TypeKind.FLOAT64)

    def test_other_constructors(self):
        """Other convenience constructors should work."""
        assert string() == DataType(TypeKind.STRING)
        assert boolean() == DataType(TypeKind.BOOLEAN)
        assert date() == DataType(TypeKind.DATE)
        assert time() == DataType(TypeKind.TIME)
        assert duration() == DataType(TypeKind.DURATION)
        assert unknown() == DataType(TypeKind.UNKNOWN)

    def test_datetime_constructor(self):
        """Datetime constructor with timezone should work."""
        assert datetime() == DataType(TypeKind.DATETIME)
        assert datetime("UTC") == DataType(TypeKind.DATETIME, timezone="UTC")

    def test_decimal_constructor(self):
        """Decimal constructor with precision should work."""
        assert decimal() == DataType(TypeKind.DECIMAL)
        assert decimal(38, 10) == DataType(
            TypeKind.DECIMAL, precision=38, scale=10
        )

    def test_nullable_parameter(self):
        """Nullable parameter should work for all constructors."""
        assert int64(nullable=False) == DataType(TypeKind.INT64, nullable=False)
        assert string(nullable=False) == DataType(
            TypeKind.STRING, nullable=False
        )


class TestPolarsConversion:
    """Tests for Polars type conversion."""

    def test_from_polars_integer_types(self):
        """Convert Polars integer types to canonical."""
        assert from_polars(pl.Int8).kind == TypeKind.INT8
        assert from_polars(pl.Int16).kind == TypeKind.INT16
        assert from_polars(pl.Int32).kind == TypeKind.INT32
        assert from_polars(pl.Int64).kind == TypeKind.INT64
        assert from_polars(pl.UInt8).kind == TypeKind.UINT8
        assert from_polars(pl.UInt16).kind == TypeKind.UINT16
        assert from_polars(pl.UInt32).kind == TypeKind.UINT32
        assert from_polars(pl.UInt64).kind == TypeKind.UINT64

    def test_from_polars_float_types(self):
        """Convert Polars float types to canonical."""
        assert from_polars(pl.Float32).kind == TypeKind.FLOAT32
        assert from_polars(pl.Float64).kind == TypeKind.FLOAT64

    def test_from_polars_string_types(self):
        """Convert Polars string types to canonical."""
        assert from_polars(pl.Utf8).kind == TypeKind.STRING
        assert from_polars(pl.String).kind == TypeKind.STRING

    def test_from_polars_boolean(self):
        """Convert Polars boolean to canonical."""
        assert from_polars(pl.Boolean).kind == TypeKind.BOOLEAN

    def test_from_polars_temporal_types(self):
        """Convert Polars temporal types to canonical."""
        assert from_polars(pl.Date).kind == TypeKind.DATE
        assert from_polars(pl.Time).kind == TypeKind.TIME
        assert from_polars(pl.Duration).kind == TypeKind.DURATION

    def test_from_polars_datetime(self):
        """Convert Polars datetime types to canonical."""
        # Simple datetime
        dt = from_polars(pl.Datetime("us"))
        assert dt.kind == TypeKind.DATETIME

        # Datetime with timezone
        dt_tz = from_polars(pl.Datetime("us", "UTC"))
        assert dt_tz.kind == TypeKind.DATETIME
        assert dt_tz.timezone == "UTC"

    def test_from_polars_string_representation(self):
        """Convert Polars dtype string representation."""
        assert from_polars_string("Int64").kind == TypeKind.INT64
        assert from_polars_string("Float64").kind == TypeKind.FLOAT64
        assert from_polars_string("Utf8").kind == TypeKind.STRING
        assert from_polars_string("Boolean").kind == TypeKind.BOOLEAN
        assert from_polars_string("Date").kind == TypeKind.DATE

    def test_from_polars_string_datetime_with_timezone(self):
        """Convert Polars datetime string with timezone."""
        dt_str = "Datetime(time_unit='us', time_zone='UTC')"
        dt = from_polars_string(dt_str)
        assert dt.kind == TypeKind.DATETIME
        assert dt.timezone == "UTC"

    def test_to_polars_integer_types(self):
        """Convert canonical integer types to Polars."""
        assert to_polars(int8()) == pl.Int8
        assert to_polars(int16()) == pl.Int16
        assert to_polars(int32()) == pl.Int32
        assert to_polars(int64()) == pl.Int64
        assert to_polars(uint8()) == pl.UInt8
        assert to_polars(uint16()) == pl.UInt16
        assert to_polars(uint32()) == pl.UInt32
        assert to_polars(uint64()) == pl.UInt64

    def test_to_polars_float_types(self):
        """Convert canonical float types to Polars."""
        assert to_polars(float32()) == pl.Float32
        assert to_polars(float64()) == pl.Float64

    def test_to_polars_other_types(self):
        """Convert other canonical types to Polars."""
        assert to_polars(string()) == pl.Utf8
        assert to_polars(boolean()) == pl.Boolean
        assert to_polars(date()) == pl.Date
        assert to_polars(time()) == pl.Time
        assert to_polars(duration()) == pl.Duration

    def test_to_polars_datetime(self):
        """Convert canonical datetime to Polars."""
        pl_dt = to_polars(datetime())
        assert pl_dt == pl.Datetime("us")

        pl_dt_tz = to_polars(datetime("UTC"))
        assert pl_dt_tz == pl.Datetime("us", "UTC")


class TestDuckDBConversion:
    """Tests for DuckDB type conversion."""

    def test_from_duckdb_integer_types(self):
        """Convert DuckDB integer types to canonical."""
        assert from_duckdb("TINYINT").kind == TypeKind.INT8
        assert from_duckdb("SMALLINT").kind == TypeKind.INT16
        assert from_duckdb("INTEGER").kind == TypeKind.INT32
        assert from_duckdb("INT").kind == TypeKind.INT32
        assert from_duckdb("BIGINT").kind == TypeKind.INT64

    def test_from_duckdb_unsigned_types(self):
        """Convert DuckDB unsigned types to canonical."""
        assert from_duckdb("UTINYINT").kind == TypeKind.UINT8
        assert from_duckdb("USMALLINT").kind == TypeKind.UINT16
        assert from_duckdb("UINTEGER").kind == TypeKind.UINT32
        assert from_duckdb("UBIGINT").kind == TypeKind.UINT64

    def test_from_duckdb_float_types(self):
        """Convert DuckDB float types to canonical."""
        assert from_duckdb("FLOAT").kind == TypeKind.FLOAT32
        assert from_duckdb("REAL").kind == TypeKind.FLOAT32
        assert from_duckdb("DOUBLE").kind == TypeKind.FLOAT64

    def test_from_duckdb_string_types(self):
        """Convert DuckDB string types to canonical."""
        assert from_duckdb("VARCHAR").kind == TypeKind.STRING
        assert from_duckdb("TEXT").kind == TypeKind.STRING
        assert from_duckdb("STRING").kind == TypeKind.STRING

    def test_from_duckdb_boolean(self):
        """Convert DuckDB boolean to canonical."""
        assert from_duckdb("BOOLEAN").kind == TypeKind.BOOLEAN
        assert from_duckdb("BOOL").kind == TypeKind.BOOLEAN

    def test_from_duckdb_temporal_types(self):
        """Convert DuckDB temporal types to canonical."""
        assert from_duckdb("DATE").kind == TypeKind.DATE
        assert from_duckdb("TIMESTAMP").kind == TypeKind.DATETIME
        assert from_duckdb("TIME").kind == TypeKind.TIME
        assert from_duckdb("INTERVAL").kind == TypeKind.DURATION

    def test_from_duckdb_decimal(self):
        """Convert DuckDB decimal types to canonical."""
        dt = from_duckdb("DECIMAL(10,2)")
        assert dt.kind == TypeKind.DECIMAL
        assert dt.precision == 10
        assert dt.scale == 2

    def test_from_duckdb_case_insensitive(self):
        """DuckDB type conversion should be case insensitive."""
        assert from_duckdb("bigint").kind == TypeKind.INT64
        assert from_duckdb("BIGINT").kind == TypeKind.INT64
        assert from_duckdb("BigInt").kind == TypeKind.INT64

    def test_to_duckdb_integer_types(self):
        """Convert canonical integer types to DuckDB."""
        assert to_duckdb(int8()) == "TINYINT"
        assert to_duckdb(int16()) == "SMALLINT"
        assert to_duckdb(int32()) == "INTEGER"
        assert to_duckdb(int64()) == "BIGINT"
        assert to_duckdb(uint8()) == "UTINYINT"
        assert to_duckdb(uint16()) == "USMALLINT"
        assert to_duckdb(uint32()) == "UINTEGER"
        assert to_duckdb(uint64()) == "UBIGINT"

    def test_to_duckdb_float_types(self):
        """Convert canonical float types to DuckDB."""
        assert to_duckdb(float32()) == "FLOAT"
        assert to_duckdb(float64()) == "DOUBLE"

    def test_to_duckdb_other_types(self):
        """Convert other canonical types to DuckDB."""
        assert to_duckdb(string()) == "VARCHAR"
        assert to_duckdb(boolean()) == "BOOLEAN"
        assert to_duckdb(date()) == "DATE"
        assert to_duckdb(datetime()) == "TIMESTAMP"
        assert to_duckdb(time()) == "TIME"
        assert to_duckdb(duration()) == "INTERVAL"

    def test_to_duckdb_datetime_with_timezone(self):
        """Convert datetime with timezone to DuckDB."""
        assert to_duckdb(datetime("UTC")) == "TIMESTAMP WITH TIME ZONE"

    def test_to_duckdb_decimal(self):
        """Convert decimal to DuckDB."""
        assert to_duckdb(decimal(10, 2)) == "DECIMAL(10,2)"
        assert to_duckdb(decimal(38)) == "DECIMAL(38)"
        assert to_duckdb(decimal()) == "DECIMAL"


class TestCrossEngineEquivalence:
    """Tests for cross-engine type equivalence."""

    def test_polars_duckdb_equivalence(self):
        """Same logical types from different engines should be equal."""
        # Integer types
        assert from_polars(pl.Int64) == from_duckdb("BIGINT")
        assert from_polars(pl.Int32) == from_duckdb("INTEGER")
        assert from_polars(pl.Int16) == from_duckdb("SMALLINT")
        assert from_polars(pl.Int8) == from_duckdb("TINYINT")

        # Float types
        assert from_polars(pl.Float64) == from_duckdb("DOUBLE")
        assert from_polars(pl.Float32) == from_duckdb("FLOAT")

        # String types
        assert from_polars(pl.Utf8) == from_duckdb("VARCHAR")

        # Boolean
        assert from_polars(pl.Boolean) == from_duckdb("BOOLEAN")

        # Temporal types
        assert from_polars(pl.Date) == from_duckdb("DATE")
        assert from_polars(pl.Datetime("us")) == from_duckdb("TIMESTAMP")


class TestAggregationOutputTypes:
    """Tests for aggregation output type mapping."""

    def test_count_returns_int64(self):
        """count aggregation should always return int64."""
        assert get_aggregation_output_type("count", int64()) == int64()
        assert get_aggregation_output_type("count", float64()) == int64()
        assert get_aggregation_output_type("count", string()) == int64()

    def test_mean_returns_float64(self):
        """mean aggregation should always return float64."""
        assert get_aggregation_output_type("mean", int64()) == float64()
        assert get_aggregation_output_type("mean", float32()) == float64()
        assert get_aggregation_output_type("avg", int64()) == float64()

    def test_std_returns_float64(self):
        """std aggregation should always return float64."""
        assert get_aggregation_output_type("std", int64()) == float64()
        assert get_aggregation_output_type("stddev", int64()) == float64()
        assert get_aggregation_output_type("stddev_samp", int64()) == float64()

    def test_median_returns_float64(self):
        """median aggregation should always return float64."""
        assert get_aggregation_output_type("median", int64()) == float64()

    def test_sum_preserves_float_type(self):
        """sum of floats should return float64."""
        assert get_aggregation_output_type("sum", float64()) == float64()
        assert get_aggregation_output_type("sum", float32()) == float32()

    def test_sum_of_integers_returns_int64(self):
        """sum of integers should return int64 to avoid overflow."""
        assert get_aggregation_output_type("sum", int32()) == int64()
        assert get_aggregation_output_type("sum", int8()) == int64()

    def test_min_max_preserve_type(self):
        """min/max should preserve input type."""
        assert get_aggregation_output_type("min", int32()) == int32()
        assert get_aggregation_output_type("max", float64()) == float64()
        assert get_aggregation_output_type("min", string()) == string()

    def test_first_last_preserve_type(self):
        """first/last should preserve input type."""
        assert get_aggregation_output_type("first", int64()) == int64()
        assert get_aggregation_output_type("last", string()) == string()


class TestSchemaNormalization:
    """Tests for schema normalization utilities."""

    def test_normalize_polars_schema(self):
        """Normalize Polars schema to canonical types."""
        polars_schema = {
            "id": "Int64",
            "name": "Utf8",
            "amount": "Float64",
            "active": "Boolean",
        }
        normalized = normalize_schema(polars_schema, "polars")

        assert normalized["id"] == int64()
        assert normalized["name"] == string()
        assert normalized["amount"] == float64()
        assert normalized["active"] == boolean()

    def test_normalize_duckdb_schema(self):
        """Normalize DuckDB schema to canonical types."""
        duckdb_schema = {
            "id": "BIGINT",
            "name": "VARCHAR",
            "amount": "DOUBLE",
            "active": "BOOLEAN",
        }
        normalized = normalize_schema(duckdb_schema, "duckdb")

        assert normalized["id"] == int64()
        assert normalized["name"] == string()
        assert normalized["amount"] == float64()
        assert normalized["active"] == boolean()

    def test_schemas_equivalent_same_engine(self):
        """Identical schemas from same engine should be equivalent."""
        schema1 = {"id": "Int64", "name": "Utf8"}
        schema2 = {"id": "Int64", "name": "Utf8"}

        assert schemas_equivalent(schema1, schema2, "polars", "polars")

    def test_schemas_equivalent_different_engines(self):
        """Equivalent schemas from different engines should be equivalent."""
        polars_schema = {"id": "Int64", "name": "Utf8", "amount": "Float64"}
        duckdb_schema = {"id": "BIGINT", "name": "VARCHAR", "amount": "DOUBLE"}

        assert schemas_equivalent(
            polars_schema, duckdb_schema, "polars", "duckdb"
        )

    def test_schemas_not_equivalent(self):
        """Different schemas should not be equivalent."""
        schema1 = {"id": "Int64", "name": "Utf8"}
        schema2 = {"id": "Int32", "name": "Utf8"}  # Different int type

        assert not schemas_equivalent(schema1, schema2, "polars", "polars")

    def test_schemas_different_columns_not_equivalent(self):
        """Schemas with different columns should not be equivalent."""
        schema1 = {"id": "Int64", "name": "Utf8"}
        schema2 = {"id": "Int64", "email": "Utf8"}  # Different column name

        assert not schemas_equivalent(schema1, schema2, "polars", "polars")


class TestSchemaHashConsistency:
    """Tests to verify schema hashing is consistent across engines."""

    def test_normalized_schemas_have_same_hash(self):
        """Same logical schema should produce same hash regardless of engine."""
        polars_schema = {"user_id": "Int64", "amount": "Float64"}
        duckdb_schema = {"user_id": "BIGINT", "amount": "DOUBLE"}

        polars_normalized = normalize_schema(polars_schema, "polars")
        duckdb_normalized = normalize_schema(duckdb_schema, "duckdb")

        # Canonical representations should be identical
        assert polars_normalized == duckdb_normalized

        # Converting to canonical strings should produce same result
        polars_strings = {
            k: v.to_canonical_string() for k, v in polars_normalized.items()
        }
        duckdb_strings = {
            k: v.to_canonical_string() for k, v in duckdb_normalized.items()
        }
        assert polars_strings == duckdb_strings

    def test_aggregation_output_types_consistent(self):
        """Aggregation output types should be same for both engines."""
        # The key insight: both engines should report same output types
        # for the same aggregations, enabling consistent schema hashing

        polars_count_output = get_aggregation_output_type(
            "count", from_polars(pl.Float64)
        )
        duckdb_count_output = get_aggregation_output_type(
            "count", from_duckdb("DOUBLE")
        )
        assert polars_count_output == duckdb_count_output == int64()

        polars_mean_output = get_aggregation_output_type(
            "mean", from_polars(pl.Int64)
        )
        duckdb_mean_output = get_aggregation_output_type(
            "mean", from_duckdb("BIGINT")
        )
        assert polars_mean_output == duckdb_mean_output == float64()
