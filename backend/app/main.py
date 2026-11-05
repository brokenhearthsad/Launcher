"""FastAPI application factory.

Run locally:  uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import analytics, health, logs, matches, players, sessions, settings, ws
from app.api.ratelimit import RateLimitMiddleware
from app.config import Settings, get_settings
from app.db.models import SystemLog
from app.db.seed import seed_players
from app.db.session import init_engine, run_migrations, session_scope
from app.errors import AppError
from app.logging_config import get_db_handler, get_logger, install_db_handler, setup_logging
from app.services import settings_service
from app.services.event_bus import EventBus
from app.state import VERSION, LabState

log = get_logger("app")


def _persist_logs(batch: list[dict]) -> None:
    with session_scope() as db:
        db.add_all([SystemLog(**row) for row in batch])


def _error(status: int, code: str, message: str, details=None) -> JSONResponse:
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(body, status_code=status)


def create_app(cfg: Settings | None = None) -> FastAPI:
    cfg = cfg or get_settings()
    setup_logging(cfg.log_level, cfg.log_dir)
    init_engine(cfg.database_url)
    run_migrations(cfg.database_url)
    install_db_handler(_persist_logs, cfg.db_log_level)

    with session_scope() as db:
        runtime = settings_service.load(db, cfg)
    settings_service.apply(runtime)
    state = LabState(cfg, EventBus(cfg.ws_queue_size), runtime)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        with session_scope() as db:
            created = seed_players(db) if cfg.seed_demo_players else 0
            state.manager.recover(db)
        if created:
            log.info("seeded %d default test participants", created)
        log.info("backend started (v%s) on http://%s:%d", VERSION, cfg.host, cfg.port)
        yield
        log.info("backend shutting down")
        await state.manager.shutdown()
        handler = get_db_handler()
        if handler is not None:
            handler.flush()

    app = FastAPI(title=cfg.app_name, version=VERSION, lifespan=lifespan,
                  description="Local test lab for 5v5 bot matches. Matches run in the local simulator.")
    app.state.lab = state
    app.add_middleware(RateLimitMiddleware, per_minute=cfg.api_rate_limit_per_minute)
    app.add_middleware(CORSMiddleware, allow_origins=cfg.cors_origins, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(AppError)
    async def app_error(_req: Request, exc: AppError):
        level = "warning" if exc.status_code < 500 else "error"
        getattr(log, level)("%s: %s", exc.code, exc.message)
        return _error(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_req: Request, exc: RequestValidationError):
        errors = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "")} for e in exc.errors()]
        first = errors[0] if errors else {"loc": [], "msg": "invalid request"}
        msg = f"{'.'.join(str(x) for x in first['loc'][1:]) or 'request'}: {first['msg']}"
        return _error(422, "validation_error", msg, errors)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_req: Request, exc: StarletteHTTPException):
        return _error(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def unhandled(_req: Request, exc: Exception):
        log.exception("unhandled error: %s", exc)
        state.bus.publish("system_error", {"component": "api", "message": f"{type(exc).__name__}: {exc}"})
        return _error(500, "internal_error", "internal server error")

    for r in (health, players, sessions, matches, analytics, logs, settings):
        app.include_router(r.router)
    app.include_router(ws.router)
    return app


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    s = get_settings()
    uvicorn.run("app.main:create_app", factory=True, host=s.host, port=s.port)
