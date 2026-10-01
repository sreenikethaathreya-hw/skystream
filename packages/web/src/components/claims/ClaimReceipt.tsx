import { fmtNum, monthName } from "@/lib/format";
import type { Entry } from "@/lib/types";
import { cn } from "@/lib/utils";

const STAMPS: Record<string, string> = {
  confirmed: "-rotate-2 border-brand-600 text-brand-700",
  contradicted: "-rotate-2 border-crit-500 text-crit-700",
  inconclusive: "-rotate-2 border-warn-500 text-warn-700",
  recorded: "-rotate-2 border-brand-600 text-brand-700",
};

/** The claim's outcome, marked like a stamp on a paper receipt. */
export function ClaimStamp({ resolution }: { resolution: string }) {
  return (
    <span
      data-testid="claim-stamp"
      className={cn(
        "inline-block whitespace-nowrap rounded-[3px] border-[1.5px] px-1.5 py-px font-mono text-[10px] font-medium uppercase tracking-[0.12em]",
        STAMPS[resolution] ?? "border-dashed border-line text-muted",
      )}
    >
      {resolution}
    </span>
  );
}

/** What the rep said next to what happened. Pending claims say when they will be checked. */
export function ClaimReceipt({ entry }: { entry: Entry }) {
  const claim = entry.claim;
  if (!claim) return null;
  const detail = claim.resolutionDetail;
  if (!detail) {
    if (claim.resolution !== "pending") return null;
    return (
      <p className="text-xs text-muted">
        Will be checked against {monthName(claim.checkMonth)} {claim.checkYear} {claim.signal.replace(/_/g, " ")}.
      </p>
    );
  }
  return (
    <div
      data-testid="claim-receipt"
      className="flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-md border border-dashed border-ink/20 bg-canvas/60 px-3 py-2 text-xs"
    >
      <ClaimStamp resolution={claim.resolution} />
      <span className="eyebrow">Resolved against actuals</span>
      <span className="tabular">
        Said <span className="font-num text-sm font-semibold">{fmtNum(entry.value)}</span>{" "}
        <span className="text-muted">
          ({fmtNum(entry.low)}–{fmtNum(entry.high)})
        </span>
      </span>
      <span className="tabular">
        Actual <span className="font-num text-sm font-semibold">{fmtNum(detail.actual)}</span>
      </span>
      <span className={detail.inRange ? "text-brand-700" : "text-crit-700"}>
        {detail.inRange ? "inside the range" : "outside the range"}
      </span>
      <span className="tabular text-muted">
        Evidence supports the reason: {Math.round(detail.supportedProbability * 100)}% ({detail.provider})
      </span>
    </div>
  );
}
