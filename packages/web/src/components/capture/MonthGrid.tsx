import { MONTHS, fmtNum } from "@/lib/format";
import type { SegmentCube } from "@/lib/types";
import { cn } from "@/lib/utils";

export function MonthGrid({
  segment,
  selectedMonth,
  draftValue,
  onSelect,
}: {
  segment: SegmentCube;
  selectedMonth: number;
  draftValue: number;
  onSelect: (month: number) => void;
}) {
  const ctx = segment.context;
  const entries = new Map(segment.latestEntries.map((e) => [e.month, e]));
  const rows: { label: string; value: (m: number) => number | null; className?: string }[] = [
    { label: "Plan", value: (m) => ctx.monthlyPlan[m - 1] },
    { label: `Last year`, value: (m) => ctx.lastYearMonthly[m - 1], className: "text-muted" },
    { label: "Actual", value: (m) => ctx.monthlyActual[m - 1] },
    {
      label: "Demand",
      value: (m) => (m === selectedMonth ? draftValue : (entries.get(m)?.value ?? null)),
      className: "font-semibold",
    },
  ];

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-separate border-spacing-0 text-xs">
        <thead>
          <tr>
            <th className="w-20">
              <span className="sr-only">Row</span>
            </th>
            {MONTHS.map((name, i) => {
              const m = i + 1;
              const open = m >= ctx.clockMonth;
              return (
                <th key={name} className="px-0.5 pb-1">
                  <button
                    disabled={!open}
                    aria-pressed={m === selectedMonth}
                    onClick={() => onSelect(m)}
                    data-testid={`month-${m}`}
                    className={cn(
                      "w-full rounded-md py-1 text-xs font-medium",
                      m === selectedMonth && "bg-ink text-white",
                      m !== selectedMonth && open && "text-ink hover:bg-canvas",
                      !open && "cursor-default text-muted/60",
                    )}
                  >
                    {name}
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <td className="py-1 pr-2 text-muted">{row.label}</td>
              {MONTHS.map((_, i) => {
                const m = i + 1;
                const value = row.value(m);
                const closed = m < ctx.clockMonth;
                return (
                  <td
                    key={m}
                    className={cn(
                      "tabular px-1 py-1 text-right",
                      closed && "bg-canvas",
                      m === selectedMonth && "bg-ink/[0.06]",
                      row.className,
                    )}
                  >
                    {value === null ? "·" : fmtNum(value)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
