import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";

export interface AsyncState<T> {
  data: T | undefined;
  error: ApiError | null;
  loading: boolean;
  reload: () => Promise<void>;
  setData: (d: T) => void;
}

/**
 * Load data from an async function. Re-runs when ``deps`` change and, if
 * ``intervalMs`` is set, polls at that interval (paused while the tab is hidden).
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = [], intervalMs?: number): AsyncState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const alive = useRef(true);

  const reload = useCallback(async () => {
    try {
      const d = await fnRef.current();
      if (alive.current) {
        setData(d);
        setError(null);
      }
    } catch (e) {
      if (alive.current) setError(e instanceof ApiError ? e : new ApiError(0, "error", String(e)));
    } finally {
      if (alive.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    setLoading(true);
    void reload();
    return () => {
      alive.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    if (!intervalMs) return;
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") void reload();
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs, reload]);

  return { data, error, loading, reload, setData };
}
