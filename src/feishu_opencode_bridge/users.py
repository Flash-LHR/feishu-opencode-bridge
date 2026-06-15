from __future__ import annotations

import logging
import time
from typing import Dict, Optional

from .identity import BotIdentity, is_display_name
from .ports import FeishuGateway
from .state import StateStore
from .types import MessageRecord

logger = logging.getLogger(__name__)


class UserNameResolver:
    def __init__(
        self,
        feishu: FeishuGateway,
        state: StateStore,
        identity: BotIdentity,
        failure_ttl_seconds: float = 60,
    ) -> None:
        self._feishu = feishu
        self._state = state
        self._identity = identity
        self._failure_ttl_seconds = failure_ttl_seconds
        self._lookup_failures: Dict[str, float] = {}

    def label_for(self, message: MessageRecord) -> str:
        sender_id = message.sender_id.strip()
        sender_name = message.sender_name.strip()
        if self._identity.is_app_sender(message) and sender_name.lower() in {"app", "bot", "unknown"}:
            return "机器人"
        if sender_name != sender_id and is_display_name(sender_name):
            return sender_name
        resolved = self.resolve_user_display_name(sender_id, message.sender_id_type, message.chat_id)
        if resolved:
            return resolved
        if self._identity.is_app_sender(message):
            return "机器人"
        return user_fallback_label(sender_id, message.sender_id_type)

    def resolve_user_display_name(
        self,
        user_id: str,
        user_id_type: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> Optional[str]:
        if not user_id or user_id.startswith(("cli_", "app_", "bot_")):
            return None
        cached = self._state.get_user_display_name(user_id)
        if cached:
            return cached
        failure_at = self._lookup_failures.get(user_id)
        if failure_at and time.time() - failure_at < self._failure_ttl_seconds:
            return None

        name = self._lookup_chat_member_name(chat_id, user_id, user_id_type)
        if name:
            self._state.set_user_display_name(user_id, name)
            return name

        try:
            name = self._feishu.get_user_display_name(user_id, user_id_type)
        except Exception as exc:
            self._lookup_failures[user_id] = time.time()
            logger.warning("Feishu user name lookup failed for %s: %s", user_id, exc)
            return None
        if name:
            self._state.set_user_display_name(user_id, name)
            return name
        return None

    def _lookup_chat_member_name(
        self,
        chat_id: Optional[str],
        user_id: str,
        user_id_type: Optional[str],
    ) -> Optional[str]:
        if not chat_id:
            return None
        try:
            return self._feishu.get_chat_member_display_name(chat_id, user_id, user_id_type)
        except Exception as exc:
            logger.debug("Feishu chat member name lookup failed for %s: %s", user_id, exc)
            return None


def user_fallback_label(user_id: str, user_id_type: Optional[str] = None) -> str:
    if not user_id:
        return "用户"
    label_type = user_id_type or infer_user_id_type(user_id)
    return f"用户({label_type}:{short_identifier(user_id)})"


def infer_user_id_type(user_id: str) -> str:
    if user_id.startswith("ou_"):
        return "open_id"
    if user_id.startswith("on_"):
        return "union_id"
    return "user_id"


def short_identifier(value: str) -> str:
    if len(value) <= 12:
        return value
    return f"{value[:4]}...{value[-4:]}"
