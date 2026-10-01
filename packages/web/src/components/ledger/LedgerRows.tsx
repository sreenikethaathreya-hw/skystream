import { AlertTriangle, ChevronDown } from "lucide-react";
import { type ReactNode, useId, useState } from "react";
import { ClaimReceipt, ClaimStamp } from "@/components/claims/ClaimReceipt";
import { ClaimTags } from "@/components/claims/ClaimTags";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { fmtDateTime, fmtKs, fmtNum, fmtPct, monthName } from "@/lib/format";
import type { Entry } from "@/lib/types";
import { cn } from "@/lib/utils";

const COLS = "md:grid md:grid-cols-[minmax(0,1fr)_8rem_6rem_8.5rem_6rem_7.5rem_1rem] md:items-center md:gap-4";

export function LedgerHeader() {
  return (
    <div className={cn("hidden px-4 pb-2", COLS)} aria-hidden="true">
      <span className="eyebrow">Segment and reason</span>
      <span className="eyebrow">Rep</span>
      <span className="eyebrow text-right">Said</span>
      <span className="eyebrow">Range</span>
      <span className="eyebrow text-right">Actual</span>
      <span className="eyebrow">Outcome</span>
      <span />
    </div>
  );
}

export function LedgerRow({ entry, children }: { entry: Entry; children?: ReactNode }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const claim = entry.claim;
  const actual = claim?.resolutionDetail?.actual;
  return (
    <li className="border-t border-line first:border-t-0" data-testid="ledger-row">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={() => setOpen((o) => !o)}
        className={cn("flex w-full flex-col gap-1 px-4 py-2.5 text-left hover:bg-canvas/60", COLS)}
      >
        <span className="min-w-0">
          <span className="flex items-center gap-1.5 text-sm font-medium">
            <span className="truncate">{entry.segmentLabel}</span>
            {entry.flags.length > 0 && (
              <span
                className={cn(
                  "inline-flex shrink-0 items-center gap-0.5 text-[11px]",
                  entry.flags.some((f) => f.severity === "critical") ? "text-crit-700" : "text-warn-700",
                )}
                title={entry.flags.map((f) => f.message).join("\n")}
              >
                <AlertTriangle size={11} aria-hidden="true" />
                {entry.flags.length}
                <span className="sr-only"> flags</span>
              </span>
            )}
          </span>
          <span className="block truncate text-xs text-muted">
            {entry.justification ? `“${entry.justification}”` : "No reason given"}
          </span>
        </span>
        <span className="flex flex-col text-xs">
          <span className="truncate">{entry.userName}</span>
          <StatusBadge status={entry.status} />
        </span>
        <span className="font-num tabular text-lg font-semibold md:text-right">{fmtNum(entry.value)}</span>
        <span className="tabular text-xs text-muted">
          {fmtNum(entry.low)}–{fmtNum(entry.high)}
        </span>
        <span className={cn("font-num tabular md:text-right", actual == null ? "text-muted" : "text-lg font-semibold")}>
          {actual == null ? "·" : fmtNum(actual)}
        </span>
        <span>{claim ? <ClaimStamp resolution={claim.resolution} /> : <span className="text-xs text-muted">no claim</span>}</span>
        <ChevronDown
          size={14}
          aria-hidden="true"
          className={cn("hidden text-muted transition-transform md:block", open && "rotate-180")}
        />
      </button>

      {open && (
        <div id={panelId} className="flex flex-col gap-2 border-t border-dashed border-line bg-canvas/40 px-4 py-3">
          {entry.justification && <p className="break-words text-sm">“{entry.justification}”</p>}
          {claim?.summary && <p className="text-xs text-muted">Reads as: {claim.summary}</p>}
          {entry.flags.map((f) => (
            <p key={f.code} className={cn("text-xs", f.severity === "critical" ? "text-crit-700" : "text-warn-700")}>
              {f.message}
            </p>
          ))}
          {claim && <ClaimTags decisions={claim.decisions} provider={claim.provider} compact />}
          <ClaimReceipt entry={entry} />
          <p className="tabular text-xs text-muted">
            {entry.impact && `Full year ${fmtKs(entry.impact.fyEstimate)} · share ${fmtPct(entry.impact.volumeShare)} · `}
            {entry.price != null && `EUR ${fmtNum(entry.price)}/KS · `}
            Entered {fmtDateTime(entry.createdAt)}
            {entry.source === "history" && (
              <Badge className="ml-2" tone="neutral">
                history
              </Badge>
            )}
          </p>
          {children}
        </div>
      )}
    </li>
  );
}

/** Entries grouped under the month they forecast, newest month first. */
export function groupByMonth(entries: Entry[]) {
  const groups = new Map<number, Entry[]>();
  for (const e of entries) {
    const key = e.year * 100 + e.month;
    const list = groups.get(key);
    if (list) list.push(e);
    else groups.set(key, [e]);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => b - a)
    .map(([key, list]) => ({ key, label: `${monthName(key % 100)} ${Math.floor(key / 100)}`, entries: list }));
}
