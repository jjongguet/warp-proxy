# API Contract

- **Last updated:** 2026-03-09
- **Status:** Canonical contract — cloud backend removed
- **Authority:** See [`docs/README.md`](./README.md) for the document authority chain. This file is the canonical HTTP contract.

## 1. Endpoints

### Public API
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `GET /v1/models`
- `POST /v1/messages`
- `POST /v1/messages/count_tokens`

### Operator API
- `GET /admin/status`

## 2. OpenAI-compatible endpoints

### 2.1 `POST /v1/chat/completions`

### Request subset

#### Required fields
- `model: string`
- `messages: array`

#### Optional fields

- **`stream`** (`boolean`, default `false`) — `true`로 설정하면 SSE(text/event-stream) 스트리밍 응답을 반환한다.
- **`temperature`** (`float | null`) — 샘플링 온도. Oz CLI에 `--temperature`로 전달된다.
- **`top_p`** (`float | null`) — Nucleus sampling 확률 임계값.
- **`max_tokens`** (`integer | null`) — 응답 최대 토큰 수.
- **`stop`** (`string | string[] | null`) — 생성 중단 시퀀스. 문자열 하나 또는 배열.
- **`user`** (`string | null`) — 최종 사용자 식별자. 프록시에서 로깅 용도로 사용할 수 있다.
- **`metadata`** (`object | null`) — 프록시 메타데이터. 현재 유일하게 의미 있는 키는 `warp_previous_response_id` (대화 이어가기).

#### Continuation (대화 이어가기)

`metadata.warp_previous_response_id`에 이전 응답의 `id`를 넣으면, 프록시가 내부 conversation store에서 Oz conversation id를 조회하여 `--conversation`으로 전달한다.

```json
{
  "metadata": {
    "warp_previous_response_id": "chatcmpl_..."
  }
}
```

- 프록시는 raw Oz conversation id를 클라이언트로부터 직접 받지 **않는다**.
- 존재하지 않는 `warp_previous_response_id`는 `400 invalid_conversation_reference`를 반환한다.

#### Compatibility-only fields (수신은 되지만 Oz로 전달하지 않음)

OpenAI SDK 호환성을 위해 아래 필드를 수신하되, 무시한다:

- `tools` — function calling 도구 정의
- `tool_choice` — 도구 선택 전략
- `functions` — legacy function calling (deprecated)
- `function_call` — legacy function calling 선택
- `response_format` — 응답 형식 지정 (JSON mode 등)
- `audio` — 오디오 입출력
- `parallel_tool_calls` — 병렬 도구 호출 허용 여부

이 필드에 값을 넣어도 에러가 발생하지 않지만, Oz CLI에 전달되지 않는다.
정의되지 않은 필드를 보내면 `400 unsupported_field` 에러가 반환된다 (`extra="forbid"`).

> **참고:** 비-텍스트 message content (이미지 등)는 지원하지 않는다.
### 2.2 `POST /v1/responses` (partial compatibility)

- OpenAI Responses API의 **text 중심 subset**을 제공한다.
- 내부 실행 경로는 `/v1/chat/completions`와 동일하게 Oz bridge를 사용한다.
- 요청의 `input`/`instructions`는 텍스트 메시지로 정규화되어 동일한 prompt path로 전달된다.
- `previous_response_id`가 주어지면 내부적으로 `metadata.warp_previous_response_id`로 매핑되어 continuation을 수행한다.
- `tools`, `tool_choice` 등 Responses 전용 필드는 수신하지만 Oz 실행으로 직접 전달되지는 않는다.

#### Streaming event shape

`stream=true`일 때 `text/event-stream`으로 다음 이벤트 시퀀스를 반환한다.

1. `response.created`
2. `response.in_progress`
3. `response.output_item.added`
4. `response.content_part.added`
5. one or more `response.output_text.delta`
6. `response.output_text.done`
7. `response.content_part.done`
8. `response.output_item.done`
9. `response.completed`
10. terminal `event: done`, `data: [DONE]`

현재 범위는 `output_text` 중심이며 tool-call 항목은 생성하지 않는다.
## 3. Anthropic-compatible endpoints

### `POST /v1/messages`
- Anthropic Messages API와 호환되는 입력/출력 형태를 제공한다.
- `model`은 OpenAI path와 동일하게 `warp-oz-cli` 또는 `warp-oz-cli/<oz_model_id>`를 사용한다.
- `messages`/`system`은 내부적으로 텍스트 prompt로 정규화되어 동일한 Oz 실행 경로를 사용한다.
- `stream=true`일 때 Anthropic SSE 이벤트(`message_start`, `content_block_*`, `message_delta`, `message_stop`)를 반환한다.
- mid-stream failure는 `event: error` 이벤트를 마지막으로 스트림을 종료한다.

### `POST /v1/messages/count_tokens`
- Claude Code gateway 호환을 위해 제공된다.
- 현재 Oz backend가 prompt token accounting을 직접 제공하지 않으므로, 반환값은 normalized prompt 기반의 **best-effort estimate**이다.
- 응답 형태:

```json
{
  "input_tokens": 42
}
```

### Anthropic error envelope

Anthropic endpoints (`/v1/messages*`)는 아래 형태로 에러를 반환한다.

```json
{
  "type": "error",
  "error": {
    "type": "invalid_request_error",
    "message": "Human-readable explanation"
  }
}
```

## 4. Model contract

### Stable alias
- `warp-oz-cli` — local Oz CLI backend의 기본 모델

