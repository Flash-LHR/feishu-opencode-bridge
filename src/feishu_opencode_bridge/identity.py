from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .config import Settings
from .types import MessageRecord


@dataclass(frozen=True)
class BotIdentity:
    app_id: str = ""
    bot_open_id: Optional[str] = None
    bot_name: Optional[str] = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "BotIdentity":
        return cls(
            app_id=settings.feishu_app_id,
            bot_open_id=settings.feishu_bot_open_id,
            bot_name=settings.feishu_bot_name,
        )

    def is_own_message(self, message: MessageRecord) -> bool:
        sender_id = (message.sender_id or "").strip()
        sender_name = (message.sender_name or "").strip()
        if message.source == "assistant":
            return True
        if self.app_id and sender_id == self.app_id:
            return True
        if self.bot_open_id and sender_id == self.bot_open_id:
            return True
        return bool(self.bot_name and sender_name == self.bot_name)

    @staticmethod
    def is_app_sender(message: MessageRecord) -> bool:
        return message.sender_type.lower() in {"app", "bot"}


def is_display_name(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    return not re.match(r"^(ou_|on_|oc_|cli_|user_|union_|open_)", text)
