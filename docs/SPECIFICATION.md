# CICI — Campsite Intelligence & Cancellation Index

**A monitoring + alerting + calendar system for Bay Area and federal (CRS) campsite reservations.**

Status: Draft spec for discussion · Owner: Cyril · Date: 2026-06-21

### Decision log
- **2026-06-21 — Build Option B (notify + fast-book assist).** Calendar windows
  (G1) + cancellation alerts (G2) + deep-link fast-book (G3). Auto-purchase
  remains a non-goal.
- **2026-06-21 — Cart-hold: DEFERRED, deep-link only.** Automated add-to-cart
  needs authenticated bot actions (ToS violation, CAPTCHA, account-ban risk), so
  we ship instant push + one-tap deep link to the booking page and finalize by
  hand. The cart-hold module stays in the tree but **gated off**; revisit only as
  a deliberate, eyes-open change.

---

## 1. What you asked for (restated)

> Monitor every campsite-reservation website that covers the Bay Area plus the federal CRS. Put every "new booking window release" date on my calendar so I know when fresh dates open. Also have agents watch for cancellations so I can grab a site right away. And tell me what my options are — and challenge my assumptions.

I'm going to give you a spec, but the most useful thing I can do first is challenge three assumptions baked into that request, because they change the whole architecture. The TL;DR:

1. **"All the websites" is not one problem — it's 5–8 different problems.** There is no single "campsite system." Bay Area camping is split across the federal system and several independent state/county systems, each with its own booking rules, API, and anti-bot defenses.
2. **A calendar full of "every release date" is mostly noise.** The dominant systems use *rolling daily* windows, so "a new window opens" happens literally every morning. The useful calendar event is the *specific datetime your specific trip becomes bookable*, computed backward from a trip you actually want.
3. **"Book right away" automatically is the risky 20% that creates 80% of the legal/maintenance cost.** Auto-purchase violates these sites' Terms of Service, triggers bot detection, and is what reservation-scalper laws target. The high-value, low-risk product is *instant notification* + a *fast-book assist*, with you clicking buy.

Details and pushback in §7. The rest is the actual spec.

---

## 2. The real landscape (this is the crux)

There is no "the campsite website." A trip within ~3 hours of the Bay Area can live in any of these **independent** systems:

| System | Operator | Bay-Area-relevant coverage | Booking-window model | API reality |
|---|---|---|---|---|
| **Recreation.gov** (the federal "CRS") | Booz Allen Hamilton for USFS/NPS/BLM/USACE | Point Reyes, Golden Gate NRA, Yosemite, national forests (Los Padres, Tahoe), Lake Sonoma | Mostly **rolling 6 months**; some **fixed block release** (e.g. Yosemite ~15th of month, 7am PT); some **lottery** | Undocumented availability JSON endpoint exists; official RIDB API is metadata-only. Akamai + hCaptcha bot defense. |
| **ReserveCalifornia** | Aspira/US eParks for CA State Parks | Mt Tamalpais, Samuel P. Taylor, Angel Island, Big Basin, Henry Cowell, Portola Redwoods, Sunol, Half Moon Bay | **Rolling 6 months**, new day opens **8am PT daily** | Undocumented JSON grid endpoints; aggressive WAF. |
| **EBRPD** (reservations.ebparks.org) | East Bay Regional Park District | Del Valle, Anthony Chabot | Typically shorter (~3 months) | Vendor portal (often ActiveNet/Vermont Systems). |
| **Santa Clara County** (gooutsideandplay.org) | SCC Parks | Coyote Lake, Uvas, Sanborn, Mt Madonna | Varies | Vendor portal. |
| **San Mateo County Parks** | SMC Parks | Memorial Park, Pescadero/Butano area | Varies | Vendor portal. |
| **Sonoma / Marin County** | County depts | Spring Lake, Doran, Bodega Dunes (some via ReserveCalifornia) | Varies | Mixed. |
| **Hipcamp** | Private aggregator | Private land all over NorCal | Host-set, no rolling window | Has a real product/app; ToS prohibits scraping. |

**Implication:** "Monitor all of them" means writing and *maintaining* a separate connector per backend, each of which can break without notice. The 80/20 is **Recreation.gov + ReserveCalifornia**, which together cover the overwhelming majority of public, in-demand camping reachable from the Bay Area. Everything else is a phase-2 connector you add only if a specific park you care about lives there.

---

## 3. Goals & non-goals

### Goals
- **G1 — Window calendar:** For a watchlist of parks/sites/date ranges I care about, compute the *exact datetime each becomes bookable* and put it on my Google Calendar with reminders.
- **G2 — Cancellation watch:** Continuously poll availability for specific (park, site-type, date) queries and alert me within seconds when something opens.
- **G3 — Fast-book assist:** When an alert fires, give me a one-tap deep link straight to the booking flow (and, optionally, pre-filled details) so *I* can complete checkout fast.
- **G4 — Options visibility:** A dashboard / digest of what's currently available across my watched parks, and which release windows are coming up.

