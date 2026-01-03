# Feature: DuckDB Compute Backend

**Version:** v0.5.0
**Status:** Done
**Effort:** Medium-High
**Breaking Changes:** No

## Summary

Drop-in replacement for Polars engine, optimized for large datasets. DuckDB uses native SQL window functions for efficient rolling aggregations and can spill to disk for datasets larger than memory.

## Motivation

- Superior performance on large datasets without requiring Spark
- SQL-based window functions for efficient rolling aggregations
- Ability to spill to disk for datasets larger than memory
- Local data warehouse capabilities

## Design Principles

- **Same Python API** - Features work with both engines without code changes
- **User functions receive Polars DataFrames** - DuckDB converts internally
- **DuckDB handles expensive parts** - Source loading and metrics computation
- **Native window functions** - Uses DuckDB's optimized RANGE BETWEEN

## API Design

### Python API

```python
from mlforge import Definitions
from mlforge.store import LocalStore

store = LocalStore(path="./feature_store")

# Default (Polars)
defs = Definitions(store=store)

# DuckDB engine
defs = Definitions(store=store, engine="duckdb")

# Per-build override
defs.build(features=["user_spend"], engine="duckdb")
```

### Feature Definition (unchanged)

```python
import polars as pl
from mlforge import feature
from mlforge.metrics import Rolling

@feature(
    keys=["user_id"],
    source="transactions.parquet",
    timestamp="event_time",
    metrics=[
        Rolling(
            windows=["7d", "30d"],
            aggregations={"amount": ["sum", "mean"]},
        ),
    ],
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    # Same code works with both engines
    return df.select(
        pl.col("user_id"),
        pl.col("event_time"),
        pl.col("amount"),
    )
```

## Implementation Details

### Rolling Metrics Compilation

DuckDB uses native SQL window functions with `RANGE BETWEEN`:

```sql
SELECT
    user_id,
    event_time,
    SUM(amount) OVER w_7d AS "user_spend__amount__sum__1d__7d",
    AVG(amount) OVER w_7d AS "user_spend__amount__mean__1d__7d"
FROM feature_data
WINDOW
    w_7d AS (PARTITION BY user_id ORDER BY event_time
             RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW)
```

### Aggregation Mapping

| mlforge | DuckDB SQL |
|---------|------------|
| `count` | `COUNT` |
| `sum` | `SUM` |
| `mean` | `AVG` |
| `min` | `MIN` |
| `max` | `MAX` |
| `std` | `STDDEV_SAMP` |
| `median` | `MEDIAN` |

### Key Files

| File | Changes |
|------|---------|
| `src/mlforge/engines/__init__.py` | Package exports, get_duckdb_connection() |
| `src/mlforge/engines/base.py` | Engine ABC |
| `src/mlforge/engines/duckdb.py` | DuckDBEngine implementation |
| `src/mlforge/compilers/__init__.py` | Package exports |
| `src/mlforge/compilers/duckdb.py` | DuckDBCompiler, SQL generation |
| `src/mlforge/results.py` | DuckDBResult class |

### Architecture

```
src/mlforge/
├── engines/
│   ├── __init__.py          # Re-exports, get_duckdb_connection()
│   ├── base.py              # Engine ABC
│   ├── polars.py            # PolarsEngine
│   └── duckdb.py            # DuckDBEngine
├── compilers/
│   ├── __init__.py          # Re-exports
│   ├── base.py              # ComputeContext
│   ├── polars.py            # PolarsCompiler
│   └── duckdb.py            # DuckDBCompiler
└── results.py               # PolarsResult, DuckDBResult
```

### Implementation Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 6 | Refactor engines/compilers to packages | Done |
| 7 | DuckDB Engine | Done |
| 8 | DuckDB Compiler | Done |
| 9 | DuckDB Result | Done |

## Definition of Done

### Code
- [x] Implementation complete
- [x] Type hints on all public functions
- [x] Docstrings following Google style
- [x] No ruff/ty errors

### Tests
- [x] Unit tests written (`tests/test_duckdb.py`)
- [x] Parity tests (`tests/test_engine_parity.py`)
- [x] All tests passing
- [x] Coverage >= 80%

### Documentation
- [x] API docs updated
- [x] User guide updated
- [ ] CLI docs updated (engine flag)
- [x] CHANGELOG entry added

### Verification
- [x] Works in `examples/transactions`
- [x] Code review completed
- [x] No regressions in existing functionality

## Dependencies

- **Depends on:** Package restructure (Phase 6)
- **Blocked by:** None
- **Optional dependency:** `duckdb>=1.0.0`

## Testing Strategy

### Unit Tests

- `test_duckdb_engine_execute` - Basic execution
- `test_duckdb_rolling_metrics` - Window functions work
- `test_duckdb_aggregations` - All aggregation types

### Parity Tests

```python
def test_rolling_metrics_parity():
    """Ensure Polars and DuckDB produce equivalent results."""
    # Create test data with known values
    # Run same feature with both engines
    # Compare results within tolerance (1e-6 for floats)
```

### Example Verification

```bash
cd examples/transactions
# Edit definitions.py to use engine="duckdb"
uv run mlforge build
```

## Installation

```bash
pip install mlforge[duckdb]
```

## Note on Polars vs DuckDB Parity

Polars uses `group_by_dynamic()` which operates on discrete time intervals, while DuckDB's `RANGE BETWEEN` is a continuous sliding window. Results may differ slightly depending on data distribution. Parity tests validate differences are within acceptable tolerance.

## Future Considerations

- Spark compute backend - v0.6.0
