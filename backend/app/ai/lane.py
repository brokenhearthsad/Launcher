"""Lane AI: lane choice, positioning, holding a lane, danger and lane switching."""
from __future__ import annotations

from app.ai.common import Candidate, SubsystemContext, fight_power
from app.ai.perception import Perception
from app.domain import Team
from app.game.actions import Action, ActionType
from app.game.simulator.map import LANE_PATHS, LANES, Vec, dist, toward


def lane_danger(p: Perception, lane: str) -> float:
    """0 = safe, 1 = deadly. Compares visible enemy vs allied power around the lane front."""
    front = lane_front(p, lane)
    enemies = p.enemies_near(front, 14)
    allies = p.allies_near(front, 14)
    e_pow = sum(fight_power(e, p.time) for e in enemies)
    a_pow = sum(fight_power(a, p.time) for a in allies) + (fight_power(p.me, p.time) if p.me not in allies else 0)
    if e_pow <= 0:
        return 0.0
    return max(0.0, min(1.0, e_pow / (e_pow + a_pow) * 1.4 - 0.2))


def lane_front(p: Perception, lane: str) -> Vec:
    """Where allied creeps meet the enemy; falls back to our outermost alive tower."""
    path = LANE_PATHS[lane]
    mine = [c for c in p.ally_creeps if c.lane == lane]
    if mine:
        s = max(c.s for c in mine) if p.team is Team.RADIANT else min(c.s for c in mine)
        return path.point_at(s)
    towers = [t for t in p.ally_towers if t.lane == lane]
    if towers:
        # outermost tower = furthest from our fountain
        return max(towers, key=lambda t: dist(t.pos, p.fountain)).pos
    return path.point_for_team(p.team, 0.3)


def safe_position(p: Perception, lane: str, back_off: float) -> Vec:
    """A point behind the lane front, ``back_off`` units toward our side."""
    path = LANE_PATHS[lane]
    front = lane_front(p, lane)
    s = path.project(front)
    s = s - back_off if p.team is Team.RADIANT else s + back_off
    return path.point_at(s)


class LaneAI:
    def __init__(self) -> None:
        self.assigned_lane: str | None = None

    def choose_lane(self, ctx: SubsystemContext) -> str:
        p, m = ctx.perception, ctx.memory
        if m.lane_override and p.time < m.lane_override_until:
            return m.lane_override
        if p.laning_phase:
            return p.me.lane
        # After laning: pick the lane with the best farm/danger trade-off.
        best_lane, best = p.me.lane, -1e9
        for lane in LANES:
            front = lane_front(p, lane)
            enemy_wave = sum(1 for c in p.enemy_creeps if c.lane == lane)
            danger = lane_danger(p, lane)
            travel = dist(p.me.pos, front) / 30.0
            allies_there = len(p.allies_near(front, 12, include_me=False))
            score = 0.4 * min(1.0, enemy_wave / 4) - danger * (1.3 - ctx.profile.risk_tolerance) - travel
            score -= 0.15 * allies_there * (1 - ctx.profile.team_coordination)  # don't steal farm
            if lane == p.me.lane:
                score += 0.1
            if score > best:
                best_lane, best = lane, score
        return best_lane

    def propose(self, ctx: SubsystemContext) -> list[Candidate]:
        p, prof, mem = ctx.perception, ctx.profile, ctx.memory
        lane = self.choose_lane(ctx)
        self.assigned_lane = lane
        danger = lane_danger(p, lane)
        out: list[Candidate] = []
        # Lane switching when our lane is lost and we are weak.
        if p.laning_phase and danger > 0.75 and p.me.hp_frac < 0.6 and mem.lane_override is None:
            alt = min((ln for ln in LANES if ln != lane), key=lambda ln: lane_danger(p, ln))
            if lane_danger(p, alt) < danger - 0.3:
                mem.lane_override, mem.lane_override_until = alt, p.time + 90
                out.append(Candidate(Action(ActionType.MOVE, pos=lane_front(p, alt), intent=f"switch lane {alt}"),
                                     0.5, "lane", f"lane {lane} danger {danger:.2f}"))
        # Hold position behind the front: ranged heroes and timid bots stand further back.
        back = 0.6 + (min(2.0, p.me.attack_range * 0.5) if p.me.attack_range > 2 else 0.0) + \
            danger * 2.5 * (1.2 - prof.risk_tolerance)
        target = safe_position(p, lane, back)
        enemy_tower = p.enemy_towers_near(target, 5.2)
        if enemy_tower and not any(dist(c.pos, enemy_tower[0].pos) < 4.4 for c in p.ally_creeps):
            # never idle inside an enemy tower's range without creeps tanking
            target = toward(enemy_tower[0].pos, p.fountain, 6.0)
        if dist(p.me.pos, target) > 0.8:
            out.append(Candidate(Action(ActionType.MOVE, pos=target, intent=f"hold {lane} lane"), 0.32, "lane",
                                 f"danger {danger:.2f}"))
        else:
            out.append(Candidate(Action(ActionType.HOLD, intent=f"hold {lane} lane"), 0.3, "lane"))
        return out
