"""Live demand math. Mirrored line-for-line in packages/web/src/lib/demandMath.ts."""

import math

from app.schemas.demand_math import (
    CompetitorImpact,
    EntryInput,
    Impact,
    RevenueSplit,
    SegmentContext,
    Thresholds,
)


def _div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _population_stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def open_months(ctx: SegmentContext) -> list[int]:
    return list(range(ctx.clock_month, 13))


def month_sigma(ctx: SegmentContext, expected: float, thresholds: Thresholds) -> float:
    residuals = [
        actual - ctx.monthly_plan[m - 1]
        for m in range(1, ctx.clock_month)
        if (actual := ctx.monthly_actual[m - 1]) is not None
    ]
    return max(
        _population_stdev(residuals),
        thresholds.min_month_sigma_pct * expected,
        thresholds.min_month_sigma_abs,
    )


def compute_impact(ctx: SegmentContext, entry: EntryInput, thresholds: Thresholds | None = None) -> Impact:
    thresholds = thresholds or Thresholds()
    months = open_months(ctx)
    past = range(1, ctx.clock_month)
    actuals_to_date = sum(ctx.monthly_actual[m - 1] or 0.0 for m in past)
    actual_value_to_date = sum(ctx.monthly_actual_value[m - 1] or 0.0 for m in past)

    other_open = sum(ctx.submitted.get(str(m), ctx.monthly_plan[m - 1]) for m in months if m != entry.month)
    fy = actuals_to_date + entry.value + other_open
    fy_low = actuals_to_date + entry.low + other_open
    fy_high = actuals_to_date + entry.high + other_open

    price = entry.price if entry.price is not None else ctx.plan_net_price
    fy_value = actual_value_to_date + entry.value * price + other_open * ctx.plan_net_price

    months_remaining = len(months)
    ytg_remaining = ctx.plan_qty_ks - actuals_to_date
    last_year_open = sum(ctx.last_year_monthly[m - 1] for m in months)

    market_by_year = {p.year: p for p in ctx.market_history}
    last_market = market_by_year.get(ctx.year - 1)
    historical_shares = [
        _div(p.qty_ks, market_by_year[p.year].qty_ks)
        for p in ctx.plan_qty_history
        if p.year <= ctx.year and p.year in market_by_year
    ]

    market_value = ctx.market_qty_ks * ctx.price_exseed
    mega = ctx.mega
    mega_base = _div(mega.syngenta_value_eur, mega.market_value_eur)
    mega_new = _div(mega.syngenta_value_eur - ctx.plan_value_eur + fy_value, mega.market_value_eur)
    scale = _div(100 - mega_new * 100, 100 - mega_base * 100)
    competitors = [
        CompetitorImpact(
            name=c.name,
            baseline_pct=c.share_pct,
            new_pct=c.share_pct * scale,
            delta_pts=c.share_pct * scale - c.share_pct,
        )
        for c in mega.competitors
    ]

    last_year_price = _div(ctx.last_year_value_eur, ctx.last_year_qty_ks)
    volume_effect = (fy - ctx.last_year_qty_ks) * last_year_price
    avg_price = _div(fy_value, fy)
    price_effect = (avg_price - last_year_price) * fy
    revenue = RevenueSplit(
        last_year=ctx.last_year_value_eur,
        estimate=fy_value,
        change=fy_value - ctx.last_year_value_eur,
        volume_effect=volume_effect,
        price_effect=price_effect,
        price_share_of_change=_div(price_effect, abs(volume_effect) + abs(price_effect)),
        avg_price=avg_price,
        last_year_price=last_year_price,
    )

    expected = ctx.monthly_plan[entry.month - 1]
    sigma = month_sigma(ctx, expected, thresholds)
    density = ctx.density

    return Impact(
        actuals_to_date=actuals_to_date,
        months_remaining=months_remaining,
        fy_estimate=fy,
        fy_low=fy_low,
        fy_high=fy_high,
        plan_fy=ctx.plan_qty_ks,
        gap_to_plan=fy - ctx.plan_qty_ks,
        ytg_remaining=ytg_remaining,
        required_monthly_rate=_div(max(0.0, ytg_remaining), months_remaining),
        entered_monthly_rate=_div(fy - actuals_to_date, months_remaining),
        historical_monthly_rate=_div(last_year_open, months_remaining),
        volume_share=_div(fy, ctx.market_qty_ks),
        volume_share_low=_div(fy_low, ctx.market_qty_ks),
        volume_share_high=_div(fy_high, ctx.market_qty_ks),
        plan_volume_share=_div(ctx.plan_qty_ks, ctx.market_qty_ks),
        last_year_volume_share=_div(ctx.last_year_qty_ks, last_market.qty_ks if last_market else 0),
        max_historical_share=max(historical_shares, default=0.0),
        fy_value=fy_value,
        value_share=_div(fy_value, market_value),
        plan_value_share=_div(ctx.plan_value_eur, market_value),
        mega_share_baseline=mega_base,
        mega_share=mega_new,
        competitors=competitors,
        implied_ha=_div(fy, density),
        implied_ha_low=_div(fy_low, density),
        implied_ha_high=_div(fy_high, density),
        market_ha=ctx.market_hectares,
        mega_implied_ha=mega.implied_ha_baseline - _div(ctx.plan_qty_ks, density) + _div(fy, density),
        revenue=revenue,
        month_expected=expected,
        month_last_year=ctx.last_year_monthly[entry.month - 1],
        month_sigma=sigma,
        month_z=_div(entry.value - expected, sigma),
    )
