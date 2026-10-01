import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { ClaimStamp } from "@/components/claims/ClaimReceipt";
import { fmtKs, fmtNum, monthName } from "@/lib/format";
import type { Entry } from "@/lib/types";

/** Shown in place of a toast after a submit, so the rep sees exactly what entered the ledger. */
export function SubmitReceipt({ entry }: { entry: Entry }) {
  const claim = entry.claim;
  return (
    <div
      role="status"
      data-testid="submit-receipt"
      className="animate-rise flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-dashed border-brand-600/40 bg-surface px-4 py-3"
    >
      <ClaimStamp resolution="recorded" />
      <div className="min-w-0">
        <p className="text-sm font-medium">
          Submitted {fmtKs(entry.value)} for {entry.segmentLabel}, {monthName(entry.month)}
        </p>
        <p className="tabular text-xs text-muted">
          Range {fmtNum(entry.low)}–{fmtNum(entry.high)} ·{" "}
          {claim
            ? `Reason recorded; checked against ${monthName(claim.checkMonth)} ${claim.checkYear} actuals.`
            : "Recorded in the ledger."}
        </p>
      </div>
      <Link
        to={`/ledger?segment=${entry.segmentId}`}
        className="ml-auto inline-flex items-center gap-1 text-sm font-medium text-brand-700 underline-offset-4 hover:underline"
      >
        View in ledger <ArrowRight size={14} aria-hidden="true" />
      </Link>
    </div>
  );
}
