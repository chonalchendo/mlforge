# Update MkDocs Documentation

Update existing documentation to reflect code changes committed on the current branch.

## Workflow

### Step 1: Identify What Changed

Determine the scope of documentation updates needed:

1. **Get the base branch:**
   ```bash
   git merge-base HEAD main
   ```
   (Try `main`, then `master` if that fails)

2. **List changed files:**
   ```bash
   git diff --name-only $(git merge-base HEAD main)
   ```

3. **Categorize changes:**
   - `src/**/*.py` → API or code changes requiring doc updates
   - `pyproject.toml` → Dependency, version, or CLI changes
   - `docs/**` → Direct documentation edits
   - `README.md` → May need to sync with docs/index.md

### Step 2: Analyse Code Changes

For each changed Python file, determine the documentation impact:

1. **Get the diff:**
   ```bash
   git diff $(git merge-base HEAD main) -- src/
   ```

2. **Identify what changed:**
   - New public functions/classes → Need new API docs
   - Modified signatures → Update existing docs
   - Renamed/moved modules → Update imports in examples
   - Deleted code → Remove from docs
   - New docstrings → API reference auto-updates

3. **Check for breaking changes:**
   - Changed function signatures
   - Renamed parameters
   - Removed public API
   - Changed return types

### Step 3: Map Changes to Documentation

Create a change map linking code changes to doc files:

| Code Change | Doc Files Affected |
|-------------|-------------------|
| New function in `module.py` | `docs/api/module.md`, `docs/quickstart.md` |
| Changed CLI command | `docs/cli.md` |
| New dependency | `docs/getting-started/installation.md` |
| New class | `docs/api/`, `docs/user-guide/` |
| Renamed parameter | All docs with examples using that parameter |

### Step 4: Update Documentation

Apply updates based on your change map:

#### For New Public API

1. Add to appropriate API reference page:
   ```markdown
   ::: package_name.new_module
   ```

2. If significant, add to user guide with examples

3. Update navigation in `mkdocs.yml` if new pages added

#### For Modified API

1. **Find affected examples:**
   ```bash
   grep -r "old_function_name" docs/
   ```

2. Update all code examples to use new signatures

3. Add migration notes if breaking:
   ```markdown
   !!! warning "Breaking change in v0.3.0"
       `old_param` has been renamed to `new_param`.
       Update your code accordingly.
   ```

#### For Deleted API

1. Remove from API reference
2. Remove or update examples using deleted code
3. Add deprecation notice if appropriate:
   ```markdown
   !!! danger "Removed in v0.3.0"
       `old_function` has been removed. Use `new_function` instead.
   ```

#### For pyproject.toml Changes

1. **New dependencies:** Update installation docs
2. **New CLI commands:** Add to `docs/cli.md`
3. **Changed entry points:** Update CLI documentation

### Step 5: Verify Updates

1. **Check for broken references:**
   ```bash
   uv run mkdocs build --strict
   ```

2. **Search for outdated references:**
   ```bash
   # Find references to old function/class names from the diff
   grep -r "old_name" docs/
   ```

3. **Verify code examples work:**
   - Mentally trace each example against the new code
   - Ensure imports are correct
   - Check that function signatures match

4. **Preview changes:**
   ```bash
   uv run mkdocs serve
   ```

### Step 6: Summarise Changes

Provide a summary of documentation updates:

```markdown
## Documentation Updates

### Files Modified
- `docs/api/module.md` - Added new `feature` function
- `docs/quickstart.md` - Updated example to use new parameter name

### Files Added
- `docs/user-guide/new-feature.md` - Guide for new feature

### Files Removed
- None

### Action Items
- [ ] Review new examples for accuracy
- [ ] Verify links work after rename
```

## Change Type Reference

### Adding a New Feature

1. Add function/class to API reference
2. Add usage example to quickstart (if core feature)
3. Create user guide page (if complex feature)
4. Update navigation in mkdocs.yml

### Modifying Existing Feature

1. API reference updates automatically via mkdocstrings
2. Update all code examples in docs
3. Add migration note if breaking change
4. Update any screenshots/diagrams if UI changed

### Deprecating a Feature

1. Add deprecation warning to API reference:
   ```markdown
   !!! warning "Deprecated"
       This function is deprecated and will be removed in v2.0.
       Use [`new_function`][package.new_function] instead.
   ```
2. Update examples to show new approach

### Removing a Feature

1. Remove from API reference
2. Remove all examples using it
3. Search docs for any remaining references

### Fixing a Bug

1. Usually no doc changes needed
2. If behaviour change affects examples, update them

## Guidelines

- **Minimal changes** - Only update what's affected by the code changes
- **Preserve style** - Match existing documentation tone and format
- **Working examples** - Verify all updated code snippets are correct
- **Clear migration path** - For breaking changes, show before/after

### Common Pitfalls

!!! danger "Don't forget"
    - Grep for old names across ALL docs, not just obvious places
    - Check code blocks inside admonitions and tabs
    - Verify mkdocs.yml nav if files were renamed/moved

!!! tip "Quick verification"
    Run `mkdocs build --strict` - it will catch:
    - Broken cross-references
    - Missing files in navigation
    - Invalid markdown syntax

## Output

- Updated `docs/` files reflecting code changes
- Updated `mkdocs.yml` if navigation changed
- Summary of changes made
- Any manual review items flagged