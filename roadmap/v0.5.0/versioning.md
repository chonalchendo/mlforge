# Feature: Versioning

**Version:** v0.5.0
**Status:** Done
**Effort:** Medium
**Breaking Changes:** Yes

## Summary

Automated semantic versioning based on schema and configuration changes. Features are stored in version directories (e.g., `user_spend/1.0.0/`) with content hashes for integrity verification and automatic version bumps based on detected changes.

## Motivation

- Enable model reproducibility by pinning feature versions
- Support A/B testing with different feature versions
- Allow rollback to previous feature versions
- Track feature evolution over time
- Automatic version bumps based on detected changes

## Design Principles

- **Version-based directories** for human readability (e.g., `user_spend/1.0.0/`)
- **Content hashes stored in metadata** for integrity verification and change detection
- **Automatic version detection** based on schema/config hash comparison
- **Explicit version override** when users need control

## API Design

### Python API

```python
# Build with auto-versioning (default)
result = defs.build(features=["user_spend"])
# -> Creates 1.0.0 (first), 1.1.0 (schema change), or 1.0.1 (data refresh)

# Build with explicit version override
defs.build(features=["user_spend"], version="2.0.0")

# Read specific version
store.read("user_spend", version="1.0.0")

# Read latest (default)
store.read("user_spend")

# List versions
store.list_versions("user_spend")  # -> ["1.0.0", "1.0.1", "1.1.0"]

# Get training data with specific versions
get_training_data(
    spine=spine_df,
    features=[
        "user_spend",                    # latest
        ("merchant_features", "1.0.0"),  # specific version
    ],
    store=store,
)
```

### CLI

```bash
# Build with auto-versioning (default)
mlforge build --features user_spend

# Build with explicit version
mlforge build --features user_spend --version 2.0.0

# List versions
mlforge versions user_spend

# Inspect specific version
mlforge inspect user_spend --version 1.0.0
```

## Implementation Details

### Auto-Versioning Logic

| Change Type | Detection Method | Version Bump |
|-------------|------------------|--------------|
| First build | No previous version exists | `1.0.0` |
| Schema breaking (columns removed) | Compare output schema | MAJOR |
| Schema breaking (dtype changed) | Compare output schema | MAJOR |
| Metrics removed | Compare config hash | MAJOR |
| Schema additive (columns added) | Compare output schema | MINOR |
| Metrics added (new windows/aggs) | Compare config hash | MINOR |
| Config change (interval, keys) | Compare config hash | MINOR |
| Data refresh (same schema/config) | Hashes match | PATCH |

### Storage Layout

```
feature_store/
├── user_spend/
│   ├── 1.0.0/
│   │   ├── data.parquet
│   │   └── .meta.json
│   ├── 1.1.0/
│   │   ├── data.parquet
│   │   └── .meta.json
│   └── _latest.json          # {"version": "1.1.0"}
└── _metadata/
    └── manifest.json
```

### Metadata Schema (.meta.json)

```json
{
  "name": "user_spend",
  "version": "1.1.0",
  "content_hash": "abc123def456",
  "schema_hash": "def789xyz012",
  "config_hash": "123abc456def",
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z",
  "row_count": 150000,
  "entity_keys": ["user_id"],
  "timestamp": "event_time",
  "interval": "1d",
  "columns": [...],
  "change_summary": {
    "bump_type": "minor",
    "reason": "added_columns",
    "details": ["amount__sum__30d", "amount__mean__30d"]
  }
}
```

### Key Files

| File | Changes |
|------|---------|
| `src/mlforge/store.py` | Version directories, list_versions(), read with version |
| `src/mlforge/version.py` | Version detection, hash computation, bump logic |
| `src/mlforge/manifest.py` | New metadata fields, change_summary |
| `src/mlforge/core.py` | Build with version support |
| `src/mlforge/retrieval.py` | get_training_data with version tuples |
| `src/mlforge/cli.py` | --version flag, versions command |

### Implementation Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Store layer - version directories | Done |
| 2 | Metadata & Hashing | Done |
| 3 | Auto-detection logic | Done |
| 4 | Core & CLI integration | Done |
| 5 | Retrieval with versions | Done |

## Definition of Done

### Code
- [x] Implementation complete
- [x] Type hints on all public functions
- [x] Docstrings following Google style
- [x] No ruff/ty errors

### Tests
- [x] Unit tests written (`tests/test_versioning.py`)
- [x] Integration tests
- [x] All tests passing
- [x] Coverage >= 80%

### Documentation
- [x] API docs updated
- [x] User guide updated
- [x] CLI docs updated
- [x] CHANGELOG entry added

### Verification
- [x] Works in `examples/transactions`
- [x] Code review completed
- [x] No regressions in existing functionality

## Dependencies

- **Depends on:** None (foundational feature)
- **Blocked by:** None

## Testing Strategy

### Unit Tests

- `test_auto_version_major_bump` - Column removal triggers MAJOR
- `test_auto_version_minor_bump` - Column addition triggers MINOR
- `test_auto_version_patch_bump` - Data refresh triggers PATCH
- `test_explicit_version_override` - Manual version works
- `test_list_versions` - Returns sorted versions
- `test_read_specific_version` - Can read old versions

### Example Verification

```bash
cd examples/transactions
uv run mlforge build --features user_spend_30d_interval
uv run mlforge inspect user_spend_30d_interval
# Verify version field in output
```

## Migration Guide

### Before (v0.4.0)

```
feature_store/
└── user_spend.parquet
```

### After (v0.5.0)

```
feature_store/
└── user_spend/
    └── 1.0.0/
        ├── data.parquet
        └── .meta.json
```

### Migration Steps

```bash
# Rebuild features with versions
mlforge build --features user_spend --version 1.0.0

# Regenerate manifest
mlforge manifest --regenerate
```

## Design Decisions

### Why Version-Based Directories (not Hash-Based)?

| Aspect | Hash-Based | Version-Based (Chosen) |
|--------|------------|------------------------|
| Readability | `abc123def456` is meaningless | `1.1.0` is clear |
| Sorting | Random order in file browser | Natural version ordering |
| Debugging | Need to look up hash -> version | Immediately obvious |
| CLI output | `Built: abc123def456` | `Built: 1.1.0` |

Content hashes are still stored in metadata for integrity verification.

### Why Auto-Versioning by Default?

- Reduces cognitive load on users
- Ensures versions have semantic meaning
- Explicit override available when needed

## Future Considerations

- Feature function code hashing (detect logic changes) - v0.5.x
