from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, List, Optional


class CardSendError(RuntimeError):
    pass


TEMPLATES = {
    "blue",
    "wathet",
    "turquoise",
    "green",
    "yellow",
    "orange",
    "red",
    "carmine",
    "violet",
    "purple",
    "indigo",
    "grey",
}

BUTTON_TYPES = {"default", "primary", "danger"}


def _clean_text(value: Any, default: str, max_len: int) -> str:
    text = str(value or "").strip()
    if not text:
        text = default
    return text[:max_len]


def _clean_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        raise ValueError("按钮链接必须以 http:// 或 https:// 开头")
    return url


def _button_elements(buttons: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for item in list(buttons or [])[:3]:
        text = str(item.get("text") or "").strip()
        url = _clean_url(item.get("url"))
        if not text or not url:
            continue
        button_type = str(item.get("type") or "default").strip()
        if button_type not in BUTTON_TYPES:
            button_type = "default"
        result.append(
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": text[:40]},
                "type": button_type,
                "url": url,
            }
        )
    return result


def build_card_payload(
    title: Any,
    markdown: Any,
    template: Any = "blue",
    buttons: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    clean_title = _clean_text(title, "未命名卡片", 80)
    clean_markdown = _clean_text(markdown, " ", 12000)
    clean_template = str(template or "blue").strip()
    if clean_template not in TEMPLATES:
        clean_template = "blue"

    elements: List[Dict[str, Any]] = [
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": clean_markdown},
        }
    ]
    button_elements = _button_elements(buttons)
    if button_elements:
        elements.append({"tag": "action", "actions": button_elements})

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": clean_title},
                "template": clean_template,
            },
            "elements": elements,
        },
    }


def send_webhook_payload(webhook_url: str, payload: Dict[str, Any], timeout_seconds: float = 10.0) -> Dict[str, Any]:
    webhook = str(webhook_url or "").strip()
    if not webhook:
        raise CardSendError("请填写飞书自定义机器人 webhook，或在 .env 配置 CARD_SENDER_WEBHOOK")
    if not webhook.startswith(("https://", "http://")) or "/open-apis/bot/v2/hook/" not in webhook:
        raise CardSendError("无效的飞书自定义机器人 webhook，应类似 https://open.feishu.cn/open-apis/bot/v2/hook/...")

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise CardSendError(f"飞书 webhook HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CardSendError(f"飞书 webhook 请求失败：{exc.reason}") from exc

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CardSendError(f"飞书 webhook 返回了非 JSON 内容：{raw[:200]}") from exc

    code = result.get("code", result.get("StatusCode"))
    if code not in (0, "0", None):
        message = result.get("msg") or result.get("StatusMessage") or result
        raise CardSendError(f"飞书 webhook 返回失败：{message}")
    return result
