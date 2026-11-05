"""Objective AI: attacking and defending towers, the ancient and Roshan."""
from __future__ import annotations

from app.ai.common import Candidate, SubsystemContext
from app.ai.perception import TeamDirective
from app.game.actions import Action, ActionType
from app.game.simulator.map import ROSHAN_PIT, dist

TIER_VALUE = {"t1": 0.0, "t2": 0.05, "t3": 0.1, "t4": 0.15, "ancient": 0.3}


class ObjectiveAI:
    def propose(self, ctx: SubsystemContext, directive: TeamDirective) -> list[Candidate]:
        p, prof = ctx.perception, ctx.profile
        me = p.me
        out: list[Candidate] = []
        w = 0.7 + 0.6 * prof.objective_priority
        # ----- attack enemy structures
        for t in p.enemy_towers:
            if not t.vulnerable:
                continue
            d = dist(me.pos, t.pos)
            if d > 16:
                continue
            creeps_tanking = sum(1 for c in p.ally_creeps if dist(c.pos, t.pos) < 4.4)
            defenders = len(p.enemies_near(t.pos, 9))
            allies = len(p.allies_near(t.pos, 9))
            if defenders > allies:
                continue
            if creeps_tanking == 0 and t.damage > 0 and (allies < 3 or me.hp_frac < 0.6):
                continue  # don't tank a tower alone
            util = 0.35 + 0.15 * min(3, creeps_tanking) / 3 + TIER_VALUE.get(t.tier, 0) + 0.2 * (1 - t.hp_frac)
            if directive.kind == "push" and directive.target_uid == t.uid:
                util += 0.15
            out.append(Candidate(Action(ActionType.ATTACK, target_uid=t.uid, intent=f"attack {t.tier}"),
                                 min(1.0, util * w / 1.0), "objective", t.uid))
        # ----- defend own structures
        for t in p.ally_towers:
            attackers_creeps = sum(1 for c in p.enemy_creeps if dist(c.pos, t.pos) < 5)
            attackers = p.enemies_near(t.pos, 7)
            if not attackers and attackers_creeps < 2:
                continue
            d = dist(me.pos, t.pos)
            urgency = 0.15 + 0.2 * (1 - t.hp_frac) + TIER_VALUE.get(t.tier, 0) + 0.05 * len(attackers)
            if d > 30:
                tp = me.item("town_portal")
                under_attack = any(p.time - ts < 3.0 for ts in t.damage_log.values())
                worth_it = (directive.kind == "defend" and directive.target_uid == t.uid) or \
                    (t.tier in ("t3", "t4", "ancient") and attackers)
                if tp is not None and p.time >= tp.ready_at and under_attack and worth_it and \
                        t.hp_frac < 0.85 and not p.enemies_near(me.pos, 10):
                    out.append(Candidate(Action(ActionType.USE_ITEM, item="town_portal", pos=t.pos,
                                                intent=f"teleport defend {t.tier}"), min(1.0, (0.35 + urgency) * w),
                                         "objective", t.uid))
                continue
            if attackers_creeps and not attackers:
                creep = min((c for c in p.enemy_creeps if dist(c.pos, t.pos) < 5), key=lambda c: c.hp)
                out.append(Candidate(Action(ActionType.ATTACK, target_uid=creep.uid, intent=f"defend {t.tier}"),
                                     min(1.0, (0.3 + urgency) * w), "objective", t.uid))
            elif attackers and len(p.allies_near(t.pos, 12)) + 1 >= len(attackers):
                out.append(Candidate(Action(ActionType.MOVE, pos=t.pos, intent=f"defend {t.tier}"),
                                     min(1.0, (0.3 + urgency) * w), "objective", t.uid))
        # ----- Roshan (only as a team decision)
        if directive.kind == "roshan" and p.roshan is not None and directive.includes(me.player_id):
            allies_at_pit = len(p.allies_near(ROSHAN_PIT, 6))
            if allies_at_pit >= 3 and dist(me.pos, ROSHAN_PIT) < 6:
                out.append(Candidate(Action(ActionType.ATTACK, target_uid=p.roshan.uid, intent="attack roshan"),
                                     min(1.0, 0.6 * w), "objective", "team roshan"))
        return out
