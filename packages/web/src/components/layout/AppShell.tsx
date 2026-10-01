import { lazy, Suspense, useEffect, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { LogOut, MessageSquare } from "lucide-react";
import { DemoControls } from "@/components/layout/DemoControls";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { useCube, useMeta } from "@/hooks/queries";
import { useChat } from "@/hooks/useChat";
import { useDisplayCurrency } from "@/hooks/useMoney";
import { useScope } from "@/hooks/useScope";
import type { DisplayCurrency } from "@/lib/types";
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

function AiStatus() {
  const { data } = useMeta();
  if (!data) return null;
  const live = data.ai.mode === "live" || data.ai.mode === "record";
  const jev = !data.ai.externalAiAllowed ? "Jev off (not cleared)" : live ? "Jev live" : "Jev replay/offline";
  return (
    <span className="whitespace-nowrap text-white/55" title={`Jev ${data.ai.jevModel} · Gemini ${data.ai.geminiModel}`}>
      {jev} · Gemini {data.ai.geminiConfigured ? "on" : "off"}
    </span>
  );
}

/** Demo-only controls, kept apart from the product header so they read as stage machinery. */
function DemoBar() {
  return (
    <div className="bg-ink text-xs text-white/80">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-x-4 gap-y-1 px-6 py-1">
        <span className="font-mono text-[10.5px] font-medium uppercase tracking-[0.12em] text-white">Demo</span>
        <span className="hidden text-white/55 md:inline">Anonymized seed data</span>
        <AiStatus />
        <div className="ml-auto flex flex-wrap items-center gap-3">
          <DemoControls />
          <RoleSwitcher />
        </div>
      </div>
    </div>
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
    <label className="flex items-center gap-2 whitespace-nowrap text-white/55">
      Acting as
      <select
        aria-label="Acting as"
        className="h-7 rounded-md border border-white/20 bg-white/10 px-2 text-xs text-white [&>option]:text-ink"
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
      <Button
        size="sm"
        variant="secondary"
        onClick={() => chat.openChat()}
        onPointerEnter={() => void loadChat()}
        onFocus={() => void loadChat()}
        data-testid="ask-the-data"
      >
        <MessageSquare size={14} aria-hidden="true" />
        Ask the data
      </Button>
      <Sheet open={chat.open} onClose={chat.closeChat} title="Ask the data">
        <Suspense fallback={<p className="p-4 text-sm text-muted">Loading…</p>}>
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
      {dataMode === "demo" && <DemoBar />}
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-6 pt-3">
          <div className="flex items-center gap-3">
            <svg className="size-10 shrink-0" viewBox="0 0 32 32" aria-hidden="true">
              <defs>
                <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor="#7dd3fc" />
                  <stop offset=".4" stopColor="#fef3c7" />
                  <stop offset=".7" stopColor="#fbbf24" />
                  <stop offset="1" stopColor="#f59e0b" />
                </linearGradient>
                <linearGradient id="mtn" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor="#22c55e" />
                  <stop offset="1" stopColor="#14532d" />
                </linearGradient>
                <clipPath id="clip">
                  <circle cx="16" cy="16" r="14" />
                </clipPath>
              </defs>
              <circle cx="16" cy="16" r="15" fill="#14532d" />
              <circle cx="16" cy="16" r="14" fill="url(#sky)" />
              <g clipPath="url(#clip)">
                <path d="M2 30 L2 19 L7 21 L12 15 L17 18 L22 11 L27 14 L32 8 L32 30Z" fill="url(#mtn)" />
                <line x1="22" y1="12" x2="22" y2="30" stroke="#fff" strokeWidth="2" />
                <line x1="22" y1="12" x2="22" y2="30" stroke="#87CEEB" strokeWidth="1" />
                <polyline points="2,19 7,21 12,15 17,18 22,11 27,14 32,8" fill="none" stroke="#fff" strokeWidth="1.5" />
                <circle cx="12" cy="15" r="2" fill="#f97316" stroke="#fff" strokeWidth="1" />
                <circle cx="22" cy="11" r="2" fill="#f97316" stroke="#fff" strokeWidth="1" />
                <circle cx="27" cy="14" r="2" fill="#f97316" stroke="#fff" strokeWidth="1" />
                <path d="M22 6 L22.5 9 L25.5 11 L22.5 13 L22 16 L21.5 13 L18.5 11 L21.5 9Z" fill="#fbbf24" />
              </g>
            </svg>
            <div className="leading-tight">
              <p className="text-[17px] font-semibold tracking-tight"><span style={{ color: '#87CEEB' }}>Sky</span>stream</p>
              <p className="eyebrow">Defensible demand ledger</p>
            </div>
            <span aria-hidden="true" className="mx-1 hidden h-8 w-px bg-line sm:block" />
            <ScopePicker />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <AskTheData />
            <CurrencyPicker />
            {dataMode !== "demo" && <UserMenu />}
          </div>
        </div>
        <nav aria-label="Main" className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-1 px-6 pt-2">
          {NAV.filter((n) => !n.roles || (user && n.roles.includes(user.role))).map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                cn(
                  "relative whitespace-nowrap px-3 pb-2.5 pt-1.5 text-sm font-medium",
                  isActive
                    ? "text-ink after:absolute after:inset-x-3 after:-bottom-px after:h-0.5 after:rounded-full after:bg-ink"
                    : "text-muted hover:text-ink",
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
