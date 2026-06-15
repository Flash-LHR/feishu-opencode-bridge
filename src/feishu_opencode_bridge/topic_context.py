from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Dict, List, Optional

from .config import Settings
from .identity import is_display_name
from .ports import FeishuGateway
from .prompt import PromptBuilder
from .state import StateStore, merge_messages
from .types import IncomingEvent, MessageRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpenCodePayload:
    topic_id: str
    message_id: str
    create_time_ms: int
    prompt: str
    session_id: Optional[str]
    mode: str
    message_count: int


class TopicContextBuilder:
    def __init__(
        self,
        settings: Settings,
        feishu: FeishuGateway,
        state: StateStore,
        prompt: PromptBuilder,
    ) -> None:
        self._settings = settings
        self._feishu = feishu
        self._state = state
        self._prompt = prompt

    def build_payload(self, incoming: IncomingEvent) -> OpenCodePayload:
        topic_id = incoming.message.topic_id
        session = self._state.get_topic_session(topic_id)
        session_id = str(session.get("session_id") or "") if session else ""
        messages = self.collect_messages(incoming)
        if session_id:
            selected = self.messages_after_session_cursor(messages, session)
            mode = "incremental"
        else:
            selected = messages
            mode = "full"

        selected = self._prompt.input_messages(selected)
        if not any(message.message_id == incoming.message.message_id for message in selected):
            selected.append(incoming.message)
            selected = self._prompt.input_messages(merge_messages(selected))

        return OpenCodePayload(
            topic_id=topic_id,
            message_id=incoming.message.message_id,
            create_time_ms=incoming.message.create_time_ms,
            prompt=self._prompt.render(selected),
            session_id=session_id or None,
            mode=mode,
            message_count=len(selected),
        )

    def collect_messages(self, incoming: IncomingEvent) -> List[MessageRecord]:
        topic_id = incoming.message.topic_id
        remote = self._read_remote_history(incoming)
        cached = self._state.get_cached_messages(topic_id)
        remote = self._ensure_root_message(remote, cached, incoming)

        messages = merge_messages(remote, cached)
        incoming_message = self._with_history_sender_name(incoming.message, messages)
        messages = [message for message in messages if message.message_id != incoming.message.message_id]
        return merge_messages(messages, [incoming_message])[-self._settings.context_max_messages :]

    def messages_after_session_cursor(
        self,
        messages: List[MessageRecord],
        session: Optional[Dict[str, object]],
    ) -> List[MessageRecord]:
        if not session:
            return messages
        last_id = str(session.get("last_sent_message_id") or "")
        if last_id:
            for index, message in enumerate(messages):
                if message.message_id == last_id:
                    return messages[index + 1 :]
        last_at_ms = int(session.get("last_sent_at_ms") or 0)
        if last_at_ms:
            return [message for message in messages if message.create_time_ms > last_at_ms]
        return messages

    def _read_remote_history(self, incoming: IncomingEvent) -> List[MessageRecord]:
        try:
            if incoming.message.thread_id:
                return self._feishu.list_thread_messages(
                    incoming.message.thread_id,
                    max_messages=self._settings.context_max_messages,
                    page_limit=self._settings.history_page_limit,
                )
            if incoming.chat_type == "p2p" and incoming.message.chat_id:
                return self._feishu.list_chat_messages(
                    incoming.message.chat_id,
                    topic_id=incoming.message.topic_id,
                    max_messages=self._settings.context_max_messages,
                    page_limit=self._settings.history_page_limit,
                )
        except Exception as exc:
            logger.warning("Feishu history read failed, using local cache only: %s", exc)
        return []

    def _ensure_root_message(
        self,
        remote: List[MessageRecord],
        cached: List[MessageRecord],
        incoming: IncomingEvent,
    ) -> List[MessageRecord]:
        root_message_id = incoming.message.root_id or ""
        if not root_message_id:
            return remote
        if any(message.message_id == root_message_id for message in remote + cached):
            return remote
        try:
            root_message = self._feishu.get_message(root_message_id, topic_id=incoming.message.topic_id)
        except Exception as exc:
            logger.warning("Feishu root message read failed message_id=%s: %s", root_message_id, exc)
            return remote
        if not root_message:
            return remote
        return merge_messages([root_message], remote)

    def _with_history_sender_name(
        self,
        incoming_message: MessageRecord,
        messages: List[MessageRecord],
    ) -> MessageRecord:
        history_copy = next(
            (message for message in messages if message.message_id == incoming_message.message_id),
            None,
        )
        if history_copy and is_display_name(history_copy.sender_name):
            return replace(incoming_message, sender_name=history_copy.sender_name)
        return incoming_message
