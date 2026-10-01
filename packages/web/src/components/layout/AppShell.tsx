import { lazy, Suspense, useCallback, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { LogOut, MessageSquare, Sprout } from "lucide-react";
import { DemoControls } from "@/components/layout/DemoControls";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { useMeta } from "@/hooks/queries";
import { useScope } from "@/hooks/useScope";
import { useSession } from "@/hooks/useSession";
import { cn } from "@/lib/utils";

const loadChat = () => import("@/components/chat/ChatPanel");
const ChatPanel = lazy(() => loadChat().then((m) => ({ default: m.ChatPanel })));

const NAV = [
  { to: "/capture", label: "Capture", roles: ["rep"] },
  { to: "/ledger", label: "Ledger" },
  { to: "/consensus", label: "Consensus", roles: ["lead", "admin"] },
  { to: "/rules", label: "Lead rules", roles: ["lead", "admin"] },
  { to: "/reps", label: "Track record" },
  { to: "/data-quality", label: "Data quality", roles: ["lead", "admin"] },
  { to: "/admin/data", label: "Admin: data", roles: ["admin"] },
  { to: "/admin/users", label: "Admin: users", roles: ["admin"] },
  { to: "/admin/settings", label: "Admin: settings", roles: ["admin"] },
];

function AiStatusBadge() {
  const { data } = useMeta();
  if (!data) return null;
  const live = data.ai.mode === "live" || data.ai.mode === "record";
  const jev = !data.ai.externalAiAllowed ? "Jev off (not cleared)" : live ? "Jev live" : "Jev replay/offline";
  return (
    <Badge tone="jev" title={`Jev ${data.ai.jevModel} · Gemini ${data.ai.geminiModel}`}>
      {jev} · Gemini {data.ai.geminiConfigured ? "on" : "off"}
    </Badge>
  );
}

function ScopePicker() {
  const { scope, options, setScope } = useScope();
  if (!options.length) return <span className="text-xs text-muted">No data loaded for your segments</span>;
  return (
    <select
      aria-label="Scope"
      data-testid="scope-picker"
      className="h-8 max-w-[360px] rounded-lg border border-line bg-surface px-2 text-xs text-ink"
      value={scope ? `${scope.countryCode}|${scope.megaSegmentId}` : ""}
      onChange={(e) => {
        const [countryCode, megaSegmentId] = e.target.value.split("|");
        setScope({ countryCode, megaSegmentId });
      }}
    >
      {options.map((o) => (
        <option key={`${o.countryCode}|${o.megaSegmentId}`} value={`${o.countryCode}|${o.megaSegmentId}`}>
          {o.countryName} › {o.species ?? "?"} › {o.megaSegmentDesc} ({o.segments})
        </option>
      ))}
    </select>
  );
}

function RoleSwitcher() {
  const { user, users, setUserId } = useSession();
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

function AskTheData() {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const { user } = useSession();
  const { scope } = useScope();
  const { data: meta } = useMeta();
  if (!user || !meta?.ai.chatEnabled) return null;
  return (
    <>
      <Button
        size="sm"
        variant="secondary"
        onClick={() => setOpen(true)}
        onPointerEnter={() => void loadChat()}
        onFocus={() => void loadChat()}
        data-testid="ask-the-data"
      >
        <MessageSquare size={14} aria-hidden="true" />
        Ask the data
      </Button>
      <Sheet open={open} onClose={close} title="Ask the data">
        <Suspense fallback={<p className="p-4 text-sm text-muted">Loading…</p>}>
          <ChatPanel key={user.id} role={user.role} scope={scope} offline={meta.ai.chatMode !== "agent"} />
        </Suspense>
      </Sheet>
    </>
  );
}

function UserMenu() {
  const { user, email, signOut } = useSession();
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-right leading-tight">
        <span className="block font-medium text-ink">{user?.name}</span>
        <span className="block text-muted">
          {email} · {user?.role}
        </span>
      </span>
      <Button size="sm" variant="ghost" onClick={signOut} title="Sign out" aria-label="Sign out">
        <LogOut size={14} aria-hidden="true" />
      </Button>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, dataMode } = useSession();
  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2 focus:text-sm focus:shadow-lg"
      >
        Skip to content
      </a>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-6 pt-3">
          <div className="flex items-center gap-3">
            <div className="flex size-8 items-center justify-center rounded-lg bg-brand-600 text-white">
              <Sprout size={18} />
            </div>
            <div className="flex flex-col gap-1">
              <p className="whitespace-nowrap text-sm font-semibold leading-tight">
                Defensible Demand Ledger
                {dataMode === "demo" && <Badge className="ml-2">demo data</Badge>}
              </p>
              <ScopePicker />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <AskTheData />
            <AiStatusBadge />
            {dataMode === "demo" ? (
              <>
                <DemoControls />
                <RoleSwitcher />
              </>
            ) : (
              <UserMenu />
            )}
          </div>
        </div>
        <nav aria-label="Main" className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-1 px-6 pb-2 pt-2">
          {NAV.filter((n) => !n.roles || (user && n.roles.includes(user.role))).map((n) => (
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
      <main id="main" tabIndex={-1} className="mx-auto max-w-[1440px] px-6 py-6 focus:outline-none">
        {children}
      </main>
    </div>
  );
}
