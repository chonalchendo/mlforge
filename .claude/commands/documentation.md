# Update Python Docstrings

Update docstrings for changed Python code in `src/mlforge/`.

## Workflow

Execute these steps in order:

### 1. Identify Changed Files
```bash
git diff --name-only HEAD~1 -- 'src/mlforge/*.py'
git diff --name-only --staged -- 'src/mlforge/*.py'
git status --porcelain -- 'src/mlforge/*.py'
```
If no changes found, check `git log --oneline -5` and ask user which commit range to review.

### 2. For Each Changed File
1. Run `git diff <file>` to see what code changed
2. Identify new/modified functions, classes, and methods
3. Review existing docstrings against current behavior
4. Update or add docstrings following the rules below

### 3. Validate
Run `just check` to verify changes pass all checks.

---

## Docstring Rules

### Style: Google-style docstrings
- One-line summary under 80 characters
- Include Args, Returns, Raises, Example sections where applicable
- Document public functions, classes, and methods
- Skip private methods unless complex

### Quality Principles

**Explain WHY, not WHAT**
```python
# ❌ Narrates the obvious
def process(user):
    """Process the user."""

# ✅ Explains the non-obvious
def process(user):
    """Process user for notification queue.
    
    Skips recently active users (<5 min) due to eventual consistency
    with the activity pipeline.
    """
```

**Keep it simple—if hard to describe, code may need refactoring**
```python
# ❌ Needs essay to explain (code smell)
def process(data, mode, flags):
    """Process data according to mode and flags.
    If mode is 'strict' and flags contains 'validate'...
    [multiple paragraphs of conditions]
    """

# ✅ Simple to describe because it does one thing
def validate(data: Data, level: ValidationLevel) -> ValidationResult:
    """Check data against schema. Level controls strictness."""
```

**Never repeat the code**
```python
# ❌ Comment repeats the obvious
def increment_count(count):
    """Increment the count by one and return it."""
    return count + 1

# ✅ Adds non-obvious information
def increment_count(count):
    """Increment count, capping at MAX_INT to prevent overflow."""
    return min(count + 1, MAX_INT)
```

**Interface docs describe behavior, not implementation**
```python
# ❌ Exposes implementation details
def get(self, key: str) -> Any:
    """Uses LRU with doubly-linked list for O(1) access.
    Internal _hash_map stores node references..."""

# ✅ Describes behavior callers care about
def get(self, key: str) -> Any:
    """Retrieve value from cache.
    
    Returns None if key not present or evicted.
    Accessing a key refreshes its LRU position.
    """
```