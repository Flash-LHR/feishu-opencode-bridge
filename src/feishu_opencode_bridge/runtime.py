from __future__ import annotations

from dataclasses import dataclass

from .bot import FeishuOpenCodeBot
from .config import Settings
from .lark_client import LarkClient, build_event_handler
from .opencode import OpenCodeClient
from .state import StateStore
from .worker import EventWorker


@dataclass(frozen=True)
class Runtime:
    feishu: LarkClient
    opencode: OpenCodeClient
    state: StateStore
    bot: FeishuOpenCodeBot
    worker: EventWorker
    event_handler: object


def create_runtime(settings: Settings) -> Runtime:
    feishu = LarkClient(settings)
    opencode = OpenCodeClient(
        settings.opencode_bin,
        settings.opencode_workdir,
        settings.opencode_timeout_seconds,
        agent=settings.opencode_agent,
        attach_url=settings.opencode_attach_url,
        skip_permissions=settings.opencode_skip_permissions,
    )
    state = StateStore(settings.state_path)
    bot = FeishuOpenCodeBot(settings, feishu, opencode, state)
    worker = EventWorker(bot.handle_raw_event, workers=settings.workers)
    event_handler = build_event_handler(settings, worker.submit)
    return Runtime(
        feishu=feishu,
        opencode=opencode,
        state=state,
        bot=bot,
        worker=worker,
        event_handler=event_handler,
    )
