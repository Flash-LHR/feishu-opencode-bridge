import json
from pathlib import Path

from feishu_opencode_bridge.bot import FeishuOpenCodeBot
from feishu_opencode_bridge.config import Settings
from feishu_opencode_bridge.opencode import OpenCodeError
from feishu_opencode_bridge.state import StateStore
from feishu_opencode_bridge.types import MessageRecord


class FakeFeishu:
    def __init__(self, thread_messages=None, user_names=None, chat_member_names=None, messages_by_id=None):
        self.replies = []
        self.reactions = []
        self.thread_messages = thread_messages or []
        self.user_names = user_names or {}
        self.chat_member_names = chat_member_names or {}
        self.messages_by_id = messages_by_id or {}

    def reply_text(self, message_id, text, uuid_seed=None):
        self.replies.append((message_id, text, uuid_seed))
        return f"reply-{len(self.replies)}"

    def add_reaction(self, message_id, emoji_type):
        reaction_id = f"reaction-{sum(1 for action, *_ in self.reactions if action == 'add') + 1}"
        self.reactions.append(("add", message_id, emoji_type, reaction_id))
        return reaction_id

    def delete_reaction(self, message_id, reaction_id):
        self.reactions.append(("delete", message_id, reaction_id))

    def send_interactive_card(self, chat_id, card, uuid_seed=None):
        return "card-message-id"

    def list_thread_messages(self, thread_id, max_messages, page_limit):
        return self.thread_messages

    def list_chat_messages(self, chat_id, topic_id, max_messages, page_limit):
        return []

    def get_message(self, message_id, topic_id):
        message = self.messages_by_id.get(message_id)
        if message is None:
            return None
        return MessageRecord(
            message_id=message.message_id,
            chat_id=message.chat_id,
            topic_id=topic_id or message.topic_id,
            thread_id=message.thread_id,
            root_id=message.root_id,
            parent_id=message.parent_id,
            create_time_ms=message.create_time_ms,
            sender_id=message.sender_id,
            sender_name=message.sender_name,
            sender_type=message.sender_type,
            message_type=message.message_type,
            text=message.text,
            mentions=message.mentions,
            source=message.source,
            sender_id_type=message.sender_id_type,
        )

    def get_user_display_name(self, user_id, user_id_type=None):
        return self.user_names.get(user_id)

    def get_chat_member_display_name(self, chat_id, user_id, user_id_type=None):
        return self.chat_member_names.get((chat_id, user_id)) or self.chat_member_names.get(user_id)


class FakeOpenCode:
    def __init__(self):
        self.prompts = []
        self.session_ids = []

    def check_ready(self):
        return "/usr/local/bin/opencode"

    def run(self, prompt, model, title=None, session_id=None):
        self.prompts.append((prompt, model, title))
        self.session_ids.append(session_id)
        return type("Result", (), {"output": "OpenCode answer", "returncode": 0, "session_id": session_id or "ses_test"})()

    def list_models(self, provider=None, refresh=False):
        return "openai/gpt-4.1\nanthropic/claude-sonnet-4-5"


class FailingOpenCode(FakeOpenCode):
    def run(self, prompt, model, title=None, session_id=None):
        self.prompts.append((prompt, model, title))
        self.session_ids.append(session_id)
        raise OpenCodeError("boom")


def _settings(path: Path) -> Settings:
    return Settings(
        feishu_app_id="cli",
        feishu_app_secret="secret",
        feishu_verification_token="token",
        feishu_encrypt_key="",
        feishu_domain="https://open.feishu.cn",
        feishu_bot_open_id="ou_bot",
        feishu_bot_name="Bot",
        host="0.0.0.0",
        port=8000,
        workers=1,
        state_path=path,
        context_max_messages=20,
        reply_max_chars=3800,
        history_page_limit=1,
        model_list_max_chars=8000,
        opencode_bin="opencode",
        opencode_default_model=None,
        opencode_workdir=Path("."),
        opencode_timeout_seconds=60,
        opencode_agent=None,
        opencode_attach_url=None,
        opencode_skip_permissions=False,
        send_processing_message=False,
        processing_reaction_emoji="Typing",
        done_reaction_emoji="DONE",
        card_sender_webhook=None,
        card_sender_chat_id=None,
    )


