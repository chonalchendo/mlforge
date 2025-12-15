# Update Unit Tests

Update existing tests to reflect code changes committed on the current branch.

## Workflow

### Step 1: Identify What Changed

Determine the scope of test updates needed:

1. **Get the base branch:**
   ```bash
   git merge-base HEAD main
   ```
   (Try `main`, then `master` if that fails)

2. **List changed source files:**
   ```bash
   git diff --name-only $(git merge-base HEAD main) -- src/
   ```

3. **Get the detailed diff:**
   ```bash
   git diff $(git merge-base HEAD main) -- src/
   ```

### Step 2: Analyse Code Changes

For each changed Python file, determine the test impact:

1. **Identify what changed:**
   - New public functions/classes → Need new tests
   - Modified signatures → Update existing tests
   - Changed behaviour → Update assertions
   - Renamed/moved modules → Update imports in tests
   - Deleted code → Remove corresponding tests

2. **Check for breaking changes:**
   - Changed function signatures
   - Renamed parameters
   - Changed return types
   - Modified exception types

### Step 3: Map Changes to Tests

Create a change map linking code changes to test files:

| Code Change | Test Files Affected |
|-------------|---------------------|
| New function in `module.py` | `tests/test_module.py` |
| Changed signature | Tests calling that function |
| New class | New test file or existing test file |
| Renamed parameter | All tests using that parameter |

### Step 4: Read Existing Test Patterns

Before writing or updating tests:

1. **Read `tests/conftest.py`** for existing fixtures
2. **Read related test files** to understand patterns
3. **Check for parametrized tests** that may need updating

### Step 5: Update Tests

Apply updates based on your change map:

#### For New Public API

Create tests following the existing patterns:

```python
def test_<function>_<scenario>_<expected_result>():
    # Given <setup description>
    ...

    # When <action description>
    ...

    # Then <expected outcome>
    assert ...
```

#### For Modified Signatures

1. **Find affected tests:**
   ```bash
   grep -r "old_param" tests/
   ```

2. Update all test calls to use new signatures

3. Update fixtures if they use the changed API

#### For Changed Behaviour

1. Update assertions to match new behaviour
2. Add tests for new behaviour paths
3. Remove tests for removed behaviour

#### For Deleted API

1. Remove tests for deleted functions/classes
2. Remove fixtures that are no longer used
3. Update any tests that depended on deleted code

#### For New Fixtures

If new test data patterns emerge, add to `tests/conftest.py`:

```python
@pytest.fixture
def new_fixture() -> SomeType:
    """Description of what this fixture provides."""
    return ...
```

### Step 6: Verify Updates

1. **Run the tests:**
   ```bash
   just check-test
   ```

2. **Check for broken imports:**
   ```bash
   grep -r "from mlforge.old_module" tests/
   ```

3. **Search for outdated references:**
   ```bash
   # Find references to old function/class names from the diff
   grep -r "old_name" tests/
   ```

### Step 7: Summarise Changes

Provide a summary of test updates:

```markdown
## Test Updates

### Files Modified
- `tests/test_module.py` - Updated tests for new `feature` signature

### Files Added
- `tests/test_new_module.py` - Tests for new module

### Files Removed
- None

### Fixtures Added/Modified
- Added `new_fixture` to conftest.py
```

## Change Type Reference

### Adding a New Feature

1. Create tests for the new function/class
2. Add fixtures if reusable test data is needed
3. Follow Given-When-Then format
4. Test critical behaviour, not edge cases

### Modifying Existing Feature

1. Update test calls to match new signature
2. Update assertions if behaviour changed
3. Update fixtures if they use the changed API

### Deprecating a Feature

1. Keep existing tests (deprecated code should still work)
2. Add tests for the replacement API

### Removing a Feature

1. Remove tests for deleted functions/classes
2. Remove unused fixtures
3. Update any tests that imported from deleted modules

### Fixing a Bug

1. Add a test that would have caught the bug
2. Verify the test passes with the fix

## Guidelines

- **Minimal changes** - Only update what's affected by the code changes
- **Preserve patterns** - Match existing test style and conventions
- **One assertion per test** where practical
- **Descriptive names** - `test_<function>_<scenario>_<expected_result>`

### Common Pitfalls

!!! danger "Don't forget"
    - Grep for old names across ALL test files
    - Check parametrized tests for outdated values
    - Update conftest.py fixtures if API changed
    - Run `just check-test` to verify everything passes

## Output

- Updated `tests/` files reflecting code changes
- Updated `tests/conftest.py` if fixtures changed
- Summary of changes made
- Test run results
