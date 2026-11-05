import { createContext, useContext, type ReactNode } from "react";
import { api } from "../api/client";
import type { Meta } from "../api/types";
import { useAsync } from "./useAsync";

const MetaCtx = createContext<Meta | null>(null);

export function MetaProvider({ children }: { children: ReactNode }) {
  const { data } = useAsync(api.meta, []);
  return <MetaCtx.Provider value={data ?? null}>{children}</MetaCtx.Provider>;
}

export function useMeta(): Meta | null {
  return useContext(MetaCtx);
}

export function useHeroName() {
  const meta = useMeta();
  return (key: string) => meta?.heroes.find((h) => h.key === key)?.name ?? key;
}

export function useItemName() {
  const meta = useMeta();
  return (key: string) => meta?.items.find((i) => i.key === key)?.name ?? key;
}
