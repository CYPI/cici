"""Signal notifications via signal-cli — free, no paid service, no third-party
server.

Setup (one time):
  1. Install signal-cli (https://github.com/AsamK/signal-cli).
  2. Register it with a DEDICATED phone number — NOT the number on your real
     phone, since registering hands Signal for that number to signal-cli. A free
     Google Voice number works:
        signal-cli -a +15105550000 register
        signal-cli -a +15105550000 verify 123-456     # code via SMS/call
  3. Point CICI at it (notifiers.signal in config).

This is a real, legitimate Signal client — not a ToS-violating automation — so no
account-ban risk like the unofficial WhatsApp route.
"""

from __future__ import annotations

import logging
import shutil
import subprocess

from .base import Alert, Notifier

log = logging.getLogger(__name__)


class SignalNotifier(Notifier):
    name = "signal"

    def __init__(
        self,
        account: str,
        recipients: list[str],
        cli_path: str = "signal-cli",
        timeout_s: float = 30.0,
    ) -> None:
        self._account = account          # the number signal-cli is registered with
        self._recipients = recipients    # your own number(s), E.164 e.g. +1510...
        self._cli = cli_path
        self._timeout = timeout_s

    def send(self, alert: Alert) -> None:
        if shutil.which(self._cli) is None and "/" not in self._cli:
            raise RuntimeError(
                f"signal-cli not found on PATH as {self._cli!r}; install it or set "
                "notifiers.signal.cli_path to the full binary path"
            )
        body = f"{alert.title}\n{alert.body}\n{alert.url}"
        cmd = [self._cli, "-a", self._account, "send", "-m", body, *self._recipients]
        try:
            subprocess.run(
                cmd, check=True, capture_output=True, text=True, timeout=self._timeout
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"signal-cli failed: {exc.stderr.strip()}") from exc
        log.info("signal -> %s", self._recipients)
