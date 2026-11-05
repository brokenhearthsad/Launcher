import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LiveEventsProvider, useLive, useLiveEvent } from "../hooks/LiveEvents";
import { FakeWebSocket } from "./utils";

function Probe() {
  const { state } = useLive();
  useLiveEvent(["match_event"], (m) => {
    document.body.dataset.last = JSON.stringify(m.data);
  });
  return <div data-testid="state">{state}</div>;
}

describe("LiveEventsProvider", () => {
  it("dispatches messages and reconnects with back-off", async () => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket as unknown as typeof WebSocket);
    render(<LiveEventsProvider url="ws://x"><Probe /></LiveEventsProvider>);
    await act(async () => { vi.advanceTimersByTime(1); });
    expect(screen.getByTestId("state")).toHaveTextContent("open");
    act(() => FakeWebSocket.instances[0].emit({ type: "match_event", session_id: 1, data: { k: 1 } }));
    expect(document.body.dataset.last).toBe('{"k":1}');
    act(() => FakeWebSocket.instances[0].emit({ type: "ping", session_id: null, data: {} }));
    expect(FakeWebSocket.instances[0].sent).toContain('{"type":"pong"}');
    act(() => FakeWebSocket.instances[0].close());
    expect(screen.getByTestId("state")).toHaveTextContent("closed");
    await act(async () => { vi.advanceTimersByTime(600); });
    expect(FakeWebSocket.instances.length).toBe(2);
  });
});
