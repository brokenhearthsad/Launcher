"""Tolerant parser for GSI payloads.

Every field is optional: Dota 2 only sends what is available in the current
context (main menu, hero pick, playing, spectating). Values with an unexpected
type are dropped (treated as missing) and reported in ``problems`` - they are
never replaced by defaults.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.integrations.gsi.heroes import hero_display_name

MAX_ABILITIES = 12
ITEM_SLOTS = [f"slot{i}" for i in range(9)] + [f"stash{i}" for i in range(6)] + ["teleport0", "neutral0"]

# Human-readable labels of DOTA_GAMERULES_STATE_* values.
GAME_STATES = {
    "DOTA_GAMERULES_STATE_INIT": "Инициализация",
    "DOTA_GAMERULES_STATE_WAIT_FOR_PLAYERS_TO_LOAD": "Загрузка игроков",
    "DOTA_GAMERULES_STATE_CUSTOM_GAME_SETUP": "Настройка игры",
    "DOTA_GAMERULES_STATE_PLAYER_DRAFT": "Драфт",
    "DOTA_GAMERULES_STATE_HERO_SELECTION": "Выбор героев",
    "DOTA_GAMERULES_STATE_STRATEGY_TIME": "Время стратегии",
    "DOTA_GAMERULES_STATE_TEAM_SHOWCASE": "Показ команд",
    "DOTA_GAMERULES_STATE_WAIT_FOR_MAP_TO_LOAD": "Загрузка карты",
    "DOTA_GAMERULES_STATE_PRE_GAME": "Подготовка (до появления крипов)",
    "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS": "Игра идёт",
    "DOTA_GAMERULES_STATE_POST_GAME": "Игра завершена",
    "DOTA_GAMERULES_STATE_DISCONNECT": "Отключение",
    "DOTA_GAMERULES_STATE_LAST": "Завершение",
}
IN_MATCH_STATES = {
    "DOTA_GAMERULES_STATE_STRATEGY_TIME", "DOTA_GAMERULES_STATE_TEAM_SHOWCASE",
    "DOTA_GAMERULES_STATE_WAIT_FOR_MAP_TO_LOAD", "DOTA_GAMERULES_STATE_PRE_GAME",
    "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
}
ENDED_STATES = {"DOTA_GAMERULES_STATE_POST_GAME", "DOTA_GAMERULES_STATE_LAST"}


class PayloadError(ValueError):
    """The payload is not usable at all (not a JSON object)."""


@dataclass
class Ability:
    slot: str
    name: str | None = None
    level: int | None = None
    can_cast: bool | None = None
    passive: bool | None = None
    active: bool | None = None
    cooldown: float | None = None
    ultimate: bool | None = None


@dataclass
class Item:
    slot: str
    name: str | None = None
    charges: int | None = None
    cooldown: float | None = None
    can_cast: bool | None = None


@dataclass
class GameSnapshot:
    # provider
    provider_name: str | None = None
    provider_version: int | None = None
    provider_timestamp: int | None = None
    # map
    has_map: bool = False
    map_name: str | None = None
    match_id: str | None = None
    game_mode: str | None = None
    custom_game_name: str | None = None
    game_state: str | None = None
    game_time: float | None = None
    clock_time: float | None = None
    daytime: bool | None = None
    paused: bool | None = None
    win_team: str | None = None
    radiant_score: int | None = None
    dire_score: int | None = None
    # player (no SteamID / account id / name is kept)
    has_player: bool = False
    activity: str | None = None
    team: str | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    last_hits: int | None = None
    denies: int | None = None
    gold: int | None = None
    gpm: int | None = None
    xpm: int | None = None
    # hero
    has_hero: bool = False
    hero_internal: str | None = None
    hero_name: str | None = None
    hero_level: int | None = None
    alive: bool | None = None
    respawn_seconds: int | None = None
    health: int | None = None
    max_health: int | None = None
    mana: int | None = None
    max_mana: int | None = None
    abilities: list[Ability] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def game_state_label(self) -> str | None:
        if self.game_state is None:
            return None
        return GAME_STATES.get(self.game_state, self.game_state)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["game_state_label"] = self.game_state_label
        return d


class _Reader:
    def __init__(self, section: str, data: Any, problems: list[str]):
        self.section = section
        self.problems = problems
        if data is not None and not isinstance(data, dict):
            problems.append(f"{section}: expected object, got {type(data).__name__}")
            data = None
        self.data: dict[str, Any] = data or {}

    @property
    def present(self) -> bool:
        return bool(self.data)

    def _bad(self, key: str, value: Any, expected: str) -> None:
        self.problems.append(f"{self.section}.{key}: expected {expected}, got {type(value).__name__}")

    def str(self, key: str) -> str | None:
        v = self.data.get(key)
        if v is None or v == "":
            return None
        if isinstance(v, (str, int)) and not isinstance(v, bool):
            return str(v)
        self._bad(key, v, "string")
        return None

    def int(self, key: str) -> int | None:
        v = self.data.get(key)
        if v is None:
            return None
        if isinstance(v, bool):
            self._bad(key, v, "integer")
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float) and v.is_integer():
            return int(v)
        if isinstance(v, str) and v.lstrip("-").isdigit():
            return int(v)
        self._bad(key, v, "integer")
        return None

    def float(self, key: str) -> float | None:
        v = self.data.get(key)
        if v is None:
            return None
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
        self._bad(key, v, "number")
        return None

    def bool(self, key: str) -> bool | None:
        v = self.data.get(key)
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if v in (0, 1):
            return bool(v)
        self._bad(key, v, "boolean")
        return None


def parse(payload: Any) -> GameSnapshot:
    if not isinstance(payload, dict):
        raise PayloadError(f"payload must be a JSON object, got {type(payload).__name__}")
    snap = GameSnapshot()
    p = snap.problems

    prov = _Reader("provider", payload.get("provider"), p)
    snap.provider_name = prov.str("name")
    snap.provider_version = prov.int("version")
    snap.provider_timestamp = prov.int("timestamp")

    m = _Reader("map", payload.get("map"), p)
    if m.present:
        snap.has_map = True
        snap.map_name = m.str("name")
        snap.match_id = m.str("matchid")
        snap.game_mode = m.str("game_mode")
        snap.custom_game_name = m.str("customgamename")
        snap.game_state = m.str("game_state")
        snap.game_time = m.float("game_time")
        snap.clock_time = m.float("clock_time")
        snap.daytime = m.bool("daytime")
        snap.paused = m.bool("paused")
        win = m.str("win_team")
        snap.win_team = None if win in (None, "none") else win
        snap.radiant_score = m.int("radiant_score")
        snap.dire_score = m.int("dire_score")

    pl = _Reader("player", payload.get("player"), p)
    if pl.present:
        snap.has_player = True
        snap.activity = pl.str("activity")
        snap.team = pl.str("team_name")
        for key in ("kills", "deaths", "assists", "last_hits", "denies", "gold", "gpm", "xpm"):
            setattr(snap, key, pl.int(key))

    h = _Reader("hero", payload.get("hero"), p)
    if h.present:
        internal = h.str("name")
        # A spectator/menu payload can contain a hero block with id -1 and no name.
        snap.has_hero = internal is not None
        snap.hero_internal = internal
        snap.hero_name = hero_display_name(internal)
        snap.hero_level = h.int("level")
        snap.alive = h.bool("alive")
        snap.respawn_seconds = h.int("respawn_seconds")
        snap.health = h.int("health")
        snap.max_health = h.int("max_health")
        snap.mana = h.int("mana")
        snap.max_mana = h.int("max_mana")

    ab = payload.get("abilities")
    if ab is not None and not isinstance(ab, dict):
        p.append(f"abilities: expected object, got {type(ab).__name__}")
    elif isinstance(ab, dict):
        for i in range(MAX_ABILITIES):
            key = f"ability{i}"
            if key not in ab:
                continue
            r = _Reader(f"abilities.{key}", ab[key], p)
            if not r.present:
                continue
            snap.abilities.append(Ability(key, r.str("name"), r.int("level"), r.bool("can_cast"), r.bool("passive"),
                                          r.bool("ability_active"), r.float("cooldown"), r.bool("ultimate")))

    it = payload.get("items")
    if it is not None and not isinstance(it, dict):
        p.append(f"items: expected object, got {type(it).__name__}")
    elif isinstance(it, dict):
        for key in ITEM_SLOTS:
            if key not in it:
                continue
            r = _Reader(f"items.{key}", it[key], p)
            name = r.str("name")
            if name in (None, "empty"):
                continue
            snap.items.append(Item(key, name, r.int("charges"), r.float("cooldown"), r.bool("can_cast")))
    return snap
