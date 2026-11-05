"""Adapter registry: maps a session ``environment`` to an adapter class."""
from __future__ import annotations

from app.game.adapters.base import AdapterInfo, GameAdapter
from app.game.adapters.dota_test import DotaTestAdapter
from app.game.adapters.mock import MockGameAdapter

ADAPTERS: dict[str, type[GameAdapter]] = {
    "mock": MockGameAdapter,
    "dota_test": DotaTestAdapter,
}


def create_adapter(environment: str) -> GameAdapter:
    try:
        return ADAPTERS[environment]()
    except KeyError as exc:
        raise ValueError(f"unknown environment '{environment}'") from exc


def adapter_infos() -> list[AdapterInfo]:
    return [cls.info for cls in ADAPTERS.values()]
