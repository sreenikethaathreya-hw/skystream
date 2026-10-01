from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MonthlyActual(Base):
    """Monthly Syngenta sales. In demo mode future months exist but stay hidden behind the demo clock."""

    __tablename__ = "monthly_actuals"
    __table_args__ = (UniqueConstraint("country_code", "segment_id", "year", "month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("segments.id"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    qty_ks: Mapped[float] = mapped_column(Float)
    value_usd: Mapped[float] = mapped_column(Float)
