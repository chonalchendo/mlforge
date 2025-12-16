# Claude Command: Commit (Python/uv)

Create well-formatted atomic commits with conventional commit messages and emoji.

**⚠️ CRITICAL: Commitizen Versioning**

This project uses **commitizen** for automated semantic versioning based on commit types. Every commit message directly impacts the package version number. Choosing the wrong commit type will result in incorrect version bumps. Take care to classify changes accurately.

## Semantic Version Format: `MAJOR.MINOR.PATCH`

| Version Part | Bump Trigger | Example |
|--------------|--------------|---------|
| **MAJOR** (1.0.0) | Breaking changes | `feat!:`, `fix!:`, `BREAKING CHANGE:` footer |
| **MINOR** (0.1.0) | New features | `feat:` |
| **PATCH** (0.0.1) | Bug fixes, refactors, performance | `fix:`, `refactor:`, `perf:` |
| **None** | Everything else | `docs:`, `style:`, `test:`, `chore:`, `ci:`, `build:` |

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

**🎯 Versioning Decision Point**: Before grouping, ask yourself:

| Question | Commit Type | Version Bump |
|----------|-------------|--------------|
| Does this introduce new functionality users can access? | feat | MINOR |
| Does this fix broken behavior? | fix | PATCH |
| Does this restructure code without changing behavior? | refactor | PATCH |
| Does this improve performance without changing API? | perf | PATCH |
| Does this change the API in a backward-incompatible way? | feat! / fix! | MAJOR |
| Is this tests, docs, CI, or tooling only? | docs, test, ci, chore, build, style | None |

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

[optional body]

[optional footer(s)]
```

- Present tense, imperative mood ("add" not "added")
- First line under 72 characters
- Lowercase description

### Breaking Changes

For breaking changes, use ONE of these formats:

```bash
# Option 1: Exclamation mark after type
git commit -m "💥 feat!: rename User.name to User.full_name"

# Option 2: BREAKING CHANGE footer
git commit -m "✨ feat: redesign authentication system

BREAKING CHANGE: OAuth tokens from v1 are no longer valid"
```

## Commit Types & Version Impact

### 🚀 Version-Bumping Types

These types trigger automatic version bumps via commitizen:

| Type | Emoji | Version Bump | Use For |
|------|-------|--------------|---------|
| `feat` | ✨ | **MINOR** (0.X.0) | New user-facing feature |
| `feat!` | 💥 | **MAJOR** (X.0.0) | Breaking feature change |
| `fix` | 🐛 | **PATCH** (0.0.X) | Bug fix |
| `fix!` | 💥 | **MAJOR** (X.0.0) | Breaking bug fix |
| `refactor` | ♻️ | **PATCH** (0.0.X) | Code restructuring, no behavior change |
| `refactor!` | 💥 | **MAJOR** (X.0.0) | Breaking refactor |
| `perf` | ⚡️ | **PATCH** (0.0.X) | Performance improvement |
| `perf!` | 💥 | **MAJOR** (X.0.0) | Breaking performance change |

### 🔧 Non-Version-Bumping Types

These types do NOT trigger version bumps but are still valuable for changelog and history:

| Type | Emoji | Version Bump | Use For |
|------|-------|--------------|---------|
| `docs` | 📝 | None | Documentation only |
| `style` | 💄 | None | Formatting, whitespace, no code change |
| `test` | ✅ | None | Adding or fixing tests |
| `chore` | 🔧 | None | Maintenance, tooling, config |
| `ci` | 🚀 | None | CI/CD pipeline changes |
| `build` | 🏗️ | None | Build system, dependencies |

## Extended Emoji Reference

### Fix Variants (all trigger PATCH bump)

| Emoji | Specific Use |
|-------|--------------|
| 🐛 | General bug fix |
| 🚑️ | Critical hotfix |
| 🩹 | Simple non-critical fix |
| 💚 | Fix CI build |
| 🚨 | Fix linter warnings |
| 🔒️ | Fix security issue |

### Refactor Variants (all trigger PATCH bump)

| Emoji | Specific Use |
|-------|--------------|
| ♻️ | General refactoring |
| 🧹 | Code cleanup |
| ⚰️ | Remove dead code |
| 🔥 | Remove code/files |

### Performance Variants (all trigger PATCH bump)

| Emoji | Specific Use |
|-------|--------------|
| ⚡️ | General performance |
| 🎯 | Optimize algorithms |

### Test Variants (no version bump)

| Emoji | Specific Use |
|-------|--------------|
| ✅ | Add/fix tests |
| 🧪 | Experimental tests |

### Build/Dependency Variants (no version bump)

| Emoji | Specific Use |
|-------|--------------|
| 🏗️ | Build system changes |
| ➕ | Add dependency |
| ➖ | Remove dependency |
| 📦️ | Update dependencies |

### Python-Specific (use with appropriate type)

| Emoji | Specific Use |
|-------|--------------|
| 🐍 | Python-specific features |
| 🏷️ | Type annotations |
| 🔍️ | Type hints/code analysis |
| 🦺 | Input validation/error handling |
| 📊 | Logging/monitoring |
| 🗃️ | Database changes |
| 🔐 | Auth features |
| 🌍 | Environment/config |

## Decision Guide: Choosing the Right Commit Type

Work through these questions in order. Use the first matching type:

| Question | If Yes | Emoji | Bump |
|----------|--------|-------|------|
| Is this a breaking change to the public API? | feat! / fix! | 💥 | MAJOR |
| Does this add new functionality users can use? | feat | ✨ | MINOR |
| Does this fix a bug or broken behavior? | fix | 🐛 | PATCH |
| Does this restructure/clean up code without changing behavior? | refactor | ♻️ | PATCH |
| Does this improve performance without changing the API? | perf | ⚡️ | PATCH |
| Is it documentation only? | docs | 📝 | none |
| Is it code formatting/style? | style | 💄 | none |
| Is it tests? | test | ✅ | none |
| Is it CI/CD? | ci | 🚀 | none |
| Is it build/dependencies? | build | 🏗️ | none |
| Is it other maintenance? | chore | 🔧 | none |

## Examples

### Feature Addition (MINOR bump: 0.1.0 → 0.2.0)

```bash
git add src/auth.py
just commit-prek
git commit -m "✨ feat: add JWT token authentication"
```

### Bug Fix (PATCH bump: 0.1.0 → 0.1.1)

```bash
git add src/parser.py
just commit-prek
git commit -m "🐛 fix: handle empty input in parse_config"
```

### Refactoring (PATCH bump: 0.1.0 → 0.1.1)

```bash
git add src/utils.py
just commit-prek
git commit -m "♻️ refactor: extract validation logic to separate module"
```

### Breaking Change (MAJOR bump: 0.1.0 → 1.0.0)

```bash
git add src/api.py
just commit-prek
git commit -m "💥 feat!: rename endpoint /users to /accounts"
```

### Documentation (NO version bump)

```bash
git add README.md
just commit-prek
git commit -m "📝 docs: document new validation module"
```

### Multiple Atomic Commits in a PR

```bash
# Commit 1: Dependencies (no bump)
git add pyproject.toml uv.lock
just commit-prek
git commit -m "➕ build: add pydantic for validation"

