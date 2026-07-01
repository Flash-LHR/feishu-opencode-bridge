from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .state import StateStore
from .types import IncomingEvent


SEVERITY_ALIASES = {
    "warn": "warning",
    "warning": "warning",
    "error": "critical",
    "fatal": "critical",
    "critical": "critical",
    "crit": "critical",
    "info": "info",
    "notice": "notice",
}


@dataclass(frozen=True)
class Alert:
    text: str
    fingerprint: str
    name: str = ""
    severity: str = ""
    service: str = ""
    environment: str = ""

    def to_json(self) -> Dict[str, str]:
        return {
            "text": self.text,
            "fingerprint": self.fingerprint,
            "name": self.name,
            "severity": self.severity,
            "service": self.service,
            "environment": self.environment,
        }


@dataclass(frozen=True)
class OncallDecision:
    action: str
    alert: Alert
    reason: str = ""
    reused_output: str = ""
    reserved_day: Optional[str] = None

    @property
    def should_analyze(self) -> bool:
        return self.action == "analyze"

    @property
    def should_reuse(self) -> bool:
        return self.action == "reuse"


class OncallPolicy:
    def __init__(self, settings: Settings, state: StateStore) -> None:
        self._settings = settings
        self._state = state

    def decide(self, incoming: IncomingEvent) -> OncallDecision:
        alert = parse_alert(incoming.clean_text)

        if alert.severity and alert.severity in self._settings.auto_ignore_severities:
            return OncallDecision("ignore", alert, reason=f"severity={alert.severity}")

        matched_keyword = self._matched_keyword(alert.text)
        if matched_keyword:
            return OncallDecision("ignore", alert, reason=f"keyword={matched_keyword}")

        reused = self._reusable_conclusion(alert)
        if reused:
            return OncallDecision("reuse", alert, reused_output=reused)

        day = current_day_key(self._settings.auto_daily_limit_timezone)
        if not self._state.claim_oncall_analysis_slot(day, self._settings.auto_daily_limit):
            return OncallDecision("ignore", alert, reason=f"daily_limit={self._settings.auto_daily_limit}")

        return OncallDecision("analyze", alert, reserved_day=day)

    def record_success(self, decision: OncallDecision, incoming: IncomingEvent, output: str) -> None:
        self._state.set_oncall_conclusion(
            decision.alert.to_json(),
            output,
            topic_id=incoming.message.topic_id,
            message_id=incoming.message.message_id,
            analyzed_at=int(time.time()),
        )

    def record_failure(self, decision: OncallDecision) -> None:
        if decision.reserved_day:
            self._state.release_oncall_analysis_slot(decision.reserved_day)

    def _matched_keyword(self, text: str) -> str:
        lowered = text.lower()
        for keyword in self._settings.auto_ignore_keywords:
            if keyword and keyword.lower() in lowered:
                return keyword
        return ""

    def _reusable_conclusion(self, alert: Alert) -> str:
        if self._settings.auto_reuse_window_seconds <= 0:
            return ""
        item = self._state.get_oncall_conclusion(alert.fingerprint)
        if not item:
            return ""
        output = str(item.get("last_output") or "").strip()
        analyzed_at = int(item.get("last_analyzed_at") or 0)
        if not output or not analyzed_at:
            return ""
        if int(time.time()) - analyzed_at > self._settings.auto_reuse_window_seconds:
            return ""
        return output


def parse_alert(text: str) -> Alert:
    cleaned = clean_text(text)
    fields = extract_fields(cleaned)
    severity = normalize_severity(fields.get("severity") or find_inline_severity(cleaned))
    name = fields.get("name") or first_content_line(cleaned)
    service = fields.get("service", "")
    environment = fields.get("environment", "")
    fingerprint = build_fingerprint(cleaned, name, severity, service, environment)
    return Alert(
        text=cleaned,
        fingerprint=fingerprint,
        name=name,
        severity=severity,
        service=service,
        environment=environment,
    )


def clean_text(text: str) -> str:
    lines = [line.strip().strip("*") for line in str(text or "").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def extract_fields(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    field_map = {
        "alertname": "name",
        "alert": "name",
        "告警名称": "name",
        "告警名": "name",
        "标题": "name",
        "name": "name",
        "severity": "severity",
        "level": "severity",
        "告警级别": "severity",
        "严重程度": "severity",
        "级别": "severity",
        "等级": "severity",
        "service": "service",
        "app": "service",
        "application": "service",
        "服务": "service",
        "应用": "service",
        "env": "environment",
        "environment": "environment",
        "环境": "environment",
    }
    pattern = re.compile(r"^\s*[-*]?\s*([A-Za-z_ -]+|[\u4e00-\u9fffA-Za-z_ -]+)\s*[:：=]\s*(.+?)\s*$")
    for line in text.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        raw_key = normalize_key(match.group(1))
        key = field_map.get(raw_key)
        value = normalize_value(match.group(2))
        if key and value and key not in result:
            result[key] = value
    return result


def normalize_key(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def normalize_value(value: str) -> str:
    return value.strip().strip("*`\"'，,。")


def normalize_severity(value: str) -> str:
    text = normalize_value(value).lower()
    if not text:
        return ""
    text = text.split()[0].strip("[]()")
    if re.fullmatch(r"p[0-5]", text):
        return text
    return SEVERITY_ALIASES.get(text, text)


def find_inline_severity(text: str) -> str:
    match = re.search(r"\b(P[0-5]|critical|crit|fatal|error|warning|warn|info|notice)\b", text, re.IGNORECASE)
    return match.group(1) if match else ""


def first_content_line(text: str) -> str:
    for line in text.splitlines():
        line = normalize_value(line)
        if not line:
            continue
        if line.startswith(("http://", "https://")):
            continue
        return line[:120]
    return ""


def build_fingerprint(text: str, name: str, severity: str, service: str, environment: str) -> str:
    parts = [name, severity, service, environment]
    if not any(parts):
        parts = [normalize_for_fingerprint(text)]
    seed = "|".join(normalize_for_fingerprint(part) for part in parts if part)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    return digest


def normalize_for_fingerprint(text: str) -> str:
    value = text.lower()
    value = re.sub(r"https?://\S+", "", value)
    value = re.sub(r"\d+(?:\.\d+)?", "{num}", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:500]


def current_day_key(timezone: str) -> str:
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    return datetime.now(tz).strftime("%Y-%m-%d")


def reuse_reply(output: str) -> str:
    return f"同类告警已在近期分析过，沿用上次结论：\n\n{output.strip()}"


def alert_summary(alert: Alert) -> str:
    parts = []
    if alert.name:
        parts.append(f"name={alert.name}")
    if alert.severity:
        parts.append(f"severity={alert.severity}")
    if alert.service:
        parts.append(f"service={alert.service}")
    if alert.environment:
        parts.append(f"env={alert.environment}")
    parts.append(f"fingerprint={alert.fingerprint}")
    return " ".join(parts)
