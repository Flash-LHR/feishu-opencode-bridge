# 运维排障文档

## 启动

HTTP 回调：

```bash
feishu-opencode-bridge http
```

WebSocket 长连接：

```bash
feishu-opencode-bridge ws
```

配置检查：

```bash
feishu-opencode-bridge check
```

健康检查：

```bash
curl http://127.0.0.1:8000/healthz
```

## 后台运行示例

开发机上可以用 `nohup`：

```bash
mkdir -p .feishu-opencode-bridge
nohup .venv/bin/python -m feishu_opencode_bridge http >> .feishu-opencode-bridge/server.log 2>&1 &
nohup .venv/bin/python -m feishu_opencode_bridge ws >> .feishu-opencode-bridge/server.log 2>&1 &
```

如果你的 shell 会清理子进程，使用 `launchd`、`systemd` 或进程管理器会更稳。

## 日志

推荐统一写入：

```text
.feishu-opencode-bridge/server.log
```

查看最近日志：

```bash
tail -n 200 .feishu-opencode-bridge/server.log
```

查 OpenCode 输入：

```bash
rg -n "OpenCode prompt input|session_id=|mode=" .feishu-opencode-bridge/server.log
```

典型日志：

```text
OpenCode prompt input topic_id=omt_xxx message_id=om_xxx session_id=(new) mode=full messages=3 prompt:
```

或：

```text
OpenCode prompt input topic_id=omt_xxx message_id=om_xxx session_id=ses_xxx mode=incremental messages=2 prompt:
```

## 重启

如果使用 pid 文件：

```bash
kill "$(cat .feishu-opencode-bridge/http.pid)" "$(cat .feishu-opencode-bridge/ws.pid)"
```

确认端口：

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

确认进程：

```bash
pgrep -fl "feishu_opencode_bridge|uvicorn|python.*feishu"
```

## 常见问题

### `/cards/send` 日志里没有 OpenCode prompt

正常。`/cards/send` 只发送卡片，不调用 OpenCode。需要在飞书话题里 @ 机器人，才会触发 OpenCode。

### 第二轮 prompt 不是全量

这是预期行为。第二轮如果日志显示：

```text
session_id=ses_xxx mode=incremental
```

说明 OpenCode session 已复用，prompt 只包含新增消息。

### 用户名显示为 `用户(open_id:...)`

说明真实姓名解析失败。检查：

- 是否开通 `im:chat.members:read`。
- 是否开通 `contact:user.basic_profile:readonly` 或通讯录基础读取权限。
- 权限数据范围是否包含该用户。
- 机器人是否在对应群里。

权限恢复后，新解析到的名字会写入 `state.json` 的 `users` 缓存。

### 卡片内容显示“卡片正文未解析”

飞书历史接口没有返回完整卡片内容。处理办法：

- 上游卡片使用旧版 interactive card 结构。
- 告警机器人同时发送文本摘要。
- 用本地 `/cards` 页面发一张测试卡片，确认当前服务对卡片解析是正常的。

### OpenCode 调用超时

检查：

- `OPENCODE_TIMEOUT_SECONDS` 是否太小。
- `OPENCODE_WORKDIR` 是否正确。
- 当前模型是否可用。
- 直接在终端执行同样的 `opencode run` 是否能完成。

### 重复回复

服务会用飞书 `event_id` 做 24 小时去重。如果仍重复，通常是：

- 同时跑了多个 WS/HTTP 实例。
- HTTP 回调和 WS 同时订阅同一个事件。
- 状态文件不是同一个 `BRIDGE_STATE_PATH`。

### 飞书回调失败

HTTP 模式检查：

- 回调 URL 是否是 `https://你的域名/feishu/events`。
- `FEISHU_VERIFICATION_TOKEN` 是否与开放平台一致。
- 如启用加密，`FEISHU_ENCRYPT_KEY` 是否一致。
- 代理是否保留 `X-Lark-*` 请求头。

### 表情 reaction 失败

检查是否开通消息表情回复权限。也可以在 `.env` 禁用：

```env
FEISHU_PROCESSING_REACTION_EMOJI=off
FEISHU_DONE_REACTION_EMOJI=off
```

## 安全注意事项

- 不要提交 `.env`。
- 不要提交 `.feishu-opencode-bridge/state.json` 和日志。
- `/cards` 和 `/cards/send` 默认只接受本机请求。
- `OPENCODE_SKIP_PERMISSIONS=true` 会跳过 OpenCode 权限确认，只建议在受控开发环境使用。
