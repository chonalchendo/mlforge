# Feature: [Feature Name]

**Version:** vX.Y.Z
**Status:** Planned | In Progress | Done
**Effort:** Low | Medium | High
**Breaking Changes:** Yes | No

## Summary

[2-3 sentences: what this feature does and why it's needed]

## Motivation

[Why is this feature important? What problem does it solve?]

- Bullet point 1
- Bullet point 2

## Design Principles

[Key design decisions and rationale]

- **Principle 1**: Description
- **Principle 2**: Description

## API Design

### Python API

```python
# Example usage
```

### CLI (if applicable)

```bash
# Example commands
```

## Implementation Details

### Key Files

| File | Changes |
|------|---------|
| `src/mlforge/file.py` | Description of changes |

### Architecture Notes

[Any important architectural decisions or patterns]

## Definition of Done

All items must be checked before the feature is considered complete:

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

## Dependencies

- **Depends on:** [Other features or phases that must be complete first]
- **Blocked by:** [External factors]

## Testing Strategy

### Unit Tests

- Test case 1
- Test case 2

### Integration Tests

- Test scenario 1

### Example Verification

[How to verify this works in examples/transactions]

```bash
# Commands to run
```

## Migration Guide (if breaking changes)

### Before

```python
# Old way
```

### After

```python
# New way
```

## Future Considerations

[Things deferred to future releases]