def _event(
    text: str,
    event_id: str = "evt1",
    *,
    mentioned: bool = True,
    chat_type: str = "group",
    thread_id: str = "thread-1",
    root_id: str = "",
    parent_id: str = "",
    sender_id=None,
    create_time: int = 1710000000000,
):
    sender_id = sender_id or {"open_id": "ou_user"}
    mentions = []
    if mentioned:
        mentions.append(
            {
                "key": "@_user_1",
                "id": {"open_id": "ou_bot"},
                "mentioned_type": "app",
                "name": "Bot",
            }
        )

    return {
        "header": {"event_id": event_id},
        "event": {
            "sender": {
                "sender_id": sender_id,
                "sender_type": "user",
            },
            "message": {
                "message_id": f"msg-{event_id}",
                "root_id": root_id,
                "parent_id": parent_id,
                "thread_id": thread_id,
                "chat_id": "chat-1",
                "chat_type": chat_type,
                "message_type": "text",
                "create_time": create_time,
                "content": json.dumps({"text": text}, ensure_ascii=False),
                "mentions": mentions,
            },
        },
    }


def _card_event(
    event_id: str = "evt-card",
    thread_id: str = "thread-1",
    sender_app_id: str = "cli_card_sender",
    create_time: int = 1710000000000,
):
    card = {
        "schema": "2.0",
        "header": {"title": {"tag": "plain_text", "content": "告警卡片"}, "template": "red"},
        "body": {
            "elements": [
                {"tag": "markdown", "content": "**服务异常**\n影响：OpenCode Bridge"},
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "查看详情"},
                    "behaviors": [{"type": "open_url", "default_url": "https://example.com/alert"}],
                },
            ]
        },
    }
    return {
        "header": {"event_id": event_id},
        "event": {
            "sender": {
                "sender_id": {"app_id": sender_app_id},
                "sender_type": "app",
            },
            "message": {
                "message_id": f"msg-{event_id}",
                "root_id": "",
                "parent_id": "",
                "thread_id": thread_id,
                "chat_id": "chat-1",
                "chat_type": "group",
                "message_type": "interactive",
                "create_time": create_time,
                "content": json.dumps(card, ensure_ascii=False),
                "mentions": [],
            },
        },
    }


def _fallback_card_event(event_id: str = "evt-card-fallback", thread_id: str = "thread-1"):
    card_fallback = {
        "title": "告警",
        "content": "请升级至最新版本客户端，以查看内容",
    }
    return {
        "header": {"event_id": event_id},
        "event": {
            "sender": {
                "sender_id": {"app_id": "cli_card_sender"},
                "sender_type": "app",
            },
            "message": {
                "message_id": f"msg-{event_id}",
                "root_id": "",
                "parent_id": "",
                "thread_id": thread_id,
                "chat_id": "chat-1",
                "chat_type": "group",
                "message_type": "interactive",
                "create_time": 1710000000000,
                "content": json.dumps(card_fallback, ensure_ascii=False),
                "mentions": [],
            },
        },
    }


def _root_card_message(message_id: str = "root-card", thread_id: str = "thread-1") -> MessageRecord:
    return MessageRecord(
        message_id=message_id,
        chat_id="chat-1",
        topic_id=thread_id,
        thread_id=thread_id,
        root_id="",
        parent_id="",
        create_time_ms=1709999999000,
        sender_id="cli",
        sender_name="app",
        sender_type="app",
        message_type="interactive",
        text="告警卡片\n**服务异常**\n影响：OpenCode Bridge",
    )


def test_model_set_command(tmp_path):
    feishu = FakeFeishu()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, FakeOpenCode(), state)

    bot.handle_raw_event(_event("@_user_1 /model set openai/gpt-4.1"))

    assert state.get_current_model() == "openai/gpt-4.1"
    assert "已切换当前模型" in feishu.replies[-1][1]
    assert not feishu.reactions


def test_first_opencode_call_includes_cached_topic_discussion(tmp_path):
    feishu = FakeFeishu(user_names={"ou_user": "李浩然"})
    opencode = FakeOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(_event("前面人工讨论", event_id="evt0", mentioned=False))
    bot.handle_raw_event(_event("@_user_1 帮我总结这个话题", event_id="evt1"))

    assert opencode.prompts
    assert opencode.prompts[0][0] == "李浩然：前面人工讨论\n李浩然：帮我总结这个话题"
    assert feishu.replies[-1][1] == "OpenCode answer"
    assert feishu.reactions == [
        ("add", "msg-evt1", "Typing", "reaction-1"),
        ("delete", "msg-evt1", "reaction-1"),
        ("add", "msg-evt1", "DONE", "reaction-2"),
    ]


