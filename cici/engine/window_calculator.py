"""Booking-window math (Goal G1).

For ROLLING facilities the moment your trip becomes bookable is pure arithmetic:
    bookable_at = (trip_start - rolling_window_days) at release_local_time, in the
    facility's timezone.
No scraping, no race, no ToS exposure — this is the safe, deterministic core that
feeds your calendar so you can be sitting on the page at 7:59am.

BLOCK facilities (e.g. Yosemite's monthly drop) don't fit a simple subtraction;
they need a per-facility rule and are handled separately / TODO.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..models import Facility, ReleaseModel, WatchItem


class NotDeterministic(Exception):
    """Raised when a facility's release isn't a simple rolling subtraction."""


def bookable_at(facility: Facility, trip_start: date) -> datetime:
    if facility.release_model is not ReleaseModel.ROLLING:
        raise NotDeterministic(
            f"{facility.name} is {facility.release_model.value}; needs a rule"
        )
    open_day = trip_start - timedelta(days=facility.rolling_window_days)
    tz = ZoneInfo(facility.timezone)
    return datetime.combine(open_day, facility.release_local_time, tzinfo=tz)


def window_for_watch(facility: Facility, watch: WatchItem) -> datetime:
    if not watch.date_start:
        raise ValueError(f"watch {watch.id} has no date_start")
    return bookable_at(facility, watch.date_start)
