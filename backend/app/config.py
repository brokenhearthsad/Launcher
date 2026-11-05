"""Application configuration.

All values can be overridden with environment variables prefixed with ``DML_``
(Dota Match Lab) or through a ``.env`` file in the backend directory.
No secrets are required: the application never stores Steam credentials.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DML_",
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Dota 2 Match Lab"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'match_lab.db').as_posix()}"

    log_level: str = "INFO"
    log_dir: Path = BACKEND_DIR / "logs"
    db_log_level: str = "INFO"

    # Load management
    max_concurrent_sessions: int = Field(default=2, ge=1, le=8)
    ws_publish_hz: float = Field(default=4.0, gt=0, le=20)
    ws_queue_size: int = Field(default=256, ge=16)
    api_rate_limit_per_minute: int = Field(default=240, ge=10)

    # Simulator defaults
    sim_tick_seconds: float = Field(default=0.5, gt=0, le=2)
    sim_default_speed: float = Field(default=20.0, gt=0)
    sim_max_game_seconds: int = Field(default=3600, ge=300)
    sim_snapshot_interval: int = Field(default=60, ge=10)

    seed_demo_players: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
