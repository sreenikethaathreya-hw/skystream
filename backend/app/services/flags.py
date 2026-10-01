"""Deterministic plausibility flags. Mirrored in packages/web/src/lib/flags.ts."""

from app.schemas.demand_math import EntryInput, Flag, Impact, SegmentContext, Thresholds


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _num(value: float) -> str:
    return f"{value:,.0f}"


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


def _vs_average(entry: EntryInput, impact: Impact) -> str:
    """'40% above the historical October average (5,062 KS, 2024-2025)'."""
    years = impact.month_history_years
    span = f"{min(years)}-{max(years)}" if len(years) > 1 else str(years[0]) if years else "last year"
    direction = "above" if impact.month_vs_avg_pct >= 0 else "below"
    return (
        f"{abs(impact.month_vs_avg_pct) * 100:.0f}% {direction} the historical "
        f"{MONTHS[entry.month - 1]} average ({_num(impact.month_history_avg)} KS, {span})"
    )


def evaluate_flags(
    ctx: SegmentContext,
    entry: EntryInput,
    impact: Impact,
    thresholds: Thresholds | None = None,
) -> list[Flag]:
    t = thresholds or Thresholds()
    flags: list[Flag] = []

    if ctx.market_qty_ks <= 0:
        flags.append(
            Flag(
                code="no_market",
                severity="critical",
                message="This micro-segment has no market size, so share cannot be checked.",
            )
        )
        return flags

    if impact.volume_share > 1:
        flags.append(
            Flag(
                code="share_over_100",
                severity="critical",
                message=f"Implied share is {_pct(impact.volume_share)}, above the whole market.",
            )
        )
    elif impact.volume_share > impact.max_historical_share + t.share_history_margin_pts / 100:
        flags.append(
            Flag(
                code="share_above_history",
                severity="warning",
                message=(
                    f"Implied share {_pct(impact.volume_share)} is more than "
                    f"{t.share_history_margin_pts:.0f} pts above the 2024-{ctx.year} high of "
                    f"{_pct(impact.max_historical_share)}."
                ),
            )
        )

    if abs(impact.share_jump_pts) > t.share_jump_pts:
        moved = (
            f"{'lifts' if impact.share_jump_pts > 0 else 'cuts'} share from {_pct(impact.baseline_share)} "
            f"to {_pct(impact.volume_share)} ({impact.share_jump_pts:+.1f} pts)"
        )
        message = (
            f"This entry is {_vs_average(entry, impact)} and {moved}."
            if impact.month_history_avg > 0
            else f"This entry {moved} in a single month."
        )
        flags.append(Flag(code="share_jump", severity="warning", message=message))

    if impact.implied_ha > impact.market_ha:
        flags.append(
            Flag(
                code="implied_ha_over_market",
                severity="critical",
                message=(
                    f"This volume needs {_num(impact.implied_ha)} ha of Syngenta seed; the market "
                    f"only plants {_num(impact.market_ha)} ha."
                ),
            )
        )

    band = t.month_sigma_multiplier * impact.month_sigma
    if abs(entry.value - impact.month_expected) > band and abs(entry.value - impact.month_last_year) > band:
        flags.append(
            Flag(
                code="month_outlier",
                severity="warning",
                message=(
                    f"{_num(entry.value)} KS is far from the plan for this "
                    f"month ({_num(impact.month_expected)}) and from last year "
                    f"({_num(impact.month_last_year)})"
                    + (
                        f"; {_vs_average(entry, impact)}."
                        if impact.month_history_avg > 0 and not any(f.code == "share_jump" for f in flags)
                        else "."
                    )
                ),
            )
        )

    history = {p.year: p.hectares for p in ctx.market_history}
    previous = history.get(ctx.year - 1)
    if previous:
        trend = (ctx.market_hectares - previous) / previous
        raising = entry.value > impact.month_expected * 1.05
        cutting = entry.value < impact.month_expected * 0.95
        if (trend < -t.market_trend_pct and raising) or (trend > t.market_trend_pct and cutting):
            note = f" Market note: {ctx.market_trend_note}" if ctx.market_trend_note else ""
            flags.append(
                Flag(
                    code="against_market_trend",
                    severity="warning",
                    message=(
                        f"Demand moves {'up' if raising else 'down'} while planted area is "
                        f"{'shrinking' if trend < 0 else 'growing'} ({trend * 100:+.1f}% vs "
                        f"{ctx.year - 1}).{note}"
                    ),
                )
            )

    revenue = impact.revenue
    if (
        revenue.volume_effect < 0
        and revenue.price_effect > 0
        and revenue.price_share_of_change >= t.price_carrying_share
    ):
        flags.append(
            Flag(
                code="price_carrying",
                severity="warning",
                message=(
                    f"Price is carrying this number: volume is down USD {_num(-revenue.volume_effect)} "
                    f"vs last year and price adds USD {_num(revenue.price_effect)} "
                    f"({_pct(revenue.price_share_of_change)} of the revenue movement)."
                ),
            )
        )

    if impact.mega_implied_ha > ctx.mega.grower_ceiling_ha > 0:
        flags.append(
            Flag(
                code="above_grower_potential",
                severity="warning",
                message=(
                    f"{ctx.mega.name or 'The mega-segment'} would need {_num(impact.mega_implied_ha)} ha on Syngenta seed, "
                    f"above the {_num(ctx.mega.grower_ceiling_ha)} ha of CRM grower potential."
                ),
            )
        )

    if entry.value > 0 and (entry.high - entry.low) / entry.value > t.range_width_pct:
        flags.append(
            Flag(
                code="range_too_wide",
                severity="warning",
                message=(
                    f"The range {_num(entry.low)}-{_num(entry.high)} spans "
                    f"{_pct((entry.high - entry.low) / entry.value)} of the number; supply "
                    "planning will build to the low end."
                ),
            )
        )

    if entry.price is not None and ctx.net_price_history:
        low = min(ctx.net_price_history) * (1 - t.price_band_pct)
        high = max(ctx.net_price_history) * (1 + t.price_band_pct)
        if not low <= entry.price <= high:
            flags.append(
                Flag(
                    code="price_outside_history",
                    severity="warning",
                    message=(
                        f"Net price USD {entry.price:,.0f}/KS is outside the historical band "
                        f"USD {low:,.0f}-{high:,.0f}."
                    ),
                )
            )

    return flags


def needs_justification(flags: list[Flag]) -> bool:
    return bool(flags)
