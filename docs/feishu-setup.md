# 飞书配置文档

本文从零开始配置飞书开放平台应用。配置项名称可能随飞书后台 UI 调整，最终以开放平台页面展示为准。

## 1. 创建应用

1. 打开飞书开放平台：https://open.feishu.cn/
2. 创建一个企业自建应用。
3. 进入应用后台，记录：
   - `App ID`，写入 `.env` 的 `FEISHU_APP_ID`
   - `App Secret`，写入 `.env` 的 `FEISHU_APP_SECRET`
4. 在“事件与回调”或“安全设置”中找到 `Verification Token`，写入 `FEISHU_VERIFICATION_TOKEN`。
5. 如开启事件加密，把 `Encrypt Key` 写入 `FEISHU_ENCRYPT_KEY`；不启用则留空。

## 2. 开启机器人能力

1. 进入“添加应用能力”。
2. 添加“机器人”能力。
3. 设置机器人名称和头像。
4. 把应用机器人安装到测试企业或目标企业。
5. 把机器人拉进需要使用的群聊。

建议把机器人名称写到：

```env
FEISHU_BOT_NAME=你的机器人名
```

如果知道机器人的 open_id，也建议写入：

```env
FEISHU_BOT_OPEN_ID=ou_xxx
```

这可以避免同一群里存在多个应用机器人时误响应。

## 3. 选择监听方式

### WebSocket 长连接

本地开发推荐 WebSocket 模式，不需要公网回调地址：

```bash
feishu-opencode-bridge ws
```

开放平台仍需要订阅消息事件：

```text
p2.im.message.receive_v1
```

### HTTP 回调

生产环境可以使用 HTTP 回调：

```bash
feishu-opencode-bridge http
```

默认监听：

```text
0.0.0.0:8000
```

开放平台回调 URL 填：

```text
https://你的域名/feishu/events
```

本地调试可用内网穿透工具把 `127.0.0.1:8000` 暴露到公网。

## 4. 权限

机器人需要的权限来自实际调用的飞书 API。推荐在权限管理页面按“接口能力”搜索并开通。

| 能力 | 代码调用 | 用途 |
| --- | --- | --- |
| 接收消息事件 | `p2.im.message.receive_v1` | 监听群聊/单聊消息 |
| 获取会话历史消息 | `im.v1.message.list` | 读取同一话题历史 |
| 获取指定消息内容 | `im.v1.message.get` | 当历史缺少话题主消息时补取根消息 |
| 回复消息 | `im.v1.message.reply` | 把 OpenCode 结果回复到原话题 |
| 发送消息 | `im.v1.message.create` | `/cards` 使用应用机器人发送测试卡片 |
| 添加消息表情回复 | `im.v1.message_reaction.create` | 添加 `Typing` / `DONE` 状态 |
| 删除消息表情回复 | `im.v1.message_reaction.delete` | OpenCode 完成后移除 `Typing` |
| 查看群成员 | `im.v1.chat_members.get` | 解析群成员真实姓名 |
| 获取用户基本信息 | `contact.v3.user.basic_batch` / `contact.v3.user.get` | 解析用户真实姓名 |

在当前应用中已验证过的权限名包括：

```text
contact:user.basic_profile:readonly
im:chat.members:read
```

常见还需要开通的权限包括：

```text
im:message
im:message.reactions:write_only
contact:contact.base:readonly
```

如果开放平台提示“版本发布后生效”，正式应用需要创建并发布新版本；测试企业里通常可先直接验证。

## 5. 数据范围

权限开通后，还要检查“权限可访问的数据范围”：

- 通讯录相关权限建议设置为“与应用的可用范围一致”。
- 如果只能看到部分用户，用户名解析会退化成 `用户(open_id:ou_x...xxxx)`。
- 如果机器人不在某个群，通常无法读取该群消息。

## 6. `.env` 配置

完整示例见 [.env.example](../.env.example)。

### 必填

| 变量 | 说明 |
| --- | --- |
| `FEISHU_APP_ID` | 飞书应用 App ID |
| `FEISHU_APP_SECRET` | 飞书应用 App Secret |
| `FEISHU_VERIFICATION_TOKEN` | 飞书事件回调校验 token |

### 飞书可选项

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `FEISHU_ENCRYPT_KEY` | 空 | 事件加密 key |
| `FEISHU_BOT_OPEN_ID` | 空 | 机器人 open_id，用于精确识别 @ |
| `FEISHU_BOT_NAME` | 空 | 机器人名称，用于移除 prompt 中的 @ |
| `FEISHU_DOMAIN` | `https://open.feishu.cn` | 飞书中国租户使用默认值，Lark 国际租户可改为 `https://open.larksuite.com` |
| `FEISHU_PROCESSING_REACTION_EMOJI` | `Typing` | 处理中表情；设为 `off` 可禁用 |
| `FEISHU_DONE_REACTION_EMOJI` | `DONE` | 完成表情；设为 `off` 可禁用 |

### 服务配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `BRIDGE_HOST` | `0.0.0.0` | HTTP 监听地址 |
| `BRIDGE_PORT` | `8000` | HTTP 监听端口 |
| `BRIDGE_WORKERS` | `2` | 后台事件处理线程数 |
| `BRIDGE_STATE_PATH` | `.feishu-opencode-bridge/state.json` | 本地状态文件 |
| `BRIDGE_CONTEXT_MAX_MESSAGES` | `80` | 每次最多读取/缓存的话题消息数 |
| `BRIDGE_REPLY_MAX_CHARS` | `3800` | 飞书回复分片长度 |
| `BRIDGE_HISTORY_PAGE_LIMIT` | `5` | 读取历史消息页数上限 |
| `BRIDGE_MODEL_LIST_MAX_CHARS` | `8000` | `/model` 返回模型列表最大长度 |
| `BRIDGE_SEND_PROCESSING_MESSAGE` | `false` | 是否额外发送“正在处理”文本消息 |

### OpenCode 配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `OPENCODE_BIN` | `opencode` | OpenCode 可执行文件 |
| `OPENCODE_DEFAULT_MODEL` | 空 | 默认模型；为空则不传 `--model` |
| `OPENCODE_WORKDIR` | `.` | OpenCode 执行目录 |
| `OPENCODE_TIMEOUT_SECONDS` | `900` | 单次调用超时时间 |
| `OPENCODE_AGENT` | 空 | 传给 `opencode run --agent` |
| `OPENCODE_ATTACH_URL` | 空 | 传给 `opencode run --attach` |
| `OPENCODE_SKIP_PERMISSIONS` | `false` | 是否传 `--dangerously-skip-permissions` |

### 卡片发送页面

| 变量 | 说明 |
| --- | --- |
| `CARD_SENDER_CHAT_ID` | 使用应用机器人直接把 `/cards` 卡片发到这个群 |
| `CARD_SENDER_WEBHOOK` | 使用飞书自定义机器人 webhook 发送 `/cards` 卡片 |

如果两者都配置，当前实现优先走 webhook。建议测试应用机器人发送链路时只配置 `CARD_SENDER_CHAT_ID`。

## 7. 验证

```bash
feishu-opencode-bridge check
feishu-opencode-bridge ws
```

在飞书群里发送：

```text
@机器人 /ping
```

如果收到 `pong`，说明消息事件、回复权限和 OpenCode 检查链路可用。

再发送：

```text
@机器人 /model
```

如果能列出模型，说明 OpenCode CLI 可正常运行。
