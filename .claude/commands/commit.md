# Claude Command: Commit (Python/uv)

Create well-formatted atomic commits with conventional commit messages and emoji.

## Usage

```
/commit              # Standard commit workflow
/commit --no-verify  # Skip pre-commit checks
/commit --with-tests # Run full test suite (just check)
```

## Workflow Steps

### Step 1: Review Source Control
```bash
git status
git diff
git diff --staged
```
Understand what files have changed and what changes are unstaged vs staged.

### Step 2: Plan Atomic Commits
Group related changes into logical commits. Split by:
- **Module/package**: Different Python modules = different commits
- **Concern**: Code vs tests vs docs vs config vs dependencies
- **Type**: Refactoring separate from features separate from fixes
- **Dependencies**: `pyproject.toml`/`uv.lock` changes separate from code

### Step 3: Stage Files for First Commit
```bash
git add <files-for-this-commit>
```
Stage only files that belong together logically.

### Step 4: Run Pre-commit Checks
```bash
just commit-prek
```
This runs ruff, bandit, and other hooks. If formatting errors occur:
1. Let the hooks auto-fix what they can
2. Stage the formatting fixes: `git add -u`
3. Re-run: `just commit-prek`
4. Repeat until all checks pass

For full checks including tests:
```bash
just check
```

### Step 5: Create Commit
```bash
git commit -m "<emoji> <type>: <description>"
```

### Step 6: Repeat
Return to Step 3 for remaining changes until all changes are committed.

## Commit Message Format

```
<emoji> <type>: <description>
```

- Present tense, imperative mood ("add" not "added")
- First line under 72 characters
- Lowercase description

## Commit Types & Emoji

| Type | Emoji | Use For |
|------|-------|---------|
| `feat` | ✨ | New feature |
| `fix` | 🐛 | Bug fix |
| `fix` | 🚑️ | Critical hotfix |
| `fix` | 🩹 | Simple non-critical fix |
| `fix` | 💚 | Fix CI build |
| `fix` | 🚨 | Fix linter warnings |
| `fix` | 🔒️ | Fix security issue |
| `docs` | 📝 | Documentation |
| `style` | 💄 | Formatting/style |
| `refactor` | ♻️ | Code refactoring |
| `refactor` | 🧹 | Code cleanup |
| `refactor` | ⚰️ | Remove dead code |
| `refactor` | 🔥 | Remove code/files |
| `perf` | ⚡️ | Performance improvement |
| `perf` | 🎯 | Optimize algorithms |
| `test` | ✅ | Add/fix tests |
| `test` | 🧪 | Experimental tests |
| `chore` | 🔧 | Config/tooling |
| `chore` | 🧑‍💻 | Developer experience |
| `ci` | 🚀 | CI/CD changes |
| `build` | 🏗️ | Build system |
| `build` | ➕ | Add dependency |
| `build` | ➖ | Remove dependency |
| `build` | 📦️ | Update dependencies |

### Python-Specific
| Emoji | Use For |
|-------|---------|
| 🐍 | Python-specific features |
| 🏷️ | Type annotations |
| 🔍️ | Type hints/code analysis |
| 🦺 | Input validation/error handling |
| 📊 | Logging/monitoring |
| 🗃️ | Database changes |
| 🔐 | Auth features |
| 🌍 | Environment/config |

## Examples

### Single Change
```bash
git add src/auth.py
just commit-prek
git commit -m "✨ feat: add JWT token authentication"
```

### Multiple Atomic Commits
```bash
# Commit 1: Dependencies
git add pyproject.toml uv.lock
just commit-prek
git commit -m "➕ build: add pydantic for validation"

# Commit 2: Feature
git add src/models.py src/api.py
just commit-prek
git commit -m "✨ feat: implement user registration endpoint"

# Commit 3: Tests
git add tests/
just commit-prek
git commit -m "✅ test: add unit tests for registration"

# Commit 4: Docs
git add README.md
just commit-prek
git commit -m "📝 docs: document registration API"
```

## Quick Reference

```
1. git status / git diff          # Review changes
2. Plan atomic commits            # Group logically
3. git add <files>                # Stage one commit's files
4. just commit-prek               # Run checks (fix & restage if needed)
5. git commit -m "emoji type: msg" # Commit
6. Repeat 3-5 for remaining changes
```

Use `just check` instead of `just commit-prek` when you want to include unit tests.
