"""Emit an .ics feed of upcoming booking-window openings (Goal G1).

You subscribe to this file's URL in Google Calendar ("Add by URL") — no OAuth,
no write access to your account. Each event is "Mt Tam opens for 2026-09-05",
timed to the exact release moment with a reminder a few minutes prior.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from ics import Calendar, Event

from ..connectors import get_connector
from ..engine.window_calculator import NotDeterministic, window_for_watch
from ..models import WatchItem


def build_calendar(watches: list[WatchItem], reminder_min: int = 10) -> Calendar:
    cal = Calendar()
    for watch in watches:
        if not watch.active or not watch.date_start:
            continue
        conn = get_connector(watch.system)
        facility = conn.get_facility(watch.facility_id)
        try:
            opens = window_for_watch(facility, watch)
        except (NotDeterministic, ValueError):
            continue  # block/lottery facilities handled elsewhere
        ev = Event(
            name=f"Booking opens: {watch.facility_name or watch.facility_id} "
            f"({watch.date_start})",
            begin=opens,
            duration=timedelta(minutes=15),
            description=(
                f"{watch.nights} night(s) from {watch.date_start}. "
                f"Be on the page before {opens.strftime('%H:%M %Z')}."
            ),
        )
        ev.alarms = [_reminder(reminder_min)]
        cal.events.add(ev)
    return cal


def _reminder(minutes: int):
    from ics.alarm import DisplayAlarm

    return DisplayAlarm(trigger=timedelta(minutes=-minutes))


def write_ics(watches: list[WatchItem], path: str | Path) -> Path:
    path = Path(path)
    path.write_text(str(build_calendar(watches)))
    return path
