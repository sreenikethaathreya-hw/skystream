import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { useDemoUser } from "@/hooks/useDemoUser";
import { CapturePage } from "@/pages/CapturePage";
import { ConsensusPage } from "@/pages/ConsensusPage";
import { DataQualityPage } from "@/pages/DataQualityPage";
import { LedgerPage } from "@/pages/LedgerPage";
import { TrackRecordPage } from "@/pages/TrackRecordPage";

function Home() {
  const { user } = useDemoUser();
  return <Navigate to={user?.role === "lead" ? "/consensus" : "/capture"} replace />;
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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
