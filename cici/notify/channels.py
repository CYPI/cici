"""Concrete notification channels.

Cancellations are a *seconds* game, so the channels here are push-first
(Pushover / Telegram). Calendar is intentionally NOT a cancellation channel —
it's for predictable booking-window releases (see engine/calendar_feed.py).
"""

from __future__ import annotations

import logging

from .base import Alert, Notifier
from ..connectors.http import PoliteSession

log = logging.getLogger(__name__)


class ConsoleNotifier(Notifier):
    name = "console"

    def send(self, alert: Alert) -> None:
        flag = "🔥" if alert.urgent else "•"
        print(f"{flag} {alert.title}\n   {alert.body}\n   {alert.url}")


class PushoverNotifier(Notifier):
    name = "pushover"

    def __init__(self, token: str, user: str) -> None:
        self._token, self._user = token, user
        self._http = PoliteSession(min_interval=0.0)  # outbound to our own service

    def send(self, alert: Alert) -> None:
        self._http._request(  # noqa: SLF001 - thin wrapper is fine here
            "POST",
            "https://api.pushover.net/1/messages.json",
            data={
                "token": self._token,
                "user": self._user,
                "title": alert.title,
                "message": alert.body,
                "url": alert.url,
                "url_title": "Open booking",
                "priority": 1 if alert.urgent else 0,
            },
        )


class TelegramNotifier(Notifier):
    name = "telegram"

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self._chat = chat_id
        self._http = PoliteSession(min_interval=0.0)

    def send(self, alert: Alert) -> None:
        self._http._request(  # noqa: SLF001
            "POST",
            self._url,
            data={
                "chat_id": self._chat,
                "text": f"{alert.title}\n{alert.body}\n{alert.url}",
                "disable_web_page_preview": False,
            },
        )


def build_notifiers(cfg: dict) -> dict[str, Notifier]:
    """Construct channels from the `notifiers:` block of config."""
    out: dict[str, Notifier] = {"console": ConsoleNotifier()}
    if po := cfg.get("pushover"):
        out["pushover"] = PushoverNotifier(po["token"], po["user"])
    if tg := cfg.get("telegram"):
        out["telegram"] = TelegramNotifier(tg["bot_token"], tg["chat_id"])
    return out
