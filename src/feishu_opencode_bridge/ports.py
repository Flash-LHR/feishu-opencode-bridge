from __future__ import annotations

from typing import List, Optional, Protocol

from .opencode import OpenCodeResult
from .types import MessageRecord


class FeishuGateway(Protocol):
    def reply_text(self, message_id: str, text: str, uuid_seed: Optional[str] = None) -> Optional[str]:
        ...

    def add_reaction(self, message_id: str, emoji_type: str) -> Optional[str]:
        ...

    def delete_reaction(self, message_id: str, reaction_id: str) -> None:
        ...

    def get_user_display_name(self, user_id: str, user_id_type: Optional[str] = None) -> Optional[str]:
        ...

    def get_chat_member_display_name(
        self,
        chat_id: str,
        user_id: str,
        user_id_type: Optional[str] = None,
    ) -> Optional[str]:
        ...

    def list_thread_messages(self, thread_id: str, max_messages: int, page_limit: int) -> List[MessageRecord]:
        ...

    def list_chat_messages(
        self,
        chat_id: str,
        topic_id: str,
        max_messages: int,
        page_limit: int,
    ) -> List[MessageRecord]:
        ...

    def get_message(self, message_id: str, topic_id: str) -> Optional[MessageRecord]:
        ...


class OpenCodeGateway(Protocol):
    def check_ready(self) -> str:
        ...

    def run(
        self,
        prompt: str,
        model: Optional[str],
        title: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> OpenCodeResult:
        ...

    def list_models(self, provider: Optional[str] = None, refresh: bool = False) -> str:
        ...