# Commit 2: Feature (MINOR bump)
git add src/models.py src/api.py
just commit-prek
git commit -m "✨ feat: implement user registration endpoint"

# Commit 3: Tests (no bump)
git add tests/
just commit-prek
git commit -m "✅ test: add unit tests for registration"

# Commit 4: Docs (no bump)
git add README.md
just commit-prek
git commit -m "📝 docs: document registration API"
```

**Result**: This PR will trigger a MINOR version bump (the `feat` commit is the highest-priority bump type present).

## PR Version Calculation

When a PR contains multiple commits, commitizen uses the **highest priority** bump:

| Priority | Commit Pattern | Version Bump |
|----------|----------------|--------------|
| 1st | BREAKING CHANGE footer or ! suffix | MAJOR |
| 2nd | feat | MINOR |
| 3rd | fix, refactor, perf | PATCH |
| 4th | All others | No bump |

**Example PR with mixed commits:**

| Commit | Bump |
|--------|------|
| 📝 docs: update README | none |
| ✨ feat: add new endpoint | MINOR |
| 🐛 fix: handle edge case | PATCH |
| ♻️ refactor: extract helper function | PATCH |
| ✅ test: add integration tests | none |

**Final PR bump: MINOR** (feat takes precedence over fix/refactor)

## Quick Reference

```
1. git status / git diff          # Review changes
2. Plan atomic commits            # Group logically, consider version impact
3. git add <files>                # Stage one commit's files
4. just commit-prek               # Run checks (fix & restage if needed)
5. git commit -m "emoji type: msg" # Commit with correct type for versioning
6. Repeat 3-5 for remaining changes
```

## ⚠️ Common Mistakes to Avoid

| Mistake | Why It's Wrong | Correct Approach |
|---------|----------------|------------------|
| Using `feat` for internal refactoring | Causes unnecessary MINOR bump | Use `refactor` (PATCH) |
| Using `fix` for new functionality | Causes PATCH instead of MINOR | Use `feat` |
| Forgetting ! for breaking changes | Missing MAJOR bump | Add ! suffix or BREAKING CHANGE footer |
| Using `chore` for bug fixes | Missing PATCH bump | Use `fix` |
| Using `chore` for refactoring | Missing PATCH bump | Use `refactor` |
| Lumping features and fixes together | Unclear version history | Separate into atomic commits |

Use `just check` instead of `just commit-prek` when you want to include unit tests.
