# warp-proxy

> **Use Warp's Oz AI anywhere — as a drop-in OpenAI / Anthropic API.**

`warp-proxy` is a lightweight local proxy server that exposes the [Warp](https://www.warp.dev/) Oz CLI as a fully compatible **OpenAI** and **Anthropic** HTTP API.
Already logged in to Warp? Your session is all you need. No extra API keys. No cloud re-routing.

> **한 줄 요약:** Warp에 이미 로그인되어 있다면, warp-proxy 하나로 Claude Code, Codex CLI, Open WebUI, Continue 등 모든 AI 클라이언트에서 Oz를 바로 쓸 수 있다.

```
Your AI client (OpenAI / Anthropic SDK)
        │
        ▼
 warp-proxy  :29113        ← this project
   (FastAPI, local-only)
        │
        ▼
   oz agent run            ← Warp's Oz CLI
        │
        ▼
   Warp / Oz AI            ← your logged-in session
```

---

## Highlights

- **Dual-protocol adapter** — speaks both OpenAI (`/v1/chat/completions`, `/v1/responses`) and Anthropic (`/v1/messages`) wire formats, including SSE streaming
- **Zero extra credentials** — reuses your existing Warp login session; `ANTHROPIC_API_KEY=dummy-local` is enough
- **Conversation continuity** — pass `metadata.warp_previous_response_id` to resume a prior Oz conversation thread
- **Model namespacing** — use the stable alias `warp-oz-cli` or pin a specific model with `warp-oz-cli/claude-4-6-sonnet-max`
- **Local-only by design** — hard-bound to `127.0.0.1`; no inbound network exposure
- **Concurrency control** — configurable semaphore prevents overwhelming the CLI backend
- **Version guard** — probes `oz dump-debug-info` at startup to ensure a known-good CLI version

---

## Table of Contents

1. [Requirements](#requirements)
2. [Quick Start](#quick-start)
3. [API Endpoints](#api-endpoints)
4. [Models](#models)
5. [Usage Examples](#usage-examples)
6. [Client Integration](#client-integration)
7. [Environment Variables](#environment-variables)
8. [Troubleshooting](#troubleshooting)
9. [Project Structure](#project-structure)
10. [Documentation Index](#documentation-index)

---

## Requirements

| Requirement | Version |
|---|---|
| Python | ≥ 3.11 |
| [uv](https://docs.astral.sh/uv/) *(recommended)* | any recent |
| Warp terminal + Oz CLI (`oz`) | verified version |

You must be **logged in to Warp** before starting warp-proxy. The proxy delegates every request to `oz agent run` and inherits your active session.

> **전제 조건:** Warp 터미널에 이미 로그인되어 있어야 한다. 프록시는 `oz agent run`을 직접 호출해 세션을 재사용한다.

---

## Quick Start

### Option A — uv (recommended)

No virtual environment management needed:

```bash
git clone https://github.com/your-org/warp-proxy
cd warp-proxy
uv run uvicorn main:app --host 127.0.0.1 --port 29113
```

### Option B — pip / venv

```bash
git clone https://github.com/your-org/warp-proxy
cd warp-proxy
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn main:app --host 127.0.0.1 --port 29113
```

### Verify

```bash
# List available models
curl http://127.0.0.1:29113/v1/models | jq .

# Smoke test
curl http://127.0.0.1:29113/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"warp-oz-cli","messages":[{"role":"user","content":"Reply with READY."}]}'
```

If you see a JSON response with `"content": "READY"` (or similar), you're good.

---

## API Endpoints

### OpenAI-compatible

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/models` | List available models |
| `POST` | `/v1/chat/completions` | Chat completions (streaming + non-streaming) |
| `POST` | `/v1/responses` | OpenAI Responses API (streaming + non-streaming) |

### Anthropic-compatible

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/messages` | Messages API (streaming + non-streaming) |
| `POST` | `/v1/messages/count_tokens` | Token count estimation |

### Admin

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/status` | Auth mode, CLI version probe, model availability |

---

## Models

### Stable alias

Always available — use this first:

```
warp-oz-cli
```

### Namespaced passthrough

Pin a specific Oz model by appending its ID:

```
warp-oz-cli/<oz_model_id>
```

**Examples:**

```
warp-oz-cli/auto
warp-oz-cli/auto-genius
warp-oz-cli/claude-4-6-sonnet-max
warp-oz-cli/claude-4-6-opus-high
warp-oz-cli/gpt-5-4-xhigh
warp-oz-cli/gemini-3-pro
```

Run `GET /v1/models` to see the current curated list. Set `WARP_PROXY_LIST_ALL_MODELS=true` to expose every model Oz reports.

> **팁:** 처음에는 항상 `warp-oz-cli`로 시작하고, 특정 모델이 필요할 때 namespaced ID로 전환하면 된다.

---

## Usage Examples

### Non-streaming chat

```bash
curl http://127.0.0.1:29113/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli",
    "messages": [
      {"role": "system", "content": "Be concise."},
      {"role": "user",   "content": "What is the capital of France?"}
    ]
  }'
```

### Streaming chat (SSE)

```bash
curl -N http://127.0.0.1:29113/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli",
    "stream": true,
    "messages": [{"role": "user", "content": "Count to five, one word per line."}]
  }'
```

The stream follows the standard OpenAI SSE contract:
`role chunk` → `content chunks` → `finish_reason: stop` → `data: [DONE]`

### OpenAI Responses API

```bash
curl http://127.0.0.1:29113/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli",
    "input": "Reply with READY."
  }'
```

### Anthropic Messages API

```bash
curl http://127.0.0.1:29113/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli/claude-4-6-sonnet-max",
    "max_tokens": 512,
    "messages": [{"role": "user", "content": "Reply with READY."}]
  }'
```

### Conversation continuation

Oz supports multi-turn conversations by referencing a prior response ID.

```bash
# --- Turn 1 ---
RESP=$(curl -s http://127.0.0.1:29113/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli",
    "messages": [{"role": "user", "content": "Remember the word BLUEBIRD and reply READY."}]
  }')

RESP_ID=$(echo "$RESP" | jq -r '.id')

# --- Turn 2 (continues the same Oz conversation thread) ---
curl http://127.0.0.1:29113/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"warp-oz-cli\",
    \"metadata\": {\"warp_previous_response_id\": \"$RESP_ID\"},
    \"messages\": [{\"role\": \"user\", \"content\": \"What word did I ask you to remember?\"}]
  }"
```

warp-proxy persists a `response_id → oz conversation_id` mapping so the second call automatically passes `--conversation` to the CLI.

> **이어가기:** `metadata.warp_previous_response_id`에 이전 응답 ID를 넣으면, warp-proxy가 내부적으로 Oz 대화 ID로 매핑해 `--conversation` 플래그와 함께 CLI를 호출한다.

---

## Client Integration

### Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:29113",
    "ANTHROPIC_API_KEY": "dummy-local"
  }
}
```

`ANTHROPIC_API_KEY` can be any non-empty string in `session` auth mode — warp-proxy does not validate it.

```bash
# Verify (headless)
claude -p "Reply with READY."

# One-liner without editing settings.json
ANTHROPIC_BASE_URL=http://127.0.0.1:29113 ANTHROPIC_API_KEY=dummy-local \
  claude -p "Reply with READY."
```

### Codex CLI

Add to `~/.codex/config.toml`:

```toml
model          = "warp-oz-cli"
model_provider = "warp_proxy"

[model_providers.warp_proxy]
name     = "warp-proxy"
base_url = "http://127.0.0.1:29113/v1"
env_key  = "WARP_PROXY_API_KEY"   # name of the env var used as the API key
wire_api = "responses"            # uses the /v1/responses endpoint
```

```bash
export WARP_PROXY_API_KEY=dummy-local   # any non-empty value

# Verify
codex -q "Reply with READY."

# One-liner
OPENAI_BASE_URL=http://127.0.0.1:29113/v1 OPENAI_API_KEY=dummy-local \
  codex -q "Reply with READY."
```

### Open WebUI

| Field | Value |
|-------|-------|
| OpenAI API URL | `http://127.0.0.1:29113/v1` |
| API Key | `dummy-local` (any value) |
| Model | `warp-oz-cli` |

If Open WebUI runs in Docker, use `http://host.docker.internal:29113/v1` instead.

### Continue (VS Code / JetBrains)

```json
{
  "models": [{
    "title": "Warp Oz",
    "provider": "openai",
    "apiBase": "http://127.0.0.1:29113/v1",
    "apiKey": "dummy-local",
    "model": "warp-oz-cli"
  }]
}
```

### CLIProxyAPI

warp-proxy registers as either an `openai-compatibility` provider or a `claude-api-key` provider in CLIProxyAPI's `config.yaml`. See [`docs/CLIPROXYAPI.md`](./docs/CLIPROXYAPI.md) for the full guide.

---

## Environment Variables

All configuration is done via environment variables — no config file required.

| Variable | Default | Description |
|----------|---------|-------------|
| `WARP_PROXY_HOST` | `127.0.0.1` | Bind address. Any non-localhost value is rejected at startup. |
| `WARP_PROXY_PORT` | `29113` | Server port. |
| `WARP_PROXY_AUTH_MODE` | `session` | `session` (reuse Warp login) or `api_key` (explicit key). |
| `WARP_API_KEY` | — | Required when `WARP_PROXY_AUTH_MODE=api_key`. |
| `WARP_PROXY_LIST_ALL_MODELS` | `false` | `true` to expose every discovered Oz model in `/v1/models`. |
| `WARP_PROXY_VERIFIED_WARP_VERSIONS` | *(built-in list)* | Comma-separated allowlist of accepted Warp CLI versions. |
| `ALLOW_UNVERIFIED_WARP_CLI` | `false` | `true` to skip the CLI version check entirely. |
| `WARP_PROXY_COMMAND_TIMEOUT_SECONDS` | `120` | Per-request Oz CLI execution timeout (seconds). |
| `WARP_PROXY_MAX_CONCURRENT_REQUESTS` | `4` | Max simultaneous Oz CLI processes. |
| `WARP_PROXY_CWD` | — | Working directory passed to `oz agent run --cwd`. |
| `WARP_PROXY_ENVIRONMENT` | — | Environment string passed to `oz agent run --environment`. |
| `WARP_PROXY_SKILL` | — | Skill passed to `oz agent run --skill`. |
| `WARP_PROXY_MCP` | — | MCP spec(s) passed to `oz agent run --mcp` (JSON string or array). |
| `WARP_PROXY_CONVERSATION_STORE` | `~/.warp-proxy/conversations.json` | Path for the response-ID → conversation-ID mapping store. |

> **주요 환경변수:** `WARP_PROXY_AUTH_MODE`, `WARP_PROXY_MAX_CONCURRENT_REQUESTS`, `WARP_PROXY_COMMAND_TIMEOUT_SECONDS` 세 가지만 알면 대부분의 경우 커버된다.

---

## Troubleshooting

### `/v1/models` works but chat requests fail

The proxy server is up, but the Oz CLI backend is not responding correctly.

1. Confirm you are logged in to Warp — open the Warp terminal and check
2. Run `oz dump-debug-info` directly and verify it exits cleanly
3. Try the stable alias first: `"model": "warp-oz-cli"`

### `unsupported_cli_version` error

warp-proxy probes the Oz CLI version at startup and rejects unknown versions to prevent silent behavioral regressions.

```bash
oz dump-debug-info   # check the reported Warp version
```

- Add the detected version to `WARP_PROXY_VERIFIED_WARP_VERSIONS`, or
- Set `ALLOW_UNVERIFIED_WARP_CLI=true` to bypass the check (not recommended for production use)

### Models don't appear in Open WebUI / Continue

```bash
# Direct check
curl http://127.0.0.1:29113/v1/models | jq .

# If the server is in Docker:
# use http://host.docker.internal:29113/v1 as the API base URL
```

### `conversation_expired` (409)

The referenced Oz conversation no longer exists on the backend (sessions can expire). Start a new conversation — omit `metadata.warp_previous_response_id`.

### Admin status endpoint

Always check this first when debugging:

```bash
curl http://127.0.0.1:29113/admin/status | jq .
```

It shows: auth mode, CLI version probe result, model availability, and configured `cwd`.

---

## Project Structure

```
warp-proxy/
├── main.py               # FastAPI app: route handlers, protocol adapters
│                         #   OpenAI ↔ Anthropic request/response translation
├── oz_bridge.py          # Core bridge: model resolution, CLI execution,
│                         #   NDJSON parsing, conversation continuation
├── models.py             # Pydantic request/response schemas
│                         #   (OpenAI + Anthropic wire types)
├── config.py             # Settings dataclass — all env-var driven
├── conversation_store.py # JSON-backed store: response_id → oz conversation_id
├── tests/                # Pytest test suite
├── docs/
│   ├── API_CONTRACT.md        # Authoritative HTTP contract (source of truth)
│   ├── ARCHITECTURE.md        # Design decisions and component boundaries
│   ├── IMPLEMENTATION_STATUS.md  # Verified feature matrix
│   ├── USAGE.md               # Extended curl examples
│   └── CLIPROXYAPI.md         # CLIProxyAPI integration guide
└── pyproject.toml
```

**How a request flows through the code:**

```
HTTP request
  → main.py (route handler)
    → protocol adapter (_anthropic_request_to_chat_request, _responses_request_to_chat_request, ...)
      → oz_bridge.OzBridge
        → _prepare_execution()   # validate, resolve model, check CLI version, resolve continuation
        → oz agent run ...       # subprocess (sync) or asyncio.create_subprocess_exec (streaming)
        → parse_ndjson_events()  # NDJSON → ParsedEvent list
        → aggregate_events()     # collapse text chunks, extract conversation_id
      → protocol adapter (response serialization)
  → HTTP response (JSON or SSE)
```

---

## Documentation Index

### Implementation reference

| Doc | Purpose |
|-----|---------|
| [`docs/API_CONTRACT.md`](./docs/API_CONTRACT.md) | Current HTTP API contract — source of truth |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | Architecture overview and design choices |
| [`docs/IMPLEMENTATION_STATUS.md`](./docs/IMPLEMENTATION_STATUS.md) | Feature matrix and verification snapshot |
| [`docs/USAGE.md`](./docs/USAGE.md) | Extended run / connection examples |
| [`docs/CLIPROXYAPI.md`](./docs/CLIPROXYAPI.md) | CLIProxyAPI integration (OpenAI + Anthropic modes) |

### Background / history

| Doc | Purpose |
|-----|---------|
| [`docs/DECISIONS.md`](./docs/DECISIONS.md) | Architecture decision records (ADRs) |
| [`docs/EVIDENCE.md`](./docs/EVIDENCE.md) | Design rationale and local verification records |
| [`docs/CLOUD_REMOVED.md`](./docs/CLOUD_REMOVED.md) | Why the cloud backend was removed (2026-03-09) |
| [`PRD.md`](./docs/archive/PRD.md) | Original product requirements draft |

---

## Security

- warp-proxy **only binds to `127.0.0.1`**. Attempting to bind to any other address is rejected at startup.
- It is designed for **single-user local use**. No multi-tenant isolation is implemented.
- In `session` mode, the API key field is not validated. Do not expose the port to a shared network.
- No silent backend switching — if the CLI version is unsupported, requests are rejected with a clear error.

---

## License

See [LICENSE](./LICENSE) for details.

---

<p align="center">
  <sub>warp-proxy is an independent open-source project and is not affiliated with or endorsed by Warp.</sub>
</p>
