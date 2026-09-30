import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { CalendarClock, Lock, RotateCcw, Sprout } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { useMeta } from "@/hooks/queries";
import { useAdvanceMonth, useResetDemo } from "@/hooks/mutations";
import { useDemoUser } from "@/hooks/useDemoUser";
import { monthName } from "@/lib/format";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/capture", label: "Capture", role: "rep" },
  { to: "/ledger", label: "Ledger" },
  { to: "/consensus", label: "Consensus", role: "lead" },
  { to: "/reps", label: "Track record" },
  { to: "/data-quality", label: "Data quality" },
];

function AiStatusBadge() {
  const { data } = useMeta();
  if (!data) return null;
  const jev = data.ai.mode === "live" || data.ai.mode === "record" ? "Jev live" : "Jev replay/offline";
  return (
    <Badge tone="jev" title={`Jev ${data.ai.jevModel} · Gemini ${data.ai.geminiModel}`}>
      {jev} · Gemini {data.ai.geminiConfigured ? "on" : "off"}
    </Badge>
  );
}

function DemoControls() {
  const { data: meta } = useMeta();
  const advance = useAdvanceMonth();
  const reset = useResetDemo();
  const toast = useToast();
  if (!meta) return null;

  const onAdvance = () =>
    advance.mutate(undefined, {
      onSuccess: (r) =>
        toast({
          tone: "success",
          title: `${monthName(r.fromMonth)} closed, clock now ${monthName(r.toMonth)}`,
          body: r.resolved.length
            ? `${r.confirmed} confirmed, ${r.contradicted} contradicted, ${r.inconclusive} inconclusive claims resolved against ${monthName(r.fromMonth)} actuals.`
            : "No claims were due this month.",
        }),
      onError: (e) => toast({ tone: "error", title: "Could not advance", body: e.message }),
    });

  return (
    <div className="flex items-center gap-2">
      <Badge tone="info" className="py-1">
        <CalendarClock size={12} /> {monthName(meta.clock.month)} {meta.clock.year}
      </Badge>
      <Button
        size="sm"
        variant="secondary"
        className="whitespace-nowrap"
        onClick={onAdvance}
        disabled={advance.isPending}
        data-testid="advance-month"
      >
        Advance month
      </Button>
      <Button
        size="sm"
        variant="ghost"
        onClick={() => reset.mutate(undefined, { onSuccess: () => toast({ tone: "info", title: "Demo reset to seed data" }) })}
        disabled={reset.isPending}
        title="Reset demo data"
      >
        <RotateCcw size={14} />
      </Button>
    </div>
  );
}

function RoleSwitcher() {
  const { user, users, setUserId } = useDemoUser();
  return (
    <label className="flex items-center gap-2 whitespace-nowrap text-xs text-muted">
      Acting as
      <select
        aria-label="Acting as"
        className="h-8 rounded-lg border border-line bg-surface px-2 text-sm text-ink"
        value={user?.id ?? ""}
        onChange={(e) => setUserId(e.target.value)}
      >
        {users.map((u) => (
          <option key={u.id} value={u.id}>
            {u.name} ({u.role})
          </option>
        ))}
      </select>
    </label>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { data: meta } = useMeta();
  const { user } = useDemoUser();
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-6 pt-3">
          <div className="flex items-center gap-3">
            <div className="flex size-8 items-center justify-center rounded-lg bg-brand-600 text-white">
              <Sprout size={18} />
            </div>
            <div>
              <p className="whitespace-nowrap text-sm font-semibold leading-tight">Defensible Demand Ledger</p>
              {meta && (
                <p className="flex items-center gap-1 whitespace-nowrap text-xs text-muted">
                  <Lock size={11} /> {meta.country} › {meta.species} › Blocky PGH (locked)
                </p>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <AiStatusBadge />
            <DemoControls />
            <RoleSwitcher />
          </div>
        </div>
        <nav className="mx-auto flex max-w-[1440px] items-center gap-1 px-6 pb-2 pt-2">
          {NAV.filter((n) => !n.role || n.role === user?.role).map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                cn(
                  "whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium",
                  isActive ? "bg-brand-50 text-brand-700" : "text-muted hover:text-ink",
                )
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-[1440px] px-6 py-6">{children}</main>
    </div>
  );
}
