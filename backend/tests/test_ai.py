"""Unit tests for AI subsystems using hand-built situations in the real simulator."""
from __future__ import annotations

import random

import pytest

from app.ai.bot import BotBrain
from app.ai.combat import CombatAI
from app.ai.common import BotMemory, Candidate, SubsystemContext
from app.ai.decision import DecisionEngine
from app.ai.economy import EconomyAI
from app.ai.farming import FarmingAI
from app.ai.items import ItemAI
from app.ai.lane import LaneAI, lane_front
from app.ai.perception import TeamDirective
from app.ai.profile import BotProfile
from app.ai.team import TeamAI
from app.domain import Difficulty, Role, Scenario, Team
from app.game.actions import Action, ActionResult, ActionType
from app.game.adapters.base import MatchSetup
from app.game.adapters.mock import MockGameAdapter
from app.game.catalog import ITEMS
from app.game.simulator.engine import MatchConfig
from app.game.simulator.entities import Creep, ItemSlot
from app.game.simulator.map import LANE_PATHS, dist
from tests.conftest import make_setups


@pytest.fixture
def adapter():
    ad = MockGameAdapter()
    ad.initialize(MatchSetup(MatchConfig(seed=1), make_setups()))
    ad.connect()
    ad.advance()
    return ad


def prof(pid=1, role=Role.CARRY, **kw):
    return BotProfile(pid, f"P{pid}", role, **kw)


def ctx_for(adapter, pid=1, **kw):
    p = adapter.get_player_state(pid)
    return SubsystemContext(p, prof(pid, p.me.role, **kw), BotMemory())


def place_lane(adapter, pid=1, fraction=0.38):
    h = adapter.engine.hero_by_player(pid)
    path = LANE_PATHS[h.lane]
    h.pos = path.point_for_team(h.team, fraction)
    return h


def add_creep(adapter, team, pos, hp, lane="bot"):
    e = adapter.engine
    path = LANE_PATHS[lane]
    c = Creep(e._uid("c"), "creep", team, pos, 550, hp, 2, 21, 1, 1, lane=lane, s=path.project(pos))
    e.creeps[lane].append(c)
    return c


# ----------------------------------------------------------------------------- lane
def test_lane_ai_holds_assigned_lane(adapter):
    h = place_lane(adapter, 1, 0.2)
    lane = LaneAI()
    cands = lane.propose(ctx_for(adapter))
    assert lane.assigned_lane == h.lane == "bot"
    move = [c for c in cands if c.action.type in (ActionType.MOVE, ActionType.HOLD)][0]
    assert "hold bot lane" in move.action.intent


def test_lane_front_follows_allied_creeps(adapter):
    p = adapter.get_player_state(1)
    front = lane_front(p, "bot")
    assert dist(front, LANE_PATHS["bot"].point_at(0)) < 25  # creeps just spawned near base


def test_lane_ai_avoids_enemy_tower_without_creeps(adapter):
    e = adapter.engine
    h = e.hero_by_player(1)
    for lane in e.creeps:
        e.creeps[lane].clear()
    tower = e.units["dire_bot_t1"]
    h.pos = tower.pos
    cands = LaneAI().propose(ctx_for(adapter))
    target = cands[-1].action.pos
    assert target is not None and dist(target, tower.pos) > 4.4


# ----------------------------------------------------------------------------- farming
def test_farming_last_hits_low_creep(adapter):
    h = place_lane(adapter)
    for lane in adapter.engine.creeps.values():
        lane.clear()
    low = add_creep(adapter, Team.DIRE, (h.pos[0] + 0.5, h.pos[1]), hp=30)
    add_creep(adapter, Team.DIRE, (h.pos[0] + 0.6, h.pos[1]), hp=500)
    farming = FarmingAI(random.Random(1))
    cands = farming.propose(ctx_for(adapter, difficulty=Difficulty.EXPERT))
    lh = [c for c in cands if c.action.intent == "last hit"]
    assert lh and lh[0].action.target_uid == low.uid and lh[0].action.hp_threshold is not None


def test_farming_denies_low_allied_creep(adapter):
    h = place_lane(adapter)
    for lane in adapter.engine.creeps.values():
        lane.clear()
    mine = add_creep(adapter, Team.RADIANT, (h.pos[0] + 0.4, h.pos[1]), hp=25)
    cands = FarmingAI(random.Random(1)).propose(ctx_for(adapter))
    assert any(c.action.intent == "deny" and c.action.target_uid == mine.uid for c in cands)


def test_last_hit_executes_and_awards_gold(adapter):
    h = place_lane(adapter)
    for lane in adapter.engine.creeps.values():
        lane.clear()
    c = add_creep(adapter, Team.DIRE, (h.pos[0] + 0.5, h.pos[1]), hp=20)
    gold = h.gold
    res = adapter.execute_action(1, Action(ActionType.ATTACK, target_uid=c.uid, once=True, hp_threshold=60))
    assert res.ok
    adapter.advance()
    assert not c.alive and h.last_hits == 1 and h.gold > gold + 30


