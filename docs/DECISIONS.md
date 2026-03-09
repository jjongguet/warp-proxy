# Decisions / ADR Log

- **Last updated:** 2026-03-09
- **Purpose:** 현재 지원되는 아키텍처/제품 방향에 대한 핵심 의사결정을 정리한다.
- **Note:** 제거된 cloud backend 관련 역사적 맥락은 `docs/CLOUD_REMOVED.md`와 `docs/EVIDENCE.md`에 남긴다.

## ADR-001 — Primary backend is the Oz CLI, not a separate REST control plane
- **Status:** Accepted
- **Date:** 2026-03-08

### Decision
기본 실행 경로는 `oz` CLI subprocess이다.

### Why
- 사용자의 핵심 요구가 "이미 로그인된 Warp/Oz 세션을 재사용하는 로컬 HTTP endpoint"에 가깝다.
- 로컬 개발 워크플로우에서는 CLI가 가장 직접적인 integration surface다.
- stdout/stderr/exit code를 바로 다루는 쪽이 별도 제어면을 가정하는 것보다 단순하다.

### Consequence
- subprocess lifecycle, timeout, output parsing을 직접 관리해야 한다.
- CLI의 실제 출력 계약이 프록시 설계의 중요한 근거가 된다.

## ADR-002 — Product shape is a single-user localhost proxy
- **Status:** Accepted
- **Date:** 2026-03-08

### Decision
제품은 `127.0.0.1`에 바인딩되는 로컬 단일 사용자 프록시로 유지한다.

### Why
- 로그인된 세션 권한을 재노출하므로 네트워크 경계를 좁게 가져가야 한다.
- 사용자의 핵심 목적은 hosted service가 아니라 local companion proxy다.

### Consequence
- `WARP_PROXY_HOST`는 사실상 고정값으로 취급된다.
- 멀티테넌트/원격 호스팅은 현재 scope 밖이다.

## ADR-003 — Default execution path is `oz agent run`
- **Status:** Accepted
- **Date:** 2026-03-08

### Decision
기본 모델 alias `warp-oz-cli`는 `oz agent run`으로 라우팅한다.

### Why
- local development/current-directory semantics와 가장 잘 맞는다.
- `--cwd`, `--environment`, `--skill`, `--mcp` 등 현재 구현이 쓰는 인자 구성이 local path와 잘 맞는다.

### Consequence
- 현재 public surface는 local backend 중심으로 설계된다.
- backend normalization 기준은 local `run`의 NDJSON 출력 계약이 된다.

## ADR-004 — Cloud backend is not part of the current supported surface
- **Status:** Accepted
- **Date:** 2026-03-09

### Decision
`oz agent run-cloud`와 `warp-oz-cli-cloud`는 현재 지원 표면에서 제거한다.

### Why
- local-only companion proxy라는 핵심 목적에 비해 복잡도를 크게 늘린다.
- historical verification 과정에서 `run-cloud`는 local `run`과 다른 출력 계약을 보였다.
- 현재 코드와 테스트는 local path를 기준으로 더 명확하고 안정적인 사용자 경험을 제공한다.

### Consequence
- current truth는 local-only contract다.
- historical cloud evidence는 삭제하지 않고 참고 문서로 남긴다.

## ADR-005 — Session auth is the default; API-key auth is explicit opt-in
- **Status:** Accepted
- **Date:** 2026-03-08

### Decision
기본 인증 모드는 session reuse이고, API-key 모드는 `WARP_PROXY_AUTH_MODE=api_key`일 때만 활성화한다.

### Why
- 사용자 요구와 가장 잘 맞는다.
- local Warp/Oz 로그인 상태를 그대로 활용할 수 있다.
- headless/remote 스타일 auth는 보조 경로로 두는 편이 명확하다.

### Consequence
- `WARP_API_KEY`는 `api_key` 모드에서만 필수다.
- silent fallback은 허용하지 않는다.

## ADR-006 — Public API surface stays intentionally narrow
- **Status:** Accepted
- **Date:** 2026-03-08

### Decision
현재 공개 API는 `GET /v1/models`, `POST /v1/chat/completions`, `GET /admin/status`로 제한한다.

### Why
- 가장 널리 호환되는 OpenAI-compatible surface를 우선 제공하기 위함이다.
- scope를 좁혀 구현/검증/문서화 일관성을 유지할 수 있다.

