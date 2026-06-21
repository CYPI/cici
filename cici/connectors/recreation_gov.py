"""Recreation.gov (the federal CRS) connector.

Availability comes from the per-campground "month" endpoint that the site's own
front-end calls:

    GET https://www.recreation.gov/api/camps/availability/campground/{id}/month
        ?start_date=YYYY-MM-01T00:00:00.000Z

Response shape (trimmed):
    {"campsites": {"<site_id>": {
        "site": "A012", "loop": "LOOP A", "campsite_type": "TENT ONLY",
        "availabilities": {"2026-09-04T00:00:00Z": "Available", ...}}}}

This endpoint is undocumented and behind Akamai bot defenses. Treat it as
fragile: confirm the shape live, poll politely, and expect it to change.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from ..models import AvailableSite, Facility, ReleaseModel, WatchItem
from .base import Connector
from .http import PoliteSession

_AVAIL_URL = (
    "https://www.recreation.gov/api/camps/availability/campground/{cid}/month"
)
_AVAILABLE = "Available"


class RecreationGovConnector(Connector):
    system = "recreation_gov"

    def __init__(self, session: PoliteSession | None = None) -> None:
        self._http = session or PoliteSession()

    def get_facility(self, facility_id: str) -> Facility:
        # Most Recreation.gov campgrounds are rolling 6 months at 7-8am local.
        # A handful (e.g. Yosemite) are BLOCK releases — override via config.
        return Facility(
            system=self.system,
            facility_id=facility_id,
            name=facility_id,
            release_model=ReleaseModel.ROLLING,
            rolling_window_days=180,
        )

    def query_availability(self, watch: WatchItem) -> list[AvailableSite]:
        if not (watch.date_start and watch.date_end):
            raise ValueError(f"watch {watch.id} needs date_start and date_end")

        # available dates per site, across every month the range touches
        per_site: dict[str, dict] = {}
        for first in _months_spanning(watch.date_start, watch.date_end):
            data = self._http.get_json(
                _AVAIL_URL.format(cid=watch.facility_id),
                params={"start_date": first.strftime("%Y-%m-01T00:00:00.000Z")},
            )
            for site_id, site in (data.get("campsites") or {}).items():
                bucket = per_site.setdefault(
                    site_id,
                    {"meta": site, "dates": set()},
                )
                for raw_day, status in (site.get("availabilities") or {}).items():
                    if status != _AVAILABLE:
                        continue
                    day = datetime.fromisoformat(raw_day.replace("Z", "+00:00")).date()
                    if watch.date_start <= day <= watch.date_end:
                        bucket["dates"].add(day)

        results: list[AvailableSite] = []
        for site_id, bucket in per_site.items():
            meta = bucket["meta"]
            if not _matches_filter(meta, watch.site_filter):
                continue
            for run_start in _consecutive_runs(
                bucket["dates"], watch.nights, watch.weekends_only
            ):
                results.append(
                    AvailableSite(
                        system=self.system,
                        facility_id=watch.facility_id,
                        site_id=site_id,
                        site_name=meta.get("site", site_id),
                        start_date=run_start,
                        nights=watch.nights,
                        loop=meta.get("loop", ""),
                        site_type=meta.get("campsite_type", ""),
                    )
                )
        return results

    def deep_link(self, site: AvailableSite) -> str:
        # Drops you on the campground page scrolled to the date; the closest to
        # checkout Recreation.gov exposes via a plain URL.
        return (
            f"https://www.recreation.gov/camping/campgrounds/{site.facility_id}"
            f"?startDate={site.start_date.isoformat()}"
        )

    def cart_link(self, site: AvailableSite) -> str:
        return "https://www.recreation.gov/cart"


def _months_spanning(start: date, end: date) -> list[date]:
    out, cur = [], start.replace(day=1)
    while cur <= end:
        out.append(cur)
        cur = (cur + timedelta(days=32)).replace(day=1)
    return out


def _consecutive_runs(
    dates: set[date], nights: int, weekends_only: bool
) -> list[date]:
    """Return each start-date that has `nights` consecutive available nights."""
    starts = []
    for d in sorted(dates):
        if weekends_only and d.weekday() not in (4, 5):  # Fri/Sat checkin
            continue
        if all(d + timedelta(days=i) in dates for i in range(nights)):
            starts.append(d)
    return starts


def _matches_filter(meta: dict, site_filter: dict) -> bool:
    for key, want in site_filter.items():
        got = str(meta.get(key, "")).upper()
        if str(want).upper() not in got:
            return False
    return True
