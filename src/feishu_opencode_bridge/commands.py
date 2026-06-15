from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import List, Optional

from .config import Settings
from .opencode import OpenCodeError
from .ports import OpenCodeGateway
from .state import StateStore
from .types import IncomingEvent

MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.:/@+-]+$")


@dataclass(frozen=True)
class CommandResponse:
    text: str
    seed_suffix: str = "reply"


class CommandHandler:
    def __init__(self, settings: Settings, state: StateStore, opencode: OpenCodeGateway) -> None:
        self._settings = settings
        self._state = state
        self._opencode = opencode

    def handle(self, incoming: IncomingEvent, text: str) -> CommandResponse:
        parts = self._split(text)
        command = parts[0].lower()
        args = parts[1:]

        if command in {"/help", "/帮助"}:
            return CommandResponse(self.help_text())
        if command == "/ping":
            return CommandResponse(self.status_text())
        if command == "/reset":
            self._state.clear_topic(incoming.message.topic_id)
            self._state.append_message(incoming.message.topic_id, incoming.message)
            return CommandResponse("已清除这个话题的本地缓存和 OpenCode session 绑定。")
        if command == "/model":
            return self._handle_model(args)
        return CommandResponse(f"未知命令：{command}\n\n{self.help_text()}")

    def status_text(self) -> str:
        current = self._state.get_current_model(self._settings.opencode_default_model)
        try:
            path = self._opencode.check_ready()
            opencode_status = f"可用：{path}"
        except OpenCodeError as exc:
            opencode_status = f"不可用：{exc}"
        return (
            "pong\n"
            f"当前模型：{current or '(OpenCode 默认模型)'}\n"
            f"OpenCode：{opencode_status}"
        )

    def help_text(self) -> str:
        return (
            "可用命令：\n"
            "/model 查看当前模型和可用模型\n"
            "/model set <provider/model> 切换模型\n"
            "/model refresh [provider] 刷新模型缓存\n"
            "/model clear 使用 OpenCode 默认模型\n"
            "/reset 清除本话题本地缓存\n"
            "/ping 检查服务和 OpenCode 状态"
        )

    def _handle_model(self, args: List[str]) -> CommandResponse:
        current = self._state.get_current_model(self._settings.opencode_default_model)
        if not args:
            try:
                models = self._opencode.list_models()
            except OpenCodeError as exc:
                models = f"获取模型列表失败：{exc}"
            return CommandResponse(
                f"当前模型：{current or '(OpenCode 默认模型)'}\n\n可用模型：\n{self._trim(models)}",
                seed_suffix="model-list",
            )

        action = args[0].lower()
        if action in {"set", "use", "切换"} and len(args) >= 2:
            return self._set_model(args[1])
        if action in {"clear", "reset", "默认"}:
            self._state.set_current_model(None)
            return CommandResponse("已清除模型覆盖，后续使用 OpenCode 默认模型。")
        if action == "refresh":
            provider = args[1] if len(args) >= 2 else None
            try:
                models = self._opencode.list_models(provider=provider, refresh=True)
            except OpenCodeError as exc:
                return CommandResponse(f"刷新模型列表失败：{exc}")
            return CommandResponse(f"当前模型：{current or '(OpenCode 默认模型)'}\n\n{self._trim(models)}")
        return self._list_provider_models(action, current)

    def _set_model(self, model: str) -> CommandResponse:
        model = model.strip()
        if not MODEL_NAME_RE.match(model):
            return CommandResponse("模型名应使用 provider/model 格式，例如 /model set anthropic/claude-sonnet-4-5")
        self._state.set_current_model(model)
        return CommandResponse(f"已切换当前模型：{model}")

    def _list_provider_models(self, provider: str, current: Optional[str]) -> CommandResponse:
        try:
            models = self._opencode.list_models(provider=provider)
        except OpenCodeError as exc:
            return CommandResponse(f"获取模型列表失败：{exc}")
        return CommandResponse(f"当前模型：{current or '(OpenCode 默认模型)'}\n\n{self._trim(models)}")

    def _trim(self, text: str) -> str:
        max_chars = self._settings.model_list_max_chars
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "\n...（已截断，使用 /model <provider> 缩小范围）"

    @staticmethod
    def _split(text: str) -> List[str]:
        try:
            return shlex.split(text)
        except ValueError:
            return text.split()
