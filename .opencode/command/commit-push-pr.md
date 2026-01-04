# Claude Command: Commit-Push-Pr

# Commit

## Format (STRICT)

```
<emoji> <type>: <description>
```

- Exactly 1 space after emoji, 1 space after colon
- Lowercase description, imperative mood, under 72 chars

## Emoji-Type Mappings (must match exactly)

| Emoji | Type | Version Bump |
|-------|------|--------------|
| ✨ | feat | MINOR |
| 💥 | boom | MAJOR |
| 🐛 | fix | PATCH |
| 🚑️ | hotfix | PATCH |
| 🩹 | fix-simple | PATCH |
| 🔒️ | security | PATCH |
| ♻️ | refactor | PATCH |
| ⚡️ | perf | PATCH |
| 📝 | docs | none |
| 🎨 | style | none |
| ✅ | test | none |
| 💚 | ci | none |
| 👷 | build | none |
| 🔧 | config | none |
| ➕ | dep-add | none |
| ➖ | dep-rm | none |
| ⬆️ | dep-bump | none |
| 🏷️ | types | none |
| 🧹 | chore | none |
| ⚰️ | dead | none |
| 🗃️ | db | none |

## Workflow

```bash
git status && git diff
git add <files>
just commit-prek      # fix issues, restage, repeat until passing
git commit -m "<emoji> <type>: <description>"
```

Repeat for each atomic commit (group by: module, concern, type).

## Common Errors

- `🔧 build:` ❌ → `🔧 config:` or `👷 build:` ✓
- `👷 ci:` ❌ → `💚 ci:` or `👷 build:` ✓
- `✨feat:` ❌ → `✨ feat:` ✓ (space after emoji)

# Push

IMPORTANT: Ask user permission before pushing to remote branch.

The following git hooks are installed and run when pushing code:

```bash
    uvx prek install --hook-type=pre-push
    uvx prek install --hook-type=commit-msg
```

Therefore, there are some linting checks made on push. If there are errors then
please commit using the above commit workflow.

# Pull-Request

I follow the following branching strategy:
- main -> release/X.Y.Z -> feature/, refactor/ etc.

IMPORTANT: PRs should only be created when merging into main.
IMPORTANT: Please ask for permission before creating a PR.

All work is done in the feature, refactor etc. branches. Once work is complete there
it is then merged with with the release/X.Y.Z branch.

Finally, a PR is created from the release branch into main once all features planned from `roadmap/vX.Y.Z.md` document has been completed.

When creating a PR follow this template:
- What has changed?
- Why has this changed been made?
- How has the code been tested?
