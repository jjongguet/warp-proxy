from __future__ import annotations

from pathlib import Path

import pytest

from conversation_store import ConversationStore, ConversationStoreError


def test_store_persists_and_reloads(tmp_path: Path) -> None:
    path = tmp_path / "conversations.json"
    store = ConversationStore(path)
    store.put("chatcmpl_1", conversation_id="conv-1", backend="run")

    reloaded = ConversationStore(path)
    record = reloaded.get("chatcmpl_1")

    assert record is not None
    assert record.conversation_id == "conv-1"
    assert record.backend == "run"


def test_store_rejects_corrupt_json(tmp_path: Path) -> None:
    path = tmp_path / "conversations.json"
    path.write_text("{not-json", encoding="utf-8")
    store = ConversationStore(path)

    with pytest.raises(ConversationStoreError) as exc_info:
        store.get("chatcmpl_1")

    assert exc_info.value.code == "conversation_store_corrupt"


def test_store_rejects_invalid_record_shape(tmp_path: Path) -> None:
    path = tmp_path / "conversations.json"
    path.write_text('{"version":1,"mappings":{"chatcmpl_1":{"backend":"run"}}}', encoding="utf-8")
    store = ConversationStore(path)

    with pytest.raises(ConversationStoreError) as exc_info:
        store.get("chatcmpl_1")

    assert exc_info.value.code == "conversation_store_corrupt"
