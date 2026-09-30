// Live demand math. Mirrors backend/app/services/demand_math.py line for line.
import {
  DEFAULT_THRESHOLDS,
  type EntryInput,
  type Impact,
  type SegmentContext,
  type Thresholds,
} from "./mathTypes";

const div = (numerator: number, denominator: number): number =>
  denominator ? numerator / denominator : 0;

function populationStdev(values: number[]): number {
  if (values.length < 2) return 0;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  return Math.sqrt(values.reduce((a, v) => a + (v - mean) ** 2, 0) / values.length);
}

export function openMonths(ctx: SegmentContext): number[] {
  const months: number[] = [];
  for (let m = ctx.clockMonth; m <= 12; m++) months.push(m);
  return months;
}

export function monthSigma(ctx: SegmentContext, expected: number, t: Thresholds): number {
  const residuals: number[] = [];
  for (let m = 1; m < ctx.clockMonth; m++) {
    const actual = ctx.monthlyActual[m - 1];
    if (actual !== null) residuals.push(actual - ctx.monthlyPlan[m - 1]);
  }
  return Math.max(populationStdev(residuals), t.minMonthSigmaPct * expected, t.minMonthSigmaAbs);
}

export function computeImpact(
  ctx: SegmentContext,
  entry: EntryInput,
  t: Thresholds = DEFAULT_THRESHOLDS,
): Impact {
  const months = openMonths(ctx);
  let actualsToDate = 0;
  let actualValueToDate = 0;
  for (let m = 1; m < ctx.clockMonth; m++) {
    actualsToDate += ctx.monthlyActual[m - 1] ?? 0;
    actualValueToDate += ctx.monthlyActualValue[m - 1] ?? 0;
  }

  let otherOpen = 0;
  for (const m of months) {
    if (m !== entry.month) otherOpen += ctx.submitted[String(m)] ?? ctx.monthlyPlan[m - 1];
  }
  const fy = actualsToDate + entry.value + otherOpen;
  const fyLow = actualsToDate + entry.low + otherOpen;
  const fyHigh = actualsToDate + entry.high + otherOpen;

  const price = entry.price ?? ctx.planNetPrice;
  const fyValue = actualValueToDate + entry.value * price + otherOpen * ctx.planNetPrice;

  const monthsRemaining = months.length;
  const ytgRemaining = ctx.planQtyKs - actualsToDate;
  const lastYearOpen = months.reduce((a, m) => a + ctx.lastYearMonthly[m - 1], 0);

  const marketByYear = new Map(ctx.marketHistory.map((p) => [p.year, p]));
  const lastMarket = marketByYear.get(ctx.year - 1);
  const historicalShares = ctx.planQtyHistory
    .filter((p) => p.year <= ctx.year && marketByYear.has(p.year))
    .map((p) => div(p.qtyKs, marketByYear.get(p.year)!.qtyKs));

  const marketValue = ctx.marketQtyKs * ctx.priceExseed;
  const mega = ctx.mega;
  const megaBase = div(mega.syngentaValueEur, mega.marketValueEur);
  const megaNew = div(mega.syngentaValueEur - ctx.planValueEur + fyValue, mega.marketValueEur);
  const scale = Math.max(0, div(100 - megaNew * 100, 100 - megaBase * 100));
  const competitors = mega.competitors.map((c) => ({
    name: c.name,
    baselinePct: c.sharePct,
    newPct: c.sharePct * scale,
    deltaPts: c.sharePct * scale - c.sharePct,
  }));

  const lastYearPrice = div(ctx.lastYearValueEur, ctx.lastYearQtyKs);
  const volumeEffect = (fy - ctx.lastYearQtyKs) * lastYearPrice;
  const avgPrice = div(fyValue, fy);
  const priceEffect = (avgPrice - lastYearPrice) * fy;

  const expected = ctx.monthlyPlan[entry.month - 1];
  const sigma = monthSigma(ctx, expected, t);
  const density = ctx.density;

  return {
    actualsToDate,
    monthsRemaining,
    fyEstimate: fy,
    fyLow,
    fyHigh,
    planFy: ctx.planQtyKs,
    gapToPlan: fy - ctx.planQtyKs,
    ytgRemaining,
    requiredMonthlyRate: div(Math.max(0, ytgRemaining), monthsRemaining),
    enteredMonthlyRate: div(fy - actualsToDate, monthsRemaining),
    historicalMonthlyRate: div(lastYearOpen, monthsRemaining),
    volumeShare: div(fy, ctx.marketQtyKs),
    volumeShareLow: div(fyLow, ctx.marketQtyKs),
    volumeShareHigh: div(fyHigh, ctx.marketQtyKs),
    planVolumeShare: div(ctx.planQtyKs, ctx.marketQtyKs),
    lastYearVolumeShare: div(ctx.lastYearQtyKs, lastMarket ? lastMarket.qtyKs : 0),
    maxHistoricalShare: historicalShares.length ? Math.max(...historicalShares) : 0,
    fyValue,
    valueShare: div(fyValue, marketValue),
    planValueShare: div(ctx.planValueEur, marketValue),
    megaShareBaseline: megaBase,
    megaShare: megaNew,
    competitors,
    impliedHa: div(fy, density),
    impliedHaLow: div(fyLow, density),
    impliedHaHigh: div(fyHigh, density),
    marketHa: ctx.marketHectares,
    megaImpliedHa: mega.impliedHaBaseline - div(ctx.planQtyKs, density) + div(fy, density),
    revenue: {
      lastYear: ctx.lastYearValueEur,
      estimate: fyValue,
      change: fyValue - ctx.lastYearValueEur,
      volumeEffect,
      priceEffect,
      priceShareOfChange: div(priceEffect, Math.abs(volumeEffect) + Math.abs(priceEffect)),
      avgPrice,
      lastYearPrice,
    },
    monthExpected: expected,
    monthLastYear: ctx.lastYearMonthly[entry.month - 1],
    monthSigma: sigma,
    monthZ: div(entry.value - expected, sigma),
  };
}
