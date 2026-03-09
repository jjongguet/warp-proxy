# CLIProxyAPI 연동 가이드

- **Last updated:** 2026-03-09
- **대상:** CLIProxyAPI v5+ (`openai-compatibility` 지원 버전)

## 개요

CLIProxyAPI는 여러 AI CLI 도구(Gemini CLI, Claude Code, Codex 등)를 OpenAI-compatible API로 노출하는 Go 기반 프록시 게이트웨이다.
warptocli도 OpenAI-compatible API를 제공하므로, CLIProxyAPI의 `openai-compatibility` provider로 등록하면 **코드 수정 없이** 연동할 수 있다.

## 사전 조건

1. **warptocli 서버가 실행 중**이어야 한다
   ```bash
   cd /path/to/warptocli
   . .venv/bin/activate
   uvicorn main:app --host 127.0.0.1 --port 29113
   ```
2. **CLIProxyAPI가 설치**되어 있어야 한다 (기본 포트 `8317`)

## config.yaml 설정

CLIProxyAPI의 `config.yaml`에 아래 `openai-compatibility` 섹션을 추가한다.

### 최소 설정

```yaml
openai-compatibility:
  - name: "warptocli"
    base-url: "http://127.0.0.1:29113/v1"
    api-key-entries:
      - api-key: "local-dev"
    models:
      - name: "warp-oz-cli"
```

- `name` — CLIProxyAPI 내부에서 이 provider를 식별하는 이름
- `base-url` — warptocli의 API base URL (포트 `29113`)
- `api-key-entries` — warptocli는 기본 `session` 모드에서 API key를 검증하지 않으므로 아무 값이나 넣어도 된다
- `models` — `name`에 warptocli가 노출하는 모델 ID를 지정한다

### 여러 모델 노출

warptocli의 namespaced passthrough ID를 사용하면 특정 Oz 모델을 지정할 수 있다.
alias를 걸어 CLIProxyAPI 클라이언트에서 짧은 이름으로 쓸 수 있다.

```yaml
openai-compatibility:
  - name: "warptocli"
    base-url: "http://127.0.0.1:29113/v1"
    api-key-entries:
      - api-key: "local-dev"
    models:
      - name: "warp-oz-cli"
        alias: "warp"
      - name: "warp-oz-cli/claude-3.5-sonnet"
        alias: "warp-sonnet"
      - name: "warp-oz-cli/gpt-4o"
        alias: "warp-gpt4o"
```

클라이언트에서 `model: "warp-sonnet"` 으로 요청하면, CLIProxyAPI가 warptocli에 `model: "warp-oz-cli/claude-3.5-sonnet"`으로 전달한다.

### 기존 provider와 병행

CLIProxyAPI에 이미 다른 provider(Gemini, Claude 등)가 있다면, `openai-compatibility` 배열에 warptocli를 추가하면 된다.

```yaml
# 기존 설정...
port: 8317
api-keys:
  - "your-api-key"

# warptocli 추가
openai-compatibility:
  - name: "warptocli"
    base-url: "http://127.0.0.1:29113/v1"
    api-key-entries:
      - api-key: "local-dev"
    models:
      - name: "warp-oz-cli"
        alias: "warp"
```

## 확인 방법

### 1. warptocli 직접 확인

```bash
curl http://127.0.0.1:29113/v1/models | jq '.data[].id'
```

### 2. CLIProxyAPI를 통한 확인

```bash
curl http://127.0.0.1:8317/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "warp",
    "messages": [{"role": "user", "content": "Reply with READY."}]
  }'
```

`model`에 alias(`warp`)를 넣으면 CLIProxyAPI가 warptocli로 라우팅한다.

## 주의사항

- **warptocli는 로컬 전용**이다. `127.0.0.1`에서만 바인드하며, 원격 접근은 지원하지 않는다.
- CLIProxyAPI가 Docker에서 실행 중이라면 `base-url`을 `http://host.docker.internal:29113/v1`로 변경해야 한다.
- warptocli의 `stream: true` SSE 스트리밍은 CLIProxyAPI의 OpenAI-compatible 패스스루와 호환된다.
- continuation (`metadata.warp_previous_response_id`)은 warptocli 고유 기능이므로, CLIProxyAPI를 통해 이어가기를 사용하려면 클라이언트가 직접 metadata를 포함해야 한다.

## 관련 문서

- [warptocli USAGE](./USAGE.md) — 서버 기동 및 curl 예시
- [warptocli API_CONTRACT](./API_CONTRACT.md) — 전체 API 스펙
- [CLIProxyAPI OpenAI Compatibility Docs](https://help.router-for.me/configuration/provider/openai-compatibility)
