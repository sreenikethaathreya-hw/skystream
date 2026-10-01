import { useEffect, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { LogOut, MessageSquare, Sprout } from "lucide-react";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { DemoControls } from "@/components/layout/DemoControls";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { useCube, useMeta } from "@/hooks/queries";
import { useChat } from "@/hooks/useChat";
import { useDisplayCurrency } from "@/hooks/useMoney";
import { useScope } from "@/hooks/useScope";
import type { DisplayCurrency } from "@/lib/types";
import { useSession } from "@/hooks/useSession";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/capture", label: "Capture", roles: ["rep"] },
  { to: "/ledger", label: "Ledger" },
  { to: "/consensus", label: "Consensus", roles: ["lead", "admin"] },
  { to: "/rules", label: "Lead rules" },
  { to: "/reps", label: "Track record" },
  { to: "/data-quality", label: "Data quality" },
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

function CurrencyPicker() {
  const { choice, setChoice } = useDisplayCurrency();
  const { scope } = useScope();
  const { data: cube } = useCube(scope);
  const local = cube?.localCurrency;
  const missing = (code: string | undefined) => !!cube && !!code && code !== "USD" && !cube.fx.rates[code];
  return (
    <label className="flex items-center gap-1 whitespace-nowrap text-xs text-muted" title="Figures are stored in net USD at the budget rate">
      Show in
      <select
        aria-label="Display currency"
        data-testid="currency-picker"
        className="h-8 rounded-lg border border-line bg-surface px-2 text-xs text-ink"
        value={choice}
        onChange={(e) => setChoice(e.target.value as DisplayCurrency)}
      >
        <option value="USD">USD</option>
        <option value="EUR" disabled={missing("EUR")}>EUR{missing("EUR") ? " (no rate)" : ""}</option>
        <option value="LOCAL" disabled={missing(local)}>
          Local{local ? ` (${local})` : ""}
          {missing(local) ? " (no rate)" : ""}
        </option>
      </select>
    </label>
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
  const chat = useChat();
  const { user } = useSession();
  const { scope } = useScope();
  const { data: meta } = useMeta();
  const { data: cube } = useCube(scope);
  const { setSessionId, setEnabled } = chat;
  const enabled = !!user && !!meta?.ai.chatEnabled;
  useEffect(() => setSessionId(null), [user?.id, setSessionId]);
  useEffect(() => setEnabled(enabled), [enabled, setEnabled]);
  if (!user || !meta?.ai.chatEnabled) return null;
  const segmentLabel = (id: number) => cube?.segments.find((s) => s.id === id)?.label;
  return (
    <>
      <Button size="sm" variant="secondary" onClick={() => chat.openChat()} data-testid="ask-the-data">
        <MessageSquare size={14} />
        Ask the data
      </Button>
      <Sheet open={chat.open} onClose={chat.closeChat} title="Ask the data">
        <ChatPanel
          key={user.id}
          role={user.role}
          scope={scope}
          offline={meta.ai.chatMode !== "agent"}
          writesAllowed={meta.ai.chatWritesAllowed}
          pageContext={chat.pageContext}
          request={chat.request}
          onRequestHandled={chat.consumeRequest}
          segmentLabel={segmentLabel}
          sessionId={chat.sessionId}
          onSessionChange={chat.setSessionId}
        />
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
      <Button size="sm" variant="ghost" onClick={signOut} title="Sign out">
        <LogOut size={14} />
      </Button>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, dataMode } = useSession();
  return (
    <div className="min-h-screen">
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
            <CurrencyPicker />
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
        <nav className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-1 px-6 pb-2 pt-2">
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
      <main className="mx-auto max-w-[1440px] px-6 py-6">{children}</main>
    </div>
  );
}
