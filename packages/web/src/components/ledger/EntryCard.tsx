import { useEffect, useRef, type ReactNode } from "react";
import { ClaimTags } from "@/components/claims/ClaimTags";
import { EntryNotes } from "@/components/ledger/EntryNotes";
import { cn } from "@/lib/utils";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { fmtKs, fmtNum, fmtPct, monthName } from "@/lib/format";
import { useMoney } from "@/hooks/useMoney";
import { fmtPrice } from "@/lib/money";
import type { Entry } from "@/lib/types";

export function EntryCard({
  entry,
  children,
  highlight = false,
  canNote = false,
  ask,
}: {
  entry: Entry;
  children?: ReactNode;
  highlight?: boolean;
  canNote?: boolean;
  ask?: ReactNode;
}) {
  const money = useMoney();
  const claim = entry.claim;
  const detail = claim?.resolutionDetail;
  const card = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (highlight) card.current?.scrollIntoView?.({ block: "center", behavior: "smooth" });
  }, [highlight]);
  return (
    <Card
      ref={card}
      data-testid="entry-card"
      data-entry-id={entry.id}
      className={cn(highlight && "ring-2 ring-brand-500/60")}
    >
      <CardBody className="flex flex-col gap-2 pt-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold">{entry.segmentLabel}</span>
            <span className="text-sm text-muted">
              {monthName(entry.month)} {entry.year}
            </span>
            <StatusBadge status={entry.status} />
            {entry.source === "history" && <Badge>history</Badge>}
            {entry.source === "ibp" && (
              <Badge tone="info" title={entry.snapshot ? `IBP snapshot ${entry.snapshot}` : undefined}>
                IBP
              </Badge>
            )}
            {claim && <StatusBadge status={claim.resolution} />}
          </div>
          <span className="flex items-center gap-1 text-xs text-muted">
            {entry.userName} · {new Date(entry.createdAt).toLocaleString()}
            {ask}
          </span>
        </div>

        <div className="tabular flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm">
          <span className="text-lg font-semibold">{fmtKs(entry.value)}</span>
          <span className="text-muted">
            range {fmtNum(entry.low)} to {fmtNum(entry.high)}
          </span>
          {entry.price != null && <span className="text-muted">{fmtPrice(entry.price, money)}</span>}
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
        {entry.source !== "history" && (
          <EntryNotes entryId={entry.id} notes={entry.notes ?? []} canWrite={canNote} />
        )}
        {children}
      </CardBody>
    </Card>
  );
}
