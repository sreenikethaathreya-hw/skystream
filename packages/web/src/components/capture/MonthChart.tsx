import { useEffect, useId, useRef, useState } from "react";
import { MONTHS, fmtNum } from "@/lib/format";
import type { SegmentCube } from "@/lib/types";
import { cn } from "@/lib/utils";

// Validated with the dataviz palette checker (lightness, chroma, CVD and normal-vision separation pass).
// Demand sits under 3:1 against the surface, so it always carries a legend, a cap label and the table view.
export const SERIES = {
  actual: { label: "Actual", color: "#1f7a41" },
  demand: { label: "Demand", color: "#4fbf6f" },
  plan: { label: "Plan", color: "#3470c9" },
  lastYear: { label: "Last year", color: "#c2799b" },
} as const;

const HEIGHT = 232;
const PAD = { top: 22, right: 8, bottom: 30, left: 48 };
const GRID = "#e4e8e1";

export interface MonthPoint {
  month: number;
  plan: number;
  lastYear: number;
  actual: number | null;
  demand: number | null;
  open: boolean;
}

export function monthPoints(segment: SegmentCube, selectedMonth: number, draftValue: number): MonthPoint[] {
  const ctx = segment.context;
  const entries = new Map(segment.latestEntries.map((e) => [e.month, e]));
  return MONTHS.map((_, i) => {
    const m = i + 1;
    return {
      month: m,
      plan: ctx.monthlyPlan[i] ?? 0,
      lastYear: ctx.lastYearMonthly[i] ?? 0,
      actual: ctx.monthlyActual[i] ?? null,
      demand: m === selectedMonth ? draftValue : (entries.get(m)?.value ?? null),
      open: m >= ctx.clockMonth,
    };
  });
}

/** Rounds the axis top up to 1, 2, 2.5 or 5 times a power of ten, so ticks land on clean numbers. */
export function niceMax(value: number): number {
  if (value <= 0) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((s) => s * power >= value) ?? 10;
  return step * power;
}

function compact(value: number): string {
  if (value >= 1000) return `${fmtNum(value / 1000)}k`;
  return fmtNum(value);
}

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(760);
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(320, entry.contentRect.width)));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return { ref, width };
}

function Legend() {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted" aria-label="Legend">
      {(["actual", "demand"] as const).map((key) => (
        <li key={key} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-[3px]" style={{ background: SERIES[key].color }} aria-hidden="true" />
          {SERIES[key].label}
        </li>
      ))}
      {(["plan", "lastYear"] as const).map((key) => (
        <li key={key} className="flex items-center gap-1.5">
          <span className="h-0.5 w-3.5 rounded-full" style={{ background: SERIES[key].color }} aria-hidden="true" />
          {SERIES[key].label}
        </li>
      ))}
    </ul>
  );
}

/** Sits beside the hovered column (flipping left near the right edge) so it never covers the column it describes. */
function Tooltip({ point, left }: { point: MonthPoint; left: number }) {
  const rows: [keyof typeof SERIES, number | null][] = [
    ["plan", point.plan],
    ["lastYear", point.lastYear],
    ["actual", point.actual],
    ["demand", point.demand],
  ];
  const vsPlan = point.demand !== null && point.plan ? ((point.demand - point.plan) / point.plan) * 100 : null;
  return (
    <div
      role="presentation"
      className="pointer-events-none absolute top-2 z-10 w-44 rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg"
      style={{ left }}
    >
      <p className="mb-1 font-semibold text-ink">
        {MONTHS[point.month - 1]} {point.open ? "· open" : "· closed"}
      </p>
      {rows.map(([key, value]) => (
        <p key={key} className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-muted">
            <span className="size-2 rounded-full" style={{ background: SERIES[key].color }} aria-hidden="true" />
            {SERIES[key].label}
          </span>
          <span className="tabular font-medium text-ink">{value === null ? "–" : fmtNum(value)}</span>
        </p>
      ))}
      {vsPlan !== null && (
        <p className="mt-1 border-t border-line pt-1 text-muted">
          Demand vs plan{" "}
          <span className="tabular font-medium text-ink">
            {vsPlan >= 0 ? "+" : ""}
            {vsPlan.toFixed(1)}%
          </span>
        </p>
      )}
    </div>
  );
}

/**
 * Plan and last year as reference lines, actuals for closed months and demand for open ones as columns.
 * Every open month is a button that selects it; the selected month's column follows the number as it is typed.
 */
