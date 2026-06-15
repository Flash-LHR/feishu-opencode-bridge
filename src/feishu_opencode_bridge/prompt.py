from __future__ import annotations

from typing import Iterable, List

from .config import Settings
from .identity import BotIdentity
from .message_content import clean_unreadable_card_fallback, strip_bot_mentions
from .types import MessageRecord
from .users import UserNameResolver


class PromptBuilder:
    def __init__(self, settings: Settings, identity: BotIdentity, users: UserNameResolver) -> None:
        self._settings = settings
        self._identity = identity
        self._users = users

    def input_messages(self, messages: Iterable[MessageRecord]) -> List[MessageRecord]:
        result: List[MessageRecord] = []
        for message in messages:
            text = self.message_text(message)
            if not text:
                continue
            if self._identity.is_own_message(message) and message.message_type != "interactive":
                continue
            if self._identity.is_app_sender(message) and message.message_type != "interactive":
                continue
            if text.startswith("/"):
                continue
            result.append(message)
        return result

    def render(self, messages: Iterable[MessageRecord]) -> str:
        return "\n".join(
            f"{self._users.label_for(message)}：{self.message_text(message)}"
            for message in messages
        )

    def message_text(self, message: MessageRecord) -> str:
        text = strip_bot_mentions(
            message.text,
            message.mentions,
            bot_open_id=self._settings.feishu_bot_open_id,
            bot_name=self._settings.feishu_bot_name,
        ).strip()
        return clean_unreadable_card_fallback(text)
