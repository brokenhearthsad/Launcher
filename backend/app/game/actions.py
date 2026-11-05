"""Adapter-neutral action and result types exchanged between bots and adapters."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionType(str, Enum):
    MOVE = "move"
    ATTACK = "attack"  # attack a unit; ``once=True`` for last hit / deny timing
    CAST = "cast"
    USE_ITEM = "use_item"
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Action:
    type: ActionType
    target_uid: str | None = None
    pos: tuple[float, float] | None = None
    ability: str | None = None
    item: str | None = None
    once: bool = False
    # Attack only when the target HP drops to this value (last-hit timing); bot-estimated.
    hp_threshold: float | None = None
    # Metadata for analytics/telemetry (ignored by the adapter)
    intent: str = ""
    source: str = ""
    score: float = 0.0
    note: str = ""

    def describe(self) -> str:
        parts = [self.intent or self.type.value]
        if self.ability:
            parts.append(f"[{self.ability}]")
        if self.item:
            parts.append(f"[{self.item}]")
        if self.target_uid:
            parts.append(f"-> {self.target_uid}")
        return " ".join(parts)


@dataclass
class ActionResult:
    ok: bool
    reason: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class AdapterError(Exception):
    """Base class for adapter failures."""


class AdapterNotSupportedError(AdapterError):
    """Raised by adapters for operations the target environment cannot perform."""

    def __init__(self, operation: str, reason: str):
        self.operation = operation
        self.reason = reason
        super().__init__(f"{operation} is not supported: {reason}")