### Non-goals (initially)
- **NG1 — Fully autonomous purchase.** No headless bot completing checkout + payment. (See §7.3 — this is a deliberate choice, not an oversight.)
- **NG2 — Covering every backend on day one.** Start with 2 connectors.
- **NG3 — Reselling / multi-user / commercial.** Single-user, personal. This matters legally.
- **NG4 — Beating dedicated scalper bots in a sub-second race.** We optimize for *you reliably hearing first*, not winning every millisecond fight.

---

## 4. Architecture

```
                 ┌────────────────────────────────────────────┐
                 │            Watchlist (your config)          │
                 │  parks, site types, date ranges, prefs      │
                 └───────────────┬────────────────────────────┘
                                 │
        ┌────────────────────────┼─────────────────────────┐
        │                        │                          │
┌───────▼────────┐      ┌────────▼────────┐        ┌────────▼────────┐
│  Connector:    │      │  Connector:     │        │  Connector:     │
│  Recreation.gov│      │ ReserveCalif.   │  ...   │  (phase 2)      │
│  (CRS)         │      │                 │        │  EBRPD / county │
└───────┬────────┘      └────────┬────────┘        └────────┬────────┘
        │  normalized availability + facility metadata       │
        └────────────────────────┬──────────────────────────┘
                                 │
                 ┌───────────────▼────────────────┐
                 │         Core engine             │
                 │  • Window calculator (G1)       │
                 │  • Diff/availability watcher(G2)│
                 │  • Dedup + state store          │
                 └───────┬─────────────────┬───────┘
                         │                 │
              ┌──────────▼─────┐   ┌───────▼─────────────┐
              │ Calendar out   │   │ Alert out           │
              │ • .ics feed or │   │ • Push/SMS/Slack/    │
              │   Google Cal   │   │   Telegram (fast)    │
              │   API (G1/G4)  │   │ • deep link (G3)     │
              └────────────────┘   └─────────────────────┘
```

### Components
- **Connectors** (one per backend): given a query, return normalized availability and facility metadata (release model, release time, rolling-window length). Isolated so one breaking doesn't take down the rest. Each carries its own polite rate-limit + backoff + caching.
- **Window calculator:** the deterministic, ToS-safe core. `bookable_at = trip_start − rolling_window_length`, materialized at the facility's `release_time` and timezone. Handles block-release facilities (e.g. Yosemite monthly) from a small rules table.
- **Availability watcher:** schedules polls per watch item, diffs against last-seen state, emits an event on `unavailable → available` transitions.
- **State store:** SQLite to start. Holds watchlist, last-seen availability, dedup keys, sent-notification log. Single file, trivially backed up.
- **Outputs:**
  - *Calendar:* generate a subscribable **`.ics` feed** (zero-write-permission, you "Add by URL" in Google Calendar) for G1/G4; optionally upgrade to Google Calendar API writes later.
  - *Alerts:* a *fast* channel (push via Pushover/Telegram/SMS) for G2/G3 — **not** calendar, which is the wrong tool for "act in the next 60 seconds."

### Deployment
- A single small always-on worker (cron-style scheduler in one process) on a cheap VM or a scheduled container. Not Jenkins/Nginx/EC2 fleet (the diagram currently in this repo is a generic CI/CD template and unrelated — recommend removing it to avoid confusion).
- Stateless connectors + one SQLite file = a $5/mo box or a free-tier scheduled function is plenty.

---

## 5. Why calendar and alerts are *different* channels

This is the heart of fixing assumption #2.

- **Predictable events → Calendar (G1).** Release windows are deterministic. If you want Mt Tam for Labor Day, ReserveCalifornia's 6-month rolling rule means it opens at **8:00am PT, exactly 6 months prior**. That's a calendar event with a 10-minute reminder. No scraping, no race, no ToS issue — pure arithmetic. Yosemite's monthly block release is the same idea on a different cadence.
- **Unpredictable events → Push (G2).** A cancellation can appear at any second and is gone in seconds. A calendar entry is useless here; you need a phone buzz with a deep link. Calendar latency (sync intervals, notification batching) is minutes — far too slow.

So: **calendar = "be ready at this time"; push = "act now."** Mixing them is why "put every release on my calendar" felt right but would actually bury you.

---

## 6. Data model (sketch)

```
WatchItem
  id, system, park_id, facility_id (optional), site_type,
  date_start, date_end, nights, party_size,
  flexible_dates (bool), weekends_only (bool),
  channels[], active (bool)

Facility (cached metadata)
  system, facility_id, name, timezone,
  release_model = rolling | block | lottery,
  rolling_window_days (e.g. 180), block_release_rule, release_local_time

AvailabilitySnapshot
  watch_item_id, observed_at, available_sites[], hash

NotificationLog
  watch_item_id, type = window|cancellation, sent_at, channel, dedup_key
```

---

## 7. Challenging your assumptions (the part you asked for)

### 7.1 "Monitor *all* the websites"
There is no master list and no shared API. Each backend is bespoke and breaks independently. **Recommendation:** define success as "the parks *I* would actually drive to," not "all websites." Build 2 connectors (Recreation.gov, ReserveCalifornia), add others only when a park you want forces it. Coverage as a goal is a treadmill; a *watchlist* is finishable.

