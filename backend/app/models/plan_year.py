from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlanYear(Base):
    __tablename__ = "plan_years"
    __table_args__ = (UniqueConstraint("country_code", "segment_id", "year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("segments.id"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    qty_ks: Mapped[float] = mapped_column(Float)
    value_eur: Mapped[float] = mapped_column(Float)
    net_price: Mapped[float] = mapped_column(Float)
    fpi_qty_ks: Mapped[float] = mapped_column(Float, default=0.0)
    comment: Mapped[str | None] = mapped_column(Text)
