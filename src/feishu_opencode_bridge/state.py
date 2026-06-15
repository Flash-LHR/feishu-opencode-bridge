from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .types import MessageRecord


class StateStore:
    def __init__(self, path: Path, max_cached_messages: int = 200) -> None:
        self._path = path
        self._max_cached_messages = max_cached_messages
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {
            "current_model": None,
            "seen_events": {},
            "sessions": {},
            "threads": {},
            "users": {},
        }
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            self._data.update(data)
            self._data.setdefault("seen_events", {})
            self._data.setdefault("sessions", {})
            self._data.setdefault("threads", {})
            self._data.setdefault("users", {})

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp_path, self._path)

    def get_current_model(self, default_model: Optional[str] = None) -> Optional[str]:
        with self._lock:
            return self._data.get("current_model") or default_model

    def set_current_model(self, model: Optional[str]) -> None:
        with self._lock:
            self._data["current_model"] = model
            self._save()

    def mark_event_seen(self, event_id: str, ttl_seconds: int = 86400) -> bool:
        if not event_id:
            return True
        now = int(time.time())
        with self._lock:
            seen = self._data.setdefault("seen_events", {})
            expired = [key for key, ts in seen.items() if now - int(ts or 0) > ttl_seconds]
            for key in expired:
                seen.pop(key, None)
            if event_id in seen:
                return False
            seen[event_id] = now
            self._save()
            return True

    def append_message(self, topic_id: str, message: MessageRecord) -> None:
        if not topic_id:
            return
        with self._lock:
            threads = self._data.setdefault("threads", {})
            items = threads.setdefault(topic_id, [])
            existing = {item.get("message_id") for item in items if isinstance(item, dict)}
            if message.message_id in existing:
                return
            items.append(message.to_json())
            items.sort(key=lambda item: int(item.get("create_time_ms") or 0))
            del items[: max(0, len(items) - self._max_cached_messages)]
            self._save()

    def get_cached_messages(self, topic_id: str) -> List[MessageRecord]:
        with self._lock:
            items = self._data.get("threads", {}).get(topic_id, [])
            records = []
            for item in items:
                if isinstance(item, dict):
                    records.append(MessageRecord.from_json(item))
            return records

    def clear_topic(self, topic_id: str) -> None:
        with self._lock:
            self._data.setdefault("threads", {}).pop(topic_id, None)
            self._data.setdefault("sessions", {}).pop(topic_id, None)
            self._save()

    def get_topic_session(self, topic_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._data.setdefault("sessions", {}).get(topic_id)
            return dict(item) if isinstance(item, dict) else None

    def set_topic_session(
        self,
        topic_id: str,
        session_id: str,
        last_sent_message_id: str,
        last_sent_at_ms: int,
    ) -> None:
        if not topic_id or not session_id:
            return
        with self._lock:
            self._data.setdefault("sessions", {})[topic_id] = {
                "session_id": session_id,
                "last_sent_message_id": last_sent_message_id,
                "last_sent_at_ms": int(last_sent_at_ms or 0),
            }
            self._save()

    def get_user_display_name(self, user_id: str) -> Optional[str]:
        if not user_id:
            return None
        with self._lock:
            value = self._data.setdefault("users", {}).get(user_id)
            return str(value) if value else None

    def set_user_display_name(self, user_id: str, display_name: str) -> None:
        if not user_id or not display_name:
            return
        with self._lock:
            self._data.setdefault("users", {})[user_id] = display_name
            self._save()


def merge_messages(*groups: List[MessageRecord]) -> List[MessageRecord]:
    by_id: Dict[str, MessageRecord] = {}
    synthetic_index = 0
    for group in groups:
        for message in group:
            key = message.message_id
            if not key:
                synthetic_index += 1
                key = f"synthetic-{synthetic_index}"
            existing = by_id.get(key)
            if existing is None or (not existing.text and message.text):
                by_id[key] = message
    return sorted(by_id.values(), key=lambda msg: (msg.create_time_ms, msg.message_id))
