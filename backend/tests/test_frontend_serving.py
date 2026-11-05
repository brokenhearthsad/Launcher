from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_settings


def _dist(tmp_path):
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<html><div id=root></div>LAUNCHER</html>", encoding="utf-8")
    (d / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (d / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")
    return d


def test_serves_built_frontend_and_spa_routes(tmp_path):
    _dist(tmp_path)
    with TestClient(create_app(make_settings(tmp_path))) as c:
        assert "LAUNCHER" in c.get("/").text
        assert "LAUNCHER" in c.get("/logs").text  # client-side route
        assert "LAUNCHER" in c.get("/settings/anything").text
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/favicon.svg").text == "<svg/>"
        r = c.get("/api/does-not-exist")
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
        assert "nope" not in c.get("/../secret.txt").text
        assert c.get("/api/health").json()["frontend_built"] is True


def test_explains_missing_build(client):
    r = client.get("/")
    assert r.status_code == 503 and "install.bat" in r.text
