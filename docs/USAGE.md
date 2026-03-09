# Usage Guide
- **Last updated:** 2026-03-09
- **Scope:** 실제 실행 방법, OpenAI/Anthropic 요청 예시, Open WebUI/Continue/Codex/Claude Code 연결 예시
- **Applies to:** 현재 local-only 구현
- **Reading note:** 동작 차이가 의심되면 `docs/API_CONTRACT.md`와 `docs/IMPLEMENTATION_STATUS.md`를 우선 확인한다.
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
첫 요청:
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
이어서 요청:
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
## 5. Open WebUI 연결
Open WebUI는 OpenAI-compatible API에 연결할 수 있다. 현재 `warp-proxy`는 `/v1/models`와 `/v1/chat/completions`를 제공하므로 OpenAI-compatible connection으로 붙이면 된다.
### 권장 설정
- **API URL:** `http://127.0.0.1:29113/v1`
- **If Open WebUI runs in Docker:** `http://host.docker.internal:29113/v1`
- **API Key:** `none` 또는 비어 있어도 되면 비움
- **Model:** `warp-oz-cli`
## 6. Continue 연결
Continue는 OpenAI-compatible provider 설정에서 `apiBase`를 지정할 수 있다. `warp-proxy`는 이 경로로 붙이면 된다.
### 예시 `config.yaml`
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
## 7. Claude Code 연결
Claude Code gateway mode에서는 Anthropic-compatible endpoint를 사용한다.
```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:29113
```
설정 파일에서 기본 모델을 `warp-oz-cli` 또는 `warp-oz-cli/<oz_model_id>`로 지정해 사용할 수 있다.
### 7.1 빠른 실행 확인
```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:29113
export ANTHROPIC_AUTH_TOKEN=dummy-local
claude -p "Reply with READY."
```
## 8. Codex CLI 연결
Codex는 OpenAI Responses API 경로를 사용하므로 `/v1` 베이스 URL을 지정한다.
```bash
export OPENAI_BASE_URL=http://127.0.0.1:29113/v1
```
설정에서 모델은 `warp-oz-cli` 또는 `warp-oz-cli/<oz_model_id>`를 사용한다.
### 8.1 빠른 실행 확인
```bash
export OPENAI_BASE_URL=http://127.0.0.1:29113/v1
export OPENAI_API_KEY=dummy-local
codex -p "Reply with READY."
```
## 9. 처음 추천 모델
처음엔 아래 순서로 써보는 걸 추천한다.
1. `warp-oz-cli`
2. `warp-oz-cli/<discovered-model-id>`
## 10. 트러블슈팅
### `/v1/models` 는 되는데 chat/messages가 안 된다
- Warp/Oz CLI 로그인 상태 확인
- `oz dump-debug-info`가 정상 동작하는지 확인
- 먼저 `warp-oz-cli`로 테스트
### Continue / Open WebUI에서 모델이 안 보인다
- `http://127.0.0.1:29113/v1/models` 직접 확인
- Docker 환경이면 `host.docker.internal` 사용
- 서버가 `127.0.0.1:29113`에서 실제로 떠 있는지 확인
### Claude Code에서 gateway 호출이 안 된다
- `ANTHROPIC_BASE_URL`가 `http://127.0.0.1:29113`인지 확인
- `POST /v1/messages`가 200을 반환하는지 curl로 먼저 확인
- `ANTHROPIC_AUTH_TOKEN`를 설정했는지 확인
### Codex에서 provider 호출이 안 된다
- `OPENAI_BASE_URL`가 `http://127.0.0.1:29113/v1`인지 확인
- `POST /v1/responses`가 200을 반환하는지 curl로 먼저 확인
- `OPENAI_API_KEY`를 설정했는지 확인
## 11. 참고 링크
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
