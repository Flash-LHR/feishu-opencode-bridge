# 开发者文档

## 代码结构

```text
src/feishu_opencode_bridge/
  app.py              FastAPI 路由：健康检查、飞书回调、卡片发送 API
  card_ui.py          本地 /cards 页面
  cards.py            飞书 interactive card payload 和 webhook 发送
  cli.py              命令行入口：http / ws / check
  commands.py         /help /ping /model /reset 命令处理
  config.py           .env 到 Settings 的解析
  feishu_event.py     飞书事件和历史消息归一化
  identity.py         当前机器人身份判断
  lark_client.py      lark-oapi 封装
  message_content.py  文本、post、interactive card 内容提取
  opencode.py         opencode CLI 封装
  ports.py            Feishu/OpenCode 端口协议
  prompt.py           OpenCode prompt 消息过滤和渲染
  runtime.py          依赖装配
  state.py            本地 JSON 状态存储
  topic_context.py    话题上下文收集和增量 cursor
  types.py            核心数据结构
  users.py            用户名解析和缓存
  worker.py           后台事件队列
```

## 事件处理流程

```text
Feishu event
  -> feishu_event.normalize_incoming_event
  -> StateStore.mark_event_seen 去重
  -> StateStore.append_message 缓存消息
  -> 非机器人消息且命中 @
  -> TopicLocks 按 topic_id 串行化
  -> 命令分支或 OpenCode 分支
```

OpenCode 分支：

```text
TopicContextBuilder.collect_messages
  -> 读取远端话题历史
  -> 合并本地缓存
  -> 必要时补取 root message
  -> 根据 session cursor 选择 full / incremental
PromptBuilder.input_messages
  -> 移除空消息、命令消息、机器人普通文本回复
PromptBuilder.render
  -> 人名：内容
OpenCodeClient.run
  -> opencode run [--session ...] [--model ...] --format json <prompt>
  -> 默认只取最后一个 text part 作为飞书回复
StateStore.set_topic_session
  -> 保存 session_id 和 last_sent_message_id
```

## OpenCode session 语义

状态文件里的 `sessions` 以 `topic_id` 为 key：

```json
{
  "sessions": {
    "omt_xxx": {
      "session_id": "ses_xxx",
      "last_sent_message_id": "om_xxx",
      "last_sent_at_ms": 1710000000000
    }
  }
}
```

第一次触发某个话题：

- `session_id` 为空。
- `mode=full`。
- prompt 包含可读取的话题上下文。

后续触发同一话题：

- `session_id=ses_xxx`。
- `mode=incremental`。
- prompt 只包含 `last_sent_message_id` 之后的消息。

如果找不到 `last_sent_message_id`，会退化为按 `last_sent_at_ms` 过滤。

## Prompt 格式

当前 prompt 是轻量格式：

```text
发送者：消息内容
发送者：消息内容
```

发送者由 `UserNameResolver` 决定：

1. 优先使用飞书历史消息里的 `sender_name`。
2. 然后查本地用户缓存。
3. 然后查群成员名称。
4. 然后查用户基本信息。
5. 最后退化为 `用户(open_id:ou_x...xxxx)`。

消息内容由 `message_content.py` 解析和清洗：

- `text`：取 `text` 字段。
- `post`：扁平化富文本。
- `interactive`：提取卡片标题、正文、按钮和 URL。
- 兼容提示“请升级至最新版本客户端，以查看内容”会被移除或替换为占位说明。

## 状态文件

默认路径：

```text
.feishu-opencode-bridge/state.json
```

顶层字段：

| 字段 | 说明 |
| --- | --- |
| `current_model` | `/model set` 设置的模型 |
| `seen_events` | 事件去重缓存 |
| `sessions` | 飞书话题到 OpenCode session 的绑定 |
| `threads` | 本地话题消息缓存 |
| `users` | 用户 ID 到显示名缓存 |

不要把状态文件提交到仓库。

## 增加命令

命令都在 `commands.py`。

增加一个命令通常需要：

1. 在 `CommandHandler.handle()` 增加分支。
2. 必要时新增私有方法处理参数。
3. 更新 `help_text()`。
4. 在 `tests/test_bot.py` 增加覆盖。
5. 更新 [用户使用文档](user-guide.md)。

命令返回 `CommandResponse`，由 `bot.py` 统一发送飞书回复。

## 增加 Feishu API

不要把 lark-oapi 细节散落到业务代码里。新增 API 时：

1. 在 `ports.py` 给 `FeishuGateway` 增加方法。
2. 在 `lark_client.py` 实现。
3. 测试里更新 `FakeFeishu`。
4. 在 [飞书配置文档](feishu-setup.md) 记录所需权限。

## 测试

运行全部测试：

```bash
.venv/bin/pytest -q
```

语法检查：

```bash
.venv/bin/python -m compileall -q src tests
```

重点测试文件：

- `tests/test_bot.py`：事件处理、命令、session、增量 prompt、用户名解析。
- `tests/test_message_content.py`：卡片和消息内容解析。
- `tests/test_cards.py`：卡片 payload 和 webhook 发送。

## 本地开发建议

开发时优先用 WebSocket 模式连飞书：

```bash
PYTHONPATH=src .venv/bin/python -m feishu_opencode_bridge ws
```

另开一个终端跑 HTTP 页面：

```bash
PYTHONPATH=src .venv/bin/python -m feishu_opencode_bridge http
```

改动核心逻辑后，至少跑：

```bash
.venv/bin/pytest -q tests/test_bot.py
```
