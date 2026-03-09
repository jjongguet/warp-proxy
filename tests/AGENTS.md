<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-09 | Updated: 2026-03-09 -->

# tests

## Purpose
Pytest coverage for the local-only proxy. This directory combines deterministic unit tests, integration tests that inject a fake command runner, static CLI output fixtures, and opt-in live smoke tests against a real logged-in Oz CLI session.

## Key Files

| File | Description |
|------|-------------|
| `conftest.py` | Adds the project root to `sys.path` so the flat module layout imports cleanly in tests |
| `test_api.py` | Integration coverage for model listing, local chat completions, SSE streaming, namespaced model discovery, environment/skill/MCP passthrough, admin status, and conversation-store error paths |
| `test_oz_bridge.py` | Unit coverage for parsing helpers, prompt flattening, settings validation, and model catalog parsing |
| `test_conversation_store.py` | Persistence and corruption tests for the JSON-backed conversation mapping store |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `fixtures/` | Container for sanitized CLI output artifacts used by parser and integration tests (see `fixtures/AGENTS.md`) |
| `smoke/` | Opt-in live end-to-end tests against a real Oz CLI session (see `smoke/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Keep non-smoke tests deterministic: use `FakeRunner`, fixtures, and temporary paths instead of a real CLI process
- Any new request/response behavior in `main.py` or `oz_bridge.py` should get either an integration test in `test_api.py` or a focused unit test here
- Do not hide regressions behind new skips in regular tests; only live smoke coverage should remain opt-in
- Historical cloud fixtures may remain for documentation value, but new tests should target the current local-only implementation unless a deliberate feature revival is underway

### Testing Requirements
```bash
pytest -q
pytest -q tests/test_api.py
pytest -q tests/test_oz_bridge.py
pytest -q tests/test_conversation_store.py
RUN_LIVE_OZ_SMOKE=1 pytest -q tests/smoke/
```

### Common Patterns
- Async API tests use `httpx.ASGITransport` and `create_app(...)` rather than launching a real server
- `FakeRunner` records CLI argv calls so tests can assert exact subprocess construction
- Fixtures are read via `Path(...).read_text()` and should stay close to real CLI output formatting
- Streaming assertions check OpenAI-style SSE framing, including a terminal `data: [DONE]` sentinel on success

## Dependencies

### Internal
- Imports target `main.py`, `config.py`, `models.py`, `oz_bridge.py`, and `conversation_store.py`
- `fixtures/oz/` provides captured CLI output for parser and response-shape tests

### External
- `pytest` / `pytest-anyio` — async test execution
- `httpx` — ASGI test client

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->