### 7.2 "Put every release date on my calendar"
For rolling systems a window opens every single day — that's 365 useless events/year per park. The signal you actually want is **"the day *my* trip opens,"** computed backward from a trip. **Recommendation:** calendar entries are generated *from your watchlist*, not from the systems' raw cadence.

### 7.3 "So I can book right away" (the big one)
"Right away" implies automation, and full auto-booking is where this gets dangerous:
- **Terms of Service.** Recreation.gov, ReserveCalifornia, and Hipcamp explicitly prohibit automated/bot access and reselling. Auto-checkout violates them outright.
- **Bot defenses.** Akamai, hCaptcha/reCAPTCHA, device fingerprinting, rate limits, and IP bans. An auto-booker is an arms race you'll lose and re-fight monthly.
- **Law & ethics.** Campsite "scalping" bots prompted real legislation (the federal **Saving Our Sequoias / anti-bot reservation** efforts, and state proposals). Even for personal use, automated checkout is squarely the behavior these target. There's also a fairness cost: every site your bot auto-grabs and might cancel is one a family refreshing manually loses.
- **Security.** Auto-checkout means storing your login + payment credentials and a card on a server — a real breach surface for a hobby project.

**Recommendation:** Draw the line at **"notify in seconds + one-tap deep link to the booking flow."** You finish checkout (often <60s on mobile if you're pre-logged-in). You get ~95% of the value, stay inside ToS, store no payment data, and have nothing to maintain against CAPTCHAs. Treat "headless auto-purchase" as an explicit non-goal we can revisit only if you decide to accept those risks knowingly.

### 7.4 "Watch for cancellations" — manage the expectation
Popular cancellations are contested in seconds by existing bots and humans. A notify-the-human design **will lose some races**. It still wins a lot — many cancellations are off-peak, mid-week, or shoulder-season and sit available for minutes. **Recommendation:** be honest that this raises your odds substantially but is not a guarantee, and tune polling/alerting for the cases you can actually win.

### 7.5 Hidden costs you didn't mention
- **Maintenance:** undocumented endpoints change; budget for connectors breaking a few times a year.
- **Politeness/legality of polling:** even read-only polling must be rate-limited and backed-off, or you'll get IP-banned and arguably cross into "unauthorized access" territory if abusive.
- **Notification fatigue:** without good dedup and quiet-hours, a busy watchlist becomes spam you start ignoring — which defeats the purpose.

---

## 8. Options & recommended path

**Option A — Calendar-only (G1 + G4).** Pure arithmetic + `.ics` feed. No scraping, no ToS risk, ships in days. Highest value-to-risk ratio.

**Option B — Calendar + Cancellation alerts + fast-book assist (G1–G4, no auto-purchase).** Adds polling and push. The recommended target product. Medium effort, low/medium risk.

**Option C — B + headless auto-purchase.** Maximum convenience, but ToS-violating, high-maintenance, security-sensitive, ethically and legally exposed. **Not recommended** as a default.

**Recommendation: ship A first (1 connector's metadata + calendar), then grow into B.** Decide on C only as a deliberate, eyes-open choice — not as the implicit goal.

### Suggested phases
1. **Phase 0:** Watchlist config + Facility metadata + Window calculator + `.ics` feed. (Option A, Recreation.gov + ReserveCalifornia metadata only.)
2. **Phase 1:** Availability watcher + push alerts + deep-link fast-book. (Option B.)
3. **Phase 2:** More connectors (EBRPD, county) on demand; availability dashboard; flexible-date / weekends-only matching.
4. **Phase 3 (optional, gated on explicit risk acceptance):** any deeper automation.

---

## 9. Open questions for you

1. **Which specific parks** are actually on your wishlist? (This sizes the connector work — and may collapse it to one system.)
2. **Push channel preference:** Pushover, Telegram, SMS (Twilio), Slack, native iOS push?
3. **Calendar integration depth:** subscribable `.ics` feed (simplest) vs. full Google Calendar API writes on your account?
4. **Risk appetite:** are you firmly in Option B (notify + you click), or do you want to discuss the trade-offs of Option C with eyes open?
5. **Trip pattern:** fixed dates, or "any weekend in September at any of these 4 parks"? (Changes the matching engine.)
6. **Hosting:** do you want this on a personal always-on box, a cloud scheduler, or run on demand?

---

## 10. Tech notes (non-binding)
- **Language:** Python (good HTTP/scheduling ecosystem, easy `.ics` via `ics`/`icalendar`).
- **Store:** SQLite.
- **Scheduler:** APScheduler or a plain async loop; one process.
- **Connectors:** per-backend module behind a common `Connector` interface (`get_metadata`, `query_availability`).
- **Polling etiquette:** per-connector rate limit, exponential backoff on 403/429, randomized jitter, conditional requests/caching, a real contact User-Agent.
- **Secrets:** none required for Option A/B beyond outbound push tokens. No payment data stored.
```
