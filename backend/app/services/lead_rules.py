"""Consensus-lead rules: fixed metrics checked like the built-in flags. Mirrored in packages/web/src/lib/leadRules.ts."""

from app.schemas.demand_math import EntryInput, Flag, Impact, LeadRuleSpec, SegmentContext

# metric -> (label, unit, is_change). Change metrics are signed; a "below" rule on one uses a negative threshold.
METRICS: dict[str, tuple[str, str, bool]] = {
    "month_vs_last_year_pct": ("the month vs the same month last year", "%", True),
    "month_vs_plan_pct": ("the month vs plan", "%", True),
    "month_vs_average_pct": ("the month vs its historical average", "%", True),
    "share_jump_pts": ("the share change from this entry", " pts", True),
    "volume_share_pct": ("full-year volume share", "%", False),
    "range_width_pct": ("the low-high range as a share of the number", "%", False),
    "price_vs_plan_pct": ("net price vs plan price", "%", True),
}


def _div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def metric_value(metric: str, entry: EntryInput, impact: Impact, plan_net_price: float) -> float | None:
    if metric == "month_vs_last_year_pct":
        return _div(entry.value - impact.month_last_year, impact.month_last_year) * 100
    if metric == "month_vs_plan_pct":
        return _div(entry.value - impact.month_expected, impact.month_expected) * 100
    if metric == "month_vs_average_pct":
        return impact.month_vs_avg_pct * 100
    if metric == "share_jump_pts":
        return impact.share_jump_pts
    if metric == "volume_share_pct":
        return impact.volume_share * 100
    if metric == "range_width_pct":
        return _div(entry.high - entry.low, entry.value) * 100
    if metric == "price_vs_plan_pct":
        if entry.price is None:
            return None
        return _div(entry.price - plan_net_price, plan_net_price) * 100
    return None


def rule_fires(comparator: str, threshold: float, value: float) -> bool:
    return value > threshold if comparator == "above" else value < threshold


def _formatted(metric: str, value: float) -> str:
    _, unit, change = METRICS[metric]
    return f"{value:+.1f}{unit}" if change else f"{value:.1f}{unit}"


def evaluate_rules(
    ctx: SegmentContext,
    segment_id: int,
    entry: EntryInput,
    impact: Impact,
    rules: list[LeadRuleSpec],
) -> list[Flag]:
    flags: list[Flag] = []
    for rule in rules:
        if rule.segment_ids is not None and segment_id not in rule.segment_ids:
            continue
        if rule.months is not None and entry.month not in rule.months:
            continue
        value = metric_value(rule.metric, entry, impact, ctx.plan_net_price)
        if value is None or not rule_fires(rule.comparator, rule.threshold, value):
            continue
        flags.append(
            Flag(
                code=f"lead_rule_{rule.id}",
                severity=rule.severity,
                message=f"Lead rule ({rule.author}): {rule.description} This entry: {_formatted(rule.metric, value)}.",
            )
        )
    return flags


def unmet_driver_flags(
    rules: list[LeadRuleSpec], fired: list[Flag], claim_driver: str | None, driver_labels: dict[str, str]
) -> list[Flag]:
    """Server-side only: a fired rule that demands a reason the structured claim does not give."""
    codes = {f.code for f in fired}
    out: list[Flag] = []
    for rule in rules:
        if f"lead_rule_{rule.id}" not in codes or not rule.required_driver or claim_driver == rule.required_driver:
            continue
        given = driver_labels.get(claim_driver or "", "no clear reason")
        out.append(
            Flag(
                code=f"lead_rule_{rule.id}_unmet",
                severity="critical",
                message=(
                    f"Lead rule ({rule.author}) needs a justification citing "
                    f"{driver_labels.get(rule.required_driver, rule.required_driver)}; this one reads as {given}."
                ),
            )
        )
    return out
