"""대화 매핑 영속화.

response_id → Oz conversation_id 매핑을 JSON 파일로 관리한다.
atomic write (NamedTemporaryFile + os.replace)로 파일 깨짐을 방지한다.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


class ConversationStoreError(Exception):
    """대화 저장소 조작 실패 시 발생하는 에러."""
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(slots=True)
class ConversationRecord:
    """하나의 response_id에 대응하는 대화 레코드."""

    conversation_id: str  # Oz 내부 conversation ID
    backend: str          # 사용된 백엔드 커맨드 (e.g. "run")
    created_at: str       # ISO 8601 생성 시각
    last_used_at: str     # ISO 8601 마지막 사용 시각


class ConversationStore:
    """response_id ↔ Oz conversation_id 매핑 저장소."""
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self._lock = threading.Lock()

    def get(self, response_id: str) -> ConversationRecord | None:
        """response_id로 레코드를 조회한다. 없으면 None."""
        with self._lock:
            data = self._read_data()
            raw = data["mappings"].get(response_id)
            if raw is None:
                return None
            return self._parse_record(raw)

    def put(self, response_id: str, *, conversation_id: str, backend: str) -> ConversationRecord:
        """새 매핑을 저장(또는 덮어쓰기)한다."""
        with self._lock:
            now = _utc_now_iso()
            record = ConversationRecord(
                conversation_id=conversation_id,
                backend=backend,
                created_at=now,
                last_used_at=now,
            )
            data = self._read_data()
            data["mappings"][response_id] = asdict(record)
            self._write_data(data)
            return record

    def touch(self, response_id: str) -> ConversationRecord:
        """last_used_at을 현재 시각으로 갱신한다. 존재하지 않으면 에러."""
        with self._lock:
            data = self._read_data()
            raw = data["mappings"].get(response_id)
            if raw is None:
                raise ConversationStoreError("invalid_conversation_reference", "Conversation reference was not found.")
            record = self._parse_record(raw)
            record.last_used_at = _utc_now_iso()
            data["mappings"][response_id] = asdict(record)
            self._write_data(data)
            return record

    def delete(self, response_id: str) -> None:
        with self._lock:
            data = self._read_data()
            data["mappings"].pop(response_id, None)
            self._write_data(data)

    def _read_data(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "mappings": {}}
        try:
            raw_text = self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConversationStoreError("conversation_store_unavailable", f"Could not read conversation store: {exc}") from exc
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ConversationStoreError("conversation_store_corrupt", "Conversation store JSON is corrupt.") from exc
        if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("mappings"), dict):
            raise ConversationStoreError("conversation_store_corrupt", "Conversation store has an invalid top-level structure.")
        return data

    def _write_data(self, data: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as tmp:
                json.dump(data, tmp, ensure_ascii=False, indent=2, sort_keys=True)
                tmp.flush()
                os.fsync(tmp.fileno())
                temp_name = tmp.name
            os.replace(temp_name, self.path)
        except OSError as exc:
            raise ConversationStoreError("conversation_store_unavailable", f"Could not write conversation store: {exc}") from exc

    def _parse_record(self, raw: Any) -> ConversationRecord:
        if not isinstance(raw, dict):
            raise ConversationStoreError("conversation_store_corrupt", "Conversation store record is invalid.")
        fields = ("conversation_id", "backend", "created_at", "last_used_at")
        if any(not isinstance(raw.get(field), str) or not raw.get(field) for field in fields):
            raise ConversationStoreError("conversation_store_corrupt", "Conversation store record is missing required fields.")
        return ConversationRecord(
            conversation_id=raw["conversation_id"],
            backend=raw["backend"],
            created_at=raw["created_at"],
            last_used_at=raw["last_used_at"],
        )


def _utc_now_iso() -> str:
    """현재 UTC 시각을 ISO 8601 형식(Z 접미사)으로 반환."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
