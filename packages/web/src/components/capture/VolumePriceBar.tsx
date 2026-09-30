import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { fmtEur } from "@/lib/format";
import type { RevenueSplit } from "@/lib/mathTypes";
import { cn } from "@/lib/utils";

export function VolumePriceBar({ revenue }: { revenue: RevenueSplit }) {
  const scale = Math.max(Math.abs(revenue.volumeEffect), Math.abs(revenue.priceEffect), 1);
  const bar = (value: number, color: string) => (
    <div className="relative h-4 flex-1 rounded bg-canvas">
      <div className="absolute inset-y-0 left-1/2 w-px bg-line" />
      <div
        className={cn("absolute inset-y-0 rounded", color)}
        style={{
          left: value >= 0 ? "50%" : `${50 - (Math.abs(value) / scale) * 50}%`,
          width: `${(Math.abs(value) / scale) * 50}%`,
        }}
      />
    </div>
  );
  return (
    <Card data-testid="volume-price">
      <CardHeader
        title="Where the revenue change comes from"
        subtitle={`Full-year revenue ${fmtEur(revenue.estimate)} vs ${fmtEur(revenue.lastYear)} last year (${revenue.change >= 0 ? "+" : ""}${fmtEur(revenue.change)})`}
      />
      <CardBody className="flex flex-col gap-2 text-xs">
        <div className="flex items-center gap-3">
          <span className="w-16 text-muted">Volume</span>
          {bar(revenue.volumeEffect, revenue.volumeEffect >= 0 ? "bg-brand-500" : "bg-crit-500")}
          <span className="tabular w-24 text-right">{revenue.volumeEffect >= 0 ? "+" : ""}{fmtEur(revenue.volumeEffect)}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="w-16 text-muted">Price</span>
          {bar(revenue.priceEffect, revenue.priceEffect >= 0 ? "bg-info-500" : "bg-crit-500")}
          <span className="tabular w-24 text-right">{revenue.priceEffect >= 0 ? "+" : ""}{fmtEur(revenue.priceEffect)}</span>
        </div>
        <p className="text-muted">
          Average price EUR {revenue.avgPrice.toFixed(0)}/KS vs EUR {revenue.lastYearPrice.toFixed(0)}/KS last year.
        </p>
      </CardBody>
    </Card>
  );
}
