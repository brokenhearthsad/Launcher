from __future__ import annotations

import asyncio

import pytest

from app.services.event_bus import EventBus


def test_ws_hello_ping_and_settings_event(client):
    with client.websocket_connect("/ws/events") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["data"]["version"]
        ws.send_json({"type": "ping"})
        assert ws.receive_json()["type"] == "pong"
        client.put("/api/settings", json={"ui_refresh_seconds": 4})
        msg = ws.receive_json()
        assert msg["type"] == "settings_updated" and msg["data"]["ui_refresh_seconds"] == 4


def test_event_bus_drops_oldest_when_full():
    bus = EventBus(queue_size=16)
    _, q = bus.subscribe()
    for i in range(20):
        bus.publish("system_error", {"i": i})
    assert q.qsize() == 16 and bus.dropped == 4
    first = asyncio.run(asyncio.wait_for(q.get(), 1))
    assert first["data"]["i"] == 4
    with pytest.raises(ValueError):
        bus.publish("not_an_event", {})


def test_publish_from_worker_thread_is_delivered(client):
    """Sync endpoints run in a threadpool; their events must still reach WebSocket clients."""
    with client.websocket_connect("/ws/events") as ws:
        ws.receive_json()  # hello
        import threading

        t = threading.Thread(target=lambda: client.app.state.lab.bus.publish("system_error", {"m": "from thread"}))
        t.start()
        t.join()
        while True:
            msg = ws.receive_json()
            if msg["type"] == "system_error":
                assert msg["data"]["m"] == "from thread"
                break
