"""Local-browser cart-hold (GATED, reference skeleton).

Design choices that make this the least-bad version of a risky feature:
  * Uses a PERSISTENT LOCAL browser profile you control. You log in once,
    interactively, and keep that profile warm. We never see or store your
    password or payment details.
  * Runs non-headless by default — a real, fingerprintable browser, and you can
    watch / take over (e.g. to solve a CAPTCHA) at any moment.
  * Refuses to do anything unless `acknowledge_risk` is set, because enabling it
    can get your reservation account banned (see cart/base.py).

The actual click-path (select site -> pick dates -> "Add to cart") differs per
backend and per A/B test and MUST be reverse-engineered live; the selectors
below are intentionally placeholders so this can't silently misfire.
"""

from __future__ import annotations

import logging

from ..models import AvailableSite
from .base import CartHolder, CartHoldError

log = logging.getLogger(__name__)


class PlaywrightCartHolder(CartHolder):
    def __init__(
        self,
        user_data_dir: str,
        acknowledge_risk: bool = False,
        headless: bool = False,
    ) -> None:
        if not acknowledge_risk:
            raise CartHoldError(
                "cart-hold is disabled: set cart_hold.acknowledge_risk=true only "
                "if you accept the ToS / account-ban risk (see cart/base.py)."
            )
        self._user_data_dir = user_data_dir
        self._headless = headless

    def try_hold(self, site: AvailableSite) -> bool:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise CartHoldError(
                "install playwright to use cart-hold: pip install playwright "
                "&& playwright install chromium"
            ) from exc

        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                self._user_data_dir, headless=self._headless
            )
            page = ctx.new_page()
            try:
                # TODO(live): implement the real add-to-cart flow per backend.
                #   recreation_gov:
                #     1. goto campground page for site.facility_id + start_date
                #     2. ensure logged in (profile is warm); bail if not
                #     3. select site.site_id, set nights, click "Add to Cart"
                #     4. confirm a cart/hold timer is now visible -> return True
                #   If a CAPTCHA appears, surface it (non-headless) for the human.
                raise NotImplementedError(
                    "add-to-cart click-path not yet wired for "
                    f"{site.system}; reverse-engineer + fill in."
                )
            finally:
                ctx.close()
