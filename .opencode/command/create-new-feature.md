---
description: Implement a feature from roadmap with guided checkpoints
---

/create-new-feature $ARGUMENTS

Implement a feature defined in the roadmap with guided checkpoints for planning, implementation, testing, verification, and review.

## Usage

```
/create-new-feature <version> <feature-name>
/create-new-feature <version> <feature-name> --quick
```

### Arguments

- `version`: Target version (e.g., v0.5.0, v0.6.0)
- `feature-name`: Feature name matching roadmap file (e.g., redis-online, versioning)

### Options

- `--quick`: Combine Testing + Verification + Review into single checkpoint

## Examples

```
/create-new-feature v0.5.0 redis-online
/create-new-feature v0.6.0 spark-engine --quick
```

---

## Workflow Overview

```
CHECKPOINT 1: Planning
    ↓ User approves
CHECKPOINT 2: Implementation
    ↓ User approves
CHECKPOINT 3: Testing
    ↓ User approves
CHECKPOINT 4: Verification
    ↓ User approves
CHECKPOINT 5: Review
    ↓ User approves
Ready for /commit-push-pr
```

With `--quick` flag, checkpoints 3-5 are combined into a single checkpoint.

---

## Phase 1: Planning

### Step 1.1: Locate Feature Spec

Look for the feature spec file:
```
roadmap/{version}/{feature-name}.md
```

Example: `roadmap/v0.5.0/redis-online.md`

**If file doesn't exist:**
1. Inform user the spec doesn't exist
2. Offer to create one using the template
3. If user agrees, use `/research` command to gather information and draft the spec
4. Save to `roadmap/{version}/{feature-name}.md`
5. Ask user to review and approve the spec before continuing

### Step 1.2: Read Feature Spec

Extract from the spec:
- Summary and motivation
- API design (Python and CLI)
- Implementation details
- Key files to modify/create
- Definition of Done checklist
- Testing strategy
- Dependencies

### Step 1.3: Explore Codebase

Use `@codebase-explorer` to understand:
- Current code structure related to the feature
- Existing patterns to follow
- Files that will need modification
- Similar implementations to reference

### Step 1.4: Generate Implementation Plan

Create a detailed plan including:
- Files to create (with purpose)
- Files to modify (with specific changes)
- Order of implementation
- Potential challenges
- Estimated phases/steps

### Step 1.5: Present Plan

Show the user:
```
## Implementation Plan for {feature-name}

### Files to Create
- `src/mlforge/new_file.py` - Description

### Files to Modify
- `src/mlforge/existing.py:123-145` - Description of changes

### Implementation Steps
1. Step 1 description
2. Step 2 description
...

### Potential Challenges
- Challenge 1
- Challenge 2

### Estimated Effort
- Code: X hours
- Tests: X hours
```

**CHECKPOINT 1**: Ask user to approve the plan or request changes.

---

## Phase 2: Implementation

### Step 2.1: Create New Files

For each new file in the plan:
1. Create the file with proper structure
2. Add imports, classes, functions as designed
3. Include type hints and docstrings
4. Follow project conventions (see AGENTS.md)

### Step 2.2: Modify Existing Files

For each modification:
1. Read the current file
2. Make the planned changes
3. Ensure imports are updated
4. Maintain backward compatibility where needed

### Step 2.3: Run Linting

```bash
just check-code
just check-type
just check-format
```

Fix any issues before proceeding.

Fix code formatting errors using the following command:

```bash
just format
```

### Step 2.4: Simplify Code

Review the code you just wrote and simplify it. AI-generated code often contains unnecessary verbosity, over-abstraction, and redundant patterns.

**Core Question:** Does every line directly contribute to completing the feature spec?

#### Design Principles Check

| Principle | Check |
|-----------|-------|
| **Deep Modules** | Don't create shallow functions that wrap one line of code |
| **Simple Interface** | Hide complexity inside modules, don't push it to callers |
| **Pull Complexity Down** | The module should handle complexity, not its callers |
| **Design for Reading** | Would a new reader understand this in one pass? |

#### Red Flags Check

| Red Flag | Action |
|----------|--------|
| **Shallow Module** | Function does almost nothing? Inline it |
| **Pass-Through Method** | Just forwards to another method? Remove it |
| **Repetition** | Same pattern twice? Consolidate into helper |
| **Comment Repeats Code** | Comment restates the obvious? Delete it |
| **Hard to Describe** | Can't explain simply? It's doing too much |

#### Avoid Over-Engineering

- [ ] **YAGNI**: Delete code for features not in the spec
- [ ] **Over-generic**: Is the code solving more than required?
- [ ] **Unused abstractions**: Classes that could be functions? Inline them
- [ ] **Defensive overkill**: Handling edge cases that can't occur?

#### Avoid Over-Splitting

- [ ] **Single-use functions**: Is this function used more than once? If not, consider inlining
- [ ] **Fragmented flow**: Can a reader follow the logic without jumping between many files?
- [ ] **Premature abstraction**: Are you creating helpers "in case" they're needed later?

**Rule of thumb:** A function should exist if it (a) is called from multiple places, OR (b) encapsulates a distinct concept that aids understanding.

#### Simplification Examples

**Over-split (bad):**
```python
def _validate_not_empty(value: str) -> bool:
    return len(value) > 0

def _validate_max_length(value: str, max_len: int) -> bool:
    return len(value) <= max_len

def validate_name(name: str) -> bool:
    if not _validate_not_empty(name):
        return False
    if not _validate_max_length(name, 100):
        return False
    return True
```

**Simple (good):**
```python
def validate_name(name: str) -> bool:
    """Name must be 1-100 characters."""
    return 0 < len(name) <= 100
```

