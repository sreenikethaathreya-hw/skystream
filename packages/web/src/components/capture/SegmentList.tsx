import { memo, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { fmtNum, fmtPct } from "@/lib/format";
import type { SegmentCube } from "@/lib/types";
import { cn } from "@/lib/utils";

const COLOR_DOT: Record<string, string> = {
  RED: "bg-red-500",
  YELLOW: "bg-yellow-400",
  ORANGE: "bg-orange-400",
  GREEN: "bg-green-500",
};

export const SegmentList = memo(function SegmentList({
  segments,
  selectedId,
  onSelect,
}: {
  segments: SegmentCube[];
  selectedId: number | undefined;
  onSelect: (id: number) => void;
}) {
  const ordered = useMemo(
    () =>
      [...segments].sort(
        (a, b) => Number(b.editable) - Number(a.editable) || b.context.planQtyKs - a.context.planQtyKs,
      ),
    [segments],
  );
  return (
    <nav aria-labelledby="segment-list-title" className="flex flex-col gap-1.5">
      <h2 id="segment-list-title" className="px-1 eyebrow">
        Micro-segments
      </h2>
      {ordered.map((s) => {
        const share = s.context.marketQtyKs ? s.context.planQtyKs / s.context.marketQtyKs : 0;
        const selected = s.id === selectedId;
        return (
          <button
            key={s.id}
            onClick={() => onSelect(s.id)}
            aria-pressed={selected}
            data-testid={`segment-${s.id}`}
            className={cn(
              "rounded-lg border px-3 py-2 text-left transition-colors",
              selected ? "border-brand-500 bg-brand-50" : "border-line bg-surface hover:border-brand-100",
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="flex min-w-0 items-center gap-2 text-sm font-medium">
                <span
                  aria-hidden="true"
                  className={cn("size-2 shrink-0 rounded-full", COLOR_DOT[s.color ?? ""] ?? "bg-gray-400")}
                />
                <span className="break-words">{s.label}</span>
              </span>
              <span className="tabular text-xs text-muted">{fmtPct(share)}</span>
            </div>
            <div className="mt-1 flex items-center gap-1.5">
              <Badge tone={s.editable ? "brand" : "neutral"}>
                {s.editable ? "Yours" : s.ownerNames.join(", ") || "Unassigned"}
              </Badge>
              <span className="tabular text-[11px] text-muted">plan {fmtNum(s.context.planQtyKs)} KS</span>
            </div>
          </button>
        );
      })}
    </nav>
  );
});
