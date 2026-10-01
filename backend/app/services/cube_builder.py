"""Pure assembly of per-segment math contexts from reference rows (ORM objects or namespaces)."""

from collections import defaultdict
from dataclasses import dataclass, field

from app.schemas.demand_math import Competitor, MarketPoint, MegaContext, SegmentContext, YearMonthly


@dataclass
class Reference:
    segments: list = field(default_factory=list)
    market: list = field(default_factory=list)
    plan: list = field(default_factory=list)
    monthly_plan: list = field(default_factory=list)
    monthly_actuals: list = field(default_factory=list)
    competitors: list = field(default_factory=list)
    grower: list = field(default_factory=list)


def _index(rows: list) -> dict[tuple[int, int], object]:
    return {(r.segment_id, r.year): r for r in rows}


def _monthly(rows: list, year: int) -> dict[int, list]:
    out: dict[int, list] = defaultdict(lambda: [None] * 12)
    for r in rows:
        if r.year == year:
            out[r.segment_id][r.month - 1] = r
    return out


def build_mega(ref: Reference, year: int) -> MegaContext:
    market = _index(ref.market)
    plan = _index(ref.plan)
    market_value = 0.0
    syngenta_value = 0.0
    implied_ha = 0.0
    for seg in ref.segments:
        m = market.get((seg.id, year))
        p = plan.get((seg.id, year))
        if m:
            market_value += m.qty_ks * m.price_exseed
        if p:
            syngenta_value += p.value_eur
            if m and m.density:
                implied_ha += p.qty_ks / m.density
    rows = [c for c in ref.competitors if c.year == year]
    syngenta = next((c for c in rows if c.competitor == "Syngenta"), None)
    first = ref.segments[0] if ref.segments else None
    return MegaContext(
        name=getattr(first, "mega_segment_desc", "") or "",
        market_value_eur=market_value,
        syngenta_value_eur=syngenta_value,
        syngenta_share_pct=syngenta.share_pct if syngenta else 0.0,
        competitors=[
            Competitor(name=c.competitor, share_pct=c.share_pct)
            for c in sorted(rows, key=lambda c: -c.share_pct)
            if c.competitor != "Syngenta"
        ],
        implied_ha_baseline=implied_ha,
        grower_ceiling_ha=sum(g.hectares for g in ref.grower if g.owner == "syngenta"),
    )


def last_year_basis(ref: Reference, segment_id: int, year: int) -> str:
    """'actuals' when all 12 months of last year's actuals are loaded, else 'plan' (or 'none')."""
    rows = _monthly(ref.monthly_actuals, year - 1).get(segment_id)
    if rows and all(r is not None for r in rows):
        return "actuals"
    return "plan" if (segment_id, year - 1) in _index(ref.plan) else "none"


def monthly_history(ref: Reference, segment_id: int, year: int) -> list[YearMonthly]:
    """Each earlier year's monthly volume: full actuals when all 12 months are loaded, else phased plan."""
    years = sorted(
        {r.year for r in ref.monthly_actuals if r.segment_id == segment_id and r.year < year}
        | {r.year for r in ref.monthly_plan if r.segment_id == segment_id and r.year < year}
    )
    out: list[YearMonthly] = []
    for y in years:
        actuals = _monthly(ref.monthly_actuals, y).get(segment_id)
        if actuals and all(r is not None for r in actuals):
            out.append(YearMonthly(year=y, basis="actuals", qty_ks=[r.qty_ks for r in actuals]))
            continue
        plan_rows = _monthly(ref.monthly_plan, y).get(segment_id)
        if plan_rows and any(r is not None for r in plan_rows):
            out.append(YearMonthly(year=y, basis="plan", qty_ks=[r.qty_ks if r else 0.0 for r in plan_rows]))
    return out


def build_segment_context(
    ref: Reference,
    segment_id: int,
    year: int,
    clock_month: int,
    submitted: dict[int, float],
    mega: MegaContext,
) -> SegmentContext:
    market = _index(ref.market)
    plan = _index(ref.plan)
    m = market[(segment_id, year)]
    p = plan.get((segment_id, year))
    last = plan.get((segment_id, year - 1))
    monthly_plan = _monthly(ref.monthly_plan, year)[segment_id]
    actual_rows = _monthly(ref.monthly_actuals, year)[segment_id]
    last_actuals = _monthly(ref.monthly_actuals, year - 1)[segment_id]
    use_actuals = last_year_basis(ref, segment_id, year) == "actuals"
    last_rows = last_actuals if use_actuals else _monthly(ref.monthly_plan, year - 1)[segment_id]
    last_qty = sum(r.qty_ks for r in last_actuals) if use_actuals else (last.qty_ks if last else 0.0)
    last_value = sum(r.value_eur for r in last_actuals) if use_actuals else (last.value_eur if last else 0.0)

    revealed = [r if r is not None and r.month < clock_month else None for r in actual_rows]
    years = sorted({r.year for r in ref.market if r.segment_id == segment_id})
    plan_years = sorted({r.year for r in ref.plan if r.segment_id == segment_id})

    return SegmentContext(
        year=year,
        clock_month=clock_month,
        market_hectares=m.hectares,
        market_qty_ks=m.qty_ks,
        density=m.density,
        price_exseed=m.price_exseed,
        plan_qty_ks=p.qty_ks if p else 0.0,
        plan_value_eur=p.value_eur if p else 0.0,
        plan_net_price=p.net_price if p else 0.0,
        last_year_qty_ks=last_qty,
        last_year_value_eur=last_value,
        market_history=[
            MarketPoint(
                year=y,
                hectares=market[(segment_id, y)].hectares,
                qty_ks=market[(segment_id, y)].qty_ks,
            )
            for y in years
            if y <= year
        ],
        plan_qty_history=[
            MarketPoint(year=y, hectares=0.0, qty_ks=plan[(segment_id, y)].qty_ks)
            for y in plan_years
            if y <= year
        ],
        net_price_history=[
            plan[(segment_id, y)].net_price
            for y in plan_years
            if y <= year and plan[(segment_id, y)].net_price
        ],
        monthly_plan=[r.qty_ks if r else 0.0 for r in monthly_plan],
        monthly_actual=[r.qty_ks if r else None for r in revealed],
        monthly_actual_value=[r.value_eur if r else None for r in revealed],
        last_year_monthly=[r.qty_ks if r else 0.0 for r in last_rows],
        monthly_history=monthly_history(ref, segment_id, year),
        submitted={str(month): value for month, value in submitted.items() if month >= clock_month},
        market_trend_note=(m.notes or {}).get("dynamics"),
        mega=mega,
    )
