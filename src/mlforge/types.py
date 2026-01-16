"""
Unified type system for mlforge.

This module provides a canonical type system that normalizes engine-specific
types (Polars, DuckDB, future Spark) into a consistent representation for
metadata, schema hashing, and type comparisons.

Design inspired by:
- Apache Arrow: Industry standard type names
- Ibis: Bidirectional conversion pattern
- Feast: Simple enum-based approach

Usage:
    from mlforge.types import DataType, TypeKind, from_polars, from_duckdb

    # Convert from engine-specific types
    canonical = from_polars(pl.Int64)
    canonical = from_duckdb("BIGINT")

    # Both produce: DataType(kind=TypeKind.INT64)

    # Serialize to JSON for metadata
    {"dtype": canonical.to_canonical_string()}  # "int64"

    # Get aggregation output types
    output_type = get_aggregation_output_type("count", input_type)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TypeKind(Enum):
    """
    Canonical type kinds for mlforge.

    Type names are Arrow-compatible for industry standard interoperability.
    """

    # Integer types (signed)
    INT8 = "int8"
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"

    # Integer types (unsigned)
    UINT8 = "uint8"
    UINT16 = "uint16"
    UINT32 = "uint32"
    UINT64 = "uint64"

    # Floating point types
    FLOAT32 = "float32"
    FLOAT64 = "float64"

    # String type
    STRING = "string"

    # Boolean type
    BOOLEAN = "boolean"

    # Temporal types
    DATE = "date"
    DATETIME = "datetime"
    TIME = "time"
    DURATION = "duration"

    # Complex types (for future expansion)
    DECIMAL = "decimal"
    LIST = "list"
    STRUCT = "struct"

    # Fallback for unknown types
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DataType:
    """
    Immutable, hashable type representation.

    This is the canonical type used throughout mlforge for type comparisons,
    schema hashing, and metadata storage.

    Attributes:
        kind: The fundamental type category
        nullable: Whether null values are allowed (default True)
        timezone: Timezone for DATETIME types (e.g., "UTC", "America/New_York")
        precision: Decimal precision (total digits)
        scale: Decimal scale (digits after decimal point)

    Example:
        # Simple types
        DataType(TypeKind.INT64)
        DataType(TypeKind.STRING, nullable=False)

        # Datetime with timezone
        DataType(TypeKind.DATETIME, timezone="UTC")

        # Decimal with precision
        DataType(TypeKind.DECIMAL, precision=38, scale=10)
    """

    kind: TypeKind
    nullable: bool = True
    timezone: str | None = None
    precision: int | None = None
    scale: int | None = None

    def to_canonical_string(self) -> str:
        """
        Convert to canonical string representation.

        This is the format used in metadata files for human readability
        and consistent hashing across engines.

        Returns:
            Canonical type string (e.g., "int64", "datetime[UTC]")
        """
        base = self.kind.value

        # Add timezone for datetime
        if self.kind == TypeKind.DATETIME and self.timezone:
            return f"{base}[{self.timezone}]"

        # Add precision/scale for decimal
        if self.kind == TypeKind.DECIMAL:
            if self.precision is not None and self.scale is not None:
                return f"{base}[{self.precision},{self.scale}]"
            elif self.precision is not None:
                return f"{base}[{self.precision}]"

        return base

    def to_json(self) -> dict[str, Any]:
        """
        Serialize to JSON-compatible dict.

        Returns:
            Dictionary suitable for JSON serialization
        """
        result: dict[str, Any] = {"kind": self.kind.value}

        if not self.nullable:
            result["nullable"] = False

        if self.timezone is not None:
            result["timezone"] = self.timezone

        if self.precision is not None:
            result["precision"] = self.precision

        if self.scale is not None:
            result["scale"] = self.scale

        return result

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "DataType":
        """
        Deserialize from JSON dict.

        Args:
            data: Dictionary from JSON deserialization

        Returns:
            DataType instance
        """
        return cls(
            kind=TypeKind(data["kind"]),
            nullable=data.get("nullable", True),
            timezone=data.get("timezone"),
            precision=data.get("precision"),
            scale=data.get("scale"),
        )

    @classmethod
    def from_canonical_string(cls, s: str) -> "DataType":
        """
        Parse canonical string representation.

        Args:
            s: Canonical type string (e.g., "int64", "datetime[UTC]")

        Returns:
            DataType instance
        """
        # Handle parameterized types like "datetime[UTC]" or "decimal[38,10]"
        if "[" in s and s.endswith("]"):
            base, params = s[:-1].split("[", 1)
            kind = TypeKind(base)

            if kind == TypeKind.DATETIME:
                return cls(kind=kind, timezone=params)
            elif kind == TypeKind.DECIMAL:
                parts = params.split(",")
                precision = int(parts[0])
                scale = int(parts[1]) if len(parts) > 1 else None
                return cls(kind=kind, precision=precision, scale=scale)

        return cls(kind=TypeKind(s))

    def is_numeric(self) -> bool:
        """Check if this is a numeric type."""
        return self.kind in {
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
        }

    def is_integer(self) -> bool:
        """Check if this is an integer type."""
        return self.kind in {
            TypeKind.INT8,
            TypeKind.INT16,
            TypeKind.INT32,
            TypeKind.INT64,
            TypeKind.UINT8,
            TypeKind.UINT16,
            TypeKind.UINT32,
            TypeKind.UINT64,
        }

    def is_floating(self) -> bool:
        """Check if this is a floating point type."""
        return self.kind in {TypeKind.FLOAT32, TypeKind.FLOAT64}

    def is_temporal(self) -> bool:
        """Check if this is a temporal type."""
        return self.kind in {
            TypeKind.DATE,
            TypeKind.DATETIME,
            TypeKind.TIME,
            TypeKind.DURATION,
        }


# =============================================================================
# Convenience constructors
# =============================================================================


def int8(nullable: bool = True) -> DataType:
    """Create int8 type."""
    return DataType(TypeKind.INT8, nullable)


def int16(nullable: bool = True) -> DataType:
    """Create int16 type."""
    return DataType(TypeKind.INT16, nullable)


def int32(nullable: bool = True) -> DataType:
    """Create int32 type."""
    return DataType(TypeKind.INT32, nullable)


def int64(nullable: bool = True) -> DataType:
    """Create int64 type."""
    return DataType(TypeKind.INT64, nullable)


def uint8(nullable: bool = True) -> DataType:
    """Create uint8 type."""
    return DataType(TypeKind.UINT8, nullable)


def uint16(nullable: bool = True) -> DataType:
    """Create uint16 type."""
    return DataType(TypeKind.UINT16, nullable)


def uint32(nullable: bool = True) -> DataType:
    """Create uint32 type."""
    return DataType(TypeKind.UINT32, nullable)


def uint64(nullable: bool = True) -> DataType:
    """Create uint64 type."""
    return DataType(TypeKind.UINT64, nullable)


def float32(nullable: bool = True) -> DataType:
    """Create float32 type."""
    return DataType(TypeKind.FLOAT32, nullable)


def float64(nullable: bool = True) -> DataType:
    """Create float64 type."""
    return DataType(TypeKind.FLOAT64, nullable)


def string(nullable: bool = True) -> DataType:
    """Create string type."""
    return DataType(TypeKind.STRING, nullable)


def boolean(nullable: bool = True) -> DataType:
    """Create boolean type."""
    return DataType(TypeKind.BOOLEAN, nullable)


def date(nullable: bool = True) -> DataType:
    """Create date type."""
    return DataType(TypeKind.DATE, nullable)


def datetime(timezone: str | None = None, nullable: bool = True) -> DataType:
    """Create datetime type with optional timezone."""
    return DataType(TypeKind.DATETIME, nullable, timezone=timezone)


def time(nullable: bool = True) -> DataType:
    """Create time type."""
    return DataType(TypeKind.TIME, nullable)


def duration(nullable: bool = True) -> DataType:
    """Create duration type."""
    return DataType(TypeKind.DURATION, nullable)


def decimal(
    precision: int | None = None,
    scale: int | None = None,
    nullable: bool = True,
) -> DataType:
    """Create decimal type with optional precision and scale."""
    return DataType(
        TypeKind.DECIMAL, nullable, precision=precision, scale=scale
    )


def unknown(nullable: bool = True) -> DataType:
    """Create unknown type (fallback for unrecognized types)."""
    return DataType(TypeKind.UNKNOWN, nullable)


# =============================================================================
# Polars type conversion
# =============================================================================

# Mapping from Polars dtype class names to TypeKind
_POLARS_TO_KIND: dict[str, TypeKind] = {
    "Int8": TypeKind.INT8,
    "Int16": TypeKind.INT16,
    "Int32": TypeKind.INT32,
    "Int64": TypeKind.INT64,
    "UInt8": TypeKind.UINT8,
    "UInt16": TypeKind.UINT16,
    "UInt32": TypeKind.UINT32,
    "UInt64": TypeKind.UINT64,
    "Float32": TypeKind.FLOAT32,
    "Float64": TypeKind.FLOAT64,
    "Utf8": TypeKind.STRING,
    "String": TypeKind.STRING,
    "Boolean": TypeKind.BOOLEAN,
    "Bool": TypeKind.BOOLEAN,
    "Date": TypeKind.DATE,
    "Time": TypeKind.TIME,
    "Duration": TypeKind.DURATION,
    "Decimal": TypeKind.DECIMAL,
    "List": TypeKind.LIST,
    "Struct": TypeKind.STRUCT,
}


def from_polars(dtype: Any) -> DataType:
    """
    Convert Polars dtype to canonical DataType.

    Args:
        dtype: Polars DataType object (e.g., pl.Int64, pl.Utf8)

    Returns:
        Canonical DataType representation

    Example:
        from_polars(pl.Int64)  # DataType(TypeKind.INT64)
        from_polars(pl.Datetime("us", "UTC"))  # DataType(TypeKind.DATETIME, timezone="UTC")
    """
    # Get the dtype class name
    dtype_str = str(dtype)

    # Handle Datetime with timezone
    if dtype_str.startswith("Datetime"):
        # Extract timezone from Datetime(time_unit='us', time_zone='UTC')
        # or Datetime (no params)
        try:
            import polars as pl

            if hasattr(dtype, "time_zone"):
                tz = dtype.time_zone
            elif isinstance(dtype, type) and issubclass(dtype, pl.Datetime):
                tz = None
            else:
                tz = None
            return DataType(TypeKind.DATETIME, timezone=tz)
        except (AttributeError, ImportError):
            return DataType(TypeKind.DATETIME)

    # Handle simple type names
    # Extract base type name (e.g., "Int64" from "Int64")
    base_name = dtype_str.split("(")[0].strip()

    kind = _POLARS_TO_KIND.get(base_name, TypeKind.UNKNOWN)
    return DataType(kind)


def from_polars_string(dtype_str: str) -> DataType:
    """
    Convert Polars dtype string representation to canonical DataType.

    This handles the string output from str(polars_dtype).

    Args:
        dtype_str: String representation of Polars dtype

    Returns:
        Canonical DataType representation

    Example:
        from_polars_string("Int64")  # DataType(TypeKind.INT64)
        from_polars_string("Datetime(time_unit='us', time_zone='UTC')")
    """
    # Handle Datetime with parameters
    if dtype_str.startswith("Datetime"):
        # Parse Datetime(time_unit='us', time_zone='UTC')
        if "time_zone=" in dtype_str:
            # Extract timezone value
            start = dtype_str.find("time_zone='") + len("time_zone='")
            end = dtype_str.find("'", start)
            if start > len("time_zone='") - 1 and end > start:
                tz = dtype_str[start:end]
                if tz != "None":
                    return DataType(TypeKind.DATETIME, timezone=tz)
        return DataType(TypeKind.DATETIME)

    # Handle simple type names
    base_name = dtype_str.split("(")[0].strip()
    kind = _POLARS_TO_KIND.get(base_name, TypeKind.UNKNOWN)
    return DataType(kind)


def to_polars(dtype: DataType) -> Any:
    """
    Convert canonical DataType to Polars dtype.

    Args:
        dtype: Canonical DataType

    Returns:
        Polars DataType object

    Example:
        to_polars(DataType(TypeKind.INT64))  # pl.Int64
    """
    import polars as pl

    kind_to_polars: dict[TypeKind, Any] = {
        TypeKind.INT8: pl.Int8,
        TypeKind.INT16: pl.Int16,
        TypeKind.INT32: pl.Int32,
        TypeKind.INT64: pl.Int64,
        TypeKind.UINT8: pl.UInt8,
        TypeKind.UINT16: pl.UInt16,
        TypeKind.UINT32: pl.UInt32,
        TypeKind.UINT64: pl.UInt64,
        TypeKind.FLOAT32: pl.Float32,
        TypeKind.FLOAT64: pl.Float64,
        TypeKind.STRING: pl.Utf8,
        TypeKind.BOOLEAN: pl.Boolean,
        TypeKind.DATE: pl.Date,
        TypeKind.TIME: pl.Time,
        TypeKind.DURATION: pl.Duration,
    }

    if dtype.kind == TypeKind.DATETIME:
        if dtype.timezone:
            return pl.Datetime("us", dtype.timezone)
        return pl.Datetime("us")

    if dtype.kind == TypeKind.DECIMAL:
        if dtype.precision is not None and dtype.scale is not None:
            return pl.Decimal(dtype.precision, dtype.scale)
        return pl.Decimal

    return kind_to_polars.get(dtype.kind, pl.Utf8)


# =============================================================================
# DuckDB type conversion
# =============================================================================

# Mapping from DuckDB type strings to TypeKind
_DUCKDB_TO_KIND: dict[str, TypeKind] = {
    # Integer types
    "TINYINT": TypeKind.INT8,
    "SMALLINT": TypeKind.INT16,
    "INTEGER": TypeKind.INT32,
    "INT": TypeKind.INT32,
    "BIGINT": TypeKind.INT64,
    "HUGEINT": TypeKind.INT64,  # Map to int64 (closest)
    # Unsigned integer types
    "UTINYINT": TypeKind.UINT8,
    "USMALLINT": TypeKind.UINT16,
    "UINTEGER": TypeKind.UINT32,
    "UINT": TypeKind.UINT32,
    "UBIGINT": TypeKind.UINT64,
    "UHUGEINT": TypeKind.UINT64,  # Map to uint64 (closest)
    # Float types
    "FLOAT": TypeKind.FLOAT32,
    "REAL": TypeKind.FLOAT32,
    "DOUBLE": TypeKind.FLOAT64,
    # String types
    "VARCHAR": TypeKind.STRING,
    "TEXT": TypeKind.STRING,
    "STRING": TypeKind.STRING,
    "CHAR": TypeKind.STRING,
    "BPCHAR": TypeKind.STRING,
    # Boolean
    "BOOLEAN": TypeKind.BOOLEAN,
    "BOOL": TypeKind.BOOLEAN,
    # Temporal types
    "DATE": TypeKind.DATE,
    "TIMESTAMP": TypeKind.DATETIME,
    "TIMESTAMP WITH TIME ZONE": TypeKind.DATETIME,
    "TIMESTAMPTZ": TypeKind.DATETIME,
    "TIME": TypeKind.TIME,
    "INTERVAL": TypeKind.DURATION,
    # Complex types
    "DECIMAL": TypeKind.DECIMAL,
    "NUMERIC": TypeKind.DECIMAL,
    "LIST": TypeKind.LIST,
    "STRUCT": TypeKind.STRUCT,
}


def from_duckdb(dtype_str: str) -> DataType:
    """
    Convert DuckDB type string to canonical DataType.

    Args:
        dtype_str: DuckDB type string (e.g., "BIGINT", "VARCHAR")

    Returns:
        Canonical DataType representation

    Example:
        from_duckdb("BIGINT")  # DataType(TypeKind.INT64)
        from_duckdb("DOUBLE")  # DataType(TypeKind.FLOAT64)
    """
    # Normalize to uppercase
    dtype_upper = dtype_str.upper().strip()

    # Handle parameterized types like DECIMAL(10,2) or VARCHAR(255)
    base_type = dtype_upper.split("(")[0].strip()

    # Handle TIMESTAMP WITH TIME ZONE
    if "TIMESTAMP" in dtype_upper and "TIME ZONE" in dtype_upper:
        # Extract timezone if present (DuckDB doesn't expose it directly)
        return DataType(TypeKind.DATETIME, timezone="UTC")

    # Handle DECIMAL with precision/scale
    if base_type in ("DECIMAL", "NUMERIC") and "(" in dtype_upper:
        params = dtype_upper.split("(")[1].rstrip(")")
        parts = params.split(",")
        precision = int(parts[0].strip())
        scale = int(parts[1].strip()) if len(parts) > 1 else 0
        return DataType(TypeKind.DECIMAL, precision=precision, scale=scale)

    kind = _DUCKDB_TO_KIND.get(base_type, TypeKind.UNKNOWN)
    return DataType(kind)


def to_duckdb(dtype: DataType) -> str:
    """
    Convert canonical DataType to DuckDB type string.

    Args:
        dtype: Canonical DataType

    Returns:
        DuckDB type string

    Example:
        to_duckdb(DataType(TypeKind.INT64))  # "BIGINT"
    """
    kind_to_duckdb: dict[TypeKind, str] = {
        TypeKind.INT8: "TINYINT",
        TypeKind.INT16: "SMALLINT",
        TypeKind.INT32: "INTEGER",
        TypeKind.INT64: "BIGINT",
        TypeKind.UINT8: "UTINYINT",
        TypeKind.UINT16: "USMALLINT",
        TypeKind.UINT32: "UINTEGER",
        TypeKind.UINT64: "UBIGINT",
        TypeKind.FLOAT32: "FLOAT",
        TypeKind.FLOAT64: "DOUBLE",
        TypeKind.STRING: "VARCHAR",
        TypeKind.BOOLEAN: "BOOLEAN",
        TypeKind.DATE: "DATE",
        TypeKind.DATETIME: "TIMESTAMP",
        TypeKind.TIME: "TIME",
        TypeKind.DURATION: "INTERVAL",
    }

    if dtype.kind == TypeKind.DATETIME and dtype.timezone:
        return "TIMESTAMP WITH TIME ZONE"

    if dtype.kind == TypeKind.DECIMAL:
        if dtype.precision is not None and dtype.scale is not None:
            return f"DECIMAL({dtype.precision},{dtype.scale})"
        elif dtype.precision is not None:
            return f"DECIMAL({dtype.precision})"
        return "DECIMAL"

    return kind_to_duckdb.get(dtype.kind, "VARCHAR")


# =============================================================================
# PySpark type conversion
# =============================================================================

# Mapping from PySpark type class names to TypeKind
_PYSPARK_TO_KIND: dict[str, TypeKind] = {
    # Integer types
    "ByteType": TypeKind.INT8,
    "ShortType": TypeKind.INT16,
    "IntegerType": TypeKind.INT32,
    "LongType": TypeKind.INT64,
    # Float types
    "FloatType": TypeKind.FLOAT32,
    "DoubleType": TypeKind.FLOAT64,
    # String types
    "StringType": TypeKind.STRING,
    # Boolean
    "BooleanType": TypeKind.BOOLEAN,
    # Temporal types
    "DateType": TypeKind.DATE,
    "TimestampType": TypeKind.DATETIME,
    "TimestampNTZType": TypeKind.DATETIME,
    # Complex types
    "DecimalType": TypeKind.DECIMAL,
    "ArrayType": TypeKind.LIST,
    "StructType": TypeKind.STRUCT,
    # Duration (Spark calls it DayTimeIntervalType)
    "DayTimeIntervalType": TypeKind.DURATION,
}


def from_pyspark(dtype: Any) -> DataType:
    """
    Convert PySpark DataType to canonical DataType.

    Args:
        dtype: PySpark DataType object (e.g., StringType(), LongType())

    Returns:
        Canonical DataType representation

    Example:
        from pyspark.sql.types import LongType, StringType
        from_pyspark(LongType())  # DataType(TypeKind.INT64)
        from_pyspark(StringType())  # DataType(TypeKind.STRING)
    """
    # Get the dtype class name
    dtype_class_name = type(dtype).__name__

    # Handle TimestampType (may have timezone info in Spark 3.4+)
    if dtype_class_name == "TimestampType":
        return DataType(TypeKind.DATETIME)

    # Handle DecimalType with precision/scale
    if dtype_class_name == "DecimalType":
        precision = getattr(dtype, "precision", None)
        scale = getattr(dtype, "scale", None)
        return DataType(TypeKind.DECIMAL, precision=precision, scale=scale)

    kind = _PYSPARK_TO_KIND.get(dtype_class_name, TypeKind.UNKNOWN)
    return DataType(kind)


def from_pyspark_string(dtype_str: str) -> DataType:
    """
    Convert PySpark type string representation to canonical DataType.

    This handles the string output from str(pyspark_dtype).

    Args:
        dtype_str: String representation of PySpark dtype

    Returns:
        Canonical DataType representation

    Example:
        from_pyspark_string("LongType()")  # DataType(TypeKind.INT64)
        from_pyspark_string("StringType()")  # DataType(TypeKind.STRING)
        from_pyspark_string("DecimalType(10,2)")  # DataType(TypeKind.DECIMAL, precision=10, scale=2)
    """
    # Remove parentheses and parameters for lookup
    base_name = dtype_str.split("(")[0].strip()

    # Handle DecimalType with parameters
    if base_name == "DecimalType" and "(" in dtype_str:
        try:
            params = dtype_str.split("(")[1].rstrip(")")
            parts = params.split(",")
            precision = int(parts[0].strip()) if parts[0].strip() else None
            scale = (
                int(parts[1].strip())
                if len(parts) > 1 and parts[1].strip()
                else None
            )
            return DataType(TypeKind.DECIMAL, precision=precision, scale=scale)
        except (ValueError, IndexError):
            return DataType(TypeKind.DECIMAL)

    # Handle TimestampType
    if base_name == "TimestampType":
        return DataType(TypeKind.DATETIME)

    # Add "Type" suffix if missing for lookup
    if not base_name.endswith("Type"):
        base_name = base_name + "Type"

    kind = _PYSPARK_TO_KIND.get(base_name, TypeKind.UNKNOWN)
    return DataType(kind)


def to_pyspark(dtype: DataType) -> Any:
    """
    Convert canonical DataType to PySpark DataType.

    Args:
        dtype: Canonical DataType

    Returns:
        PySpark DataType object

    Example:
        to_pyspark(DataType(TypeKind.INT64))  # LongType()
        to_pyspark(DataType(TypeKind.STRING))  # StringType()
    """
    from pyspark.sql.types import (
        BooleanType,
        ByteType,
        DateType,
        DecimalType,
        DoubleType,
        FloatType,
        IntegerType,
        LongType,
        ShortType,
        StringType,
        TimestampType,
    )

    kind_to_pyspark: dict[TypeKind, Any] = {
        TypeKind.INT8: ByteType(),
        TypeKind.INT16: ShortType(),
        TypeKind.INT32: IntegerType(),
        TypeKind.INT64: LongType(),
        TypeKind.UINT8: ShortType(),  # No unsigned in Spark, use next larger
        TypeKind.UINT16: IntegerType(),
        TypeKind.UINT32: LongType(),
        TypeKind.UINT64: LongType(),  # May overflow for large values
        TypeKind.FLOAT32: FloatType(),
        TypeKind.FLOAT64: DoubleType(),
        TypeKind.STRING: StringType(),
        TypeKind.BOOLEAN: BooleanType(),
        TypeKind.DATE: DateType(),
        TypeKind.DATETIME: TimestampType(),
        TypeKind.TIME: StringType(),  # Spark has no native Time type
        TypeKind.DURATION: StringType(),  # Use string for duration
    }

    if dtype.kind == TypeKind.DECIMAL:
        precision = dtype.precision or 38
        scale = dtype.scale or 10
        return DecimalType(precision, scale)

    return kind_to_pyspark.get(dtype.kind, StringType())


# =============================================================================
# Aggregation output types
# =============================================================================

# Mapping of aggregation name to output type function
# The function takes input type and returns output type
_AGG_OUTPUT_TYPES: dict[str, DataType | None] = {
    # count always returns int64
    "count": DataType(TypeKind.INT64),
    # mean/avg always returns float64
    "mean": DataType(TypeKind.FLOAT64),
    "avg": DataType(TypeKind.FLOAT64),
    # std/stddev always returns float64
    "std": DataType(TypeKind.FLOAT64),
    "stddev": DataType(TypeKind.FLOAT64),
    "stddev_samp": DataType(TypeKind.FLOAT64),
    # median always returns float64
    "median": DataType(TypeKind.FLOAT64),
    # sum preserves input type (handled specially)
    "sum": None,
    # min/max preserve input type (handled specially)
    "min": None,
    "max": None,
    # first/last preserve input type
    "first": None,
    "last": None,
}


def get_aggregation_output_type(
    agg_name: str,
    input_type: DataType,
) -> DataType:
    """
    Get the output type for an aggregation function.

    Args:
        agg_name: Aggregation function name (e.g., "count", "sum", "mean")
        input_type: Input column data type

    Returns:
        Output data type for the aggregation

    Example:
        get_aggregation_output_type("count", int64())  # int64
        get_aggregation_output_type("mean", int64())   # float64
        get_aggregation_output_type("sum", float64())  # float64
    """
    agg_lower = agg_name.lower()

    # Check for fixed output types
    fixed_output = _AGG_OUTPUT_TYPES.get(agg_lower)
    if fixed_output is not None:
        return fixed_output

    # For sum, min, max, first, last - preserve input type
    # But sum of integers should still be int64 to avoid overflow
    if agg_lower == "sum":
        if input_type.is_integer():
            return DataType(TypeKind.INT64)
        return input_type

    # min, max, first, last preserve exact input type
    if agg_lower in ("min", "max", "first", "last"):
        return input_type

    # Unknown aggregation - return float64 as safe default
    return DataType(TypeKind.FLOAT64)


# =============================================================================
# Schema normalization utilities
# =============================================================================


def normalize_schema(
    schema: dict[str, str],
    source: str = "polars",
) -> dict[str, DataType]:
    """
    Normalize a schema dictionary to canonical types.

    Args:
        schema: Dictionary mapping column names to type strings
        source: Source engine ("polars", "duckdb", or "pyspark")

    Returns:
        Dictionary mapping column names to DataType objects

    Example:
        # From Polars
        normalize_schema({"user_id": "Int64", "name": "Utf8"}, "polars")
        # Returns: {"user_id": DataType(INT64), "name": DataType(STRING)}

        # From DuckDB
        normalize_schema({"user_id": "BIGINT", "name": "VARCHAR"}, "duckdb")
        # Returns: {"user_id": DataType(INT64), "name": DataType(STRING)}

        # From PySpark
        normalize_schema({"user_id": "LongType()", "name": "StringType()"}, "pyspark")
        # Returns: {"user_id": DataType(INT64), "name": DataType(STRING)}
    """
    if source == "polars":
        converter = from_polars_string
    elif source == "duckdb":
        converter = from_duckdb
    elif source == "pyspark":
        converter = from_pyspark_string
    else:
        converter = from_polars_string

    return {name: converter(dtype_str) for name, dtype_str in schema.items()}


def schemas_equivalent(
    schema1: dict[str, str],
    schema2: dict[str, str],
    source1: str = "polars",
    source2: str = "polars",
) -> bool:
    """
    Check if two schemas are equivalent after normalization.

    This allows comparing schemas from different engines that may use
    different type string representations.

    Args:
        schema1: First schema dictionary
        schema2: Second schema dictionary
        source1: Source engine for schema1
        source2: Source engine for schema2

    Returns:
        True if schemas are equivalent after normalization

    Example:
        # Polars and DuckDB schemas that are logically equivalent
        polars_schema = {"id": "Int64", "name": "Utf8"}
        duckdb_schema = {"id": "BIGINT", "name": "VARCHAR"}

        schemas_equivalent(polars_schema, duckdb_schema, "polars", "duckdb")
        # Returns: True
    """
    normalized1 = normalize_schema(schema1, source1)
    normalized2 = normalize_schema(schema2, source2)

    return normalized1 == normalized2
