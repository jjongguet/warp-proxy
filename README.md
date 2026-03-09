# warp-proxy

Warp/Oz CLI를 OpenAI-compatible + Anthropic-compatible HTTP endpoint로 재노출하는 **로컬 companion proxy** 프로젝트다.
이미 로그인된 Oz CLI 세션을 재사용해, 로컬에서 Oz를 OpenAI-style/Anthropic-style 클라이언트(Open WebUI, Continue, Codex CLI, Claude Code, curl, 간단한 스크립트)와 연결할 수 있게 만든다.

- **현재 상태:** 구현 완료, local-only 지원 유지
- **현재 기준 문서:** `docs/API_CONTRACT.md`, `docs/IMPLEMENTATION_STATUS.md`, `docs/USAGE.md`
- **중요 변경:** cloud backend는 **2026-03-09** 기준 supported surface에서 제거되었다. 관련 배경은 `docs/CLOUD_REMOVED.md` 참고

---

## 한눈에 보기

- **Bind:** `127.0.0.1` only
- **Primary backend:** `oz agent run`
- **Primary model:** `warp-oz-cli`
- **Main endpoints:** `GET /v1/models`, `POST /v1/chat/completions`, `POST /v1/responses`, `POST /v1/messages`, `POST /v1/messages/count_tokens`, `GET /admin/status`

---

## 추천 읽기 순서

### 지금 바로 필요한 문서
1. [`docs/API_CONTRACT.md`](./docs/API_CONTRACT.md) — 현재 지원하는 HTTP 계약의 source of truth
2. [`docs/USAGE.md`](./docs/USAGE.md) — 실제 실행/연결 방법
3. [`docs/IMPLEMENTATION_STATUS.md`](./docs/IMPLEMENTATION_STATUS.md) — 현재 구현 범위와 검증 상태
4. [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — 왜 이렇게 설계되었는지

### 배경/역사 문서
- [`docs/DECISIONS.md`](./docs/DECISIONS.md) — 현재 ADR과 설계 선택
- [`docs/EVIDENCE.md`](./docs/EVIDENCE.md) — 검증 근거와 조사 결과
- [`docs/CLOUD_REMOVED.md`](./docs/CLOUD_REMOVED.md) — 제거된 cloud backend 배경
- [`PRD.md`](./PRD.md) — 초기 기획 초안(현재 계약 문서는 아님)

---

## 이 프로젝트가 하는 일

바깥에서는 OpenAI/Anthropic API처럼:
- OpenAI: `POST /v1/chat/completions`, `POST /v1/responses`, `GET /v1/models`
- Anthropic: `POST /v1/messages`, `POST /v1/messages/count_tokens`

를 호출하고,
안쪽에서는 실제로:
- `oz agent run`

을 실행한다.

즉, 핵심 shape는 다음과 같다.

```text
OpenAI-compatible client
  -> local FastAPI proxy
  -> oz agent run
  -> logged-in Warp/Oz session (or explicit api_key mode)
```

### OpenAI Responses 요청

```bash
curl http://127.0.0.1:29113/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli",
    "input": "Reply with READY."
  }'
```

---

## 현재 지원하는 표면

### 공개 API (OpenAI-compatible)
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/responses`
### 공개 API (Anthropic-compatible)
- `POST /v1/messages`
- `POST /v1/messages/count_tokens`

### 운영용 API
- `GET /admin/status`

### 구현된 동작
- non-streaming chat completions
- SSE streaming (`stream=true`)
- explicit continuation via `metadata.warp_previous_response_id`
- stable alias `warp-oz-cli`
- namespaced passthrough IDs `warp-oz-cli/<oz_model_id>`
- startup-level `cwd`, `environment`, `skill`, `mcp`
- dynamic model discovery cache + refresh-on-miss
- strict Warp CLI version probe via `oz dump-debug-info`
- local live smoke coverage for non-streaming / streaming / continuation

### 보안/운영 원칙
- `127.0.0.1` 바인딩 강제
- 단일 사용자 로컬 사용 전제
- silent backend switching 없음
- 설정은 모두 환경변수 기반

---

## 빠른 시작

### 1. 서버 실행

```bash
cd /path/to/warp-proxy
. .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 29113
```

### 2. 모델 목록 확인

```bash
curl http://127.0.0.1:29113/v1/models | jq .
```

### 3. 가장 기본적인 요청

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

정상이라면 OpenAI-style `chat.completion` JSON이 반환된다.

---

## 모델 사용법

### 1. Stable alias
가장 먼저 써야 하는 기본 모델:
- `warp-oz-cli`

### 2. Namespaced passthrough
특정 Oz 모델을 직접 지정하려면:
- `warp-oz-cli/<oz_model_id>`

예:
- `warp-oz-cli/auto`
- `warp-oz-cli/claude-4-6-sonnet-max`
- `warp-oz-cli/gpt-5-4-xhigh`

### 3. `/v1/models` 노출 방식
- 기본값: curated passthrough 목록만 노출
- `WARP_PROXY_LIST_ALL_MODELS=true`: discovered 모델 전체 노출

처음에는 **반드시 `warp-oz-cli`부터** 확인하는 것을 권장한다.

---

## 요청 예시

### Non-streaming 요청

```bash
curl http://127.0.0.1:29113/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli",
    "messages": [
      {"role": "system", "content": "Be concise."},
      {"role": "user", "content": "Say hello."}
    ]
  }'
