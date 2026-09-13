# GJC (Gajae Code) Integration Guide

**[English](./gjc-integration.md)** | **[한국어](./gjc-integration.ko.md)**

Connect **GJC (Gajae Code)** — a local coding-agent harness — to warp-proxy so every model role (default, executor, planner, critic, architect) can run on Warp Oz.

GJC custom providers speak HTTP (OpenAI-compatible or Anthropic-compatible). warp-proxy is the missing server half that translates HTTP into `oz agent run` subprocess calls, so Oz appears to GJC as a normal API provider.

---

## 1. Prerequisites

| Requirement | Check |
|---|---|
| Warp terminal installed and logged in | `oz whoami` exits cleanly |
| warp-proxy cloned with dependencies | `cd warp-proxy && uv sync --extra dev` |
| GJC installed | `gjc --version` |

## 2. Start the proxy (manual)

GJC does not start the proxy for you. Run it explicitly before using Oz-backed models:

```bash
cd /path/to/warp-proxy
python run.py                 # foreground; Ctrl+C to stop
# or: uv run python run.py
```

`python run.py` listens on `127.0.0.1:29113` and defaults
`WARP_PROXY_IGNORE_UNSUPPORTED_FIELDS=true`, so GJC's probe requests
(`stream_options`, `max_completion_tokens`) are accepted instead of rejected with 400.

Verify:

```bash
curl -s http://127.0.0.1:29113/v1/models | jq '.data[].id'
```

## 3. Register the provider in GJC

Add to `~/.gjc/agent/models.yml` under `providers:`:

```yaml
providers:
  warp-oz:
    baseUrl: http://127.0.0.1:29113/v1
    api: openai-completions
    auth: none
    discovery:
      type: openai-models-list
```

Then confirm GJC sees the models:

```bash
gjc models | grep warp-oz
```

> **Note on caching:** GJC caches provider discovery results in
> `~/.gjc/agent/models.db` (`model_cache` table). If newly curated models do not
> appear, delete the provider's row and run `gjc models` again while the proxy is up:
> `sqlite3 ~/.gjc/agent/models.db "DELETE FROM model_cache WHERE provider_id='warp-oz';"`

## 4. Create a model preset

Presets map GJC roles to models. Example — a strong/cheap split across the current lineup:

```yaml
profiles:
  oz-warp:
    required_providers:
      - warp-oz
    display_name: OZ-WARP · Fable Max + Astra Max + Auto
    model_mapping:
      default: warp-oz/warp-oz-cli/claude-5-1-fable-max
      executor: warp-oz/warp-oz-cli/auto-efficient
      planner: warp-oz/warp-oz-cli/gpt-6-astra-max
      critic: warp-oz/warp-oz-cli/gpt-6-astra-max
      architect: warp-oz/warp-oz-cli/gpt-6-astra-max
```

Model IDs come from `GET /v1/models` (curated list) or `oz model list --output-format json` (full catalog).

## 5. Verify the preset end to end

```bash
# with the proxy running:
gjc --mpreset oz-warp --no-session -p 'Reply with exactly: READY'
```

Expected: `READY`, and the proxy log shows the request arriving.

> **Protocol note:** GJC auto-selects the Anthropic wire format for `claude-*`
> model IDs, so those requests hit `POST /v1/messages`, while other models use
> `POST /v1/chat/completions`. warp-proxy serves both — no extra configuration.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `gjc models` shows no `warp-oz` section | Proxy not running, or probe got rejected — check §2, then clear the discovery cache (§3 note) |
| Requests fail with connection refused | Start the proxy: `python run.py` |
| `unsupported_cli_version` at startup | Your Warp version is newer than the allowlist — set `WARP_PROXY_VERIFIED_WARP_VERSIONS` or update warp-proxy |
| Preset roles ignored for subagents | `task.agentModelOverrides` in `~/.gjc/agent/config.yml` takes precedence for subagent roles — remove it if the preset should govern all roles |
