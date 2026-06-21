# CICI — Campsite Intelligence & Cancellation Index

Monitors campsite-reservation systems around the Bay Area and the federal CRS,
and helps you grab hard-to-get sites by:

- **📅 Booking-window calendar** — for the trips you want, computes the exact
  moment they become bookable and emits an `.ics` feed for your calendar.
- **🔭 Cancellation watcher** — polls availability and pushes you a deep link the
  instant a matching site opens up.
- **🚨 Super-watcher** — a fast, focused loop for the one site you can't miss,
  with an active-window schedule and an auto-backoff circuit-breaker.
- **🔔 Free notifications** — Signal, email, SMS (carrier gateway), Telegram, or
  console. No paid service required.

It is **notify + fast-book-assist**, by design. It does *not* auto-purchase or
bot your way through checkout — that violates these sites' Terms of Service and
risks your reservation account. See [`docs/SPECIFICATION.md`](docs/SPECIFICATION.md)
§7 for the full reasoning and the assumptions this project deliberately pushes
back on.

---

## How it works (30-second version)

Each backend (Recreation.gov, ReserveCalifornia, …) sits behind a **connector**
that returns normalized availability. The **watcher** polls each of your watch
items, and on every tick it diffs current openings against what it saw last time;
a site flipping **unavailable → available** is a cancellation, and you get an
alert with a deep link straight to the booking page. Predictable *release*
windows are pure arithmetic and go to your **calendar** instead.

```
watchlist.yaml ─▶ connectors ─▶ watcher (poll → diff → alert) ─▶ Signal/email/SMS
                      │
                      └─────────▶ calendar feed (.ics) for release windows
```

More detail: [`docs/CANCELLATION_WATCHING.md`](docs/CANCELLATION_WATCHING.md) and
[`docs/SUPER_WATCHER.md`](docs/SUPER_WATCHER.md).

---

## Install

Requires Python 3.11+.

```bash
git clone <repo-url> && cd cici
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Copy the example and edit it:

```bash
cp config/watchlist.example.yaml config/watchlist.yaml
```

A watch item looks like:

```yaml
watches:
  - id: pointreyes-coast-weekends
    system: recreation_gov
    facility_id: "233359"            # Recreation.gov campground id
    facility_name: "Point Reyes — Coast Camp"
    date_start: 2026-08-01
    date_end: 2026-09-30
    nights: 2
    weekends_only: true              # only Fri/Sat check-ins
    site_filter: { loop: "COAST" }   # match a loop / site type
    channels: [console, signal]
```

**Finding a `facility_id`:** open the campground on recreation.gov; the number in
the URL `…/camping/campgrounds/<ID>` is it. For grouped backcountry campgrounds
(like Point Reyes), point at the campground id and narrow with `site_filter`
(e.g. `loop: "COAST"`).

### Notifications (pick any; all free)

```yaml
notifiers:
  signal:                            # via local signal-cli — see docs
    account: "+1XXXXXXXXXX"          # dedicated number signal-cli is registered with
    recipients: ["+1XXXXXXXXXX"]
  email:                             # Gmail SMTP + a free App Password
    smtp_host: smtp.gmail.com
    smtp_port: 587
    username: you@gmail.com
    password: "app-password"
    to: [you@gmail.com]
  sms:                               # carrier email-to-SMS gateway (reuses email creds)
    gateways: ["5105551234@tmomail.net"]
```

Then list the channels you want on each watch via `channels: [...]`.

---

## Usage

```bash
# One pass — print current matching openings (great for a quick test)
python -m cici.main check    -c config/watchlist.yaml

# Run continuously — watch + alert until you stop it
python -m cici.main watch    -c config/watchlist.yaml

# Generate the booking-window calendar feed for your watchlist
python -m cici.main calendar -c config/watchlist.yaml -o windows.ics
```

Subscribe to `windows.ics` in Google Calendar via **Add by URL** (host it
somewhere reachable, or import the file) — no account write-access needed.

### The super-watcher

Mark a must-not-miss site with `super: true` and give it a tight cadence plus an
active window so it only sprints when it matters:

```yaml
  - id: kirby-cove-fri-night
    system: recreation_gov
    facility_id: "10043061"
    facility_name: "Kirby Cove"
    date_start: 2026-08-28
    date_end: 2026-09-07
    nights: 2
    weekends_only: true
    super: true
    interval_s: 10                   # seconds (faster = more ban risk)
    schedule:
      days: [thu, fri, sat, sun]
      hours: "06:00-23:59"           # facility-local time
      off_window_interval_s: 600
    channels: [console, signal, email]
```

---

## Testing it

There's a ready-made one-shot test for **Coast Camp at Point Reyes**, Fri/Sat
check-ins over the next three weeks:

```bash
python -m cici.main check -c config/coast-camp-test.yaml
```

Expected output:

```
[coast-camp-test] N new opening(s)
🏕️ Opening — Point Reyes — Coast Camp · Site 007
   2026-06-26 (1n) · COAST CAMP
   https://www.recreation.gov/camping/campgrounds/233359?startDate=2026-06-26
```

(`N` is however many Coast-loop sites are open on a Friday/Saturday in the window;
it's `0` when nothing's available — run `watch` to be alerted when one appears.)

> **Heads-up — run this from your own machine.** Recreation.gov's availability
> API is behind Akamai bot-defense that **403s datacenter/CI traffic** and
> sometimes a non-browser User-Agent. From a normal residential connection it
> works; if you still get throttled, set a browser `user_agent` under `settings:`
> (the config files show how) and retry. This cat-and-mouse is expected for an
> undocumented endpoint — see the spec.

### Developer smoke tests

The core logic (consecutive-night runs, the poll→diff→alert transition, dedup,
active-window scheduling, circuit-breaker backoff) is pure-Python and testable
without network. Quick compile check:

```bash
python -m py_compile cici/*.py cici/*/*.py
```

---

## Safety, etiquette & limitations

- **Be a good citizen.** Polling is rate-limited, jittered, and backs off on
  403/429; don't crank intervals to the floor. Abusive polling gets your IP
  banned and is how read-only scraping turns into "unauthorized access."
- **No auto-booking.** Cart-hold / auto-purchase is intentionally out of scope
  (gated off in `cici/cart/`); it violates ToS and risks your account.
- **Not a guarantee.** This raises your odds a lot, especially on the frequent
  mid-week / shoulder-season cancellations. It will not win every sub-second race
  for marquee summer weekends.
- **Connectors drift.** Undocumented endpoints change; expect occasional fixes.
  ReserveCalifornia is a Phase-1 stub today (Recreation.gov is wired first).

## Project layout

```
cici/
  connectors/   backend adapters (recreation_gov, reserve_california, http)
  engine/       watcher, window_calculator, calendar_feed, schedule
  notify/       signal, email/sms, telegram, pushover, console
  cart/         gated/off auto-cart module (not used by default)
  config.py · models.py · store.py · main.py
config/         example + Coast Camp test watchlists
docs/           SPECIFICATION, CANCELLATION_WATCHING, SUPER_WATCHER
```

See [`docs/SPECIFICATION.md`](docs/SPECIFICATION.md) for goals, architecture, the
phased roadmap, and the assumption-challenges behind the design.
