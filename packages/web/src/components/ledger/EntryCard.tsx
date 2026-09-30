import type { ReactNode } from "react";
import { ClaimTags } from "@/components/claims/ClaimTags";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { fmtKs, fmtNum, fmtPct, monthName } from "@/lib/format";
import type { Entry } from "@/lib/types";

export function EntryCard({ entry, children }: { entry: Entry; children?: ReactNode }) {
  const claim = entry.claim;
  const detail = claim?.resolutionDetail;
  return (
    <Card data-testid="entry-card">
      <CardBody className="flex flex-col gap-2 pt-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold">{entry.segmentLabel}</span>
            <span className="text-sm text-muted">
              {monthName(entry.month)} {entry.year}
            </span>
            <StatusBadge status={entry.status} />
            {entry.source === "history" && <Badge>history</Badge>}
            {claim && <StatusBadge status={claim.resolution} />}
          </div>
          <span className="text-xs text-muted">
            {entry.userName} · {new Date(entry.createdAt).toLocaleString()}
          </span>
        </div>

        <div className="tabular flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm">
          <span className="text-lg font-semibold">{fmtKs(entry.value)}</span>
          <span className="text-muted">
            range {fmtNum(entry.low)} to {fmtNum(entry.high)}
          </span>
          {entry.price != null && <span className="text-muted">EUR {fmtNum(entry.price)}/KS</span>}
          {entry.impact && (
            <span className="text-muted">
              full year {fmtKs(entry.impact.fyEstimate)} · share {fmtPct(entry.impact.volumeShare)}
            </span>
          )}
        </div>

        {entry.justification && <p className="text-sm">"{entry.justification}"</p>}
        {claim?.summary && <p className="text-xs text-muted">Claim: {claim.summary}</p>}

        {entry.flags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {entry.flags.map((f) => (
              <Badge key={f.code} tone={f.severity === "critical" ? "crit" : "warn"} title={f.message}>
                {f.code.replace(/_/g, " ")}
              </Badge>
            ))}
          </div>
        )}

        {claim && Object.keys(claim.decisions).length > 0 && (
          <ClaimTags decisions={claim.decisions} provider={claim.provider} compact />
        )}

        {detail && (
          <p className="tabular rounded-lg bg-canvas px-3 py-2 text-xs">
            Resolved against actuals: {fmtKs(detail.actual)} vs plan {fmtKs(detail.plan)}.{" "}
            {detail.inRange ? "Actual fell inside the range." : "Actual fell outside the range."} Evidence supports the
            claim with {Math.round(detail.supportedProbability * 100)}% probability ({detail.provider}).
          </p>
        )}
        {claim && !detail && claim.resolution === "pending" && (
          <p className="text-xs text-muted">
            Will be checked against {monthName(claim.checkMonth)} {claim.checkYear} {claim.signal.replace(/_/g, " ")}.
          </p>
        )}
        {children}
      </CardBody>
    </Card>
  );
}
