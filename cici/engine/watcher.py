"""The cancellation watcher.

Per watch item, on every tick:
  1. ask the connector what's currently bookable for the wanted dates/nights,
  2. diff against the set we saw last tick,
  3. for each NEWLY-appeared opening, fire an alert (deduped/cooled-down),
  4. optionally try to hold the cart (gated, see cart/),
  5. persist the new "currently available" set as last-seen.

We alert on the unavailable->available *transition*, not on "is available", so a
site that stays open doesn't re-spam you, but one that disappears and comes back
is a fresh event.
"""

from __future__ import annotations

import logging
import random
import time

from ..connectors import get_connector
from ..models import AvailableSite, WatchItem
from ..notify import Alert, Notifier
from ..store import Store

log = logging.getLogger(__name__)


class Watcher:
    def __init__(
        self,
        watches: list[WatchItem],
        notifiers: dict[str, Notifier],
        store: Store,
        cart_holder=None,
        poll_interval_s: float = 90.0,
        jitter_s: float = 30.0,
        notify_cooldown_s: float = 6 * 3600,
    ) -> None:
        self._watches = [w for w in watches if w.active]
        self._notifiers = notifiers
        self._store = store
        self._cart = cart_holder
        self._interval = poll_interval_s
        self._jitter = jitter_s
        self._cooldown = notify_cooldown_s

    def run_forever(self) -> None:
        log.info("watching %d item(s)", len(self._watches))
        while True:
            for watch in self._watches:
                try:
                    self.tick(watch)
                except NotImplementedError as exc:
                    log.warning("skip %s: %s", watch.id, exc)
                except Exception:  # one bad connector must not kill the loop
                    log.exception("tick failed for %s", watch.id)
            time.sleep(self._interval + random.uniform(0, self._jitter))

    def tick(self, watch: WatchItem) -> list[AvailableSite]:
        conn = get_connector(watch.system)
        current = conn.query_availability(watch)
        keys = {s.dedup_key(watch.id) for s in current}

        previous = self._store.get_last_seen(watch.id)
        new_sites = [s for s in current if s.dedup_key(watch.id) not in previous]

        for site in new_sites:
            self._handle_new(watch, conn, site)

        self._store.set_last_seen(watch.id, keys)
        return new_sites

    def _handle_new(self, watch: WatchItem, conn, site: AvailableSite) -> None:
        key = site.dedup_key(watch.id)
        if self._store.already_notified(key, self._cooldown):
            return

        url = conn.deep_link(site)
        held = False
        if watch.cart_hold and self._cart is not None:
            try:
                held = self._cart.try_hold(site)
                if held:
                    url = conn.cart_link(site)
            except Exception:
                log.exception("cart-hold failed for %s", key)

        where = f"{watch.facility_name or watch.facility_id} · {site.site_name}"
        when = f"{site.start_date} ({site.nights}n)"
        title = ("🛒 HELD 15min — " if held else "🏕️ Opening — ") + where
        body = f"{when}{' · '+site.loop if site.loop else ''}"
        if held:
            body += "\nIn your cart — finalize within 15 min."

        for ch in watch.channels or ["console"]:
            notifier = self._notifiers.get(ch)
            if notifier:
                notifier.send(Alert(title=title, body=body, url=url, urgent=True))
        self._store.mark_notified(key)
        log.info("alerted %s (held=%s)", key, held)
