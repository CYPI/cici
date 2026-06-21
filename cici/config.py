"""Load watchlist + settings from YAML into typed objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from .models import WatchItem


@dataclass
class Config:
    watches: list[WatchItem]
    notifiers: dict = field(default_factory=dict)
    cart_hold: dict = field(default_factory=dict)
    poll_interval_s: float = 90.0
    super_interval_s: float = 15.0
    db_path: str = "cici.db"


def load(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    watches = [_watch(w) for w in raw.get("watches", [])]
    settings = raw.get("settings", {})
    return Config(
        watches=watches,
        notifiers=raw.get("notifiers", {}),
        cart_hold=raw.get("cart_hold", {}),
        poll_interval_s=float(settings.get("poll_interval_s", 90.0)),
        super_interval_s=float(settings.get("super_interval_s", 15.0)),
        db_path=settings.get("db_path", "cici.db"),
    )


def _watch(w: dict) -> WatchItem:
    return WatchItem(
        id=w["id"],
        system=w["system"],
        facility_id=str(w["facility_id"]),
        facility_name=w.get("facility_name", ""),
        date_start=_date(w.get("date_start")),
        date_end=_date(w.get("date_end")),
        nights=int(w.get("nights", 1)),
        site_filter=w.get("site_filter", {}),
        weekends_only=bool(w.get("weekends_only", False)),
        channels=w.get("channels", ["console"]),
        cart_hold=bool(w.get("cart_hold", False)),
        active=bool(w.get("active", True)),
        is_super=bool(w.get("super", False)),
        interval_s=(float(w["interval_s"]) if w.get("interval_s") is not None else None),
        schedule=w.get("schedule", {}),
    )


def _date(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))
