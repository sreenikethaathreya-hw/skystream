import { useEffect, useRef, type ReactNode } from "react";
import { ClaimReceipt } from "@/components/claims/ClaimReceipt";
import { ClaimTags } from "@/components/claims/ClaimTags";
import { EntryNotes } from "@/components/ledger/EntryNotes";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { useMoney } from "@/hooks/useMoney";
import { fmtDateTime, fmtKs, fmtNum, fmtPct, monthName } from "@/lib/format";
import { fmtPrice } from "@/lib/money";
import type { Entry } from "@/lib/types";
import { cn } from "@/lib/utils";

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
  const card = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (highlight) card.current?.scrollIntoView?.({ block: "center", behavior: "smooth" });
  }, [highlight]);
  return (
    <div ref={card}>
      <Card data-testid="entry-card" data-entry-id={entry.id} className={cn(highlight && "ring-2 ring-brand-500/60")}>
        <CardBody className="flex flex-col gap-2 pt-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
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
            </div>
            <span className="flex items-center gap-1 text-xs text-muted">
              {entry.userName} · {fmtDateTime(entry.createdAt)}
              {ask}
            </span>
          </div>

          <div className="tabular flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm">
            <span className="font-num tabular text-lg font-semibold">{fmtKs(entry.value)}</span>
            <span className="text-muted">
              range {fmtNum(entry.low)}–{fmtNum(entry.high)}
            </span>
            {entry.price != null && <span className="text-muted">{fmtPrice(entry.price, money)}</span>}
            {entry.impact && (
              <span className="text-muted">
                full year {fmtKs(entry.impact.fyEstimate)} · share {fmtPct(entry.impact.volumeShare)}
              </span>
            )}
          </div>

          {entry.justification && <p className="break-words text-sm">“{entry.justification}”</p>}
          {claim?.summary && <p className="text-xs text-muted">Reads as: {claim.summary}</p>}

          {(entry.flags.length > 0 || (claim && Object.keys(claim.decisions).length > 0)) && (
            <div className="flex flex-wrap gap-1.5">
              {entry.flags.map((f) => (
                <Badge key={f.code} tone={f.severity === "critical" ? "crit" : "warn"} title={f.message}>
                  {f.code.replace(/_/g, " ")}
                </Badge>
              ))}
              {claim && <ClaimTags decisions={claim.decisions} provider={claim.provider} compact />}
            </div>
          )}

          <ClaimReceipt entry={entry} />
          {entry.source !== "history" && <EntryNotes entryId={entry.id} notes={entry.notes ?? []} canWrite={canNote} />}
          {children}
        </CardBody>
      </Card>
    </div>
  );
}