**Unnecessary abstraction (bad):**
```python
class ResultBuilder:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)

    def build(self) -> list:
        return self.items

builder = ResultBuilder()
for x in data:
    builder.add(process(x))
result = builder.build()
```

**Simple (good):**
```python
result = [process(x) for x in data]
```

#### Required Output

After simplifying, document what changed:

```
## Simplifications Made

### Removed
- Deleted `_validate_helper()` - only called once, inlined into `validate()`
- Removed `ResultBuilder` class - replaced with list comprehension
- Deleted 3 comments that restated the code

### Consolidated
- Merged `_load_config()` and `_parse_config()` into single `load_config()`

### Inlined
- `_check_exists()` was single-use, inlined into `process_file()`

### Kept As-Is (with justification)
- `EntityKeyTransform` class - used in 3 places, encapsulates distinct concept

**Lines reduced:** X -> Y (Z% reduction)
```

If no simplifications needed, state: "Reviewed for simplification - no changes needed."

### Step 2.5: Show Changes Summary

```bash
git diff --stat
```

Present a summary of all changes made.

**CHECKPOINT 2**: Ask user to approve the implementation or request changes.

---

## Phase 3: Testing

### Step 3.1: Generate Tests

Use `@tester` agent (or write directly) to create tests:
- Follow patterns in existing test files
- Use fixtures from `tests/conftest.py`
- Cover critical paths from Definition of Done
- Use Given-When-Then format

### Step 3.2: Run Tests

```bash
# Run new tests specifically
uv run pytest tests/test_{feature}.py -v

# Run all tests to check for regressions
just check-test
```

### Step 3.3: Check Coverage

```bash
just check-coverage
```

Ensure coverage remains >= 80%.

### Step 3.4: Report Results

```
## Test Results

### New Tests
- tests/test_{feature}.py: X tests, all passing

### Full Suite
- Total: X | Passed: X | Failed: X
- Coverage: X%

### Coverage for New Code
- src/mlforge/{file}.py: X%
```

**CHECKPOINT 3**: Ask user to approve test results or request changes.

---

## Phase 4: Verification

### Step 4.1: Navigate to Example

```bash
cd examples/transactions
```

### Step 4.2: Run mlforge Commands

Test the new feature using CLI commands:

```bash
# Build features
uv run mlforge build

# List features
uv run mlforge list

# Inspect feature
uv run mlforge inspect {feature_name}

# Other relevant commands based on feature
```

### Step 4.3: Validate Output

Check that:
- Commands succeed without errors
- Output matches expected behavior from spec
- Files are created/modified as expected
- Data is correct

### Step 4.4: Report Verification

```
## Verification Results

### Commands Executed
1. `uv run mlforge build` -> Success
2. `uv run mlforge inspect {feature}` -> Success

### Validation Checklist
- [x] Feature builds correctly
- [x] Output matches spec
- [x] No errors or warnings

### Sample Output
[Relevant output snippet]
```

**CHECKPOINT 4**: Ask user to approve verification or request changes.

---

## Phase 5: Review

### Step 5.1: Code Review

Use `@code-reviewer` agent to analyze:
- Design principles compliance
- Red flags detection
- Code quality assessment

Or perform manual review against:
- AGENTS.md guidelines
- Project conventions
- Definition of Done checklist

### Step 5.2: Simplification Check

Look for opportunities to:
- Reduce code complexity
- Remove duplication
- Improve naming
- Simplify interfaces

### Step 5.3: Final Checklist

Verify against Definition of Done from spec:

```
## Definition of Done

### Code
- [x] Implementation complete
- [x] Type hints on all public functions
- [x] Docstrings following Google style
- [x] No ruff/ty errors

### Tests
- [x] Unit tests written
- [x] All tests passing
- [x] Coverage >= 80%

### Documentation
- [ ] API docs updated
- [ ] User guide updated
- [ ] CHANGELOG entry added

### Verification
- [x] Works in examples/transactions
- [x] Code review completed
```

### Step 5.4: Present Summary

```
## Feature Complete: {feature-name}

### Summary
- Files created: X
- Files modified: X
- Tests added: X
- Coverage: X%

### Remaining Items
- [ ] Update API docs
- [ ] Update user guide

### Ready for Commit
The feature implementation is complete and ready for `/commit-push-pr`.
```

**CHECKPOINT 5**: Ask user for final approval.

---

## Quick Mode (--quick)

When `--quick` flag is provided, combine Phases 3-5 into a single checkpoint:

1. Run all tests
2. Run verification
3. Perform quick review
4. Present combined results
5. Single approval checkpoint

Use for smaller features or when user wants faster iteration.

---

## Error Handling

### Feature Spec Not Found

```
Feature spec not found: roadmap/{version}/{feature-name}.md

Would you like me to:
1. Create a new spec using the template
2. Search for similar feature names
3. Cancel

Please choose (1/2/3):
```

If user chooses 1:
1. Copy from `roadmap/FEATURE_TEMPLATE.md`
2. Use `/research` to gather context
3. Draft the spec
4. Present for review

### Tests Failing

```
Some tests are failing:

## Failures
- test_name: error message

Would you like me to:
1. Fix the failing tests
2. Show detailed error output
3. Skip and continue (not recommended)
```

### Verification Failed

```
Verification failed:

## Issues
- Command X failed with error Y

Would you like me to:
1. Investigate and fix
2. Show full output
3. Skip (not recommended)
```

---

## Integration with Other Commands

After successful completion:
- Use `/commit-push-pr` to commit and create PR
- Use `/docs update` to update documentation
- Use `/tests coverage` to improve test coverage

---

## Tips

- Start with the spec - a good spec makes implementation smoother
- Review the plan carefully before approving
- Run tests frequently during implementation
- Use `--quick` for small features or hotfixes
- Always verify in `examples/transactions` before marking complete
