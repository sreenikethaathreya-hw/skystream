import { CheckCircle2 } from "lucide-react";
import { fmtNum, fmtPct, fmtPts } from "@/lib/format";
import type { EntryInput, Flag, Impact } from "@/lib/mathTypes";
import { cn } from "@/lib/utils";

// Reference labels closer than this share of the axis are merged so they never overlap.
const MERGE_WITHIN = 0.16;
const PAD = 0.12;

interface Marker {
  label: string;
  value: number;
}

interface Axis {
  min: number;
  span: number;
}

/** Zooms the axis onto the numbers in play so references and the entry spread across the width. */
function axisFor(values: number[]): Axis {
  const shown = values.filter((v) => v > 0);
  const lo = Math.min(...shown, Infinity);
  const hi = Math.max(...shown, 1);
  const pad = Math.max((hi - Math.min(lo, hi)) * PAD, hi * 0.05);
  const min = Math.max(0, Math.min(lo, hi) - pad);
  return { min, span: hi + pad - min };
}

const ratio = (value: number, axis: Axis) => Math.min(1, Math.max(0, (value - axis.min) / axis.span));
const pct = (value: number, axis: Axis) => `${ratio(value, axis) * 100}%`;

function groupMarkers(markers: Marker[], axis: Axis) {
  const sorted = markers.filter((m) => m.value > 0).sort((a, b) => a.value - b.value);
  const groups: Marker[][] = [];
  for (const m of sorted) {
    const last = groups[groups.length - 1];
    if (last && ratio(m.value, axis) - ratio(last[0].value, axis) < MERGE_WITHIN) last.push(m);
    else groups.push([m]);
  }
  return groups;
}

const shareAxis = (max: number): Axis => ({ min: 0, span: max });

/** Moves an absolutely positioned child along the full axis width with a transform, not `left`. */
function Slider({ at, className, children }: { at: string; className?: string; children: React.ReactNode }) {
  return (
    <div className={cn("pointer-events-none absolute inset-x-0 transition-transform duration-200 ease-out", className)} style={{ transform: `translateX(${at})` }}>
      {children}
    </div>
  );
}

function tone(flags: Flag[]) {
  if (flags.some((f) => f.severity === "critical")) return { mark: "bg-crit-500", band: "bg-crit-500/15", text: "text-crit-700" };
  if (flags.length) return { mark: "bg-warn-500", band: "bg-warn-500/20", text: "text-warn-700" };
  return { mark: "bg-ink", band: "bg-ink/10", text: "text-ink" };
}

