import { lazy, Suspense, type ComponentType } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { useSession } from "@/hooks/useSession";
import { CapturePage } from "@/pages/CapturePage";

function page<K extends string>(load: () => Promise<Record<K, ComponentType>>, name: K) {
  return lazy(() => load().then((m) => ({ default: m[name] })));
}

const LedgerPage = page(() => import("@/pages/LedgerPage"), "LedgerPage");
const ConsensusPage = page(() => import("@/pages/ConsensusPage"), "ConsensusPage");
const RulesPage = page(() => import("@/pages/RulesPage"), "RulesPage");
const TrackRecordPage = page(() => import("@/pages/TrackRecordPage"), "TrackRecordPage");
const DataQualityPage = page(() => import("@/pages/DataQualityPage"), "DataQualityPage");
const AdminDataPage = page(() => import("@/pages/admin/AdminDataPage"), "AdminDataPage");
const AdminUsersPage = page(() => import("@/pages/admin/AdminUsersPage"), "AdminUsersPage");
const AdminSettingsPage = page(() => import("@/pages/admin/AdminSettingsPage"), "AdminSettingsPage");

function Home() {
  const { user } = useSession();
  const target = user?.role === "admin" ? "/admin/data" : user?.role === "lead" ? "/consensus" : "/capture";
  return <Navigate to={target} replace />;
}

export function App() {
  return (
    <AppShell>
      <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/capture" element={<CapturePage />} />
          <Route path="/ledger" element={<LedgerPage />} />
          <Route path="/consensus" element={<ConsensusPage />} />
          <Route path="/rules" element={<RulesPage />} />
          <Route path="/reps" element={<TrackRecordPage />} />
          <Route path="/data-quality" element={<DataQualityPage />} />
          <Route path="/admin/data" element={<AdminDataPage />} />
          <Route path="/admin/users" element={<AdminUsersPage />} />
          <Route path="/admin/settings" element={<AdminSettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </AppShell>
  );
}
