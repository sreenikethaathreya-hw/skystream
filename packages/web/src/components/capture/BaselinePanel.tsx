import { History } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { fmtNum, fmtPct, monthName } from "@/lib/format";
import type { Impact, SegmentContext } from "@/lib/mathTypes";
import { cn } from "@/lib/utils";

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <>
      <dt className="text-muted">{label}</dt>
      <dd className={cn("tabular text-right", strong && "font-medium")}>{value}</dd>
    </>
  );
}

function ShareHistory({ ctx, impact }: { ctx: SegmentContext; impact: Impact }) {
  const markets = new Map(ctx.marketHistory.map((p) => [p.year, p.qtyKs]));
  const years = ctx.planQtyHistory
    .filter((p) => markets.has(p.year))
    .map((p) => ({
      year: p.year,
      basis: p.basis ?? (p.year < ctx.year ? "actual" : "plan"),
      share: markets.get(p.year) ? p.qtyKs / markets.get(p.year)! : 0,
    }));
  const top = Math.max(impact.volumeShare, ...years.map((y) => y.share), 0.01);
  const bars = [
    ...years.map((y) => ({ label: `${y.year} ${y.basis}`, share: y.share, live: false })),
    { label: "This entry", share: impact.volumeShare, live: true },
  ];
  return (
    <div data-testid="baseline-share-history">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted">Syngenta volume share by year</p>
      <p className="text-[11px] text-muted">Past years are actual sales; the planning year is plan.</p>
      <div className="mt-2 flex flex-col gap-1.5">
        {bars.map((b) => (
          <div key={b.label} className="grid grid-cols-[84px_1fr_48px] items-center gap-2 text-xs">
            <span className={cn("text-muted", b.live && "font-medium text-ink")}>{b.label}</span>
            <div className="h-2 overflow-hidden rounded-full bg-line">
              <div
                className={cn("h-full rounded-full", b.live ? (b.share > impact.maxHistoricalShare ? "bg-warn-500" : "bg-brand-500") : "bg-muted/50")}
                style={{ width: `${Math.min(1, b.share / top) * 100}%` }}
              />
            </div>
            <span className={cn("tabular text-right", b.live && "font-medium")}>{fmtPct(b.share)}</span>
          </div>
        ))}
      </div>
      <p className="tabular mt-2 text-xs text-muted">
        Average of past years {fmtPct(impact.avgHistoricalShare)} · high {fmtPct(impact.maxHistoricalShare)}
      </p>
    </div>
  );
}

export function BaselinePanel({
  ctx,
  impact,
  month,
  value,
  megaName,
}: {
  ctx: SegmentContext;
  impact: Impact;
  month: number;
  value: number;
  megaName: string;
}) {
  const years = impact.monthHistoryYears;
  const span = years.length > 1 ? `${Math.min(...years)}-${Math.max(...years)}` : years.length ? String(years[0]) : "last year";
  const planImpliedHa = ctx.density ? ctx.planQtyKs / ctx.density : 0;
  const ceiling = ctx.mega.growerCeilingHa;
  const vsAvg = impact.monthVsAvgPct;

  return (
    <Card data-testid="baseline-panel">
      <CardHeader
        title="Baseline"
        subtitle="Historical benchmarks and market potential before you change anything"
        icon={<History size={15} />}
      />
      <CardBody className="grid gap-6 md:grid-cols-3">
        <ShareHistory ctx={ctx} impact={impact} />

        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">{monthName(month)} benchmarks</p>
          <dl className="mt-2 grid grid-cols-2 gap-x-2 gap-y-1 text-xs">
            <Row label="Plan" value={`${fmtNum(impact.monthExpected)} KS`} />
            <Row label="Last year" value={`${fmtNum(impact.monthLastYear)} KS`} />
            <Row label={`Historical average (${span})`} value={`${fmtNum(impact.monthHistoryAvg)} KS`} />
            <Row label="Your entry" value={`${fmtNum(value)} KS`} strong />
          </dl>
          {impact.monthHistoryAvg > 0 && (
            <p
              className={cn("tabular mt-2 text-xs font-medium", Math.abs(vsAvg) > 0.25 ? "text-warn-700" : "text-brand-700")}
              data-testid="baseline-vs-average"
            >
              {(Math.abs(vsAvg) * 100).toFixed(0)}% {vsAvg >= 0 ? "above" : "below"} the historical {monthName(month)} average
            </p>
          )}
        </div>

        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">Market potential</p>
          <dl className="mt-2 grid grid-cols-2 gap-x-2 gap-y-1 text-xs">
            <Row label="Planted area" value={`${fmtNum(ctx.marketHectares)} ha`} />
            <Row label="Market volume" value={`${fmtNum(ctx.marketQtyKs)} KS`} />
            <Row label="Plan needs" value={`${fmtNum(planImpliedHa)} ha`} />
            <Row label="This entry needs" value={`${fmtNum(impact.impliedHa)} ha`} strong />
          </dl>
          {ceiling > 0 && (
            <p className="tabular mt-2 text-xs text-muted" data-testid="baseline-grower-potential">
              {megaName}: {fmtNum(impact.megaImpliedHa)} of {fmtNum(ceiling)} ha CRM grower potential (
              {fmtPct(impact.megaImpliedHa / ceiling, 0)})
            </p>
          )}
        </div>
      </CardBody>
    </Card>
  );
}