### Namespaced passthrough IDs
- `warp-oz-cli/<oz_model_id>` — 특정 Oz 모델 지정

예: `warp-oz-cli/claude-3.5-sonnet`, `warp-oz-cli/gpt-4o`

Stable alias가 canonical이며, namespaced ID는 `oz model list --output-format json`에서 자동 검색된다.
기본적으로 curated 목록(약 21개)만 노출되며, `WARP_PROXY_LIST_ALL_MODELS=true`로 전체 목록을 볼 수 있다.

### Discovery lifecycle
- catalog starts unloaded
- first `/v1/models` or first namespaced request triggers discovery
- successful catalog is cached for process lifetime
- one refresh-on-miss is attempted before returning `unsupported_model`
- if discovery is required for a namespaced request and no successful catalog exists, return `503 model_catalog_unavailable`

## 5. Startup-level config (환경변수)

- **`WARP_PROXY_HOST`** — 바인드 주소 (기본 `127.0.0.1`, 변경 불가)
- **`WARP_PROXY_PORT`** — 포트 (기본 `29113`)
- **`WARP_PROXY_AUTH_MODE`** — `session` (기본) 또는 `api_key`
- **`WARP_API_KEY`** — `api_key` 모드일 때 필수
- **`WARP_PROXY_CWD`** — local `oz agent run`에 전달할 작업 디렉토리
- **`WARP_PROXY_ENVIRONMENT`** — local `oz agent run`에 전달할 Oz environment (`--environment`)
- **`WARP_PROXY_SKILL`** — local `oz agent run`에 전달할 Oz skill (`--skill`)
- **`WARP_PROXY_MCP`** — local `oz agent run`에 전달할 MCP 서버 스펙(JSON string 또는 JSON 배열)
- **`WARP_PROXY_CONVERSATION_STORE`** — 대화 저장 경로 (기본 `~/.warp-proxy/conversations.json`)
- **`WARP_PROXY_LIST_ALL_MODELS`** — `true`이면 curated 필터 해제, 전체 모델 노출
- **`WARP_PROXY_VERIFIED_WARP_VERSIONS`** — 허용할 Warp CLI 버전의 쉼표 구분 allowlist
- **`WARP_PROXY_COMMAND_TIMEOUT_SECONDS`** — CLI 실행 타임아웃 (기본 `120`)
- **`WARP_PROXY_MAX_CONCURRENT_REQUESTS`** — 동시에 처리할 Oz 요청 수 제한 (기본 `4`)
- **`ALLOW_UNVERIFIED_WARP_CLI`** — `true`이면 CLI 버전 검증 건너뜀

## 6. Non-streaming success response

```json
{
  "id": "chatcmpl_<generated>",
  "object": "chat.completion",
  "created": 1770000000,
  "model": "warp-oz-cli",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "<normalized assistant text>"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  }
}
```

## 7. Streaming response contract

When `stream=true`, the endpoint returns:
- HTTP `200`
- `Content-Type: text/event-stream`
- OpenAI-style SSE frames using `data: <json>\n\n`

### Streaming behavior
1. first chunk carries `choices[0].delta.role = "assistant"`
2. subsequent chunks carry `choices[0].delta.content`
3. final success chunk carries `finish_reason = "stop"`
4. final terminator is `data: [DONE]`
5. if a mid-stream error occurs after output has started, the stream emits one terminal `data: {"error": ...}` payload and closes without `[DONE]`

## 8. Error response

All non-SSE errors use:

```json
{
  "error": {
    "message": "Human-readable explanation",
    "type": "invalid_request_error",
    "param": null,
    "code": "unsupported_feature"
  }
}
```

### Status / code mapping

| Condition | HTTP | code |
|---|---:|---|
| Unsupported field | 400 | `unsupported_field` |
| Unsupported model | 400 | `unsupported_model` |
| Invalid message content | 400 | `invalid_message_content` |
| Unknown previous response id | 400 | `invalid_conversation_reference` |
| Missing/expired CLI session | 503 | `cli_session_required` |
| Unsupported CLI version | 503 | `unsupported_cli_version` |
| Model catalog unavailable | 503 | `model_catalog_unavailable` |
| Backend timeout | 504 | `backend_timeout` |
| Malformed backend output | 502 | `malformed_backend_output` |
| Backend execution failure | 502 | `backend_execution_failed` |
| Conversation store corrupt | 500 | `conversation_store_corrupt` |
| Conversation store unavailable | 500 | `conversation_store_unavailable` |
| Conversation expired backend-side | 409 | `conversation_expired` |

## 9. `/v1/models`

### Response shape

```json
{
  "object": "list",
  "data": [
    {"id": "warp-oz-cli", "object": "model", "owned_by": "warp-proxy"},
    {"id": "warp-oz-cli/claude-3.5-sonnet", "object": "model", "owned_by": "warp-proxy"}
  ]
}
```

Stable alias(`warp-oz-cli`)가 항상 첫 번째.
Curated passthrough ID들이 이어서 나온다 (기본 약 21개).
`WARP_PROXY_LIST_ALL_MODELS=true` 설정 시 전체 discovered 모델이 노출된다.

## 10. `/admin/status`

운영자용 헬스체크 엔드포인트. 모델 alias의 가용성(CLI 존재 여부)과 Warp CLI 버전 검증 상태를 반환한다.
dynamic model discovery 결과는 포함하지 않는다 (alias-only).
