from __future__ import annotations

import argparse
import logging
import sys

import uvicorn

from .app import create_app
from .config import Settings
from .opencode import OpenCodeClient, OpenCodeError
from .runtime import create_runtime


def _configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not verbose:
        logging.getLogger("Lark").setLevel(logging.WARNING)


def _load_settings(args) -> Settings:
    return Settings.from_env(env_file=args.env_file)


def run_http(args) -> None:
    settings = _load_settings(args)
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


def run_ws(args) -> None:
    settings = _load_settings(args)
    runtime = create_runtime(settings)
    runtime.worker.start()
    try:
        from lark_oapi.core.enum import LogLevel
        from lark_oapi.ws import Client as WsClient

        client = WsClient(
            settings.feishu_app_id,
            settings.feishu_app_secret,
            log_level=LogLevel.WARNING,
            event_handler=runtime.event_handler,
            domain=settings.feishu_domain,
            source="feishu-opencode-bridge",
        )
        logging.getLogger(__name__).info("Feishu WebSocket listener started")
        client.start()
    finally:
        runtime.worker.stop()


def run_check(args) -> None:
    settings = _load_settings(args)
    print(f"Feishu app_id: {settings.feishu_app_id}")
    print(f"Feishu domain: {settings.feishu_domain}")
    print(f"State path: {settings.state_path}")
    print(f"OpenCode workdir: {settings.opencode_workdir}")

    try:
        import lark_oapi  # noqa: F401

        print("lark_oapi: ok")
    except Exception as exc:
        print(f"lark_oapi: failed: {exc}")
        raise SystemExit(1) from exc

    opencode = OpenCodeClient(
        settings.opencode_bin,
        settings.opencode_workdir,
        settings.opencode_timeout_seconds,
        agent=settings.opencode_agent,
        attach_url=settings.opencode_attach_url,
        skip_permissions=settings.opencode_skip_permissions,
        reply_full_output=settings.opencode_reply_full_output,
    )
    try:
        print(f"OpenCode: {opencode.check_ready()}")
    except OpenCodeError as exc:
        print(f"OpenCode: failed: {exc}")
        raise SystemExit(1) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bridge Feishu bot mentions to OpenCode.")
    parser.add_argument("--env-file", default=".env", help="dotenv file to load, default: .env")
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    subparsers = parser.add_subparsers(dest="command")

    http = subparsers.add_parser("http", help="run HTTP callback server")
    http.set_defaults(func=run_http)

    ws = subparsers.add_parser("ws", help="run Feishu websocket long-connection client")
    ws.set_defaults(func=run_ws)

    check = subparsers.add_parser("check", help="validate local configuration")
    check.set_defaults(func=run_check)

    parser.set_defaults(func=run_http)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    try:
        args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        logging.getLogger(__name__).exception("Command failed")
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
