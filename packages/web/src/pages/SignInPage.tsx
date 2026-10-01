import { useState } from "react";
import type { Auth } from "firebase/auth";
import { Sprout } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";

export function SignInPage({ auth }: { auth: Auth }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const onSignIn = async () => {
    setBusy(true);
    setError(null);
    try {
      const { signInWithGoogle } = await import("@/lib/firebase");
      await signInWithGoogle(auth);
    } catch {
      setError("Sign-in did not complete. Allow pop-ups for this site and try again.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <Card className="w-full max-w-sm">
        <CardBody className="flex flex-col items-center gap-4 pt-6 text-center">
          <div className="flex size-10 items-center justify-center rounded-xl bg-brand-600 text-white" aria-hidden="true">
            <Sprout size={22} />
          </div>
          <div>
            <h1 className="text-lg font-semibold">Defensible Demand Ledger</h1>
            <p className="mt-1 text-sm text-muted">Sign in with your company Google account.</p>
          </div>
          <Button className="w-full" onClick={onSignIn} disabled={busy} data-testid="sign-in">
            {busy ? "Opening Google…" : "Sign in with Google"}
          </Button>
          {error && (
            <p role="alert" className="text-xs text-crit-700">
              {error}
            </p>
          )}
          <p className="text-[11px] text-muted">Access is limited to users an admin has added.</p>
        </CardBody>
      </Card>
    </main>
  );
}
