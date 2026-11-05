// WebSocket connection to /ws/events with automatic reconnection.
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { wsUrl } from "../api/client";
import type { WsMessage } from "../api/types";

export type ConnectionState = "connecting" | "open" | "closed";
type Listener = (msg: WsMessage) => void;

interface LiveContextValue {
  state: ConnectionState;
  subscribe: (types: string[] | "*", fn: Listener) => () => void;
  lastMessageAt: number | null;
}

const LiveContext = createContext<LiveContextValue | null>(null);

const MIN_DELAY = 500;
const MAX_DELAY = 10_000;

export function LiveEventsProvider({ children, url }: { children: ReactNode; url?: string }) {
  const [state, setState] = useState<ConnectionState>("connecting");
  const [lastMessageAt, setLast] = useState<number | null>(null);
  const listeners = useRef(new Set<{ types: string[] | "*"; fn: Listener }>());

  useEffect(() => {
    let ws: WebSocket | null = null;
    let delay = MIN_DELAY;
    let timer: number | undefined;
    let stopped = false;

    const connect = () => {
      if (stopped) return;
      setState("connecting");
      try {
        ws = new WebSocket(url ?? wsUrl());
      } catch {
        schedule();
        return;
      }
      ws.onopen = () => {
        delay = MIN_DELAY;
        setState("open");
      };
      ws.onmessage = (ev) => {
        let msg: WsMessage;
        try {
          msg = JSON.parse(ev.data as string) as WsMessage;
        } catch {
          return;
        }
        if (msg.type === "ping") {
          ws?.send(JSON.stringify({ type: "pong" }));
          return;
        }
        setLast(Date.now());
        for (const l of listeners.current) {
          if (l.types === "*" || l.types.includes(msg.type)) l.fn(msg);
        }
      };
      ws.onclose = () => {
        setState("closed");
        schedule();
      };
      ws.onerror = () => ws?.close();
    };

    const schedule = () => {
      if (stopped) return;
      timer = window.setTimeout(connect, delay);
      delay = Math.min(MAX_DELAY, delay * 2); // exponential back-off
    };

    connect();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      ws?.close();
    };
  }, [url]);

  const subscribe = (types: string[] | "*", fn: Listener) => {
    const entry = { types, fn };
    listeners.current.add(entry);
    return () => {
      listeners.current.delete(entry);
    };
  };

  return <LiveContext.Provider value={{ state, subscribe, lastMessageAt }}>{children}</LiveContext.Provider>;
}

export function useLive(): LiveContextValue {
  const ctx = useContext(LiveContext);
  if (!ctx) throw new Error("useLive must be used inside LiveEventsProvider");
  return ctx;
}

/** Subscribe to specific event types for the lifetime of the component. */
export function useLiveEvent(types: string[] | "*", fn: Listener) {
  const { subscribe } = useLive();
  const ref = useRef(fn);
  ref.current = fn;
  const key = types === "*" ? "*" : types.join(",");
  useEffect(() => subscribe(types, (m) => ref.current(m)), [key]); // eslint-disable-line react-hooks/exhaustive-deps
}
