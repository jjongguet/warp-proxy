from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from config import SUPPORTED_WARP_VERSION, Settings
from conversation_store import ConversationStore
from main import create_app
from oz_bridge import CommandResult, DEFAULT_MODEL_ALIAS, OzBridge, ProxyError, parse_event_line

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "oz"


class FakeRunner:
    def __init__(self, responses: list[CommandResult]) -> None:
        self.responses = list(responses)
        self.calls: list[list[str]] = []

    def run(self, *, args: list[str], timeout_seconds: float) -> CommandResult:
        self.calls.append(args)
        if not self.responses:
            raise AssertionError(f"No more fake responses configured for args={args}")
        return self.responses.pop(0)


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        auth_mode="session",
        verified_warp_versions=(SUPPORTED_WARP_VERSION,),
        conversation_store_path=str(tmp_path / "conversations.json"),
    )


async def make_client(bridge: OzBridge):
    app = create_app(settings=bridge.settings, bridge=bridge)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def _version_result() -> CommandResult:
    return CommandResult(
        args=["oz", "dump-debug-info"],
        returncode=0,
        stdout=f'Warp version: Some("{SUPPORTED_WARP_VERSION}")\n',
        stderr="",
    )


def _local_success(stdout: str | None = None) -> CommandResult:
    return CommandResult(
        args=["oz", "agent", "run"],
        returncode=0,
        stdout=stdout or (FIXTURES_DIR / "live_local_success.ndjson").read_text(),
        stderr="",
    )


