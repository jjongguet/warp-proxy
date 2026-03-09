# Evidence / Decision Basis

- **Last updated:** 2026-03-09
- **Purpose:** 현재 설계와 문서가 어떤 근거 위에 서 있는지 정리한다.
- **Note:** historical cloud investigation은 삭제하지 않고 요약만 유지한다. 현재 supported surface는 local-only이며, cloud 관련 현재 상태는 `docs/CLOUD_REMOVED.md`를 우선한다.

## 1. Evidence categories

### A. Official Warp documentation
- Oz CLI reference
- API & SDK reference
- Warp blog / product pages

### B. Local CLI verification on this machine
- `oz agent run --help`
- `oz model list --output-format json`
- `oz mcp --help`
- `oz dump-debug-info`

### C. Repository implementation evidence
- fixture captures under `tests/fixtures/oz/`
- unit/integration tests under `tests/`
- live smoke coverage under `tests/smoke/`

## 2. Official/docs-backed facts

### 2.1 CLI login/session reuse is an official path
Warp CLI documentation describes:
- interactive login for local machines,
- API keys for automated/headless scenarios,
- reuse of existing credentials when already signed into Warp on the host.

This is the main basis for the default **session-backed local proxy** direction.

### 2.2 `oz agent run` is the best fit for the current product shape
The project goal is not a hosted orchestration control plane; it is a local companion proxy.
For that reason, the local `run` path is the most relevant execution surface for the current implementation.

### 2.3 Oz model discovery is a real backend capability
`oz model list --output-format json` provides a machine-readable model catalog.
This supports the current namespaced passthrough strategy and curated model exposure in `/v1/models`.

## 3. Local verification on this machine

### 3.1 Local `run` surface verified
Observed locally from `oz agent run --help`:
- `--output-format`
- `--conversation`
- `--cwd`
- `--environment`
- `--skill`
- `--mcp`

Why this matters:
- conversation continuation is technically available,
- local-workflow options are visible on the path the proxy actually uses,
- startup-level `cwd` / `environment` / `skill` / `mcp` passthrough is grounded in the CLI surface.

### 3.2 Version probing uses `oz dump-debug-info`
Observed locally:
- `oz version` is not a normal version command on this machine,
- `oz --version` is not supported,
- `oz dump-debug-info` exposes a `Warp version:` line.

This is the basis for the current allowlist-based version policy.

### 3.3 MCP is a backend input, not this project's public surface
`oz mcp --help` shows MCP management/listing behavior.
That supports the interpretation that this project should forward MCP server specs into Oz, not try to expose Oz itself as an MCP server.

## 4. Repository implementation evidence

### 4.1 Local NDJSON capture exists and matches the parser design
A direct local command produced NDJSON-style output like:

```json
{"type":"system","event_type":"conversation_started","conversation_id":"<redacted>"}
{"type":"agent","text":"READY.\n"}
```

Sanitized fixture:
- `tests/fixtures/oz/live_local_success.ndjson`

What this justifies:
- `oz agent run --output-format json` is a viable adapter contract,
- `type=agent` text extraction is a reasonable first-pass parser rule,
- conversation id capture from system events is practical.

### 4.2 Streaming evidence exists at both event and SSE levels
Sanitized fixtures:
- `tests/fixtures/oz/live_stream_events.ndjson`
- `tests/fixtures/oz/live_stream_sse.txt`

Together these show that the proxy's streaming path can be grounded in:
- local NDJSON backend events,
- OpenAI-style SSE output with role/content/stop framing,
- a terminal `[DONE]` sentinel on success.

### 4.3 Version baseline capture exists
Sanitized fixture:
- `tests/fixtures/oz/dump_debug_info_supported.txt`

This fixture pins the currently verified Warp version line used by parser and settings tests.

### 4.4 Automated verification commands are recorded
Repository docs currently record successful verification of:

```bash
python3 -m compileall main.py config.py models.py oz_bridge.py conversation_store.py tests
. .venv/bin/activate && pytest -q
. .venv/bin/activate && RUN_LIVE_OZ_SMOKE=1 pytest -q tests/smoke/test_live_oz.py
```

This is the strongest repo-local evidence that the documented local-only path is not merely theoretical.

## 5. What these facts justify

The combined evidence supports the following current product choices:
- local single-user proxy bound to `127.0.0.1`
- default session-backed auth with explicit API-key fallback
- `oz agent run --output-format json` as the canonical adapter path
- stable alias `warp-oz-cli` plus namespaced passthrough IDs
- explicit continuation via `metadata.warp_previous_response_id`
- OpenAI-style SSE streaming as an implemented and tested feature
- allowlist-based Warp version validation via `oz dump-debug-info`

## 6. Historical cloud evidence retained for reference

Earlier research and implementation work also explored `oz agent run-cloud`.
Those experiments confirmed that cloud execution exposed a materially different native contract than local `run`, and that maintaining both paths increased complexity for this project.

Historical captures retained in the repo:
- `tests/fixtures/oz/live_cloud_launch_summary.txt`
- `tests/fixtures/oz/live_cloud_run_get_success.txt`
- `tests/fixtures/oz/live_cloud_success_summary.txt`

Current interpretation:
- these artifacts are useful historical evidence,
- they do **not** define the current supported surface,
- the removal decision is documented in `docs/CLOUD_REMOVED.md`.

## 7. Source links

### Official docs
- CLI reference: https://docs.warp.dev/reference/cli/cli
- API & SDK reference: https://docs.warp.dev/reference/api-and-sdk/api-and-sdk
- Oz cloud agents blog: https://www.warp.dev/blog/oz-orchestration-platform-cloud-agents

### GitHub source
- warp-agent-action repo: https://github.com/warpdotdev/warp-agent-action
- source file: https://raw.githubusercontent.com/warpdotdev/warp-agent-action/main/src/index.ts
- README: https://raw.githubusercontent.com/warpdotdev/warp-agent-action/main/README.md

### Internal planning artifacts
- `.omx/specs/deep-interview-warp-code-agents-cli-endpoint.md`
- `.omx/plans/prd-warp-logged-in-proxy.md`
- `.omx/plans/test-spec-warp-logged-in-proxy.md`
