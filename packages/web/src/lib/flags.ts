// Deterministic plausibility flags. Mirrors backend/app/services/flags.py.
import {
  DEFAULT_THRESHOLDS,
  type EntryInput,
  type Flag,
  type Impact,
  type SegmentContext,
  type Thresholds,
} from "./mathTypes";

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const num = (v: number) => Math.round(v).toLocaleString("en-US");
const signed = (v: number, digits: number) => `${v >= 0 ? "+" : ""}${v.toFixed(digits)}`;

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function vsAverage(entry: EntryInput, impact: Impact): string {
  const years = impact.monthHistoryYears;
  const span =
    years.length > 1 ? `${Math.min(...years)}-${Math.max(...years)}` : years.length ? String(years[0]) : "last year";
  const direction = impact.monthVsAvgPct >= 0 ? "above" : "below";
  return (
    `${(Math.abs(impact.monthVsAvgPct) * 100).toFixed(0)}% ${direction} the historical ` +
    `${MONTHS[entry.month - 1]} average (${num(impact.monthHistoryAvg)} KS, ${span})`
  );
}

export function evaluateFlags(
  ctx: SegmentContext,
  entry: EntryInput,
  impact: Impact,
  t: Thresholds = DEFAULT_THRESHOLDS,
): Flag[] {
  const flags: Flag[] = [];

  if (ctx.marketQtyKs <= 0) {
    flags.push({
      code: "no_market",
      severity: "critical",
      message: "This micro-segment has no market size, so share cannot be checked.",
    });
    return flags;
  }

  if (impact.volumeShare > 1) {
    flags.push({
      code: "share_over_100",
      severity: "critical",
      message: `Implied share is ${pct(impact.volumeShare)}, above the whole market.`,
    });
  } else if (impact.volumeShare > impact.maxHistoricalShare + t.shareHistoryMarginPts / 100) {
    flags.push({
      code: "share_above_history",
      severity: "warning",
      message:
        `Implied share ${pct(impact.volumeShare)} is more than ${t.shareHistoryMarginPts.toFixed(0)} pts ` +
        `above the 2024-${ctx.year} high of ${pct(impact.maxHistoricalShare)}.`,
    });
  }

  if (Math.abs(impact.shareJumpPts) > t.shareJumpPts) {
    const moved =
      `${impact.shareJumpPts > 0 ? "lifts" : "cuts"} share from ${pct(impact.baselineShare)} ` +
      `to ${pct(impact.volumeShare)} (${signed(impact.shareJumpPts, 1)} pts)`;
    flags.push({
      code: "share_jump",
      severity: "warning",
      message:
        impact.monthHistoryAvg > 0
          ? `This entry is ${vsAverage(entry, impact)} and ${moved}.`
          : `This entry ${moved} in a single month.`,
    });
  }

  if (impact.impliedHa > impact.marketHa) {
    flags.push({
      code: "implied_ha_over_market",
      severity: "critical",
      message:
        `This volume needs ${num(impact.impliedHa)} ha of Syngenta seed; the market only plants ` +
        `${num(impact.marketHa)} ha.`,
    });
  }

  const band = t.monthSigmaMultiplier * impact.monthSigma;
  if (
    Math.abs(entry.value - impact.monthExpected) > band &&
    Math.abs(entry.value - impact.monthLastYear) > band
  ) {
    flags.push({
      code: "month_outlier",
      severity: "warning",
      message:
        `${num(entry.value)} KS is ${signed(impact.monthZ, 1)} sigma from the plan for this month ` +
        `(${num(impact.monthExpected)}) and far from last year (${num(impact.monthLastYear)})` +
        (impact.monthHistoryAvg > 0 && !flags.some((f) => f.code === "share_jump")
          ? `; ${vsAverage(entry, impact)}.`
          : "."),
    });
  }

  const previous = ctx.marketHistory.find((p) => p.year === ctx.year - 1)?.hectares;
  if (previous) {
    const trend = (ctx.marketHectares - previous) / previous;
    const raising = entry.value > impact.monthExpected * 1.05;
    const cutting = entry.value < impact.monthExpected * 0.95;
    if ((trend < -t.marketTrendPct && raising) || (trend > t.marketTrendPct && cutting)) {
      const note = ctx.marketTrendNote ? ` Market note: ${ctx.marketTrendNote}` : "";
      flags.push({
        code: "against_market_trend",
        severity: "warning",
        message:
          `Demand moves ${raising ? "up" : "down"} while planted area is ` +
          `${trend < 0 ? "shrinking" : "growing"} (${signed(trend * 100, 1)}% vs ${ctx.year - 1}).${note}`,
      });
    }
  }

  const revenue = impact.revenue;
  if (
    revenue.volumeEffect < 0 &&
    revenue.priceEffect > 0 &&
    revenue.priceShareOfChange >= t.priceCarryingShare
  ) {
    flags.push({
      code: "price_carrying",
      severity: "warning",
      message:
        `Price is carrying this number: volume is down EUR ${num(-revenue.volumeEffect)} vs last year ` +
        `and price adds EUR ${num(revenue.priceEffect)} (${pct(revenue.priceShareOfChange)} of the revenue movement).`,
    });
  }

  if (ctx.mega.growerCeilingHa > 0 && impact.megaImpliedHa > ctx.mega.growerCeilingHa) {
    flags.push({
      code: "above_grower_potential",
      severity: "warning",
      message:
        `${ctx.mega.name || "The mega-segment"} would need ${num(impact.megaImpliedHa)} ha on Syngenta seed, above the ` +
        `${num(ctx.mega.growerCeilingHa)} ha of CRM grower potential.`,
    });
  }

  if (entry.value > 0 && (entry.high - entry.low) / entry.value > t.rangeWidthPct) {
    flags.push({
      code: "range_too_wide",
      severity: "warning",
      message:
        `The range ${num(entry.low)}-${num(entry.high)} spans ` +
        `${pct((entry.high - entry.low) / entry.value)} of the number; supply planning will build to the low end.`,
    });
  }

  if (entry.price != null && ctx.netPriceHistory.length) {
    const low = Math.min(...ctx.netPriceHistory) * (1 - t.priceBandPct);
    const high = Math.max(...ctx.netPriceHistory) * (1 + t.priceBandPct);
    if (entry.price < low || entry.price > high) {
      flags.push({
        code: "price_outside_history",
        severity: "warning",
        message: `Net price EUR ${num(entry.price)}/KS is outside the historical band EUR ${num(low)}-${num(high)}.`,
      });
    }
  }

  return flags;
}