def test_external_bot_card_is_cached_as_context_but_does_not_trigger(tmp_path):
    feishu = FakeFeishu(user_names={"ou_user": "李浩然"})
    opencode = FakeOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(_card_event(event_id="card"))
    bot.handle_raw_event(_event("@_user_1 总结这张卡片", event_id="evt1"))

    assert len(opencode.prompts) == 1
    assert opencode.prompts[0][0] == (
        "机器人：告警卡片\n"
        "**服务异常**\n影响：OpenCode Bridge\n"
        "查看详情\n"
        "https://example.com/alert\n"
        "李浩然：总结这张卡片"
    )


def test_own_app_interactive_card_is_kept_as_context(tmp_path):
    feishu = FakeFeishu(user_names={"ou_user": "李浩然"})
    opencode = FakeOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(_card_event(event_id="card", sender_app_id="cli"))
    bot.handle_raw_event(_event("@_user_1 总结这张卡片", event_id="evt1"))

    assert len(opencode.prompts) == 1
    assert opencode.prompts[0][0] == (
        "机器人：告警卡片\n"
        "**服务异常**\n影响：OpenCode Bridge\n"
        "查看详情\n"
        "https://example.com/alert\n"
        "李浩然：总结这张卡片"
    )


def test_external_bot_card_upgrade_fallback_is_not_sent_as_real_content(tmp_path):
    feishu = FakeFeishu(user_names={"ou_user": "李浩然"})
    opencode = FakeOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(_fallback_card_event(event_id="card"))
    bot.handle_raw_event(_event("@_user_1 看看怎么回事", event_id="evt1"))

    assert len(opencode.prompts) == 1
    assert "请升级至最新版本客户端" not in opencode.prompts[0][0]
    assert opencode.prompts[0][0] == (
        "机器人：告警\n"
        "[飞书卡片正文未解析：飞书只返回了客户端兼容提示，请打开原卡片查看，或让告警机器人同时发送文本摘要]\n"
        "李浩然：看看怎么回事"
    )


def test_processing_reaction_is_cleared_after_opencode_failure(tmp_path):
    feishu = FakeFeishu(user_names={"ou_user": "李浩然"})
    opencode = FailingOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(_event("@_user_1 处理一下", event_id="evt1"))

    assert "OpenCode 调用失败：boom" in feishu.replies[-1][1]
    assert feishu.reactions == [
        ("add", "msg-evt1", "Typing", "reaction-1"),
        ("delete", "msg-evt1", "reaction-1"),
        ("add", "msg-evt1", "DONE", "reaction-2"),
    ]


def test_topic_reuses_opencode_session_and_sends_incremental_messages(tmp_path):
    feishu = FakeFeishu(user_names={"ou_user": "李浩然"})
    opencode = FakeOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(_event("@_user_1 第一轮问题", event_id="evt1"))
    bot.handle_raw_event(_event("中间普通讨论", event_id="evt2", mentioned=False))
    bot.handle_raw_event(_event("@_user_1 第二轮问题", event_id="evt3"))

    assert opencode.session_ids == [None, "ses_test"]
    assert opencode.prompts[0][0] == "李浩然：第一轮问题"
    assert "第一轮问题" not in opencode.prompts[1][0]
    assert opencode.prompts[1][0] == "李浩然：中间普通讨论\n李浩然：第二轮问题"


def test_incremental_prompt_does_not_repeat_topic_root_card(tmp_path):
    root_card = _root_card_message()
    feishu = FakeFeishu(thread_messages=[root_card], user_names={"ou_user": "李浩然"})
    opencode = FakeOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(
        _event(
            "@_user_1 第一轮问题",
            event_id="evt1",
            root_id="root-card",
            create_time=1710000001000,
        )
    )
    bot.handle_raw_event(
        _event(
            "中间普通讨论",
            event_id="evt2",
            mentioned=False,
            root_id="root-card",
            create_time=1710000002000,
        )
    )
    bot.handle_raw_event(
        _event(
            "@_user_1 第二轮问题",
            event_id="evt3",
            root_id="root-card",
            create_time=1710000003000,
        )
    )

    assert opencode.session_ids == [None, "ses_test"]
    assert opencode.prompts[0][0] == (
        "机器人：告警卡片\n"
        "**服务异常**\n"
        "影响：OpenCode Bridge\n"
        "李浩然：第一轮问题"
    )
    assert "第一轮问题" not in opencode.prompts[1][0]
    assert opencode.prompts[1][0] == (
        "李浩然：中间普通讨论\n"
        "李浩然：第二轮问题"
    )


