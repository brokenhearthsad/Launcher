"""Display names for Dota 2 internal hero identifiers (``npc_dota_hero_*``).

Only heroes whose internal name differs from the display name are listed;
others are derived by title-casing the identifier.
"""
from __future__ import annotations

SPECIAL = {
    "abyssal_underlord": "Underlord", "antimage": "Anti-Mage", "centaur": "Centaur Warrunner",
    "doom_bringer": "Doom", "furion": "Nature's Prophet", "keeper_of_the_light": "Keeper of the Light",
    "life_stealer": "Lifestealer", "magnataur": "Magnus", "necrolyte": "Necrophos", "nevermore": "Shadow Fiend",
    "obsidian_destroyer": "Outworld Destroyer", "queenofpain": "Queen of Pain", "rattletrap": "Clockwerk",
    "shredder": "Timbersaw", "skeleton_king": "Wraith King", "treant": "Treant Protector",
    "vengefulspirit": "Vengeful Spirit", "windrunner": "Windranger", "wisp": "Io", "zuus": "Zeus",
    "skywrath_mage": "Skywrath Mage", "sand_king": "Sand King", "crystal_maiden": "Crystal Maiden",
    "storm_spirit": "Storm Spirit", "ancient_apparition": "Ancient Apparition", "faceless_void": "Faceless Void",
    "night_stalker": "Night Stalker", "phantom_assassin": "Phantom Assassin", "templar_assassin": "Templar Assassin",
    "dark_willow": "Dark Willow", "monkey_king": "Monkey King", "primal_beast": "Primal Beast",
}
PREFIX = "npc_dota_hero_"


def hero_display_name(internal: str | None) -> str | None:
    if not internal:
        return None
    key = internal.removeprefix(PREFIX)
    if key in SPECIAL:
        return SPECIAL[key]
    return " ".join(part.capitalize() for part in key.split("_"))
