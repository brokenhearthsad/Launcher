from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain import Role, Team
from app.game.simulator.engine import HeroSetup
from app.main import create_app

HEROES = ["juggernaut", "shadow_fiend", "axe", "earthshaker", "crystal_maiden",
          "phantom_assassin", "lina", "mars", "mirana", "lion"]
ROLES = [Role.CARRY, Role.MID, Role.OFFLANE, Role.SOFT_SUPPORT, Role.HARD_SUPPORT]
LANES = {Role.CARRY: "safe", Role.MID: "mid", Role.OFFLANE: "off", Role.SOFT_SUPPORT: "off",
         Role.HARD_SUPPORT: "safe"}


def make_setups() -> list[HeroSetup]:
    return [HeroSetup(i + 1, f"P{i + 1}", Team.RADIANT if i < 5 else Team.DIRE, ROLES[i % 5], HEROES[i],
                      LANES[ROLES[i % 5]]) for i in range(10)]


def make_settings(tmp_path: Path, **overrides) -> Settings:
    values = dict(database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}", log_dir=tmp_path / "logs",
                  api_rate_limit_per_minute=100_000, ws_publish_hz=10.0, log_level="INFO")
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def wait_for(predicate, timeout: float = 60.0, interval: float = 0.1):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    raise AssertionError("condition not met in time")
