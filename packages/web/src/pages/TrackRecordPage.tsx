import { EntryCard } from "@/components/ledger/EntryCard";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ProbBar } from "@/components/ui/prob-bar";
import { useEntries, useReps } from "@/hooks/queries";
import { fmtPct } from "@/lib/format";
import type { TrackRecord } from "@/lib/types";

function Metric({ label, value, hint, bar }: { label: string; value: string; hint: string; bar?: number }) {
  return (
    <div className="rounded-lg bg-canvas p-3">
      <p className="text-xs text-muted">{label}</p>
      <p className="tabular text-2xl font-semibold">{value}</p>
      {bar !== undefined && <ProbBar value={bar} tone="brand" className="mt-1" />}
      <p className="mt-1 text-[11px] text-muted">{hint}</p>
    </div>
  );
}

function RepCard({ record }: { record: TrackRecord }) {
  const { data: recent } = useEntries({ userId: record.user.id });
  const resolved = recent?.filter((e) => e.claim && e.claim.resolution !== "pending").slice(0, 3) ?? [];
  return (
    <Card data-testid={`rep-${record.user.id}`}>
      <CardHeader
        title={record.user.name}
        subtitle={`${record.user.title} · ${record.entriesResolved} resolved entries`}
        action={record.weak ? <Badge tone="warn">Weak record: entries go to consensus</Badge> : <Badge tone="brand">Reliable</Badge>}
      />
      <CardBody className="flex flex-col gap-4">
        <div className="grid grid-cols-3 gap-3">
          <Metric
            label="Claims confirmed"
            value={record.claimHitRate == null ? "-" : fmtPct(record.claimHitRate, 0)}
            hint={`${record.confirmed} confirmed, ${record.contradicted} contradicted`}
            bar={record.claimHitRate ?? 0}
          />
          <Metric
            label="Bias"
            value={record.biasPct == null ? "-" : `${record.biasPct >= 0 ? "+" : ""}${fmtPct(record.biasPct, 1)}`}
            hint="Average of (entry - actual) / actual"
          />
          <Metric
            label="Actual inside range"
            value={record.rangeCoverage == null ? "-" : fmtPct(record.rangeCoverage, 0)}
            hint="How often the stated range held"
            bar={record.rangeCoverage ?? 0}
          />
        </div>
        {resolved.length > 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-xs font-medium uppercase tracking-wide text-muted">Latest resolved claims</p>
            {resolved.map((e) => (
              <EntryCard key={e.id} entry={e} />
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

export function TrackRecordPage() {
  const { data } = useReps();
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold">Track record</h1>
        <p className="text-sm text-muted">
          Descriptive statistics from resolved claims, not a forecasting model. Shown next to every new entry and used to
          decide what the consensus meeting discusses.
        </p>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">{data?.map((r) => <RepCard key={r.user.id} record={r} />)}</div>
    </div>
  );
}
