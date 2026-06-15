import json

from feishu_opencode_bridge.message_content import decode_message_text, split_text, strip_bot_mentions
from feishu_opencode_bridge.types import MentionRef


def test_decode_text_message():
    content = json.dumps({"text": "@_user_1 hello"}, ensure_ascii=False)
    assert decode_message_text("text", content) == "@_user_1 hello"


def test_decode_interactive_card_message_extracts_readable_text():
    content = json.dumps(
        {
            "schema": "2.0",
            "header": {
                "title": {"tag": "plain_text", "content": "部署通知"},
                "template": "blue",
            },
            "body": {
                "elements": [
                    {"tag": "markdown", "content": "**状态**：成功\n服务：bridge"},
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看详情"},
                        "behaviors": [{"type": "open_url", "default_url": "https://example.com/deploy"}],
                    },
                ]
            },
        },
        ensure_ascii=False,
    )

    assert decode_message_text("interactive", content) == (
        "部署通知\n"
        "**状态**：成功\n服务：bridge\n"
        "查看详情\n"
        "https://example.com/deploy"
    )


def test_decode_legacy_interactive_card_message_extracts_readable_text():
    content = json.dumps(
        {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": "部署通知"}, "template": "blue"},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": "**状态**：成功\n服务：bridge"}},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看详情"},
                            "url": "https://example.com/deploy",
                        }
                    ],
                },
            ],
        },
        ensure_ascii=False,
    )

    assert decode_message_text("interactive", content) == (
        "部署通知\n"
        "**状态**：成功\n服务：bridge\n"
        "查看详情\n"
        "https://example.com/deploy"
    )


def test_decode_interactive_card_removes_upgrade_fallback():
    content = json.dumps(
        {
            "title": "告警",
            "content": "请升级至最新版本客户端，以查看内容",
        },
        ensure_ascii=False,
    )

    assert decode_message_text("interactive", content) == (
        "告警\n"
        "[飞书卡片正文未解析：飞书只返回了客户端兼容提示，请打开原卡片查看，或让告警机器人同时发送文本摘要]"
    )


def test_strip_bot_mention_by_open_id():
    mention = MentionRef(key="@_user_1", name="Bot", mentioned_type="app", open_id="ou_bot")
    assert strip_bot_mentions("@_user_1 /ping", [mention], bot_open_id="ou_bot") == "/ping"


def test_split_text_respects_limit():
    chunks = split_text("a" * 10 + "\n" + "b" * 10, 12)
    assert chunks == ["a" * 10, "b" * 10]
