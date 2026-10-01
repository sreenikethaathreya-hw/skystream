// Consensus-lead rules. Mirrors backend/app/services/lead_rules.py.
import type { EntryInput, Flag, Impact, LeadRuleSpec, SegmentContext } from "./mathTypes";

// metric -> [label, unit, isChange]. Change metrics are signed; a "below" rule on one uses a negative threshold.
export const METRICS: Record<string, [string, string, boolean]> = {
  month_vs_last_year_pct: ["the month vs the same month last year", "%", true],
  month_vs_plan_pct: ["the month vs plan", "%", true],
  month_vs_average_pct: ["the month vs its historical average", "%", true],
  share_jump_pts: ["the share change from this entry", " pts", true],
  volume_share_pct: ["full-year volume share", "%", false],
  range_width_pct: ["the low-high range as a share of the number", "%", false],
  price_vs_plan_pct: ["net price vs plan price", "%", true],
};

const div = (numerator: number, denominator: number): number => (denominator ? numerator / denominator : 0);

export function metricValue(metric: string, entry: EntryInput, impact: Impact, planNetPrice: number): number | null {
  switch (metric) {
    case "month_vs_last_year_pct":
      return div(entry.value - impact.monthLastYear, impact.monthLastYear) * 100;
    case "month_vs_plan_pct":
      return div(entry.value - impact.monthExpected, impact.monthExpected) * 100;
    case "month_vs_average_pct":
      return impact.monthVsAvgPct * 100;
    case "share_jump_pts":
      return impact.shareJumpPts;
    case "volume_share_pct":
      return impact.volumeShare * 100;
    case "range_width_pct":
      return div(entry.high - entry.low, entry.value) * 100;
    case "price_vs_plan_pct":
      return entry.price == null ? null : div(entry.price - planNetPrice, planNetPrice) * 100;
    default:
      return null;
  }
}

export const ruleFires = (comparator: string, threshold: number, value: number) =>
  comparator === "above" ? value > threshold : value < threshold;

function formatted(metric: string, value: number): string {
  const [, unit, change] = METRICS[metric];
  return change ? `${value >= 0 ? "+" : ""}${value.toFixed(1)}${unit}` : `${value.toFixed(1)}${unit}`;
}

export function evaluateRules(
  ctx: SegmentContext,
  segmentId: number,
  entry: EntryInput,
  impact: Impact,
  rules: LeadRuleSpec[],
): Flag[] {
  const flags: Flag[] = [];
  for (const rule of rules) {
    if (rule.segmentIds != null && !rule.segmentIds.includes(segmentId)) continue;
    if (rule.months != null && !rule.months.includes(entry.month)) continue;
    const value = metricValue(rule.metric, entry, impact, ctx.planNetPrice);
    if (value === null || !ruleFires(rule.comparator, rule.threshold, value)) continue;
    flags.push({
      code: `lead_rule_${rule.id}`,
      severity: rule.severity,
      message: `Lead rule (${rule.author}): ${rule.description} This entry: ${formatted(rule.metric, value)}.`,
    });
  }
  return flags;
}
