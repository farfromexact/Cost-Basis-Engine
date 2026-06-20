from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import quote
from urllib.request import Request, urlopen

from research.prompts import IntradayPrompt


@dataclass(frozen=True)
class NotificationConfig:
    provider: str = "console"
    token: str | None = None
    url: str | None = None
    timeout: float = 10.0
    dry_run: bool = False


class Notifier:
    def __init__(self, config: NotificationConfig) -> None:
        self.config = config

    def send(self, title: str, body: str, payload: dict | None = None) -> None:
        provider = self.config.provider.lower()
        if self.config.dry_run or provider == "console":
            print(f"[NOTIFY] {title}\n{body}")
            return
        if provider == "webhook":
            self._send_webhook(title, body, payload or {})
            return
        if provider == "bark":
            self._send_bark(title, body)
            return
        if provider == "pushplus":
            self._send_pushplus(title, body)
            return
        raise ValueError(f"unsupported notify provider: {self.config.provider}")

    def _send_webhook(self, title: str, body: str, payload: dict) -> None:
        if not self.config.url:
            raise ValueError("webhook provider requires notify url")
        data = json.dumps(
            {"title": title, "body": body, "payload": payload},
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            self.config.url,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urlopen(request, timeout=self.config.timeout):
            return

    def _send_bark(self, title: str, body: str) -> None:
        token_or_url = self.config.token or self.config.url
        if not token_or_url:
            raise ValueError("bark provider requires notify token or url")
        base = token_or_url.rstrip("/")
        if not base.startswith("http"):
            base = f"https://api.day.app/{base}"
        url = f"{base}/{quote(title)}/{quote(body)}"
        with urlopen(Request(url, method="GET"), timeout=self.config.timeout):
            return

    def _send_pushplus(self, title: str, body: str) -> None:
        if not self.config.token:
            raise ValueError("pushplus provider requires notify token")
        data = json.dumps(
            {
                "token": self.config.token,
                "title": title,
                "content": body,
                "template": "txt",
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            "https://www.pushplus.plus/send",
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urlopen(request, timeout=self.config.timeout):
            return


def format_prompt_notification(
    data_label: str,
    prompt: IntradayPrompt,
) -> tuple[str, str]:
    title = f"{data_label} {prompt.action.value}"
    lines = [
        f"action: {prompt.action.value}",
        f"time: {prompt.ts}",
        f"price: {prompt.price}",
        f"qty: {prompt.qty}",
        f"confidence: {prompt.confidence}",
        f"reason: {prompt.reason}",
        f"vwap: {prompt.vwap}",
        f"vwap_deviation_pct: {prompt.vwap_deviation_pct}",
        f"amount_ratio: {prompt.amount_ratio}",
        f"day_position_pct: {prompt.day_position_pct}",
    ]
    for key, value in prompt.planned_zone.items():
        lines.append(f"{key}: {value}")
    for warning in prompt.warnings:
        lines.append(f"warning: {warning}")
    return title, "\n".join(lines)
