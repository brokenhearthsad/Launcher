"""Economy AI: gold tracking, purchase evaluation, prioritisation and spending."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.ai.common import Candidate, SubsystemContext
from app.ai.items import ItemAI
from app.game.actions import Action, ActionType
from app.game.catalog import ITEMS


@dataclass
class EconomyState:
    # (game time, total gold earned) samples for income estimation
    income_history: list[tuple[float, float]] = field(default_factory=list)
    spent: int = 0
    purchases: list[str] = field(default_factory=list)

    def income_per_min(self) -> float:
        if len(self.income_history) < 2:
            return 0.0
        (t0, g0), (t1, g1) = self.income_history[0], self.income_history[-1]
        if t1 <= t0:
            return 0.0
        return max(0.0, (g1 - g0) / (t1 - t0) * 60)


class EconomyAI:
    """Decides *whether* to spend gold; :class:`ItemAI` decides *what* to buy."""

    def __init__(self, items: ItemAI):
        self.items = items
        self.state = EconomyState()

    def track(self, time: float, gold_earned: float) -> None:
        h = self.state.income_history
        h.append((time, gold_earned))
        if len(h) > 120:
            del h[0]

    def reserve(self, ctx: SubsystemContext) -> int:
        """Gold kept back for consumables and emergencies."""
        p = ctx.perception
        if p.time < 30:
            return 0
        reserve = 0
        if p.me.item("town_portal") is None and p.time > 180:
            reserve += ITEMS["town_portal"].cost
        return reserve

    def propose(self, ctx: SubsystemContext) -> list[Candidate]:
        p, prof = ctx.perception, ctx.profile
        me = p.me
        self.track(p.time, me.gold_earned)
        out: list[Candidate] = []

        def buy(key: str, score: float, why: str) -> None:
            ok, reason = self.items.is_available(p, key)
            if ok:
                out.append(Candidate(Action(ActionType.BUY, item=key, intent=f"buy {key}"), score, "economy", why))
            elif reason == "inventory full":
                sell = self.items.sell_candidate(p)
                if sell is not None and sell != key and ITEMS[key].cost > ITEMS[sell].cost * 3:
                    out.append(Candidate(Action(ActionType.SELL, item=sell, intent=f"sell {sell}"), score - 0.05,
                                         "economy", f"make room for {key}"))

        # 1) consumables needed right now
        if p.time > 180 and me.item("town_portal") is None:
            buy("town_portal", 0.7, "always carry a teleport")
        if p.laning_phase and me.hp_frac < 0.5 and me.item("healing_salve") is None and me.gold > 200:
            buy("healing_salve", 0.75, "sustain in lane")
        if prof.is_support and p.time > 60 and me.item("observer_ward") is None and \
                int(p.time // 180) > ctx.memory.wards_placed // 2:
            buy("observer_ward", 0.6, "restock wards")
        # 2) next build item when affordable beyond reserve
        nxt = self.items.next_item(p)
        if nxt is not None:
            cost = ITEMS[nxt].cost
            if me.gold - self.reserve(ctx) >= cost or p.time < 30:
                buy(nxt, 0.8, f"build item ({cost}g)")
        return out

    def record_purchase(self, key: str) -> None:
        self.state.purchases.append(key)
        self.state.spent += ITEMS[key].cost if key in ITEMS else 0
