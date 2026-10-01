from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Country, DemoClock, IbpForecast, MonthlyActual, Segment, VarietyMap
from app.services.fx_service import BudgetRates, load_budget_rates


def normalize(value: str) -> str:
    return " ".join(str(value).replace("\xa0", " ").split()).upper()


@dataclass
class ImportContext:
    """Reference data validators need: country spellings and the product hierarchy already loaded."""

    country_aliases: dict[str, str] = field(default_factory=dict)
    segment_ids: set[int] = field(default_factory=set)
    segment_by_desc: dict[str, int] = field(default_factory=dict)
    mega_by_segment: dict[int, str] = field(default_factory=dict)
    grower_ha_cap: float = 500.0
    fx: BudgetRates = field(default_factory=BudgetRates)
    price_source: str = "value_over_qty"
    current_year: int | None = None
    # (country, normalized variety) -> micro-segment, for SAC exports without a micro-segment column.
    variety_map: dict[tuple[str, str], int] = field(default_factory=dict)
    # First open (year, month) per country; forecasts for earlier months are skipped.
    open_from: dict[str, tuple[int, int]] = field(default_factory=dict)
    # Latest IBP snapshot per (country, segment, year, month): (snapshot, qty) for the preview's change list.
    previous_forecast: dict[tuple[str, int, int, int], tuple[str, float]] = field(default_factory=dict)

    @property
    def mega_ids(self) -> set[str]:
        return set(self.mega_by_segment.values())

    def country(self, value) -> str | None:
        if value is None:
            return None
        return self.country_aliases.get(normalize(value))


async def load_context(db: AsyncSession, settings) -> ImportContext:
    ctx = ImportContext(
        grower_ha_cap=settings.grower_ha_cap,
        fx=await load_budget_rates(db, settings.fx_rate_year_rule, settings.current_year),
        price_source=settings.price_source,
        current_year=settings.current_year,
    )
    for c in (await db.execute(select(Country))).scalars():
        for alias in [c.code, c.name, *(c.aliases or [])]:
            ctx.country_aliases[normalize(alias)] = c.code
    for s in (await db.execute(select(Segment))).scalars():
        ctx.segment_ids.add(s.id)
        ctx.segment_by_desc[normalize(s.description)] = s.id
        ctx.mega_by_segment[s.id] = s.mega_segment_id
    for v in (await db.execute(select(VarietyMap))).scalars():
        ctx.variety_map[(v.country_code, normalize(v.variety))] = v.segment_id
    ctx.open_from = await _open_months(db, set(ctx.country_aliases.values()), settings.current_year)
    ctx.previous_forecast = await _latest_forecast(db)
    return ctx


async def _open_months(db: AsyncSession, countries: set[str], year: int) -> dict[str, tuple[int, int]]:
    if get_settings().is_demo:
        clock = await db.get(DemoClock, 1)
        return {c: (clock.year, clock.month) for c in countries} if clock else {}
    rows = await db.execute(
        select(MonthlyActual.country_code, func.max(MonthlyActual.month))
        .where(MonthlyActual.year == year)
        .group_by(MonthlyActual.country_code)
    )
    closed = dict(rows.all())
    return {c: (year, (closed.get(c) or 0) + 1) for c in countries}


async def _latest_forecast(db: AsyncSession) -> dict[tuple[str, int, int, int], tuple[str, float]]:
    totals: dict[tuple[str, int, int, int, str], float] = {}
    for f in (await db.execute(select(IbpForecast))).scalars():
        key = (f.country_code, f.segment_id, f.year, f.month, f.snapshot)
        totals[key] = totals.get(key, 0.0) + f.qty_ks
    latest: dict[tuple[str, int, int, int], tuple[str, float]] = {}
    for (country, segment, year, month, snapshot), qty in totals.items():
        key = (country, segment, year, month)
        if key not in latest or snapshot > latest[key][0]:
            latest[key] = (snapshot, qty)
    return latest
