from __future__ import annotations

import json

from .config import Settings


def render_card_sender_page(settings: Settings) -> str:
    config_json = json.dumps(
        {
            "webhookConfigured": bool(settings.card_sender_webhook),
            "chatConfigured": bool(settings.card_sender_chat_id),
            "templates": [
                "blue",
                "wathet",
                "turquoise",
                "green",
                "yellow",
                "orange",
                "red",
                "purple",
                "grey",
            ],
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")
    return _HTML.replace("__CONFIG__", config_json)


_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Card Sender</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #fff;
      --line: #d8dde6;
      --line-strong: #bdc6d3;
      --text: #18202d;
      --muted: #667085;
      --blue: #246bfe;
      --blue-strong: #1554d1;
      --danger: #c0342b;
      --ok: #14804a;
      --shadow: 0 18px 42px rgba(28, 39, 60, .14);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); }
    header {
      height: 56px; display: flex; align-items: center; justify-content: space-between;
      padding: 0 20px; border-bottom: 1px solid var(--line); background: rgba(255,255,255,.92);
      position: sticky; top: 0; z-index: 2;
    }
    .brand { display: flex; align-items: center; gap: 10px; min-width: 0; }
    .mark { width: 28px; height: 28px; border-radius: 6px; display: grid; place-items: center; background: var(--blue); color: #fff; font-weight: 700; }
    h1 { margin: 0; font-size: 16px; line-height: 1.2; font-weight: 700; letter-spacing: 0; }
    .status { color: var(--muted); font-size: 13px; white-space: nowrap; }
    main { display: grid; grid-template-columns: minmax(360px, 480px) minmax(0, 1fr); min-height: calc(100vh - 56px); }
    .editor, .preview { padding: 18px; }
    .editor { border-right: 1px solid var(--line); background: #fbfcfe; }
    .field { margin-bottom: 14px; }
    label { display: block; font-size: 12px; line-height: 1.4; color: #394150; font-weight: 650; margin-bottom: 6px; }
    input, select, textarea {
      width: 100%; border: 1px solid var(--line-strong); background: #fff; color: var(--text);
      border-radius: 6px; padding: 9px 10px; font: inherit; font-size: 14px; letter-spacing: 0; outline: none;
    }
    textarea { min-height: 250px; resize: vertical; line-height: 1.5; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    input:focus, select:focus, textarea:focus { border-color: var(--blue); box-shadow: 0 0 0 3px rgba(36,107,254,.14); }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .actions { display: flex; align-items: center; gap: 10px; margin-top: 18px; }
    button {
      height: 36px; border: 1px solid var(--line-strong); background: #fff; color: var(--text);
      border-radius: 6px; padding: 0 14px; font: inherit; font-size: 14px; cursor: pointer; white-space: nowrap;
    }
    button.primary { background: var(--blue); border-color: var(--blue); color: #fff; font-weight: 650; }
    button.primary:hover { background: var(--blue-strong); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .message { min-height: 20px; color: var(--muted); font-size: 13px; line-height: 1.45; }
    .message.error { color: var(--danger); }
    .message.ok { color: var(--ok); }
    .preview { display: grid; grid-template-rows: auto minmax(0, 1fr); gap: 14px; min-width: 0; }
    .tabs { display: flex; gap: 8px; border-bottom: 1px solid var(--line); }
    .tab { border: 0; border-bottom: 2px solid transparent; border-radius: 0; background: transparent; color: var(--muted); padding: 0 4px 10px; height: auto; }
    .tab.active { border-bottom-color: var(--blue); color: var(--text); font-weight: 650; }
    .pane { min-height: 0; overflow: auto; }
    .feishu-card { width: min(680px, 100%); background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; box-shadow: var(--shadow); }
    .card-header { padding: 13px 14px; color: #fff; font-weight: 700; line-height: 1.35; word-break: break-word; }
    .card-body { padding: 14px; white-space: pre-wrap; line-height: 1.55; font-size: 14px; word-break: break-word; }
    .card-button {
      display: inline-flex; align-items: center; max-width: calc(100% - 28px); margin: 0 14px 14px;
      height: 34px; padding: 0 12px; border-radius: 6px; background: #eef4ff; color: #1d4ed8;
      font-size: 14px; font-weight: 650; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    pre { margin: 0; padding: 14px; background: #101828; color: #e7edf7; border-radius: 8px; min-height: 420px; overflow: auto; font-size: 12px; line-height: 1.55; }
    .theme-blue { background: #246bfe; }
    .theme-wathet { background: #2f8acb; }
    .theme-turquoise { background: #08979c; }
    .theme-green { background: #2a7f46; }
    .theme-yellow { background: #a46a00; }
    .theme-orange { background: #c75c00; }
    .theme-red { background: #c0342b; }
    .theme-purple { background: #7b3fe4; }
    .theme-grey { background: #4b5563; }
    @media (max-width: 860px) {
      header { align-items: flex-start; height: auto; gap: 8px; flex-direction: column; padding: 12px 14px; }
      main { grid-template-columns: 1fr; }
      .editor { border-right: 0; border-bottom: 1px solid var(--line); }
      .grid-2 { grid-template-columns: 1fr; }
      .actions { flex-wrap: wrap; }
    }
  </style>
</head>
<body>
  <header>
    <div class="brand"><div class="mark">C</div><h1>Card Sender</h1></div>
    <div class="status" id="webhookStatus"></div>
  </header>
  <main>
    <section class="editor">
      <div class="field" id="webhookField">
        <label for="webhook">Webhook</label>
        <input id="webhook" autocomplete="off" spellcheck="false" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/...">
      </div>
      <div class="grid-2">
        <div class="field"><label for="title">标题</label><input id="title" maxlength="80" value="Card Sender 测试卡片"></div>
        <div class="field"><label for="template">主题</label><select id="template"></select></div>
      </div>
      <div class="field">
        <label for="markdown">内容</label>
        <textarea id="markdown" spellcheck="false">**卡片内容**&#10;&#10;这里可以编辑 Markdown 文本。</textarea>
      </div>
      <div class="grid-2">
        <div class="field"><label for="buttonText">按钮文本</label><input id="buttonText" maxlength="40" value="查看详情"></div>
        <div class="field"><label for="buttonUrl">按钮链接</label><input id="buttonUrl" spellcheck="false" placeholder="https://example.com"></div>
      </div>
      <div class="actions">
        <button class="primary" id="sendBtn">发送卡片</button>
        <button id="copyBtn">复制 JSON</button>
        <span class="message" id="message"></span>
      </div>
    </section>
    <section class="preview">
      <div class="tabs">
        <button class="tab active" data-tab="visual">预览</button>
        <button class="tab" data-tab="json">JSON</button>
      </div>
      <div class="pane" id="visualPane">
        <div class="feishu-card">
          <div class="card-header theme-blue" id="previewTitle"></div>
          <div class="card-body" id="previewBody"></div>
          <div class="card-button" id="previewButton"></div>
        </div>
      </div>
      <div class="pane" id="jsonPane" hidden><pre id="jsonPreview"></pre></div>
    </section>
  </main>
  <script>
    const CONFIG = __CONFIG__;
    const $ = (id) => document.getElementById(id);
    const fields = ["webhook", "title", "template", "markdown", "buttonText", "buttonUrl"];
    const storageKey = "feishu-card-sender:v1";
    const themeNames = ["blue","wathet","turquoise","green","yellow","orange","red","purple","grey"];
    const themeClass = (name) => "theme-" + (themeNames.includes(name) ? name : "blue");

    function loadState() {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
      for (const name of fields) if (saved[name] && $(name)) $(name).value = saved[name];
    }

    function saveState() {
      const data = {};
      for (const name of fields) if ($(name)) data[name] = $(name).value;
      localStorage.setItem(storageKey, JSON.stringify(data));
    }

    function buildPayload() {
      const buttonText = $("buttonText").value.trim();
      const buttonUrl = $("buttonUrl").value.trim();
      const actions = buttonText && buttonUrl ? [{
        tag: "action",
        actions: [{
          tag: "button",
          text: { tag: "plain_text", content: buttonText },
          type: "default",
          url: buttonUrl
        }]
      }] : [];
      return {
        msg_type: "interactive",
        card: {
          config: { wide_screen_mode: true },
          header: {
            title: { tag: "plain_text", content: $("title").value.trim() || "未命名卡片" },
            template: $("template").value
          },
          elements: [{
            tag: "div",
            text: { tag: "lark_md", content: $("markdown").value.trim() || " " }
          }, ...actions]
        }
      };
    }

    function render() {
      saveState();
      const payload = buildPayload();
      $("previewTitle").textContent = payload.card.header.title.content;
      $("previewTitle").className = "card-header " + themeClass(payload.card.header.template);
      $("previewBody").textContent = $("markdown").value || " ";
      const buttonText = $("buttonText").value.trim();
      const buttonUrl = $("buttonUrl").value.trim();
      $("previewButton").hidden = !(buttonText && buttonUrl);
      $("previewButton").textContent = buttonText;
      $("jsonPreview").textContent = JSON.stringify(payload, null, 2);
    }

    function setMessage(text, kind) {
      $("message").textContent = text;
      $("message").className = "message " + (kind || "");
    }

    async function sendCard() {
      setMessage("", "");
      if (!CONFIG.webhookConfigured && !CONFIG.chatConfigured && !$("webhook").value.trim()) {
        setMessage("请填写飞书自定义机器人 webhook，或在 .env 配置 CARD_SENDER_WEBHOOK", "error");
        return;
      }
      const body = {
        webhook: (CONFIG.webhookConfigured || CONFIG.chatConfigured) ? "" : $("webhook").value.trim(),
        title: $("title").value,
        template: $("template").value,
        markdown: $("markdown").value,
        buttons: $("buttonText").value.trim() && $("buttonUrl").value.trim()
          ? [{ text: $("buttonText").value, url: $("buttonUrl").value, type: "default" }]
          : []
      };
      $("sendBtn").disabled = true;
      try {
        const response = await fetch("/cards/send", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body)
        });
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || "发送失败");
        setMessage("已发送", "ok");
      } catch (error) {
        setMessage(error.message || String(error), "error");
      } finally {
        $("sendBtn").disabled = false;
      }
    }

    async function copyJson() {
      await navigator.clipboard.writeText(JSON.stringify(buildPayload(), null, 2));
      setMessage("JSON 已复制", "ok");
    }

    for (const template of CONFIG.templates) {
      const option = document.createElement("option");
      option.value = template;
      option.textContent = template;
      $("template").appendChild(option);
    }
    $("template").value = "blue";
    $("webhookField").hidden = CONFIG.webhookConfigured || CONFIG.chatConfigured;
    $("webhookStatus").textContent = CONFIG.chatConfigured
      ? "应用机器人发送已配置"
      : (CONFIG.webhookConfigured ? "Webhook 已配置" : "Webhook 未配置");
    loadState();
    if (!CONFIG.webhookConfigured && !CONFIG.chatConfigured) $("webhookField").hidden = false;
    for (const name of fields) if ($(name)) $(name).addEventListener("input", render);
    $("template").addEventListener("change", render);
    $("sendBtn").addEventListener("click", sendCard);
    $("copyBtn").addEventListener("click", copyJson);
    document.querySelectorAll(".tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
        tab.classList.add("active");
        $("visualPane").hidden = tab.dataset.tab !== "visual";
        $("jsonPane").hidden = tab.dataset.tab !== "json";
      });
    });
    render();
  </script>
</body>
</html>"""