def test_farming_priority_scales_utility(adapter):
    place_lane(adapter)
    h = adapter.engine.hero_by_player(1)
    for lane in adapter.engine.creeps.values():
        lane.clear()
    add_creep(adapter, Team.DIRE, (h.pos[0] + 0.5, h.pos[1]), hp=30)
    lo = FarmingAI(random.Random(1)).propose(ctx_for(adapter, farming_priority=0.0))
    hi = FarmingAI(random.Random(1)).propose(ctx_for(adapter, farming_priority=1.0))
    score = lambda cs: max(c.score for c in cs if c.action.intent == "last hit")  # noqa: E731
    assert score(hi) > score(lo)


# ----------------------------------------------------------------------------- combat
def test_combat_retreats_at_low_hp_under_threat(adapter):
    e = adapter.engine
    me, enemy = e.hero_by_player(1), e.hero_by_player(6)
    me.pos = (50.0, 50.0)
    enemy.pos = (52.0, 50.0)
    me.hp = me.max_hp * 0.15
    adapter.advance()
    ctx = ctx_for(adapter)
    combat = CombatAI(random.Random(1))
    threat = combat.assess(ctx.perception)
    retreat, score, why = combat.should_retreat(ctx, threat)
    assert retreat and score > 0.8 and why
    action = combat.retreat_action(ctx, why, score).action
    assert dist(action.pos, ctx.perception.fountain) < dist(me.pos, ctx.perception.fountain)


def test_combat_targets_weak_enemy(adapter):
    e = adapter.engine
    me = e.hero_by_player(1)
    weak, healthy = e.hero_by_player(10), e.hero_by_player(6)
    me.pos, weak.pos, healthy.pos = (50.0, 50.0), (51.5, 50.0), (51.0, 51.0)
    weak.hp = weak.max_hp * 0.1
    for a in [e.hero_by_player(i) for i in (2, 3)]:
        a.pos = (49.0, 50.0)
    adapter.advance()
    ctx = ctx_for(adapter, aggression=0.9)
    combat = CombatAI(random.Random(1))
    cands = combat.propose(ctx, combat.assess(ctx.perception))
    attacks = [c for c in cands if c.action.intent == "attack hero"]
    assert attacks and attacks[0].action.target_uid == weak.uid


def test_combat_heals_hurt_ally(adapter):
    e = adapter.engine
    me = e.hero_by_player(1)  # juggernaut has a heal ability (index 1)
    me.level = 3
    ally = e.hero_by_player(2)
    me.pos, ally.pos = (40.0, 40.0), (41.0, 40.0)
    ally.hp = ally.max_hp * 0.3
    adapter.advance()
    ctx = ctx_for(adapter)
    combat = CombatAI(random.Random(1))
    cands = combat.propose(ctx, combat.assess(ctx.perception))
    assert any(c.action.intent == "heal ally" and c.action.target_uid == ally.uid for c in cands)


# ----------------------------------------------------------------------------- economy & items
def test_economy_buys_starting_items(adapter):
    ctx = ctx_for(adapter)
    eco = EconomyAI(ItemAI(Role.CARRY, "juggernaut"))
    buys = [c for c in eco.propose(ctx) if c.action.type is ActionType.BUY]
    assert buys and buys[0].action.item == "quelling_blade"


def test_economy_buys_core_item_with_enough_gold(adapter):
    e = adapter.engine
    for _ in range(int(120 / e.config.tick)):
        e.step()
    h = e.hero_by_player(1)
    h.gold = 5000
    eco = EconomyAI(ItemAI(Role.CARRY, "juggernaut"))
    items = [c.action.item for c in eco.propose(ctx_for(adapter)) if c.action.type is ActionType.BUY]
    assert "power_treads" in items


def test_economy_sells_to_make_room(adapter):
    e = adapter.engine
    for _ in range(int(240 / e.config.tick)):
        e.step()
    h = e.hero_by_player(1)
    h.items = [ItemSlot(ITEMS["iron_branch"]) for _ in range(5)] + [ItemSlot(ITEMS["town_portal"], charges=1)]
    h.gold = 2000
    eco = EconomyAI(ItemAI(Role.CARRY, "juggernaut"))
    cands = eco.propose(ctx_for(adapter))
    assert any(c.action.type is ActionType.SELL and c.action.item == "iron_branch" for c in cands)


def test_item_ai_adapts_build_to_enemy_disables():
    items = ItemAI(Role.CARRY, "juggernaut")
    items.adapt_build(["lion", "earthshaker", "mars", "axe", "puck"], ["crystal_maiden"])
    assert items.core.index("black_king_bar") <= 1 and items.adjustments