def test_root_message_is_fetched_when_thread_history_omits_it(tmp_path):
    root_card = _root_card_message()
    feishu = FakeFeishu(messages_by_id={"root-card": root_card}, user_names={"ou_user": "李浩然"})
    opencode = FakeOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(_event("@_user_1 看看告警", event_id="evt1", root_id="root-card"))

    assert opencode.prompts[0][0] == (
        "机器人：告警卡片\n"
        "**服务异常**\n"
        "影响：OpenCode Bridge\n"
        "李浩然：看看告警"
    )


def test_prompt_uses_feishu_sender_name_from_history_and_strips_bot_mention(tmp_path):
    remote_current = MessageRecord(
        message_id="msg-evt1",
        chat_id="chat-1",
        topic_id="thread-1",
        thread_id="thread-1",
        root_id="",
        parent_id="",
        create_time_ms=1710000000000,
        sender_id="ou_user",
        sender_name="李浩然",
        sender_type="user",
        message_type="text",
        text="@Bot 总结一下",
    )
    feishu = FakeFeishu(thread_messages=[remote_current])
    opencode = FakeOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(_event("@_user_1 总结一下", event_id="evt1"))

    assert opencode.prompts[0][0] == "李浩然：总结一下"


def test_prompt_resolves_sender_name_from_union_id(tmp_path):
    feishu = FakeFeishu(user_names={"on_user": "李浩然"})
    opencode = FakeOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(_event("@_user_1 看看怎么回事", event_id="evt1", sender_id={"union_id": "on_user"}))

    assert opencode.prompts[0][0] == "李浩然：看看怎么回事"


def test_prompt_resolves_sender_name_from_user_id(tmp_path):
    feishu = FakeFeishu(user_names={"tenant_user_1": "李浩然"})
    opencode = FakeOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(_event("@_user_1 看看怎么回事", event_id="evt1", sender_id={"user_id": "tenant_user_1"}))

    assert opencode.prompts[0][0] == "李浩然：看看怎么回事"


def test_prompt_resolves_sender_name_from_chat_member(tmp_path):
    user_id = "ou_f1f32e846ca931636ffffc78f9af624b"
    feishu = FakeFeishu(chat_member_names={("chat-1", user_id): "李浩然"})
    opencode = FakeOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(
        _event("@_user_1 看看怎么回事", event_id="evt1", sender_id={"open_id": user_id})
    )

    assert opencode.prompts[0][0] == "李浩然：看看怎么回事"


def test_prompt_keeps_distinguishable_user_label_without_name_permission(tmp_path):
    user_id = "ou_f1f32e846ca931636ffffc78f9af624b"
    feishu = FakeFeishu()
    opencode = FakeOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(
        _event("@_user_1 看看怎么回事", event_id="evt1", sender_id={"open_id": user_id})
    )

    assert opencode.prompts[0][0] == "用户(open_id:ou_f...624b)：看看怎么回事"


def test_context_command_is_removed(tmp_path):
    feishu = FakeFeishu()
    opencode = FakeOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(_event("@_user_1 /context", event_id="evt1"))

    assert not opencode.prompts
    assert "未知命令：/context" in feishu.replies[-1][1]
    assert "/context" not in bot._help_text()


def test_topic_reply_without_bot_mention_is_cached_but_not_triggered(tmp_path):
    feishu = FakeFeishu()
    opencode = FakeOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(
        _event(
            "这是话题里的普通讨论",
            mentioned=False,
            chat_type="p2p",
            thread_id="thread-1",
            parent_id="msg-parent",
        )
    )

    assert not opencode.prompts
    assert not feishu.replies
    assert state.get_cached_messages("thread-1")[-1].text == "这是话题里的普通讨论"


def test_direct_p2p_message_still_triggers_without_mention(tmp_path):
    feishu = FakeFeishu()
    opencode = FakeOpenCode()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, opencode, state)

    bot.handle_raw_event(
        _event(
            "/ping",
            mentioned=False,
            chat_type="p2p",
            thread_id="",
            root_id="",
            parent_id="",
        )
    )

    assert "pong" in feishu.replies[-1][1]


def test_duplicate_event_is_ignored(tmp_path):
    feishu = FakeFeishu()
    state = StateStore(tmp_path / "state.json")
    bot = FeishuOpenCodeBot(_settings(tmp_path / "state.json"), feishu, FakeOpenCode(), state)
    event = _event("@_user_1 /ping")

    bot.handle_raw_event(event)
    bot.handle_raw_event(event)

    assert len(feishu.replies) == 1
