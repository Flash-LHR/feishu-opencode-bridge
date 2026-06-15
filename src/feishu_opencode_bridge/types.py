from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class MentionRef:
    key: str = ""
    name: str = ""
    mentioned_type: str = ""
    open_id: str = ""
    user_id: str = ""
    union_id: str = ""


@dataclass(frozen=True)
class MessageRecord:
    message_id: str
    chat_id: str
    topic_id: str
    thread_id: str
    root_id: str
    parent_id: str
    create_time_ms: int
    sender_id: str
    sender_name: str
    sender_type: str
    message_type: str
    text: str
    mentions: List[MentionRef] = field(default_factory=list)
    source: str = "feishu"
    sender_id_type: str = ""

    @property
    def role(self) -> str:
        if self.sender_type.lower() in {"app", "bot"} or self.source == "assistant":
            return "assistant"
        return "user"

    def to_json(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "chat_id": self.chat_id,
            "topic_id": self.topic_id,
            "thread_id": self.thread_id,
            "root_id": self.root_id,
            "parent_id": self.parent_id,
            "create_time_ms": self.create_time_ms,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "sender_type": self.sender_type,
            "message_type": self.message_type,
            "text": self.text,
            "mentions": [m.__dict__ for m in self.mentions],
            "source": self.source,
            "sender_id_type": self.sender_id_type,
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "MessageRecord":
        mentions = [MentionRef(**m) for m in data.get("mentions", []) if isinstance(m, dict)]
        return cls(
            message_id=str(data.get("message_id") or ""),
            chat_id=str(data.get("chat_id") or ""),
            topic_id=str(data.get("topic_id") or ""),
            thread_id=str(data.get("thread_id") or ""),
            root_id=str(data.get("root_id") or ""),
            parent_id=str(data.get("parent_id") or ""),
            create_time_ms=int(data.get("create_time_ms") or 0),
            sender_id=str(data.get("sender_id") or ""),
            sender_name=str(data.get("sender_name") or ""),
            sender_type=str(data.get("sender_type") or ""),
            message_type=str(data.get("message_type") or "text"),
            text=str(data.get("text") or ""),
            mentions=mentions,
            source=str(data.get("source") or "feishu"),
            sender_id_type=str(data.get("sender_id_type") or ""),
        )


@dataclass(frozen=True)
class IncomingEvent:
    event_id: str
    message: MessageRecord
    chat_type: str
    raw_text: str
    clean_text: str
    is_mentioned: bool

