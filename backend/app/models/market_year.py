from sqlalchemy import JSON, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MarketYear(Base):
    __tablename__ = "market_years"
    __table_args__ = (UniqueConstraint("segment_id", "year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("segments.id"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    hectares: Mapped[float] = mapped_column(Float)
    qty_ks: Mapped[float] = mapped_column(Float)
    density: Mapped[float] = mapped_column(Float)
    price_exseed: Mapped[float] = mapped_column(Float)
    price_farmgate: Mapped[float] = mapped_column(Float)
    notes: Mapped[dict] = mapped_column(JSON, default=dict)
