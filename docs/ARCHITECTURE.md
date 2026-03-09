# Architecture

- **Last updated:** 2026-03-09
- **Status:** Current implementation — local-only proxy with Phase 2 features integrated
- **Authority note:** historical 문서와 충돌할 경우 현재 아키텍처 설명은 이 문서와 `docs/API_CONTRACT.md`를 우선한다.

## 1. System overview

```text
Client (OpenAI-compatible)
    |
    | POST /v1/chat/completions
    | GET  /v1/models
    v
Local FastAPI Proxy
    |
    | validate request
    | resolve model + auth mode
    | resolve continuation metadata
    | build subprocess args
    v
OzBridge
    |
    | oz agent run --output-format json
    v
Warp/Oz authenticated session or explicit API key
```

The proxy is intentionally narrow: it exposes a small OpenAI-compatible HTTP surface and translates that surface into local Oz CLI subprocess execution.

## 2. Primary design goals

- **Local-only safety** — bind exclusively to `127.0.0.1`
- **Session reuse first** — use an already logged-in Warp/Oz session by default
- **Deterministic normalization** — prefer machine-readable CLI output over ad hoc text scraping
- **Contract stability** — keep the public API smaller and steadier than the full Oz CLI surface
- **Explained failures** — return normalized OpenAI-style error envelopes instead of opaque 500s

## 3. Supported runtime modes

### A. Default session-backed mode
- Transport: local FastAPI service
- Backend command: `oz agent run`
- Auth mode: existing Warp/Oz session reuse
- Typical use case: local development and companion-proxy workflows

### B. Explicit API-key auth mode
- Enabled only with `WARP_PROXY_AUTH_MODE=api_key`
- Requires `WARP_API_KEY`
- Still uses the same local proxy and local CLI subprocess path
- Must never activate silently

### Not supported on the current public surface
- `oz agent run-cloud`
- `warp-oz-cli-cloud`
- any remote/network-exposed binding mode

Cloud support was intentionally removed from the supported surface on **2026-03-09**. Historical notes live in `docs/CLOUD_REMOVED.md` and `docs/EVIDENCE.md`.

## 4. Request lifecycle

For non-streaming requests, the runtime path is:

1. Parse and validate the OpenAI-compatible request body.
2. Reject unsupported fields via Pydantic `extra="forbid"`.
3. Resolve `model` into either the stable alias or a namespaced passthrough ID.
4. Validate or lazily discover the Oz model catalog when needed.
5. Probe the Warp CLI version if no cached version result exists yet.
6. Resolve `metadata.warp_previous_response_id` into a stored Oz conversation id when continuation is requested.
7. Flatten the `messages` array into a single prompt string.
8. Build the `oz agent run --output-format json ... --prompt <flattened>` command.
9. Execute the subprocess with timeout and concurrency limits.
10. Parse NDJSON output, extract assistant text, persist conversation mapping, and return a normalized OpenAI-style response.

Streaming follows the same preparation path, but emits OpenAI-style SSE chunks while backend events arrive.

## 5. Prompt normalization strategy

The proxy does not send raw message arrays to Oz. Instead it:
- flattens the full `messages` array in order,
- preserves role labels such as `[system]`, `[user]`, `[assistant]`,
- appends a short tail instruction that asks Oz to answer the latest user request.

This keeps system context and prior assistant/user turns visible to the CLI while preserving a predictable adapter boundary.

## 6. Backend output strategy

### Canonical local path
- Command: `oz agent run --output-format json`
- Output shape: NDJSON-style event stream
- Primary signal: `type="agent"` text payloads
- Conversation capture: `conversation_started` / `conversation_id`

### Why JSON/NDJSON is preferred
- easier fixture-based verification
- better malformed-output detection
- easier SSE chunk generation for streaming mode
- less ambiguity than scraping plain text stdout

The current implementation still treats stdout/stderr/exit code as the core integration surface; it simply prefers the JSON-backed CLI mode for determinism.

## 7. Model strategy

There are two distinct layers:

### Public model surface
- stable alias: `warp-oz-cli`
- namespaced passthrough: `warp-oz-cli/<oz_model_id>`

### Underlying Oz catalog
- sourced from `oz model list --output-format json`
- cached in-process after successful discovery
- refreshed once on model-miss before returning `unsupported_model`

The public contract stays stable even though the underlying Oz catalog may change over time.

## 8. Continuation strategy

### Default behavior
- requests are stateless unless the client explicitly asks to continue a previous response

### Explicit continuation path
- client sends `metadata.warp_previous_response_id`
- proxy looks up the stored mapping in `ConversationStore`
- proxy forwards the corresponding Oz conversation id via `--conversation`
- proxy updates `last_used_at` on successful lookup

### Persistence model
- mapping key: OpenAI-style response id
- stored value: Oz conversation id + backend + timestamps
- storage backend: local JSON file with atomic writes

This design keeps the default contract simple while still allowing reliable multi-turn continuation.

## 9. Streaming strategy

Streaming is implemented as OpenAI-style SSE.

### Success path
1. send an initial chunk with `delta.role = "assistant"`
2. emit content chunks as backend `agent` text arrives
3. emit a terminal chunk with `finish_reason = "stop"`
4. terminate with `data: [DONE]`

### Error path
- if an error happens **before** any stream chunk is emitted, return a normal JSON error response
- if an error happens **after** streaming has started, emit one terminal `data: {"error": ...}` payload and close without `[DONE]`

### Concurrency
- `OzBridge` enforces `WARP_PROXY_MAX_CONCURRENT_REQUESTS`
- streaming requests acquire a semaphore slot during the full stream lifecycle

## 10. Version and safety policy

### Version probe
- source of truth: `oz dump-debug-info`
- extracted field: `Warp version: Some("...")`
- policy: allowlist-based verification via `WARP_PROXY_VERIFIED_WARP_VERSIONS`
- override: `ALLOW_UNVERIFIED_WARP_CLI=true`

### Safety constraints
- `WARP_PROXY_HOST` must remain `127.0.0.1`
- no config files; configuration is environment-variable only
- no silent auth fallback between session and API key
- unsupported or malformed backend behavior should fail closed with explicit error codes

## 11. Operator diagnostics

The service exposes one operator endpoint outside the OpenAI-compatible contract:
- `GET /admin/status`

It reports:
- current auth mode
- whether `cwd` is configured
- stable alias availability
- cached Warp CLI version probe status

`/admin/status` remains alias-only even when `/v1/models` exposes additional discovered namespaced passthrough IDs.
