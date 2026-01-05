# Plan Feature

Create a comprehensive feature specification for collaborative planning with teammates.

## Usage

```
/plan-feature <version> <feature-name>
/plan-feature <version> <feature-name> --from-idea "<description>"
```

### Arguments

- `version`: Target version (e.g., v0.5.0, v0.6.0)
- `feature-name`: Feature name in kebab-case (e.g., redis-online, versioning)

### Options

- `--from-idea`: Starting description of the feature (skip initial prompt)

## Examples

```
/plan-feature v0.6.0 spark-engine
/plan-feature v0.7.0 rest-api --from-idea "REST API for serving features in real-time"
```

---

## Workflow Overview

```
CHECKPOINT 1: Research & Discovery
    ↓ User approves findings
CHECKPOINT 2: Draft Spec
    ↓ User approves spec
CHECKPOINT 3: Design Decisions
    ↓ User approves decisions
Spec saved → Ready for teammate review or /create-new-feature
```

---

## Phase 1: Research & Discovery

### Step 1.1: Understand the Feature

**If `--from-idea` provided:**
- Use that as the starting point
- Ask clarifying questions if needed

**Otherwise, ask the user:**
- What does this feature do? (2-3 sentences)
- What problem does it solve?
- Who benefits from this feature?

### Step 1.2: Codebase Exploration

Explore the codebase to understand the current state and patterns:

**Discovery tasks:**
- Use glob for filename searches, grep for content searches
- Search for variations (singular/plural, synonyms)
- Look in `src/mlforge/`, `tests/`, `examples/`

**Analysis tasks:**
- Find related existing code and patterns
- Identify integration points
- Discover similar implementations to reference
- List files that might need changes

**Output format:**
```
## Codebase Findings

### Related Code
- `src/mlforge/file.py:line` - Description of relevance

### Patterns to Follow
- **Pattern name**: Description with file reference

### Integration Points
- Where this feature connects to existing code

### Files Likely to Change
- `src/mlforge/file.py` - Type of changes needed
```

### Step 1.3: External Research

Research how similar tools handle this feature:

**Research targets:**
- Tools most relevant to the feature being built (e.g., Feast, Tecton, Hopsworks for feature store features; Redis docs for caching; DuckDB docs for query engines)
- Best practices and common patterns
- Potential pitfalls and anti-patterns
- Performance considerations

**Research methods:**
- Official documentation and changelogs
- GitHub issues and discussions
- Technical blog posts and articles
- Stack Overflow solutions

**Output format:**
```
## External Research

### How Others Solve This

#### [Tool/Library Name]
**Approach:** How they implement this
**Pros:** What works well
**Cons:** Limitations or issues
**Source:** [URL]

### Best Practices
- Practice 1 with rationale
- Practice 2 with rationale

### Pitfalls to Avoid
- Pitfall 1: Why and how to avoid
- Pitfall 2: Why and how to avoid

### Performance Considerations
- Consideration 1
- Consideration 2
```

### Step 1.4: Present Research Summary

Combine findings into a cohesive summary:

```
## Research Summary

### Current State
[What exists in the codebase today]

### External Landscape
[How other tools handle this, key insights]

### Recommended Approach
[Proposed direction based on research]

### Trade-offs to Consider
| Option | Pros | Cons |
|--------|------|------|
| Option A | ... | ... |
| Option B | ... | ... |

### Open Questions
- Question 1 for user/team to decide
- Question 2 for user/team to decide
```

**CHECKPOINT 1**: Ask user to approve research findings or request more investigation.

---

## Phase 2: Draft Specification

### Step 2.1: Generate Spec Header

```markdown
# Feature: [Feature Name]

**Version:** vX.Y.Z
**Status:** Planned
**Effort:** Low | Medium | High (estimate based on research)
**Breaking Changes:** Yes | No (based on API impact)
```

### Step 2.2: Write Summary & Motivation

Based on research findings:

```markdown
## Summary

[2-3 sentences: what this feature does and why it's needed]

## Motivation

- Why is this feature important?
- What problem does it solve?
- Who benefits?
```

### Step 2.3: Define Design Principles

Key decisions that will guide implementation:

```markdown
## Design Principles

- **Principle 1**: Description and rationale
- **Principle 2**: Description and rationale
- **Principle 3**: Description and rationale
```

Draw from:
- Existing mlforge patterns
- Best practices from external research
- Trade-off decisions made with user

### Step 2.4: Design API

Follow existing mlforge patterns from codebase exploration:

```markdown
## API Design

### Python API

```python
# Example usage showing the happy path
```

### CLI (if applicable)

```bash
# Example commands
```
```

**Guidelines:**
- Match existing mlforge API style
- Show common use cases first
- Include configuration options
- Add type hints in examples

### Step 2.5: Detail Implementation

