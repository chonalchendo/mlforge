# Tests

Generate or update unit tests.

## Usage

```
/tests                   # Auto-detect what needs tests
/tests generate <file>   # Generate tests for source file
/tests update            # Update tests for code changes
/tests coverage          # Find and fill coverage gaps
/tests feature <name>    # Generate tests for a feature
```

---

## Mode: auto (default)

When no argument provided, auto-detect what needs tests:

1. Check `git diff` for changed source files
2. Identify files without corresponding tests
3. Suggest test generation or updates

---

## Mode: generate

Generate tests for a specific source file.

### Usage

```
/tests generate core           # tests/test_core.py
/tests generate store          # tests/test_store.py
/tests generate validators     # tests/test_validators.py
```

### Workflow

1. **Read source file** to understand what to test
2. **Read existing tests** in `tests/` for patterns
3. **Read `tests/conftest.py`** for available fixtures
4. **Identify critical behavior** to test
5. **Write tests** following project conventions
6. **Run tests**: `just check-test`

### Test Structure

Mirror `src/mlforge/` structure:
```
src/mlforge/validators.py  ->  tests/test_validators.py
src/mlforge/store.py       ->  tests/test_store.py
```

### Test Format

Use **Given-When-Then** comments:

```python
def test_feature_decorator_registers_feature():
    # Given a feature function with decorator
    @feature(keys=["user_id"], source="data.parquet")
    def my_feature(df):
        return df

    # When the feature is accessed
    result = my_feature

    # Then it should have feature metadata
    assert hasattr(result, "keys")
    assert result.keys == ["user_id"]
```

### Naming Convention

`test_<function>_<scenario>_<expected_result>`

Examples:
- `test_validator_passes_for_valid_data`
- `test_store_read_raises_when_not_found`
- `test_feature_build_creates_parquet_file`

---

## Mode: update

Update existing tests to reflect code changes.

### Workflow

1. **Identify changed source files**:
   ```bash
   git diff --name-only $(git merge-base HEAD main) -- src/
   ```

2. **Map to test files**:
   - `src/mlforge/core.py` -> `tests/test_core.py`

3. **Analyze changes**:
   - New functions -> Add new tests
   - Changed signatures -> Update test calls
   - Changed behavior -> Update assertions
   - Deleted code -> Remove tests

4. **Update tests** to match new code

5. **Verify**: `just check-test`

### Change Type Reference

| Code Change | Test Action |
|-------------|-------------|
| New function/class | Add new tests |
| Changed signature | Update test calls |
| Changed behavior | Update assertions |
| Renamed parameter | Update all usages |
| Deleted code | Remove tests |
| Bug fix | Add regression test |

---

## Mode: coverage

Find coverage gaps and generate tests to fill them.

### Workflow

1. **Run coverage report**:
   ```bash
   uv run pytest tests/ --cov=src/mlforge --cov-report=term-missing
   ```

2. **Identify gaps**:
   - Uncovered lines
   - Uncovered branches
   - Missing edge cases

3. **Prioritize by impact**:
   - Core functionality first
   - Error handling paths
   - Edge cases

4. **Generate tests** for highest-impact gaps

5. **Re-run coverage** to verify improvement

### Coverage Target

Project requires **80% minimum** coverage.

```bash
# Check current coverage
just check-coverage

# Detailed report
uv run pytest tests/ --cov=src/mlforge --cov-report=html
# Open htmlcov/index.html
```

---

## Mode: feature

Generate comprehensive tests for a specific feature/module.

### Usage

```
/tests feature versioning    # Test versioning functionality
/tests feature duckdb        # Test DuckDB engine
/tests feature validation    # Test validators
```

### Workflow

1. **Identify all code related to feature**
2. **Read existing tests** for that feature
3. **Generate comprehensive test suite**:
   - Happy path tests
   - Edge cases
   - Error handling
   - Integration tests

---

## Guidelines

- **Test critical behavior** - Not every line needs a test
- **One assertion per test** where practical
- **Use fixtures** for reusable test data
- **Descriptive names** - Test name should explain what's being tested
- **Given-When-Then** - Structure tests clearly

### Fixtures

Define in `tests/conftest.py`:

```python
import pytest
import polars as pl
from mlforge import LocalStore

@pytest.fixture
def sample_df() -> pl.DataFrame:
    """Standard test DataFrame."""
    return pl.DataFrame({
        "user_id": ["a", "b", "c"],
        "amount": [100.0, 200.0, 300.0],
    })

@pytest.fixture
def temp_store(tmp_path) -> LocalStore:
    """Temporary LocalStore for testing."""
    return LocalStore(tmp_path / "feature_store")
```

Use fixtures in tests:
```python
def test_store_write(temp_store, sample_df):
    # Given a store and sample data
    # When ...
    # Then ...
```

### Parametrization

Use for testing multiple inputs:

```python
@pytest.mark.parametrize("input,expected", [
    ("7d", timedelta(days=7)),
    ("24h", timedelta(hours=24)),
    ("30m", timedelta(minutes=30)),
])
def test_parse_duration(input, expected):
    assert parse_duration(input) == expected
```

### Testing Exceptions

```python
def test_store_read_raises_for_missing_feature():
    # Given a store without the feature
    store = LocalStore("./test_store")

    # When/Then reading should raise FileNotFoundError
    with pytest.raises(FileNotFoundError, match="not found"):
        store.read("nonexistent_feature")
```

### Testing Warnings

```python
def test_deprecated_function_warns():
    with pytest.warns(DeprecationWarning, match="deprecated"):
        old_function()
```

---

## Test Commands Reference

```bash
# Run all tests
just check-test

# Run with coverage
just check-coverage

# Run specific file
uv run pytest tests/test_core.py -v

# Run specific test
uv run pytest tests/test_core.py::test_feature_decorator -v

# Run tests matching pattern
uv run pytest tests/ -k "versioning" -v

# Run with verbose output
uv run pytest tests/ -v --tb=long

# Run full check suite
just check
```

---

## Common Pitfalls

- **Don't forget** to grep for old names across ALL test files when renaming
- **Check parametrized tests** for outdated values
- **Update conftest.py fixtures** if API changed
- **Run `just check-test`** to verify everything passes before committing
