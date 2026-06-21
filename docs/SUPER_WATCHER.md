# The Super Watcher

For the one site you *cannot* miss (a coveted Friday-night / weekend / long-weekend
spot). It polls far faster than the regular watcher to maximize your odds of
catching a cancellation first.

## How it differs from the regular watcher

| | Regular | Super |
|---|---|---|
| Cadence | ~90s | ~10–15s (configurable) |
| Loop | shared round-robin | its own due-time in the scheduler, never blocked by slow watches |
| Schedule | always on | optional **active window** (e.g. Thu–Sun, 6am–midnight) |
| Throttle response | backs off | backs off **per-watch** via a circuit-breaker |
| Alert label | 🏕️ Opening | 🚨 SUPER |

Enable it on a watch with `super: true` and (optionally) `interval_s`, plus a
`schedule`. See `config/watchlist.example.yaml` for a full example.

## Why it is not just "poll every 5 seconds forever"

A flat 5s poll, 24/7, is the *fastest way to get your IP/account flagged* by
Recreation.gov's bot defenses (Akamai/hCaptcha) — which would lose you the exact
reservation you cared about most. So the super-watcher is fast **where it counts**
and protects access everywhere else:

1. **Active window** — sprint only when bookings actually turn over for your
   target (Friday evenings, weekends, the days around a long weekend). Outside the
   window it idles at `off_window_interval_s` (default 10 min). Times are in the
   facility's local timezone.
2. **Circuit-breaker** — if the backend starts returning 403/429, that watch
   automatically backs off exponentially (up to ~64×), then recovers once it's
   happy again. It never digs in against a block.
3. **Tight jitter** — small randomization so it's fast but not a perfectly
   detectable metronome.

You *can* set `interval_s: 5`, but treat the floor as eyes-open: faster cadence
trades higher catch-rate for higher ban risk. ~10–15s inside a focused window is
the sweet spot.

## Notifications (no backend, no paid service)

The super-watcher (and every watcher) can alert through:

- **Email** — plain Gmail SMTP with a free [App Password]. No server, no cost.
- **SMS** — your carrier's free **email-to-SMS gateway** (e.g.
  `5105551234@tmomail.net`). It reuses the email SMTP credentials, so configuring
  email enables SMS too. Best-effort: some carriers throttle or have curtailed
  gateways, so keep email (or Telegram) as the reliable channel and treat SMS as
  a bonus buzz.
- **Signal** — via local [`signal-cli`]: free, no paid service, no third-party
  server, and a legitimate client (no ban risk). One-time setup: register
  signal-cli with a *dedicated* phone number. See its header in
  `cici/notify/signal_cli.py`.
- **Telegram** — the fastest *free* push if you want phone notifications without
  relying on carrier gateways (just create a bot, no backend).
- **WhatsApp** — not built: the official Cloud API needs a Meta Business account
  + approved template messages (a cloud service), and the unofficial route
  violates ToS and risks a number ban. Use Signal instead.
- **Console** — rings the terminal bell (`\a`) on urgent hits when you're at your
  machine.

Set the channels per watch, e.g. `channels: [console, email, sms]`.

## Reality check

This meaningfully raises your odds on a contested site — it does **not** guarantee
a booking. Marquee summer weekends are fought over in sub-second windows by
dedicated bots; a polite, ban-avoiding watcher will win many cancellations
(especially the frequent mid-week/shoulder ones) but not every race.
