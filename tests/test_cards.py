import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from feishu_opencode_bridge.cards import build_card_payload, send_webhook_payload


def test_build_card_payload_with_button():
    payload = build_card_payload(
        "发布通知",
        "**状态**：成功",
        "green",
        buttons=[{"text": "查看详情", "url": "https://example.com/detail", "type": "primary"}],
    )

    assert payload["msg_type"] == "interactive"
    card = payload["card"]
    assert "schema" not in card
    assert card["config"]["wide_screen_mode"] is True
    assert card["header"]["title"]["content"] == "发布通知"
    assert card["header"]["template"] == "green"
    assert card["elements"][0]["text"]["content"] == "**状态**：成功"
    assert card["elements"][1]["actions"][0]["text"]["content"] == "查看详情"
    assert card["elements"][1]["actions"][0]["url"] == "https://example.com/detail"


def test_build_card_payload_rejects_bad_button_url():
    with pytest.raises(ValueError):
        build_card_payload("标题", "内容", buttons=[{"text": "打开", "url": "javascript:alert(1)"}])


def test_send_webhook_payload_rejects_empty_webhook():
    with pytest.raises(Exception) as exc:
        send_webhook_payload("", build_card_payload("标题", "内容"))

    assert "请填写飞书自定义机器人 webhook" in str(exc.value)


def test_send_webhook_payload_posts_card_json_to_webhook():
    received = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            received["path"] = self.path
            received["content_type"] = self.headers.get("Content-Type")
            received["body"] = json.loads(self.rfile.read(length).decode("utf-8"))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"code":0,"msg":"success"}')

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/open-apis/bot/v2/hook/test"
        payload = build_card_payload("标题", "内容")

        result = send_webhook_payload(url, payload)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)

    assert result["code"] == 0
    assert received["path"] == "/open-apis/bot/v2/hook/test"
    assert received["content_type"].startswith("application/json")
    assert received["body"]["msg_type"] == "interactive"
    assert received["body"]["card"]["header"]["title"]["content"] == "标题"