def test_item_ai_uses_salve_when_hurt_and_safe(adapter):
    h = adapter.engine.hero_by_player(1)
    h.items = [ItemSlot(ITEMS["healing_salve"], charges=1)]
    h.hp = h.max_hp * 0.4
    cands = ItemAI(Role.CARRY, "juggernaut").propose_usage(ctx_for(adapter), in_fight=False, retreating=False)
    assert any(c.action.item == "healing_salve" for c in cands)


# ----------------------------------------------------------------------------- decision engine
def _cand(source, score, intent):
    return Candidate(Action(ActionType.HOLD, intent=intent), score, source)


def test_decision_engine_weights_personality():
    cands = [_cand("combat", 0.6, "fight"), _cand("farming", 0.6, "farm")]
    agg = DecisionEngine(prof(aggression=1.0, farming_priority=0.0, difficulty=Difficulty.EXPERT), random.Random(1))
    farm = DecisionEngine(prof(aggression=0.0, farming_priority=1.0, difficulty=Difficulty.EXPERT), random.Random(1))
    assert agg.decide(cands, BotMemory(), 0).main.action.intent == "fight"
    assert farm.decide(cands, BotMemory(), 0).main.action.intent == "farm"


def test_decision_engine_separates_shopping_channel():
    cands = [_cand("economy", 0.9, "buy"), _cand("lane", 0.3, "hold")]
    d = DecisionEngine(prof(), random.Random(1)).decide(cands, BotMemory(), 0)
    assert d.main.action.intent == "hold" and d.shop.action.intent == "buy"


def test_decision_engine_suppresses_failed_actions():
    a, b = _cand("lane", 0.5, "a"), _cand("lane", 0.45, "b")
    mem = BotMemory()
    mem.failures[a.key] = 10.0
    d = DecisionEngine(prof(difficulty=Difficulty.EXPERT), random.Random(1)).decide([a, b], mem, 5.0)
    assert d.main.action.intent == "b"


def test_decision_noise_depends_on_difficulty():
    cands = [_cand("lane", 0.50, "a"), _cand("lane", 0.48, "b")]

    def flips(diff):
        eng = DecisionEngine(prof(difficulty=diff), random.Random(3))
        return sum(eng.decide(cands, BotMemory(), 0).main.action.intent == "b" for _ in range(300))

    assert flips(Difficulty.EASY) > flips(Difficulty.EXPERT)


def test_scenario_offsets_profiles():
    p = prof(aggression=0.5)
    assert p.with_scenario(Scenario.AGGRESSIVE).aggression > 0.5
    assert p.with_scenario(Scenario.DEFENSIVE).aggression < 0.5
    assert p.with_scenario(Scenario.BALANCED) == p


# ----------------------------------------------------------------------------- bot & team
def test_bot_brain_full_cycle(adapter):
    brain = BotBrain(prof(), "juggernaut", seed=1)
    p = adapter.get_player_state(1)
    turn = brain.think(p, TeamDirective())
    assert turn.actions and turn.decision.ranked
    for a in turn.actions:
        brain.observe(a, adapter.execute_action(1, a), p.time)
    assert brain.memory.decisions == 1 and brain.memory.successes >= 1
    brain.observe(Action(ActionType.CAST, ability="r", intent="x", source="combat"),
                  ActionResult(False, "ability not learned"), p.time)
    assert brain.memory.failed == 1 and brain.memory.failures


def test_team_ai_defends_attacked_tower(adapter):
    e = adapter.engine
    tower = e.units["radiant_mid_t1"]
    tower.hp = tower.max_hp * 0.4  # a healthy T1 under laning pressure is not an emergency
    enemies = [e.hero_by_player(i) for i in (6, 7, 8)]
    for en in enemies:
        en.pos = (tower.pos[0] + 1, tower.pos[1] + 1)
        tower.damage_log[en.uid] = e.time
    adapter.advance()
    team = TeamAI(Team.RADIANT, [prof(i, Role.CARRY) for i in range(1, 6)])
    d = team.update(adapter.get_team_state(Team.RADIANT))
    assert d.kind == "defend" and d.target_uid == "radiant_mid_t1" and len(d.participants) == 5


def test_team_ai_pushes_when_ahead(adapter):
    e = adapter.engine
    while e.time < 700:
        e.step()
    for i in (6, 7, 8, 9):
        h = e.hero_by_player(i)
        h.alive, h.respawn_at = False, e.time + 60
    team = TeamAI(Team.RADIANT, [prof(i, Role.CARRY, team_coordination=0.8) for i in range(1, 6)])
    d = team.update(adapter.get_team_state(Team.RADIANT))
    assert d.kind in ("push", "roshan") and d.rally is not None
