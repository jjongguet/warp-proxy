# Implementation Status

- **Last updated:** 2026-09-14
- **Status:** Phase 2 implemented and evidenced
- **Authority note:** See [`docs/README.md`](./README.md) for the document authority chain. This file tracks implemented features and verification.

## What exists now

The repository contains a runnable FastAPI implementation with the originally planned Phase 2 additions now integrated.

### Implemented files
- `run.py`
- `requirements.txt` / `requirements-dev.txt`
- `src/warp_proxy/__init__.py`
- `src/warp_proxy/main.py`
- `src/warp_proxy/config.py`
- `src/warp_proxy/models.py`
- `src/warp_proxy/oz_bridge.py`
- `src/warp_proxy/conversation_store.py`
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
- `run.py` entry point with client-compat default (`WARP_PROXY_IGNORE_UNSUPPORTED_FIELDS=true` unless set)
- curated `/v1/models` lineup refreshed to the current catalog (46 models, dead IDs removed)
- bilingual docs (English / 한국어) and a GJC integration guide (`docs/gjc-integration.md`)

## Backend adapter shape

### Local path
- `oz agent run --output-format json`
- NDJSON event parsing
- `type=agent` text extraction
- `conversation_started` / `conversation_id` capture

> Cloud backend (`oz agent run-cloud`) has been removed. See [`docs/CLOUD_REMOVED.md`](./CLOUD_REMOVED.md) for details.

## Verification snapshot

Verified successfully:
- src-layout restructure verified on 2026-09-14 in a clean venv (warp-proxy itself not pip-installed):
  - `pip install -r requirements.txt` → `python run.py` boots on `127.0.0.1:29113`
  - `GET /admin/status` → 200 with supported CLI version `v0.2026.09.09.08.26.stable_02`
  - `GET /v1/models` → 200, 47 entries (baseline preserved)
  - real completion with OpenAI-SDK probe field `max_completion_tokens` → 200
  - `pip install -r requirements-dev.txt` → `pytest` — 39 passed, 3 skipped (2026-09-14)
- `run.py` self-heal verified on 2026-09-14 against hostile interpreters:
  - bare `python run.py` with the system shim (externally-managed Homebrew/Xcode Python) re-executes into `.venv` and serves: `/admin/status` 200, `/v1/models` 47, completion 200
  - `uv run python run.py` → `/admin/status` 200
  - `.venv/bin/pip install -r requirements.txt` runs clean after the bootstrap provisions `pip` into the uv-created venv
- `uv run --extra dev pytest` — 39 passed, 3 skipped (2026-09-13 and 2026-09-14 post-restructure)
- live smoke via `python run.py` on 2026-09-13: `/v1/models` lists 47 entries; completions on `auto-efficient`, `claude-5-1-fable-max`, `gpt-6-astra-max`, and `auto-open` all returned successfully; strict mode (`WARP_PROXY_IGNORE_UNSUPPORTED_FIELDS=false`) still rejects unsupported fields with 400
- GJC end-to-end on 2026-09-13: a preset mapping all roles to warp-oz models drove real completions through both `/v1/messages` (claude-family models) and `/v1/chat/completions`

## Remaining caveats

1. `/admin/status` remains alias-only even though `/v1/models` can expose additive namespaced passthrough ids.
2. The Oz CLI does not return token usage, so the `usage` field is always 0.

## Practical status

For the original goal — “run Oz as a local HTTP API server” — the project is now in a usable implemented state.
