"""Cart-hold (gated). See base.py before enabling."""

from __future__ import annotations

from .base import CartHolder, CartHoldError


def build_cart_holder(cfg: dict | None):
    """Return a CartHolder if config explicitly enables it, else None."""
    if not cfg or not cfg.get("enabled"):
        return None
    from .browser_playwright import PlaywrightCartHolder

    return PlaywrightCartHolder(
        user_data_dir=cfg["user_data_dir"],
        acknowledge_risk=cfg.get("acknowledge_risk", False),
        headless=cfg.get("headless", False),
    )


__all__ = ["CartHolder", "CartHoldError", "build_cart_holder"]
