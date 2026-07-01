from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dependency is installed in normal use.
    load_dotenv = None


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {value!r}") from exc


def _get_path(name: str, default: str) -> Path:
    return Path(os.getenv(name, default)).expanduser()


def _get_optional(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _get_optional_default(name: str, default: Optional[str]) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    if value.lower() in {"0", "false", "no", "none", "off", "disabled"}:
        return None
    return value or None


def _get_csv(name: str, default: str = "") -> List[str]:
    value = os.getenv(name, default).strip()
    if not value or value.lower() in {"0", "false", "no", "none", "off", "disabled"}:
        return []
    return [item.strip().lower() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    feishu_app_id: str
    feishu_app_secret: str
    feishu_verification_token: str
    feishu_encrypt_key: str
    feishu_domain: str
    feishu_bot_open_id: Optional[str]
    feishu_bot_name: Optional[str]

    host: str
    port: int
    workers: int
    state_path: Path

    context_max_messages: int
    reply_max_chars: int
    history_page_limit: int
    model_list_max_chars: int

    opencode_bin: str
    opencode_default_model: Optional[str]
    opencode_workdir: Path
    opencode_timeout_seconds: float
    opencode_agent: Optional[str]
    opencode_attach_url: Optional[str]
    opencode_skip_permissions: bool
    opencode_reply_full_output: bool

    send_processing_message: bool
    processing_reaction_emoji: Optional[str]
    done_reaction_emoji: Optional[str]
    auto_trigger_without_mention: bool
    auto_trigger_prompt: Optional[str]
    auto_ignore_severities: List[str]
    auto_ignore_keywords: List[str]
    auto_daily_limit: int
    auto_daily_limit_timezone: str
    auto_reuse_window_seconds: int
    card_sender_webhook: Optional[str] = None
    card_sender_chat_id: Optional[str] = None

    @classmethod
    def from_env(cls, env_file: Optional[str] = ".env") -> "Settings":
        if env_file and load_dotenv is not None:
            load_dotenv(env_file)

        app_id = os.getenv("FEISHU_APP_ID", "").strip()
        app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
        verification_token = os.getenv("FEISHU_VERIFICATION_TOKEN", "").strip()
        if not app_id:
            raise ValueError("FEISHU_APP_ID is required")
        if not app_secret:
            raise ValueError("FEISHU_APP_SECRET is required")
        if not verification_token:
            raise ValueError("FEISHU_VERIFICATION_TOKEN is required")

        return cls(
            feishu_app_id=app_id,
            feishu_app_secret=app_secret,
            feishu_verification_token=verification_token,
            feishu_encrypt_key=os.getenv("FEISHU_ENCRYPT_KEY", "").strip(),
            feishu_domain=os.getenv("FEISHU_DOMAIN", "https://open.feishu.cn").strip(),
            feishu_bot_open_id=_get_optional("FEISHU_BOT_OPEN_ID"),
            feishu_bot_name=_get_optional("FEISHU_BOT_NAME"),
            host=os.getenv("BRIDGE_HOST", "0.0.0.0").strip(),
            port=_get_int("BRIDGE_PORT", 8000),
            workers=max(1, _get_int("BRIDGE_WORKERS", 2)),
            state_path=_get_path("BRIDGE_STATE_PATH", ".feishu-opencode-bridge/state.json"),
            context_max_messages=max(1, _get_int("BRIDGE_CONTEXT_MAX_MESSAGES", 80)),
            reply_max_chars=max(500, _get_int("BRIDGE_REPLY_MAX_CHARS", 3800)),
            history_page_limit=max(1, _get_int("BRIDGE_HISTORY_PAGE_LIMIT", 5)),
            model_list_max_chars=max(1000, _get_int("BRIDGE_MODEL_LIST_MAX_CHARS", 8000)),
            opencode_bin=os.getenv("OPENCODE_BIN", "opencode").strip(),
            opencode_default_model=_get_optional("OPENCODE_DEFAULT_MODEL"),
            opencode_workdir=_get_path("OPENCODE_WORKDIR", "."),
            opencode_timeout_seconds=max(1.0, _get_float("OPENCODE_TIMEOUT_SECONDS", 900)),
            opencode_agent=_get_optional("OPENCODE_AGENT"),
            opencode_attach_url=_get_optional("OPENCODE_ATTACH_URL"),
            opencode_skip_permissions=_get_bool("OPENCODE_SKIP_PERMISSIONS", False),
            opencode_reply_full_output=_get_bool("OPENCODE_REPLY_FULL_OUTPUT", False),
            send_processing_message=_get_bool("BRIDGE_SEND_PROCESSING_MESSAGE", False),
            processing_reaction_emoji=_get_optional_default("FEISHU_PROCESSING_REACTION_EMOJI", "Typing"),
            done_reaction_emoji=_get_optional_default("FEISHU_DONE_REACTION_EMOJI", "DONE"),
            auto_trigger_without_mention=_get_bool("BRIDGE_AUTO_TRIGGER_WITHOUT_MENTION", False),
            auto_trigger_prompt=_get_optional_default(
                "BRIDGE_AUTO_TRIGGER_PROMPT",
                (
                    "请作为 oncall 助手处理下面这条飞书消息或告警。"
                    "如果这是告警，请给出结论、影响、证据和建议动作；"
                    "如果信息不足，请明确还需要什么。"
                ),
            ),
            auto_ignore_severities=_get_csv("BRIDGE_AUTO_IGNORE_SEVERITIES"),
            auto_ignore_keywords=_get_csv("BRIDGE_AUTO_IGNORE_KEYWORDS"),
            auto_daily_limit=max(0, _get_int("BRIDGE_AUTO_DAILY_LIMIT", 0)),
            auto_daily_limit_timezone=os.getenv("BRIDGE_AUTO_DAILY_LIMIT_TIMEZONE", "Asia/Shanghai").strip(),
            auto_reuse_window_seconds=max(0, _get_int("BRIDGE_AUTO_REUSE_WINDOW_SECONDS", 86400)),
            card_sender_webhook=_get_optional("CARD_SENDER_WEBHOOK"),
            card_sender_chat_id=_get_optional("CARD_SENDER_CHAT_ID"),
        )
