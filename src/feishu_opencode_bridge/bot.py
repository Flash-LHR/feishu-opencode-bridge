from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Optional

from .commands import CommandHandler
from .config import Settings
from .feishu_event import normalize_incoming_event
from .identity import BotIdentity
from .message_content import split_text
from .opencode import OpenCodeError
from .ports import FeishuGateway, OpenCodeGateway
from .prompt import PromptBuilder
from .state import StateStore
from .topic_context import OpenCodePayload, TopicContextBuilder
from .types import IncomingEvent, MessageRecord
from .users import UserNameResolver

logger = logging.getLogger(__name__)


class TopicLocks:
    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: Dict[str, threading.Lock] = {}

    def get(self, topic_id: str) -> threading.Lock:
        with self._guard:
            lock = self._locks.get(topic_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[topic_id] = lock
            return lock


class FeishuOpenCodeBot:
    def __init__(
        self,
        settings: Settings,
        feishu: FeishuGateway,
        opencode: OpenCodeGateway,
        state: StateStore,
    ) -> None:
        self._settings = settings
        self._feishu = feishu
        self._opencode = opencode
        self._state = state
        self._topic_locks = TopicLocks()

        self._identity = BotIdentity.from_settings(settings)
        self._users = UserNameResolver(feishu, state, self._identity)
        self._prompt = PromptBuilder(settings, self._identity, self._users)
        self._topic_context = TopicContextBuilder(settings, feishu, state, self._prompt)
        self._commands = CommandHandler(settings, state, opencode)

    def handle_raw_event(self, data: object) -> None:
        incoming = normalize_incoming_event(
            data,
            bot_open_id=self._settings.feishu_bot_open_id,
            bot_name=self._settings.feishu_bot_name,
        )
        if not self._state.mark_event_seen(incoming.event_id):
            logger.info("Skip duplicate event %s", incoming.event_id)
            return
        if self._identity.is_own_message(incoming.message) and incoming.message.message_type != "interactive":
            return

        topic_id = incoming.message.topic_id
        self._state.append_message(topic_id, incoming.message)
        if self._identity.is_app_sender(incoming.message):
            return
        if not incoming.is_mentioned:
            return

        lock = self._topic_locks.get(topic_id)
        with lock:
            self._handle_mentioned_message(incoming)

    def _handle_mentioned_message(self, incoming: IncomingEvent) -> None:
        text = incoming.clean_text.strip()
        if not text:
            self._reply(incoming, "我看到了 @，但没有看到具体问题。发送 /help 查看可用命令。")
            return

        if text.startswith("/"):
            response = self._commands.handle(incoming, text)
            self._reply(incoming, response.text, seed_suffix=response.seed_suffix)
            return

        if self._settings.send_processing_message:
            self._reply(incoming, "收到，正在让 OpenCode 处理。", record=False, seed_suffix="processing")

        processing_reaction_id = self._add_processing_reaction(incoming)
        try:
            payload = self._topic_context.build_payload(incoming)
            result = self._run_opencode(incoming, payload)
            self._remember_opencode_session(payload, result.session_id)
            self._reply(incoming, result.output, seed_suffix="opencode")
        except OpenCodeError as exc:
            logger.warning("OpenCode call failed: %s", exc)
            self._reply(incoming, f"OpenCode 调用失败：{exc}")
        except Exception as exc:
            logger.exception("Message handling failed")
            self._reply(incoming, f"处理失败：{exc}")
        finally:
            self._finish_processing_reactions(incoming, processing_reaction_id)

    def _run_opencode(self, incoming: IncomingEvent, payload: OpenCodePayload):
        model = self._state.get_current_model(self._settings.opencode_default_model)
        logger.info(
            "OpenCode prompt input topic_id=%s message_id=%s session_id=%s mode=%s messages=%d prompt:\n%s",
            payload.topic_id,
            incoming.message.message_id,
            payload.session_id or "(new)",
            payload.mode,
            payload.message_count,
            payload.prompt,
        )
        return self._opencode.run(
            payload.prompt,
            model=model,
            title=f"Feishu {payload.topic_id} {incoming.message.message_id}",
            session_id=payload.session_id,
        )

    def _remember_opencode_session(self, payload: OpenCodePayload, session_id: Optional[str]) -> None:
        if not session_id:
            return
        self._state.set_topic_session(
            payload.topic_id,
            session_id,
            payload.message_id,
            payload.create_time_ms,
        )

    def _reply(
        self,
        incoming: IncomingEvent,
        text: str,
        record: bool = True,
        seed_suffix: str = "reply",
    ) -> None:
        chunks = split_text(text, self._settings.reply_max_chars)
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            body = f"({index}/{total})\n{chunk}" if total > 1 else chunk
            reply_id = self._feishu.reply_text(
                incoming.message.message_id,
                body,
                uuid_seed=f"{incoming.event_id}:{seed_suffix}:{index}:{body}",
            )
            if record:
                self._record_assistant_reply(incoming, reply_id or f"{incoming.event_id}:{seed_suffix}:{index}", body)

    def _record_assistant_reply(self, incoming: IncomingEvent, message_id: str, text: str) -> None:
        now_ms = int(time.time() * 1000)
        self._state.append_message(
            incoming.message.topic_id,
            MessageRecord(
                message_id=message_id,
                chat_id=incoming.message.chat_id,
                topic_id=incoming.message.topic_id,
                thread_id=incoming.message.thread_id,
                root_id=incoming.message.root_id,
                parent_id=incoming.message.message_id,
                create_time_ms=now_ms,
                sender_id="feishu-opencode-bridge",
                sender_name="OpenCode",
                sender_type="app",
                message_type="text",
                text=text,
                source="assistant",
                sender_id_type="app_id",
            ),
        )

    def _add_processing_reaction(self, incoming: IncomingEvent) -> Optional[str]:
        return self._add_reaction(incoming, self._settings.processing_reaction_emoji)

    def _finish_processing_reactions(self, incoming: IncomingEvent, processing_reaction_id: Optional[str]) -> None:
        if processing_reaction_id:
            self._delete_reaction(incoming, processing_reaction_id)
        self._add_reaction(incoming, self._settings.done_reaction_emoji)

    def _add_reaction(self, incoming: IncomingEvent, emoji_type: Optional[str]) -> Optional[str]:
        if not emoji_type:
            return None
        try:
            reaction_id = self._feishu.add_reaction(incoming.message.message_id, emoji_type)
        except Exception as exc:
            logger.warning(
                "Feishu add reaction failed message_id=%s emoji_type=%s: %s",
                incoming.message.message_id,
                emoji_type,
                exc,
            )
            return None
        logger.info(
            "Feishu reaction added message_id=%s emoji_type=%s reaction_id=%s",
            incoming.message.message_id,
            emoji_type,
            reaction_id or "(empty)",
        )
        return reaction_id

    def _delete_reaction(self, incoming: IncomingEvent, reaction_id: str) -> None:
        try:
            self._feishu.delete_reaction(incoming.message.message_id, reaction_id)
        except Exception as exc:
            logger.warning(
                "Feishu delete reaction failed message_id=%s reaction_id=%s: %s",
                incoming.message.message_id,
                reaction_id,
                exc,
            )

    def _help_text(self) -> str:
        return self._commands.help_text()
