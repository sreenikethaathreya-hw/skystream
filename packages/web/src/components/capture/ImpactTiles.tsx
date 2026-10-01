import { AlertTriangle, CheckCircle2, Map as MapIcon, PieChart, Target } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { fmtKs, fmtNum, fmtPct, fmtPts } from "@/lib/format";
import type { Flag, Impact } from "@/lib/mathTypes";
import { cn } from "@/lib/utils";

function Delta({ value, suffix }: { value: number; suffix: string }) {
  return (
    <span className="tabular text-xs font-medium text-ink">
      {value >= 0 ? "+" : ""}
      {value.toFixed(1)}
      {suffix}
    </span>
  );
}

export function ShareTile({ impact, megaName = "Mega-segment" }: { impact: Impact; megaName?: string }) {
  const movers = [...impact.competitors].sort((a, b) => a.deltaPts - b.deltaPts).slice(0, 3);
  return (
    <Card data-testid="tile-share">
      <CardHeader title="Market share" subtitle="Full-year volume share of the micro-segment" icon={<PieChart size={15} />} />
      <CardBody>
        <p className="font-num tabular text-2xl font-semibold" data-testid="share-value">
          {fmtPct(impact.volumeShare)}
        </p>
        <p className="tabular mt-0.5 text-xs text-muted">
          range {fmtPct(impact.volumeShareLow)} to {fmtPct(impact.volumeShareHigh)}
        </p>
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
          <span>
            vs plan <Delta value={(impact.volumeShare - impact.planVolumeShare) * 100} suffix=" pts" />
          </span>
          <span>
            vs last year <Delta value={(impact.volumeShare - impact.lastYearVolumeShare) * 100} suffix=" pts" />
          </span>
          <span>value share {fmtPct(impact.valueShare)}</span>
        </div>
        <div className="mt-3 border-t border-line pt-2">
          <p className="eyebrow">
            {megaName} value share {fmtPct(impact.megaShare)} ({fmtPts((impact.megaShare - impact.megaShareBaseline) * 100)})
          </p>
          {impact.megaShare > 1 && (
            <p className="mt-1 text-xs text-crit-700" data-testid="mega-overflow">
              Syngenta would exceed the whole {megaName} market; competitor shares stop at 0%.
            </p>
          )}
          {movers.map((c) => (
            <div key={c.name} className="mt-1 flex items-center justify-between text-xs">
              <span>{c.name}</span>
              <span className="tabular text-muted">
                {c.newPct.toFixed(1)}% <Delta value={c.deltaPts} suffix=" pts" />
              </span>
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}

export function YtgTile({ impact }: { impact: Impact }) {
  const gap = impact.gapToPlan;
  return (
    <Card data-testid="tile-ytg">
      <CardHeader title="Year to go" subtitle={`${impact.monthsRemaining} open months`} icon={<Target size={15} />} />
      <CardBody>
        <p className={cn("font-num tabular text-2xl font-semibold", gap >= 0 && "text-brand-700")} data-testid="ytg-gap">
          {gap >= 0 ? "+" : "-"}
          {fmtNum(Math.abs(gap))}
        </p>
        <p className="text-xs text-muted">{gap >= 0 ? "KS above plan" : "KS short of plan"}</p>
        <dl className="tabular mt-2 grid grid-cols-2 gap-x-2 gap-y-1 text-xs">
          <dt className="text-muted">Full year</dt>
          <dd className="text-right">{fmtKs(impact.fyEstimate)}</dd>
          <dt className="text-muted">Plan</dt>
          <dd className="text-right">{fmtKs(impact.planFy)}</dd>
          <dt className="text-muted">Actuals to date</dt>
          <dd className="text-right">{fmtKs(impact.actualsToDate)}</dd>
          <dt className="text-muted">Needed / month</dt>
          <dd className="text-right">{fmtNum(impact.requiredMonthlyRate)}</dd>
          <dt className="text-muted">Entered / month</dt>
          <dd className="text-right font-medium">{fmtNum(impact.enteredMonthlyRate)}</dd>
          <dt className="text-muted">Last year / month</dt>
          <dd className="text-right">{fmtNum(impact.historicalMonthlyRate)}</dd>
        </dl>
      </CardBody>
    </Card>
  );
}

export function HectaresTile({ impact }: { impact: Impact }) {
  const ratio = impact.marketHa ? impact.impliedHa / impact.marketHa : 0;
  return (
    <Card data-testid="tile-hectares">
      <CardHeader title="Implied hectares" subtitle="Full-year volume ÷ plant density" icon={<MapIcon size={15} />} />
      <CardBody>
        <p className={cn("font-num tabular text-2xl font-semibold", ratio > 1 && "text-crit-700")}>
          {fmtNum(impact.impliedHa)} ha
        </p>
        <p className="tabular text-xs text-muted">of {fmtNum(impact.marketHa)} ha planted in the segment</p>
        <div
          role="meter"
          aria-label="Share of planted hectares"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(ratio * 100)}
          className="mt-3 h-1.5 overflow-hidden rounded-full bg-line"
        >
          <div
            className={cn("h-full rounded-full", ratio > 1 ? "bg-crit-500" : ratio > 0.85 ? "bg-warn-500" : "bg-ink/60")}
            style={{ width: `${Math.min(1, ratio) * 100}%` }}
          />
        </div>
        <p className="tabular mt-1 text-xs text-muted">
          {fmtPct(ratio, 0)} of the market · range {fmtNum(impact.impliedHaLow)} to {fmtNum(impact.impliedHaHigh)} ha
        </p>
      </CardBody>
    </Card>
  );
}

/** `shownAbove` is the flag already shown under the demand input; it is not repeated here. */
export function FlagsTile({ flags, shownAbove }: { flags: Flag[]; shownAbove?: string }) {
  const listed = flags.filter((f) => f.code !== shownAbove);
  return (
    <Card data-testid="tile-flags" className={cn(flags.some((f) => f.severity === "critical") && "border-crit-500/50")}>
      <CardHeader
        title="Checks"
        subtitle={flags.length ? `${flags.length} flag${flags.length > 1 ? "s" : ""}, justification required` : "Checked against history"}
        icon={flags.length ? <AlertTriangle size={15} /> : <CheckCircle2 size={15} />}
      />
      <CardBody className="flex flex-col gap-2">
        <p className="sr-only" aria-live="polite">
          {flags.length ? `${flags.length} check${flags.length > 1 ? "s" : ""} raised` : "No checks raised"}
        </p>
        {flags.length === 0 && <p className="text-sm text-brand-700">No flags. This number is in line with history.</p>}
        {shownAbove && flags.length > 0 && <p className="text-xs text-muted">The main check is shown under your number.</p>}
        {listed.map((f) => (
          <div
            key={f.code}
            data-testid={`flag-${f.code}`}
            className={cn(
              "rounded-md border px-2.5 py-1.5 text-xs",
              f.severity === "critical" ? "border-crit-500/30 bg-crit-50 text-crit-700" : "border-warn-500/30 bg-warn-50 text-warn-700",
            )}
          >
            {f.message}
          </div>
        ))}
      </CardBody>
    </Card>
  );
}
