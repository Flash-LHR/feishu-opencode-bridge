from __future__ import annotations

from typing import Any, Iterable, List, Optional

from .message_content import decode_message_text, replace_mention_keys, strip_bot_mentions
from .types import IncomingEvent, MentionRef, MessageRecord


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _user_id_value(user_id: Any, field: str) -> str:
    return str(_attr(user_id, field, "") or "")


def _sender_id_and_type(sender_id_obj: Any) -> tuple[str, str]:
    for field, id_type in (
        ("open_id", "open_id"),
        ("user_id", "user_id"),
        ("union_id", "union_id"),
        ("app_id", "app_id"),
    ):
        value = _user_id_value(sender_id_obj, field)
        if value:
            return value, id_type
    return "", ""


def mention_from_event(value: Any) -> MentionRef:
    user_id = _attr(value, "id")
    return MentionRef(
        key=str(_attr(value, "key", "") or ""),
        name=str(_attr(value, "name", "") or ""),
        mentioned_type=str(_attr(value, "mentioned_type", "") or ""),
        open_id=_user_id_value(user_id, "open_id"),
        user_id=_user_id_value(user_id, "user_id"),
        union_id=_user_id_value(user_id, "union_id"),
    )


def mention_from_message(value: Any) -> MentionRef:
    id_type = str(_attr(value, "id_type", "") or "")
    raw_id = str(_attr(value, "id", "") or "")
    return MentionRef(
        key=str(_attr(value, "key", "") or ""),
        name=str(_attr(value, "name", "") or ""),
        mentioned_type=id_type,
        open_id=raw_id if id_type == "open_id" else "",
        user_id=raw_id if id_type == "user_id" else "",
        union_id=raw_id if id_type == "union_id" else "",
    )


def _mention_matches_bot(
    mention: MentionRef,
    bot_open_id: Optional[str],
    bot_name: Optional[str],
) -> bool:
    if bot_open_id and mention.open_id == bot_open_id:
        return True
    if bot_name and mention.name == bot_name:
        return True
    if not bot_open_id and not bot_name and mention.mentioned_type.lower() in {"app", "bot"}:
        return True
    return False


def is_message_directed_at_bot(
    chat_type: str,
    mentions: Iterable[MentionRef],
    bot_open_id: Optional[str],
    bot_name: Optional[str],
    is_thread_message: bool = False,
) -> bool:
    if any(_mention_matches_bot(item, bot_open_id, bot_name) for item in mentions):
        return True
    return chat_type == "p2p" and not is_thread_message


def normalize_incoming_event(
    data: Any,
    bot_open_id: Optional[str] = None,
    bot_name: Optional[str] = None,
) -> IncomingEvent:
    event = _attr(data, "event")
    header = _attr(data, "header")
    event_message = _attr(event, "message")
    event_sender = _attr(event, "sender")
    sender_id_obj = _attr(event_sender, "sender_id")

    mentions = [mention_from_event(item) for item in (_attr(event_message, "mentions", []) or [])]
    message_type = str(_attr(event_message, "message_type", "") or "text")
    raw_text = decode_message_text(message_type, _attr(event_message, "content", ""))
    clean_text = strip_bot_mentions(raw_text, mentions, bot_open_id, bot_name)
    clean_text = replace_mention_keys(clean_text, mentions).strip()

    thread_id = str(_attr(event_message, "thread_id", "") or "")
    root_id = str(_attr(event_message, "root_id", "") or "")
    parent_id = str(_attr(event_message, "parent_id", "") or "")
    message_id = str(_attr(event_message, "message_id", "") or "")
    topic_id = thread_id or root_id or message_id

    sender_id, sender_id_type = _sender_id_and_type(sender_id_obj)
    chat_type = str(_attr(event_message, "chat_type", "") or "")
    message = MessageRecord(
        message_id=message_id,
        chat_id=str(_attr(event_message, "chat_id", "") or ""),
        topic_id=topic_id,
        thread_id=thread_id,
        root_id=root_id,
        parent_id=parent_id,
        create_time_ms=_int(_attr(event_message, "create_time", 0)),
        sender_id=sender_id,
        sender_name=sender_id or str(_attr(event_sender, "sender_type", "") or "unknown"),
        sender_type=str(_attr(event_sender, "sender_type", "") or ""),
        message_type=message_type,
        text=clean_text,
        mentions=mentions,
        sender_id_type=sender_id_type,
    )
    event_id = str(_attr(header, "event_id", "") or message_id)
    return IncomingEvent(
        event_id=event_id,
        message=message,
        chat_type=chat_type,
        raw_text=raw_text,
        clean_text=clean_text,
        is_mentioned=is_message_directed_at_bot(
            chat_type,
            mentions,
            bot_open_id,
            bot_name,
            is_thread_message=bool(thread_id or root_id or parent_id),
        ),
    )


def normalize_history_message(value: Any, topic_id: str = "") -> MessageRecord:
    body = _attr(value, "body")
    sender = _attr(value, "sender")
    mentions: List[MentionRef] = [mention_from_message(item) for item in (_attr(value, "mentions", []) or [])]
    message_type = str(_attr(value, "msg_type", "") or "text")
    text = decode_message_text(message_type, _attr(body, "content", ""))
    text = replace_mention_keys(text, mentions)
    thread_id = str(_attr(value, "thread_id", "") or "")
    root_id = str(_attr(value, "root_id", "") or "")
    message_id = str(_attr(value, "message_id", "") or "")
    return MessageRecord(
        message_id=message_id,
        chat_id=str(_attr(value, "chat_id", "") or ""),
        topic_id=topic_id or thread_id or root_id or message_id,
        thread_id=thread_id,
        root_id=root_id,
        parent_id=str(_attr(value, "parent_id", "") or ""),
        create_time_ms=_int(_attr(value, "create_time", 0)),
        sender_id=str(_attr(sender, "id", "") or ""),
        sender_name=str(_attr(sender, "sender_name", "") or _attr(sender, "id", "") or "unknown"),
        sender_type=str(_attr(sender, "sender_type", "") or ""),
        message_type=message_type,
        text=text,
        mentions=mentions,
        sender_id_type=str(_attr(sender, "id_type", "") or ""),
    )
