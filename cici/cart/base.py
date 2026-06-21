"""Cart-hold contract.

A "cart hold" means: when a cancellation appears, programmatically add the site
to *your* cart so the backend's ~15-minute hold timer locks it, then send you a
deep link to the cart to finish payment by hand.

Read this before enabling it (config `cart_hold.enabled: true`):

  * It requires authenticated, automated actions against the reservation
    backend. That is exactly the behavior these sites' Terms of Service
    prohibit, and it is what their bot defenses (Akamai, hCaptcha) try to stop.
  * The realistic consequence of getting flagged is a banned reservation
    account — the same account you need to actually camp. That's hard to undo.
  * So this is NOT the "safe" part of Option B. Risk-wise it's nearly Option C
    (only the final "pay" click stays manual).

To keep it as low-harm as possible, the reference implementation drives YOUR
OWN local, already-logged-in browser profile (you log in and solve any CAPTCHA
yourself; we store no passwords and no card). It is gated off by default and
will refuse to run unless you set `acknowledge_risk: true` in config.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import AvailableSite


class CartHoldError(RuntimeError):
    pass


class CartHolder(ABC):
    @abstractmethod
    def try_hold(self, site: AvailableSite) -> bool:
        """Attempt to place `site` in the cart. Return True on success."""