```markdown
## Implementation Details

### Key Files

| File | Changes |
|------|---------|
| `src/mlforge/file.py` | Description of changes |

### Architecture Notes

[Important architectural decisions or patterns]

### Implementation Phases (if complex)

| Phase | Description | Dependencies |
|-------|-------------|--------------|
| 1 | First step | None |
| 2 | Second step | Phase 1 |
```

### Step 2.6: Define Done Criteria

Use standard template:

```markdown
## Definition of Done

### Code
- [ ] Implementation complete
- [ ] Type hints on all public functions
- [ ] Docstrings following Google style
- [ ] No ruff/ty errors

### Tests
- [ ] Unit tests written
- [ ] Integration tests (if applicable)
- [ ] All tests passing
- [ ] Coverage >= 80%

### Documentation
- [ ] API docs updated
- [ ] User guide updated (if applicable)
- [ ] CLI docs updated (if applicable)
- [ ] CHANGELOG entry added

### Verification
- [ ] Works in `examples/transactions`
- [ ] Code review completed
- [ ] No regressions in existing functionality
```

### Step 2.7: Document Dependencies

```markdown
## Dependencies

- **Depends on:** [Other features that must be complete first]
- **Blocked by:** [External factors]
- **Optional dependencies:** [e.g., `redis>=5.0.0`]
```

### Step 2.8: Plan Testing Strategy

```markdown
## Testing Strategy

### Unit Tests

- `test_function_scenario` - What it tests
- `test_function_edge_case` - What it tests

### Integration Tests

- Test scenario 1
- Test scenario 2

### Example Verification

```bash
cd examples/transactions
# Commands to verify the feature works
```
```

### Step 2.9: Present Draft Spec

Show the complete spec (without Design Decisions section yet).

**CHECKPOINT 2**: Ask user to approve draft or request changes.

---

## Phase 3: Design Decisions

### Step 3.1: Identify Key Decisions

Based on research and spec draft, identify decisions that need documentation:

- API design choices
- Storage/data model choices
- Algorithm or approach choices
- What's in scope vs out of scope

### Step 3.2: Document Each Decision

For each significant decision, create a trade-off table:

```markdown
## Design Decisions

### Why [Decision Topic]?

| Aspect | Option A | Option B (Chosen) |
|--------|----------|-------------------|
| Aspect 1 | How A handles it | How B handles it |
| Aspect 2 | A's approach | B's approach |
| Aspect 3 | A's trade-off | B's trade-off |

**Rationale:** [Why we chose Option B]

### Why [Another Decision]?

[Same format...]
```

### Step 3.3: Document Future Considerations

```markdown
## Future Considerations

- Feature/enhancement deferred to future release
- Potential optimization for later
- Integration with future planned features
```

### Step 3.4: Present Design Decisions

Show the design decisions section.

**CHECKPOINT 3**: Ask user to approve or refine decisions.

---

## Phase 4: Finalize & Save

### Step 4.1: Assemble Complete Spec

Combine all sections in order:
1. Header (name, version, status, effort, breaking)
2. Summary
3. Motivation
4. Design Principles
5. API Design
6. Implementation Details
7. Definition of Done
8. Dependencies
9. Testing Strategy
10. Design Decisions
11. Migration Guide (if breaking changes)
12. Future Considerations

### Step 4.2: Save Spec

Write to: `roadmap/{version}/{feature-name}.md`

### Step 4.3: Present Summary

```
## Feature Spec Complete: {feature-name}

Spec saved to: roadmap/{version}/{feature-name}.md

### Next Steps

1. **Share with teammates** for review and feedback
2. **Iterate** on the spec based on feedback
3. **When approved**, run `/create-new-feature {version} {feature-name}` to implement

### Spec Summary
- **Feature:** {feature-name}
- **Version:** {version}
- **Effort:** {effort}
- **Breaking:** {yes/no}
- **Key files:** {count} files to modify/create
- **Estimated phases:** {count}
```

---

## Error Handling

### Version Directory Doesn't Exist

```
Version directory not found: roadmap/{version}/

Would you like me to:
1. Create the directory and continue
2. List available versions
3. Cancel

Please choose (1/2/3):
```

### Feature Spec Already Exists

```
Feature spec already exists: roadmap/{version}/{feature-name}.md

Would you like me to:
1. Review and update the existing spec
2. Overwrite with a new spec
3. Cancel

Please choose (1/2/3):
```

---

## Tips

- **Iterate on research** - Don't rush to drafting; good research leads to better specs
- **Be specific in APIs** - Concrete examples prevent misunderstandings
- **Document trade-offs** - Future you (and teammates) will thank you
- **Keep scope tight** - Use "Future Considerations" for nice-to-haves
- **Verify against template** - Compare with existing specs in `roadmap/` for consistency
- **Share early** - Get teammate feedback before implementation begins
