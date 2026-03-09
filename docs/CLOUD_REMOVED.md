# Cloud Backend 제거 안내

- **제거일:** 2026-03-09
- **이유:** `oz agent run-cloud`는 CLI에 존재하지만, warptocli에서 실질적으로 활용되지 않음. cloud 모드를 사용하려면 `WARP_PROXY_ENABLE_CLOUD=true` + `WARP_PROXY_ENVIRONMENT` 설정이 필요하며, 대부분의 사용자에게는 불필요한 복잡성만 추가함.

## 제거된 항목
- `warp-oz-cli-cloud` 모델 alias 및 관련 라우팅
- `WARP_PROXY_ENABLE_CLOUD` 환경변수
- `oz agent run-cloud` → `oz run get` polling 로직
- cloud launch/summary output 파싱 (`parse_cloud_launch_output`, `parse_cloud_summary_output`)
- cloud 관련 테스트 (unit + smoke)
- 문서 내 cloud 섹션

## 복구 방법
cloud 지원이 다시 필요하면, git history에서 아래 파일들의 이전 버전을 참고:
- `oz_bridge.py` — `CLOUD_MODEL_ALIAS`, `_execute_cloud_chat_completion`, `_prepare_cloud_stream`, `_finalize_cloud_run`, `_poll_cloud_run_status_sync`, `parse_cloud_launch_output`, `parse_cloud_summary_output`
- `config.py` — `enable_cloud` 필드
- `models.py` — `cloud_enabled` in `AdminStatusResponse`
- `tests/test_api.py` — cloud 관련 테스트 케이스
- `tests/smoke/test_live_oz.py` — `test_live_cloud_chat_completion_smoke`
