# Commit, Push, and Pull Request Workflow

## Commit Format (STRICT)

```
<type>: <description>
```

- Exactly 1 space after colon
- Lowercase description, imperative mood, under 72 chars

## Commit Types

| Type | Version Bump |
|------|--------------|
| feat | MINOR |
| boom | MAJOR |
| fix | PATCH |
| hotfix | PATCH |
| fix-simple | PATCH |
| security | PATCH |
| refactor | PATCH |
| perf | PATCH |
| docs | none |
| style | none |
| test | none |
| ci | none |
| build | none |
| config | none |
| dep-add | none |
| dep-rm | none |
| dep-bump | none |
| types | none |
| chore | none |
| dead | none |
| db | none |

## Workflow

```bash
git status && git diff
git add <files>
git commit -m "<type>: <description>"
```

Repeat for each atomic commit (group by: module, concern, type).

## Common Errors

- `build: update config` - use `config:` for configuration changes
- `ci: add workflow` - use `ci:` for CI/CD changes, `build:` for build system
- `feat:add feature` - missing space after colon, should be `feat: add feature`

## Push

IMPORTANT: Ask user permission before pushing to remote branch.

If there are linting hooks configured, fix any issues and recommit before pushing.

## Pull Request

Branching strategy:
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
