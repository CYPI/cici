"""Core data structures shared across connectors and the engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum


class ReleaseModel(str, Enum):
    """How a facility releases new bookable inventory."""

    ROLLING = "rolling"   # a new day opens every morning, N days out
    BLOCK = "block"       # a chunk opens on a fixed cadence (e.g. Yosemite, monthly)
    LOTTERY = "lottery"   # allocated by lottery, no first-come window


@dataclass
class Facility:
    """Static-ish metadata about a campground, used for window math + links."""

    system: str                       # "recreation_gov" | "reserve_california" | ...
    facility_id: str
    name: str
    timezone: str = "America/Los_Angeles"
    release_model: ReleaseModel = ReleaseModel.ROLLING
    rolling_window_days: int = 180     # 6 months is the common default
    release_local_time: time = time(8, 0)   # 8:00 local; CONFIRM per facility
    block_release_rule: str | None = None    # cron-ish, only for BLOCK facilities


@dataclass
class WatchItem:
    """One thing the user wants to be told about."""

    id: str
    system: str
    facility_id: str
    facility_name: str = ""
    date_start: date | None = None
    date_end: date | None = None
    nights: int = 1
    site_filter: dict = field(default_factory=dict)  # e.g. {"type": "TENT", "loop": "A"}
    weekends_only: bool = False
    channels: list[str] = field(default_factory=list)
    cart_hold: bool = False           # attempt to hold the cart on a hit (gated)
    active: bool = True

    # --- super-watcher knobs ---
    is_super: bool = False            # a must-not-miss site: its own tight loop
    interval_s: float | None = None   # override poll cadence (super: e.g. 15)
    schedule: dict = field(default_factory=dict)  # active-window: days/hours/off_window_interval_s

    def base_interval(self, default_regular: float, default_super: float) -> float:
        if self.interval_s is not None:
            return float(self.interval_s)
        return default_super if self.is_super else default_regular


@dataclass(frozen=True)
class AvailableSite:
    """A concrete, bookable opening discovered by a connector."""

    system: str
    facility_id: str
    site_id: str
    site_name: str
    start_date: date     # first night of a run that satisfies WatchItem.nights
    nights: int
    loop: str = ""
    site_type: str = ""

    def dedup_key(self, watch_id: str) -> str:
        return f"{watch_id}:{self.site_id}:{self.start_date.isoformat()}:{self.nights}"
