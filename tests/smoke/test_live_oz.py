from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

from config import Settings
from main import create_app
from oz_bridge import DEFAULT_MODEL_ALIAS, OzBridge


def _require_live_smoke() -> None:
    if os.getenv("RUN_LIVE_OZ_SMOKE") != "1":
        pytest.skip("Set RUN_LIVE_OZ_SMOKE=1 to run live Oz smoke tests")


async def _make_client(settings: Settings) -> httpx.AsyncClient:
    app = create_app(settings=settings, bridge=OzBridge(settings))
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def _base_settings(tmp_path: Path) -> Settings:
    settings = Settings.from_env()
    settings.conversation_store_path = str((tmp_path / "conversations.json").resolve())
    return settings


@pytest.mark.anyio
async def test_live_local_chat_completion_smoke(tmp_path: Path) -> None:
    _require_live_smoke()
    settings = _base_settings(tmp_path)

    async with await _make_client(settings) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": DEFAULT_MODEL_ALIAS,
                "messages": [{"role": "user", "content": "Without modifying files or running commands, reply with exactly READY."}],
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["choices"][0]["message"]["content"].strip()


@pytest.mark.anyio
async def test_live_local_streaming_smoke(tmp_path: Path) -> None:
    _require_live_smoke()
    settings = _base_settings(tmp_path)

    async with await _make_client(settings) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": DEFAULT_MODEL_ALIAS,
                "stream": True,
                "messages": [{"role": "user", "content": "Reply with READY in one or more chunks."}],
            },
        )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data: [DONE]" in response.text or '"error":' in response.text


@pytest.mark.anyio
async def test_live_local_conversation_continuation_smoke(tmp_path: Path) -> None:
    _require_live_smoke()
    settings = _base_settings(tmp_path)

    async with await _make_client(settings) as client:
        first = await client.post(
            "/v1/chat/completions",
            json={
                "model": DEFAULT_MODEL_ALIAS,
                "messages": [{"role": "user", "content": "Remember the word BLUEBIRD and reply READY."}],
            },
        )
        assert first.status_code == 200, first.text
        first_id = first.json()["id"]
        second = await client.post(
            "/v1/chat/completions",
            json={
                "model": DEFAULT_MODEL_ALIAS,
                "metadata": {"warp_previous_response_id": first_id},
                "messages": [{"role": "user", "content": "What word did I ask you to remember?"}],
            },
        )

    assert second.status_code == 200, second.text
    assert second.json()["choices"][0]["message"]["content"].strip()


