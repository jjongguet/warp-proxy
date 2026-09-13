# warp-proxy

**[English](README.md)** | **[한국어](README.ko.md)**

> **Warp의 Oz AI를 어디서든 — OpenAI / Anthropic 호환 API로.**

`warp-proxy` 는 [Warp](https://www.warp.dev/) 의 Oz CLI를 완전히 호환되는 **OpenAI** 및 **Anthropic** HTTP API로 노출하는 가벼운 로컬 프록시 서버다.
이미 Warp에 로그인되어 있다면 세션 하나면 충분하다. 추가 API 키도, 클라우드 우회도 없다.

```
AI 클라이언트 (OpenAI / Anthropic SDK)
        │
        ▼
 warp-proxy  :29113        ← 이 프로젝트
   (FastAPI, 로컬 전용)
        │
        ▼
   oz agent run            ← Warp의 Oz CLI
        │
        ▼
   Warp / Oz AI            ← 로그인된 세션
```

---

## Highlights

- **듀얼 프로토콜 어댑터** — OpenAI(`/v1/chat/completions`, `/v1/responses`)와 Anthropic(`/v1/messages`) 와이어 포맷을 모두 지원, SSE 스트리밍 포함
- **추가 자격증명 불필요** — 기존 Warp 로그인 세션 재사용; `ANTHROPIC_API_KEY=dummy-local` 로 충분
- **대화 연속성** — `metadata.warp_previous_response_id` 를 전달하면 이전 Oz 대화 스레드를 이어감
- **모델 네임스페이싱** — 안정 별칭 `warp-oz-cli` 사용 또는 `warp-oz-cli/claude-5-1-fable-max` 처럼 특정 모델 고정
- **로컬 전용 설계** — `127.0.0.1` 에 강제 바인드; 인바운드 네트워크 노출 없음
- **동시성 제어** — 설정 가능한 세마포어로 CLI 백엔드 보호
- **버전 가드** — 기동 시 `oz dump-debug-info` 를 조회해 알려진 CLI 버전인지 확인

---

## 목차

1. [요구 사항](#요구-사항)
2. [퀵 스타트](#퀵-스타트)
3. [API 엔드포인트](#api-엔드포인트)
4. [모델](#모델)
5. [사용 예시](#사용-예시)
6. [클라이언트 연동](#클라이언트-연동)
7. [환경변수](#환경변수)
8. [문제 해결](#문제-해결)
9. [프로젝트 구조](#프로젝트-구조)
10. [문서 인덱스](#문서-인덱스)

---

## 요구 사항

| 요구 | 버전 |
|---|---|
| Python | ≥ 3.11 |
| [uv](https://docs.astral.sh/uv/) *(권장)* | 최신 버전 아무거나 |
| Warp 터미널 + Oz CLI (`oz`) | 검증된 버전 |

warp-proxy 시작 전 **Warp에 로그인**되어 있어야 한다. 프록시는 모든 요청을 `oz agent run` 에 위임하며 활성 세션을 상속받는다.

---

## 퀵 스타트

### 옵션 A — uv (권장)

가상환경 관리가 필요 없다:

```bash
git clone https://github.com/jjongguet/warp-proxy
cd warp-proxy
uv run python run.py
```

### 옵션 B — pip / venv

```bash
git clone https://github.com/jjongguet/warp-proxy
cd warp-proxy
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python run.py
```

### 확인

```bash
# 모델 목록
curl http://127.0.0.1:29113/v1/models | jq .

# 스모크 테스트
curl http://127.0.0.1:29113/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"warp-oz-cli","messages":[{"role":"user","content":"Reply with READY."}]}'
```

`"content": "READY"` 가 담긴 JSON 응답이 오면 성공.

> **참고:** `python run.py` 는 환경변수를 지정하지 않으면
> `WARP_PROXY_IGNORE_UNSUPPORTED_FIELDS=true` 로 기동한다. OpenAI SDK / GJC 가
> 보내는 `stream_options`, `max_completion_tokens` 필드가 400으로 거부되지
> 않도록 하기 위해서다. 엄격 모드는 `=false` 로 명시하면 된다.

---

## API 엔드포인트

### OpenAI 호환

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/v1/models` | 사용 가능한 모델 목록 |
| `POST` | `/v1/chat/completions` | 채팅 완성 (스트리밍 + 논스트리밍) |
| `POST` | `/v1/responses` | OpenAI Responses API (스트리밍 + 논스트리밍) |

### Anthropic 호환

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/v1/messages` | Messages API (스트리밍 + 논스트리밍) |
| `POST` | `/v1/messages/count_tokens` | 토큰 수 추정 |

### Admin

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/admin/status` | 인증 모드, CLI 버전 프로브, 모델 가용성 |

---

## 모델

### 안정 별칭

항상 사용 가능 — 우선 이것부터:

```
warp-oz-cli
```

### 네임스페이스 패스스루

Oz 모델 ID를 덧붙여 특정 모델을 고정한다:

```
warp-oz-cli/<oz_model_id>
```

**예시:**

```
warp-oz-cli/auto
warp-oz-cli/auto-efficient
warp-oz-cli/claude-5-1-fable-max
warp-oz-cli/claude-4-8-opus-max
warp-oz-cli/gpt-6-astra-max
warp-oz-cli/gpt-5-6-luna-xhigh
```

`GET /v1/models` 로 현재 큐레이션 목록을 확인한다. `WARP_PROXY_LIST_ALL_MODELS=true` 를 설정하면 Oz가 보고하는 모든 모델이 노출된다.

---

## 사용 예시

### 논스트리밍 채팅

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

### 스트리밍 채팅 (SSE)

```bash
curl -N http://127.0.0.1:29113/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli",
    "stream": true,
    "messages": [{"role": "user", "content": "Count to five, one word per line."}]
  }'
```

스트림은 표준 OpenAI SSE 계약을 따른다:
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
    "model": "warp-oz-cli/claude-5-1-fable-max",
    "max_tokens": 512,
    "messages": [{"role": "user", "content": "Reply with READY."}]
  }'
```

### 대화 이어가기

이전 응답 ID를 참조해 멀티턴 대화를 지속한다.

```bash
# --- 1턴 ---
RESP=$(curl -s http://127.0.0.1:29113/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "warp-oz-cli",
    "messages": [{"role": "user", "content": "Remember the word BLUEBIRD and reply READY."}]
  }')

RESP_ID=$(echo "$RESP" | jq -r '.id')

# --- 2턴 (같은 Oz 대화 스레드를 이어감) ---
curl http://127.0.0.1:29113/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"warp-oz-cli\",
    \"metadata\": {\"warp_previous_response_id\": \"$RESP_ID\"},
    \"messages\": [{\"role\": \"user\", \"content\": \"What word did I ask you to remember?\"}]
  }"
```

warp-proxy는 `response_id → oz conversation_id` 매핑을 저장하므로 두 번째 호출에서 자동으로 CLI에 `--conversation` 을 전달한다.

---

## 클라이언트 연동

### Claude Code

`~/.claude/settings.json` 에 추가:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:29113",
    "ANTHROPIC_API_KEY": "dummy-local"
  }
}
```

`session` 인증 모드에서 `ANTHROPIC_API_KEY` 는 빈 값만 아니면 아무 문자열이나 가능하다 — warp-proxy가 검증하지 않는다.

```bash
# 확인 (헤드리스)
claude -p "Reply with READY."

# settings.json 수정 없이 한 줄 실행
ANTHROPIC_BASE_URL=http://127.0.0.1:29113 ANTHROPIC_API_KEY=dummy-local \
  claude -p "Reply with READY."
```

### Codex CLI

`~/.codex/config.toml` 에 추가:

```toml
model          = "warp-oz-cli"
model_provider = "warp_proxy"

[model_providers.warp_proxy]
name     = "warp-proxy"
base_url = "http://127.0.0.1:29113/v1"
env_key  = "WARP_PROXY_API_KEY"   # API 키로 쓸 환경변수 이름
wire_api = "responses"            # /v1/responses 엔드포인트 사용
```

```bash
export WARP_PROXY_API_KEY=dummy-local   # 빈 값이 아니면 아무거나

# 확인
codex -q "Reply with READY."
```

### Open WebUI

| 필드 | 값 |
|-------|---|
| OpenAI API URL | `http://127.0.0.1:29113/v1` |
| API Key | `dummy-local` (아무 값) |
| Model | `warp-oz-cli` |

Open WebUI 가 Docker 에서 실행 중이면 `http://host.docker.internal:29113/v1` 을 대신 사용한다.

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

### GJC (가재코드)

`~/.gjc/agent/models.yml` 에 `warp-oz` 커스텀 프로바이더로 등록하고 그 위에 모델 프리셋을 구성한다. 전체 가이드(영어/한국어)는 [`docs/gjc-integration.ko.md`](./docs/gjc-integration.ko.md) 를 참고.

### CLIProxyAPI

warp-proxy는 CLIProxyAPI 의 `config.yaml` 에 `openai-compatibility` 또는 `claude-api-key` 프로바이더로 등록된다. 전체 가이드는 [`docs/CLIPROXYAPI.md`](./docs/CLIPROXYAPI.md).

---

## 환경변수

모든 설정은 환경변수로만 한다 — 설정 파일 불필요.

| 변수 | 기본값 | 설명 |
|------|---------|------|
| `WARP_PROXY_HOST` | `127.0.0.1` | 바인드 주소. 로컬호스트 외 값은 기동 시 거부. |
| `WARP_PROXY_PORT` | `29113` | 서버 포트. |
| `WARP_PROXY_AUTH_MODE` | `session` | `session` (Warp 로그인 재사용) 또는 `api_key` (명시적 키). |
| `WARP_API_KEY` | — | `WARP_PROXY_AUTH_MODE=api_key` 일 때 필수. |
| `WARP_PROXY_LIST_ALL_MODELS` | `false` | `true` 면 디스커버리된 모든 Oz 모델을 `/v1/models` 에 노출. |
| `WARP_PROXY_VERIFIED_WARP_VERSIONS` | *(내장 목록)* | 허용할 Warp CLI 버전 쉼표 목록. |
| `ALLOW_UNVERIFIED_WARP_CLI` | `false` | `true` 면 CLI 버전 검사를 완전히 건너뜀. |
| `WARP_PROXY_IGNORE_UNSUPPORTED_FIELDS` | `false` | `true` 면 미지원 요청 필드를 400 거부 대신 무시. `python run.py` 는 명시 없으면 `true` 로 기동. |
| `WARP_PROXY_COMMAND_TIMEOUT_SECONDS` | `120` | 요청별 Oz CLI 실행 타임아웃 (초). |
| `WARP_PROXY_MAX_CONCURRENT_REQUESTS` | `4` | 동시 Oz CLI 프로세스 최대 수. |
| `WARP_PROXY_CWD` | — | `oz agent run --cwd` 로 전달할 작업 디렉터리. |
| `WARP_PROXY_ENVIRONMENT` | — | `oz agent run --environment` 으로 전달할 환경 문자열. |
| `WARP_PROXY_SKILL` | — | `oz agent run --skill` 로 전달할 스킬. |
| `WARP_PROXY_MCP` | — | `oz agent run --mcp` 로 전달할 MCP 스펙 (JSON 문자열 또는 배열). |
| `WARP_PROXY_CONVERSATION_STORE` | `~/.warp-proxy/conversations.json` | response-ID → conversation-ID 매핑 저장 경로. |

---

## 문제 해결

### `/v1/models` 는 되는데 채팅 요청이 실패한다

프록시 서버는 살아 있지만 Oz CLI 백엔드가 제대로 응답하지 않는 상태다.

1. Warp 로그인 상태 확인 — Warp 터미널을 열고 점검
2. `oz dump-debug-info` 를 직접 실행해 정상 종료하는지 확인
3. 안정 별칭부터 시도: `"model": "warp-oz-cli"`

### `unsupported_cli_version` 에러

warp-proxy는 기동 시 Oz CLI 버전을 조회하고 알 수 없는 버전은 조용한 동작 회귀를 막기 위해 거부한다.

```bash
oz dump-debug-info   # 보고된 Warp 버전 확인
```

- 감지된 버전을 `WARP_PROXY_VERIFIED_WARP_VERSIONS` 에 추가하거나,
- `ALLOW_UNVERIFIED_WARP_CLI=true` 로 검사를 우회 (운영 사용은 권장하지 않음)

### Open WebUI / Continue 에 모델이 안 보인다

```bash
# 직접 확인
curl http://127.0.0.1:29113/v1/models | jq .

# 서버가 Docker 안에 있다면:
# API base URL 을 http://host.docker.internal:29113/v1 로 지정
```

### `conversation_expired` (409)

참조한 Oz 대화가 백엔드에 더 이상 없다(세션 만료 가능). `metadata.warp_previous_response_id` 를 생략하고 새 대화를 시작한다.

### Admin 상태 엔드포인트

디버깅 시 항상 이것부터 확인한다:

```bash
curl http://127.0.0.1:29113/admin/status | jq .
```

인증 모드, CLI 버전 프로브 결과, 모델 가용성, 설정된 `cwd` 를 보여준다.

---

## 프로젝트 구조

```
warp-proxy/
├── run.py                # 서버 실행 진입점 (python run.py)
├── main.py               # FastAPI 앱: 라우트 핸들러, 프로토콜 어댑터
│                         #   OpenAI ↔ Anthropic 요청/응답 변환
├── oz_bridge.py          # 핵심 브리지: 모델 해석, CLI 실행,
│                         #   NDJSON 파싱, 대화 연속
├── models.py             # Pydantic 요청/응답 스키마
│                         #   (OpenAI + Anthropic 와이어 타입)
├── config.py             # Settings 데이터클래스 — 전부 환경변수 기반
├── conversation_store.py # JSON 저장소: response_id → oz conversation_id
├── tests/                # Pytest 테스트 스위트
├── docs/
│   ├── API_CONTRACT.md        # 권위 있는 HTTP 계약 (단일 진실 공급원)
│   ├── ARCHITECTURE.md        # 설계 결정과 컴포넌트 경계
│   ├── IMPLEMENTATION_STATUS.md  # 검증된 기능 매트릭스
│   ├── USAGE.md               # 확장 curl 예시
│   ├── gjc-integration.md     # GJC 연동 가이드 (EN)
│   ├── gjc-integration.ko.md  # GJC 연동 가이드 (KO)
│   └── CLIPROXYAPI.md         # CLIProxyAPI 연동 가이드
└── pyproject.toml
```

**요청이 코드를 통과하는 흐름:**

```
HTTP 요청
  → main.py (라우트 핸들러)
    → 프로토콜 어댑터 (_anthropic_request_to_chat_request, _responses_request_to_chat_request, ...)
      → oz_bridge.OzBridge
        → _prepare_execution()   # 검증, 모델 해석, CLI 버전 확인, 연속 확인
        → oz agent run ...       # 서브프로세스 (동기) 또는 asyncio.create_subprocess_exec (스트리밍)
        → parse_ndjson_events()  # NDJSON → ParsedEvent 목록
        → aggregate_events()     # 텍스트 청크 병합, conversation_id 추출
      → 프로토콜 어댑터 (응답 직렬화)
  → HTTP 응답 (JSON 또는 SSE)
```

---

## 보안

- warp-proxy 는 **오직 `127.0.0.1` 에만 바인드**한다. 다른 주소로의 바인드는 기동 시 거부된다.
- **단일 사용자 로컬 용도**로 설계됐다. 다중 테넌트 격리는 없다.
- `session` 모드에서는 API 키 필드를 검증하지 않는다. 포트를 공유 네트워크에 노출하지 마라.
- 조용한 백엔드 전환 없음 — 지원하지 않는 CLI 버전은 명확한 에러로 거부한다.

---

## 라이선스

아직 오픈소스 라이선스가 선언되지 않았다. 이 코드를 사용하고 싶다면 먼저 이슈를 열어라.

---

<p align="center">
  <sub>warp-proxy 는 독립적인 오픈소스 프로젝트이며 Warp와 제휴하거나 보증받지 않는다.</sub>
</p>
