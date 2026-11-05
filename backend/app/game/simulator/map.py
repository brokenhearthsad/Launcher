"""Lab map geometry (100 x 100 abstract map, Radiant bottom-left).

Three lanes are polylines from the Radiant ancient to the Dire ancient. The map
is point-symmetric around (50, 50), which keeps balanced scenarios fair.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain import Team

Vec = tuple[float, float]
LANES = ("top", "mid", "bot")

RADIANT_ANCIENT: Vec = (12.0, 12.0)
DIRE_ANCIENT: Vec = (88.0, 88.0)
FOUNTAIN = {Team.RADIANT: (4.0, 4.0), Team.DIRE: (96.0, 96.0)}
ANCIENT = {Team.RADIANT: RADIANT_ANCIENT, Team.DIRE: DIRE_ANCIENT}
ROSHAN_PIT: Vec = (38.0, 60.0)

_LANE_POINTS: dict[str, list[Vec]] = {
    "top": [RADIANT_ANCIENT, (10.0, 22.0), (10.0, 90.0), (78.0, 90.0), DIRE_ANCIENT],
    "mid": [RADIANT_ANCIENT, DIRE_ANCIENT],
    "bot": [RADIANT_ANCIENT, (22.0, 10.0), (90.0, 10.0), (90.0, 78.0), DIRE_ANCIENT],
}

# Tower placement as fraction of lane length measured from the owner's ancient.
TOWER_FRACTIONS = {"t1": {"top": 0.40, "mid": 0.40, "bot": 0.40}, "t2": 0.26, "t3": 0.13}


def dist(a: Vec, b: Vec) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def toward(a: Vec, b: Vec, step: float) -> Vec:
    """Move from ``a`` toward ``b`` by at most ``step``."""
    d = dist(a, b)
    if d <= step or d == 0:
        return b
    k = step / d
    return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)


def away(a: Vec, threat: Vec, step: float) -> Vec:
    d = dist(a, threat) or 1e-6
    k = step / d
    x = min(99.0, max(1.0, a[0] + (a[0] - threat[0]) * k))
    y = min(99.0, max(1.0, a[1] + (a[1] - threat[1]) * k))
    return (x, y)


@dataclass(frozen=True)
class LanePath:
    name: str
    points: tuple[Vec, ...]
    cumulative: tuple[float, ...]

    @property
    def length(self) -> float:
        return self.cumulative[-1]

    def point_at(self, s: float) -> Vec:
        """Point at arc-length ``s`` from the Radiant ancient."""
        s = max(0.0, min(self.length, s))
        for i in range(1, len(self.points)):
            if s <= self.cumulative[i]:
                seg = self.cumulative[i] - self.cumulative[i - 1]
                k = 0 if seg == 0 else (s - self.cumulative[i - 1]) / seg
                a, b = self.points[i - 1], self.points[i]
                return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
        return self.points[-1]

    def point_for_team(self, team: Team, fraction: float) -> Vec:
        """``fraction`` of the lane measured from ``team``'s own ancient."""
        f = fraction if team is Team.RADIANT else 1.0 - fraction
        return self.point_at(f * self.length)

    def project(self, p: Vec) -> float:
        """Approximate arc-length of the closest lane point to ``p``."""
        best_s, best_d = 0.0, float("inf")
        for i in range(1, len(self.points)):
            a, b = self.points[i - 1], self.points[i]
            ax, ay = b[0] - a[0], b[1] - a[1]
            seg2 = ax * ax + ay * ay
            t = 0.0 if seg2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / seg2))
            q = (a[0] + ax * t, a[1] + ay * t)
            d = dist(p, q)
            if d < best_d:
                best_d = d
                best_s = self.cumulative[i - 1] + t * math.sqrt(seg2)
        return best_s


def _build(name: str) -> LanePath:
    pts = _LANE_POINTS[name]
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + dist(pts[i - 1], pts[i]))
    return LanePath(name, tuple(pts), tuple(cum))


LANE_PATHS: dict[str, LanePath] = {n: _build(n) for n in LANES}


def safe_lane(team: Team) -> str:
    return "bot" if team is Team.RADIANT else "top"


def off_lane(team: Team) -> str:
    return "top" if team is Team.RADIANT else "bot"


def resolve_lane(team: Team, lane_kind: str) -> str:
    """Map logical lane (safe/mid/off) to geometric lane for a team."""
    if lane_kind == "safe":
        return safe_lane(team)
    if lane_kind == "off":
        return off_lane(team)
    return "mid"


def mirror(p: Vec) -> Vec:
    return (100.0 - p[0], 100.0 - p[1])


# Neutral camps on the Radiant side; Dire camps are the mirror image.
_RADIANT_CAMPS: list[tuple[str, Vec, str]] = [
    ("r_small_1", (42.0, 22.0), "small"),
    ("r_medium_1", (55.0, 24.0), "medium"),
    ("r_large_1", (36.0, 32.0), "large"),
    ("r_medium_2", (62.0, 33.0), "medium"),
    ("r_large_2", (24.0, 44.0), "large"),
]
NEUTRAL_CAMPS: list[tuple[str, Vec, str, Team]] = [
    *[(cid, pos, kind, Team.RADIANT) for cid, pos, kind in _RADIANT_CAMPS],
    *[(cid.replace("r_", "d_"), mirror(pos), kind, Team.DIRE) for cid, pos, kind in _RADIANT_CAMPS],
]

# Ward spots used by supports (own side first, then contested).
WARD_SPOTS: dict[Team, list[Vec]] = {
    Team.RADIANT: [(40.0, 50.0), (60.0, 40.0), (30.0, 70.0), (70.0, 22.0), (50.0, 62.0)],
    Team.DIRE: [mirror(p) for p in [(40.0, 50.0), (60.0, 40.0), (30.0, 70.0), (70.0, 22.0), (50.0, 62.0)]],
}
