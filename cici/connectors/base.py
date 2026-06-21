"""The contract every backend connector implements.

Each reservation system (Recreation.gov, ReserveCalifornia, county portals) is
its own bespoke, undocumented API. We isolate that mess behind this interface so
the engine stays backend-agnostic and one connector breaking can't take down the
rest.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import AvailableSite, Facility, WatchItem


class Connector(ABC):
    system: str

    @abstractmethod
    def get_facility(self, facility_id: str) -> Facility:
        """Return metadata used for window math and link building."""

    @abstractmethod
    def query_availability(self, watch: WatchItem) -> list[AvailableSite]:
        """Return current openings that satisfy `watch` (date range + nights)."""

    @abstractmethod
    def deep_link(self, site: AvailableSite) -> str:
        """A URL that drops the user as close to checkout as possible."""

    def cart_link(self, site: AvailableSite) -> str:
        """URL to the user's cart, used after a (gated) cart-hold succeeds."""
        return self.deep_link(site)
