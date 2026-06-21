"""ReserveCalifornia (CA State Parks) connector — STUB.

ReserveCalifornia (operated by Aspira) does not expose a clean month endpoint
like Recreation.gov. Availability comes from POSTing to a grid/search API
(roughly `/rdr/rdr/search/grid`) with a place/facility id and a date range, and
the payloads + anti-WAF behavior need live reverse-engineering before this is
reliable. The structure below mirrors the Recreation.gov connector so the engine
treats both identically; fill in `query_availability` once the live shapes are
confirmed.
"""

from __future__ import annotations

from ..models import AvailableSite, Facility, ReleaseModel, WatchItem
from .base import Connector
from .http import PoliteSession


class ReserveCaliforniaConnector(Connector):
    system = "reserve_california"

    def __init__(self, session: PoliteSession | None = None) -> None:
        self._http = session or PoliteSession()

    def get_facility(self, facility_id: str) -> Facility:
        # Rolling 6 months, new day opens 08:00 PT.
        return Facility(
            system=self.system,
            facility_id=facility_id,
            name=facility_id,
            release_model=ReleaseModel.ROLLING,
            rolling_window_days=180,
        )

    def query_availability(self, watch: WatchItem) -> list[AvailableSite]:
        raise NotImplementedError(
            "ReserveCalifornia availability needs the live grid API reverse-"
            "engineered. Tracked as Phase-1 work; Recreation.gov is wired first."
        )

    def deep_link(self, site: AvailableSite) -> str:
        return (
            "https://www.reservecalifornia.com/Web/Default.aspx#!park/"
            f"{site.facility_id}"
        )
