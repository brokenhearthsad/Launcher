"""Application configuration.

All values can be overridden with environment variables prefixed with ``DML_``
or through ``backend/.env``. No secrets are needed: the application never
stores Steam passwords, tokens or Steam Guard codes.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DML_",
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Launcher"
    host: str = "127.0.0.1"
    port: int = 8000
    # Host headers accepted by the server (protects against DNS rebinding).
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    # Only needed for frontend development with the Vite dev server.
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'match_lab.db').as_posix()}"
    backup_dir: Path = BACKEND_DIR / "data" / "backups"

    # Production frontend bundle served by FastAPI (built by install.bat).
    frontend_dist: Path = PROJECT_DIR / "frontend" / "dist"

    log_level: str = "INFO"
    log_dir: Path = BACKEND_DIR / "logs"
    db_log_level: str = "INFO"

    ws_publish_hz: float = Field(default=4.0, gt=0, le=20)
    ws_queue_size: int = Field(default=256, ge=16)
    api_rate_limit_per_minute: int = Field(default=600, ge=10)

    # Opt-in: lower the priority of the Launcher process itself (never other processes).
    lower_own_priority: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
