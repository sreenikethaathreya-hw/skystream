import { SERIES, monthPoints, type MonthPoint } from "@/components/capture/MonthChart";
import { MONTHS, fmtNum } from "@/lib/format";
import type { SegmentCube } from "@/lib/types";
import { cn } from "@/lib/utils";

type SeriesKey = keyof typeof SERIES;

const ROWS: { key: SeriesKey; mark: "bar" | "line"; strong?: boolean; hint: string }[] = [
  { key: "plan", mark: "line", hint: "Monthly plan" },
  { key: "lastYear", mark: "line", hint: "Same month last year" },
  { key: "actual", mark: "bar", hint: "Sold, closed months" },
  { key: "demand", mark: "bar", strong: true, hint: "Rep's number" },
];

function value(point: MonthPoint, key: SeriesKey): number | null {
  return point[key];
}

function vsPlan(point: MonthPoint): number | null {
  return point.demand !== null && point.plan ? ((point.demand - point.plan) / point.plan) * 100 : null;
}

function signed(pct: number): string {
  if (Math.abs(pct) < 0.5) return "on plan";
  return `${pct > 0 ? "+" : ""}${pct.toFixed(0)}%`;
}

function total(points: MonthPoint[], key: SeriesKey): number | null {
  const values = points.map((p) => value(p, key)).filter((v): v is number => v !== null);
  return values.length ? values.reduce((a, b) => a + b, 0) : null;
}

/**
 * The exact figures behind the chart: closed months carry actuals, open months take the rep's number.
 * Month headers select the month to enter; the selected column is lifted, and a total column closes each row.
 */
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
  const points = monthPoints(segment, selectedMonth, draftValue);
  const clockMonth = segment.context.clockMonth;
  const closedCount = Math.min(12, Math.max(0, clockMonth - 1));
  const openCount = 12 - closedCount;

  const columnClass = (p: MonthPoint) =>
    cn(
      "px-2 text-right",
      !p.open && "bg-canvas/70",
      p.month === selectedMonth && "bg-ink/[0.06]",
      p.open && p.month !== selectedMonth && "cursor-pointer hover:bg-canvas",
    );

  return (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full min-w-[860px] border-separate border-spacing-0 text-xs">
        <thead>
          <tr className="text-[10px] uppercase tracking-wide text-muted">
            <th className="sticky left-0 z-10 bg-surface" />
            {closedCount > 0 && (
              <th colSpan={closedCount} className="border-b border-line bg-canvas/70 px-2 py-1.5 text-left font-medium">
                Closed · actuals in
              </th>
            )}
            {openCount > 0 && (
              <th colSpan={openCount} className="border-b border-line px-2 py-1.5 text-left font-medium">
                Open · enter demand
              </th>
            )}
            <th className="border-b border-l border-line px-3 py-1.5 text-right font-medium">Total</th>
          </tr>
          <tr>
            <th className="sticky left-0 z-10 w-36 border-b border-line bg-surface px-3 py-2 text-left">
              <span className="sr-only">Series</span>
            </th>
            {points.map((p) => {
              const isSelected = p.month === selectedMonth;
              return (
                <th key={p.month} className={cn("border-b border-line py-1.5", columnClass(p))}>
                  <button
                    type="button"
                    disabled={!p.open}
                    aria-pressed={isSelected}
                    onClick={() => onSelect(p.month)}
                    data-testid={`month-${p.month}`}
                    className={cn(
                      "w-full rounded-md px-1 py-1 text-xs font-medium",
                      isSelected && "bg-ink text-white",
                      !isSelected && p.open && "text-ink hover:bg-surface",
                      !p.open && "cursor-default text-muted/70",
                      p.month === clockMonth && !isSelected && "ring-1 ring-ink/30",
                    )}
                  >
                    {MONTHS[p.month - 1]}
                  </button>
                </th>
              );
            })}
            <th className="border-b border-l border-line px-3 py-1.5 text-right text-[11px] font-medium text-muted">KS</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => {
            const fy = total(points, row.key);
            return (
              <tr key={row.key} className="group/row">
                <th
                  scope="row"
                  className="sticky left-0 z-10 border-b border-line/70 bg-surface px-3 py-2 text-left font-normal"
                >
                  <span className="flex items-center gap-2">
                    {row.mark === "bar" ? (
                      <span className="size-2.5 rounded-[3px]" style={{ background: SERIES[row.key].color }} aria-hidden="true" />
                    ) : (
                      <span className="h-0.5 w-2.5 rounded-full" style={{ background: SERIES[row.key].color }} aria-hidden="true" />
                    )}
                    <span className={cn("text-ink", row.strong && "font-semibold")}>{SERIES[row.key].label}</span>
                  </span>
                  <span className="mt-0.5 block pl-[18px] text-[10px] text-muted">{row.hint}</span>
                </th>
                {points.map((p) => {
                  const v = value(p, row.key);
                  return (
                    <td
                      key={p.month}
                      onClick={p.open ? () => onSelect(p.month) : undefined}
                      className={cn(
                        "tabular border-b border-line/70 py-2",
                        columnClass(p),
                        row.strong ? "font-semibold text-ink" : row.key === "lastYear" ? "text-muted" : "text-ink",
                        row.strong && p.month === selectedMonth && "text-[13px]",
                      )}
                    >
                      {v === null ? <span className="text-muted/50">–</span> : fmtNum(v)}
                    </td>
                  );
                })}
                <td
                  className={cn(
                    "tabular border-b border-l border-line/70 px-3 py-2 text-right",
                    row.strong ? "font-semibold text-ink" : "text-muted",
                  )}
                >
                  {fy === null ? "–" : fmtNum(fy)}
                </td>
              </tr>
            );
          })}
          <tr>
            <th scope="row" className="sticky left-0 z-10 bg-surface px-3 py-2 text-left font-normal text-muted">
              Demand vs plan
            </th>
            {points.map((p) => {
              const pct = vsPlan(p);
              const far = pct !== null && Math.abs(pct) >= 20;
              return (
                <td
                  key={p.month}
                  onClick={p.open ? () => onSelect(p.month) : undefined}
                  className={cn("tabular py-2 text-[11px]", columnClass(p), far ? "font-semibold text-ink" : "text-muted")}
                  data-testid={`vs-plan-${p.month}`}
                >
                  {pct === null ? "" : signed(pct)}
                </td>
              );
            })}
            <td className="border-l border-line/70 px-3 py-2" />
          </tr>
        </tbody>
      </table>
    </div>
  );
}
