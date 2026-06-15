# 用户使用文档

## 机器人做什么

机器人只处理两类消息：

- 群聊话题中明确 @ 机器人的消息。
- 单聊中直接发给机器人的消息。

在话题里第一次 @ 机器人时，服务会把当前可读取的话题上下文发给 OpenCode，并记录返回的 OpenCode session。之后同一话题继续 @ 机器人时，会复用该 session，只把新增消息发给 OpenCode。

## 多轮会话规则

假设一个飞书话题里有这些消息：

```text
机器人：告警
新加坡节点异常
李浩然：看看怎么回事
```

第一次 @ 机器人会创建 OpenCode session，prompt 包含话题主卡片和这次提问。

如果后面继续讨论：

```text
李浩然：哈哈
李浩然：我知道了
李浩然：是因为网络
李浩然：总结一下
```

下一次 @ 机器人时，prompt 只包含这几条新增消息，不会重复发送首轮已经进入 session 的话题主卡片。

## 命令

### `/help`

查看机器人支持的命令。

### `/ping`

检查服务和 OpenCode CLI 是否可用。返回内容包含当前模型和 OpenCode 可执行文件路径。

### `/model`

查看当前模型和 OpenCode 返回的可用模型列表。

### `/model set <provider/model>`

切换后续调用使用的模型，例如：

```text
/model set anthropic/claude-sonnet-4-5
```

也支持：

```text
/model use <provider/model>
/model 切换 <provider/model>
```

### `/model refresh [provider]`

刷新 OpenCode 模型缓存。可以指定 provider 缩小范围：

```text
/model refresh anthropic
```

### `/model clear`

清除模型覆盖，后续不传 `--model`，让 OpenCode 使用自己的默认模型。

### `/reset`

清除当前飞书话题的本地消息缓存和 OpenCode session 绑定。下一次 @ 机器人会重新创建 session。

## 卡片内容

机器人会尽量从飞书 `interactive` 卡片中提取可读文本，包括标题、正文、按钮文本和 URL。

如果飞书历史接口只返回：

```text
请升级至最新版本客户端，以查看内容
```

机器人不会把这句话当成真实告警内容，而是把上下文标记为：

```text
[飞书卡片正文未解析：飞书只返回了客户端兼容提示，请打开原卡片查看，或让告警机器人同时发送文本摘要]
```

这通常说明原卡片结构无法通过历史接口拿到完整正文。解决办法是让上游告警机器人使用兼容结构，或同时发送一份文本摘要。

## 本地卡片发送页面

启动 HTTP 服务后打开：

```text
http://127.0.0.1:8000/cards
```

用途：

- 发送一张测试卡片到配置好的飞书群。
- 验证卡片是否能进入话题上下文。
- 验证机器人后续 @ 时是否能解析卡片内容。

发送方式优先级：

1. 如果 `.env` 配置了 `CARD_SENDER_CHAT_ID` 且没有配置 `CARD_SENDER_WEBHOOK`，页面会用当前飞书应用机器人发送卡片。
2. 如果配置了 `CARD_SENDER_WEBHOOK`，页面走飞书自定义机器人 webhook。
3. 如果两者都没有配置，页面会要求临时填写 webhook。

`/cards/send` 只负责发卡片，不会调用 OpenCode。只有在飞书话题里 @ 机器人后，才会出现 OpenCode prompt 日志。

## 如何看日志

日志默认写到：

```text
.feishu-opencode-bridge/server.log
```

每次调用 OpenCode 前都会打印：

```text
OpenCode prompt input topic_id=... message_id=... session_id=... mode=... messages=... prompt:
```

字段含义：

- `session_id=(new)`：这次会创建新的 OpenCode session。
- `session_id=ses_xxx`：这次复用已有 OpenCode session。
- `mode=full`：首次触发，发送完整可读上下文。
- `mode=incremental`：后续触发，只发送新增消息。
- `messages=N`：本次 prompt 中的消息条数。

如果你在日志中只看到 `/cards/send`，说明只是发送了卡片，还没有在飞书话题里 @ 机器人。
