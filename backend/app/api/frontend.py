"""Serve the production frontend bundle (``frontend/dist``) from FastAPI.

Client-side routes (``/logs``, ``/settings`` ...) fall back to ``index.html``.
API and WebSocket paths are never shadowed.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.errors import NotFoundError

NOT_BUILT = """<!doctype html><html lang="ru"><meta charset="utf-8"><title>Launcher</title>
<body style="background:#030712;color:#e5e7eb;font-family:Segoe UI,sans-serif;padding:40px">
<h1>Интерфейс не собран</h1>
<p>Папка <code>frontend/dist</code> не найдена. Запустите <b>install.bat</b> — он соберёт интерфейс.</p>
<p>API работает: <a style="color:#f59e0b" href="/docs">/docs</a></p></body></html>"""


def mount_frontend(app: FastAPI, dist: Path) -> None:
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    router = APIRouter(include_in_schema=False)
    index = dist / "index.html"
    root = dist.resolve()

    @router.get("/{path:path}")
    def spa(path: str):
        if path.startswith(("api/", "ws/")) or path in ("api", "ws"):
            raise NotFoundError(f"/{path} not found")
        if not index.exists():
            return HTMLResponse(NOT_BUILT, status_code=503)
        if path:
            candidate = (dist / path).resolve()
            if candidate.is_file() and root in candidate.parents:
                return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    app.include_router(router)
