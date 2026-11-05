"""Team AI: one coordinator per team synchronising its five bots.

Every few seconds it evaluates the team situation and emits a
:class:`TeamDirective` (farm / push / defend / group / roshan / regroup) with
a rally point and the list of participating players. Individual bots weigh the
directive by their ``team_coordination`` parameter, so a low-coordination bot
may keep farming while the others group.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.ai.common import fight_power
from app.ai.perception import TeamDirective, TeamView
from app.ai.profile import BotProfile
from app.domain import Role, Team
from app.game.simulator.map import ANCIENT, LANE_PATHS, ROSHAN_PIT, dist, toward

UPDATE_INTERVAL = 3.0


@dataclass
class TeamEvaluation:
    alive: int
    enemy_alive: int
    nw_ratio: float  # our net worth / enemy net worth
    avg_level: float
    power_ratio: float

    @property
    def advantage(self) -> float:
        """Positive = we are ahead. Roughly in [-1, 1]."""
        alive_adv = (self.alive - self.enemy_alive) / 5
        nw_adv = max(-0.5, min(0.5, self.nw_ratio - 1.0))
        return alive_adv * 0.6 + nw_adv * 0.8 + max(-0.3, min(0.3, self.power_ratio - 1.0)) * 0.4


class TeamAI:
    def __init__(self, team: Team, profiles: list[BotProfile]):
        self.team = team
        self.profiles = {p.player_id: p for p in profiles}
        self.directive = TeamDirective(kind="farm", reason="laning stage")
        self.next_update = 0.0
        self.history: list[tuple[float, str]] = []

    @property
    def coordination(self) -> float:
        vals = [p.team_coordination for p in self.profiles.values()]
        return sum(vals) / len(vals) if vals else 0.5

    def evaluate(self, v: TeamView) -> TeamEvaluation:
        alive = [h for h in v.heroes if h.alive]
        power = sum(fight_power(h, v.time) for h in alive)
        enemy_power = sum(fight_power(h, v.time) for h in v.visible_enemies)
        # Unknown (fogged) enemies are assumed to be as strong as our average hero.
        unseen = max(0, v.enemy_alive - len(v.visible_enemies))
        if alive:
            enemy_power += unseen * power / len(alive)
        return TeamEvaluation(
            alive=len(alive), enemy_alive=v.enemy_alive,
            nw_ratio=v.net_worth / max(1, v.enemy_net_worth_estimate),
            avg_level=sum(h.level for h in v.heroes) / max(1, len(v.heroes)),
            power_ratio=power / max(1.0, enemy_power),
        )

    def update(self, v: TeamView) -> TeamDirective:
        if v.time < self.next_update:
            return self.directive
        self.next_update = v.time + UPDATE_INTERVAL
        ev = self.evaluate(v)
        d = self._decide(v, ev)
        if d.kind != self.directive.kind or d.target_uid != self.directive.target_uid:
            self.history.append((v.time, f"{d.kind}:{d.target_uid or d.lane or ''}"))
        self.directive = d
        return d

    # ------------------------------------------------------------------ strategy
    def _decide(self, v: TeamView, ev: TeamEvaluation) -> TeamDirective:
        all_ids = tuple(h.player_id for h in v.heroes if h.alive)
        # 1) Defend structures under real pressure.
        threatened = self._threatened_tower(v)
        if threatened is not None:
            tower, attackers = threatened
            if attackers >= 2 or tower.tier in ("t3", "t4", "ancient"):
                if ev.alive >= max(2, attackers - 1):
                    return TeamDirective("defend", lane=tower.lane, target_uid=tower.uid, rally=tower.pos,
                                         participants=all_ids, reason=f"{attackers} enemies at {tower.uid}")
                return TeamDirective("regroup", rally=toward(ANCIENT[self.team], tower.pos, 6),
                                     participants=all_ids, reason="cannot hold, regroup at base")
        # 2) Badly behind: regroup near base towers.
        if ev.alive <= ev.enemy_alive - 2:
            return TeamDirective("regroup", rally=toward(ANCIENT[self.team], (50.0, 50.0), 10),
                                 participants=all_ids, reason=f"{ev.alive}v{ev.enemy_alive}")
        if v.laning_phase:
            return TeamDirective("farm", reason="laning stage")
        # 3) Ahead: take objectives.
        if v.roshan_alive and ev.advantage > 0.25 and ev.avg_level >= 11 and ev.alive >= 4:
            return TeamDirective("roshan", rally=ROSHAN_PIT, participants=all_ids,
                                 reason=f"advantage {ev.advantage:.2f}")
        push_threshold = 0.15 - 0.15 * self.coordination
        if ev.advantage > push_threshold and ev.alive >= 3:
            target = self._push_target(v)
            if target is not None:
                participants = self._participants(v, "push")
                rally = toward(target.pos, ANCIENT[self.team], 5)
                return TeamDirective("push", lane=target.lane, target_uid=target.uid, rally=rally,
                                     participants=participants, reason=f"advantage {ev.advantage:.2f}")
        # 4) Even game in mid/late: group and look for fights in mid.
        if v.time > 1500 and ev.alive >= 4 and self.coordination > 0.35:
            front = LANE_PATHS["mid"].point_for_team(self.team, 0.42)
            return TeamDirective("group", lane="mid", rally=front, participants=self._participants(v, "group"),
                                 reason="contest the map as five")
        return TeamDirective("farm", reason="even game, farm up")

    def _participants(self, v: TeamView, kind: str) -> tuple[int, ...]:
        ids = []
        for h in v.heroes:
            if not h.alive:
                continue
            prof = self.profiles.get(h.player_id)
            # Greedy carries stay farming during low-value grouping.
            if kind == "group" and prof and prof.role is Role.CARRY and prof.farming_priority > 0.75 \
                    and prof.team_coordination < 0.6:
                continue
            ids.append(h.player_id)
        return tuple(ids)

    def _threatened_tower(self, v: TeamView):
        worst = None
        for t in v.ally_towers:
            # Only towers that are actually taking damage right now count.
            if not any(v.time - ts < 3.0 for ts in t.damage_log.values()):
                continue
            if v.laning_phase and t.tier == "t1" and t.hp_frac > 0.5:
                continue  # enemy laners near a healthy T1 is normal laning
            attackers = sum(1 for e in v.visible_enemies if dist(e.pos, t.pos) < 8)
            creeps = sum(1 for lane in v.enemy_creeps_by_lane.values() for c in lane if dist(c.pos, t.pos) < 5)
            pressure = attackers * 2 + creeps * 0.3
            if attackers >= 1 and (worst is None or pressure > worst[0]):
                worst = (pressure, t, attackers)
        if worst is None:
            return None
        return worst[1], worst[2]

    def _push_target(self, v: TeamView):
        vulnerable = [t for t in v.enemy_towers if t.vulnerable]
        if not vulnerable:
            return None
        center = [h.pos for h in v.heroes if h.alive]
        cx = sum(p[0] for p in center) / len(center)
        cy = sum(p[1] for p in center) / len(center)
        tier_rank = {"ancient": 0, "t4": 1, "t1": 2, "t2": 3, "t3": 4}
        return min(vulnerable, key=lambda t: (dist(t.pos, (cx, cy)) / 25 + tier_rank.get(t.tier, 5) * 0.2
                                              + t.hp_frac * 0.5, t.uid))
