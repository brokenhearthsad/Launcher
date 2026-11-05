"""Farming AI: last hits, denies, wave clearing and jungle farming."""
from __future__ import annotations

import random

from app.ai.common import Candidate, SubsystemContext, hero_dps
from app.ai.lane import lane_danger
from app.game.actions import Action, ActionType
from app.game.simulator.entities import Creep, NeutralCamp, armor_multiplier
from app.game.simulator.map import dist


class FarmingAI:
    def __init__(self, rng: random.Random):
        self.rng = rng

    def creep_hit_damage(self, ctx: SubsystemContext, creep: Creep) -> float:
        me = ctx.perception.me
        dmg = me.damage * armor_multiplier(creep.armor - me.armor_reduction) * (1 + me.creep_damage)
        # Imperfect estimation: lower difficulty = larger misjudgement.
        err = ctx.profile.params.last_hit_error
        return dmg * (1 + self.rng.uniform(-err, err))

    def predicted_hp(self, ctx: SubsystemContext, creep: Creep) -> float:
        """Creep HP when our attack lands, accounting for incoming creep damage if we can predict it."""
        p = ctx.perception
        me = p.me
        travel = max(0.0, dist(me.pos, creep.pos) - me.attack_range) / max(0.5, me.move_speed)
        delay = travel + max(0.0, me.next_attack - p.time)
        if not ctx.profile.params.predicts_creep_damage:
            return creep.hp
        attackers = [c for c in (p.ally_creeps if creep.team is not me.team else p.enemy_creeps)
                     if c.target_uid == creep.uid]
        incoming = sum(c.damage / c.attack_interval for c in attackers) * armor_multiplier(creep.armor)
        return creep.hp - incoming * delay * 0.8

    def farm_safety(self, ctx: SubsystemContext) -> float:
        p = ctx.perception
        danger = lane_danger(p, p.me.lane)
        near_enemies = len(p.enemies_near(p.me.pos, 9))
        return max(0.0, 1.0 - danger * 0.8 - 0.15 * near_enemies * (1 - ctx.profile.risk_tolerance))

    def propose(self, ctx: SubsystemContext) -> list[Candidate]:
        p, prof = ctx.perception, ctx.profile
        me = p.me
        out: list[Candidate] = []
        safety = self.farm_safety(ctx)
        core_bonus = 0.12 if prof.is_core else -0.05
        weight = 0.55 + 0.35 * prof.farming_priority + core_bonus
        # Supports leave last hits to cores sharing the lane.
        cores_nearby = any(a.role.value in ("carry", "mid") for a in p.allies_near(me.pos, 7, include_me=False))
        if prof.is_support and cores_nearby:
            weight -= 0.25
        reach = me.attack_range + me.move_speed * 2.0
        best_lh: tuple[float, Creep, float] | None = None
        best_deny: tuple[float, Creep, float] | None = None
        for c in p.enemy_creeps:
            d = dist(me.pos, c.pos)
            if d > reach:
                continue
            hit = self.creep_hit_damage(ctx, c)
            # Creeps that will soon be killable: commit now and time the hit.
            if self.predicted_hp(ctx, c) <= hit * 2.2:
                value = c.bounty_gold - d * 2 - c.hp * 0.05
                if best_lh is None or value > best_lh[0]:
                    best_lh = (value, c, hit)
        for c in p.ally_creeps:
            if c.hp_frac >= 0.5:
                continue
            d = dist(me.pos, c.pos)
            hit = self.creep_hit_damage(ctx, c)
            if d <= reach and self.predicted_hp(ctx, c) <= hit * 1.8:
                if best_deny is None or -d > best_deny[0]:
                    best_deny = (-d, c, hit)
        if best_lh is not None:
            _, c, hit = best_lh
            out.append(Candidate(Action(ActionType.ATTACK, target_uid=c.uid, once=True, hp_threshold=hit,
                                        intent="last hit"), weight * (0.6 + 0.4 * safety), "farming",
                                 f"creep hp {c.hp:.0f}"))
        if best_deny is not None:
            _, c, hit = best_deny
            out.append(Candidate(Action(ActionType.ATTACK, target_uid=c.uid, once=True, hp_threshold=hit,
                                        intent="deny"), (weight - 0.12) * (0.6 + 0.4 * safety), "farming"))
        if not p.laning_phase and p.enemy_creeps:
            # Clear the wave quickly once the laning stage is over (pushes lane, collects gold).
            near = [c for c in p.enemy_creeps if dist(me.pos, c.pos) < 7]
            if near:
                tgt = min(near, key=lambda c: (c.hp, c.uid))
                out.append(Candidate(Action(ActionType.ATTACK, target_uid=tgt.uid, intent="clear wave"),
                                     (0.36 + 0.25 * prof.farming_priority) * safety, "farming"))
                aoe = self._aoe_farm(ctx, near)
                if aoe is not None:
                    out.append(aoe)
        jungle = self._jungle(ctx, safety)
        if jungle is not None:
            out.append(jungle)
        return out

    def _aoe_farm(self, ctx: SubsystemContext, near: list[Creep]) -> Candidate | None:
        p = ctx.perception
        if p.me.mana < p.me.max_mana * 0.6:
            return None
        for ab in p.abilities:
            if ab.ready and ab.spec.kind == "aoe_nuke" and not ab.spec.ultimate:
                center = min(near, key=lambda c: c.uid)
                hit = [c for c in near if dist(c.pos, center.pos) <= ab.spec.radius]
                if len(hit) >= 3:
                    return Candidate(Action(ActionType.CAST, ability=ab.spec.key, target_uid=center.uid,
                                            intent="aoe farm"), 0.45 + 0.2 * ctx.profile.farming_priority,
                                     "farming", f"{len(hit)} creeps")
        return None

    def _jungle(self, ctx: SubsystemContext, safety: float) -> Candidate | None:
        p, prof = ctx.perception, ctx.profile
        me = p.me
        if p.laning_phase and not (prof.is_core and me.level >= 6 and prof.farming_priority > 0.7):
            return None
        dps = hero_dps(me, 2)
        best: tuple[float, NeutralCamp] | None = None
        for camp in p.camps:
            if not camp.alive:
                continue
            own_side = camp.side is me.team
            if not own_side and prof.aggression < 0.6:
                continue
            kill_time = camp.hp / max(1.0, dps)
            taken = camp.damage * kill_time * armor_multiplier(me.armor)
            if kill_time > 25 or taken > me.hp * 0.7:
                continue
            if p.enemies_near(camp.pos, 12):
                continue
            score = camp.bounty_gold / (kill_time + dist(me.pos, camp.pos) / me.move_speed + 5)
            if best is None or score > best[0]:
                best = (score, camp)
        if best is None:
            return None
        camp = best[1]
        util = (0.3 + 0.3 * prof.farming_priority + (0.08 if prof.is_core else -0.08)) * (0.5 + 0.5 * safety)
        return Candidate(Action(ActionType.ATTACK, target_uid=camp.uid, intent="farm jungle"),
                         util, "farming", f"camp {camp.uid}")
