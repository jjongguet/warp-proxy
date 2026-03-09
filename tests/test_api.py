from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from config import Settings, SUPPORTED_WARP_VERSION
from conversation_store import ConversationStore
from main import create_app
from oz_bridge import CURATED_MODEL_IDS, DEFAULT_MODEL_ALIAS, CommandResult, OzBridge, ProxyError, parse_event_line

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
    return CommandResult(args=["oz", "dump-debug-info"], returncode=0, stdout=f'Warp version: Some("{SUPPORTED_WARP_VERSION}")\n', stderr="")


def _model_list_result(*ids: str) -> CommandResult:
    return CommandResult(args=["oz", "model", "list"], returncode=0, stdout=json.dumps([{"id": model_id} for model_id in ids]), stderr="")


def _local_success(stdout: str | None = None) -> CommandResult:
    return CommandResult(args=["oz", "agent", "run"], returncode=0, stdout=stdout or (FIXTURES_DIR / "live_local_success.ndjson").read_text(), stderr="")


@pytest.mark.anyio
async def test_models_endpoint_returns_curated_models_by_default(settings: Settings) -> None:
    runner = FakeRunner([])
    bridge = OzBridge(settings, runner=runner)
    async with await make_client(bridge) as client:
        response = await client.get("/v1/models")
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["data"]]
    assert ids[0] == DEFAULT_MODEL_ALIAS
    assert len(ids) == 1 + len(CURATED_MODEL_IDS)
    for curated in CURATED_MODEL_IDS:
        assert f"{DEFAULT_MODEL_ALIAS}/{curated}" in ids


@pytest.mark.anyio
async def test_models_endpoint_returns_all_discovered_when_list_all_models(settings: Settings) -> None:
    settings.list_all_models = True
    runner = FakeRunner([_model_list_result("gpt-5", "claude")])
    bridge = OzBridge(settings, runner=runner)
    async with await make_client(bridge) as client:
        response = await client.get("/v1/models")
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["data"]]
    assert ids[0] == DEFAULT_MODEL_ALIAS
    assert f"{DEFAULT_MODEL_ALIAS}/gpt-5" in ids
    assert f"{DEFAULT_MODEL_ALIAS}/claude" in ids


