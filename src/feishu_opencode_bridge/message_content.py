from __future__ import annotations

import json
import re
from typing import Any, Iterable, List, Optional, Set

from .types import MentionRef

UNREADABLE_CARD_HINTS = {
    "请升级至最新版本客户端，以查看内容",
    "Please upgrade to the latest version to view this content",
}

UNREADABLE_CARD_PLACEHOLDER = (
    "[飞书卡片正文未解析：飞书只返回了客户端兼容提示，请打开原卡片查看，"
    "或让告警机器人同时发送文本摘要]"
)


def _json_loads(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _flatten_post_content(value: Any) -> str:
    parts: List[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            tag = node.get("tag")
            if tag == "at":
                user_name = node.get("user_name") or node.get("name") or node.get("text")
                if user_name:
                    parts.append(f"@{user_name}")
                return
            text = node.get("text")
            if isinstance(text, str):
                parts.append(text)
            for key in ("content", "children", "elements"):
                if key in node:
                    walk(node[key])
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    return "".join(parts).strip()


def _flatten_card_content(value: Any) -> str:
    parts: List[str] = []
    seen: Set[str] = set()
    text_keys = {
        "alt",
        "content",
        "default_url",
        "description",
        "ios_url",
        "label",
        "pc_url",
        "placeholder",
        "subtitle",
        "text",
        "title",
        "url",
        "value",
    }
    skip_string_keys = {
        "color",
        "icon_key",
        "mode",
        "schema",
        "size",
        "tag",
        "template",
        "type",
        "width",
    }

    def append(text: str) -> None:
        normalized = re.sub(r"[ \t\r\f\v]+", " ", text).strip()
        if not normalized or normalized in seen:
            return
        if _is_unreadable_card_hint(normalized):
            return
        seen.add(normalized)
        parts.append(normalized)

    def walk(node: Any, key_hint: str = "") -> None:
        if isinstance(node, str):
            if key_hint in text_keys:
                append(node)
            return
        if isinstance(node, list):
            for item in node:
                walk(item, key_hint)
            return
        if not isinstance(node, dict):
            return

        tag = str(node.get("tag") or "")
        if tag == "at":
            name = node.get("user_name") or node.get("name") or node.get("text") or node.get("id")
            if isinstance(name, str):
                append(f"@{name}")
            return

        for key, child in node.items():
            if isinstance(child, str):
                if key in text_keys:
                    append(child)
                elif key not in skip_string_keys and child.startswith(("http://", "https://")):
                    append(child)
                continue
            walk(child, key)

    walk(value)
    return "\n".join(parts).strip()


def _is_unreadable_card_hint(text: str) -> bool:
    normalized = re.sub(r"\s+", "", text).lower()
    for hint in UNREADABLE_CARD_HINTS:
        if re.sub(r"\s+", "", hint).lower() in normalized:
            return True
    return False


def _contains_unreadable_card_hint(value: Any) -> bool:
    if isinstance(value, str):
        return _is_unreadable_card_hint(value)
    if isinstance(value, list):
        return any(_contains_unreadable_card_hint(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_unreadable_card_hint(item) for item in value.values())
    return False


def clean_unreadable_card_fallback(text: str) -> str:
    lines = [line.strip() for line in str(text or "").splitlines()]
    kept = [line for line in lines if line and not _is_unreadable_card_hint(line)]
    had_fallback = len(kept) != len([line for line in lines if line])
    if not had_fallback:
        return str(text or "").strip()
    if not kept:
        return UNREADABLE_CARD_PLACEHOLDER
    return "\n".join(kept + [UNREADABLE_CARD_PLACEHOLDER]).strip()


def decode_message_text(message_type: str, content: Any) -> str:
    data = _json_loads(content)
    if isinstance(data, str):
        return clean_unreadable_card_fallback(data)

    if message_type == "text" and isinstance(data, dict):
        return clean_unreadable_card_fallback(str(data.get("text") or ""))

    if message_type == "post" and isinstance(data, dict):
        if "content" in data:
            return _flatten_post_content(data["content"])
        return _flatten_post_content(data)

    if message_type == "interactive" and isinstance(data, dict):
        had_unreadable_hint = _contains_unreadable_card_hint(data)
        card_text = _flatten_card_content(data)
        if card_text:
            cleaned = clean_unreadable_card_fallback(card_text)
            if had_unreadable_hint and UNREADABLE_CARD_PLACEHOLDER not in cleaned:
                return f"{cleaned}\n{UNREADABLE_CARD_PLACEHOLDER}".strip()
            return cleaned
        if had_unreadable_hint:
            return UNREADABLE_CARD_PLACEHOLDER
        return json.dumps(data, ensure_ascii=False, sort_keys=True)

    if isinstance(data, dict):
        for key in ("text", "title", "summary", "content"):
            value = data.get(key)
            if isinstance(value, str):
                return clean_unreadable_card_fallback(value)
        return json.dumps(data, ensure_ascii=False, sort_keys=True)

    if isinstance(data, list):
        return _flatten_post_content(data)

    return str(data or "").strip()


def replace_mention_keys(text: str, mentions: Iterable[MentionRef]) -> str:
    result = text
    for mention in mentions:
        if not mention.key:
            continue
        label = f"@{mention.name}" if mention.name else "@用户"
        result = result.replace(mention.key, label)
    return result


def strip_bot_mentions(
    text: str,
    mentions: Iterable[MentionRef],
    bot_open_id: Optional[str] = None,
    bot_name: Optional[str] = None,
) -> str:
    result = text
    for mention in mentions:
        is_bot = False
        if bot_open_id and mention.open_id == bot_open_id:
            is_bot = True
        if bot_name and mention.name == bot_name:
            is_bot = True
        if not bot_open_id and not bot_name and mention.mentioned_type.lower() in {"app", "bot"}:
            is_bot = True

        if is_bot and mention.key:
            result = result.replace(mention.key, "")
        if is_bot and mention.name:
            result = re.sub(rf"^\s*@{re.escape(mention.name)}\s*", "", result)

    if bot_name:
        result = re.sub(rf"^\s*@{re.escape(bot_name)}\s*", "", result)

    result = re.sub(r"<at\b[^>]*>.*?</at>", "", result)
    return result.strip()


def split_text(text: str, max_chars: int) -> List[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    remaining = text
    while len(remaining) > max_chars:
        cut = remaining.rfind("\n", 0, max_chars)
        if cut < max_chars // 2:
            cut = remaining.rfind("。", 0, max_chars)
        if cut < max_chars // 2:
            cut = max_chars
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks
