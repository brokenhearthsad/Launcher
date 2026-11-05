"""Deterministic 5v5 match simulator.

The engine advances in fixed time steps (``tick`` seconds of game time). It has
no knowledge of wall-clock time, so a match can be simulated as fast as the CPU
allows or throttled to any playback speed by the caller.

All randomness comes from a single ``random.Random(seed)`` instance and every
collection is iterated in a deterministic order, so the same seed, scenario and
bot configuration reproduce the same match.
"""
from __future__ import annotations

import bisect
import random
from dataclasses import dataclass, field
from typing import Any

from app.domain import GameMode, Role, Scenario, Team
from app.game.actions import Action, ActionResult, ActionType
from app.game.catalog import (
    HEROES,
    INVENTORY_SLOTS,
    ITEMS,
    MAX_LEVEL,
    STARTING_GOLD,
    XP_TABLE,
    AbilitySpec,
    ItemSpec,
)
from app.game.simulator.entities import (
    Creep,
    Hero,
    ItemSlot,
    NeutralCamp,
    Order,
    Roshan,
    Tower,
    Unit,
    Ward,
    armor_multiplier,
)
from app.game.simulator.map import (
    ANCIENT,
    FOUNTAIN,
    LANE_PATHS,
    LANES,
    NEUTRAL_CAMPS,
    ROSHAN_PIT,
    TOWER_FRACTIONS,
    Vec,
    away,
    dist,
    resolve_lane,
    toward,
)

WAVE_INTERVAL = 30.0
CREEP_AGGRO = 5.0
HERO_XP_RADIUS = 9.5
ASSIST_WINDOW = 15.0
FOUNTAIN_RADIUS = 7.0
SHOP_RADIUS = 9.0
VISION_HERO = 11.0
VISION_TOWER = 12.0
VISION_CREEP = 7.0
VISION_WARD = 11.0
TOWER_RANGE = 4.4
NEUTRAL_LEASH = 6.0


@dataclass
class MatchConfig:
    seed: int = 1
    scenario: Scenario = Scenario.BALANCED
    mode: GameMode = GameMode.STANDARD
    tick: float = 0.5
    max_game_seconds: int = 3600
    snapshot_interval: int = 60


@dataclass
class HeroSetup:
    player_id: int
    name: str
    team: Team
    role: Role
    hero_key: str
    lane_kind: str  # safe | mid | off


@dataclass
class TeamModifiers:
    gold: float = 1.0
    xp: float = 1.0
    damage: float = 1.0


SCENARIO_MODIFIERS: dict[Scenario, dict[Team, TeamModifiers]] = {
    Scenario.RADIANT_ADVANTAGE: {Team.RADIANT: TeamModifiers(1.25, 1.2, 1.1)},
    Scenario.DIRE_ADVANTAGE: {Team.DIRE: TeamModifiers(1.25, 1.2, 1.1)},
}


@dataclass
class GameEvent:
    type: str
    time: float
    player_id: int | None = None
    data: dict[str, Any] = field(default_factory=dict)


class SimulationError(RuntimeError):
    pass


