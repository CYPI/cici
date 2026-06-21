"""SQLite state: last-seen availability (for diffing) + a notification log (for
dedup / cooldown). One file, trivially backed up."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS last_seen (
    watch_id TEXT PRIMARY KEY,
    keys     TEXT NOT NULL,        -- newline-joined dedup keys
    updated  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS notif_log (
    dedup_key TEXT PRIMARY KEY,
    sent_at   REAL NOT NULL
);
"""


class Store:
    def __init__(self, path: str | Path = "cici.db") -> None:
        self._db = sqlite3.connect(str(path))
        self._db.executescript(_SCHEMA)
        self._db.commit()

    def get_last_seen(self, watch_id: str) -> set[str]:
        row = self._db.execute(
            "SELECT keys FROM last_seen WHERE watch_id=?", (watch_id,)
        ).fetchone()
        return set(row[0].split("\n")) - {""} if row else set()

    def set_last_seen(self, watch_id: str, keys: set[str]) -> None:
        self._db.execute(
            "INSERT INTO last_seen(watch_id, keys, updated) VALUES(?,?,?) "
            "ON CONFLICT(watch_id) DO UPDATE SET keys=excluded.keys, "
            "updated=excluded.updated",
            (watch_id, "\n".join(sorted(keys)), time.time()),
        )
        self._db.commit()

    def already_notified(self, dedup_key: str, cooldown_s: float) -> bool:
        row = self._db.execute(
            "SELECT sent_at FROM notif_log WHERE dedup_key=?", (dedup_key,)
        ).fetchone()
        return bool(row) and (time.time() - row[0]) < cooldown_s

    def mark_notified(self, dedup_key: str) -> None:
        self._db.execute(
            "INSERT INTO notif_log(dedup_key, sent_at) VALUES(?,?) "
            "ON CONFLICT(dedup_key) DO UPDATE SET sent_at=excluded.sent_at",
            (dedup_key, time.time()),
        )
        self._db.commit()
