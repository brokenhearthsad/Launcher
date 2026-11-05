from __future__ import annotations

import pytest

from app.ai.profile import BotProfile
from app.domain import GameMode, Role, Scenario, Team
from app.game.actions import Action, ActionType, AdapterError, AdapterNotSupportedError
from app.game.adapters.base import MatchSetup
from app.game.adapters.dota_test import DotaTestAdapter
from app.game.adapters.mock import MockGameAdapter
from app.game.match import MatchController
from app.game.simulator.engine import GameEngine, MatchConfig, SimulationError
from tests.conftest import ROLES, make_setups


def controller(seed=1, scenario=Scenario.BALANCED, mode=GameMode.STANDARD, max_s=3600, profiles=None):
    setups = make_setups()
    profiles = profiles or [BotProfile(i + 1, f"P{i + 1}", ROLES[i % 5]) for i in range(10)]
    mc = MatchController(MockGameAdapter(), MatchSetup(MatchConfig(seed=seed, scenario=scenario, mode=mode,
                                                                   max_game_seconds=max_s), setups), profiles)
    mc.start()
    return mc


def test_requires_five_per_team():
    setups = make_setups()
    with pytest.raises(SimulationError):
        GameEngine(MatchConfig(), setups[:9])
    for s in setups[:6]:
        s.team = Team.RADIANT
    with pytest.raises(SimulationError):
        GameEngine(MatchConfig(), setups)


def test_initial_state():
    e = GameEngine(MatchConfig(), make_setups())
    assert len(e.heroes) == 10 and len(e.towers) == 2 * (9 + 2 + 1)
    assert all(h.gold == 600 and h.level == 1 for h in e.heroes)
    t1 = [t for t in e.towers if t.tier == "t1"]
    assert all(t.vulnerable for t in t1)
    assert not any(t.vulnerable for t in e.towers if t.tier in ("t2", "t3", "t4", "ancient"))


def test_creep_waves_spawn_and_fight():
    e = GameEngine(MatchConfig(), make_setups())
    e.step()
    assert all(len(e.creeps[lane]) == 8 for lane in ("top", "mid", "bot"))
    for _ in range(int(60 / e.config.tick)):
        e.step()
    assert any(c.hp < c.max_hp for lane in e.creeps.values() for c in lane)


def test_deterministic_with_same_seed():
    a, b = controller(seed=5, max_s=900), controller(seed=5, max_s=900)
    a.run_to_end()
    b.run_to_end()
    sa, sb = a.adapter.get_game_state(), b.adapter.get_game_state()
    assert sa["score"] == sb["score"] and sa["heroes"] == sb["heroes"]


def test_different_seeds_differ():
    a, b = controller(seed=1, max_s=900), controller(seed=2, max_s=900)
    a.run_to_end()
    b.run_to_end()
    assert a.adapter.get_game_state()["heroes"] != b.adapter.get_game_state()["heroes"]


def test_full_match_completes_and_bots_play():
    mc = controller(seed=3)
    events = mc.run_to_end()
    e = mc.adapter.engine
    assert e.finished and e.win_condition in ("ancient_destroyed", "time_limit")
    types = {ev.type for ev in events}
    assert {"hero_killed", "tower_destroyed", "item_purchased", "level_up", "ability_cast", "item_used"} <= types
    for h in e.heroes:
        assert h.level > 5, f"{h.name} did not gain experience"
        assert h.gold_earned > 3000, f"{h.name} did not farm"
        assert len(h.items) >= 2, f"{h.name} did not buy items"
    assert sum(h.last_hits for h in e.heroes) > 200
    assert sum(h.tower_damage for h in e.heroes) > 0
    tower_teams = {ev.data["team"] for ev in events if ev.type == "tower_destroyed"}
    assert tower_teams, "towers must fall"
    stats = mc.bot_stats()
    for pid, st in stats.items():
        assert {"farming", "lane", "combat"} <= set(st["intents"]), f"bot {pid} lacks behaviours"


def test_roles_produce_different_play():
    mc = controller(seed=4, max_s=1500)
    mc.run_to_end()
    e = mc.adapter.engine
    carries = [h for h in e.heroes if h.role is Role.CARRY]
    supports = [h for h in e.heroes if h.role is Role.HARD_SUPPORT]
    assert sum(h.last_hits for h in carries) > sum(h.last_hits for h in supports)
    assert any("observer_ward" in ev for ev in mc.brains[5].economy.state.purchases)


