from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_settings(tmp_path: Path, **overrides) -> Settings:
    values = dict(
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        backup_dir=tmp_path / "backups",
        log_dir=tmp_path / "logs",
        frontend_dist=tmp_path / "dist",
        allowed_hosts=["localhost", "127.0.0.1", "testserver"],
        api_rate_limit_per_minute=100_000,
        log_level="INFO",
    )
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


def wait_for(predicate, timeout: float = 10.0, interval: float = 0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    raise AssertionError("condition not met in time")
