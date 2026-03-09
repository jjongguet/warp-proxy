# CLIProxyAPI 연동 가이드

- **Last updated:** 2026-03-09
- **대상:** CLIProxyAPI v5+ (`openai-compatibility` / `claude-api-key` 지원 버전)
- **Applies to:** local-only `warp-proxy`를 CLIProxyAPI의 upstream provider로 붙이는 구성

## 개요

CLIProxyAPI는 여러 AI CLI 도구(Gemini CLI, Claude Code, Codex 등)를 OpenAI/Anthropic compatible API로 노출하는 Go 기반 프록시 게이트웨이다.
warp-proxy는 **OpenAI-compatible** (`/v1/chat/completions`) 및 **Anthropic-compatible** (`/v1/messages`) API를 모두 제공하므로, CLIProxyAPI에 두 가지 방식으로 등록할 수 있다.

## 사전 조건

1. **warp-proxy 서버가 실행 중**이어야 한다
   ```bash
   # uv 방식 (권장)
   cd /path/to/warp-proxy
   uv run uvicorn main:app --host 127.0.0.1 --port 29113

   # 또는 venv 방식
   . .venv/bin/activate
   uvicorn main:app --host 127.0.0.1 --port 29113
   ```
2. **CLIProxyAPI가 설치**되어 있어야 한다 (기본 포트 `8317`)

---

## 방법 1: OpenAI-compatible (`openai-compatibility`)

CLIProxyAPI의 `config.yaml`에 `openai-compatibility` 섹션을 추가한다.
`/v1/chat/completions` 경로를 사용하며, Codex CLI / OpenCode / Continue 등 OpenAI-style 클라이언트와 연결할 때 적합하다.

### 최소 설정

```yaml
openai-compatibility:
  - name: "warp-proxy"
    base-url: "http://127.0.0.1:29113/v1"
    api-key-entries:
      - api-key: "local-dev"  # session 모드에서는 아무 값이나 가능
    models:
      - name: "warp-oz-cli"
```

### 여러 모델 + alias

warp-proxy의 namespaced passthrough ID(`warp-oz-cli/<oz_model_id>`)를 사용하면 특정 Oz 모델을 지정할 수 있다.
실제 노출 모델 목록은 `GET /v1/models`로 확인한다.

```yaml
openai-compatibility:
  - name: "warp-proxy"
    base-url: "http://127.0.0.1:29113/v1"
    api-key-entries:
      - api-key: "local-dev"
    models:
      - name: "warp-oz-cli"
        alias: "warp"
      - name: "warp-oz-cli/auto"
        alias: "warp-auto"
      - name: "warp-oz-cli/claude-4-6-sonnet-max"
        alias: "warp-sonnet"
      - name: "warp-oz-cli/gpt-5-4-high"
        alias: "warp-gpt5"
```

### 확인

```bash
curl http://127.0.0.1:8317/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{"model": "warp", "messages": [{"role": "user", "content": "Reply with READY."}]}'
```

---

## 방법 2: Anthropic-compatible (`claude-api-key` + `base-url`)

CLIProxyAPI의 `claude-api-key` 섹션은 `base-url`을 커스텀으로 지정할 수 있다.
warp-proxy가 `/v1/messages` Anthropic API를 지원하므로, Claude Code 등 Anthropic-style 클라이언트와 연결할 때 이 방식을 사용한다.

```yaml
claude-api-key:
  - api-key: "local-dev"          # session 모드에서는 아무 값이나 가능
    base-url: "http://127.0.0.1:29113"  # /v1/messages 는 CLIProxyAPI가 자동으로 붙임
    models:
      - name: "warp-oz-cli"
        alias: "warp-claude"
      - name: "warp-oz-cli/auto"
        alias: "warp-auto"
```

### 확인

```bash
curl http://127.0.0.1:8317/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "warp-claude",
    "max_tokens": 64,
    "messages": [{"role": "user", "content": "Reply with READY."}]
  }'
```

---

## 두 방식 비교

| | `openai-compatibility` | `claude-api-key` + base-url |
|---|---|---|
| warp-proxy 경로 | `/v1/chat/completions` | `/v1/messages` |
| 주 대상 클라이언트 | Codex CLI, OpenCode, Continue 등 | Claude Code |
| 스트리밍 포맷 | OpenAI SSE | Anthropic SSE |

---

## 기존 provider와 병행

```yaml
port: 8317
api-keys:
  - "your-api-key"

# OpenAI-compatible 경로로 warp-proxy 추가
openai-compatibility:
  - name: "warp-proxy"
    base-url: "http://127.0.0.1:29113/v1"
    api-key-entries:
      - api-key: "local-dev"
    models:
      - name: "warp-oz-cli"
        alias: "warp"

# Anthropic-compatible 경로로 warp-proxy 추가 (선택)
claude-api-key:
  - api-key: "local-dev"
    base-url: "http://127.0.0.1:29113"
    models:
      - name: "warp-oz-cli"
        alias: "warp-claude"
```

---

## 주의사항

- **warp-proxy는 로컬 전용**이다. `127.0.0.1`에서만 바인드하며, 원격 접근은 지원하지 않는다.
- CLIProxyAPI가 Docker에서 실행 중이라면 `base-url`을 `http://host.docker.internal:29113/v1` (OpenAI) 또는 `http://host.docker.internal:29113` (Anthropic)으로 변경해야 한다.
- continuation (`metadata.warp_previous_response_id`)은 warp-proxy 고유 기능이므로, CLIProxyAPI를 통해 이어가기를 사용하려면 클라이언트가 직접 metadata를 포함해야 한다.

## 관련 문서

- [warp-proxy USAGE](./USAGE.md) — 서버 기동 및 curl 예시
- [warp-proxy API_CONTRACT](./API_CONTRACT.md) — 전체 API 스펙
- [CLIProxyAPI OpenAI Compatibility Docs](https://help.router-for.me/configuration/provider/openai-compatibility)
