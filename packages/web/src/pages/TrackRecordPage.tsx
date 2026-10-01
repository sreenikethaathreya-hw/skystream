import { AskButton } from "@/components/chat/AskButton";
import { EntryCard } from "@/components/ledger/EntryCard";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { ProbBar } from "@/components/ui/prob-bar";
import { useEntries, useReps } from "@/hooks/queries";
import { usePageContext } from "@/hooks/useChat";
import { useSession } from "@/hooks/useSession";
import { fmtPct } from "@/lib/format";
import type { TrackRecord } from "@/lib/types";

function Metric({ label, value, hint, bar }: { label: string; value: string; hint: string; bar?: number }) {
  return (
    <div className="rounded-lg bg-canvas p-3">
      <p className="text-xs text-muted">{label}</p>
      <p className="font-num tabular text-2xl font-semibold">{value}</p>
      {bar !== undefined && <ProbBar value={bar} tone="brand" className="mt-1" />}
      <p className="mt-1 text-[11px] text-muted">{hint}</p>
    </div>
  );
}

function RepCard({ record, mine, askable }: { record: TrackRecord; mine: boolean; askable: boolean }) {
  const { data: recent } = useEntries({ userId: record.user.id });
  const resolved = recent?.filter((e) => e.claim && e.claim.resolution !== "pending").slice(0, 3) ?? [];
  return (
    <Card data-testid={`rep-${record.user.id}`}>
      <CardHeader
        title={record.user.name}
        subtitle={`${record.user.title} · ${record.entriesResolved} resolved entries`}
        action={
          <span className="flex items-center gap-1">
            {askable && (
              <AskButton
                question={
                  mine
                    ? "How have my last months gone: bias, range coverage and claims by month?"
                    : `How has ${record.user.name}'s accuracy changed by month?`
                }
                context={{ page: "reps" }}
              />
            )}
            {record.weak ? <Badge tone="warn">Weak record: entries go to consensus</Badge> : <Badge tone="brand">Reliable</Badge>}
          </span>
        }
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
            <p className="eyebrow">Latest resolved claims</p>
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
  const { user } = useSession();
  usePageContext({ page: "reps" });
  const canAsk = (id: string) => user?.role !== "rep" || user.id === id;
  return (
    <div className="flex flex-col gap-4">
      <PageHeader eyebrow="Accountability" title="Track record">
        Descriptive statistics from resolved claims, not a forecasting model. Shown next to every new entry and used to
        decide what the consensus meeting discusses.
      </PageHeader>
      <div className="grid gap-4 xl:grid-cols-2">
        {data?.map((r) => (
          <RepCard key={r.user.id} record={r} mine={user?.id === r.user.id} askable={canAsk(r.user.id)} />
        ))}
      </div>
    </div>
  );
}
