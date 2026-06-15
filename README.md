# Feishu OpenCode Bridge

Feishu OpenCode Bridge 是一个 Python 服务：当用户在飞书消息话题里 @ 机器人时，服务读取该话题上下文，调用本机 `opencode run`，再把结果回复回同一话题。

核心行为：

- 首次 @ 某个话题时，用可读取的话题上下文创建一个 OpenCode session。
- 后续同一话题复用同一个 OpenCode session，只把上次成功调用之后的新增消息发给 OpenCode。
- 普通话题回复不会立即触发机器人，但会在下一次 @ 机器人时作为增量上下文补给 OpenCode。
- 支持解析飞书 `interactive` 卡片正文、真实用户名、模型查看/切换、话题级 `/reset`。
- 附带本地 `/cards` 页面，用于发送测试卡片并验证卡片解析链路。

## 文档

- [用户使用文档](docs/user-guide.md)：日常使用、命令、多轮会话、卡片测试、日志观察。
- [飞书配置文档](docs/feishu-setup.md)：开放平台应用、权限、事件订阅、`.env` 全量配置。
- [开发者文档](docs/developer-guide.md)：模块边界、事件流、状态文件、扩展命令和测试。
- [运维排障文档](docs/operations.md)：启动方式、健康检查、日志、重启、常见问题。

## 快速启动

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

编辑 `.env`，至少填入：

```env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_VERIFICATION_TOKEN=xxx
```

确认 OpenCode 可用：

```bash
opencode --version
feishu-opencode-bridge check
```

启动 HTTP 回调服务：

```bash
feishu-opencode-bridge http
```

或启动飞书 WebSocket 长连接监听：

```bash
feishu-opencode-bridge ws
```

本地健康检查：

```bash
curl http://127.0.0.1:8000/healthz
```

本地卡片发送页面：

```text
http://127.0.0.1:8000/cards
```

## 开发检查

```bash
.venv/bin/pytest -q
.venv/bin/python -m compileall -q src tests
```

## 官方参考

- 飞书获取会话历史消息：https://open.feishu.cn/document/server-docs/im-v1/message/list
- 飞书获取指定消息内容：https://open.feishu.cn/document/server-docs/im-v1/message/get
- 飞书回复消息：https://open.feishu.cn/document/server-docs/im-v1/message/reply
- 飞书发送消息：https://open.feishu.cn/document/server-docs/im-v1/message/create
- OpenCode CLI：https://opencode.ai/docs/cli/
