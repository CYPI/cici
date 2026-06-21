"""CICI command-line entrypoint.

  python -m cici.main check    -c config/watchlist.yaml   # one pass, print hits
  python -m cici.main watch    -c config/watchlist.yaml   # run the loop forever
  python -m cici.main calendar -c config/watchlist.yaml -o windows.ics  # G1 feed
"""

from __future__ import annotations

import argparse
import logging

from . import config as config_mod
from .cart import build_cart_holder
from .engine.calendar_feed import write_ics
from .engine.watcher import Watcher
from .notify import build_notifiers
from .store import Store


def _setup(args):
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    return config_mod.load(args.config)


def cmd_check(args) -> None:
    cfg = _setup(args)
    notifiers = build_notifiers(cfg.notifiers)
    store = Store(cfg.db_path)
    watcher = Watcher(cfg.watches, notifiers, store, user_agent=cfg.user_agent)
    for watch in cfg.watches:
        if not watch.active:
            continue
        try:
            hits = watcher.tick(watch)
            print(f"[{watch.id}] {len(hits)} new opening(s)")
        except NotImplementedError as exc:
            print(f"[{watch.id}] skipped: {exc}")


def cmd_watch(args) -> None:
    cfg = _setup(args)
    Watcher(
        watches=cfg.watches,
        notifiers=build_notifiers(cfg.notifiers),
        store=Store(cfg.db_path),
        cart_holder=build_cart_holder(cfg.cart_hold),
        poll_interval_s=cfg.poll_interval_s,
        super_interval_s=cfg.super_interval_s,
        user_agent=cfg.user_agent,
    ).run_forever()


def cmd_calendar(args) -> None:
    cfg = _setup(args)
    path = write_ics(cfg.watches, args.output)
    print(f"wrote {path} — subscribe to it in Google Calendar via 'Add by URL'")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="cici")
    p.add_argument("-c", "--config", default="config/watchlist.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("watch").set_defaults(func=cmd_watch)
    cal = sub.add_parser("calendar")
    cal.add_argument("-o", "--output", default="windows.ics")
    cal.set_defaults(func=cmd_calendar)
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
