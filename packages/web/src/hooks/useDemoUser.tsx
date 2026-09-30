import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getStoredUserId, storeUserId } from "@/lib/api";
import type { DemoUser } from "@/lib/types";
import { useMeta } from "@/hooks/queries";

interface DemoUserState {
  user: DemoUser | undefined;
  users: DemoUser[];
  setUserId: (id: string) => void;
}

const DemoUserContext = createContext<DemoUserState | null>(null);

export function DemoUserProvider({ children }: { children: ReactNode }) {
  const [userId, setUserIdState] = useState(getStoredUserId);
  const queryClient = useQueryClient();
  const { data: meta } = useMeta();

  const setUserId = useCallback(
    (id: string) => {
      storeUserId(id);
      setUserIdState(id);
      queryClient.invalidateQueries();
    },
    [queryClient],
  );

  const value = useMemo<DemoUserState>(() => {
    const users = meta?.users ?? [];
    return { user: users.find((u) => u.id === userId), users, setUserId };
  }, [meta, userId, setUserId]);

  return <DemoUserContext.Provider value={value}>{children}</DemoUserContext.Provider>;
}

export function useDemoUser(): DemoUserState {
  const ctx = useContext(DemoUserContext);
  if (!ctx) throw new Error("useDemoUser must be used inside DemoUserProvider");
  return ctx;
}
