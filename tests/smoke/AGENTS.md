<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-09 | Updated: 2026-03-09 -->

# smoke

## Purpose
Opt-in live end-to-end tests for the current local-only proxy. These tests exercise the real FastAPI app and a real logged-in Oz CLI session to verify non-streaming completions, SSE streaming, and conversation continuation against the actual environment.

## Key Files

| File | Description |
|------|-------------|
| `test_live_oz.py` | Live smoke coverage for local chat completions, local streaming, and local conversation continuation |

## Subdirectories
This directory currently has no child directories that require separate `AGENTS.md` files.

## For AI Agents

### Working In This Directory
- Keep all tests here explicitly opt-in via `RUN_LIVE_OZ_SMOKE=1`; the current file uses `_require_live_smoke()` and equivalent gating is acceptable
- Do not introduce mocks or `FakeRunner` here; the point is to validate the real CLI path
- Prefer structural assertions (status code, JSON shape, SSE framing, non-empty content) over brittle exact-response matching
- Use temporary conversation-store paths so live runs do not mutate a shared persistent store

### Testing Requirements
```bash
RUN_LIVE_OZ_SMOKE=1 pytest -q tests/smoke/
RUN_LIVE_OZ_SMOKE=1 pytest -q tests/smoke/test_live_oz.py
```

### Common Patterns
- Tests build an in-process app with `create_app(settings=..., bridge=OzBridge(settings))`
- Requests run through `httpx.ASGITransport` instead of a separately launched server process
- Helper functions centralize smoke gating and temp-path setup before the actual HTTP requests are made

## Dependencies

### Internal
- Imports from `../../main.py`, `../../config.py`, and `../../oz_bridge.py`

### External
- Requires a working `oz` CLI installation with an active Warp session
- Uses `httpx` and `pytest` / `pytest-anyio` for async smoke execution

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->

