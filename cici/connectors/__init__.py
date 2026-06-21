"""Connector registry."""

from __future__ import annotations

from .base import Connector
from .recreation_gov import RecreationGovConnector
from .reserve_california import ReserveCaliforniaConnector

_REGISTRY: dict[str, type[Connector]] = {
    RecreationGovConnector.system: RecreationGovConnector,
    ReserveCaliforniaConnector.system: ReserveCaliforniaConnector,
}


def get_connector(system: str) -> Connector:
    try:
        return _REGISTRY[system]()
    except KeyError:
        raise ValueError(
            f"no connector for system {system!r}; known: {sorted(_REGISTRY)}"
        ) from None
