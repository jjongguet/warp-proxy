# Usage Guide

- **Last updated:** 2026-03-09
- **Scope:** 실제 실행 방법, curl 예시, Open WebUI/Continue 연결 예시

## 1. 5-line quick start

```bash
cd /path/to/warptocli
. .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 29113
curl http://127.0.0.1:29113/v1/models
curl http://127.0.0.1:29113/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"warp-oz-cli","messages":[{"role":"user","content":"Reply with READY."}]}'
```

## 2. Run the server

### Local shell

```bash
cd /path/to/warptocli
. .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 29113
```

## 3. curl examples

### 3.1 List models

```bash
curl http://127.0.0.1:29113/v1/models | jq .
```

### 3.2 Basic non-streaming request

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

### 3.3 Streaming / SSE request

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

### 3.4 Continuation request

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

Continuation:

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

## 4. Open WebUI

Open WebUI는 OpenAI-compatible API에 연결할 수 있다. 현재 `warptocli`는 `/v1/models`와 `/v1/chat/completions`를 제공하므로 OpenAI-compatible connection으로 붙이면 된다.

### Recommended settings
- **API URL:** `http://127.0.0.1:29113/v1`
- **If Open WebUI runs in Docker:** `http://host.docker.internal:29113/v1`
- **API Key:** `none` 또는 비어 있어도 되면 비움
- **Model:** `warp-oz-cli`

### Open WebUI steps
1. Open WebUI에서 **Admin Settings** 로 이동
2. **Connections > OpenAI > Manage** 로 이동
3. **Add New Connection** 클릭
4. **Standard / Compatible** 연결 유형 선택
5. URL에 `http://127.0.0.1:29113/v1` 입력
6. API Key는 `none` 또는 로컬 placeholder 입력
7. 저장 후 모델 선택기에서 `warp-oz-cli` 선택

### Notes
- Open WebUI가 `/v1/models`를 호출해서 모델을 확인한다.

## 5. Continue connection example

Continue는 OpenAI-compatible provider 설정에서 `apiBase`를 지정할 수 있다. `warptocli`는 이 경로로 붙이면 된다.

### Example `config.yaml`

```yaml
name: warptocli
version: 0.0.1
schema: v1

models:
  - name: warptocli-local
    provider: openai
    model: warp-oz-cli
    apiBase: http://127.0.0.1:29113/v1
    apiKey: local-dev
    roles:
      - chat
      - edit
      - apply
```

### Notes
- `apiKey`는 Continue 설정상 필드가 있으므로 예시에서는 `local-dev` placeholder를 썼다.
- 현재 `warptocli`는 별도 client-facing API key를 강제하지 않는다.

## 6. Recommended first model to use

처음엔 아래 순서로 써보는 걸 추천한다.

1. `warp-oz-cli`
2. `warp-oz-cli/<discovered-model-id>`

즉, 가장 먼저는 **local stable alias** 로 붙여서 동작을 확인하는 게 좋다.

## 7. Troubleshooting

### `/v1/models` 는 되는데 chat이 안 된다
- Warp/Oz CLI 로그인 상태 확인
- `oz dump-debug-info`가 정상 동작하는지 확인
- local path라면 먼저 `warp-oz-cli`로 테스트

### Continue / Open WebUI에서 모델이 안 보인다
- `http://127.0.0.1:29113/v1/models` 직접 확인
- Docker 환경이면 `host.docker.internal` 사용
- 서버가 127.0.0.1:29113에서 실제로 떠 있는지 확인

## 8. References

- Continue OpenAI-compatible config:
  - https://docs.continue.dev/customize/model-providers/top-level/openai
  - https://docs.continue.dev/reference/config
- Open WebUI OpenAI-compatible connections:
  - https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/
  - https://docs.openwebui.com/getting-started/quick-start/starting-with-vllm/
