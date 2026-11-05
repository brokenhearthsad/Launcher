from __future__ import annotations

from types import SimpleNamespace

from tests.conftest import wait_for


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["database"] == "ok"
    assert body["frontend_built"] is False


def test_process_usage_reports_own_process(client):
    body = client.get("/api/system/process").json()
    assert body["pid"] > 0 and body["rss_mb"] > 10 and body["threads"] >= 1
    assert body["cpu_percent"] >= 0 and body["child_processes"] == 0


def test_shutdown_requires_custom_header(client):
    r = client.post("/api/system/shutdown")
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"


def test_shutdown_without_runner_is_conflict(client):
    r = client.post("/api/system/shutdown", headers={"X-Launcher-Request": "1"})
    assert r.status_code == 409


def test_shutdown_sets_should_exit(client):
    server = SimpleNamespace(should_exit=False)
    client.app.state.lab.server = server
    r = client.post("/api/system/shutdown", headers={"X-Launcher-Request": "1"})
    assert r.status_code == 202 and r.json()["status"] == "stopping"
    wait_for(lambda: server.should_exit)


def test_untrusted_host_header_rejected(client):
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
    assert client.get("/api/health", headers={"Host": "localhost:8000"}).status_code == 200


def test_no_simulator_endpoints_left(client):
    for path in ("/api/players", "/api/sessions", "/api/matches/history", "/api/meta"):
        assert client.get(path).status_code == 404


def test_rate_limit(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.conftest import make_settings

    with TestClient(create_app(make_settings(tmp_path, api_rate_limit_per_minute=10))) as c:
        codes = [c.get("/api/logs").status_code for _ in range(12)]
        assert codes[:10] == [200] * 10 and codes[-1] == 429
        assert c.get("/api/health").status_code == 200  # exempt
