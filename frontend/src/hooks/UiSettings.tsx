// Interface refresh settings (stored on the backend, edited on the Settings page).
import { createContext, useContext, type ReactNode } from "react";
import { api } from "../api/client";
import { useAsync } from "./useAsync";

interface UiSettings {
  refreshMs: number;
  reload: () => Promise<void>;
}

const Ctx = createContext<UiSettings>({ refreshMs: 5000, reload: async () => {} });

export function UiSettingsProvider({ children }: { children: ReactNode }) {
  const { data, reload } = useAsync(api.settings, []);
  const refreshMs = (data?.runtime.ui_refresh_seconds ?? 5) * 1000;
  return <Ctx.Provider value={{ refreshMs, reload }}>{children}</Ctx.Provider>;
}

export function useUiSettings(): UiSettings {
  return useContext(Ctx);
}
