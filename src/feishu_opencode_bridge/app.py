from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from .card_ui import render_card_sender_page
from .cards import CardSendError, build_card_payload, send_webhook_payload
from .config import Settings
from .runtime import create_runtime

logger = logging.getLogger(__name__)


def _canonical_headers(headers) -> Dict[str, str]:
    result = {str(k): str(v) for k, v in headers.items()}
    lower = {str(k).lower(): str(v) for k, v in headers.items()}
    known = {
        "x-request-id": "X-Request-Id",
        "content-type": "Content-Type",
        "x-lark-request-timestamp": "X-Lark-Request-Timestamp",
        "x-lark-request-nonce": "X-Lark-Request-Nonce",
        "x-lark-signature": "X-Lark-Signature",
    }
    for lower_name, canonical in known.items():
        if lower_name in lower:
            result[canonical] = lower[lower_name]
    return result


def _is_local_request(request: Request) -> bool:
    host = getattr(request.client, "host", "") if request.client else ""
    return host in {"127.0.0.1", "::1", "localhost"} or host.startswith("127.")


def _local_only(request: Request) -> Optional[JSONResponse]:
    if _is_local_request(request):
        return None
    return JSONResponse({"ok": False, "error": "Card UI only accepts localhost requests"}, status_code=403)


def _mask_identifier(value: str) -> str:
    if len(value) <= 12:
        return "***"
    return f"{value[:6]}...{value[-6:]}"


def _card_uuid_seed(payload: Dict[str, object]) -> str:
    try:
        card = payload["card"]
        title = card["header"]["title"]["content"]  # type: ignore[index]
        markdown = card["elements"][0]["text"]["content"]  # type: ignore[index]
    except (KeyError, TypeError, IndexError):
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return f"card:{title}:{markdown}"


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or Settings.from_env()
    runtime = create_runtime(settings)

    app = FastAPI(title="Feishu OpenCode Bridge")
    app.state.settings = settings
    app.state.worker = runtime.worker
    app.state.event_handler = runtime.event_handler

    @app.on_event("startup")
    def _startup() -> None:
        runtime.worker.start()
        logger.info("Feishu OpenCode bridge started")

    @app.on_event("shutdown")
    def _shutdown() -> None:
        runtime.worker.stop()
        logger.info("Feishu OpenCode bridge stopped")

    @app.get("/healthz")
    def healthz() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/cards", response_class=HTMLResponse)
    def card_ui(request: Request) -> Response:
        blocked = _local_only(request)
        if blocked:
            return blocked
        return HTMLResponse(render_card_sender_page(settings))

    @app.post("/cards/send")
    async def send_card(request: Request) -> Response:
        blocked = _local_only(request)
        if blocked:
            return blocked
        try:
            data = await request.json()
            payload = build_card_payload(
                data.get("title"),
                data.get("markdown"),
                data.get("template"),
                buttons=data.get("buttons") or [],
            )
            result = await _send_card_payload(settings, runtime.feishu, payload, data)
        except (CardSendError, ValueError) as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
        except Exception as exc:
            logger.exception("Card send failed")
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
        return JSONResponse({"ok": True, "feishu": result, "payload": payload})

    @app.post("/feishu/events")
    async def feishu_events(request: Request) -> Response:
        from lark_oapi.core.model import RawRequest

        raw = RawRequest()
        raw.uri = request.url.path
        raw.headers = _canonical_headers(request.headers)
        raw.body = await request.body()
        logger.info("Feishu event callback received bytes=%d", len(raw.body or b""))
        raw_response = await asyncio.to_thread(runtime.event_handler.do, raw)
        return Response(
            content=raw_response.content or b"",
            status_code=raw_response.status_code or 200,
            headers=dict(raw_response.headers or {}),
        )

    return app


async def _send_card_payload(settings: Settings, feishu, payload: Dict[str, object], data: Dict[str, object]):
    if settings.card_sender_chat_id and not settings.card_sender_webhook:
        message_id = await asyncio.to_thread(
            feishu.send_interactive_card,
            settings.card_sender_chat_id,
            payload["card"],
            _card_uuid_seed(payload),
        )
        logger.info(
            "Card sent via app bot target_chat_id=%s message_id=%s. "
            "/cards/send does not call OpenCode; prompt logs appear after Feishu posts /feishu/events for an @ mention.",
            _mask_identifier(settings.card_sender_chat_id),
            message_id or "(none)",
        )
        return {"message_id": message_id, "target": "chat_id"}

    webhook = settings.card_sender_webhook or str(data.get("webhook") or "").strip()
    result = await asyncio.to_thread(send_webhook_payload, webhook, payload)
    logger.info(
        "Card sent via webhook. /cards/send does not call OpenCode; "
        "prompt logs appear after Feishu posts /feishu/events for an @ mention."
    )
    return result
