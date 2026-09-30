import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { useReps } from "@/hooks/queries";
import { fmtPct } from "@/lib/format";

export function TrackRecordInline({ userId }: { userId: string }) {
  const { data } = useReps();
  const record = data?.find((r) => r.user.id === userId);
  if (!record) return null;
  return (
    <Card data-testid="track-record-inline">
      <CardHeader
        title="Your track record"
        subtitle={`${record.entriesResolved} resolved entries`}
        action={record.weak ? <Badge tone="warn">Needs support</Badge> : <Badge tone="brand">Reliable</Badge>}
      />
      <CardBody className="tabular grid grid-cols-3 gap-2 text-center text-xs">
        <div>
          <p className="text-lg font-semibold">{record.claimHitRate == null ? "-" : fmtPct(record.claimHitRate, 0)}</p>
          <p className="text-muted">claims right</p>
        </div>
        <div>
          <p className="text-lg font-semibold">
            {record.biasPct == null ? "-" : `${record.biasPct >= 0 ? "+" : ""}${fmtPct(record.biasPct, 0)}`}
          </p>
          <p className="text-muted">bias</p>
        </div>
        <div>
          <p className="text-lg font-semibold">{record.rangeCoverage == null ? "-" : fmtPct(record.rangeCoverage, 0)}</p>
          <p className="text-muted">in range</p>
        </div>
      </CardBody>
    </Card>
  );
}
