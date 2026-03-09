"""warp-proxy 서버 설정.

환경변수에서 Settings를 생성하고, 값 검증을 수행한다.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Literal

# 검증 완료된 Warp CLI 버전. 이 버전 외에는 기본적으로 거부한다.
SUPPORTED_WARP_VERSION = "v0.2026.03.04.08.20.stable_02"
DEFAULT_APP_VERSION = "0.1.0"
DEFAULT_CONVERSATION_STORE = Path.home() / ".warp-proxy" / "conversations.json"


def get_app_version() -> str:
    """설치된 패키지 메타데이터에서 버전을 읽고, 없으면 기본값 반환."""
    try:
        return metadata.version("warp-proxy")
    except metadata.PackageNotFoundError:
        return DEFAULT_APP_VERSION


@dataclass(slots=True)
class Settings:
    """서버 런타임 설정. 환경변수 또는 직접 생성으로 초기화한다."""

    host: str = "127.0.0.1"
    port: int = 29113
    auth_mode: Literal["session", "api_key"] = "session"
    list_all_models: bool = False
    warp_api_key: str | None = None
    allow_unverified_warp_cli: bool = False
    verified_warp_versions: tuple[str, ...] = field(default_factory=lambda: (SUPPORTED_WARP_VERSION,))
    command_timeout_seconds: float = 120.0
    max_concurrent_requests: int = 4
    cwd: str | None = None
    environment: str | None = None
    skill: str | None = None
    mcp: tuple[str, ...] = field(default_factory=tuple)
    conversation_store_path: str = str(DEFAULT_CONVERSATION_STORE)
    app_version: str = field(default_factory=get_app_version)

    def __post_init__(self) -> None:  # noqa: C901 — 설정값 검증 로직이 집중되어 있어 길다
        if self.host != "127.0.0.1":
            raise ValueError("warp-proxy must bind to 127.0.0.1 by default")
        if self.auth_mode not in {"session", "api_key"}:
            raise ValueError("WARP_PROXY_AUTH_MODE must be either 'session' or 'api_key'")
        if self.auth_mode == "api_key" and not self.warp_api_key:
            raise ValueError("WARP_API_KEY is required when WARP_PROXY_AUTH_MODE=api_key")
        if self.command_timeout_seconds <= 0:
            raise ValueError("WARP_PROXY_COMMAND_TIMEOUT_SECONDS must be positive")
        if self.max_concurrent_requests < 1:
            raise ValueError("WARP_PROXY_MAX_CONCURRENT_REQUESTS must be at least 1")
        if self.cwd:
            self.cwd = _resolve_existing_dir(self.cwd, "WARP_PROXY_CWD")
        if self.environment is not None and not self.environment.strip():
            raise ValueError("WARP_PROXY_ENVIRONMENT must be a non-empty string when provided")
        if self.skill is not None and not self.skill.strip():
            raise ValueError("WARP_PROXY_SKILL must be a non-empty string when provided")
        self.environment = self.environment.strip() if self.environment else None
        self.skill = self.skill.strip() if self.skill else None
        for spec in self.mcp:
            if not isinstance(spec, str) or not spec.strip():
                raise ValueError("WARP_PROXY_MCP must contain only non-empty strings")
        self.mcp = tuple(spec.strip() for spec in self.mcp)
        self.conversation_store_path = str(Path(self.conversation_store_path).expanduser().resolve())

    @classmethod
    def from_env(cls) -> "Settings":
        """환경변수에서 Settings 인스턴스를 생성한다."""
        return cls(
            host=os.getenv("WARP_PROXY_HOST", "127.0.0.1"),
            port=int(os.getenv("WARP_PROXY_PORT", "29113")),
            list_all_models=_env_bool("WARP_PROXY_LIST_ALL_MODELS", default=False),
            auth_mode=os.getenv("WARP_PROXY_AUTH_MODE", "session"),
            warp_api_key=os.getenv("WARP_API_KEY"),
            allow_unverified_warp_cli=_env_bool("ALLOW_UNVERIFIED_WARP_CLI", default=False),
            verified_warp_versions=_env_csv(
                "WARP_PROXY_VERIFIED_WARP_VERSIONS",
                default=(SUPPORTED_WARP_VERSION,),
            ),
            command_timeout_seconds=float(os.getenv("WARP_PROXY_COMMAND_TIMEOUT_SECONDS", "120")),
            max_concurrent_requests=int(os.getenv("WARP_PROXY_MAX_CONCURRENT_REQUESTS", "4")),
            cwd=_env_optional_str("WARP_PROXY_CWD"),
            environment=_env_optional_str("WARP_PROXY_ENVIRONMENT"),
            skill=_env_optional_str("WARP_PROXY_SKILL"),
            mcp=_env_json_string_or_string_list("WARP_PROXY_MCP"),
            conversation_store_path=os.getenv("WARP_PROXY_CONVERSATION_STORE", str(DEFAULT_CONVERSATION_STORE)),
        )


# ---------------------------------------------------------------------------
# 환경변수 파싱 헬퍼
# ---------------------------------------------------------------------------

def _env_bool(name: str, *, default: bool) -> bool:
    """'1', 'true', 'yes', 'on' → True, 나머지/미설정 → default."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, *, default: tuple[str, ...]) -> tuple[str, ...]:
    """쉼표 구분 문자열 → tuple. 빈 결과면 default 반환."""
    value = os.getenv(name)
    if value is None:
        return default
    parts = tuple(part.strip() for part in value.split(",") if part.strip())
    return parts or default


def _env_optional_str(name: str) -> str | None:
    """환경변수가 없거나 빈 문자열이면 None, 아니면 strip된 값."""
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _env_json_string_or_string_list(name: str) -> tuple[str, ...]:
    """JSON 문자열 또는 문자열 배열을 파싱한다. MCP 스펙 등에 사용."""
    value = os.getenv(name)
    if value is None:
        return ()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be a JSON string or JSON array of strings") from exc
    if isinstance(parsed, str):
        parsed = parsed.strip()
        if not parsed:
            raise ValueError(f"{name} must not be an empty string")
        return (parsed,)
    if isinstance(parsed, list) and all(isinstance(item, str) and item.strip() for item in parsed):
        return tuple(item.strip() for item in parsed)
    raise ValueError(f"{name} must be a JSON string or JSON array of strings")


def _resolve_existing_dir(value: str, env_name: str) -> str:
    """경로를 resolve하고, 존재하지 않으면 ValueError."""
    resolved = Path(value).expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"{env_name} must be an existing directory")
    return str(resolved)
