"""BotBrain: one instance per participant, combining all AI subsystems.

Decision loop (called by the match runner):
    perceive -> propose -> evaluate -> choose -> execute (adapter) -> observe
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from app.ai.combat import CombatAI
from app.ai.common import BotMemory, Candidate, SubsystemContext
from app.ai.decision import Decision, DecisionEngine
from app.ai.economy import EconomyAI
from app.ai.farming import FarmingAI
from app.ai.items import ItemAI
from app.ai.lane import LaneAI
from app.ai.objective import ObjectiveAI
from app.ai.perception import Perception, TeamDirective
from app.ai.profile import BotProfile
from app.game.actions import Action, ActionResult, ActionType
from app.game.simulator.map import dist


@dataclass
class BotTurn:
    """Actions chosen in one decision step (main + optional shopping)."""

    actions: list[Action]
    decision: Decision


class BotBrain:
    def __init__(self, profile: BotProfile, hero_key: str, seed: int):
        self.profile = profile
        # Per-bot RNG derived deterministically from the match seed and player.
        self.rng = random.Random(seed * 7919 + profile.player_id * 104729)
        self.memory = BotMemory()
        self.lane = LaneAI()
        self.farming = FarmingAI(self.rng)
        self.items = ItemAI(profile.role, hero_key)
        self.economy = EconomyAI(self.items)
        self.combat = CombatAI(self.rng)
        self.objective = ObjectiveAI()
        self.engine = DecisionEngine(profile, self.rng)
        self.next_decision = 0.0

    def ready(self, now: float) -> bool:
        return now >= self.next_decision

    def schedule_next(self, now: float) -> None:
        base = self.profile.params.reaction_time
        self.next_decision = now + base * self.rng.uniform(0.85, 1.15)

    # ------------------------------------------------------------------ think
    def think(self, p: Perception, directive: TeamDirective) -> BotTurn:
        mem = self.memory
        mem.hp_trend = p.me.hp - mem.last_hp if mem.last_hp else 0.0
        mem.last_hp = p.me.hp
        ctx = SubsystemContext(p, self.profile, mem)
        threat = self.combat.assess(p)
        retreat, r_score, why = self.combat.should_retreat(ctx, threat)
        in_fight = threat.enemies_near > 0 and p.time - p.me.last_hero_damage_taken_at < 3
        candidates: list[Candidate] = []
        if retreat:
            candidates.append(self.combat.retreat_action(ctx, why, r_score))
            candidates.extend(self._teleport_home(ctx))
        candidates.extend(self.items.propose_usage(ctx, in_fight, retreat))
        candidates.extend(self.economy.propose(ctx))
        if not retreat or r_score < 0.85:
            candidates.extend(self.combat.propose(ctx, threat))
            candidates.extend(self.farming.propose(ctx))
            candidates.extend(self.objective.propose(ctx, directive))
            candidates.extend(self._follow_directive(ctx, directive))
        candidates.extend(self.lane.propose(ctx))
        decision = self.engine.decide(candidates, mem, p.time)
        actions: list[Action] = []
        if decision.shop is not None:
            actions.append(self._annotate(decision.shop))
        if decision.main is not None:
            actions.append(self._annotate(decision.main))
            mem.last_intent = decision.main.action.intent
            mem.last_key = decision.main.key
            src = decision.main.source
            mem.intents[src] = mem.intents.get(src, 0) + 1
        mem.decisions += 1
        return BotTurn(actions, decision)

    @staticmethod
    def _annotate(c: Candidate) -> Action:
        c.action.source = c.source
        c.action.score = round(c.score, 3)
        c.action.note = c.reason
        return c.action

    def _follow_directive(self, ctx: SubsystemContext, d: TeamDirective) -> list[Candidate]:
        p = ctx.perception
        if d.kind == "farm" or d.rally is None or not d.includes(p.me.player_id):
            return []
        if dist(p.me.pos, d.rally) < 3.0:
            return []
        base = {"push": 0.44, "defend": 0.52, "group": 0.4, "roshan": 0.5, "regroup": 0.55}.get(d.kind, 0.4)
        return [Candidate(Action(ActionType.MOVE, pos=d.rally, intent=f"team {d.kind}"), base, "team", d.reason)]

    def _teleport_home(self, ctx: SubsystemContext) -> list[Candidate]:
        p = ctx.perception
        tp = p.me.item("town_portal")
        if tp is None or p.time < tp.ready_at:
            return []
        if dist(p.me.pos, p.fountain) > 40 and not p.enemies_near(p.me.pos, 9) and p.me.hp_frac < 0.35:
            return [Candidate(Action(ActionType.USE_ITEM, item="town_portal", pos=p.fountain, intent="teleport home"),
                              0.9, "survival", "low hp far from base")]
        return []

    # ------------------------------------------------------------------ feedback
    def observe(self, action: Action, result: ActionResult, now: float) -> None:
        """Update internal state with the adapter's response."""
        mem = self.memory
        if result.ok:
            mem.successes += 1
            if action.type is ActionType.BUY and action.item:
                self.economy.record_purchase(action.item)
            if action.type is ActionType.USE_ITEM and action.item == "observer_ward":
                mem.wards_placed += 1
            return
        mem.failed += 1
        key = f"{action.source}:{action.intent}:{action.target_uid or ''}:{action.ability or ''}:{action.item or ''}"
        mem.failures[key] = now + 4.0
        if len(mem.failures) > 64:
            for k in [k for k, t in mem.failures.items() if t <= now]:
                del mem.failures[k]

    def stats(self) -> dict:
        m = self.memory
        return {"decisions": m.decisions, "ok": m.successes, "failed": m.failed, "intents": dict(m.intents),
                "build_adjustments": list(self.items.adjustments),
                "income_per_min": round(self.economy.state.income_per_min(), 1)}
