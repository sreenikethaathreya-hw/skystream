import { Badge } from "@/components/ui/badge";
import { fmtPct } from "@/lib/format";
import type { DemoUser, SegmentCube } from "@/lib/types";
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
  user,
  users,
  onSelect,
}: {
  segments: SegmentCube[];
  selectedId: number | undefined;
  user: DemoUser | undefined;
  users: DemoUser[];
  onSelect: (id: number) => void;
}) {
  const ordered = [...segments].sort((a, b) => {
    const mineA = a.ownerId === user?.id ? 0 : 1;
    const mineB = b.ownerId === user?.id ? 0 : 1;
    return mineA - mineB || b.context.planQtyKs - a.context.planQtyKs;
  });
  return (
    <div className="flex flex-col gap-1.5">
      <p className="px-1 text-xs font-medium uppercase tracking-wide text-muted">Micro-segments</p>
      {ordered.map((s) => {
        const share = s.context.marketQtyKs ? s.context.planQtyKs / s.context.marketQtyKs : 0;
        const owner = users.find((u) => u.id === s.ownerId);
        const mine = s.ownerId === user?.id;
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
              <Badge tone={mine ? "brand" : "neutral"}>{mine ? "Yours" : owner?.name ?? s.ownerId}</Badge>
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
