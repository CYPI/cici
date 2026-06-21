"""Notification channel contract + the alert payload."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Alert:
    title: str
    body: str
    url: str          # the deep link / cart link to act on
    urgent: bool = True


class Notifier(ABC):
    name: str

    @abstractmethod
    def send(self, alert: Alert) -> None: ...
