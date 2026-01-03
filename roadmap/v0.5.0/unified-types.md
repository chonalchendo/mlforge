# Feature: Unified Type System

**Version:** v0.5.0
**Status:** Done
**Effort:** Medium
**Breaking Changes:** No

## Summary

A canonical type system that normalizes engine-specific types (Polars, DuckDB, future Spark) into a consistent representation for metadata, schema hashing, and type comparisons.

## Motivation

- Polars uses `Int64`, `Float64`, `Utf8` while DuckDB uses `BIGINT`, `DOUBLE`, `VARCHAR`
- Same logical schema produces different metadata depending on which engine built it
- Schema hashing is inconsistent across engines (affects versioning)
- Type comparisons in point-in-time joins fail on minor type differences
- Future engines (Spark) will introduce more type variations

## Design Principles

- **Canonical types** - Engine-agnostic type representation inspired by Apache Arrow
- **Bidirectional mapping** - Convert to/from Polars, DuckDB, and future engines
- **Immutable & hashable** - Type objects can be used as dict keys and in sets
- **JSON serializable** - Human-readable format for metadata storage
- **Backward compatible** - Existing metadata remains valid

## API Design

### Core Types

```python
from mlforge.types import DataType, TypeKind

# Create types
int_type = DataType(TypeKind.INT64)
datetime_type = DataType(TypeKind.DATETIME, timezone="UTC")

# Convenience constructors
from mlforge.types import int64, float64, string, datetime

int_type = int64()
dt_type = datetime(timezone="UTC")

# Serialize to JSON
int_type.to_canonical_string()  # "int64"

# From engine types
from mlforge.types import from_polars, from_duckdb

canonical = from_polars(pl.Float64)  # DataType(TypeKind.FLOAT64)
canonical = from_duckdb("DOUBLE")    # DataType(TypeKind.FLOAT64)
```

## Implementation Details

### Type Mapping Tables

| mlforge Canonical | Polars | DuckDB | Arrow |
|-------------------|--------|--------|-------|
| `int8` | `Int8` | `TINYINT` | `int8` |
| `int16` | `Int16` | `SMALLINT` | `int16` |
| `int32` | `Int32` | `INTEGER` | `int32` |
| `int64` | `Int64` | `BIGINT` | `int64` |
| `uint8` | `UInt8` | `UTINYINT` | `uint8` |
| `uint16` | `UInt16` | `USMALLINT` | `uint16` |
| `uint32` | `UInt32` | `UINTEGER` | `uint32` |
| `uint64` | `UInt64` | `UBIGINT` | `uint64` |
| `float32` | `Float32` | `FLOAT` | `float32` |
| `float64` | `Float64` | `DOUBLE` | `float64` |
| `string` | `Utf8` | `VARCHAR` | `string` |
| `boolean` | `Boolean` | `BOOLEAN` | `bool` |
| `date` | `Date` | `DATE` | `date32` |
| `datetime` | `Datetime` | `TIMESTAMP` | `timestamp` |

### Aggregation Output Types

| Aggregation | Input Type | Output Type |
|-------------|-----------|-------------|
| `count` | Any | `int64` |
| `sum` | Integer | Same as input |
| `sum` | Float | `float64` |
| `mean` | Numeric | `float64` |
| `min` | Any | Same as input |
| `max` | Any | Same as input |
| `std` | Numeric | `float64` |
| `median` | Numeric | `float64` |

### Key Files

| File | Changes |
|------|---------|
| `src/mlforge/types.py` | New file - TypeKind, DataType, conversions |
| `src/mlforge/results.py` | schema_canonical(), base_schema_canonical() |
| `src/mlforge/core.py` | Schema hashing uses canonical types |
| `src/mlforge/manifest.py` | Type normalization for metadata |
| `src/mlforge/retrieval.py` | Canonical type comparison in asof joins |

### Integration Points

| Location | Before | After |
|----------|--------|-------|
| `results.py:schema()` | `str(dtype)` | Raw type (unchanged) |
| `results.py:schema_canonical()` | N/A | `from_polars(dtype)` |
| `manifest.py` | Store raw dtype | Store canonical dtype |
| `core.py` hash computation | Hash raw types | Hash canonical types |
| `retrieval.py` comparison | Direct comparison | Compare canonical |

### Implementation Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 9.1 | Core types module | Done |
| 9.2 | Engine integration | Done |
| 9.3 | Metadata & hashing | Done |
| 9.4 | Tests | Done |

## Definition of Done

### Code
- [x] Implementation complete
- [x] Type hints on all public functions
- [x] Docstrings following Google style
- [x] No ruff/ty errors

### Tests
- [x] Unit tests written (`tests/test_types.py` - 69 tests)
- [x] All Polars -> canonical conversions tested
- [x] All DuckDB -> canonical conversions tested
- [x] JSON serialization roundtrip tested
- [x] Schema hashing consistency tested
- [x] All tests passing
- [x] Coverage >= 80% (95% for types.py)

### Documentation
- [x] API docs updated
- [x] User guide updated
- [x] CHANGELOG entry added

### Verification
- [x] Works in `examples/transactions`
- [x] Code review completed
- [x] No regressions in existing functionality

## Dependencies

- **Depends on:** DuckDB Engine (for testing parity)
- **Blocked by:** None

## Testing Strategy

### Unit Tests

```python
def test_polars_to_canonical():
    """Test Polars dtype to canonical type conversion."""
    assert from_polars(pl.Int64) == DataType(TypeKind.INT64)
    assert from_polars(pl.Float64) == DataType(TypeKind.FLOAT64)
    assert from_polars(pl.Utf8) == DataType(TypeKind.STRING)

def test_duckdb_to_canonical():
    """Test DuckDB type string to canonical type conversion."""
    assert from_duckdb("BIGINT") == DataType(TypeKind.INT64)
    assert from_duckdb("DOUBLE") == DataType(TypeKind.FLOAT64)
    assert from_duckdb("VARCHAR") == DataType(TypeKind.STRING)

def test_schema_hash_consistency():
    """Same logical schema produces same hash regardless of engine."""
    polars_schema = {"user_id": pl.Utf8, "amount": pl.Float64}
    duckdb_schema = {"user_id": "VARCHAR", "amount": "DOUBLE"}

    polars_canonical = {k: from_polars(v) for k, v in polars_schema.items()}
    duckdb_canonical = {k: from_duckdb(v) for k, v in duckdb_schema.items()}

    assert polars_canonical == duckdb_canonical

def test_type_json_roundtrip():
    """Types serialize and deserialize correctly."""
    original = DataType(TypeKind.DATETIME, timezone="UTC")
    serialized = original.to_json()
    deserialized = DataType.from_json(serialized)
    assert original == deserialized
```

### Example Verification

```bash
cd examples/transactions
# Build with Polars
uv run mlforge build --features user_spend_30d_interval
# Check metadata uses canonical types
cat feature_store/user_spend_30d_interval/*/. meta.json
```

## Research Basis

| Project | Approach | Key Insight |
|---------|----------|-------------|
| Apache Arrow | Class-based, language-agnostic | Industry standard for cross-engine interop |
| Ibis | Class-based with conversion methods | 20+ backends with unified types |
| Feast | Enum-based (ValueType) | Simple but limited expressiveness |

**Chosen approach:** Hybrid class-based system inspired by Ibis, using Arrow-compatible type names.

## Future Considerations

- Spark type mappings - v0.6.0
- Complex types (List, Struct) - Future
