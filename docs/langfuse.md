# Langfuse 接入文档

本文说明如何让 OpenCode 通过 Langfuse 官方 OpenCode Observability Plugin 上报 trace。桥接服务本身不直接调用 Langfuse；它调用 `opencode run`，由 OpenCode 在运行时加载插件并上报。

## 适用场景

接入后，可以在 Langfuse 里观察：

- 飞书话题触发的 OpenCode turn。
- OpenCode 内部的模型调用、工具调用、失败步骤和重试。
- 模型名、token 用量和成本统计，前提是上报数据里包含模型和用量，或 Langfuse 能按模型定义推断。

## 配置 OpenCode 插件

推荐使用全局 OpenCode 配置：

```bash
mkdir -p ~/.config/opencode
vim ~/.config/opencode/opencode.json
```

写入或合并以下配置：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "experimental": {
    "openTelemetry": true
  },
  "plugin": ["@langfuse/opencode-observability-plugin@latest"]
}
```

不需要手动执行 `npm install`。OpenCode 会在启动时按 `plugin` 数组里的 npm 包名自动安装并缓存插件。

如果只想让某个项目启用 Langfuse，也可以把同样配置写到项目级 `opencode.json` 或 `opencode.jsonc`。注意 OpenCode 会同时加载全局配置和项目配置里的插件，避免重复配置同一个插件。

## 配置 Langfuse 凭证

有两种方式。二选一即可。

### 方式一：放入本项目 `.env`

桥接服务启动时会加载项目 `.env`，`opencode run` 子进程会继承这些环境变量：

```env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASEURL=https://cloud.langfuse.com
LANGFUSE_ENVIRONMENT=production
LANGFUSE_USER_ID=feishu-opencode-bridge
```

`LANGFUSE_BASEURL` 必须和 key 所属区域一致：

```text
EU:    https://cloud.langfuse.com
US:    https://us.cloud.langfuse.com
Japan: https://jp.cloud.langfuse.com
HIPAA: https://hipaa.cloud.langfuse.com
```

如果通过 `systemd`、`launchd`、Docker 或其他进程管理器启动服务，确认实际启动目录和 `.env` 路径正确，或用 `feishu-opencode-bridge --env-file` 指定 dotenv 文件。

### 方式二：使用 OpenCode 的 Langfuse 配置文件

创建：

```bash
vim ~/.config/opencode/opencode-langfuse.json
```

内容：

```json
{
  "publicKey": "pk-lf-...",
  "secretKey": "sk-lf-...",
  "baseUrl": "https://cloud.langfuse.com",
  "environment": "production",
  "userId": "feishu-opencode-bridge"
}
```

只有 `publicKey` 和 `secretKey` 是必填项。`baseUrl` 省略时默认使用 `https://cloud.langfuse.com`，`environment` 省略时默认是 `development`。

如果同时设置了 `LANGFUSE_PUBLIC_KEY` 和 `LANGFUSE_SECRET_KEY`，插件会优先使用环境变量，而不是 `opencode-langfuse.json`。

## 重启服务

修改 OpenCode 配置或 Langfuse 凭证后，需要重启运行桥接服务的进程。HTTP 模式和 WebSocket 模式按实际部署方式重启即可：

```bash
feishu-opencode-bridge http
```

或：

```bash
feishu-opencode-bridge ws
```

不需要额外启动 `opencode web`。飞书消息触发后，桥接服务会调用 `opencode run`，插件会随 OpenCode 运行而加载。

## 验证接入

先确认 OpenCode 本身可用：

```bash
opencode --version
```

然后在飞书话题里 @ 机器人，等待一次完整回复。再到 Langfuse 项目里查看 trace。

可以同时观察桥接服务日志，确认确实触发了 OpenCode：

```bash
rg -n "OpenCode prompt input|session_id=|mode=" .feishu-opencode-bridge/server.log
```

Langfuse 里通常应能看到：

- 一个 turn trace。
- 一个或多个 generation。
- 工具调用 span。
- 配置的 `environment` 和 `userId` 标签。

## Token 成本统计

Langfuse 的成本统计依赖 generation 上的模型名和 token 用量。接入后先打开一条真实 trace，确认 generation 里的 `model` 字段长什么样，然后在 Langfuse 的 Project Settings -> Models 中配置对应模型价格。

建议：

- 按 Langfuse trace 里实际出现的模型名配置，不要只按本地命令里的别名猜。
- 如果同一类模型有不同前缀或供应商别名，可以用 Langfuse model definition 的 match pattern 做匹配。
- 如果上游没有上报 token 用量，Langfuse 可能会尝试推断；推理模型的 reasoning token 和缓存 token 可能无法完全准确，需要以实际 trace 为准。

## 隐私和安全

启用该插件后，OpenCode session telemetry 会发送到 Langfuse，包括用户输入、模型输出、reasoning、工具调用输入和工具输出。不要在不可信的 Langfuse 项目里开启，也不要把生产密钥提交到 Git。

建议：

- 不要提交 `.env`。
- 不要把 Langfuse secret key 写进仓库文件。
- 自建 Langfuse 时确认 `LANGFUSE_BASEURL` 指向可信实例。
- 如需临时排查敏感会话，先禁用插件或切换到隔离的 Langfuse 项目。

## 常见问题

### Langfuse 没有 trace

检查：

- `~/.config/opencode/opencode.json` 或项目 `opencode.json` 是否启用了 `experimental.openTelemetry: true`。
- `plugin` 是否包含 `@langfuse/opencode-observability-plugin@latest`。
- 桥接服务是否已重启。
- `LANGFUSE_PUBLIC_KEY` 是否以 `pk-lf-` 开头。
- `LANGFUSE_BASEURL` 是否和 key 所属区域一致。

### 插件没有安装

OpenCode npm 插件会在启动时自动安装。如果失败，通常是本机无法访问 npm registry，或者 OpenCode/Bun 环境异常。先直接运行一次：

```bash
opencode run "hello"
```

如果仍失败，检查 OpenCode 输出和本机网络。

### 成本为 0 或模型没匹配

先看 Langfuse trace 的 generation：

- 是否有 `model`。
- 是否有 token usage。
- `model` 名称是否和 Project Settings -> Models 里的定义完全匹配，或能被 match pattern 匹配。

## 官方参考

- Langfuse OpenCode integration: https://langfuse.com/integrations/developer-tools/opencode
- OpenCode plugins: https://opencode.ai/docs/plugins/
- Langfuse token and cost tracking: https://langfuse.com/docs/observability/features/token-and-cost-tracking
