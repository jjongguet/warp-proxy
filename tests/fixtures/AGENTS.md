<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-09 | Updated: 2026-03-09 -->

# fixtures

## Purpose
Container directory for static test artifacts that capture Oz CLI behavior in reusable, deterministic files.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `oz/` | Sanitized Oz CLI output fixtures and notes about their provenance (see `oz/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Prefer adding or refreshing sanitized fixture files here instead of embedding large raw payloads directly in tests
- Keep fixture names descriptive and tied to the Oz command/output shape they represent

### Testing Requirements
- After changing fixtures, rerun the parser and integration tests that consume them, especially `pytest -q tests/test_oz_bridge.py tests/test_api.py`

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
