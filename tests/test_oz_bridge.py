from __future__ import annotations

from pathlib import Path

import pytest

from config import Settings, SUPPORTED_WARP_VERSION
from models import ChatCompletionRequest
from oz_bridge import (
    DEFAULT_MODEL_ALIAS,
    aggregate_events,
    flatten_messages,
    parse_event_line,
    parse_json_output,
    parse_ndjson_events,
    parse_warp_version,
    ProxyError,
    _parse_model_catalog,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "oz"


def test_parse_warp_version_extracts_verified_value_from_fixture() -> None:
    assert parse_warp_version((FIXTURES_DIR / "dump_debug_info_supported.txt").read_text()) == SUPPORTED_WARP_VERSION


def test_parse_json_output_collects_agent_text_from_real_fixture() -> None:
    assert parse_json_output((FIXTURES_DIR / "live_local_success.ndjson").read_text()) == "READY."


def test_parse_ndjson_events_captures_conversation_id() -> None:
    events = parse_ndjson_events((FIXTURES_DIR / "live_local_success.ndjson").read_text())
    assert events[0].conversation_id == "00000000-0000-0000-0000-000000000000"
    assert events[1].kind == "agent"
    assert aggregate_events(events) == ("READY.", "00000000-0000-0000-0000-000000000000")


def test_parse_json_output_rejects_non_json_lines() -> None:
    with pytest.raises(ProxyError) as exc_info:
        parse_json_output("not-json\n")
    assert exc_info.value.error.code == "malformed_backend_output"


def test_flatten_messages_preserves_roles_and_adds_tail_instruction() -> None:
    request = ChatCompletionRequest(
        model=DEFAULT_MODEL_ALIAS,
        messages=[
            {"role": "system", "content": "Set context."},
            {"role": "user", "content": [{"type": "text", "text": "First line"}, {"type": "text", "text": "Second line"}]},
        ],
    )

    prompt = flatten_messages(request)

    assert "[system]\nSet context." in prompt
    assert "[user]\nFirst line\nSecond line" in prompt
    assert prompt.endswith("Please answer the latest user request directly and clearly.")


def test_settings_requires_api_key_in_api_key_mode() -> None:
    with pytest.raises(ValueError):
        Settings(auth_mode="api_key", warp_api_key=None)


def test_settings_validates_cwd_exists(tmp_path: Path) -> None:
    settings = Settings(cwd=str(tmp_path))
    assert settings.cwd == str(tmp_path.resolve())


def test_settings_parses_environment_skill_and_mcp_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WARP_PROXY_ENVIRONMENT", "env-123")
    monkeypatch.setenv("WARP_PROXY_SKILL", "repo:skill")
    monkeypatch.setenv("WARP_PROXY_MCP", '["mcp-a","mcp-b"]')
    monkeypatch.setenv("WARP_PROXY_CONVERSATION_STORE", str(tmp_path / "conv.json"))

    settings = Settings.from_env()

    assert settings.environment == "env-123"
    assert settings.skill == "repo:skill"
    assert settings.mcp == ("mcp-a", "mcp-b")
    assert settings.conversation_store_path.endswith("conv.json")


def test_parse_event_line_rejects_non_object_json() -> None:
    with pytest.raises(ProxyError):
        parse_event_line('"hello"')


def test_parse_model_catalog_parses_dicts_and_strings() -> None:
    payload = [{"id": "gpt-5"}, {"id": "claude"}, "manual"]
    assert _parse_model_catalog(payload) == ("gpt-5", "claude", "manual")
