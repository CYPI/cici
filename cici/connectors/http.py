"""A deliberately polite HTTP session.

Read-only polling of these reservation backends is tolerable only if we behave:
rate-limit ourselves, back off hard on 429/403/503, jitter so we don't look
like a metronome, and identify ourselves honestly. Hammering them is how you
get IP-banned and how casual scraping turns into "unauthorized access."
"""

from __future__ import annotations

import logging
import random
import time

import requests

log = logging.getLogger(__name__)

DEFAULT_UA = (
    "CICI/0.1 (personal campsite watcher; contact: cyril.pinkham@gmail.com)"
)


class PoliteSession:
    def __init__(
        self,
        user_agent: str = DEFAULT_UA,
        min_interval: float = 2.5,
        max_retries: int = 5,
    ) -> None:
        self._s = requests.Session()
        self._s.headers.update({"User-Agent": user_agent, "Accept": "application/json"})
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._last = 0.0

    def get_json(self, url: str, **kw) -> dict:
        return self._request("GET", url, **kw).json()

    def _request(self, method: str, url: str, **kw) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                resp = self._s.request(method, url, timeout=30, **kw)
            except requests.RequestException as exc:  # transient network error
                last_exc = exc
                self._sleep_backoff(attempt, reason=str(exc))
                continue
            if resp.status_code in (429, 403, 503):
                self._sleep_backoff(attempt, reason=f"HTTP {resp.status_code}")
                continue
            resp.raise_for_status()
            return resp
        if last_exc:
            raise last_exc
        raise RuntimeError(f"exhausted retries for {url}")

    def _sleep_backoff(self, attempt: int, reason: str) -> None:
        wait = min(90.0, 2.0 ** attempt) + random.uniform(0, 2.0)
        log.warning("backing off %.1fs (%s)", wait, reason)
        time.sleep(wait)

    def _throttle(self) -> None:
        now = time.monotonic()
        gap = self.min_interval + random.uniform(0, 1.0)
        delta = now - self._last
        if delta < gap:
            time.sleep(gap - delta)
        self._last = time.monotonic()
