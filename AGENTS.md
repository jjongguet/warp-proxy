<!-- Generated: 2026-03-09 | Updated: 2026-03-09 -->

# warp-proxy

## Purpose
A local OpenAI-compatible FastAPI proxy that exposes the logged-in Oz CLI through a narrow REST surface. The project translates chat completion requests into local `oz agent run` subprocess calls, normalizes NDJSON output into OpenAI-style JSON or SSE, preserves conversation continuation through a local mapping store, and stays locked to `127.0.0.1` for safety.

## Key Files

| File | Description |
|------|-------------|
| `src/warp_proxy/main.py` | FastAPI app factory and route registration for `/v1/models`, `/admin/status`, and `/v1/chat/completions` |
| `src/warp_proxy/config.py` | Environment-driven `Settings` dataclass, localhost-only validation, timeout/concurrency settings, and CLI version policy |
| `src/warp_proxy/models.py` | Pydantic request/response models for chat completions, model listing, admin status, and error envelopes |
| `src/warp_proxy/oz_bridge.py` | Core local Oz adapter: request validation, model discovery, version probing, CLI command assembly, NDJSON parsing, SSE streaming, and error mapping |
| `src/warp_proxy/conversation_store.py` | Persistent JSON mapping store from OpenAI-style response IDs to Oz conversation IDs using atomic writes |
| `requirements.txt` / `requirements-dev.txt` | Pinned-range runtime and dev dependency lists for `pip install -r` users |
| `pyproject.toml` | Package metadata, `src/` layout setuptools config, dependencies, and pytest configuration |
| `README.md` | Korean quick start, configuration, curl usage, and client integration guide |
| `docs/archive/PRD.md` | Initial product requirements and scope notes; historical planning artifact, archived |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `docs/` | Architecture, API contract, usage, implementation status, and historical design evidence (see `docs/AGENTS.md`) |
| `tests/` | Unit, integration, fixture, and live smoke coverage for the proxy (see `tests/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Do not change the host binding: `WARP_PROXY_HOST` is intentionally enforced as `127.0.0.1`
- Keep the OpenAI-compatible surface narrow and aligned with `docs/API_CONTRACT.md`; unsupported request fields should remain rejected via `extra="forbid"`
- Treat the cloud backend as removed; do not reintroduce `run-cloud` support casually without updating docs, tests, and compatibility notes together
- All runtime configuration must continue to come from environment variables; do not add config files or remote state
- Fail closed on Warp CLI version checks unless `ALLOW_UNVERIFIED_WARP_CLI=true` is explicitly set

### Testing Requirements
```bash
pytest -q
RUN_LIVE_OZ_SMOKE=1 pytest -q tests/smoke/
```

### Common Patterns
- `OzBridge` is the single adapter boundary between FastAPI handlers and Oz CLI subprocess execution
- Model exposure uses one stable alias (`warp-oz-cli`) plus optional namespaced passthrough IDs (`warp-oz-cli/<model_id>`)
- Conversation continuation is explicit through `metadata.warp_previous_response_id` and `ConversationStore`
- Streaming responses emit an assistant role chunk first, content chunks after that, then a terminal stop chunk and `[DONE]`
- Error mapping aims for descriptive OpenAI-style 4xx/5xx responses instead of opaque internal errors

## Dependencies

### Internal
- `src/warp_proxy/main.py` depends on `config.py`, `models.py`, and `oz_bridge.py` within the package
- `src/warp_proxy/oz_bridge.py` depends on `config.py`, `models.py`, and `conversation_store.py` within the package
- `tests/` exercises the public API surface plus parsing and persistence helpers
- `docs/` is the documentation source of truth for the supported API and current implementation status

### External
- `fastapi` — HTTP framework and routing
- `pydantic` — request/response validation
- `uvicorn` — ASGI server runtime
- `httpx` — async ASGI client used in tests
- `pytest` / `pytest-anyio` — unit, integration, and smoke test execution

## Configuration (Environment Variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `WARP_PROXY_HOST` | `127.0.0.1` | Bind address; any non-localhost value is rejected |
| `WARP_PROXY_PORT` | `29113` | HTTP listen port |
| `WARP_PROXY_AUTH_MODE` | `session` | Use logged-in session reuse or explicit `api_key` mode |
| `WARP_API_KEY` | — | Required when `WARP_PROXY_AUTH_MODE=api_key` |
| `WARP_PROXY_LIST_ALL_MODELS` | `false` | When `true`, expose discovered namespaced model IDs instead of only the curated set |
| `WARP_PROXY_VERIFIED_WARP_VERSIONS` | supported version list | Comma-separated allowlist for Warp CLI version validation |
| `WARP_PROXY_COMMAND_TIMEOUT_SECONDS` | `120` | Per-command timeout for short Oz CLI probes (version, model catalog) |
| `WARP_PROXY_AGENT_RUN_TIMEOUT_SECONDS` | `900` | Budget for one `oz agent run`: max NDJSON silence while streaming and total runtime for non-streaming completions. Agent tool work can legitimately stay silent for minutes |
| `WARP_PROXY_MAX_CONCURRENT_REQUESTS` | `4` | Concurrency limit enforced inside `OzBridge` |
| `WARP_PROXY_CWD` | — | Existing working directory forwarded to `oz agent run --cwd` |
| `WARP_PROXY_ENVIRONMENT` | — | Optional Oz environment forwarded to local runs |
| `WARP_PROXY_SKILL` | — | Optional Oz skill passed through to local runs |
| `WARP_PROXY_MCP` | — | JSON string or JSON array of strings forwarded as repeated `--mcp` flags |
| `WARP_PROXY_CONVERSATION_STORE` | `~/.warp-proxy/conversations.json` | Persistent response-id to conversation-id mapping store |
| `ALLOW_UNVERIFIED_WARP_CLI` | `false` | Bypass strict Warp CLI version enforcement |
| `WARP_PROXY_IGNORE_UNSUPPORTED_FIELDS` | `false` | `true` accepts-and-ignores unsupported request fields instead of rejecting with 400 |

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->

