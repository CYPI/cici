"""The cancellation watcher (regular + super).

Per watch item, on every tick:
  1. ask the connector what's currently bookable for the wanted dates/nights,
  2. diff against the set we saw last tick,
  3. for each NEWLY-appeared opening, fire an alert (deduped/cooled-down),
  4. optionally try to hold the cart (gated, see cart/),
  5. persist the new "currently available" set as last-seen.

We alert on the unavailable->available *transition*, not on "is available", so a
site that stays open doesn't re-spam you, but one that disappears and comes back
is a fresh event.

Scheduling: each watch has its own cadence, so a "super" must-not-miss site can
poll every ~15s while regular watches sit at ~90s, all in one loop (heap of due
times). Two safety behaviors protect access:
  * active-window schedule — a super-watch only runs fast inside e.g. Fri nights
    / weekends, and idles slowly otherwise (see schedule.py);
  * circuit-breaker — if the backend throttles us (RateLimited), that watch backs
    off exponentially on its own, then recovers. Hammering through a 403 is how
    you get the IP/account flagged and lose the very site you cared about.
"""

from __future__ import annotations

import heapq
import logging
import random
import time

from ..connectors import get_connector
from ..connectors.http import RateLimited
from ..models import AvailableSite, WatchItem
from ..notify import Alert, Notifier
from ..store import Store
from .schedule import in_active_window

log = logging.getLogger(__name__)

_MAX_BACKOFF_STEPS = 6   # cap circuit-breaker slowdown at 2**6 = 64x


class Watcher:
    def __init__(
        self,
        watches: list[WatchItem],
        notifiers: dict[str, Notifier],
        store: Store,
        cart_holder=None,
        poll_interval_s: float = 90.0,
        super_interval_s: float = 15.0,
        jitter_s: float = 30.0,
        notify_cooldown_s: float = 6 * 3600,
    ) -> None:
        self._watches = [w for w in watches if w.active]
        self._notifiers = notifiers
        self._store = store
        self._cart = cart_holder
        self._interval = poll_interval_s
        self._super_interval = super_interval_s
        self._jitter = jitter_s
        self._cooldown = notify_cooldown_s
        self._connectors: dict[str, object] = {}     # reuse sessions across ticks
        self._failures: dict[str, int] = {}          # circuit-breaker per watch

    # -- public API -----------------------------------------------------------

    def run_forever(self) -> None:
        n_super = sum(w.is_super for w in self._watches)
        log.info("watching %d item(s) (%d super)", len(self._watches), n_super)
        by_id = {w.id: w for w in self._watches}
        heap = [(time.monotonic(), w.id) for w in self._watches]
        heapq.heapify(heap)

        while heap:
            due, wid = heapq.heappop(heap)
            now = time.monotonic()
            if due > now:
                time.sleep(due - now)
            watch = by_id[wid]
            interval = self._run_once(watch)
            heapq.heappush(heap, (time.monotonic() + interval, wid))

    def tick(self, watch: WatchItem) -> list[AvailableSite]:
        """One poll+diff+alert pass. Raises on connector errors (used by `check`)."""
        conn = self._conn(watch.system)
        current = conn.query_availability(watch)
        keys = {s.dedup_key(watch.id) for s in current}

        previous = self._store.get_last_seen(watch.id)
        new_sites = [s for s in current if s.dedup_key(watch.id) not in previous]
        for site in new_sites:
            self._handle_new(watch, conn, site)
        self._store.set_last_seen(watch.id, keys)
        return new_sites

    # -- internals ------------------------------------------------------------

    def _run_once(self, watch: WatchItem) -> float:
        """Tick a watch, manage the circuit-breaker, return seconds until next run."""
        try:
            self.tick(watch)
            self._failures[watch.id] = 0
            return self._next_interval(watch)
        except RateLimited:
            steps = self._failures[watch.id] = min(
                self._failures.get(watch.id, 0) + 1, _MAX_BACKOFF_STEPS
            )
            backoff = self._next_interval(watch) * (2 ** steps)
            log.warning(
                "%s throttled; circuit-breaker backing off to %.0fs", watch.id, backoff
            )
            return backoff
        except NotImplementedError as exc:
            log.warning("skip %s: %s", watch.id, exc)
            return max(self._next_interval(watch), 300.0)
        except Exception:  # one bad connector must not kill the loop
            log.exception("tick failed for %s", watch.id)
            return self._next_interval(watch)

    def _next_interval(self, watch: WatchItem) -> float:
        base = watch.base_interval(self._interval, self._super_interval)

        # Super-watch outside its active window: idle gently instead of hammering.
        if watch.is_super and watch.schedule:
            if not in_active_window(watch.schedule):
                base = float(watch.schedule.get("off_window_interval_s", 600))

        # Keep super-watch jitter tight so it stays fast; regular gets more spread.
        spread = min(base * 0.2, 3.0) if watch.is_super else self._jitter
        return base + random.uniform(0, spread)

    def _conn(self, system: str):
        if system not in self._connectors:
            self._connectors[system] = get_connector(system)
        return self._connectors[system]

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
        if held:
            prefix = "🛒 HELD 15min — "
        elif watch.is_super:
            prefix = "🚨 SUPER — "
        else:
            prefix = "🏕️ Opening — "
        title = prefix + where
        body = f"{when}{' · ' + site.loop if site.loop else ''}"
        if held:
            body += "\nIn your cart — finalize within 15 min."

        for ch in watch.channels or ["console"]:
            notifier = self._notifiers.get(ch)
            if notifier:
                notifier.send(Alert(title=title, body=body, url=url, urgent=True))
        self._store.mark_notified(key)
        log.info("alerted %s (super=%s held=%s)", key, watch.is_super, held)
