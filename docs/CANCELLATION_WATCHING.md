# How cancellation watching works

This is the mechanism behind Goal G2 (and how the cart-hold in G3 hangs off it).

## The core idea: poll → diff → alert on the transition

A "cancellation" is not a special event the systems announce. It's just a site
flipping from **Reserved** back to **Available**. So we detect it by *sampling*
availability on a short interval and watching for the change:

```
every tick, per watch item:
    current  = connector.query_availability(watch)   # set of bookable openings
    new      = current  −  last_seen                  # set difference
    for each opening in new:  alert (+ optional cart-hold)
    last_seen = current                               # persist for next tick
```

We alert on the **unavailable → available transition**, not on "is available."
That's the whole trick:
- a site that *stays* open doesn't re-spam you every 90 seconds,
- a site that disappears (someone else grabbed it) and later reappears is a
  genuinely new event and alerts again.

State lives in SQLite (`last_seen` table). Implementation: `cici/engine/watcher.py`.

## What "an opening that matches" means

Raw availability is per-site, per-night. Your trip isn't — you want *N
consecutive nights*. So the connector collapses raw nightly availability into
**qualifying runs**: a site only counts if it has `nights` consecutive available
nights starting inside your date window (and, if `weekends_only`, starting Fri/Sat).
This kills the most common false positive — "a Tuesday opened up" when you asked
for a 2-night weekend. See `_consecutive_runs()` in the Recreation.gov connector.

The dedup key is `watch:site:run_start:nights`, so each distinct bookable run is
tracked independently.

## Where the data comes from

| System | Source | Notes |
|---|---|---|
| Recreation.gov (CRS) | `GET /api/camps/availability/campground/{id}/month` | The site's own front-end endpoint. Returns every site's per-day status for a month. Undocumented, behind Akamai — fragile, poll politely. |
| ReserveCalifornia | grid/search POST API | Different shape, stronger WAF; Phase-1 stub today. |

Both are normalized to the same `AvailableSite` objects so the engine doesn't
care which backend it's talking to.

## Polling cadence & being a good citizen

The watcher loops every `poll_interval_s` (default 90s) **plus random jitter**, and
the HTTP layer (`connectors/http.py`) adds: a per-request minimum spacing, random
sub-second jitter, exponential backoff on 429/403/503, and an honest User-Agent.

Cadence is a trade-off:
- **Faster polling = fresher hits but more load and higher ban risk.** Sub-30s
  polling on Recreation.gov is asking for a 403.
- **90s is a sane default.** Many winnable cancellations (mid-week, shoulder
  season, less-famous parks) sit open for minutes — you'll catch those reliably.
- **Marquee summer weekends** get sniped in seconds by other bots and humans;
  no polite poller wins those consistently. We optimize for the cases you can
  actually win and are honest about the ones you can't.

You can raise cadence per-need later (e.g. a tight loop only in the minutes after
a known release), but keep it adaptive and backed-off.

## Notification path

Hits go to push channels (Pushover / Telegram) — **not** calendar, which is too
slow to act on. The alert carries a **deep link** straight to the booking page,
pre-set to your dates. If cart-hold is enabled and succeeds, the link instead
points at your **cart**, where the backend's ~15-minute hold timer is already
running, and you just pay.

Dedup/cooldown (`notif_log` table) prevents the same opening from buzzing your
phone repeatedly within a cooldown window.

## How the cart-hold attaches

On a new hit, if `watch.cart_hold` is on and a `CartHolder` is configured, the
watcher calls `try_hold(site)` before notifying. On success the alert is upgraded
to "🛒 HELD 15min" with the cart link. See `docs/SPECIFICATION.md` §7.3 and
`cici/cart/base.py` for why this piece is gated and risk-flagged — it's the one
part of Option B that behaves like Option C.

## Known limitations (honest list)

- **Races on hot inventory.** A polite poller will lose some sub-second fights.
- **Endpoint drift.** Undocumented APIs change; connectors will break a few times
  a year and need a fix.
- **Bot defenses can escalate.** If they tighten detection, read-only polling may
  need slowing further; cart-hold may stop working entirely.
- **Not a guarantee.** This meaningfully raises your odds; it does not promise a
  booking.
