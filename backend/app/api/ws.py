"""WebSocket endpoint: pushes throttled lab events to the dashboard."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.logging_config import get_logger

router = APIRouter()
log = get_logger("ws")
PING_INTERVAL = 20.0


@router.websocket("/ws/events")
async def events(ws: WebSocket) -> None:
    state = ws.app.state.lab
    await ws.accept()
    sid, queue = state.bus.subscribe()
    await ws.send_json({"type": "hello", "session_id": None,
                        "data": {"active_sessions": state.manager.active_ids()}})

    async def reader() -> None:
        # Clients may send {"type": "ping"}; anything else is ignored.
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if isinstance(msg, dict) and msg.get("type") == "ping":
                await ws.send_json({"type": "pong", "session_id": None, "data": {}})

    reader_task = asyncio.create_task(reader())
    try:
        while True:
            get = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait({get, reader_task}, timeout=PING_INTERVAL,
                                         return_when=asyncio.FIRST_COMPLETED)
            if reader_task in done:
                get.cancel()
                reader_task.result()  # re-raise disconnects
                break
            if get in done:
                await ws.send_json(get.result())
            else:
                get.cancel()
                await ws.send_json({"type": "ping", "session_id": None, "data": {}})
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        log.exception("websocket error")
    finally:
        reader_task.cancel()
        state.bus.unsubscribe(sid)
