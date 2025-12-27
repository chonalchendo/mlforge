# Unit Test Generator

Generate unit tests for mlforge source code.

## Process

1. **Read the source file** to understand what you're testing
2. **Read existing tests** in `tests/` to understand patterns and existing fixtures in `tests/conftest.py`
3. **Identify critical behavior** — focus on key functionality, not edge cases or trivial code
4. **Write tests** following the structure and conventions below
5. **Run `just check-test`** to verify tests pass

## Test Structure

Mirror the `src/mlforge/` package structure:
```
src/mlforge/
├── validators.py
├── store.py
└── agg.py

tests/
├── conftest.py          # shared fixtures
├── test_validators.py
├── test_store.py
└── test_agg.py
```

## Test Format

Use **Given-When-Then** comments to clarify test logic:
```python
def test_unique_validator_passes_for_unique_column():
    # Given a dataframe with unique values in 'id' column
    df = pl.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})
    validator = unique("id")

    # When the validator is called
    result = validator(df)

    # Then it should pass without raising
    assert result is None


def test_unique_validator_fails_for_duplicate_column():
    # Given a dataframe with duplicate values in 'id' column
    df = pl.DataFrame({"id": [1, 1, 3], "value": [10, 20, 30]})
    validator = unique("id")

    # When/Then it should raise ValidationError
    with pytest.raises(ValidationError, match="duplicate"):
        validator(df)
```

## Fixtures

Define reusable test objects in `tests/conftest.py`:
```python
import pytest
import polars as pl

@pytest.fixture
def sample_transactions_df() -> pl.DataFrame:
    """Standard transactions dataframe for testing."""
    return pl.DataFrame({
        "user_id": ["a", "b", "c"],
        "amount": [100.0, 200.0, 300.0],
        "timestamp": ["2024-01-01", "2024-01-02", "2024-01-03"],
    })
```

Use fixtures in tests:
```python
def test_feature_with_transactions(sample_transactions_df):
    # Given the sample transactions
    # When ...
    # Then ...
```

## Guidelines

- **Test critical behavior only** — if it's not core functionality, skip it
- **Read docstrings and comments** in source code to understand intended behavior
- **One assertion per test** where practical
- **Descriptive test names** — `test_<function>_<scenario>_<expected_result>`
- **Use `pytest.raises`** for expected exceptions
- **Use `pytest.mark.parametrize`** for testing multiple inputs with same logic
