"""Budget-rate lookups. Money is stored in USD; rates convert it for display or convert local uploads into USD."""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FxRate

REPORTING = "USD"


@dataclass
class BudgetRates:
    """Units of each currency per 1 USD, by budget year."""

    by_year: dict[int, dict[str, float]] = field(default_factory=dict)
    rule: str = "same_year"
    current_year: int | None = None

    def year_for(self, year: int | None) -> int | None:
        if not self.by_year:
            return None
        if self.rule == "current_budget" and self.current_year in self.by_year:
            return self.current_year
        if year in self.by_year:
            return year
        earlier = [y for y in self.by_year if year is not None and y <= year]
        return max(earlier) if earlier else max(self.by_year)

    def rates(self, year: int | None) -> tuple[int | None, dict[str, float]]:
        chosen = self.year_for(year)
        return chosen, {REPORTING: 1.0, **(self.by_year.get(chosen, {}) if chosen is not None else {})}

    def to_usd(self, amount: float, currency: str | None, year: int | None) -> float | None:
        """None when there is no budget rate for that currency."""
        code = (currency or REPORTING).upper()
        if code == REPORTING:
            return amount
        _, rates = self.rates(year)
        rate = rates.get(code)
        return amount / rate if rate else None


async def load_budget_rates(db: AsyncSession, rule: str = "same_year", current_year: int | None = None) -> BudgetRates:
    out = BudgetRates(rule=rule, current_year=current_year)
    for r in (await db.execute(select(FxRate))).scalars():
        out.by_year.setdefault(r.budget_year, {})[r.currency] = r.per_usd
    return out
