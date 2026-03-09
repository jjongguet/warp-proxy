# Implementation Status

- **Last updated:** 2026-03-09
- **Status:** Phase 2 implemented and evidenced
- **Authority note:** See [`docs/README.md`](./README.md) for the document authority chain. This file tracks implemented features and verification.

## What exists now

The repository contains a runnable FastAPI implementation with the originally planned Phase 2 additions now integrated.

### Implemented files
- `main.py`
- `config.py`
- `models.py`
- `oz_bridge.py`
- `conversation_store.py`
- `tests/test_api.py`
- `tests/test_anthropic_api.py`
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
- `POST /v1/responses` non-streaming (text subset)
- `POST /v1/responses` streaming/SSE (output_text events)
- `POST /v1/messages` non-streaming
- `POST /v1/messages` streaming/SSE
- `POST /v1/messages/count_tokens` (best-effort estimate)

### Operator API
- `GET /admin/status`

### Functional behavior
- explicit continuation via `metadata.warp_previous_response_id`
- persistent conversation store
- dual protocol adapters (OpenAI-compatible + Anthropic-compatible) over one Oz execution core
- OpenAI Responses API adapter for Codex-style gateway clients
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

> Cloud backend (`oz agent run-cloud`) has been removed. See [`docs/CLOUD_REMOVED.md`](./CLOUD_REMOVED.md) for details.

## Verification snapshot

Verified successfully:
- `python3 -m compileall main.py config.py models.py oz_bridge.py conversation_store.py tests`
- `. .venv/bin/activate && pytest -q`
- `. .venv/bin/activate && RUN_LIVE_OZ_SMOKE=1 pytest -q tests/smoke/test_live_oz.py`

## Remaining caveats

1. `/admin/status` remains alias-only even though `/v1/models` can expose additive namespaced passthrough ids.
2. The Oz CLI does not return token usage, so the `usage` field is always 0.

## Practical status

For the original goal — “run Oz as a local HTTP API server” — the project is now in a usable implemented state.
