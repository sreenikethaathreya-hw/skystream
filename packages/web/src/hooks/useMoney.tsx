import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { useCube, useMeta } from "@/hooks/queries";
import { useScope } from "@/hooks/useScope";
import { moneyFor, type Money } from "@/lib/money";
import type { DisplayCurrency } from "@/lib/types";

const KEY = "skystream.displayCurrency";
const CHOICES: DisplayCurrency[] = ["USD", "EUR", "LOCAL"];

interface CurrencyState {
  choice: DisplayCurrency;
  setChoice: (choice: DisplayCurrency) => void;
}

const CurrencyContext = createContext<CurrencyState | null>(null);

function stored(): DisplayCurrency | null {
  const raw = localStorage.getItem(KEY);
  return CHOICES.includes(raw as DisplayCurrency) ? (raw as DisplayCurrency) : null;
}

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const { data: meta } = useMeta();
  const [picked, setPicked] = useState<DisplayCurrency | null>(stored);
  const setChoice = useCallback((choice: DisplayCurrency) => {
    localStorage.setItem(KEY, choice);
    setPicked(choice);
  }, []);
  const value = useMemo(
    () => ({ choice: picked ?? meta?.defaultDisplayCurrency ?? "USD", setChoice }),
    [picked, meta, setChoice],
  );
  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>;
}

export function useDisplayCurrency(): CurrencyState {
  const ctx = useContext(CurrencyContext);
  if (!ctx) throw new Error("useDisplayCurrency must be used inside CurrencyProvider");
  return ctx;
}

/** Display conversion for the current scope, from the budget rates shipped with the cube. */
export function useMoney(): Money {
  const { choice } = useDisplayCurrency();
  const { scope } = useScope();
  const { data: cube } = useCube(scope);
  return useMemo(() => moneyFor(choice, cube?.fx, cube?.localCurrency), [choice, cube]);
}