def test_time_limit_decides_winner():
    mc = controller(seed=9, max_s=300)
    mc.run_to_end()
    e = mc.adapter.engine
    assert e.finished and e.win_condition == "time_limit" and e.time >= 300


def test_turbo_mode_is_faster_economy():
    std, turbo = controller(seed=6, max_s=600), controller(seed=6, mode=GameMode.TURBO, max_s=600)
    std.run_to_end()
    turbo.run_to_end()
    gold = lambda mc: sum(h.gold_earned for h in mc.adapter.engine.heroes)  # noqa: E731
    assert gold(turbo) > gold(std) * 1.4


def test_mid_only_mode_uses_one_lane():
    mc = controller(seed=2, mode=GameMode.MID_ONLY, max_s=300)
    mc.run_to_end()
    e = mc.adapter.engine
    assert not e.creeps["top"] and not e.creeps["bot"]
    assert all(h.lane == "mid" for h in e.heroes)


def test_scenario_advantage_shifts_economy():
    adv = controller(seed=8, scenario=Scenario.RADIANT_ADVANTAGE, max_s=900)
    adv.run_to_end()
    e = adv.adapter.engine
    assert e.team_net_worth(Team.RADIANT) > e.team_net_worth(Team.DIRE)


def test_bot_settings_change_behaviour():
    passive = [BotProfile(i + 1, f"P{i + 1}", ROLES[i % 5], aggression=0.05, risk_tolerance=0.05) for i in range(10)]
    aggressive = [BotProfile(i + 1, f"P{i + 1}", ROLES[i % 5], aggression=0.95, risk_tolerance=0.95) for i in range(10)]
    a = controller(seed=12, max_s=900, profiles=passive)
    b = controller(seed=12, max_s=900, profiles=aggressive)
    a.run_to_end()
    b.run_to_end()
    combat = lambda mc: sum(s["intents"].get("combat", 0) for s in mc.bot_stats().values())  # noqa: E731
    assert combat(b) > combat(a)


def test_mock_adapter_pause_blocks_progress_and_actions():
    mc = controller(max_s=600)
    ad = mc.adapter
    ad.advance()
    t = ad.game_time
    ad.pause()
    assert ad.advance() == t
    assert ad.execute_action(1, Action(ActionType.HOLD)).ok is False
    ad.resume()
    assert ad.advance() > t
    ad.stop()
    assert ad.outcome().finished and ad.outcome().winner is None


def test_mock_adapter_requires_initialize():
    with pytest.raises(AdapterError):
        MockGameAdapter().get_game_state()


def test_action_validation():
    mc = controller(max_s=600)
    ad = mc.adapter
    ad.advance()
    assert ad.execute_action(1, Action(ActionType.BUY, item="heart")).reason == "not enough gold"
    assert ad.execute_action(1, Action(ActionType.BUY, item="nope")).reason == "unknown item"
    assert ad.execute_action(1, Action(ActionType.CAST, ability="r")).reason == "ability not learned"
    assert ad.execute_action(1, Action(ActionType.ATTACK, target_uid="dire_mid_t2")).ok is False
    assert ad.execute_action(1, Action(ActionType.USE_ITEM, item="blink_dagger")).reason == "item not in inventory"
    assert ad.execute_action(99, Action(ActionType.HOLD)).reason == "unknown player"
    assert ad.execute_action(1, Action(ActionType.BUY, item="healing_salve")).ok


def test_fog_of_war_hides_far_enemies():
    mc = controller(max_s=600)
    ad = mc.adapter
    ad.advance()
    p = ad.get_player_state(1)
    assert p is not None and p.enemies == []  # everyone is in their own base at the start


def test_dota_adapter_explains_unsupported_operations():
    ad = DotaTestAdapter()
    assert ad.info.available is False
    for call in (lambda: ad.connect(), lambda: ad.get_game_state(), lambda: ad.execute_action(1, Action(ActionType.HOLD)),
                 lambda: ad.pause(), lambda: ad.game_time):
        with pytest.raises(AdapterNotSupportedError) as exc:
            call()
        assert "not implemented" in exc.value.reason
