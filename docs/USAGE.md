# Usage Guide
- **Last updated:** 2026-03-09
- **Scope:** Runtime execution, OpenAI/Anthropic request examples, and client integration guides for Open WebUI, Continue, Codex, and Claude Code
- **Applies to:** Current local-only implementation
- **Reading note:** If behavior looks different from what is described here, check `docs/API_CONTRACT.md` and `docs/IMPLEMENTATION_STATUS.md` first.
## 1. 5-line quick start
```bash
cd /path/to/warp-proxy
uv run uvicorn main:app --host 127.0.0.1 --port 29113
curl http://127.0.0.1:29113/v1/models
curl http://127.0.0.1:29113/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"warp-oz-cli","messages":[{"role":"user","content":"Reply with READY."}]}'
```
## 2. Run the server
### Option A — uv (recommended)
```bash
cd /path/to/warp-proxy
uv run uvicorn main:app --host 127.0.0.1 --port 29113
```
### Option B — venv
```bash
cd /path/to/warp-proxy
. .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 29113
```
## 3. OpenAI-compatible examples
### 3.1 List models
```bash
curl http://127.0.0.1:29113/v1/models | jq .
```
### 3.2 Basic non-streaming chat request
```bash
curl http://127.0.0.1:29113/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli",
    "messages": [
      {"role": "user", "content": "Reply with READY."}
    ]
  }'
```
### 3.3 Basic non-streaming responses request
```bash
curl http://127.0.0.1:29113/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli",
    "input": "Reply with READY."
  }'
```
### 3.4 Streaming responses request
```bash
curl -N http://127.0.0.1:29113/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli",
    "stream": true,
    "input": "Reply with READY in chunks."
  }'
```
### 3.5 Streaming / SSE chat request
```bash
curl -N http://127.0.0.1:29113/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli",
    "stream": true,
    "messages": [
      {"role": "user", "content": "Reply with READY in one or more chunks."}
    ]
  }'
```
### 3.6 Continuation request
First request:
```bash
first=$(curl -s http://127.0.0.1:29113/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli",
    "messages": [
      {"role": "user", "content": "Remember the word BLUEBIRD and reply READY."}
    ]
  }')
resp_id=$(printf '%s' "$first" | jq -r '.id')
```
Follow-up request:
```bash
curl http://127.0.0.1:29113/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"warp-oz-cli\",
    \"metadata\": {\"warp_previous_response_id\": \"${resp_id}\"},
    \"messages\": [
      {\"role\": \"user\", \"content\": \"What word did I ask you to remember?\"}
    ]
  }"
```
## 4. Anthropic-compatible examples
### 4.1 Basic `/v1/messages` request
```bash
curl http://127.0.0.1:29113/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli/claude-4-6-sonnet-high",
    "max_tokens": 512,
    "messages": [
      {"role": "user", "content": "Reply with READY."}
    ]
  }'
```
### 4.2 Streaming `/v1/messages` request
```bash
curl -N http://127.0.0.1:29113/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli/claude-4-6-sonnet-high",
    "max_tokens": 512,
    "stream": true,
    "messages": [
      {"role": "user", "content": "Reply with READY in chunks."}
    ]
  }'
```
### 4.3 `/v1/messages/count_tokens` request
```bash
curl http://127.0.0.1:29113/v1/messages/count_tokens \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli",
    "max_tokens": 256,
    "messages": [
      {"role": "user", "content": "Count this prompt."}
    ]
  }'
```
## 5. Open WebUI

Open WebUI connects to OpenAI-compatible APIs. Since `warp-proxy` exposes `/v1/models` and `/v1/chat/completions`, use the OpenAI-compatible connection type.

### Recommended settings
- **API URL:** `http://127.0.0.1:29113/v1`
- **If Open WebUI runs in Docker:** `http://host.docker.internal:29113/v1`
- **API Key:** `none` or leave empty
- **Model:** `warp-oz-cli`

## 6. Continue

Continue supports specifying `apiBase` in the OpenAI-compatible provider configuration. Point it to `warp-proxy` as follows.

### Example `config.yaml`
```yaml
name: warp-proxy
version: 0.0.1
schema: v1
models:
  - name: warp-proxy-local
    provider: openai
    model: warp-oz-cli
    apiBase: http://127.0.0.1:29113/v1
    apiKey: local-dev
    roles:
      - chat
      - edit
      - apply
```
## 7. Claude Code

In Claude Code gateway mode, use the Anthropic-compatible endpoint.
```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:29113
```
You can set the default model to `warp-oz-cli` or `warp-oz-cli/<oz_model_id>` in the settings file.

### 7.1 Quick verification
```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:29113
export ANTHROPIC_AUTH_TOKEN=dummy-local
claude -p "Reply with READY."
```
## 8. Codex CLI

Codex uses the OpenAI Responses API path, so specify the `/v1` base URL.
```bash
export OPENAI_BASE_URL=http://127.0.0.1:29113/v1
```
Set the model to `warp-oz-cli` or `warp-oz-cli/<oz_model_id>` in your configuration.

### 8.1 Quick verification
```bash
export OPENAI_BASE_URL=http://127.0.0.1:29113/v1
export OPENAI_API_KEY=dummy-local
codex -p "Reply with READY."
```
## 9. Recommended starting models

Start in this order:
1. `warp-oz-cli`
2. `warp-oz-cli/<discovered-model-id>`

## 10. Troubleshooting

### `/v1/models` works but chat/messages does not
- Check your Warp/Oz CLI login status
- Verify `oz dump-debug-info` runs without errors
- Test with `warp-oz-cli` first

### Models not visible in Continue / Open WebUI
- Check `http://127.0.0.1:29113/v1/models` directly
- Use `host.docker.internal` if running in a Docker environment
- Confirm the server is actually running on `127.0.0.1:29113`

### Claude Code gateway calls not working
- Confirm `ANTHROPIC_BASE_URL` is set to `http://127.0.0.1:29113`
- First verify with curl that `POST /v1/messages` returns 200
- Confirm `ANTHROPIC_AUTH_TOKEN` is set

### Codex provider calls not working
- Confirm `OPENAI_BASE_URL` is set to `http://127.0.0.1:29113/v1`
- First verify with curl that `POST /v1/responses` returns 200
- Confirm `OPENAI_API_KEY` is set

## 11. Reference links
- Continue OpenAI-compatible config:
  - https://docs.continue.dev/customize/model-providers/top-level/openai
  - https://docs.continue.dev/reference/config
- Open WebUI OpenAI-compatible connections:
  - https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/
  - https://docs.openwebui.com/getting-started/quick-start/starting-with-vllm/
- Claude Code LLM gateway requirements:
  - https://code.claude.com/docs/en/llm-gateway
- OpenAI Responses API:
  - https://platform.openai.com/docs/api-reference/responses
