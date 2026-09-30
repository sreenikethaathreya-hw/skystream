import { Badge } from "@/components/ui/badge";
import { fmtPct } from "@/lib/format";
import type { SegmentCube } from "@/lib/types";
import { cn } from "@/lib/utils";

const COLOR_DOT: Record<string, string> = {
  RED: "bg-red-500",
  YELLOW: "bg-yellow-400",
  ORANGE: "bg-orange-400",
  GREEN: "bg-green-500",
};

export function SegmentList({
  segments,
  selectedId,
  onSelect,
}: {
  segments: SegmentCube[];
  selectedId: number | undefined;
  onSelect: (id: number) => void;
}) {
  const ordered = [...segments].sort(
    (a, b) => Number(b.editable) - Number(a.editable) || b.context.planQtyKs - a.context.planQtyKs,
  );
  return (
    <div className="flex flex-col gap-1.5">
      <p className="px-1 text-xs font-medium uppercase tracking-wide text-muted">Micro-segments</p>
      {ordered.map((s) => {
        const share = s.context.marketQtyKs ? s.context.planQtyKs / s.context.marketQtyKs : 0;
        return (
          <button
            key={s.id}
            onClick={() => onSelect(s.id)}
            data-testid={`segment-${s.id}`}
            className={cn(
              "rounded-lg border px-3 py-2 text-left transition-colors",
              s.id === selectedId ? "border-brand-500 bg-brand-50" : "border-line bg-surface hover:border-brand-100",
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 text-sm font-medium">
                <span className={cn("size-2 rounded-full", COLOR_DOT[s.color ?? ""] ?? "bg-gray-400")} />
                {s.label}
              </span>
              <span className="tabular text-xs text-muted">{fmtPct(share)}</span>
            </div>
            <div className="mt-1 flex items-center gap-1.5">
              <Badge tone={s.editable ? "brand" : "neutral"}>
                {s.editable ? "Yours" : s.ownerNames.join(", ") || "Unassigned"}
              </Badge>
              <span className="tabular text-[11px] text-muted">
                plan {Math.round(s.context.planQtyKs).toLocaleString("en-US")} KS
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
