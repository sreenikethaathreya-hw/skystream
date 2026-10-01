from sqlalchemy import Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FxRate(Base):
    """Finance budget rate: units of `currency` per 1 USD for a budget year. Money is stored in USD."""

    __tablename__ = "fx_rates"
    __table_args__ = (UniqueConstraint("budget_year", "currency", name="uq_fx_rates_year_currency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    budget_year: Mapped[int] = mapped_column(Integer, index=True)
    currency: Mapped[str] = mapped_column(String(3))
    currency_name: Mapped[str | None] = mapped_column(String(80))
    per_usd: Mapped[float] = mapped_column(Float)
    batch_id: Mapped[str | None] = mapped_column(String(36))
