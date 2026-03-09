# PRD — Warp Logged-In CLI Proxy

- **Status:** Historical draft / initial planning artifact
- **Last updated:** 2026-03-09
- **Project type:** Greenfield
- **Current implementation note:** 이 문서는 2026-03-08 시점의 초기 기획 초안이다. 현재 구현은 local-only이며 cloud backend는 제거되었다. 현재 truth는 `docs/API_CONTRACT.md`, `docs/IMPLEMENTATION_STATUS.md`, `docs/CLOUD_REMOVED.md`를 우선한다.

## 1. Problem

Warp/Oz는 공식 CLI와 API를 제공하지만, OpenAI-compatible 클라이언트(예: Open WebUI, Continue, 커스텀 스크립트)에서 바로 쓰기에는 인터페이스가 다릅니다.

특히 이 프로젝트의 핵심 요구는 다음과 같습니다.

1. **별도 API key 발급을 강제하지 않고**
2. **이미 로그인된 Warp Plan / Oz CLI 세션을 활용**하여
3. Oz agent 능력을 **로컬 HTTP endpoint**로 노출하고 싶다.

## 2. Product statement

이 프로젝트는 **이미 로그인된 Oz CLI를 백엔드로 사용**하는 로컬 프록시 서버를 만든다.
외부에서는 OpenAI-compatible HTTP API처럼 호출할 수 있어야 한다.

## 3. Target user

### Primary user
- Warp를 이미 사용 중인 개발자
- 자신의 로컬 머신에서 Oz agent를 재사용하고 싶은 사용자
- OpenAI-compatible 클라이언트와 Oz를 연결하고 싶은 사용자

### Not the target in v1
- 멀티테넌트 SaaS 운영자
- shared hosted API 서비스
- 완전한 server-side headless Oz platform 대체 목적

## 4. Jobs to be done

사용자는 다음을 할 수 있어야 한다.

1. 로컬에서 프록시 서버를 띄운다.
2. OpenAI format으로 `POST /v1/chat/completions`를 호출한다.
3. 프록시가 내부적으로 `oz agent run`을 실행한다.
4. 결과를 assistant text로 받아 기존 OpenAI-compatible 툴에서 활용한다.

## 5. Scope

## In scope for v1

- 로컬 단일 사용자용 프록시
- 기본 바인드: `127.0.0.1`
- `POST /v1/chat/completions`
- `GET /v1/models`
- 기본 백엔드: `oz agent run`
- 선택적 cloud backend: `oz agent run-cloud`
- 기본 인증 모드: **logged-in session reuse**
- 선택적 API-key mode: process-level opt-in only
- 전체 `messages`를 flatten해서 CLI prompt로 전달
- non-streaming 기본 동작
- OpenAI-style success/error envelope 반환

## Explicitly out of scope for v1

- 멀티테넌트/원격 호스팅 서비스
- Warp desktop 내부 비공개 프로토콜 reverse engineering
- Anthropic-compatible surface
- OpenAI Responses API
- 완전 자동 conversation persistence
- per-request backend/auth override
- runtime-dependent dynamic API shape

## 6. Key product requirements

### Functional requirements

1. 프록시는 OpenAI-compatible `chat.completion` 응답을 반환해야 한다.
2. 기본 model alias `warp-oz-cli`는 `oz agent run`으로 라우팅되어야 한다.
3. `warp-oz-cli-cloud`는 cloud mode가 활성화된 경우에만 `oz agent run-cloud`로 라우팅되어야 한다.
4. 로그인 세션이 없거나 만료되면 자동 fallback 없이 명확한 setup guidance를 반환해야 한다.
5. unsupported feature는 OpenAI-style error object로 반환해야 한다.
6. `/v1/models`는 최소한 안정적인 모델 surface를 제공해야 한다.

### Non-functional requirements

1. 로컬 전용, 단일 사용자 안전성을 우선한다.
2. 요청 실패가 opaque 500이 아니라 설명 가능한 4xx/5xx로 분류되어야 한다.
3. CLI 버전 drift를 감지할 수 있어야 한다.
4. silent backend switching이 없어야 한다.
5. 구현은 테스트하기 쉬운 subprocess adapter 구조여야 한다.

## 7. Current recommended v1 shape

### Chosen product shape

```text
OpenAI-compatible client
  -> local FastAPI proxy
  -> oz CLI subprocess
  -> authenticated local Warp/Oz session
```

### Backend modes

- **Default**: `oz agent run`
- **Opt-in**: `oz agent run-cloud`
- **Opt-in auth fallback**: `WARP_PROXY_AUTH_MODE=api_key`

### Public API

- `POST /v1/chat/completions`
- `GET /v1/models`

## 8. Capabilities discovered during research

다음 항목은 **가능성이 확인되었거나 근거가 강함**:

- CLI stdout이 프록시의 주요 응답 표면이 될 수 있음
- `--conversation <ID>` 기반 멀티턴 가능성 존재
- `oz model list --output-format json`로 모델 목록 조회 가능
- CLI는 interactive login과 API key 둘 다 지원함
- `oz agent run`과 `oz agent run-cloud`는 역할이 다르며, cloud mode에는 `--cwd`가 없음

이 중 일부는 v1에 바로 넣지 않고 후속 단계로 미룹니다.

## 9. Risks and constraints

### Product / UX risks
- Oz는 일반 챗봇보다 오래 걸릴 수 있다.
- stdout 형식이 항상 순수 assistant text라는 보장은 실제 fixture 검증이 필요하다.
- `/v1/models`를 정적으로 둘지 동적으로 둘지 tension이 있다.

### Technical risks
- subprocess lifecycle / timeout 관리
- CLI 버전 변화
- `run-cloud`와 `cwd`의 구조적 불일치
- streaming flush semantics 미검증

### Security risks
- 로그인된 세션 권한을 재노출하는 구조이므로 localhost-only 기본값이 중요하다.
- API-key fallback은 명시적 opt-in이어야 한다.

## 10. Success criteria

v1은 다음을 만족하면 성공으로 본다.

1. 로컬 프록시가 뜬다.
2. `POST /v1/chat/completions`가 `warp-oz-cli` 모델로 성공 응답을 반환한다.
3. 로그인 세션 부재/만료 시 명확한 `503` setup error를 반환한다.
4. `/v1/models`가 안정적인 모델 surface를 제공한다.
5. 기본 경로에서 silent fallback이 발생하지 않는다.
6. 최소 1개의 실제 smoke test에서 로컬 Oz CLI와 end-to-end로 동작한다.

## 11. Roadmap

### Phase 1
- Non-streaming local proxy
- `warp-oz-cli` default path
- stable OpenAI-compatible response envelope

### Phase 1.1
- `warp-oz-cli-cloud` opt-in path
- improved diagnostics / admin endpoint
- dynamic capability notes in docs

### Phase 2
- streaming feasibility validation
- optional conversation mapping
- optional Responses API support
