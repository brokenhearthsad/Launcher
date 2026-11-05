"""GSI parser and state machine (pure logic, synthetic fixtures)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.integrations.gsi.heroes import hero_display_name
from app.integrations.gsi.parser import PayloadError, parse
from app.integrations.gsi.tracker import GsiTracker

FIX = Path(__file__).parent / "fixtures" / "gsi"


def load(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def test_full_in_game_payload():
    s = parse(load("playing"))
    assert s.problems == []
    assert s.game_state == "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS" and s.game_state_label == "Игра идёт"
    assert s.game_time == 754 and s.clock_time == 664 and s.match_id == "9000000001" and s.map_name == "start"
    assert (s.radiant_score, s.dire_score) == (7, 4) and s.win_team is None
    assert s.hero_internal == "npc_dota_hero_antimage" and s.hero_name == "Anti-Mage" and s.hero_level == 11
    assert (s.health, s.max_health, s.mana, s.max_mana) == (812, 1210, 210, 482)
    assert (s.kills, s.deaths, s.assists, s.last_hits, s.gpm) == (3, 1, 5, 61, 412)
    assert [a.name for a in s.abilities] == ["antimage_mana_break", "antimage_blink", "antimage_mana_void"]
    assert s.abilities[2].ultimate is True and s.abilities[1].cooldown == 3
    assert [i.slot for i in s.items] == ["slot0", "slot1", "teleport0"], "empty slots are skipped"
    assert s.items[2].charges == 1


def test_personal_identifiers_are_not_kept():
    d = parse(load("playing")).to_dict()
    text = json.dumps(d)
    assert "76561190000000000" not in text and "SHOULD-NOT-BE-STORED" not in text
    assert "steamid" not in d and "accountid" not in d


def test_menu_payload_has_no_game_data():
    s = parse(load("menu"))
    assert not s.has_map and not s.has_hero and s.activity == "menu"
    assert s.game_state is None and s.game_time is None and s.hero_name is None and s.radiant_score is None


def test_hero_selection_with_placeholder_hero():
    s = parse(load("hero_selection"))
    assert s.has_map and not s.has_hero and s.hero_name is None and s.hero_level is None
    assert s.game_state_label == "Выбор героев"


def test_wrong_types_become_missing_and_are_reported():
    s = parse(load("malformed_types"))
    assert s.provider_name is None and s.game_time is None and s.radiant_score is None and s.paused is None
    assert s.hero_level is None and s.health is None and s.max_health == 900
    assert s.game_state == "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS" and s.hero_name == "Zeus"
    assert s.abilities == [] and s.items == []
    joined = " ".join(s.problems)
    for key in ("provider", "map.game_time", "map.radiant_score", "hero.level", "hero.health", "abilities", "items.slot0"):
        assert key in joined, key


@pytest.mark.parametrize("bad", [[], "text", 5, None])
def test_non_object_payload_rejected(bad):
    with pytest.raises(PayloadError):
        parse(bad)


def test_unknown_state_label_passthrough():
    s = parse({"map": {"game_state": "DOTA_GAMERULES_STATE_SOMETHING_NEW"}})
    assert s.game_state_label == "DOTA_GAMERULES_STATE_SOMETHING_NEW"


@pytest.mark.parametrize("internal,name", [("npc_dota_hero_nevermore", "Shadow Fiend"),
                                           ("npc_dota_hero_drow_ranger", "Drow Ranger"),
                                           ("npc_dota_hero_furion", "Nature's Prophet"), (None, None)])
def test_hero_names(internal, name):
    assert hero_display_name(internal) == name


# ----------------------------------------------------------------------------- tracker
def types(evs):
    return [e.type for e in evs]


def test_lifecycle_events_in_order():
    t = GsiTracker(stale_seconds=40)
    assert t.freshness(0) == "never"
    assert types(t.apply(parse(load("menu")), 0, 1000)) == ["connected"]
    evs = t.apply(parse(load("hero_selection")), 1, 1001)
    assert types(evs) == ["first_state", "phase_changed"]
    evs = t.apply(parse(load("playing")), 2, 1002)
    assert types(evs) == ["phase_changed", "game_started"]
    assert evs[0].data == {"from": "DOTA_GAMERULES_STATE_HERO_SELECTION", "to": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS"}
    assert t.apply(parse(load("playing")), 3, 1003) == [], "unchanged state produces no events"
    evs = t.apply(parse(load("post_game")), 4, 1004)
    assert types(evs) == ["phase_changed", "game_ended"] and evs[1].data["win_team"] == "radiant"
    assert t.updates == 5


def test_leaving_match_ends_game():
    t = GsiTracker()
    t.apply(parse(load("playing")), 0, 0)
    evs = t.apply(parse(load("menu")), 1, 1)
    assert "game_ended" in types(evs) and "игрок вышел" in evs[-1].message
    assert evs[-1].data["game_time"] == 754


def test_freshness_and_stale_event_once():
    t = GsiTracker(stale_seconds=40, fresh_seconds=5)
    t.apply(parse(load("playing")), 100, 0)
    assert t.freshness(103) == "fresh" and t.freshness(130) == "delayed" and t.freshness(141) == "stale"
    assert t.check_stale(130) == []
    assert types(t.check_stale(141)) == ["stale"]
    assert t.check_stale(200) == [], "stale is reported once"
    assert types(t.apply(parse(load("playing")), 201, 1)) == ["connected"], "reconnect after stale"


def test_format_problems_counted():
    t = GsiTracker()
    t.apply(parse(load("malformed_types")), 0, 0)
    assert t.format_errors == 1
