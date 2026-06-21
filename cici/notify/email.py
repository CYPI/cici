"""Email + SMS notifications with no backend and no paid service.

Email: plain SMTP (e.g. Gmail with a free App Password).
SMS:  carrier email-to-SMS gateways (free) — you send an email to an address
      like 5105551234@tmomail.net (T-Mobile), @vtext.com (Verizon),
      @txt.att.net (AT&T) and it arrives as a text. No Twilio, no account.

Caveat worth knowing: carrier gateways are best-effort and some carriers have
curtailed them; treat SMS as a nice-to-have and keep email (or Telegram) as the
reliable channel.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from .base import Alert, Notifier

log = logging.getLogger(__name__)


class EmailNotifier(Notifier):
    name = "email"

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        sender: str,
        recipients: list[str],
        sms_style: bool = False,
        name: str = "email",
    ) -> None:
        self._host = smtp_host
        self._port = int(smtp_port)
        self._username = username
        self._password = password
        self._sender = sender
        self._recipients = recipients
        self._sms_style = sms_style   # short body, no subject — friendlier to SMS
        self.name = name

    def send(self, alert: Alert) -> None:
        msg = EmailMessage()
        msg["From"] = self._sender
        msg["To"] = ", ".join(self._recipients)
        if self._sms_style:
            # SMS gateways truncate hard and often drop the subject; keep it tight.
            msg["Subject"] = ""
            msg.set_content(f"{alert.title}\n{alert.url}")
        else:
            msg["Subject"] = alert.title
            msg.set_content(f"{alert.body}\n\n{alert.url}")

        ctx = ssl.create_default_context()
        if self._port == 465:
            with smtplib.SMTP_SSL(self._host, self._port, context=ctx, timeout=20) as s:
                s.login(self._username, self._password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(self._host, self._port, timeout=20) as s:
                s.starttls(context=ctx)
                s.login(self._username, self._password)
                s.send_message(msg)
        log.info("%s -> %s", self.name, self._recipients)