@pytest.mark.anyio
async def test_anthropic_messages_non_streaming_success(settings: Settings) -> None:
    runner = FakeRunner([_version_result(), _local_success()])
    bridge = OzBridge(settings, runner=runner)
    async with await make_client(bridge) as client:
        response = await client.post(
            "/v1/messages",
            json={
                "model": DEFAULT_MODEL_ALIAS,
                "max_tokens": 512,
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "message"
    assert body["model"] == DEFAULT_MODEL_ALIAS
    assert body["content"][0]["type"] == "text"
    assert isinstance(body["content"][0]["text"], str)
    assert body["usage"]["input_tokens"] >= 1
    assert body["usage"]["output_tokens"] >= 1


@pytest.mark.anyio
async def test_anthropic_messages_streaming_sse_shape(settings: Settings) -> None:
    runner = FakeRunner([_version_result()])
    bridge = OzBridge(settings, runner=runner)

    async def fake_stream(_prepared):
        yield parse_event_line('{"type":"system","event_type":"conversation_started","conversation_id":"conv-123"}')
        yield parse_event_line('{"type":"agent","text":"hel"}')
        yield parse_event_line('{"type":"agent","text":"lo"}')

    bridge._stream_local_backend_events = fake_stream  # type: ignore[method-assign]
    async with await make_client(bridge) as client:
        response = await client.post(
            "/v1/messages",
            json={
                "model": DEFAULT_MODEL_ALIAS,
                "max_tokens": 512,
                "stream": True,
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
    assert response.status_code == 200
    lines = response.text.splitlines()
    events = [line for line in lines if line.startswith("event: ")]
    assert events == [
        "event: message_start",
        "event: content_block_start",
        "event: content_block_delta",
        "event: content_block_delta",
        "event: content_block_stop",
        "event: message_delta",
        "event: message_stop",
    ]
    data_lines = [line for line in lines if line.startswith("data: ")]
    assert json.loads(data_lines[2][6:])["delta"]["text"] == "hel"
    assert json.loads(data_lines[3][6:])["delta"]["text"] == "lo"
    assert json.loads(data_lines[5][6:])["usage"]["output_tokens"] >= 1


@pytest.mark.anyio
async def test_anthropic_streaming_midstream_error_emits_error_event(settings: Settings) -> None:
    runner = FakeRunner([_version_result()])
    bridge = OzBridge(settings, runner=runner)

    async def bad_stream(_prepared):
        yield parse_event_line('{"type":"system","event_type":"conversation_started","conversation_id":"conv-123"}')
        yield parse_event_line('{"type":"agent","text":"first"}')
        raise ProxyError(status_code=502, code="malformed_backend_output", message="stream broken")
        yield  # pragma: no cover

    bridge._stream_local_backend_events = bad_stream  # type: ignore[method-assign]
    async with await make_client(bridge) as client:
        response = await client.post(
            "/v1/messages",
            json={
                "model": DEFAULT_MODEL_ALIAS,
                "max_tokens": 512,
                "stream": True,
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
    assert response.status_code == 200
    lines = response.text.splitlines()
    events = [line for line in lines if line.startswith("event: ")]
    assert "event: error" in events
    error_index = events.index("event: error")
    data_lines = [line for line in lines if line.startswith("data: ")]
    error_payload = json.loads(data_lines[error_index][6:])
    assert error_payload["type"] == "error"


@pytest.mark.anyio
async def test_anthropic_count_tokens_estimate(settings: Settings) -> None:
    bridge = OzBridge(settings, runner=FakeRunner([]))
    async with await make_client(bridge) as client:
        payload = {
            "model": DEFAULT_MODEL_ALIAS,
            "max_tokens": 256,
            "messages": [{"role": "user", "content": "count this prompt please"}],
        }
        first = await client.post("/v1/messages/count_tokens", json=payload)
        second = await client.post("/v1/messages/count_tokens", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["input_tokens"] >= 1
    assert first.json()["input_tokens"] == second.json()["input_tokens"]


@pytest.mark.anyio
async def test_anthropic_count_tokens_reflects_tools_payload(settings: Settings) -> None:
    bridge = OzBridge(settings, runner=FakeRunner([]))
    async with await make_client(bridge) as client:
        base_payload = {
            "model": DEFAULT_MODEL_ALIAS,
            "max_tokens": 256,
            "messages": [{"role": "user", "content": "Count this prompt."}],
        }
        with_tools_payload = {
            **base_payload,
            "tools": [
                {
                    "name": "run_cmd",
                    "description": "run local command",
                    "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}},
                }
            ],
        }
        base = await client.post("/v1/messages/count_tokens", json=base_payload)
        with_tools = await client.post("/v1/messages/count_tokens", json=with_tools_payload)
    assert base.status_code == 200
    assert with_tools.status_code == 200
    assert with_tools.json()["input_tokens"] >= base.json()["input_tokens"]


@pytest.mark.anyio
async def test_anthropic_system_and_block_content_are_normalized(settings: Settings) -> None:
    runner = FakeRunner([_version_result(), _local_success()])
    bridge = OzBridge(settings, runner=runner)
    async with await make_client(bridge) as client:
        response = await client.post(
            "/v1/messages",
            json={
                "model": DEFAULT_MODEL_ALIAS,
                "max_tokens": 256,
                "system": [{"type": "text", "text": "You are concise."}],
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "First line."},
                            {"type": "text", "text": "Second line."},
                        ],
                    }
                ],
            },
        )
    assert response.status_code == 200
    run_args = runner.calls[1]
    assert "--prompt" in run_args
    prompt = run_args[run_args.index("--prompt") + 1]
    assert "[system]" in prompt and "You are concise." in prompt
    assert "First line." in prompt and "Second line." in prompt


@pytest.mark.anyio
async def test_anthropic_continuation_uses_metadata_mapping(settings: Settings) -> None:
    runner = FakeRunner(
        [
            _version_result(),
            _local_success(),
            _local_success('{"type":"agent","text":"continued"}\n'),
        ]
    )
    bridge = OzBridge(settings, runner=runner)
    async with await make_client(bridge) as client:
        first = await client.post(
            "/v1/messages",
            json={
                "model": DEFAULT_MODEL_ALIAS,
                "max_tokens": 128,
                "messages": [{"role": "user", "content": "Remember BLUEBIRD"}],
            },
        )
        first_id = first.json()["id"]
        second = await client.post(
            "/v1/messages",
            json={
                "model": DEFAULT_MODEL_ALIAS,
                "max_tokens": 128,
                "metadata": {"warp_previous_response_id": first_id},
                "messages": [{"role": "user", "content": "What did I ask?"}],
            },
        )
    assert second.status_code == 200
    second_args = runner.calls[2]
    assert "--conversation" in second_args
    assert second_args[second_args.index("--conversation") + 1] == "00000000-0000-0000-0000-000000000000"
    store = ConversationStore(settings.conversation_store_path)
    assert store.get(first_id) is not None


@pytest.mark.anyio
async def test_anthropic_error_shape_for_unsupported_model(settings: Settings) -> None:
    bridge = OzBridge(settings, runner=FakeRunner([]))
    async with await make_client(bridge) as client:
        response = await client.post(
            "/v1/messages",
            json={
                "model": "not-supported",
                "max_tokens": 128,
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    assert response.status_code == 400
    body = response.json()
    assert body["type"] == "error"
    assert body["error"]["type"] == "invalid_request_error"


@pytest.mark.anyio
async def test_anthropic_validation_error_shape(settings: Settings) -> None:
    bridge = OzBridge(settings, runner=FakeRunner([]))
    async with await make_client(bridge) as client:
        response = await client.post(
            "/v1/messages",
            json={
                "model": DEFAULT_MODEL_ALIAS,
                "max_tokens": 128,
                "messages": [{"role": "user", "content": {"type": "text", "text": "hi"}}],
            },
        )
    assert response.status_code == 400
    body = response.json()
    assert body["type"] == "error"
    assert "content" in body["error"]["message"].lower()
