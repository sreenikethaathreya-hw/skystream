import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Auth, User } from "firebase/auth";
import { SignInPage } from "@/pages/SignInPage";
import { useConfig, useMeta } from "@/hooks/queries";
import { ApiError, getStoredUserId, setTokenProvider, storeUserId } from "@/lib/api";
import { firebaseAuth, signOutUser, watchUser } from "@/lib/firebase";
import type { DataMode, DemoUser } from "@/lib/types";

interface SessionState {
  dataMode: DataMode;
  user: DemoUser | undefined;
  users: DemoUser[];
  email: string | null;
  setUserId: (id: string) => void;
  signOut: () => void;
}

const SessionContext = createContext<SessionState | null>(null);

function Centered({ children }: { children: ReactNode }) {
  return <div className="flex min-h-screen items-center justify-center p-6 text-sm text-muted">{children}</div>;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { data: config, error: configError } = useConfig();
  const [auth, setAuth] = useState<Auth | null>(null);
  const [firebaseUser, setFirebaseUser] = useState<User | null | undefined>(undefined);
  const [, setDemoUserId] = useState(getStoredUserId);
  const real = config?.dataMode === "real";

  useEffect(() => {
    if (!config) return;
    if (config.dataMode === "demo") {
      setTokenProvider(null);
      return;
    }
    if (!config.firebase) return;
    const a = firebaseAuth(config.firebase);
    setAuth(a);
    return watchUser(a, (user) => {
      setFirebaseUser(user);
      setTokenProvider(user ? () => user.getIdToken() : async () => null);
      queryClient.invalidateQueries();
    });
  }, [config, queryClient]);

  const signedIn = !!config && (!real || !!firebaseUser);
  const { data: meta, error: metaError } = useMeta(signedIn);

  const setUserId = useCallback(
    (id: string) => {
      storeUserId(id);
      setDemoUserId(id);
      queryClient.invalidateQueries();
    },
    [queryClient],
  );
  const signOut = useCallback(() => {
    if (auth) void signOutUser(auth);
  }, [auth]);

  const value = useMemo<SessionState>(
    () => ({
      dataMode: config?.dataMode ?? "demo",
      user: meta?.me,
      users: meta?.users ?? [],
      email: firebaseUser?.email ?? null,
      setUserId,
      signOut,
    }),
    [config, meta, firebaseUser, setUserId, signOut],
  );

  if (configError) return <Centered>Could not reach the server: {String(configError)}</Centered>;
  if (!config) return <Centered>Loading...</Centered>;
  if (real && !config.firebase) {
    return <Centered>Sign-in is not configured on the server (FIREBASE_PROJECT_ID / FIREBASE_WEB_API_KEY).</Centered>;
  }
  if (real && firebaseUser === undefined) return <Centered>Checking your session...</Centered>;
  if (real && !firebaseUser && auth) return <SignInPage auth={auth} />;
  if (metaError instanceof ApiError && metaError.status === 403) {
    return (
      <Centered>
        <div className="max-w-md space-y-3 text-center">
          <p className="text-base font-semibold text-ink">{firebaseUser?.email} is not registered</p>
          <p>{metaError.message}</p>
          <button className="text-brand-700 underline" onClick={signOut}>
            Sign in with another account
          </button>
        </div>
      </Centered>
    );
  }
  if (!meta) return <Centered>Loading your workspace...</Centered>;
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}
