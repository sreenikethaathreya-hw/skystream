import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { useSession } from "@/hooks/useSession";
import { AdminDataPage } from "@/pages/admin/AdminDataPage";
import { AdminSettingsPage } from "@/pages/admin/AdminSettingsPage";
import { AdminUsersPage } from "@/pages/admin/AdminUsersPage";
import { CapturePage } from "@/pages/CapturePage";
import { ConsensusPage } from "@/pages/ConsensusPage";
import { DataQualityPage } from "@/pages/DataQualityPage";
import { LedgerPage } from "@/pages/LedgerPage";
import { TrackRecordPage } from "@/pages/TrackRecordPage";

function Home() {
  const { user } = useSession();
  const target = user?.role === "admin" ? "/admin/data" : user?.role === "lead" ? "/consensus" : "/capture";
  return <Navigate to={target} replace />;
}

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/capture" element={<CapturePage />} />
        <Route path="/ledger" element={<LedgerPage />} />
        <Route path="/consensus" element={<ConsensusPage />} />
        <Route path="/reps" element={<TrackRecordPage />} />
        <Route path="/data-quality" element={<DataQualityPage />} />
        <Route path="/admin/data" element={<AdminDataPage />} />
        <Route path="/admin/users" element={<AdminUsersPage />} />
        <Route path="/admin/settings" element={<AdminSettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
