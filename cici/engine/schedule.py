"""Active-window scheduling for the super-watcher.

Lets a must-not-miss watch run hyper-fast only when it matters (Fri nights, whole
weekends, the run-up to a long weekend) and idle gently the rest of the time —
which is both what the user wants and how we avoid 24/7 hammering that gets the
IP flagged.
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

_DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def in_active_window(
    schedule: dict | None,
    now: datetime | None = None,
    tz: str = "America/Los_Angeles",
) -> bool:
    """True if `now` (facility-local) falls inside the configured window.

    Empty/absent schedule means "always active".
    schedule = {"days": ["fri","sat","sun"], "hours": "16:00-23:59"}
    """
    if not schedule:
        return True
    now = now or datetime.now(ZoneInfo(tz))

    days = schedule.get("days")
    if days and now.weekday() not in {_DAYS[d[:3].lower()] for d in days}:
        return False

    hours = schedule.get("hours")
    if hours:
        start, end = _parse_range(hours)
        t = now.time()
        if start <= end:
            if not (start <= t <= end):
                return False
        elif not (t >= start or t <= end):   # window wraps past midnight
            return False
    return True


def _parse_range(spec: str) -> tuple[time, time]:
    a, b = spec.split("-")
    return _parse_time(a), _parse_time(b)


def _parse_time(s: str) -> time:
    h, m = s.strip().split(":")
    return time(int(h), int(m))