### Consequence
- Responses API, Anthropic-compatible surface, multimodal, tool execution orchestration은 현재 범위 밖이다.
- `/admin/status`는 OpenAI 호환 표면이 아니라 운영 진단용이다.

## ADR-007 — Machine-readable JSON/NDJSON is the canonical adapter path
- **Status:** Accepted
- **Date:** 2026-03-08

### Decision
현재 구현은 `oz agent run --output-format json`을 기본 출력 계약으로 사용한다.

### Why
- fixture 기반 테스트가 쉬워진다.
- malformed output을 더 명확하게 탐지할 수 있다.
- SSE chunk 생성과 conversation id 포착이 단순해진다.

### Consequence
- `type=agent` text extraction이 핵심 파싱 규칙이 된다.
- plain text stdout 연구 결과는 참고 자료로 유지하되, 현재 구현의 기본 계약은 JSON/NDJSON이다.

## ADR-008 — Streaming uses OpenAI-style SSE conventions
- **Status:** Accepted
- **Date:** 2026-03-09

### Decision
`stream=true`는 OpenAI-style SSE chunking으로 제공한다.

### Why
- 기존 OpenAI-compatible client와 가장 잘 맞는다.
- 역할 chunk / content chunk / stop chunk / `[DONE]` sentinel 패턴이 익숙하고 검증 가능하다.

### Consequence
- mid-stream error는 이미 출력이 시작된 경우 terminal error payload로 닫는다.
- streaming path도 non-streaming과 동일한 validation/model-resolution/version-check 경로를 공유한다.

## ADR-009 — Continuation is explicit and backed by a local conversation store
- **Status:** Accepted
- **Date:** 2026-03-09

### Decision
multi-turn continuation은 `metadata.warp_previous_response_id`를 통해서만 명시적으로 허용한다.

### Why
- 기본 요청은 stateless하게 유지하면서도 continuation은 안정적으로 제공할 수 있다.
- raw Oz conversation id를 외부 계약에 직접 노출하지 않아도 된다.

### Consequence
- `ConversationStore`가 response id ↔ conversation id 매핑을 영속화한다.
- unknown/expired/corrupt store 상태는 명시적인 4xx/5xx로 변환된다.

## ADR-010 — Public model surface uses one stable alias plus namespaced passthrough IDs
- **Status:** Accepted
- **Date:** 2026-03-09

### Decision
기본 모델은 `warp-oz-cli` 하나이며, 선택적으로 `warp-oz-cli/<oz_model_id>` passthrough를 지원한다.

### Why
- stable alias는 사용자 onboarding을 단순하게 만든다.
- passthrough는 Oz 모델 catalog의 실제 capability를 활용할 수 있게 한다.
- `/v1/models`를 너무 넓은 runtime contract로 만들지 않으면서 유연성을 유지할 수 있다.

### Consequence
- curated model ids를 기본 노출하고, 필요 시 전체 discovery를 켤 수 있다.
- namespaced 요청은 catalog discovery/cache/refresh-on-miss 로직에 의존한다.

## ADR-011 — Version detection uses `oz dump-debug-info` with an allowlist policy
- **Status:** Accepted
- **Date:** 2026-03-08

### Decision
Warp CLI 버전 검증은 `oz dump-debug-info`를 기준으로 한다.

### Why
- 이 환경에서는 `oz version` / `oz --version`이 일반적인 버전 명령처럼 동작하지 않는다.
- `dump-debug-info`의 `Warp version:` 라인이 가장 안정적인 probe surface였다.

### Consequence
- broad semver 가정 대신 verified version allowlist를 사용한다.
- mismatch는 `503 unsupported_cli_version`으로 fail closed 한다.

## ADR-012 — `/admin/status` remains an alias-only operator endpoint
- **Status:** Accepted
- **Date:** 2026-03-09

### Decision
`/admin/status`는 stable alias availability와 version-probe 상태를 보여주는 운영 진단용 endpoint로 유지한다.

### Why
- `/v1/models`의 dynamic discovery 결과까지 운영 엔드포인트에 섞으면 상태 해석이 복잡해진다.
- alias-level health와 current configuration 확인이 운영 관점에서 더 유용하다.

### Consequence
- `/admin/status`는 discovered namespaced 모델 전체를 반영하지 않는다.
- client-visible 모델 카탈로그와 operator diagnostics는 의도적으로 분리된다.
