"""Split each yearly Syngenta plan into months.

Priority: uploaded micro-segment seasonality, then mega-segment seasonality, then the shape of the previous
two complete years of monthly actuals, then a flat split. The basis is stored per row so the screen can say which.
"""

from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MonthlyActual, MonthlyPlan, PlanYear, Seasonality, Segment

PROFILE_YEARS = 2


def _normalized(values: list[float]) -> list[float] | None:
    total = sum(values)
    return [v / total for v in values] if total > 0 else None


async def rebuild_monthly_plan(db: AsyncSession, countries: set[str]) -> dict[str, int]:
    if not countries:
        return {}
    plans = (await db.execute(select(PlanYear).where(PlanYear.country_code.in_(countries)))).scalars().all()
    mega_of = {s.id: s.mega_segment_id for s in (await db.execute(select(Segment))).scalars()}

    seasonality: dict[tuple[str, str, str], list[float]] = defaultdict(lambda: [0.0] * 12)
    for s in (await db.execute(select(Seasonality).where(Seasonality.country_code.in_(countries)))).scalars():
        seasonality[(s.country_code, s.scope_type, s.scope_id)][s.month - 1] = s.weight

    actuals: dict[tuple[str, int, int], list[float | None]] = defaultdict(lambda: [None] * 12)
    for a in (
        await db.execute(select(MonthlyActual).where(MonthlyActual.country_code.in_(countries)))
    ).scalars():
        actuals[(a.country_code, a.segment_id, a.year)][a.month - 1] = a.qty_ks
    # Only complete years shape the profile; a part-year would put the whole plan into the months seen so far.
    complete = {key: values for key, values in actuals.items() if all(v is not None for v in values)}

    await db.execute(delete(MonthlyPlan).where(MonthlyPlan.country_code.in_(countries)))
    bases: dict[str, int] = defaultdict(int)
    for plan in plans:
        country, segment_id, year = plan.country_code, plan.segment_id, plan.year
        weights, basis = None, "flat"
        if (country, "micro", str(segment_id)) in seasonality:
            weights, basis = (
                _normalized(seasonality[(country, "micro", str(segment_id))]),
                "seasonality_micro",
            )
        elif (country, "mega", mega_of.get(segment_id, "")) in seasonality:
            weights, basis = (
                _normalized(seasonality[(country, "mega", mega_of[segment_id])]),
                "seasonality_mega",
            )
        else:
            history = [complete.get((country, segment_id, year - k)) for k in range(1, PROFILE_YEARS + 1)]
            summed = [sum(h[m] for h in history if h) for m in range(12)]
            profile = _normalized(summed)
            if profile:
                weights, basis = profile, "actuals_profile"
        weights = weights or [1 / 12] * 12
        bases[basis] += 1
        db.add_all(
            MonthlyPlan(
                country_code=country,
                segment_id=segment_id,
                year=year,
                month=m + 1,
                qty_ks=plan.qty_ks * weights[m],
                basis=basis,
            )
            for m in range(12)
        )
    await db.flush()
    return dict(bases)
