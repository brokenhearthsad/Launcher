"""Item AI: build selection per role, situational adjustments, active item usage."""
from __future__ import annotations

from app.ai.common import Candidate, SubsystemContext
from app.ai.perception import Perception
from app.domain import Role
from app.game.actions import Action, ActionType
from app.game.catalog import HEROES, INVENTORY_SLOTS, ITEMS, ROLE_CORE_BUILD, ROLE_STARTING_ITEMS
from app.game.simulator.map import dist


class ItemAI:
    def __init__(self, role: Role, hero_key: str):
        self.role = role
        self.hero_key = hero_key
        self.starting = list(ROLE_STARTING_ITEMS[role])
        self.core = list(ROLE_CORE_BUILD[role])
        self.adjusted = False
        self.adjustments: list[str] = []

    # ------------------------------------------------------------------ build
    def adapt_build(self, enemy_hero_keys: list[str], ally_hero_keys: list[str]) -> None:
        """Situational build changes based on the enemy and allied line-ups."""
        if self.adjusted:
            return
        self.adjusted = True
        enemy = [HEROES[k] for k in enemy_hero_keys if k in HEROES]
        allies = [HEROES[k] for k in ally_hero_keys if k in HEROES]
        disables = sum(1 for h in enemy for a in h.abilities if a.stun > 0)
        physical = sum(1 for h in enemy if h.primary == "agi")
        magical = sum(1 for h in enemy if h.primary == "int")
        team_heals = sum(1 for h in allies for a in h.abilities if a.kind == "heal")

        def promote(item: str, index: int, why: str) -> None:
            if item in self.core:
                self.core.remove(item)
            self.core.insert(min(index, len(self.core)), item)
            self.adjustments.append(f"{item}: {why}")

        if self.role in (Role.CARRY, Role.MID) and disables >= 5:
            promote("black_king_bar", 1, f"{disables} enemy disables")
        if physical >= 3:
            if self.role is Role.OFFLANE:
                promote("assault_cuirass", 2, f"{physical} physical enemies")
            elif self.role is Role.CARRY:
                promote("butterfly", 2, f"{physical} physical enemies")
        if magical >= 3:
            if self.role is Role.OFFLANE:
                promote("pipe", 1, f"{magical} magical enemies")
            elif self.role in (Role.SOFT_SUPPORT, Role.HARD_SUPPORT):
                promote("glimmer_cape", 1, f"{magical} magical enemies")
        if team_heals == 0 and self.role is Role.HARD_SUPPORT:
            promote("mekansm", 1, "team lacks healing")
        self.core = self.core[: INVENTORY_SLOTS + 2]

    def next_item(self, p: Perception) -> str | None:
        """Next item to buy from the build, or None when complete."""
        owned = p.me.item_keys + [spec.key for _, spec in p.me.pending]
        if p.time < 30:
            for key in self.starting:
                if owned.count(key) < self.starting.count(key):
                    return key
                owned.remove(key)
        for key in self.core:
            if key not in owned:
                return key
        return None

    def is_available(self, p: Perception, key: str) -> tuple[bool, str]:
        spec = ITEMS.get(key)
        if spec is None:
            return False, "unknown item"
        if p.me.gold < spec.cost:
            return False, "not enough gold"
        stack = spec.charges and p.me.item(key) is not None
        if not stack and len(p.me.items) + len(p.me.pending) >= INVENTORY_SLOTS:
            return False, "inventory full"
        return True, ""

    def sell_candidate(self, p: Perception) -> str | None:
        """Cheapest item worth replacing when the inventory is full."""
        replaceable = [s for s in p.me.items if s.spec.category in ("basic", "consumable")
                       and s.spec.key not in ("town_portal",)]
        if not replaceable:
            boots = [s for s in p.me.items if s.spec.key == "boots_of_speed"]
            replaceable = boots
        if not replaceable:
            return None
        return min(replaceable, key=lambda s: (s.spec.cost, s.spec.key)).spec.key

    # ------------------------------------------------------------------ usage
    def propose_usage(self, ctx: SubsystemContext, in_fight: bool, retreating: bool) -> list[Candidate]:
        p, prof = ctx.perception, ctx.profile
        me = p.me
        now = p.time
        out: list[Candidate] = []
        enemies_close = p.enemies_near(me.pos, 8)
        for slot in me.items:
            spec = slot.spec
            if not spec.active or now < slot.ready_at:
                continue
            a = spec.active

            def use(score: float, why: str, target: str | None = None, pos=None, key: str = spec.key) -> None:
                out.append(Candidate(Action(ActionType.USE_ITEM, item=key, target_uid=target, pos=pos,
                                            intent=f"use {key}"), score, "items", why))

            if a == "heal_400" and me.hp_frac < 0.55 and not enemies_close and now >= me.regen_until:
                use(0.72, "low hp, safe to regenerate")
            elif a == "mana_180" and me.mana < me.max_mana * 0.35 and not enemies_close:
                use(0.5, "low mana")
            elif a == "wand_restore" and (me.hp_frac < 0.3 or (in_fight and me.hp_frac < 0.5)):
                use(0.86, "emergency restore")
            elif a == "spell_immunity" and in_fight and len(enemies_close) >= 2:
                use(0.88, f"{len(enemies_close)} enemies in fight")
            elif a == "lifesteal_burst" and in_fight and me.hp_frac < 0.45:
                use(0.85, "lifesteal while fighting")
            elif a == "aoe_slow_nuke" and len(p.enemies_near(me.pos, 5)) >= 2:
                use(0.8, "multiple enemies close")
            elif a in ("blink", "force") and retreating and enemies_close:
                use(0.93, "escape", pos=p.fountain)
            elif a == "team_heal":
                hurt = [x for x in p.allies_near(me.pos, 7) if x.hp_frac < 0.65]
                if len(hurt) >= 2 or (hurt and in_fight):
                    use(0.8, f"{len(hurt)} hurt allies")
            elif a == "team_shield" and in_fight and len(p.allies_near(me.pos, 7)) >= 2:
                use(0.78, "shield team in fight")
            elif a == "team_mana":
                low = [x for x in p.allies_near(me.pos, 8) if x.mana < x.max_mana * 0.5]
                if len(low) >= 2:
                    use(0.55, "restore team mana")
            elif a == "ally_shield":
                saving = [x for x in p.allies_near(me.pos, 6) if x.hp_frac < 0.35 and now - x.last_hero_damage_taken_at < 2]
                if saving:
                    use(0.84 * (0.6 + 0.4 * prof.team_coordination), "save ally", target=saving[0].uid)
            elif a == "ward":
                spot = self._ward_spot(p)
                if spot is not None:
                    use(0.4 + 0.25 * prof.team_coordination, "provide vision", pos=spot)
            elif a == "teleport":
                pass  # decided by ObjectiveAI / survival (needs a destination)
        return out

    def _ward_spot(self, p: Perception):
        from app.game.simulator.map import WARD_SPOTS

        for spot in WARD_SPOTS[p.team]:
            if all(dist(w.pos, spot) > 12 for w in p.wards if w.team is p.team):
                if dist(p.me.pos, spot) < 30 and not p.enemies_near(spot, 10):
                    return spot
        return None