@pytest.mark.anyio
async def test_local_chat_completion_success_persists_conversation(settings: Settings) -> None:
    runner = FakeRunner([_version_result(), _local_success()])
    bridge = OzBridge(settings, runner=runner)
    async with await make_client(bridge) as client:
        response = await client.post("/v1/chat/completions", json={"model": DEFAULT_MODEL_ALIAS, "messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 200
    body = response.json()
    store = ConversationStore(settings.conversation_store_path)
    record = store.get(body["id"])
    assert record is not None
    assert record.conversation_id == "00000000-0000-0000-0000-000000000000"


@pytest.mark.anyio
async def test_streaming_returns_sse_frames_and_done(settings: Settings) -> None:
    runner = FakeRunner([_version_result()])
    bridge = OzBridge(settings, runner=runner)

    async def fake_stream(_prepared):
        yield parse_event_line('{"type":"system","event_type":"conversation_started","conversation_id":"conv-123"}')
        yield parse_event_line('{"type":"agent","text":"hel"}')
        yield parse_event_line('{"type":"agent","text":"lo"}')

    bridge._stream_local_backend_events = fake_stream  # type: ignore[method-assign]
    async with await make_client(bridge) as client:
        response = await client.post("/v1/chat/completions", json={"model": DEFAULT_MODEL_ALIAS, "stream": True, "messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
    assert json.loads(lines[0][6:])["choices"][0]["delta"] == {"role": "assistant"}
    assert json.loads(lines[1][6:])["choices"][0]["delta"] == {"content": "hel"}
    assert json.loads(lines[2][6:])["choices"][0]["delta"] == {"content": "lo"}
    assert json.loads(lines[3][6:])["choices"][0]["finish_reason"] == "stop"
    assert lines[4] == "data: [DONE]"


@pytest.mark.anyio
async def test_streaming_malformed_before_first_chunk_returns_json_error(settings: Settings) -> None:
    runner = FakeRunner([_version_result()])
    bridge = OzBridge(settings, runner=runner)

    async def bad_stream(_prepared):
        raise ProxyError(status_code=502, code="malformed_backend_output", message="bad stream before first chunk")
        yield  # pragma: no cover

    bridge._stream_local_backend_events = bad_stream  # type: ignore[method-assign]
    async with await make_client(bridge) as client:
        response = await client.post("/v1/chat/completions", json={"model": DEFAULT_MODEL_ALIAS, "stream": True, "messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "malformed_backend_output"


@pytest.mark.anyio
async def test_namespaced_request_triggers_inline_model_discovery(settings: Settings) -> None:
    runner = FakeRunner([_model_list_result("gpt-5"), _version_result(), _local_success()])
    bridge = OzBridge(settings, runner=runner)
    async with await make_client(bridge) as client:
        response = await client.post("/v1/chat/completions", json={"model": f"{DEFAULT_MODEL_ALIAS}/gpt-5", "messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 200
    assert "--model" in runner.calls[2]
    assert runner.calls[2][runner.calls[2].index("--model") + 1] == "gpt-5"


@pytest.mark.anyio
async def test_namespaced_request_returns_503_when_catalog_unavailable(settings: Settings) -> None:
    runner = FakeRunner([CommandResult(args=["oz", "model", "list"], returncode=1, stdout="", stderr="catalog down")])
    bridge = OzBridge(settings, runner=runner)
    async with await make_client(bridge) as client:
        response = await client.post("/v1/chat/completions", json={"model": f"{DEFAULT_MODEL_ALIAS}/gpt-5", "messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_catalog_unavailable"


@pytest.mark.anyio
async def test_environment_and_mcp_are_passed_to_local_backend(tmp_path: Path) -> None:
    settings = Settings(auth_mode="session", environment="env-123", mcp=("mcp-a", "mcp-b"), verified_warp_versions=(SUPPORTED_WARP_VERSION,), conversation_store_path=str(tmp_path / "conversations.json"))
    runner = FakeRunner([_version_result(), _local_success()])
    bridge = OzBridge(settings, runner=runner)
    async with await make_client(bridge) as client:
        response = await client.post("/v1/chat/completions", json={"model": DEFAULT_MODEL_ALIAS, "messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 200
    args = runner.calls[1]
    assert args[args.index("--environment") + 1] == "env-123"
    mcp_indexes = [index + 1 for index, value in enumerate(args) if value == "--mcp"]
    assert [args[index] for index in mcp_indexes] == ["mcp-a", "mcp-b"]


@pytest.mark.anyio
async def test_local_continuation_uses_previous_response_id_mapping(settings: Settings) -> None:
    runner = FakeRunner([_version_result(), _local_success(), _local_success('{"type":"agent","text":"continued"}\n')])
    bridge = OzBridge(settings, runner=runner)
    async with await make_client(bridge) as client:
        first = await client.post("/v1/chat/completions", json={"model": DEFAULT_MODEL_ALIAS, "messages": [{"role": "user", "content": "Remember READY."}]})
        first_id = first.json()["id"]
        second = await client.post("/v1/chat/completions", json={"model": DEFAULT_MODEL_ALIAS, "metadata": {"warp_previous_response_id": first_id}, "messages": [{"role": "user", "content": "What did I say?"}]})
    assert second.status_code == 200
    second_args = runner.calls[2]
    assert "--conversation" in second_args
    assert second_args[second_args.index("--conversation") + 1] == "00000000-0000-0000-0000-000000000000"


@pytest.mark.anyio
async def test_unknown_previous_response_id_returns_400(settings: Settings) -> None:
    bridge = OzBridge(settings, runner=FakeRunner([_version_result()]))
    async with await make_client(bridge) as client:
        response = await client.post("/v1/chat/completions", json={"model": DEFAULT_MODEL_ALIAS, "metadata": {"warp_previous_response_id": "chatcmpl_missing"}, "messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_conversation_reference"


@pytest.mark.anyio
async def test_corrupt_store_record_returns_500(settings: Settings) -> None:
    Path(settings.conversation_store_path).write_text('{"version":1,"mappings":{"chatcmpl_bad":{"backend":"run"}}}', encoding="utf-8")
    bridge = OzBridge(settings, runner=FakeRunner([_version_result()]))
    async with await make_client(bridge) as client:
        response = await client.post("/v1/chat/completions", json={"model": DEFAULT_MODEL_ALIAS, "metadata": {"warp_previous_response_id": "chatcmpl_bad"}, "messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "conversation_store_corrupt"


@pytest.mark.anyio
async def test_expired_conversation_returns_409_and_deletes_mapping(settings: Settings) -> None:
    store = ConversationStore(settings.conversation_store_path)
    store.put("chatcmpl_old", conversation_id="conv-old", backend="run")
    runner = FakeRunner([_version_result(), CommandResult(args=[], returncode=1, stdout="", stderr="Conversation not found or expired.")])
    bridge = OzBridge(settings, runner=runner)
    async with await make_client(bridge) as client:
        response = await client.post("/v1/chat/completions", json={"model": DEFAULT_MODEL_ALIAS, "metadata": {"warp_previous_response_id": "chatcmpl_old"}, "messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conversation_expired"
    assert store.get("chatcmpl_old") is None


@pytest.mark.anyio
async def test_admin_status_remains_alias_only_even_after_dynamic_discovery(settings: Settings) -> None:
    runner = FakeRunner([_model_list_result("gpt-5"), _version_result()])
    bridge = OzBridge(settings, runner=runner)
    async with await make_client(bridge) as client:
        _ = await client.get("/v1/models")
        status_response = await client.get("/admin/status")
    assert status_response.status_code == 200
    assert status_response.json()["models"] == [
        {"id": DEFAULT_MODEL_ALIAS, "available": True, "reason": None},
    ]