export function DemandInstrument({ impact, entry, flags }: { impact: Impact; entry: EntryInput; flags: Flag[] }) {
  const t = tone(flags);
  const markers: Marker[] = [
    { label: "Plan", value: impact.monthExpected },
    { label: "Last year", value: impact.monthLastYear },
    { label: "Avg", value: impact.monthHistoryAvg },
  ];
  const axis = axisFor([entry.low, entry.high, entry.value, ...markers.map((m) => m.value)]);
  const groups = groupMarkers(markers, axis);
  const shares = shareAxis(Math.max(1, impact.volumeShare, impact.maxHistoricalShare));
  const jump = (impact.volumeShare - impact.baselineShare) * 100;
  const ytg = impact.gapToPlan;

  return (
    <div className="flex flex-col gap-5" data-testid="demand-instrument">
      <div className="relative h-16" role="img" aria-label={`Entry ${fmtNum(entry.value)} against plan ${fmtNum(impact.monthExpected)} and last year ${fmtNum(impact.monthLastYear)}`}>
        <div className="absolute inset-x-0 top-10 h-px bg-line" />
        <div
          className={cn("absolute top-8 h-5 rounded-sm transition-colors", t.band)}
          style={{ left: pct(entry.low, axis), width: `calc(${pct(entry.high, axis)} - ${pct(entry.low, axis)})` }}
        />
        {groups.map((g) => {
          const at = g.reduce((s, m) => s + m.value, 0) / g.length;
          const r = ratio(at, axis);
          const align = r < 0.12 ? "translate-x-0" : r > 0.88 ? "-translate-x-full" : "-translate-x-1/2";
          return (
            <div key={g.map((m) => m.label).join("|")} className="absolute inset-y-0" style={{ left: pct(at, axis) }}>
              <div className="absolute top-7 h-7 w-px bg-muted/70" />
              <p className={cn("tabular absolute top-0 whitespace-nowrap font-mono text-[10.5px] text-muted", align)}>
                {g.map((m) => `${m.label} ${fmtNum(m.value)}`).join(" · ")}
              </p>
            </div>
          );
        })}
        <Slider at={pct(entry.value, axis)} className="top-6 h-9">
          <div className={cn("h-9 w-[3px] -translate-x-1/2 rounded-full", t.mark)} />
        </Slider>
      </div>

      <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
        <div className="flex flex-col gap-2">
          <p className="flex flex-wrap items-baseline gap-x-2">
            <span className="eyebrow">Share</span>
            <span className="font-num tabular text-xl text-muted">{fmtPct(impact.baselineShare)}</span>
            <span aria-hidden="true" className="text-muted">→</span>
            <span className={cn("font-num tabular text-3xl font-semibold", t.text)} data-testid="instrument-share">
              {fmtPct(impact.volumeShare)}
            </span>
            <span className="tabular text-xs text-muted">{fmtPts(jump)}</span>
          </p>
          <div className="relative h-1.5 rounded-full bg-line">
            <div
              className="absolute -top-1 h-3.5 w-px bg-muted"
              style={{ left: pct(impact.maxHistoricalShare, shares) }}
              title={`Historical high ${fmtPct(impact.maxHistoricalShare)}`}
            />
            <Slider at={pct(impact.volumeShare, shares)} className="-top-1.5 h-4">
              <div className={cn("h-4 w-[3px] -translate-x-1/2 rounded-full", t.mark)} />
            </Slider>
          </div>
          <p className="tabular text-[11px] text-muted">Tick marks the historical high, {fmtPct(impact.maxHistoricalShare)}</p>
        </div>
        <p className="flex items-baseline gap-2 sm:justify-end">
          <span className="eyebrow">Year to go</span>
          <span className={cn("font-num tabular text-3xl font-semibold", ytg >= 0 ? "text-brand-700" : "text-ink")}>
            {ytg >= 0 ? "+" : "−"}
            {fmtNum(Math.abs(ytg))}
          </span>
          <span className="text-xs text-muted">{ytg >= 0 ? "KS above plan" : "KS short"}</span>
        </p>
      </div>
    </div>
  );
}

/** Every check, right under the number while typing: the most serious first and largest. */
export function Checks({ flags }: { flags: Flag[] }) {
  const ordered = [...flags].sort((a, b) => Number(b.severity === "critical") - Number(a.severity === "critical"));
  const lead = ordered[0];
  const critical = lead?.severity === "critical";
  return (
    <div data-testid="checks">
      <p className="sr-only" aria-live="polite">
        {flags.length ? `${flags.length} check${flags.length > 1 ? "s" : ""} raised, a reason is required` : "No checks raised"}
      </p>
      {!lead ? (
        <p className="flex items-center gap-1.5 text-sm text-brand-700">
          <CheckCircle2 size={15} aria-hidden="true" /> No flags. This number is in line with history.
        </p>
      ) : (
        <div
          key={lead.code}
          className={cn(
            "animate-rise flex flex-col gap-1.5 rounded-md border-l-[3px] px-3 py-2",
            critical ? "border-crit-500 bg-crit-50" : "border-warn-500 bg-warn-50",
          )}
        >
          {ordered.map((f, i) => (
            <p
              key={f.code}
              data-testid={`flag-${f.code}`}
              className={cn(
                i === 0 ? "text-sm" : "text-xs",
                f.severity === "critical" ? "text-crit-700" : "text-warn-700",
              )}
            >
              {f.message}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
