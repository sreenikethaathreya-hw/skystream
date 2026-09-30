import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { useScopes } from "@/hooks/queries";
import type { Scope, ScopeOption } from "@/lib/types";

const SCOPE_KEY = "skystream.scope";

interface ScopeState {
  scope: Scope | null;
  option: ScopeOption | undefined;
  options: ScopeOption[];
  loading: boolean;
  setScope: (scope: Scope) => void;
}

const ScopeContext = createContext<ScopeState | null>(null);

function readStored(): Scope | null {
  const raw = localStorage.getItem(SCOPE_KEY);
  if (!raw) return null;
  const [countryCode, megaSegmentId] = raw.split("|");
  return countryCode && megaSegmentId ? { countryCode, megaSegmentId } : null;
}

export function ScopeProvider({ children }: { children: ReactNode }) {
  const { data: options = [], isLoading } = useScopes();
  const [stored, setStored] = useState<Scope | null>(readStored);

  const setScope = useCallback((scope: Scope) => {
    localStorage.setItem(SCOPE_KEY, `${scope.countryCode}|${scope.megaSegmentId}`);
    setStored(scope);
  }, []);

  const value = useMemo<ScopeState>(() => {
    const match = (s: Scope | null) =>
      s ? options.find((o) => o.countryCode === s.countryCode && o.megaSegmentId === s.megaSegmentId) : undefined;
    const option = match(stored) ?? options[0];
    const scope = option ? { countryCode: option.countryCode, megaSegmentId: option.megaSegmentId } : null;
    return { scope, option, options, loading: isLoading, setScope };
  }, [options, stored, isLoading, setScope]);

  return <ScopeContext.Provider value={value}>{children}</ScopeContext.Provider>;
}

export function useScope(): ScopeState {
  const ctx = useContext(ScopeContext);
  if (!ctx) throw new Error("useScope must be used inside ScopeProvider");
  return ctx;
}
