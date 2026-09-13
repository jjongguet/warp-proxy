# GJC(가재코드) 연동 가이드

**[English](./gjc-integration.md)** | **[한국어](./gjc-integration.ko.md)**

**GJC(가재코드)** — 로컬 코딩 에이전트 하니스 — 를 warp-proxy에 연결하여 모든 모델 역할(default, executor, planner, critic, architect)을 Warp Oz로 실행하는 방법을 다룬다.

GJC의 커스텀 프로바이더는 HTTP(OpenAI 호환 또는 Anthropic 호환)로 통신한다. warp-proxy가 HTTP를 `oz agent run` 서브프로세스 호출로 변환하는 서버 역할을 맡아, GJC 입장에서 Oz는 일반 API 프로바이더처럼 보인다.

---

## 1. 사전 조건

| 요구 사항 | 확인 방법 |
|---|---|
| Warp 터미널 설치 및 로그인 | `oz whoami` 가 정상 종료 |
| warp-proxy 클론 및 의존성 설치 | `cd warp-proxy && uv sync --extra dev` |
| GJC 설치 | `gjc --version` |

## 2. 프록시 기동 (수동)

GJC가 프록시를 대신 띄워주지 않는다. Oz 기반 모델을 쓰기 전에 직접 실행한다:

```bash
cd /path/to/warp-proxy
python run.py                 # 포그라운드; 종료는 Ctrl+C
# 또는: uv run python run.py
```

`python run.py` 는 `127.0.0.1:29113` 에서 수신하며,
`WARP_PROXY_IGNORE_UNSUPPORTED_FIELDS=true` 가 기본 적용되어 GJC의 프로브 요청
(`stream_options`, `max_completion_tokens`)이 400으로 거부되지 않는다.

확인:

```bash
curl -s http://127.0.0.1:29113/v1/models | jq '.data[].id'
```

## 3. GJC에 프로바이더 등록

`~/.gjc/agent/models.yml` 의 `providers:` 에 추가:

```yaml
providers:
  warp-oz:
    baseUrl: http://127.0.0.1:29113/v1
    api: openai-completions
    auth: none
    discovery:
      type: openai-models-list
```

GJC가 모델을 인식하는지 확인:

```bash
gjc models | grep warp-oz
```

> **캐시 주의:** GJC는 프로바이더 디스커버리 결과를
> `~/.gjc/agent/models.db` (`model_cache` 테이블)에 캐시한다. 새로 큐레이션된
> 모델이 보이지 않으면 해당 프로바이더 행을 삭제하고 프록시가 떠 있는 상태에서
> `gjc models` 를 다시 실행한다:
> `sqlite3 ~/.gjc/agent/models.db "DELETE FROM model_cache WHERE provider_id='warp-oz';"`

## 4. 모델 프리셋 만들기

프리셋은 GJC 역할을 모델에 매핑한다. 예시 — 현재 라인업으로 강한 모델/저렴한 모델을 분배:

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

모델 ID는 `GET /v1/models` (큐레이션 목록) 또는 `oz model list --output-format json` (전체 카탈로그)에서 확인한다.

## 5. 프리셋 엔드투엔드 검증

```bash
# 프록시 기동 상태에서:
gjc --mpreset oz-warp --no-session -p 'Reply with exactly: READY'
```

기대 결과: `READY` 출력, 프록시 로그에 요청 도착 기록.

> **프로토콜 참고:** GJC는 `claude-*` 계열 모델 ID에 대해 Anthropic 와이어
> 포맷을 자동 선택하므로 해당 요청은 `POST /v1/messages` 로 들어오고, 나머지
> 모델은 `POST /v1/chat/completions` 를 사용한다. warp-proxy는 둘 다 처리하므로
> 추가 설정이 필요 없다.

## 6. 문제 해결

| 증상 | 해결 |
|---|---|
| `gjc models` 에 `warp-oz` 섹션이 없음 | 프록시 미기동 또는 프로브 거부 — §2 확인 후 디스커버리 캐시 정리(§3 주석) |
| 요청이 connection refused 로 실패 | 프록시 기동: `python run.py` |
| 기동 시 `unsupported_cli_version` | Warp 버전이 허용 목록보다 최신 — `WARP_PROXY_VERIFIED_WARP_VERSIONS` 설정 또는 warp-proxy 업데이트 |
| 서브에이전트에 프리셋 역할이 안 적용됨 | `~/.gjc/agent/config.yml` 의 `task.agentModelOverrides` 가 서브에이전트 역할에 우선한다 — 프리셋이 전 역할을 지배하게 하려면 해당 항목 제거 |
