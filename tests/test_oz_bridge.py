from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from warp_proxy.config import Settings, SUPPORTED_WARP_VERSION
from warp_proxy.models import ChatCompletionRequest
from warp_proxy.oz_bridge import (
    DEFAULT_MODEL_ALIAS,
    OzBridge,
    PreparedExecution,
    ResolvedModel,
    aggregate_events,
    flatten_messages,
    parse_event_line,
    parse_json_output,
    parse_ndjson_events,
    parse_warp_version,
    ProxyError,
    CommandResult,
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

@pytest.mark.anyio
async def test_stream_local_backend_events_accepts_line_longer_than_64kib(tmp_path: Path) -> None:
    # asyncio StreamReader 기본 한계(64 KiB)를 넘는 한 줄 NDJSON 이벤트도 죽지 않고 파싱되어야 한다.
    script = (
        "import json, sys\n"
        f"payload = {{'type': 'agent', 'text': 'x' * 70000}}\n"
        "sys.stdout.write(json.dumps(payload) + '\\n')\n"
    )
    settings = Settings(conversation_store_path=str(tmp_path / "conversations.json"))
    bridge = OzBridge(settings)
    prepared = PreparedExecution(
        request=ChatCompletionRequest(model=DEFAULT_MODEL_ALIAS, messages=[]),
        response_id="resp_test",
        created=0,
        model=ResolvedModel(public_model=DEFAULT_MODEL_ALIAS, backend_command="run"),
        args=[sys.executable, "-c", script],
        prior_response_id=None,
        prior_record=None,
    )

    events = [event async for event in bridge._stream_local_backend_events(prepared)]

    assert len(events) == 1
    assert events[0].kind == "agent"
    assert len(events[0].text or "") == 70000


def test_settings_agent_run_timeout_parses_env_and_validates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WARP_PROXY_CONVERSATION_STORE", str(tmp_path / "conv.json"))
    monkeypatch.setenv("WARP_PROXY_AGENT_RUN_TIMEOUT_SECONDS", "1234")

    assert Settings.from_env().agent_run_timeout_seconds == 1234.0

    with pytest.raises(ValueError):
        Settings(agent_run_timeout_seconds=0)


@pytest.mark.anyio
async def test_create_chat_completion_uses_agent_run_budget_not_probe_timeout(tmp_path: Path) -> None:
    # 논스트리밍 agent run 전체는 프로브용 command_timeout(120s)이 아니라
    # agent_run_timeout 예산으로 실행되어야 한다.
    captured: dict[str, float] = {}

    class TimeoutCapturingRunner:
        def run(self, *, args: list[str], timeout_seconds: float) -> CommandResult:
            if "dump-debug-info" in args:
                return CommandResult(args=args, returncode=0, stdout=f'Warp version: Some("{SUPPORTED_WARP_VERSION}")\n', stderr="")
            captured["timeout"] = timeout_seconds
            return CommandResult(
                args=args,
                returncode=0,
                stdout=json.dumps({"type": "agent", "text": "hi"}) + "\n",
                stderr="",
            )

    settings = Settings(
        command_timeout_seconds=120.0,
        agent_run_timeout_seconds=777.0,
        conversation_store_path=str(tmp_path / "conversations.json"),
    )
    bridge = OzBridge(settings, runner=TimeoutCapturingRunner())  # type: ignore[arg-type]

    response = await bridge.create_chat_completion(
        ChatCompletionRequest(model=DEFAULT_MODEL_ALIAS, messages=[{"role": "user", "content": "hi"}])
    )

    assert response.choices[0].message.content == "hi"
    assert captured["timeout"] == 777.0


@pytest.mark.anyio
async def test_stream_survives_silence_longer_than_probe_timeout(tmp_path: Path) -> None:
    # 에이전트 내부 툴 작업처럼 NDJSON이 오래 멈춰도 agent_run 예산 내이면 죽으면 안 된다.
    script = (
        "import json, sys, time\n"
        "time.sleep(2.5)\n"
        f"sys.stdout.write(json.dumps({{'type': 'agent', 'text': 'done'}}) + '\\n')\n"
    )
    settings = Settings(
        command_timeout_seconds=1.0,
        agent_run_timeout_seconds=15.0,
        conversation_store_path=str(tmp_path / "conversations.json"),
    )
    bridge = OzBridge(settings)
    prepared = PreparedExecution(
        request=ChatCompletionRequest(model=DEFAULT_MODEL_ALIAS, messages=[]),
        response_id="resp_test",
        created=0,
        model=ResolvedModel(public_model=DEFAULT_MODEL_ALIAS, backend_command="run"),
        args=[sys.executable, "-c", script],
        prior_response_id=None,
        prior_record=None,
    )

    events = [event async for event in bridge._stream_local_backend_events(prepared)]

    assert len(events) == 1
    assert events[0].kind == "agent"
    assert events[0].text == "done"


@pytest.mark.anyio
async def test_stream_times_out_beyond_agent_run_budget(tmp_path: Path) -> None:
    # agent_run 예산을 넘는 침묵은 backend_timeout으로 죽는다 (완전히 죽은 CLI 방어).
    script = (
        "import time\n"
        "time.sleep(30)\n"
    )
    settings = Settings(
        agent_run_timeout_seconds=1.0,
        conversation_store_path=str(tmp_path / "conversations.json"),
    )
    bridge = OzBridge(settings)
    prepared = PreparedExecution(
        request=ChatCompletionRequest(model=DEFAULT_MODEL_ALIAS, messages=[]),
        response_id="resp_test",
        created=0,
        model=ResolvedModel(public_model=DEFAULT_MODEL_ALIAS, backend_command="run"),
        args=[sys.executable, "-c", script],
        prior_response_id=None,
        prior_record=None,
    )

    with pytest.raises(ProxyError) as exc_info:
        async for _ in bridge._stream_local_backend_events(prepared):
            pass

    assert exc_info.value.error.code == "backend_timeout"
