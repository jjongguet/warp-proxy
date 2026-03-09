# Implementation Status

- **Last updated:** 2026-03-09
- **Status:** Phase 2 implemented and evidenced

## What exists now

The repository contains a runnable FastAPI implementation with the originally planned Phase 2 additions now integrated.

### Implemented files
- `main.py`
- `config.py`
- `models.py`
- `oz_bridge.py`
- `conversation_store.py`
- `tests/test_api.py`
- `tests/test_oz_bridge.py`
- `tests/test_conversation_store.py`
- `tests/smoke/test_live_oz.py`
- `tests/fixtures/oz/live_local_success.ndjson`
- `tests/fixtures/oz/live_stream_events.ndjson`
- `tests/fixtures/oz/live_stream_sse.txt`
- `tests/fixtures/oz/dump_debug_info_supported.txt`

## Implemented now

### Public API
- `GET /v1/models`
- `POST /v1/chat/completions` non-streaming
- `POST /v1/chat/completions` streaming/SSE

### Operator API
- `GET /admin/status`

### Functional behavior
- explicit continuation via `metadata.warp_previous_response_id`
- persistent conversation store
- startup-level `cwd`
- startup-level `environment`
- startup-level local-only `skill`
- startup-level `mcp`
- additive dynamic model passthrough
- lazy model discovery cache + refresh-on-miss
- local live smoke for non-streaming / streaming / continuation

## Backend adapter shape

### Local path
- `oz agent run --output-format json`
- NDJSON event parsing
- `type=agent` text extraction
- `conversation_started` / `conversation_id` capture

> Cloud backend(`oz agent run-cloud`)은 제거됨. 자세한 내용은 [`docs/CLOUD_REMOVED.md`](./CLOUD_REMOVED.md) 참조.

## Verification snapshot

Verified successfully:
- `python3 -m compileall main.py config.py models.py oz_bridge.py conversation_store.py tests`
- `. .venv/bin/activate && pytest -q`
- `. .venv/bin/activate && RUN_LIVE_OZ_SMOKE=1 pytest -q tests/smoke/test_live_oz.py`

## Remaining caveats

1. `/admin/status` remains alias-only even though `/v1/models` can expose additive namespaced passthrough ids.
2. Oz CLI는 토큰 사용량을 반환하지 않으므로 `usage` 필드는 항상 0이다.

## Practical status

For the original goal — “로컬에서 Oz를 HTTP API 서버처럼 띄워서 쓴다” — the project is now in a usable implemented state.
