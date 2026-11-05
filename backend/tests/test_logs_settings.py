from __future__ import annotations

import logging

from app.logging_config import get_db_handler, get_logger


def _flush():
    get_db_handler().flush()


def test_logs_are_persisted_and_filterable(client):
    get_logger("probe").warning("hello from probe")
    _flush()
    logs = client.get("/api/logs").json()
    assert logs["total"] > 0
    assert "probe" in client.get("/api/logs/components").json()
    only = client.get("/api/logs", params={"component": "probe"}).json()["items"]
    assert only and all(r["component"] == "probe" for r in only)
    assert client.get("/api/logs", params={"search": "hello from"}).json()["items"]
    warn = client.get("/api/logs", params={"level": "WARNING"}).json()["items"]
    assert all(r["level"] == "WARNING" for r in warn) and warn
    assert client.get("/api/logs", params={"page_size": 500}).status_code == 422


def test_settings_roundtrip_and_effect(client):
    s = client.get("/api/settings").json()
    assert s["runtime"]["ws_publish_hz"] > 0 and s["database"]["dialect"] == "sqlite"
    assert s["backend"]["lower_own_priority"] is False
    r = client.put("/api/settings", json={"ui_refresh_seconds": 9, "log_level": "DEBUG"})
    assert r.status_code == 200 and r.json()["ui_refresh_seconds"] == 9
    assert client.get("/api/settings").json()["runtime"]["ui_refresh_seconds"] == 9
    assert logging.getLogger("dml").level == logging.DEBUG
    assert client.put("/api/settings", json={"log_level": "LOUD"}).status_code == 422
    client.put("/api/settings", json={"log_level": "INFO"})


def test_old_simulator_settings_keys_are_ignored(client):
    from app.db.models import AppSetting
    from app.db.session import session_scope

    with session_scope() as db:
        row = db.get(AppSetting, "runtime")
        if row is None:
            db.add(AppSetting(key="runtime", value={"default_speed": 50, "ui_refresh_seconds": 7}))
        else:
            row.value = {"default_speed": 50, "ui_refresh_seconds": 7}
    runtime = client.get("/api/settings").json()["runtime"]
    assert "default_speed" not in runtime


def test_database_maintenance(client):
    assert "size_after" in client.post("/api/settings/database/vacuum").json()
    assert client.post("/api/settings/database/purge-logs", json={"older_than_days": 0}).status_code == 200