export function MonthChart({
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
  const { ref, width } = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const describe = useId();
  const points = monthPoints(segment, selectedMonth, draftValue);
  const clockMonth = segment.context.clockMonth;

  const plotW = width - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const band = plotW / 12;
  const barW = Math.min(24, band * 0.42);
  const top = niceMax(
    Math.max(...points.flatMap((p) => [p.plan, p.lastYear, p.actual ?? 0, p.demand ?? 0])) * 1.08,
  );
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * top);
  const x = (m: number) => PAD.left + band * (m - 0.5);
  const y = (v: number) => PAD.top + plotH - (v / top) * plotH;
  const line = (key: "plan" | "lastYear") =>
    points.map((p, i) => `${i ? "L" : "M"}${x(p.month).toFixed(1)},${y(p[key]).toFixed(1)}`).join(" ");

  // A column with a 4px rounded data end and a square base.
  const column = (m: number, value: number) => {
    const h = Math.max(0, y(0) - y(value));
    const r = Math.min(4, h, barW / 2);
    const left = x(m) - barW / 2;
    const base = y(0);
    return `M${left},${base} V${base - h + r} Q${left},${base - h} ${left + r},${base - h} H${left + barW - r} Q${left + barW},${base - h} ${left + barW},${base - h + r} V${base} Z`;
  };

  const selected = points[selectedMonth - 1];
  const selectedVsPlan =
    selected.demand !== null && selected.plan ? ((selected.demand - selected.plan) / selected.plan) * 100 : null;
  const hovered = hover ? points[hover - 1] : null;
  const closedEdge = clockMonth > 1 && clockMonth <= 12 ? PAD.left + band * (clockMonth - 1) : null;

  return (
    <div className="flex flex-col gap-2">
      <Legend />
      <div ref={ref} className="relative w-full select-none" onMouseLeave={() => setHover(null)}>
        <svg width={width} height={HEIGHT} role="img" aria-labelledby={describe} className="block overflow-visible">
          <title id={describe}>
            Monthly plan, last year, actuals and demand. {MONTHS[selectedMonth - 1]} demand{" "}
            {selected.demand === null ? "not entered" : fmtNum(selected.demand)} against a plan of {fmtNum(selected.plan)}.
          </title>

          {closedEdge !== null && (
            <rect x={PAD.left} y={PAD.top} width={closedEdge - PAD.left} height={plotH} fill="#f3f5f1" />
          )}
          <rect
            x={x(selectedMonth) - band / 2 + 2}
            y={PAD.top - 14}
            width={band - 4}
            height={plotH + 14}
            rx={6}
            fill="#16211a"
            fillOpacity={0.05}
          />

          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke={GRID} strokeWidth={1} />
              <text x={PAD.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="tabular fill-muted text-[10px]">
                {compact(t)}
              </text>
            </g>
          ))}

          {points.map((p) => {
            const value = p.open ? p.demand : p.actual;
            if (value === null || value <= 0) return null;
            const isSelected = p.month === selectedMonth;
            return (
              <path
                key={p.month}
                d={column(p.month, value)}
                fill={p.open ? SERIES.demand.color : SERIES.actual.color}
                fillOpacity={hover && hover !== p.month && !isSelected ? 0.55 : 1}
                className="transition-[fill-opacity] duration-150"
                data-testid={`month-bar-${p.month}`}
              />
            );
          })}

          <path d={line("lastYear")} fill="none" stroke={SERIES.lastYear.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          <path d={line("plan")} fill="none" stroke={SERIES.plan.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          {points.map((p) => (
            <circle
              key={p.month}
              cx={x(p.month)}
              cy={y(p.plan)}
              r={p.month === selectedMonth || p.month === hover ? 4.5 : 3}
              fill={SERIES.plan.color}
              stroke="#ffffff"
              strokeWidth={2}
            />
          ))}

          {selected.demand !== null && (
            <text
              x={x(selectedMonth)}
              y={Math.min(y(selected.demand), y(selected.plan)) - (selectedVsPlan === null ? 9 : 22)}
              textAnchor="middle"
              className="tabular fill-ink text-[11px] font-semibold"
              data-testid="selected-demand-label"
            >
              {fmtNum(selected.demand)}
              {selectedVsPlan !== null && (
                <tspan x={x(selectedMonth)} dy="1.2em" className="fill-muted text-[10px] font-medium">
                  {Math.abs(selectedVsPlan) < 0.5
                    ? "on plan"
                    : `${selectedVsPlan > 0 ? "+" : ""}${selectedVsPlan.toFixed(0)}% vs plan`}
                </tspan>
              )}
            </text>
          )}
        </svg>

        {/* Month buttons: the whole column is the hit target; closed months show values but cannot be selected. */}
        <div className="absolute inset-y-0 flex" style={{ left: PAD.left, width: plotW }}>
          {points.map((p) => {
            const isSelected = p.month === selectedMonth;
            return (
              <button
                key={p.month}
                type="button"
                // aria-disabled, not disabled: browsers fire no hover on disabled buttons, and closed months
                // still show their tooltip.
                aria-disabled={!p.open}
                aria-pressed={isSelected}
                aria-describedby={`${describe}-m${p.month}`}
                onClick={() => p.open && onSelect(p.month)}
                onMouseEnter={() => setHover(p.month)}
                onFocus={() => setHover(p.month)}
                onBlur={() => setHover(null)}
                data-testid={`month-${p.month}`}
                className={cn(
                  "group relative flex h-full flex-1 flex-col justify-end rounded-md pb-1.5 outline-offset-[-2px]",
                  p.open ? "cursor-pointer" : "cursor-default",
                )}
              >
                <span
                  className={cn(
                    "mx-auto rounded-md px-2 py-0.5 text-[11px] font-medium",
                    isSelected && "bg-ink text-white",
                    !isSelected && p.open && "text-ink group-hover:bg-canvas",
                    !p.open && "text-muted/70",
                    p.month === clockMonth && !isSelected && "ring-1 ring-ink/30",
                  )}
                >
                  {MONTHS[p.month - 1]}
                </span>
              </button>
            );
          })}
        </div>
        {/* Outside the buttons so each one's name stays just the month. */}
        {points.map((p) => (
          <span key={p.month} id={`${describe}-m${p.month}`} className="sr-only">
            Plan {fmtNum(p.plan)}, last year {fmtNum(p.lastYear)}
            {p.actual !== null ? `, actual ${fmtNum(p.actual)}` : ""}
            {p.demand !== null ? `, demand ${fmtNum(p.demand)}` : ""}
          </span>
        ))}

        {hovered && (
          <Tooltip
            point={hovered}
            left={
              x(hovered.month) + band / 2 + 184 <= width
                ? x(hovered.month) + band / 2
                : x(hovered.month) - band / 2 - 176
            }
          />
        )}
      </div>
    </div>
  );
}
