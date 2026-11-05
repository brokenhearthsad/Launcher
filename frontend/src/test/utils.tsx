import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { LiveEventsProvider } from "../hooks/LiveEvents";

/** Fake WebSocket so components can mount without a server. */
export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];
  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
    setTimeout(() => this.onopen?.(), 0);
  }
  send(d: string) { this.sent.push(d); }
  close() { this.onclose?.(); }
  emit(msg: unknown) { this.onmessage?.({ data: JSON.stringify(msg) }); }
}

type Route = [RegExp, unknown | ((url: string, init?: RequestInit) => unknown)];

export function mockFetch(routes: Route[]) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    for (const [re, body] of routes) {
      if (re.test(`${init?.method ?? "GET"} ${url}`)) {
        const value = typeof body === "function" ? (body as (u: string, i?: RequestInit) => unknown)(url, init) : body;
        if (value instanceof Response) return value;
        return new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
      }
    }
    return new Response(JSON.stringify({ error: { code: "not_found", message: `no mock for ${url}` } }), { status: 404 });
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

export function renderWithProviders(ui: ReactElement, path = "/") {
  vi.stubGlobal("WebSocket", FakeWebSocket as unknown as typeof WebSocket);
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <LiveEventsProvider url="ws://test/ws/events">{ui}</LiveEventsProvider>
    </MemoryRouter>,
  );
}
