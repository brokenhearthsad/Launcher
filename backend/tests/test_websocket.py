from __future__ import annotations

from collections import Counter


def test_ws_hello_and_ping(client):
    with client.websocket_connect("/ws/events") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["data"]["active_sessions"] == []
        ws.send_json({"type": "ping"})
        assert ws.receive_json()["type"] == "pong"


def test_ws_streams_session_events(client):
    sid = client.post("/api/sessions", json={"speed": 1000, "max_game_seconds": 600, "seed": 11}).json()["id"]
    seen: Counter = Counter()
    stats_msgs = []
    with client.websocket_connect("/ws/events") as ws:
        assert ws.receive_json()["type"] == "hello"
        client.post(f"/api/sessions/{sid}/start")
        while True:
            msg = ws.receive_json()
            seen[msg["type"]] += 1
            if msg["type"] == "statistics_updated":
                stats_msgs.append(msg)
            if msg["type"] == "session_finished":
                break
    assert seen["session_started"] == 1
    assert seen["player_updated"] >= 1
    assert seen["bot_action"] >= 1 and seen["match_event"] >= 1
    assert stats_msgs and stats_msgs[-1]["session_id"] == sid
    snap = stats_msgs[-1]["data"]
    assert len(snap["heroes"]) == 10 and len(snap["statistics"]) == 10 and snap["is_simulation"] is True
    # throttled: far fewer UI updates than simulation ticks (600 s / 0.5 s = 1200 ticks)
    assert seen["statistics_updated"] < 200


def test_event_bus_drops_oldest_when_full():
    import asyncio

    from app.services.event_bus import EventBus

    bus = EventBus(queue_size=16)
    _, q = bus.subscribe()
    for i in range(20):
        bus.publish("match_event", {"i": i})
    assert q.qsize() == 16 and bus.dropped == 4
    first = asyncio.run(asyncio.wait_for(q.get(), 1))
    assert first["data"]["i"] == 4
    import pytest
    with pytest.raises(ValueError):
        bus.publish("not_an_event", {})
