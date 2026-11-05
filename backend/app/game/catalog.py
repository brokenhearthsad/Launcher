"""Static game data used by the local simulator.

This is a *simplified test model*, not a reproduction of Dota 2 balance data.
Hero names are used as labels so test setups are recognisable; their stats and
abilities are generic archetype kits tuned for the simulator.

Distance units: 1 map unit ~= 160 Dota units (map is 100 x 100).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.domain import Role

AbilityKind = Literal[
    "nuke", "aoe_nuke", "stun", "slow", "heal", "shield", "buff", "escape", "ult_aoe", "ult_single"
]


@dataclass(frozen=True)
class AbilitySpec:
    key: str
    name: str
    kind: AbilityKind
    mana: tuple[int, ...]
    cooldown: tuple[float, ...]
    damage: tuple[int, ...] = (0, 0, 0, 0)
    cast_range: float = 4.0
    radius: float = 0.0
    stun: float = 0.0
    slow: float = 0.0  # fraction of move speed removed
    slow_duration: float = 0.0
    heal: tuple[int, ...] = (0, 0, 0, 0)
    shield: tuple[int, ...] = (0, 0, 0, 0)
    buff_damage: tuple[int, ...] = (0, 0, 0, 0)
    buff_duration: float = 0.0
    ultimate: bool = False


@dataclass(frozen=True)
class HeroSpec:
    key: str
    name: str
    primary: Literal["str", "agi", "int"]
    roles: tuple[Role, ...]
    base_hp: int
    hp_per_level: int
    base_mana: int
    mana_per_level: int
    base_damage: int
    damage_per_level: float
    base_armor: float
    armor_per_level: float
    attack_range: float
    attack_time: float  # seconds between attacks at level 1
    move_speed: float  # map units / second
    hp_regen: float
    mana_regen: float
    abilities: tuple[AbilitySpec, ...]

    @property
    def melee(self) -> bool:
        return self.attack_range <= 1.5


# --------------------------------------------------------------------------- abilities
def _nuke(name: str, dmg=(90, 160, 230, 300), mana=(90, 105, 120, 135), cd=(10, 9, 8, 7), rng=4.0):
    return AbilitySpec("q", name, "nuke", mana, cd, damage=dmg, cast_range=rng)


def _aoe(name: str, dmg=(80, 140, 200, 260), radius=2.2, rng=4.0):
    return AbilitySpec(
        "q", name, "aoe_nuke", (100, 115, 130, 145), (12, 11, 10, 9), damage=dmg, cast_range=rng, radius=radius
    )


def _stun(name: str, stun=1.5, dmg=(70, 120, 170, 220), rng=4.0, radius=0.0, key="w"):
    return AbilitySpec(
        key, name, "stun", (100, 110, 120, 130), (14, 13, 12, 11), damage=dmg, cast_range=rng, stun=stun, radius=radius
    )


def _slow(name: str, slow=0.35, dmg=(60, 100, 140, 180), key="w"):
    return AbilitySpec(
        key, name, "slow", (70, 80, 90, 100), (12, 11, 10, 9), damage=dmg, cast_range=4.0, slow=slow, slow_duration=3.0
    )


def _heal(name: str, heal=(100, 160, 220, 280), key="e"):
    return AbilitySpec(key, name, "heal", (80, 95, 110, 125), (14, 12, 10, 8), heal=heal, cast_range=4.0)


def _shield(name: str, shield=(80, 140, 200, 260), key="e"):
    return AbilitySpec(key, name, "shield", (75, 85, 95, 105), (14, 12, 10, 8), shield=shield, cast_range=4.0)


def _buff(name: str, dmg=(15, 30, 45, 60), dur=8.0, key="e"):
    return AbilitySpec(key, name, "buff", (40, 45, 50, 55), (20, 18, 16, 14), buff_damage=dmg, buff_duration=dur)


def _escape(name: str, key="e"):
    return AbilitySpec(key, name, "escape", (60, 60, 60, 60), (16, 13, 10, 7), cast_range=6.0)


def _ult_aoe(name: str, dmg=(250, 375, 500, 500), stun=1.5, radius=2.6):
    return AbilitySpec(
        "r", name, "ult_aoe", (150, 200, 250, 250), (90, 75, 60, 60), damage=dmg, cast_range=4.5,
        radius=radius, stun=stun, ultimate=True,
    )


def _ult_single(name: str, dmg=(350, 500, 650, 650), stun=0.0):
    return AbilitySpec(
        "r", name, "ult_single", (150, 225, 300, 300), (70, 60, 50, 50), damage=dmg, cast_range=4.5,
        stun=stun, ultimate=True,
    )


# --------------------------------------------------------------------------- heroes
def _hero(key, name, primary, roles, *, hp=600, hpl=85, mana=290, manal=40, dmg=52, dmgl=3.0, armor=2.5,
          armorl=0.35, rng=1.0, at=1.6, ms=1.95, hpr=2.0, mpr=1.0, abilities=()):
    return HeroSpec(key, name, primary, tuple(roles), hp, hpl, mana, manal, dmg, dmgl, armor, armorl, rng, at, ms,
                    hpr, mpr, tuple(abilities))


C, M, O, SS, HS = Role.CARRY, Role.MID, Role.OFFLANE, Role.SOFT_SUPPORT, Role.HARD_SUPPORT  # noqa: E741

HEROES: dict[str, HeroSpec] = {
    h.key: h
    for h in [
        _hero("juggernaut", "Juggernaut", "agi", [C], hp=620, dmg=54, dmgl=3.4, armor=3.5, ms=1.97,
              abilities=[_aoe("Spinning Edge", radius=1.6, rng=0.5), _heal("Field Ward", key="w"),
                         _buff("Keen Strikes"), _ult_single("Blade Storm", dmg=(400, 560, 720, 720))]),
        _hero("phantom_assassin", "Phantom Assassin", "agi", [C], hp=580, dmg=56, dmgl=3.5, armor=4.0, ms=1.97,
              abilities=[_nuke("Thrown Dagger", dmg=(70, 120, 170, 220)), _escape("Shadow Step", key="w"),
                         _buff("Assassin Focus", dmg=(20, 35, 50, 65)), _ult_single("Coup Strike")]),
        _hero("anti_mage", "Anti-Mage", "agi", [C], hp=580, dmg=53, dmgl=3.3, armor=3.0, ms=2.0, mana=280,
              abilities=[_slow("Mana Rend"), _escape("Phase Jump", key="e"), _buff("Focus", key="w"),
                         _ult_single("Void Burst", dmg=(300, 450, 600, 600))]),
        _hero("sven", "Sven", "str", [C, O], hp=680, hpl=95, dmg=56, dmgl=3.2, armor=3.0, ms=1.95,
              abilities=[_stun("Hammer Throw", radius=1.6), _shield("Warcry", key="w"), _buff("Great Cleave"),
                         _ult_single("Gods Might", dmg=(300, 420, 540, 540))]),
        _hero("luna", "Luna", "agi", [C], hp=560, dmg=50, dmgl=3.3, armor=2.5, rng=4.0, at=1.5, ms=2.0,
              abilities=[_nuke("Moon Beam"), _buff("Lunar Blessing", key="w"), _slow("Glaive Bounce", key="e"),
                         _ult_aoe("Eclipse", dmg=(300, 450, 600, 600), stun=0.0)]),
        _hero("shadow_fiend", "Shadow Fiend", "agi", [M, C], hp=560, dmg=55, dmgl=3.6, armor=1.5, rng=3.1, at=1.6,
              abilities=[_aoe("Shadowraze", rng=2.5), _aoe("Far Raze", rng=4.0), _buff("Soul Harvest"),
                         _ult_aoe("Requiem", dmg=(320, 480, 640, 640), stun=0.0)]),
        _hero("lina", "Lina", "int", [M, SS], hp=540, mana=330, manal=50, dmg=50, dmgl=2.8, armor=1.0, rng=4.0,
              abilities=[_aoe("Flame Wave"), _stun("Fire Pillar", radius=1.5), _buff("Fiery Soul"),
                         _ult_single("Laguna Strike", dmg=(450, 650, 850, 850))]),
        _hero("zeus", "Zeus", "int", [M, SS], hp=540, mana=360, manal=55, dmg=48, dmgl=2.5, armor=1.0, rng=2.4,
              abilities=[_nuke("Arc Bolt", dmg=(85, 120, 155, 190), cd=(4, 4, 3.5, 3)), _stun("Lightning Hand"),
                         _shield("Static Field", key="e"), _ult_aoe("Thundergod", dmg=(225, 325, 425, 425), stun=0.0,
                                                                     radius=50.0)]),
        _hero("puck", "Puck", "int", [M], hp=540, mana=330, manal=50, dmg=47, dmgl=2.6, armor=1.5, rng=3.6, ms=2.0,
              abilities=[_aoe("Illusory Orb"), _stun("Waning Rift", radius=2.0, stun=1.2), _escape("Phase Shift"),
                         _ult_aoe("Dream Bind", dmg=(150, 250, 350, 350), stun=2.0)]),
        _hero("storm_spirit", "Storm Spirit", "int", [M], hp=560, mana=360, manal=55, dmg=50, dmgl=2.8, rng=3.0,
              abilities=[_aoe("Static Remnant", radius=1.6, rng=1.5), _stun("Vortex", stun=1.4, dmg=(0, 0, 0, 0)),
                         _buff("Overload"), _ult_single("Ball Strike", dmg=(250, 380, 510, 510))]),
        _hero("axe", "Axe", "str", [O], hp=700, hpl=95, dmg=52, armor=3.5, armorl=0.4, ms=2.0,
              abilities=[_stun("Berserker Call", stun=2.0, rng=1.6, radius=1.8, dmg=(0, 0, 0, 0)),
                         _slow("Battle Hunger"), _shield("Counter Helix", key="e"),
                         _ult_single("Culling Blade", dmg=(250, 350, 450, 450))]),
        _hero("mars", "Mars", "str", [O], hp=680, hpl=95, dmg=54, armor=3.0, ms=1.95,
              abilities=[_stun("Spear Charge", stun=1.6, rng=4.5), _aoe("God Rebuke", rng=1.5),
                         _shield("Bulwark"), _ult_aoe("Arena", dmg=(200, 300, 400, 400), stun=1.0)]),
        _hero("tidehunter", "Tidehunter", "str", [O], hp=720, hpl=100, dmg=50, armor=3.0, ms=1.9,
              abilities=[_slow("Gush", slow=0.4), _shield("Kraken Shell", key="w"), _aoe("Anchor Smash", rng=1.4),
                         _ult_aoe("Ravage", dmg=(250, 350, 450, 450), stun=2.0, radius=5.0)]),
        _hero("centaur", "Centaur Warrunner", "str", [O], hp=720, hpl=100, dmg=52, armor=2.5, ms=1.95,
              abilities=[_stun("Hoof Stomp", radius=1.8, rng=0.5), _nuke("Double Edge", dmg=(100, 160, 220, 280),
                                                                       rng=1.2), _shield("Retaliate"),
                         _ult_aoe("Stampede", dmg=(150, 225, 300, 300), stun=1.0, radius=50.0)]),
        _hero("bristleback", "Bristleback", "str", [O, C], hp=700, hpl=95, dmg=52, armor=4.0, ms=1.95,
              abilities=[_slow("Nasal Goo", slow=0.3), _aoe("Quill Spray", rng=0.5, radius=3.0),
                         _shield("Bristle Back", shield=(120, 180, 240, 300)),
                         _ult_single("Warpath", dmg=(250, 350, 450, 450))]),
        _hero("earthshaker", "Earthshaker", "str", [SS, O], hp=620, mana=300, dmg=50, armor=2.0,
              abilities=[_stun("Fissure", stun=1.4, rng=4.5, radius=1.5), _buff("Enchant Totem", key="w"),
                         _aoe("Aftershock", rng=1.0, dmg=(60, 90, 120, 150)),
                         _ult_aoe("Echo Slam", dmg=(300, 400, 500, 500), stun=0.5, radius=3.5)]),
        _hero("mirana", "Mirana", "agi", [SS, M], hp=560, dmg=50, rng=3.8, ms=2.0,
              abilities=[_aoe("Starstorm", radius=3.0, rng=0.5), _stun("Sacred Arrow", stun=2.5, rng=6.0),
                         _escape("Leap"), _shield("Moonlight Cloak", key="r")]),
        _hero("skywrath", "Skywrath Mage", "int", [SS, HS], hp=520, mana=360, manal=55, dmg=46, armor=0.5, rng=3.8,
              abilities=[_nuke("Arcane Bolt", cd=(5, 4.5, 4, 3.5)), _slow("Concussive Shot"),
                         _slow("Ancient Seal", slow=0.3, key="e"),
                         _ult_aoe("Mystic Flare", dmg=(350, 550, 750, 750), stun=0.0, radius=1.2)]),
        _hero("crystal_maiden", "Crystal Maiden", "int", [HS], hp=520, mana=360, manal=55, dmg=46, armor=0.5,
              rng=3.75, ms=1.9, mpr=2.0,
              abilities=[_aoe("Crystal Nova"), _stun("Frostbite", stun=1.8, dmg=(50, 100, 150, 200)),
                         _shield("Arcane Aura", key="e"), _ult_aoe("Freezing Field", dmg=(300, 450, 600, 600),
                                                                   stun=0.0, radius=3.0)]),
        _hero("dazzle", "Dazzle", "int", [HS], hp=540, mana=340, manal=50, dmg=46, armor=1.0, rng=3.4,
              abilities=[_slow("Poison Touch"), _shield("Shallow Grave", shield=(200, 300, 400, 500), key="w"),
                         _heal("Shadow Wave", heal=(120, 180, 240, 300)), _heal("Bad Juju", key="r")]),
        _hero("witch_doctor", "Witch Doctor", "int", [HS], hp=540, mana=340, manal=50, dmg=48, armor=1.0, rng=3.75,
              abilities=[_stun("Paralyzing Cask", stun=1.0, radius=2.0), _heal("Voodoo Restoration", key="w"),
                         _slow("Maledict", key="e"), _ult_single("Death Ward", dmg=(400, 600, 800, 800))]),
        _hero("lion", "Lion", "int", [HS, SS], hp=540, mana=340, manal=50, dmg=48, armor=1.0, rng=3.6,
              abilities=[_stun("Earth Spike", stun=1.6, radius=1.0), _stun("Hex", stun=2.5, dmg=(0, 0, 0, 0), key="e"),
                         _nuke("Mana Drain", dmg=(60, 90, 120, 150)), _ult_single("Finger Strike",
                                                                                   dmg=(600, 725, 850, 850))]),
        _hero("warlock", "Warlock", "int", [HS], hp=560, mana=340, manal=50, dmg=46, armor=1.0, rng=3.75,
              abilities=[_slow("Fatal Bonds", slow=0.2), _heal("Shadow Word"), _aoe("Upheaval", radius=3.0),
                         _ult_aoe("Chaotic Offering", dmg=(250, 350, 450, 450), stun=1.0)]),
        _hero("ogre_magi", "Ogre Magi", "str", [HS, SS], hp=720, hpl=95, mana=300, dmg=52, armor=4.0,
              abilities=[_stun("Fireblast", stun=1.3), _nuke("Ignite", dmg=(70, 120, 170, 220)),
                         _buff("Bloodlust", key="e"),
                         _ult_aoe("Multicast", dmg=(200, 300, 400, 400), stun=0.5, radius=2.0)]),
    ]
}

# --------------------------------------------------------------------------- items


@dataclass(frozen=True)
class ItemSpec:
    key: str
    name: str
    cost: int
    category: Literal["consumable", "basic", "boots", "core", "support", "luxury"]
    stats: dict[str, float] = field(default_factory=dict)
    active: str | None = None  # see simulator.engine.ITEM_ACTIVES
    cooldown: float = 0.0
    charges: int = 0  # consumables


ITEMS: dict[str, ItemSpec] = {
    i.key: i
    for i in [
        ItemSpec("healing_salve", "Healing Salve", 110, "consumable", active="heal_400", cooldown=1, charges=1),
        ItemSpec("clarity", "Clarity", 50, "consumable", active="mana_180", cooldown=1, charges=1),
        ItemSpec("town_portal", "Town Portal Scroll", 100, "consumable", active="teleport", cooldown=80, charges=1),
        ItemSpec("observer_ward", "Observer Ward", 50, "consumable", active="ward", cooldown=1, charges=1),
        ItemSpec("iron_branch", "Iron Branch", 50, "basic", {"hp": 18, "mana": 12, "damage": 1}),
        ItemSpec("quelling_blade", "Quelling Blade", 100, "basic", {"creep_damage": 0.25}),
        ItemSpec("magic_wand", "Magic Wand", 450, "basic", {"hp": 40, "mana": 40},
                 active="wand_restore", cooldown=13),
        ItemSpec("boots_of_speed", "Boots of Speed", 500, "boots", {"move_speed": 0.28}),
        ItemSpec("power_treads", "Power Treads", 1400, "boots",
                 {"move_speed": 0.28, "attack_speed": 0.25, "damage": 10, "hp": 100}),
        ItemSpec("phase_boots", "Phase Boots", 1500, "boots", {"move_speed": 0.3, "damage": 18, "armor": 4}),
        ItemSpec("arcane_boots", "Arcane Boots", 1400, "boots", {"move_speed": 0.28, "mana": 250},
                 active="team_mana", cooldown=55),
        ItemSpec("tranquil_boots", "Tranquil Boots", 925, "boots", {"move_speed": 0.4, "hp_regen": 14}),
        ItemSpec("battle_fury", "Battle Fury", 4100, "core",
                 {"damage": 50, "hp_regen": 7.5, "mana_regen": 2.75, "creep_damage": 0.6}),
        ItemSpec("maelstrom", "Maelstrom", 2950, "core", {"damage": 24, "proc_damage": 30, "creep_damage": 0.3}),
        ItemSpec("desolator", "Desolator", 3500, "core", {"damage": 50, "armor_reduction": 6}),
        ItemSpec("black_king_bar", "Black King Bar", 4050, "core", {"damage": 24, "hp": 200},
                 active="spell_immunity", cooldown=70),
        ItemSpec("blink_dagger", "Blink Dagger", 2250, "core", {}, active="blink", cooldown=15),
        ItemSpec("blade_mail", "Blade Mail", 2100, "core", {"damage": 28, "armor": 6, "mana": 120}),
        ItemSpec("aghanims_scepter", "Aghanim's Scepter", 4200, "core",
                 {"hp": 175, "mana": 150, "damage": 10, "ult_amp": 0.3}),
        ItemSpec("force_staff", "Force Staff", 2200, "support", {"hp": 175, "mana_regen": 1.5},
                 active="force", cooldown=19),
        ItemSpec("glimmer_cape", "Glimmer Cape", 1950, "support", {"magic_resist": 0.2},
                 active="ally_shield", cooldown=14),
        ItemSpec("mekansm", "Mekansm", 1775, "support", {"armor": 2, "hp_regen": 2.5},
                 active="team_heal", cooldown=50),
        ItemSpec("pipe", "Pipe of Insight", 3475, "support", {"hp_regen": 7.5, "magic_resist": 0.3},
                 active="team_shield", cooldown=60),
        ItemSpec("aether_lens", "Aether Lens", 2275, "support", {"mana": 300, "mana_regen": 2.5, "cast_range": 1.4}),
        ItemSpec("heart", "Heart of Tarrasque", 5000, "luxury", {"hp": 1000, "hp_regen": 18}),
        ItemSpec("butterfly", "Butterfly", 4975, "luxury", {"damage": 25, "attack_speed": 0.6, "evasion": 0.35}),
        ItemSpec("daedalus", "Daedalus", 5150, "luxury", {"damage": 88, "crit": 0.3}),
        ItemSpec("satanic", "Satanic", 5050, "luxury", {"damage": 25, "hp": 300, "lifesteal": 0.3},
                 active="lifesteal_burst", cooldown=30),
        ItemSpec("assault_cuirass", "Assault Cuirass", 5125, "luxury", {"armor": 15, "attack_speed": 0.35}),
        ItemSpec("shivas_guard", "Shiva's Guard", 4850, "luxury", {"armor": 15, "mana": 250},
                 active="aoe_slow_nuke", cooldown=27),
    ]
}

# Starting builds and core build orders per role (Item AI adapts these).
ROLE_STARTING_ITEMS: dict[Role, list[str]] = {
    Role.CARRY: ["quelling_blade", "healing_salve", "iron_branch", "iron_branch"],
    Role.MID: ["iron_branch", "iron_branch", "healing_salve", "clarity"],
    Role.OFFLANE: ["quelling_blade", "healing_salve", "iron_branch", "iron_branch"],
    Role.SOFT_SUPPORT: ["observer_ward", "healing_salve", "clarity", "iron_branch"],
    Role.HARD_SUPPORT: ["observer_ward", "healing_salve", "clarity", "clarity"],
}

ROLE_CORE_BUILD: dict[Role, list[str]] = {
    Role.CARRY: ["power_treads", "battle_fury", "black_king_bar", "butterfly", "daedalus", "satanic"],
    Role.MID: ["power_treads", "maelstrom", "black_king_bar", "aghanims_scepter", "daedalus", "butterfly"],
    Role.OFFLANE: ["phase_boots", "blink_dagger", "blade_mail", "pipe", "assault_cuirass", "heart"],
    Role.SOFT_SUPPORT: ["arcane_boots", "blink_dagger", "force_staff", "aether_lens", "aghanims_scepter",
                        "shivas_guard"],
    Role.HARD_SUPPORT: ["tranquil_boots", "magic_wand", "glimmer_cape", "mekansm", "force_staff", "shivas_guard"],
}

STARTING_GOLD = 600
INVENTORY_SLOTS = 6

# Cumulative XP required for each level (index = level-1). Simplified curve.
XP_TABLE: list[int] = [0, 240, 640, 1160, 1760, 2440, 3200, 4000, 4900, 5900, 7000, 8200, 9500, 10900,
                       12400, 14000, 15700, 17500, 19400, 21400, 23600, 26000, 28600, 31400, 34400]
MAX_LEVEL = len(XP_TABLE)


def hero_options() -> list[dict]:
    return [
        {"key": h.key, "name": h.name, "primary": h.primary, "roles": [r.value for r in h.roles],
         "attack_range": h.attack_range, "abilities": [a.name for a in h.abilities]}
        for h in HEROES.values()
    ]


def item_options() -> list[dict]:
    return [{"key": i.key, "name": i.name, "cost": i.cost, "category": i.category} for i in ITEMS.values()]
