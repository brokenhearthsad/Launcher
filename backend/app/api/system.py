"""Launcher process information and graceful shutdown."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Header, Request

from app.api.deps import State
from app.errors import AppError, ConflictError
from app.logging_config import get_logger
from app.platform.process_info import self_usage

router = APIRouter(prefix="/api/system", tags=["system"])
log = get_logger("system")
LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


@router.get("/process")
def process() -> dict:
    """RAM/CPU of the Launcher process itself (what Task Manager shows for python.exe)."""
    return self_usage()


@router.post("/shutdown", status_code=202)
async def shutdown(request: Request, state: State,
                   x_launcher_request: str | None = Header(None)) -> dict:
    """Stop the Launcher gracefully.

    Requires the custom ``X-Launcher-Request`` header: browsers cannot send it
    cross-origin without a CORS preflight, so other websites cannot trigger it.
    """
    client = request.client.host if request.client else ""
    if x_launcher_request != "1" or client not in LOOPBACK:
        raise ForbiddenError("shutdown is only accepted from the local Launcher UI or stop.bat")
    if state.server is None:
        raise ConflictError("not started via 'python -m app'; stop the server from its console")
    log.info("graceful shutdown requested")
    state.bus.publish("shutdown", {"reason": "requested"})

    async def _stop() -> None:
        await asyncio.sleep(0.3)  # let the response reach the client first
        state.server.should_exit = True

    asyncio.get_running_loop().create_task(_stop())
    return {"status": "stopping"}
