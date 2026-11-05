"""GSI configuration installer: plan -> confirm -> backup -> write; uninstall; restore."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.integrations.vdf import get_ci, loads
from app.main import create_app
from app.services.gsi_installer import CFG_NAME, MARKER
from tests.conftest import make_settings
from tests.test_environment import make_layout

H = {"X-Launcher-Request": "1"}


@pytest.fixture
def lab(tmp_path):
    steam, lib = make_layout(tmp_path)
    game_dota = lib / "steamapps" / "common" / "dota 2 beta" / "game" / "dota"
    (game_dota / "cfg").mkdir(parents=True)
    other = game_dota / "cfg" / "gamestate_integration"
    other.mkdir()
    (other / "gamestate_integration_obs.cfg").write_text('"OBS" { "uri" "http://127.0.0.1:3000" }', encoding="utf-8")
    with TestClient(create_app(make_settings(tmp_path, steam_path=steam))) as c:
        yield c, other / CFG_NAME, other / "gamestate_integration_obs.cfg", steam


def plan(c):
    return c.get("/api/gsi/config").json()


def test_check_reports_plan_without_leaking_token(lab):
    c, target, _, _ = lab
    cfg = plan(c)
    token = c.app.state.lab.gsi.token
    assert cfg["available"] and not cfg["exists"] and not cfg["installed"]
    assert cfg["plan"]["action"] == "create" and cfg["plan"]["backup_before_change"] is False
    assert cfg["other_configs"] == ["gamestate_integration_obs.cfg"]
    assert cfg["expected_uri"] == "http://127.0.0.1:8000/gsi"
    assert "http://127.0.0.1:8000/gsi" in cfg["plan"]["new_content"] and "••••" in cfg["plan"]["new_content"]
    assert token not in json.dumps(cfg)
    assert not target.exists(), "checking must not write anything"


def test_install_requires_header_confirmation_and_current_plan(lab):
    c, target, _, _ = lab
    p = plan(c)["plan"]
    assert c.post("/api/gsi/install", json={"plan_id": p["plan_id"], "confirm": True}).status_code == 403
    assert c.post("/api/gsi/install", json={"plan_id": p["plan_id"]}, headers=H).status_code == 422
    assert c.post("/api/gsi/install", json={"plan_id": "0" * 128, "confirm": True}, headers=H).status_code == 409
    assert not target.exists()
    r = c.post("/api/gsi/install", json={"plan_id": p["plan_id"], "confirm": True}, headers=H)
    assert r.status_code == 200 and r.json()["changed"] and r.json()["backup"] is None
    text = target.read_text(encoding="utf-8")
    assert text.startswith(MARKER)
    block = next(iter(loads(text).values()))
    assert get_ci(block, "uri") == "http://127.0.0.1:8000/gsi"
    assert get_ci(get_ci(block, "auth"), "token") == c.app.state.lab.gsi.token
    after = plan(c)
    assert after["installed"] and after["up_to_date"] and after["plan"]["action"] == "none"
    types = [e["type"] for e in c.get("/api/events", params={"source": "gsi"}).json()["items"]]
    assert "config_installed" in types


def test_installed_token_is_accepted_by_receiver(lab):
    c, target, _, _ = lab
    c.post("/api/gsi/install", json={"plan_id": plan(c)["plan"]["plan_id"], "confirm": True}, headers=H)
    token = get_ci(get_ci(next(iter(loads(target.read_text(encoding="utf-8")).values())), "auth"), "token")
    assert c.post("/gsi", json={"provider": {"name": "Dota 2"}, "auth": {"token": token}}).status_code == 200


def test_other_configs_are_never_touched(lab):
    c, _, other, _ = lab
    before = other.read_bytes()
    c.post("/api/gsi/install", json={"plan_id": plan(c)["plan"]["plan_id"], "confirm": True}, headers=H)
    c.post("/api/gsi/uninstall", json={"confirm": True}, headers=H)
    assert other.read_bytes() == before


def test_foreign_file_is_backed_up_before_replacement(lab):
    c, target, _, _ = lab
    target.write_text('"Someone else" { "uri" "http://127.0.0.1:9999/" }', encoding="utf-8")
    cfg = plan(c)
    assert cfg["exists"] and not cfg["managed"] and cfg["plan"]["action"] == "replace_foreign"
    assert cfg["plan"]["backup_before_change"] and "Someone else" in cfg["plan"]["current_content"]
    # not removable: it is not Launcher's file
    assert c.post("/api/gsi/uninstall", json={"confirm": True}, headers=H).status_code == 409
    r = c.post("/api/gsi/install", json={"plan_id": cfg["plan"]["plan_id"], "confirm": True}, headers=H).json()
    backups = c.get("/api/gsi/backups").json()
    assert r["backup"] == backups[0]["name"] and backups[0]["managed"] is False
    saved = c.app.state.lab.gsi_installer.backup_dir / r["backup"]
    assert "Someone else" in saved.read_text(encoding="utf-8")


def test_file_changed_after_preview_is_not_overwritten(lab):
    c, target, _, _ = lab
    p = plan(c)["plan"]
    target.write_text("// edited by the user after preview", encoding="utf-8")
    assert c.post("/api/gsi/install", json={"plan_id": p["plan_id"], "confirm": True}, headers=H).status_code == 409
    assert target.read_text(encoding="utf-8") == "// edited by the user after preview"


def test_update_existing_managed_file_makes_backup(lab):
    c, target, _, _ = lab
    c.post("/api/gsi/install", json={"plan_id": plan(c)["plan"]["plan_id"], "confirm": True}, headers=H)
    target.write_text(target.read_text(encoding="utf-8").replace('"0.5"', '"0.1"'), encoding="utf-8")
    p = plan(c)["plan"]
    assert p["action"] == "update" and p["backup_before_change"]
    r = c.post("/api/gsi/install", json={"plan_id": p["plan_id"], "confirm": True}, headers=H).json()
    assert r["backup"].endswith("before_install.cfg") and plan(c)["up_to_date"]


def test_uninstall_only_with_confirmation_and_keeps_backup(lab):
    c, target, _, _ = lab
    assert c.post("/api/gsi/uninstall", json={"confirm": True}, headers=H).status_code == 404
    c.post("/api/gsi/install", json={"plan_id": plan(c)["plan"]["plan_id"], "confirm": True}, headers=H)
    assert c.post("/api/gsi/uninstall", json={"confirm": False}, headers=H).status_code == 422
    assert c.post("/api/gsi/uninstall", json={"confirm": True}).status_code == 403
    r = c.post("/api/gsi/uninstall", json={"confirm": True}, headers=H).json()
    assert r["removed"] and not target.exists()
    assert any(b["name"] == r["backup"] and b["managed"] for b in c.get("/api/gsi/backups").json())


def test_restore_backup(lab):
    c, target, _, _ = lab
    target.write_text("// my original config", encoding="utf-8")
    cfg = plan(c)
    first_backup = c.post("/api/gsi/install", json={"plan_id": cfg["plan"]["plan_id"], "confirm": True},
                          headers=H).json()["backup"]
    assert c.post("/api/gsi/restore", json={"name": "../../etc/passwd", "confirm": True}, headers=H).status_code == 422
    assert c.post("/api/gsi/restore", json={"name": "20990101-000000-x.cfg", "confirm": True}, headers=H).status_code == 404
    assert c.post("/api/gsi/restore", json={"name": first_backup}, headers=H).status_code == 422
    r = c.post("/api/gsi/restore", json={"name": first_backup, "confirm": True}, headers=H).json()
    assert target.read_text(encoding="utf-8") == "// my original config"
    assert r["backup"] and r["backup"].endswith("before_restore.cfg"), "current file is backed up before restore"
    assert "config_restored" in [e["type"] for e in c.get("/api/events", params={"source": "gsi"}).json()["items"]]


def test_no_dota_means_no_install(tmp_path):
    with TestClient(create_app(make_settings(tmp_path, steam_path=tmp_path / "nope"))) as c:
        cfg = c.get("/api/gsi/config").json()
        assert cfg["available"] is False and cfg["error"] and cfg["plan"] is None
        assert c.post("/api/gsi/install", json={"plan_id": "0" * 128, "confirm": True}, headers=H).status_code == 409


@pytest.mark.parametrize("options,expected", [("-novid -gamestateintegration", True), ("-novid", False)])
def test_launch_option_detection(lab, options, expected):
    c, _, _, steam = lab
    cfg_dir = Path(steam) / "userdata" / "123456" / "config"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "localconfig.vdf").write_text(
        '"UserLocalConfigStore" { "Software" { "Valve" { "Steam" { "apps" { "570" { "LaunchOptions" "'
        + options + '" } } } } } }', encoding="utf-8")
    lo = plan(c)["launch_option"]
    assert lo == {"checked": True, "found": expected, "accounts": 1}


def test_launch_option_unknown_without_userdata(lab):
    c, _, _, _ = lab
    assert plan(c)["launch_option"] == {"checked": False, "found": None, "accounts": 0}