class GameEngine:
    def __init__(self, config: MatchConfig, setups: list[HeroSetup]):
        if len(setups) != 10:
            raise SimulationError(f"a 5v5 match needs exactly 10 heroes, got {len(setups)}")
        for team in Team:
            if sum(1 for s in setups if s.team is team) != 5:
                raise SimulationError(f"team {team.value} must have exactly 5 heroes")
        self.config = config
        self.rng = random.Random(config.seed)
        self.time = 0.0
        self.tick_count = 0
        self.turbo = config.mode is GameMode.TURBO
        self.lanes_active = ("mid",) if config.mode is GameMode.MID_ONLY else LANES
        self.winner: Team | None = None
        self.win_condition: str | None = None
        self.finished = False
        self.events: list[GameEvent] = []
        self.timeline: list[dict[str, Any]] = []
        self.first_blood = False
        self.score = {Team.RADIANT: 0, Team.DIRE: 0}
        self.creeps: dict[str, list[Creep]] = {lane: [] for lane in LANES}
        self.towers: list[Tower] = []
        self.camps: list[NeutralCamp] = []
        self.wards: list[Ward] = []
        self.heroes: list[Hero] = []
        self._uid_counter = 0
        self._next_wave = 0.0
        self._next_snapshot = float(config.snapshot_interval)
        self._visible: dict[Team, set[str]] = {Team.RADIANT: set(), Team.DIRE: set()}
        self._build_structures()
        self._build_camps()
        self.roshan = Roshan("roshan", "roshan", None, ROSHAN_PIT, 5500, 5500, 10, 75, 1.6, 1.0)
        for s in setups:
            self._add_hero(s)
        self.units: dict[str, Unit] = {}
        self._reindex()
        self._recompute_vulnerability()
        self._emit("game_start", None, {"seed": config.seed, "scenario": config.scenario.value,
                                        "mode": config.mode.value})

    # ================================================================ setup
    def _uid(self, prefix: str) -> str:
        self._uid_counter += 1
        return f"{prefix}{self._uid_counter}"

    def _build_structures(self) -> None:
        hp_mult = 0.75 if self.turbo else 1.0
        stats = {"t1": (1800, 14, 140), "t2": (2100, 16, 160), "t3": (2400, 18, 180),
                 "t4": (2500, 20, 180), "ancient": (4500, 15, 0)}
        for team in Team:
            for lane in LANES:
                path = LANE_PATHS[lane]
                for tier in ("t1", "t2", "t3"):
                    frac = TOWER_FRACTIONS["t1"][lane] if tier == "t1" else TOWER_FRACTIONS[tier]
                    pos = path.point_for_team(team, frac)
                    hp, armor, dmg = stats[tier]
                    self.towers.append(Tower(
                        f"{team.value}_{lane}_{tier}", "tower", team, pos, hp * hp_mult, hp * hp_mult, armor, dmg,
                        TOWER_RANGE, 1.0, tier=tier, lane=lane, s=path.project(pos)))
            ax, ay = ANCIENT[team]
            sign = 1 if team is Team.RADIANT else -1
            for i, off in enumerate(((3.0, 1.0), (1.0, 3.0))):
                hp, armor, dmg = stats["t4"]
                pos = (ax + sign * off[0], ay + sign * off[1])
                self.towers.append(Tower(f"{team.value}_base_t4_{i + 1}", "tower", team, pos, hp * hp_mult,
                                         hp * hp_mult, armor, dmg, TOWER_RANGE, 1.0, tier="t4", lane="base"))
            hp, armor, _ = stats["ancient"]
            self.towers.append(Tower(f"{team.value}_ancient", "tower", team, ANCIENT[team], hp * hp_mult,
                                     hp * hp_mult, armor, 0, 0, 1.0, tier="ancient", lane="base"))

    def _build_camps(self) -> None:
        for cid, pos, kind, side in NEUTRAL_CAMPS:
            hp, dmg, gold, xp = {"small": (550, 22, 75, 100), "medium": (900, 34, 115, 150),
                                 "large": (1350, 48, 170, 220)}[kind]
            camp = NeutralCamp(cid, "neutral", None, pos, hp, hp, 2, dmg, 1.4, 1.0, camp_id=cid, camp_type=kind,
                               side=side, home=pos, bounty_gold=gold, bounty_xp=xp)
            camp.alive = False  # neutrals spawn at 1:00
            self.camps.append(camp)

    def _add_hero(self, s: HeroSetup) -> None:
        spec = HEROES.get(s.hero_key)
        if spec is None:
            raise SimulationError(f"unknown hero '{s.hero_key}'")
        lane = resolve_lane(s.team, s.lane_kind)
        if self.config.mode is GameMode.MID_ONLY:
            lane = "mid"
        h = Hero(f"hero_{s.player_id}", "hero", s.team, FOUNTAIN[s.team], spec.base_hp, spec.base_hp,
                 spec.base_armor, spec.base_damage, spec.attack_range, spec.attack_time,
                 player_id=s.player_id, name=s.name, spec=spec, role=s.role, lane=lane)
        mods = SCENARIO_MODIFIERS.get(self.config.scenario, {}).get(s.team, TeamModifiers())
        turbo = 2.0 if self.turbo else 1.0
        h.gold_mult, h.xp_mult, h.damage_mult = mods.gold * turbo, mods.xp * turbo, mods.damage
        h.gold = STARTING_GOLD
        self._recalc(h)
        h.hp, h.mana = h.max_hp, h.max_mana
        self.heroes.append(h)

    def _reindex(self) -> None:
        self.units = {h.uid: h for h in self.heroes}
        self.units.update({t.uid: t for t in self.towers})
        self.units.update({c.uid: c for c in self.camps})
        self.units[self.roshan.uid] = self.roshan

    def hero_by_player(self, player_id: int) -> Hero | None:
        for h in self.heroes:
            if h.player_id == player_id:
                return h
        return None

    def get_unit(self, uid: str) -> Unit | None:
        u = self.units.get(uid)
        if u is not None:
            return u
        if uid.startswith("c"):
            for lane in LANES:
                for c in self.creeps[lane]:
                    if c.uid == uid:
                        return c
        return None

    # ================================================================ stats
    def _recalc(self, h: Hero) -> None:
        """Recompute derived hero stats from level and items."""
        spec = h.spec
        assert spec is not None
        lvl = h.level - 1
        bonus: dict[str, float] = {}
        for slot in h.items:
            for k, v in slot.spec.stats.items():
                bonus[k] = bonus.get(k, 0.0) + v
        hp_frac = h.hp / h.max_hp if h.max_hp else 1.0
        mana_frac = h.mana / h.max_mana if h.max_mana else 1.0
        h.max_hp = spec.base_hp + spec.hp_per_level * lvl + bonus.get("hp", 0)
        h.max_mana = spec.base_mana + spec.mana_per_level * lvl + bonus.get("mana", 0)
        h.damage = (spec.base_damage + spec.damage_per_level * lvl + bonus.get("damage", 0)) * h.damage_mult
        h.armor = spec.base_armor + spec.armor_per_level * lvl + bonus.get("armor", 0)
        attack_speed = 1.0 + 0.02 * lvl + bonus.get("attack_speed", 0)
        h.attack_interval = spec.attack_time / attack_speed
        h.move_speed = spec.move_speed + bonus.get("move_speed", 0)
        h.hp_regen = spec.hp_regen + 0.15 * lvl + bonus.get("hp_regen", 0)
        h.mana_regen = spec.mana_regen + 0.1 * lvl + bonus.get("mana_regen", 0)
        h.magic_resist = min(0.75, 0.25 + bonus.get("magic_resist", 0))
        h.creep_damage = bonus.get("creep_damage", 0)
        h.lifesteal = bonus.get("lifesteal", 0)
        h.crit = bonus.get("crit", 0)
        h.evasion = bonus.get("evasion", 0)
        h.armor_reduction = bonus.get("armor_reduction", 0)
        h.proc_damage = bonus.get("proc_damage", 0)
        h.cast_range_bonus = bonus.get("cast_range", 0)
        h.ult_amp = bonus.get("ult_amp", 0)
        if h.alive:
            h.hp = max(1.0, h.max_hp * hp_frac)
            h.mana = h.max_mana * mana_frac

    # ================================================================ events
    def _emit(self, etype: str, hero: Hero | None, data: dict[str, Any] | None = None) -> None:
        self.events.append(GameEvent(etype, round(self.time, 2), hero.player_id if hero else None, data or {}))

    def drain_events(self) -> list[GameEvent]:
        out, self.events = self.events, []
        return out

    # ================================================================ public API
    def step(self) -> None:
        if self.finished:
            return
        dt = self.config.tick
        self.time += dt
        self.tick_count += 1
        now = self.time
        if now >= self._next_wave:
            self._spawn_waves()
            self._next_wave += WAVE_INTERVAL
        if self.tick_count % int(round(60 / dt)) == 0:
            self._respawn_neutrals()
        self._passive(dt)
        self._update_vision()
        for h in self.heroes:
            if h.alive:
                self._hero_act(h, dt)
        for lane in self.lanes_active:
            self._creeps_act(lane, dt)
        self._towers_act()
        self._neutrals_act()
        self._roshan_act()
        self._cleanup()
        self._respawns()
        if now >= self._next_snapshot:
            self._record_snapshot()
            self._next_snapshot += self.config.snapshot_interval
        self._check_end()

    def run_until_finished(self, max_ticks: int | None = None) -> None:
        """Run without bots (heroes keep their last orders). Used in tests."""
        n = 0
        while not self.finished and (max_ticks is None or n < max_ticks):
            self.step()
            n += 1

    def visible_enemy_uids(self, team: Team) -> set[str]:
        return self._visible[team]

    def is_visible_to(self, team: Team, unit: Unit) -> bool:
        if unit.team is team or unit.kind in ("tower", "neutral", "roshan"):
            return True
        return unit.uid in self._visible[team]

    # ================================================================ waves & neutrals
    def _spawn_waves(self) -> None:
        wave_no = int(self.time // WAVE_INTERVAL)
        upgrade = 1.0 + 0.1 * int(self.time // 450)
        for team in Team:
            direction = 1 if team is Team.RADIANT else -1
            for lane in self.lanes_active:
                path = LANE_PATHS[lane]
                s0 = 1.5 if team is Team.RADIANT else path.length - 1.5
                mega = 1.0
                enemy_t3 = self._tower(f"{team.enemy.value}_{lane}_t3")
                if enemy_t3 is not None and not enemy_t3.alive:
                    mega = 1.6
                kinds = ["melee", "melee", "melee", "ranged"]
                if wave_no > 0 and wave_no % 10 == 0:
                    kinds.append("siege")
                for i, ctype in enumerate(kinds):
                    hp, dmg, rng, gold, xp = {"melee": (550, 21, 1.0, 46, 72), "ranged": (300, 23, 3.0, 56, 88),
                                              "siege": (850, 40, 4.0, 80, 110)}[ctype]
                    s = s0 - direction * i * 0.6
                    c = Creep(self._uid("c"), "creep", team, path.point_at(s), hp * upgrade * mega,
                              hp * upgrade * mega, 2.0 if ctype != "siege" else 0, dmg * upgrade * mega, rng, 1.0,
                              lane=lane, s=s, move_speed=2.0, creep_type=ctype, bounty_gold=gold, bounty_xp=xp)
                    self.creeps[lane].append(c)

    def _respawn_neutrals(self) -> None:
        growth = 1.0 + self.time / 2400.0
        for camp in self.camps:
            if not camp.alive:
                base = {"small": 550, "medium": 900, "large": 1350}[camp.camp_type]
                camp.max_hp = camp.hp = base * growth
                camp.alive = True
                camp.pos = camp.home
                camp.damage_log.clear()
                camp.target_uid = None
        if not self.roshan.alive and self.time >= self.roshan.respawn_at:
            self.roshan.alive = True
            self.roshan.max_hp = self.roshan.hp = 5500 + 115 * (self.time / 60)
            self.roshan.damage_log.clear()
            self._emit("roshan_spawned", None, {})

    # ================================================================ passive
    def _passive(self, dt: float) -> None:
        now = self.time
        if now >= 90:  # passive gold starts at 1:30
            for h in self.heroes:
                self._give_gold(h, 1.5 * dt, passive=True)
        for h in self.heroes:
            if not h.alive:
                continue
            regen = h.hp_regen
            if now < h.regen_until:
                regen += h.regen_rate
            mregen = h.mana_regen
            if dist(h.pos, FOUNTAIN[h.team]) < FOUNTAIN_RADIUS:
                regen += 0.06 * h.max_hp
                mregen += 0.05 * h.max_mana
            if h.hp < h.max_hp:
                heal = min(h.max_hp - h.hp, regen * dt)
                h.hp += heal
            h.mana = min(h.max_mana, h.mana + mregen * dt)
            if h.shield and now >= h.shield_until:
                h.shield = 0
            # courier deliveries
            if h.pending:
                arrived = [p for p in h.pending if p[0] <= now]
                if arrived and len(h.items) < INVENTORY_SLOTS:
                    for p in arrived:
                        if len(h.items) >= INVENTORY_SLOTS:
                            break
                        h.pending.remove(p)
                        self._add_item(h, p[1])
            # channel (teleport)
            if h.channel_until and now >= h.channel_until and h.channel_target:
                h.pos = h.channel_target
                h.channel_until = 0.0
                h.channel_target = None
                self._emit("teleport", h, {"pos": [round(h.pos[0], 1), round(h.pos[1], 1)]})
        self.wards = [w for w in self.wards if w.expires_at > now]

    def _update_vision(self) -> None:
        for team in Team:
            seers: list[tuple[Vec, float]] = [(h.pos, VISION_HERO) for h in self.heroes if h.team is team and h.alive]
            seers += [(t.pos, VISION_TOWER) for t in self.towers if t.team is team and t.alive]
            seers += [(w.pos, VISION_WARD) for w in self.wards if w.team is team]
            for lane in self.lanes_active:
                seers += [(c.pos, VISION_CREEP) for c in self.creeps[lane] if c.team is team]
            visible: set[str] = set()
            for h in self.heroes:
                if h.team is team or not h.alive:
                    continue
                hx, hy = h.pos
                for (sx, sy), r in seers:
                    if (hx - sx) ** 2 + (hy - sy) ** 2 <= r * r:
                        visible.add(h.uid)
                        break
            self._visible[team] = visible

    # ================================================================ hero orders
    def _hero_act(self, h: Hero, dt: float) -> None:
        now = self.time
        if h.is_stunned(now) or (h.channel_until and now < h.channel_until):
            return
        o = h.order
        if o.kind == "move" and o.pos is not None:
            h.pos = toward(h.pos, o.pos, h.current_speed(now) * dt)
            if h.pos == o.pos:
                h.order = Order("hold")
        elif o.kind == "attack" and o.target_uid:
            t = self.get_unit(o.target_uid)
            if t is None or not t.alive or not self._attackable_by(h, t):
                h.order = Order("hold")
                return
            if o.expires_at and now > o.expires_at:
                h.order = Order("hold")
                return
            if dist(h.pos, t.pos) > h.attack_range + 0.3:
                h.pos = toward(h.pos, t.pos, h.current_speed(now) * dt)
            elif o.hp_threshold is not None and t.hp > o.hp_threshold:
                return  # in range, waiting for the right moment
            elif now >= h.next_attack:
                self._hero_attack(h, t)
                if o.once:
                    h.order = Order("hold")
        elif o.kind == "cast" and o.ability:
            self._try_cast(h, o)
        elif o.kind == "use_item" and o.item:
            self._try_item(h, o)

    def _attackable_by(self, h: Hero, t: Unit) -> bool:
        if isinstance(t, Tower):
            return t.team is not h.team and t.vulnerable or (t.team is h.team and t.hp_frac < 0.1 and t.tier != "ancient")
        if isinstance(t, Hero):
            return t.team is not h.team and self.is_visible_to(h.team, t)
        if isinstance(t, Creep):
            return t.team is not h.team or t.hp_frac < 0.5  # deny allowed below 50%
        return True  # neutral / roshan

    def _hero_attack(self, h: Hero, t: Unit) -> None:
        now = self.time
        h.next_attack = now + h.attack_interval
        if isinstance(t, Hero) and self.rng.random() < t.evasion:
            return
        dmg = h.damage + (h.buff_damage if now < h.buff_until else 0)
        if h.crit and self.rng.random() < h.crit:
            dmg *= 2.25
        armor = t.armor - h.armor_reduction
        dmg *= armor_multiplier(armor)
        if isinstance(t, (Creep, NeutralCamp)):
            dmg *= 1.0 + h.creep_damage
        if h.proc_damage and self.rng.random() < 0.3:
            dmg += h.proc_damage * 3 * (1 - (t.magic_resist if isinstance(t, Hero) else 0.0))
        dealt = self._damage(t, dmg, h)
        if isinstance(t, Hero):
            self.draw_creep_aggro(h, t)
        if h.lifesteal or now < h.lifesteal_until:
            ls = h.lifesteal + (1.75 if now < h.lifesteal_until else 0)
            self._heal(h, dealt * ls, h, count=False)

    # ---------------------------------------------------------------- abilities
    def ability_state(self, h: Hero, key: str) -> tuple[AbilitySpec | None, int, str]:
        """Return (spec, level, error) for casting ``key`` right now."""
        idx = h.ability_index(key)
        if idx < 0 or h.spec is None:
            return None, 0, "unknown ability"
        spec = h.spec.abilities[idx]
        lvl = h.ability_level(idx)
        if lvl <= 0:
            return spec, 0, "ability not learned"
        if self.time < h.ability_ready_at.get(key, 0.0):
            return spec, lvl, "ability on cooldown"
        if h.mana < spec.mana[lvl - 1]:
            return spec, lvl, "not enough mana"
        return spec, lvl, ""

    def _try_cast(self, h: Hero, o: Order) -> None:
        spec, lvl, err = self.ability_state(h, o.ability or "")
        if err or spec is None:
            h.order = Order("hold")
            return
        target = self.get_unit(o.target_uid) if o.target_uid else None
        if o.target_uid and (target is None or not target.alive):
            h.order = Order("hold")
            return
        pos = target.pos if target is not None else (o.pos or h.pos)
        cast_range = spec.cast_range + h.cast_range_bonus
        if spec.kind != "escape" and spec.radius < 40 and dist(h.pos, pos) > cast_range:
            h.pos = toward(h.pos, pos, h.current_speed(self.time) * self.config.tick)
            return
        self._cast(h, spec, lvl, target, pos)
        h.order = Order("hold")

    def _cast(self, h: Hero, spec: AbilitySpec, lvl: int, target: Unit | None, pos: Vec) -> None:
        now = self.time
        i = lvl - 1
        h.mana -= spec.mana[i]
        h.ability_ready_at[spec.key] = now + spec.cooldown[i]
        amp = 1.0 + (h.ult_amp if spec.ultimate else 0.0)
        dmg = spec.damage[i] * amp * h.damage_mult
        affected: list[str] = []
        if spec.kind in ("nuke", "stun", "slow", "ult_single") and spec.radius == 0:
            if target is not None and target.team is not h.team:
                self._spell_hit(h, target, dmg, spec)
                affected.append(target.uid)
        elif spec.kind in ("aoe_nuke", "ult_aoe", "stun", "slow", "nuke", "ult_single"):
            center = h.pos if spec.cast_range <= 1.6 else pos
            for u in self._enemies_near(h.team, center, spec.radius):
                self._spell_hit(h, u, dmg, spec)
                affected.append(u.uid)
        elif spec.kind == "heal":
            ally = target if isinstance(target, Hero) and target.team is h.team else h
            self._heal(ally, spec.heal[i], h)
            affected.append(ally.uid)
        elif spec.kind == "shield":
            ally = target if isinstance(target, Hero) and target.team is h.team else h
            ally.shield = max(ally.shield, spec.shield[i])
            ally.shield_until = now + 8
            affected.append(ally.uid)
        elif spec.kind == "buff":
            h.buff_damage = spec.buff_damage[i]
            h.buff_until = now + spec.buff_duration
        elif spec.kind == "escape":
            h.pos = toward(h.pos, pos, spec.cast_range + h.cast_range_bonus)
        self._emit("ability_cast", h, {"ability": spec.name, "kind": spec.kind, "targets": affected[:5]})

    def _spell_hit(self, h: Hero, u: Unit, dmg: float, spec: AbilitySpec) -> None:
        now = self.time
        if isinstance(u, Hero):
            if u.is_immune(now):
                return
            if spec.stun:
                u.stunned_until = max(u.stunned_until, now + spec.stun)
                u.channel_until, u.channel_target = 0.0, None  # stuns interrupt teleports
            if spec.slow:
                u.slowed_until, u.slow_amount = now + spec.slow_duration, spec.slow
            dmg *= 1 - u.magic_resist
        if dmg > 0:
            self._damage(u, dmg, h)

    def _enemies_near(self, team: Team, center: Vec, radius: float) -> list[Unit]:
        out: list[Unit] = []
        for e in self.heroes:
            if e.team is not team and e.alive and dist(e.pos, center) <= radius:
                out.append(e)
        if radius < 40:
            for lane in self.lanes_active:
                for c in self.creeps[lane]:
                    if c.team is not team and c.alive and dist(c.pos, center) <= radius:
                        out.append(c)
        return out

    # ---------------------------------------------------------------- items
    def _try_item(self, h: Hero, o: Order) -> None:
        slot = h.item(o.item or "")
        if slot is None or self.time < slot.ready_at:
            h.order = Order("hold")
            return
        target = self.get_unit(o.target_uid) if o.target_uid else None
        pos = target.pos if target is not None else (o.pos or h.pos)
        ranged = {"ward": 3.0, "ally_shield": 6.0, "force": 6.0}
        need = ranged.get(slot.spec.active or "")
        if need and dist(h.pos, pos) > need:
            h.pos = toward(h.pos, pos, h.current_speed(self.time) * self.config.tick)
            return
        self._use_item(h, slot, target, pos)
        h.order = Order("hold")

    def _use_item(self, h: Hero, slot: ItemSlot, target: Unit | None, pos: Vec) -> None:
        now = self.time
        active = slot.spec.active
        allies = [a for a in self.heroes if a.team is h.team and a.alive]
        if active == "heal_400":
            h.regen_until, h.regen_rate = now + 8, 50
        elif active == "mana_180":
            h.mana = min(h.max_mana, h.mana + 180)
        elif active == "teleport":
            h.channel_until, h.channel_target = now + 3.0, pos
        elif active == "ward":
            self.wards.append(Ward(h.team, pos, now + 360, h.uid))
        elif active == "wand_restore":
            self._heal(h, 120, h)
            h.mana = min(h.max_mana, h.mana + 120)
        elif active == "team_mana":
            for a in allies:
                if dist(a.pos, h.pos) <= 8:
                    a.mana = min(a.max_mana, a.mana + 175)
        elif active == "spell_immunity":
            h.immune_until = now + 7
            h.stunned_until = min(h.stunned_until, now)
        elif active == "blink":
            h.pos = toward(h.pos, pos, 7.5)
        elif active == "force":
            who = target if isinstance(target, Hero) and target.team is h.team else h
            who.pos = toward(who.pos, FOUNTAIN[who.team], 3.75)
        elif active == "ally_shield":
            who = target if isinstance(target, Hero) and target.team is h.team else h
            who.shield, who.shield_until = max(who.shield, 250), now + 5
        elif active == "team_heal":
            for a in allies:
                if dist(a.pos, h.pos) <= 7:
                    self._heal(a, 275, h)
        elif active == "team_shield":
            for a in allies:
                if dist(a.pos, h.pos) <= 7:
                    a.shield, a.shield_until = max(a.shield, 300), now + 10
        elif active == "lifesteal_burst":
            h.lifesteal_until = now + 5
        elif active == "aoe_slow_nuke":
            for e in self._enemies_near(h.team, h.pos, 5):
                if isinstance(e, Hero):
                    e.slowed_until, e.slow_amount = now + 3, 0.4
                self._damage(e, 200 * (1 - (e.magic_resist if isinstance(e, Hero) else 0)), h)
        slot.ready_at = now + slot.spec.cooldown
        if slot.spec.charges:
            slot.charges -= 1
            if slot.charges <= 0:
                h.items.remove(slot)
                self._recalc(h)
        self._emit("item_used", h, {"item": slot.spec.key})

    def _add_item(self, h: Hero, spec: ItemSpec) -> None:
        if spec.charges:
            existing = h.item(spec.key)
            if existing is not None:
                existing.charges += spec.charges
                return
        h.items.append(ItemSlot(spec, charges=spec.charges))
        self._recalc(h)

    # ================================================================ action validation
    def apply_action(self, player_id: int, action: Action) -> ActionResult:
        """Validate a bot action and turn it into a hero order."""
        h = self.hero_by_player(player_id)
        if h is None:
            return ActionResult(False, "unknown player")
        if self.finished:
            return ActionResult(False, "match finished")
        if not h.alive:
            return ActionResult(False, "hero is dead")
        h.last_action = action.describe()
        t = action.type
        if t is ActionType.HOLD:
            h.order = Order("hold")
            return ActionResult(True)
        if t is ActionType.MOVE:
            if action.pos is None:
                return ActionResult(False, "move requires pos")
            x, y = action.pos
            h.order = Order("move", pos=(min(99.5, max(0.5, x)), min(99.5, max(0.5, y))))
            return ActionResult(True)
        if t is ActionType.ATTACK:
            target = self.get_unit(action.target_uid or "")
            if target is None or not target.alive:
                return ActionResult(False, "target not found")
            if not self._attackable_by(h, target):
                return ActionResult(False, "target cannot be attacked")
            h.order = Order("attack", target_uid=target.uid, once=action.once, hp_threshold=action.hp_threshold,
                            expires_at=self.time + 4.0 if action.hp_threshold is not None else 0.0)
            return ActionResult(True)
        if t is ActionType.CAST:
            spec, _lvl, err = self.ability_state(h, action.ability or "")
            if err:
                return ActionResult(False, err)
            if action.target_uid:
                target = self.get_unit(action.target_uid)
                if target is None or not target.alive:
                    return ActionResult(False, "target not found")
                if isinstance(target, Hero) and target.team is not h.team and not self.is_visible_to(h.team, target):
                    return ActionResult(False, "target not visible")
            h.order = Order("cast", target_uid=action.target_uid, pos=action.pos, ability=action.ability)
            return ActionResult(True)
        if t is ActionType.USE_ITEM:
            slot = h.item(action.item or "")
            if slot is None:
                return ActionResult(False, "item not in inventory")
            if not slot.spec.active:
                return ActionResult(False, "item has no active ability")
            if self.time < slot.ready_at:
                return ActionResult(False, "item on cooldown")
            if slot.spec.active == "teleport" and action.pos is None:
                return ActionResult(False, "teleport requires destination")
            h.order = Order("use_item", target_uid=action.target_uid, pos=action.pos, item=slot.spec.key)
            return ActionResult(True)
        if t is ActionType.BUY:
            return self._buy(h, action.item or "")
        if t is ActionType.SELL:
            slot = h.item(action.item or "")
            if slot is None:
                return ActionResult(False, "item not in inventory")
            h.items.remove(slot)
            refund = slot.spec.cost // 2
            h.gold += refund
            self._recalc(h)
            self._emit("item_sold", h, {"item": slot.spec.key, "refund": refund})
            return ActionResult(True, data={"refund": refund})
        return ActionResult(False, f"unsupported action {t}")

    def _buy(self, h: Hero, key: str) -> ActionResult:
        spec = ITEMS.get(key)
        if spec is None:
            return ActionResult(False, "unknown item")
        if h.gold < spec.cost:
            return ActionResult(False, "not enough gold")
        stackable = spec.charges and h.item(key) is not None
        if not stackable and len(h.items) + len(h.pending) >= INVENTORY_SLOTS:
            return ActionResult(False, "inventory full")
        h.gold -= spec.cost
        at_shop = dist(h.pos, FOUNTAIN[h.team]) <= SHOP_RADIUS
        if at_shop:
            self._add_item(h, spec)
        else:
            delay = 12.0 if self.turbo else 25.0
            h.pending.append((self.time + delay, spec))
        self._emit("item_purchased", h, {"item": key, "cost": spec.cost, "delivered": at_shop})
        return ActionResult(True, data={"delivered": at_shop})

    # ================================================================ damage / death
    def _damage(self, target: Unit, amount: float, source: Unit) -> float:
        if amount <= 0 or not target.alive:
            return 0.0
        if isinstance(target, Hero) and target.shield > 0:
            absorbed = min(target.shield, amount)
            target.shield -= absorbed
            amount -= absorbed
        dealt = min(target.hp, amount)
        target.hp -= amount
        target.damage_log[source.uid] = self.time
        if isinstance(source, Hero):
            if isinstance(target, Hero):
                source.hero_damage += dealt
                target.last_hero_damage_taken_at = self.time
                target.regen_until = 0.0  # salve is cancelled by hero damage
            elif isinstance(target, Tower) and target.team is not source.team:
                source.tower_damage += dealt
        if target.hp <= 0:
            self._kill(target, source)
        return dealt

    def _heal(self, target: Hero, amount: float, source: Hero, count: bool = True) -> None:
        healed = min(target.max_hp - target.hp, amount)
        if healed <= 0:
            return
        target.hp += healed
        if count and source is not target:
            source.healing += healed
        elif count:
            source.healing += healed * 0.5

    def _give_gold(self, h: Hero, amount: float, passive: bool = False) -> None:
        amount *= h.gold_mult
        h.gold += amount
        h.gold_earned += amount

    def _give_xp(self, h: Hero, amount: float) -> None:
        if not h.alive and amount > 0:
            amount *= 0.5
        h.xp += amount * h.xp_mult
        leveled = False
        while h.level < MAX_LEVEL and h.xp >= XP_TABLE[h.level]:
            h.level += 1
            leveled = True
        if leveled:
            self._recalc(h)
            self._emit("level_up", h, {"level": h.level})

    def _heroes_near(self, team: Team, pos: Vec, radius: float) -> list[Hero]:
        return [h for h in self.heroes if h.team is team and h.alive and dist(h.pos, pos) <= radius]

    def _kill(self, victim: Unit, killer: Unit) -> None:
        victim.alive = False
        victim.hp = 0
        now = self.time
        k_hero = killer if isinstance(killer, Hero) else None
        if isinstance(victim, Creep):
            if k_hero is not None and k_hero.team is victim.team:
                k_hero.denies += 1
                xp_share = victim.bounty_xp * 0.5
            else:
                xp_share = victim.bounty_xp
                if k_hero is not None:
                    k_hero.last_hits += 1
                    self._give_gold(k_hero, victim.bounty_gold + self.rng.randint(-3, 3))
            assert victim.team is not None
            receivers = self._heroes_near(victim.team.enemy, victim.pos, HERO_XP_RADIUS)
            for r in receivers:
                self._give_xp(r, xp_share / len(receivers))
        elif isinstance(victim, NeutralCamp):
            if k_hero is not None:
                k_hero.last_hits += 1
                self._give_gold(k_hero, victim.bounty_gold)
                receivers = self._heroes_near(k_hero.team, victim.pos, HERO_XP_RADIUS) or [k_hero]
                for r in receivers:
                    self._give_xp(r, victim.bounty_xp / len(receivers))
        elif isinstance(victim, Roshan):
            victim.kills += 1
            victim.respawn_at = now + self.rng.uniform(480, 660)
            if k_hero is not None:
                for a in self.heroes:
                    if a.team is k_hero.team:
                        self._give_gold(a, 150)
                        self._give_xp(a, 400 / 5)
                holder = max(self._heroes_near(k_hero.team, victim.pos, 10) or [k_hero],
                             key=lambda x: (x.role is Role.CARRY, x.net_worth))
                holder.has_aegis = True
                self._emit("roshan_killed", k_hero, {"team": k_hero.team.value, "aegis": holder.player_id})
        elif isinstance(victim, Tower):
            self._on_tower_destroyed(victim, k_hero)
        elif isinstance(victim, Hero):
            self._on_hero_killed(victim, killer)

    def _on_tower_destroyed(self, tower: Tower, killer: Hero | None) -> None:
        assert tower.team is not None
        enemy = tower.team.enemy
        if killer is not None and killer.team is enemy:
            self._give_gold(killer, 150)
        for h in self.heroes:
            if h.team is enemy:
                self._give_gold(h, 90 if tower.tier != "ancient" else 0)
        self._emit("tower_destroyed", killer, {"tower": tower.uid, "team": tower.team.value, "tier": tower.tier,
                                               "lane": tower.lane, "denied": bool(killer and killer.team is tower.team)})
        if tower.tier == "ancient":
            self._finish(enemy, "ancient_destroyed")
        self._recompute_vulnerability()

    def _on_hero_killed(self, victim: Hero, killer: Unit) -> None:
        now = self.time
        assert victim.team is not None
        if victim.has_aegis:
            victim.has_aegis = False
            victim.alive = True
            victim.hp, victim.mana = victim.max_hp, victim.max_mana
            victim.damage_log.clear()
            self._emit("aegis_used", victim, {})
            return
        victim.deaths += 1
        victim.streak = 0
        enemy = victim.team.enemy
        contributors = [self.units[uid] for uid, t in sorted(victim.damage_log.items())
                        if now - t <= ASSIST_WINDOW and uid in self.units]
        enemy_heroes = [u for u in contributors if isinstance(u, Hero) and u.team is enemy]
        k_hero = killer if isinstance(killer, Hero) and killer.team is enemy else None
        if k_hero is None and enemy_heroes:
            k_hero = max(enemy_heroes, key=lambda u: victim.damage_log.get(u.uid, 0))
        assisters = [u for u in enemy_heroes if u is not k_hero]
        if k_hero is not None:
            k_hero.kills += 1
            k_hero.streak += 1
            self.score[enemy] += 1
            bounty = 110 + 8 * victim.level + min(480, max(0, victim.streak - 2) * 60)
            self._give_gold(k_hero, bounty)
            for a in assisters:
                a.assists += 1
                self._give_gold(a, (60 + 6 * victim.level) / max(1, len(assisters)))
            xp_receivers = list({h.uid: h for h in [k_hero, *assisters,
                                                    *self._heroes_near(enemy, victim.pos, HERO_XP_RADIUS)]}.values())
            for r in xp_receivers:
                self._give_xp(r, (100 + 30 * victim.level) / len(xp_receivers))
            if not self.first_blood:
                self.first_blood = True
                self._give_gold(k_hero, 150)
                self._emit("first_blood", k_hero, {"victim": victim.player_id})
        else:
            self.score[enemy] += 1  # killed by creeps/towers: still a team kill
        lost = min(victim.gold, 30 + victim.level * 4)
        victim.gold -= lost
        respawn = 6 + 2.6 * victim.level
        if self.turbo:
            respawn *= 0.5
        victim.respawn_at = now + respawn
        victim.order = Order("hold")
        victim.stunned_until = victim.slowed_until = victim.buff_until = victim.regen_until = 0.0
        victim.channel_until, victim.channel_target = 0.0, None
        victim.damage_log.clear()
        self._emit("hero_killed", k_hero, {
            "victim": victim.player_id, "victim_name": victim.name,
            "killer": k_hero.player_id if k_hero else None, "killer_name": k_hero.name if k_hero else killer.uid,
            "assists": [a.player_id for a in assisters], "gold_lost": int(lost),
            "pos": [round(victim.pos[0], 1), round(victim.pos[1], 1)],
        })

    def _respawns(self) -> None:
        for h in self.heroes:
            if not h.alive and self.time >= h.respawn_at:
                h.alive = True
                h.pos = FOUNTAIN[h.team]
                h.hp, h.mana = h.max_hp, h.max_mana
                self._emit("hero_respawned", h, {})

    def _cleanup(self) -> None:
        for lane in self.lanes_active:
            self.creeps[lane] = [c for c in self.creeps[lane] if c.alive]

    # ================================================================ creeps
    def _creeps_act(self, lane: str, dt: float) -> None:
        creeps = self.creeps[lane]
        if not creeps:
            return
        now = self.time
        by_team = {Team.RADIANT: sorted((c.s, i) for i, c in enumerate(creeps) if c.team is Team.RADIANT),
                   Team.DIRE: sorted((c.s, i) for i, c in enumerate(creeps) if c.team is Team.DIRE)}
        s_lists = {t: [x[0] for x in v] for t, v in by_team.items()}
        structures = [t for t in self.towers if t.alive and (t.lane == lane or t.lane == "base")]
        heroes = [h for h in self.heroes if h.alive]
        # Alternate processing order between teams every tick so neither side
        # gets a systematic "acts first" advantage.
        first = Team.RADIANT if self.tick_count % 2 == 0 else Team.DIRE
        ordered = [c for c in creeps if c.team is first] + [c for c in creeps if c.team is not first]
        for c in ordered:
            if not c.alive:
                continue
            assert c.team is not None
            enemy = c.team.enemy
            target: Unit | None = None
            cur = self.get_unit(c.target_uid) if c.target_uid else None
            if cur is not None and cur.alive and dist(c.pos, cur.pos) <= c.attack_range + 1.5:
                target = cur
            if target is None and now < c.aggro_until and cur is not None and cur.alive:
                target = cur
            if target is not None and isinstance(target, Hero) and \
                    dist(c.pos, LANE_PATHS[lane].point_at(c.s)) > 3.0:
                target = None  # leash: creeps do not chase heroes far from their lane
                c.aggro_until = 0.0
            if target is None:
                # nearest enemy creep along the lane (1D search)
                sl = s_lists[enemy]
                if sl:
                    k = bisect.bisect_left(sl, c.s)
                    best = None
                    for j in (k - 1, k):
                        if 0 <= j < len(sl):
                            d = abs(sl[j] - c.s)
                            if d <= CREEP_AGGRO and (best is None or d < best[0]):
                                best = (d, creeps[by_team[enemy][j][1]])
                    if best is not None and best[1].alive:
                        target = best[1]
            if target is None:
                for t in structures:
                    if t.team is enemy and t.vulnerable and dist(c.pos, t.pos) <= CREEP_AGGRO:
                        target = t
                        break
            if target is None and dist(c.pos, LANE_PATHS[lane].point_at(c.s)) <= 3.0:
                near = [h for h in heroes if h.team is enemy and dist(h.pos, c.pos) <= CREEP_AGGRO * 0.7]
                if near:
                    target = min(near, key=lambda h: dist(h.pos, c.pos))
            if target is not None:
                c.target_uid = target.uid
                if dist(c.pos, target.pos) > c.attack_range:
                    c.pos = toward(c.pos, target.pos, c.move_speed * dt)
                    c.s = LANE_PATHS[lane].project(c.pos)
                elif now >= c.next_attack:
                    c.next_attack = now + c.attack_interval
                    mult = 0.25 if isinstance(target, Tower) and c.creep_type != "siege" else 1.0
                    if isinstance(target, Tower) and c.creep_type == "siege":
                        mult = 2.5
                    self._damage(target, c.damage * mult * armor_multiplier(target.armor), c)
            else:
                c.target_uid = None
                direction = 1 if c.team is Team.RADIANT else -1
                path = LANE_PATHS[lane]
                on_lane = path.point_at(c.s)
                if dist(c.pos, on_lane) > 0.5:
                    c.pos = toward(c.pos, on_lane, c.move_speed * dt)  # walk back to the lane
                else:
                    c.s = max(0.0, min(path.length, c.s + direction * c.move_speed * dt))
                    c.pos = path.point_at(c.s)

    def draw_creep_aggro(self, attacker: Hero, victim: Hero) -> None:
        """Hero attacking an enemy hero near enemy creeps draws their aggro."""
        lane = victim.lane
        for c in self.creeps.get(lane, []):
            if c.team is victim.team and dist(c.pos, attacker.pos) <= CREEP_AGGRO:
                c.target_uid = attacker.uid
                c.aggro_until = self.time + 2.0

    # ================================================================ towers
    def _tower(self, uid: str) -> Tower | None:
        u = self.units.get(uid)
        return u if isinstance(u, Tower) else None

    def _recompute_vulnerability(self) -> None:
        for t in self.towers:
            if not t.alive:
                continue
            team = t.team.value if t.team else ""
            if t.tier == "t1":
                t.vulnerable = True
            elif t.tier in ("t2", "t3"):
                prev = self._tower(f"{team}_{t.lane}_{'t1' if t.tier == 't2' else 't2'}")
                t.vulnerable = prev is None or not prev.alive
            elif t.tier == "t4":
                t.vulnerable = any(not x.alive for x in self.towers if x.team is t.team and x.tier == "t3")
            else:  # ancient
                t.vulnerable = all(not x.alive for x in self.towers if x.team is t.team and x.tier == "t4")

    def _towers_act(self) -> None:
        now = self.time
        towers = self.towers if self.tick_count % 2 == 0 else self.towers[::-1]
        for t in towers:
            if not t.alive or t.damage <= 0 or now < t.next_attack:
                continue
            assert t.team is not None
            target: Unit | None = None
            cur = self.get_unit(t.target_uid) if t.target_uid else None
            if cur is not None and cur.alive and dist(cur.pos, t.pos) <= t.attack_range:
                if not isinstance(cur, Hero) or self.is_visible_to(t.team, cur):
                    target = cur
            if target is None:
                # heroes attacking allied heroes in range take priority
                for h in self.heroes:
                    if h.team is not t.team and h.alive and dist(h.pos, t.pos) <= t.attack_range:
                        if any(a.damage_log.get(h.uid, -99.0) > now - 2 for a in self.heroes if a.team is t.team):
                            target = h
                            break
            if target is None:
                lanes = self.lanes_active if t.lane == "base" else (t.lane,)
                best_d = t.attack_range
                for lane in lanes:
                    for c in self.creeps[lane]:
                        if c.team is not t.team:
                            d = dist(c.pos, t.pos)
                            if d <= best_d:
                                best_d, target = d, c
            if target is None:
                near = [h for h in self.heroes if h.team is not t.team and h.alive
                        and dist(h.pos, t.pos) <= t.attack_range]
                if near:
                    target = min(near, key=lambda h: dist(h.pos, t.pos))
            if target is not None:
                t.target_uid = target.uid
                t.next_attack = now + t.attack_interval
                self._damage(target, t.damage * armor_multiplier(target.armor), t)
        # fountain defence
        for h in self.heroes:
            if h.alive and dist(h.pos, FOUNTAIN[h.team.enemy]) <= FOUNTAIN_RADIUS:
                src = self._tower(f"{h.team.enemy.value}_ancient")
                if src is not None:
                    self._damage(h, 180 * self.config.tick, src)

    # ================================================================ neutrals / roshan
    def _neutrals_act(self) -> None:
        now = self.time
        for camp in self.camps:
            if not camp.alive or not camp.damage_log:
                continue
            attackers = [self.units[u] for u in camp.damage_log if u in self.units]
            attackers = [a for a in attackers if isinstance(a, Hero) and a.alive and
                         dist(a.pos, camp.home) <= NEUTRAL_LEASH]
            if not attackers:
                camp.hp = camp.max_hp
                camp.damage_log.clear()
                continue
            if now >= camp.next_attack:
                camp.next_attack = now + camp.attack_interval
                victim = min(attackers, key=lambda a: dist(a.pos, camp.pos))
                if dist(victim.pos, camp.pos) <= 2.0:
                    self._damage(victim, camp.damage * armor_multiplier(victim.armor), camp)

    def _roshan_act(self) -> None:
        r = self.roshan
        now = self.time
        if not r.alive or now < r.next_attack:
            return
        near = [h for h in self.heroes if h.alive and dist(h.pos, r.pos) <= 2.5]
        if not near:
            if r.damage_log and r.hp < r.max_hp:
                r.hp = min(r.max_hp, r.hp + 30 * self.config.tick)
            return
        r.next_attack = now + r.attack_interval
        victim = min(near, key=lambda h: (h.hp, h.uid))
        self._damage(victim, (r.damage + now / 60 * 3) * armor_multiplier(victim.armor), r)

    # ================================================================ snapshots / end
    def _record_snapshot(self) -> None:
        self.timeline.append({
            "time": round(self.time),
            "heroes": [{"player_id": h.player_id, "gold": int(h.gold), "net_worth": h.net_worth, "xp": int(h.xp),
                        "level": h.level, "kills": h.kills, "deaths": h.deaths, "assists": h.assists,
                        "last_hits": h.last_hits, "denies": h.denies} for h in self.heroes],
        })

    def team_net_worth(self, team: Team) -> int:
        return sum(h.net_worth for h in self.heroes if h.team is team)

    def _check_end(self) -> None:
        if self.finished:
            return
        if self.time >= self.config.max_game_seconds:
            r = (self.team_net_worth(Team.RADIANT), self.score[Team.RADIANT],
                 sum(t.alive for t in self.towers if t.team is Team.RADIANT))
            d = (self.team_net_worth(Team.DIRE), self.score[Team.DIRE],
                 sum(t.alive for t in self.towers if t.team is Team.DIRE))
            # tie-break on surviving structures, then net worth, then kills
            rk, dk = (r[2], r[0], r[1]), (d[2], d[0], d[1])
            winner = Team.RADIANT if rk > dk else Team.DIRE if dk > rk else None
            self._finish(winner, "time_limit")

    def _finish(self, winner: Team | None, condition: str) -> None:
        if self.finished:
            return
        self.finished = True
        self.winner = winner
        self.win_condition = condition
        self._record_snapshot()
        self._emit("game_end", None, {"winner": winner.value if winner else None, "condition": condition,
                                      "duration": round(self.time, 1)})

    def force_finish(self, reason: str = "stopped") -> None:
        """End the match without a winner (operator stop)."""
        self._finish(None, reason)

    # ================================================================ views
    def snapshot(self) -> dict[str, Any]:
        now = self.time
        heroes = []
        for h in self.heroes:
            d = h.summary()
            d["respawn_in"] = 0 if h.alive else max(0, round(h.respawn_at - now))
            heroes.append(d)
        return {
            "time": round(now, 1),
            "finished": self.finished,
            "winner": self.winner.value if self.winner else None,
            "win_condition": self.win_condition,
            "score": {t.value: v for t, v in self.score.items()},
            "net_worth": {t.value: self.team_net_worth(t) for t in Team},
            "heroes": heroes,
            "towers": [{"uid": t.uid, "team": t.team.value if t.team else None, "tier": t.tier, "lane": t.lane,
                        "alive": t.alive, "hp": round(max(0, t.hp)), "max_hp": round(t.max_hp),
                        "pos": [round(t.pos[0], 1), round(t.pos[1], 1)]} for t in self.towers],
            "creeps": {lane: {"radiant": sum(1 for c in self.creeps[lane] if c.team is Team.RADIANT),
                              "dire": sum(1 for c in self.creeps[lane] if c.team is Team.DIRE),
                              "front": self._lane_front(lane)} for lane in LANES},
            "roshan": {"alive": self.roshan.alive, "hp": round(max(0, self.roshan.hp)), "kills": self.roshan.kills},
            "wards": [{"team": w.team.value, "pos": [round(w.pos[0], 1), round(w.pos[1], 1)]} for w in self.wards],
        }

    def _lane_front(self, lane: str) -> list[float] | None:
        creeps = self.creeps[lane]
        if not creeps:
            return None
        xs = sum(c.pos[0] for c in creeps) / len(creeps)
        ys = sum(c.pos[1] for c in creeps) / len(creeps)
        return [round(xs, 1), round(ys, 1)]

    def retreat_point(self, h: Hero, threat: Vec) -> Vec:
        """Point to run to: away from the threat, biased toward own fountain."""
        a = away(h.pos, threat, 4.0)
        f = FOUNTAIN[h.team]
        return toward(a, f, 3.0)

