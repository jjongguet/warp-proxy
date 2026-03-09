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

- **`stream`** (`boolean`, default `false`) — When `true`, returns an SSE (`text/event-stream`) streaming response.
- **`temperature`** (`float | null`) — Sampling temperature. Passed to the Oz CLI as `--temperature`.
- **`top_p`** (`float | null`) — Nucleus sampling probability threshold.
- **`max_tokens`** (`integer | null`) — Maximum number of tokens in the response.
- **`stop`** (`string | string[] | null`) — Stop sequences for generation. A single string or an array.
- **`user`** (`string | null`) — End-user identifier. May be used by the proxy for logging.
- **`metadata`** (`object | null`) — Proxy metadata. The only meaningful key is `warp_previous_response_id` (conversation continuation).

#### Continuation

Set `metadata.warp_previous_response_id` to the `id` of a previous response. The proxy looks up the Oz conversation id in its internal conversation store and forwards it via `--conversation`.

```json
{
  "metadata": {
    "warp_previous_response_id": "chatcmpl_..."
  }
}
```

- The proxy does **not** accept raw Oz conversation ids directly from the client.
- An unknown `warp_previous_response_id` returns `400 invalid_conversation_reference`.

#### Compatibility-only fields (received but not forwarded to Oz)

The following fields are accepted for OpenAI SDK compatibility but ignored:

- `tools` — function calling tool definitions
- `tool_choice` — tool selection strategy
- `functions` — legacy function calling (deprecated)
- `function_call` — legacy function calling selection
- `response_format` — response format specification (JSON mode, etc.)
- `audio` — audio input/output
- `parallel_tool_calls` — parallel tool call permission

Setting these fields does not produce an error, but they are not forwarded to the Oz CLI.
Sending any undefined field will return a `400 unsupported_field` error (`extra="forbid"`).

> **Note:** Non-text message content (images, etc.) is not supported.

### 2.2 `POST /v1/responses` (partial compatibility)

- Provides a **text-focused subset** of the OpenAI Responses API.
- Uses the same Oz bridge execution path as `/v1/chat/completions` internally.
- The request's `input`/`instructions` are normalized into text messages and sent through the same prompt path.
- When `previous_response_id` is provided, it is mapped internally to `metadata.warp_previous_response_id` for continuation.
- Responses-specific fields such as `tools` and `tool_choice` are accepted but not forwarded to Oz execution directly.

#### Streaming event shape

When `stream=true`, the endpoint returns `text/event-stream` with the following event sequence:

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

The current scope is `output_text`-focused; tool-call items are not generated.

## 3. Anthropic-compatible endpoints

### `POST /v1/messages`
- Provides Anthropic Messages API-compatible input/output.
- `model` uses the same identifiers as the OpenAI path: `warp-oz-cli` or `warp-oz-cli/<oz_model_id>`.
- `messages`/`system` are normalized internally into a text prompt and sent through the same Oz execution path.
- When `stream=true`, returns Anthropic SSE events (`message_start`, `content_block_*`, `message_delta`, `message_stop`).
- Mid-stream failures terminate the stream with an `event: error` event.

### `POST /v1/messages/count_tokens`
- Provided for Claude Code gateway compatibility.
- Because the Oz backend does not directly provide prompt token accounting, the returned value is a **best-effort estimate** based on the normalized prompt.
- Response shape:

```json
{
  "input_tokens": 42
}
```

### Anthropic error envelope

Anthropic endpoints (`/v1/messages*`) return errors in the following format:

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
- `warp-oz-cli` — default model for the local Oz CLI backend

### Namespaced passthrough IDs
- `warp-oz-cli/<oz_model_id>` — target a specific Oz model

e.g., `warp-oz-cli/claude-3.5-sonnet`, `warp-oz-cli/gpt-4o`

The stable alias is canonical. Namespaced IDs are auto-discovered from `oz model list --output-format json`.
By default only the curated list (~21 models) is exposed. Set `WARP_PROXY_LIST_ALL_MODELS=true` to expose the full list.

### Discovery lifecycle
- catalog starts unloaded
- first `/v1/models` or first namespaced request triggers discovery
- successful catalog is cached for process lifetime
- one refresh-on-miss is attempted before returning `unsupported_model`
- if discovery is required for a namespaced request and no successful catalog exists, return `503 model_catalog_unavailable`

## 5. Startup-level config (environment variables)

- **`WARP_PROXY_HOST`** — bind address (default `127.0.0.1`, cannot be changed)
- **`WARP_PROXY_PORT`** — port (default `29113`)
- **`WARP_PROXY_AUTH_MODE`** — `session` (default) or `api_key`
- **`WARP_API_KEY`** — required when `auth_mode=api_key`
- **`WARP_PROXY_CWD`** — working directory forwarded to local `oz agent run`
- **`WARP_PROXY_ENVIRONMENT`** — Oz environment forwarded to local `oz agent run` (`--environment`)
- **`WARP_PROXY_SKILL`** — Oz skill forwarded to local `oz agent run` (`--skill`)
- **`WARP_PROXY_MCP`** — MCP server spec forwarded to local `oz agent run` (JSON string or JSON array)
- **`WARP_PROXY_CONVERSATION_STORE`** — conversation store path (default `~/.warp-proxy/conversations.json`)
- **`WARP_PROXY_LIST_ALL_MODELS`** — when `true`, removes curated filter and exposes all discovered models
- **`WARP_PROXY_VERIFIED_WARP_VERSIONS`** — comma-separated allowlist of permitted Warp CLI versions
- **`WARP_PROXY_COMMAND_TIMEOUT_SECONDS`** — CLI execution timeout (default `120`)
- **`WARP_PROXY_MAX_CONCURRENT_REQUESTS`** — concurrency limit for simultaneous Oz requests (default `4`)
- **`ALLOW_UNVERIFIED_WARP_CLI`** — when `true`, skips CLI version validation

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

The stable alias (`warp-oz-cli`) is always first.
Curated passthrough IDs follow (default ~21).
Set `WARP_PROXY_LIST_ALL_MODELS=true` to expose all discovered models.

## 10. `/admin/status`

Operator health-check endpoint. Returns the availability (CLI presence) of model aliases and the Warp CLI version validation status.
Dynamic model discovery results are not included (alias-only).
