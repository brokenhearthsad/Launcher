"""Process-wide application state (one instance per FastAPI app)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from fastapi import Request

from app.config import Settings
from app.db.session import session_scope
from app.schemas import RuntimeSettings
from app.services import settings_service
from app.services.event_bus import EventBus
from app.services.session_manager import SessionManager

VERSION = "1.0.0"


@dataclass
class LabState:
    config: Settings
    bus: EventBus
    runtime: RuntimeSettings
    manager: SessionManager = field(init=False)
    started_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        self.manager = SessionManager(self.bus, lambda: self.runtime)

    def reload_runtime(self) -> RuntimeSettings:
        with session_scope() as db:
            self.runtime = settings_service.load(db, self.config)
        return self.runtime


def get_state(request: Request) -> LabState:
    return request.app.state.lab
