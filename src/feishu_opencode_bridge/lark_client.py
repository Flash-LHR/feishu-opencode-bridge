from __future__ import annotations

import hashlib
import json
from typing import List, Optional

from .config import Settings
from .feishu_event import normalize_history_message
from .types import MessageRecord


class LarkApiError(RuntimeError):
    pass


class LarkClient:
    def __init__(self, settings: Settings) -> None:
        import lark_oapi as lark
        from lark_oapi.core.enum import LogLevel

        self._settings = settings
        self._lark = lark
        self._client = (
            lark.Client.builder()
            .app_id(settings.feishu_app_id)
            .app_secret(settings.feishu_app_secret)
            .domain(settings.feishu_domain)
            .log_level(LogLevel.WARNING)
            .source("feishu-opencode-bridge")
            .build()
        )

    def reply_text(self, message_id: str, text: str, uuid_seed: Optional[str] = None) -> Optional[str]:
        from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody

        content = json.dumps({"text": text}, ensure_ascii=False)
        seed = uuid_seed or f"{message_id}:{text}"
        uuid = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
        request = (
            ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .msg_type("text")
                .content(content)
                .reply_in_thread(True)
                .uuid(uuid)
                .build()
            )
            .build()
        )
        response = self._client.im.v1.message.reply(request)
        self._ensure_success(response, "reply message")
        return getattr(getattr(response, "data", None), "message_id", None)

    def add_reaction(self, message_id: str, emoji_type: str) -> Optional[str]:
        from lark_oapi.api.im.v1 import CreateMessageReactionRequest, CreateMessageReactionRequestBody, Emoji

        request = (
            CreateMessageReactionRequest.builder()
            .message_id(message_id)
            .request_body(
                CreateMessageReactionRequestBody.builder()
                .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
                .build()
            )
            .build()
        )
        response = self._client.im.v1.message_reaction.create(request)
        self._ensure_success(response, f"add reaction {emoji_type}")
        return getattr(getattr(response, "data", None), "reaction_id", None)

    def delete_reaction(self, message_id: str, reaction_id: str) -> None:
        from lark_oapi.api.im.v1 import DeleteMessageReactionRequest

        request = (
            DeleteMessageReactionRequest.builder()
            .message_id(message_id)
            .reaction_id(reaction_id)
            .build()
        )
        response = self._client.im.v1.message_reaction.delete(request)
        self._ensure_success(response, f"delete reaction {reaction_id}")

    def send_interactive_card(self, chat_id: str, card: dict, uuid_seed: Optional[str] = None) -> Optional[str]:
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

        seed = uuid_seed or json.dumps(card, ensure_ascii=False, sort_keys=True)
        uuid = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("interactive")
                .content(json.dumps(card, ensure_ascii=False))
                .uuid(uuid)
                .build()
            )
            .build()
        )
        response = self._client.im.v1.message.create(request)
        self._ensure_success(response, "send interactive card")
        return getattr(getattr(response, "data", None), "message_id", None)

    def list_thread_messages(self, thread_id: str, max_messages: int, page_limit: int) -> List[MessageRecord]:
        return self._list_messages("thread", thread_id, thread_id, max_messages, page_limit)

    def list_chat_messages(self, chat_id: str, topic_id: str, max_messages: int, page_limit: int) -> List[MessageRecord]:
        return self._list_messages("chat", chat_id, topic_id, max_messages, page_limit)

    def get_message(self, message_id: str, topic_id: str) -> Optional[MessageRecord]:
        if not message_id:
            return None
        from lark_oapi.api.im.v1 import GetMessageRequest

        request = (
            GetMessageRequest.builder()
            .message_id(message_id)
            .card_msg_content_type("raw")
            .build()
        )
        response = self._client.im.v1.message.get(request)
        self._ensure_success(response, "get message")
        items = getattr(getattr(response, "data", None), "items", None) or []
        if not items:
            return None
        return normalize_history_message(items[0], topic_id=topic_id)

    def get_user_display_name(self, user_id: str, user_id_type: Optional[str] = None) -> Optional[str]:
        if not user_id:
            return None
        resolved_type = user_id_type or _infer_user_id_type(user_id)
        name = self._get_basic_user_display_name(user_id, resolved_type)
        if name:
            return name
        from lark_oapi.api.contact.v3 import GetUserRequest

        request = GetUserRequest.builder().user_id_type(resolved_type).user_id(user_id).build()
        response = self._client.contact.v3.user.get(request)
        self._ensure_success(response, "get user")
        user = getattr(getattr(response, "data", None), "user", None)
        return _display_name_from_user(user)

    def get_chat_member_display_name(
        self,
        chat_id: str,
        user_id: str,
        user_id_type: Optional[str] = None,
    ) -> Optional[str]:
        if not chat_id or not user_id:
            return None
        from lark_oapi.api.im.v1 import GetChatMembersRequest

        resolved_type = _member_id_type(user_id_type or _infer_user_id_type(user_id))
        page_token = ""
        pages = 0
        while pages < 5:
            builder = (
                GetChatMembersRequest.builder()
                .chat_id(chat_id)
                .member_id_type(resolved_type)
                .page_size(100)
            )
            if page_token:
                builder.page_token(page_token)
            response = self._client.im.v1.chat_members.get(builder.build())
            self._ensure_success(response, "get chat members")
            data = getattr(response, "data", None)
            for item in getattr(data, "items", None) or []:
                if str(getattr(item, "member_id", "") or "") == user_id:
                    name = str(getattr(item, "name", "") or "").strip()
                    return name or None
            pages += 1
            if not getattr(data, "has_more", False):
                break
            page_token = getattr(data, "page_token", "") or ""
            if not page_token:
                break
        return None

    def _get_basic_user_display_name(self, user_id: str, user_id_type: str) -> Optional[str]:
        from lark_oapi.api.contact.v3 import BasicBatchUserRequest, BasicBatchUserRequestBody

        request = (
            BasicBatchUserRequest.builder()
            .user_id_type(user_id_type)
            .request_body(BasicBatchUserRequestBody.builder().user_ids([user_id]).build())
            .build()
        )
        response = self._client.contact.v3.user.basic_batch(request)
        try:
            self._ensure_success(response, "basic batch user")
        except LarkApiError:
            return None
        users = getattr(getattr(response, "data", None), "users", None) or []
        if not users:
            return None
        return _display_name_from_user(users[0])

    def _list_messages(
        self,
        container_id_type: str,
        container_id: str,
        topic_id: str,
        max_messages: int,
        page_limit: int,
    ) -> List[MessageRecord]:
        from lark_oapi.api.im.v1 import ListMessageRequest

        page_token = ""
        records: List[MessageRecord] = []
        pages = 0
        while pages < page_limit and len(records) < max_messages:
            builder = (
                ListMessageRequest.builder()
                .container_id_type(container_id_type)
                .container_id(container_id)
                .sort_type("ByCreateTimeAsc")
                .page_size(min(50, max_messages - len(records)))
                .card_msg_content_type("raw")
            )
            if page_token:
                builder.page_token(page_token)
            request = builder.build()
            response = self._client.im.v1.message.list(request)
            self._ensure_success(response, "list messages")
            data = getattr(response, "data", None)
            for item in getattr(data, "items", None) or []:
                records.append(normalize_history_message(item, topic_id=topic_id))
            pages += 1
            if not getattr(data, "has_more", False):
                break
            page_token = getattr(data, "page_token", "") or ""
            if not page_token:
                break
        return records[-max_messages:]

    @staticmethod
    def _ensure_success(response: object, action: str) -> None:
        success = getattr(response, "success", None)
        ok = success() if callable(success) else False
        if ok:
            return
        code = getattr(response, "code", None)
        msg = getattr(response, "msg", None)
        log_id = None
        get_log_id = getattr(response, "get_log_id", None)
        if callable(get_log_id):
            log_id = get_log_id()
        suffix = f", log_id={log_id}" if log_id else ""
        raise LarkApiError(f"Feishu {action} failed: code={code}, msg={msg}{suffix}")


def _display_name_from_user(user: object) -> Optional[str]:
    if user is None:
        return None
    for attr in ("name", "nickname", "en_name"):
        value = getattr(user, attr, None)
        if value:
            return str(value)
    return None


def build_event_handler(settings: Settings, submit) -> object:
    import lark_oapi as lark

    return (
        lark.EventDispatcherHandler.builder(
            settings.feishu_encrypt_key,
            settings.feishu_verification_token,
        )
        .register_p2_im_message_receive_v1(submit)
        .build()
    )


def _infer_user_id_type(user_id: str) -> str:
    if user_id.startswith("ou_"):
        return "open_id"
    if user_id.startswith("on_"):
        return "union_id"
    return "user_id"


def _member_id_type(user_id_type: str) -> str:
    if user_id_type in {"open_id", "union_id", "user_id"}:
        return user_id_type
    return "open_id"
