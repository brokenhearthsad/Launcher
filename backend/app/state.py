"""Process-wide application state (one instance per FastAPI app)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Request

from app.config import Settings
from app.schemas import RuntimeSettings
from app.services.event_bus import EventBus

VERSION = "2.0.0-phase2"


@dataclass
class LabState:
    config: Settings
    bus: EventBus
    runtime: RuntimeSettings
    started_at: float = field(default_factory=time.time)
    last_backup: Path | None = None
    # Set by ``python -m app`` so the shutdown endpoint can stop uvicorn gracefully.
    server: Any = None
    # Phase 2 services (created in the lifespan; None when monitoring is disabled).
    monitor: Any = None
    environment: Any = None
    slots: Any = None


def get_state(request: Request) -> LabState:
    return request.app.state.lab
