import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MetaProvider } from "../hooks/MetaContext";
import MatchControl from "../pages/MatchControl";
import { META, SESSION, players } from "./fixtures";
import { mockFetch, renderWithProviders } from "./utils";

function setup(extra: [RegExp, unknown][] = []) {
  return mockFetch([
    ...extra,
    [/GET \/api\/meta/, META], [/GET \/api\/players/, players()],
    [/POST \/api\/sessions$/, { ...SESSION, id: 9, status: "created", participants: [], live: null }],
    [/GET \/api\/sessions/, { items: [SESSION], total: 1, page: 1, page_size: 10 }],
  ]);
}

describe("Match Control", () => {
  it("creates a session with all ten participants", async () => {
    const calls = setup();
    renderWithProviders(<MetaProvider><MatchControl /></MetaProvider>);
    expect(await screen.findByText("Radiant 5/5")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("session-seed"), { target: { value: "42" } });
    fireEvent.click(screen.getByTestId("create-session"));
    expect(await screen.findByText(/Session #9 created/)).toBeInTheDocument();
    const post = calls.find((c) => c.init?.method === "POST")!;
    const body = JSON.parse(String(post.init!.body));
    expect(body.participants).toHaveLength(10);
    expect(body.seed).toBe(42);
    expect(body.environment).toBe("mock");
  });

  it("updates team counters when a participant is excluded", async () => {
    setup();
    renderWithProviders(<MetaProvider><MatchControl /></MetaProvider>);
    fireEvent.click(await screen.findByLabelText("Include Dire 1"));
    expect(screen.getByText("Dire 4/5")).toBeInTheDocument();
  });

  it("asks for confirmation before stopping an active match", async () => {
    const calls = setup([[/POST \/api\/sessions\/3\/stop/, { ...SESSION, status: "stopped" }]]);
    renderWithProviders(<MetaProvider><MatchControl /></MetaProvider>);
    fireEvent.click(await screen.findByLabelText("Stop session 3"));
    expect(screen.getByText("Stop the active match?")).toBeInTheDocument();
    expect(calls.some((c) => c.url.includes("/stop"))).toBe(false);
    fireEvent.click(screen.getByText("Stop match"));
    await waitFor(() => expect(calls.some((c) => c.url.includes("/api/sessions/3/stop"))).toBe(true));
  });

  it("pauses a running session", async () => {
    const calls = setup([[/POST \/api\/sessions\/3\/pause/, { ...SESSION, status: "paused" }]]);
    renderWithProviders(<MetaProvider><MatchControl /></MetaProvider>);
    fireEvent.click(await screen.findByLabelText("Pause session 3"));
    await waitFor(() => expect(calls.some((c) => c.url.includes("/pause"))).toBe(true));
  });

  it("explains why an unavailable environment cannot run", async () => {
    setup();
    renderWithProviders(<MetaProvider><MatchControl /></MetaProvider>);
    await screen.findByText("Radiant 5/5");
    await waitFor(() => expect(screen.getByTestId("session-environment").querySelectorAll("option")).toHaveLength(2));
    fireEvent.change(screen.getByTestId("session-environment"), { target: { value: "dota_test" } });
    expect(screen.getByText("read-only GSI")).toBeInTheDocument();
  });
});