```

프록시는 `messages`를 flatten한 뒤 `oz agent run --output-format json` 기반으로 처리한다.

### Streaming / SSE 요청

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

성공 시 스트림은 다음 순서를 따른다.
- 첫 chunk: `assistant` role
- 이후 chunk: `content`
- 마지막 성공 chunk: `finish_reason=stop`
- 종료 sentinel: `data: [DONE]`
### Anthropic Messages 요청

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

### Continuation(이어가기)

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

이때 proxy가 내부적으로 `response_id -> oz conversation_id` 매핑을 조회해 `--conversation`으로 이어간다.

---

## 주요 환경변수

| Variable | Default | Purpose |
|----------|---------|---------|
| `WARP_PROXY_HOST` | `127.0.0.1` | 바인드 주소. localhost 외 값은 거부됨 |
| `WARP_PROXY_PORT` | `29113` | 서버 포트 |
| `WARP_PROXY_AUTH_MODE` | `session` | `session` 또는 `api_key` |
| `WARP_API_KEY` | — | `api_key` 모드일 때 필수 |
| `WARP_PROXY_LIST_ALL_MODELS` | `false` | discovered 모델 전체 노출 여부 |
| `WARP_PROXY_VERIFIED_WARP_VERSIONS` | supported version list | 허용할 Warp CLI 버전 allowlist |
| `WARP_PROXY_COMMAND_TIMEOUT_SECONDS` | `120` | Oz CLI 실행 타임아웃 |
| `WARP_PROXY_MAX_CONCURRENT_REQUESTS` | `4` | 내부 동시 실행 제한 |
| `WARP_PROXY_CWD` | — | local run에 전달할 작업 디렉토리 |
| `WARP_PROXY_ENVIRONMENT` | — | local run에 전달할 environment |
| `WARP_PROXY_SKILL` | — | local run에 전달할 skill |
| `WARP_PROXY_MCP` | — | local run에 전달할 MCP 스펙(JSON string/array) |
| `WARP_PROXY_CONVERSATION_STORE` | `~/.warp-proxy/conversations.json` | continuation 매핑 저장 경로 |
| `ALLOW_UNVERIFIED_WARP_CLI` | `false` | 버전 allowlist 검증 우회 |

추가 세부사항은 `docs/API_CONTRACT.md` 참고.

---

## 클라이언트 연결

### Open WebUI
- **API URL:** `http://127.0.0.1:29113/v1`
- **Docker에서 Open WebUI 실행 시:** `http://host.docker.internal:29113/v1`
- **Model:** `warp-oz-cli`

### Continue
- `provider: openai`
- `apiBase: http://127.0.0.1:29113/v1`
- `model: warp-oz-cli`
### Codex CLI
- `OPENAI_BASE_URL=http://127.0.0.1:29113/v1`
- 모델은 `warp-oz-cli` 또는 `warp-oz-cli/<oz_model_id>` 사용
### Claude Code (Anthropic gateway mode)
- `ANTHROPIC_BASE_URL=http://127.0.0.1:29113`
- model을 `warp-oz-cli` 또는 `warp-oz-cli/<oz_model_id>`로 설정

### 빠른 CLI 점검 (codex / claude)

Codex:

```bash
export OPENAI_BASE_URL=http://127.0.0.1:29113/v1
export OPENAI_API_KEY=dummy-local
codex -p "Reply with READY."
```

Claude Code:

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:29113
export ANTHROPIC_AUTH_TOKEN=dummy-local
claude -p "Reply with READY."
```

보다 자세한 예시는 `docs/USAGE.md` 참고.
CLIProxyAPI에 연결하려면 `docs/CLIPROXYAPI.md` 참고.

---

## 운영 확인용 엔드포인트

### `/admin/status`

```bash
curl http://127.0.0.1:29113/admin/status | jq .
```

여기서 확인할 수 있는 것:
- auth mode
- configured `cwd`
- stable alias availability
- cached Warp CLI version probe 상태

---

## 트러블슈팅

### `/v1/models` 는 되는데 chat이 안 된다
- Warp/Oz CLI 로그인 상태를 확인
- `oz dump-debug-info`가 정상 동작하는지 확인
- 먼저 `warp-oz-cli`로 테스트

### Continue / Open WebUI에서 모델이 안 보인다
- `http://127.0.0.1:29113/v1/models` 직접 확인
- Docker 환경이면 `host.docker.internal` 사용
- 서버가 실제로 `127.0.0.1:29113`에서 떠 있는지 확인

### unsupported CLI version 오류가 난다
- `oz dump-debug-info` 출력에서 Warp version을 확인
- `WARP_PROXY_VERIFIED_WARP_VERSIONS`를 맞추거나
- 정말 필요한 경우에만 `ALLOW_UNVERIFIED_WARP_CLI=true` 사용

---

## 문서 가이드

### 현재 구현 기준 문서
- [`docs/API_CONTRACT.md`](./docs/API_CONTRACT.md) — 현재 공개 API 계약
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — 현재 아키텍처와 설계 선택
- [`docs/IMPLEMENTATION_STATUS.md`](./docs/IMPLEMENTATION_STATUS.md) — 구현 상태와 검증 스냅샷
- [`docs/USAGE.md`](./docs/USAGE.md) — 실행/연결 예시
- [`docs/CLIPROXYAPI.md`](./docs/CLIPROXYAPI.md) — CLIProxyAPI 연동 가이드

### 역사적/배경 문서
- [`PRD.md`](./PRD.md) — 초기 기획 초안 (현재 구현과 일부 차이 있음)
- [`docs/DECISIONS.md`](./docs/DECISIONS.md) — 현재 ADR 로그
- [`docs/EVIDENCE.md`](./docs/EVIDENCE.md) — 설계 근거와 로컬 검증 기록
- [`docs/CLOUD_REMOVED.md`](./docs/CLOUD_REMOVED.md) — 제거된 cloud backend 관련 배경
