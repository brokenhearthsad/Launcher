"""Combat AI: threat assessment, target selection, ability usage, retreat, ally support."""
from __future__ import annotations

import random
from dataclasses import dataclass

from app.ai.common import Candidate, SubsystemContext, burst_damage, effective_hp, fight_power, hero_dps
from app.ai.perception import Perception
from app.domain import Role
from app.game.actions import Action, ActionType
from app.game.simulator.map import dist

ROLE_TARGET_PRIORITY = {Role.CARRY: 0.12, Role.MID: 0.1, Role.OFFLANE: 0.0, Role.SOFT_SUPPORT: 0.06,
                        Role.HARD_SUPPORT: 0.08}


@dataclass
class ThreatAssessment:
    ally_power: float
    enemy_power: float
    tower_threat: float  # enemy tower dps on me if I stay
    incoming_burst: float  # what visible enemies could deal to me right now
    enemies_near: int
    allies_near: int

    @property
    def ratio(self) -> float:
        return self.ally_power / max(1.0, self.enemy_power + self.tower_threat * 5)

    def lethal_risk(self, my_ehp: float) -> float:
        return min(1.5, self.incoming_burst / max(1.0, my_ehp))


class CombatAI:
    def __init__(self, rng: random.Random):
        self.rng = rng

    def assess(self, p: Perception) -> ThreatAssessment:
        me = p.me
        enemies = p.enemies_near(me.pos, 11)
        close = p.enemies_near(me.pos, 7)
        allies = p.allies_near(me.pos, 11)
        towers = p.enemy_towers_near(me.pos, 5.0)
        protected = any(dist(c.pos, towers[0].pos) < 4.4 for c in p.ally_creeps) if towers else False
        tower_threat = 0.0 if (not towers or protected) else towers[0].damage
        incoming = sum(hero_dps(e, me.armor) * 3 + burst_damage(e, p.time) for e in close)
        return ThreatAssessment(
            ally_power=sum(fight_power(a, p.time) for a in allies),
            enemy_power=sum(fight_power(e, p.time) for e in enemies),
            tower_threat=tower_threat,
            incoming_burst=incoming + tower_threat * 3,
            enemies_near=len(enemies),
            allies_near=len(allies) - 1,
        )

    def should_retreat(self, ctx: SubsystemContext, threat: ThreatAssessment) -> tuple[bool, float, str]:
        p, prof = ctx.perception, ctx.profile
        me = p.me
        threshold = 0.22 + 0.28 * (1 - prof.risk_tolerance)
        if me.hp_frac < threshold and (threat.enemies_near or threat.tower_threat):
            return True, 0.95, f"hp {me.hp_frac:.0%} under threat"
        if me.hp_frac < threshold * 0.6:
            return True, 0.8, f"hp {me.hp_frac:.0%}"
        risk = threat.lethal_risk(effective_hp(me))
        if risk > 0.8 + 0.5 * prof.risk_tolerance and threat.ratio < 1.0:
            return True, 0.9, f"lethal risk {risk:.2f}"
        losing_hp = ctx.memory.hp_trend < 0
        if threat.ratio < 0.45 + 0.3 * (1 - prof.risk_tolerance) and threat.enemies_near >= 2 and \
                (losing_hp or not p.laning_phase):
            return True, 0.82, f"outnumbered ({threat.allies_near + 1}v{threat.enemies_near})"
        if threat.tower_threat and me.hp_frac < 0.6 and not threat.enemies_near:
            return True, 0.6, "under enemy tower"
        return False, 0.0, ""

    def retreat_action(self, ctx: SubsystemContext, why: str, score: float) -> Candidate:
        p = ctx.perception
        me = p.me
        # Fountain when badly hurt, else the nearest allied tower behind us.
        dest = p.fountain
        if me.hp_frac > 0.35 and p.ally_towers:
            behind = [t for t in p.ally_towers if dist(t.pos, p.fountain) < dist(me.pos, p.fountain) and t.damage > 0]
            if behind:
                dest = min(behind, key=lambda t: dist(t.pos, me.pos)).pos
        ctx.memory.retreat_until = p.time + 3
        return Candidate(Action(ActionType.MOVE, pos=dest, intent="retreat"), score, "survival", why)

    def kill_potential(self, p: Perception, target, coordination: float) -> float:
        me = p.me
        allies = p.allies_near(target.pos, 8, include_me=False)
        dmg = burst_damage(me, p.time) + hero_dps(me, target.armor) * 4
        dmg += sum(burst_damage(a, p.time) + hero_dps(a, target.armor) * 4 for a in allies) * (0.4 + 0.6 * coordination)
        return dmg / max(1.0, effective_hp(target))

    def propose(self, ctx: SubsystemContext, threat: ThreatAssessment) -> list[Candidate]:
        p, prof = ctx.perception, ctx.profile
        me = p.me
        out: list[Candidate] = []
        out.extend(self._support_allies(ctx))
        # During laning bots only engage what is close; afterwards they look further.
        engage_radius = 7.5 + 4 * prof.aggression if p.laning_phase else 13
        enemies = p.enemies_near(me.pos, engage_radius)
        if not enemies:
            return out
        willing = threat.ratio * (0.6 + 0.8 * prof.aggression)
        if p.laning_phase:
            willing *= 0.85 + 0.3 * prof.aggression
        best: tuple[float, object] | None = None
        for e in enemies:
            kp = self.kill_potential(p, e, prof.team_coordination)
            d = dist(me.pos, e.pos)
            towers = p.enemy_towers_near(e.pos, 4.6)
            dive_penalty = (0.35 * (1.2 - prof.risk_tolerance) if towers else 0.0) * (1.0 if kp < 1.2 else 0.4)
            util = 0.32 + 0.38 * min(1.0, kp) + 0.12 * (1 - e.hp_frac) + ROLE_TARGET_PRIORITY.get(e.role, 0)
            util -= 0.015 * max(0.0, d - me.attack_range) + dive_penalty
            if e.is_immune(p.time):
                util -= 0.08
            if best is None or util > best[0]:
                best = (util, e)
        assert best is not None
        util, target = best
        threshold = 0.95 if p.laning_phase else 0.75
        if willing < threshold and self.kill_potential(p, target, prof.team_coordination) < 0.9:
            # Not a favourable fight: harass only if safe and we are ranged.
            if p.laning_phase and me.attack_range > 2.5 and me.hp_frac > 0.7 and threat.tower_threat == 0:
                out.append(Candidate(Action(ActionType.ATTACK, target_uid=target.uid, once=True, intent="harass"),
                                     0.3 + 0.25 * prof.aggression, "combat", "safe harass"))
            return out
        kp = self.kill_potential(p, target, prof.team_coordination)
        out.append(Candidate(Action(ActionType.ATTACK, target_uid=target.uid, intent="attack hero"),
                             min(1.0, util), "combat", f"kill potential {kp:.2f}"))
        out.extend(self._abilities(ctx, target, util, threat))
        return out

    def _abilities(self, ctx: SubsystemContext, target, base: float, threat: ThreatAssessment) -> list[Candidate]:
        p, prof = ctx.perception, ctx.profile
        me = p.me
        out: list[Candidate] = []
        if self.rng.random() > prof.params.ability_skill:
            return out  # lower difficulties sometimes "forget" their spells
        d = dist(me.pos, target.pos)
        kp = self.kill_potential(p, target, prof.team_coordination)
        for ab in p.abilities:
            if not ab.ready:
                continue
            s = ab.spec
            rng = s.cast_range + me.cast_range_bonus + 2.0
            if s.kind in ("nuke", "slow", "ult_single", "stun", "aoe_nuke", "ult_aoe") and (d <= rng or s.radius >= 40):
                if s.kind in ("ult_aoe", "ult_single") or s.ultimate:
                    hit = len(p.enemies_near(target.pos, s.radius)) if s.radius else 1
                    if s.radius >= 40:
                        hit = len(p.enemies)
                    if kp < 0.6 and hit < 2:
                        continue
                    score = base + 0.12 + 0.04 * hit
                elif s.kind == "stun":
                    if target.is_stunned(p.time):
                        continue
                    score = base + 0.1
                else:
                    score = base + 0.06
                out.append(Candidate(Action(ActionType.CAST, ability=s.key, target_uid=target.uid,
                                            intent=f"cast {s.name}"), min(1.0, score), "combat", s.kind))
            elif s.kind == "buff" and d <= me.attack_range + 2:
                out.append(Candidate(Action(ActionType.CAST, ability=s.key, intent=f"cast {s.name}"),
                                     min(1.0, base + 0.03), "combat", "self buff"))
        return out

    def _support_allies(self, ctx: SubsystemContext) -> list[Candidate]:
        p, prof = ctx.perception, ctx.profile
        me = p.me
        out: list[Candidate] = []
        for ab in p.abilities:
            if not ab.ready or ab.spec.kind not in ("heal", "shield"):
                continue
            candidates = [a for a in p.allies_near(me.pos, ab.spec.cast_range + 3) if a.hp_frac < 0.6]
            if not candidates:
                continue
            ally = min(candidates, key=lambda a: (a.hp_frac, a.uid))
            urgency = 1 - ally.hp_frac
            recent = p.time - ally.last_hero_damage_taken_at < 3
            score = (0.45 + 0.4 * urgency + (0.1 if recent else 0)) * (0.6 + 0.4 * prof.team_coordination)
            out.append(Candidate(Action(ActionType.CAST, ability=ab.spec.key, target_uid=ally.uid,
                                        intent=f"{ab.spec.kind} ally"), score, "combat", f"{ally.name} {ally.hp_frac:.0%}"))
        # Rotate to help an ally under attack.
        if me.hp_frac > 0.5:
            max_rotate = 10 if p.laning_phase else 18
            for a in p.allies:
                if p.laning_phase and a.lane != me.lane:
                    continue
                if p.time - a.last_hero_damage_taken_at < 2.5 and 4 < dist(me.pos, a.pos) < max_rotate:
                    score = (0.35 + 0.3 * prof.team_coordination + 0.1 * prof.aggression)
                    out.append(Candidate(Action(ActionType.MOVE, pos=a.pos, intent="help ally"), score, "combat",
                                         f"{a.name} under attack"))
                    break
        return out
