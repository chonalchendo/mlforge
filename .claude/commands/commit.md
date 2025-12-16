# Claude Command: Commit

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
