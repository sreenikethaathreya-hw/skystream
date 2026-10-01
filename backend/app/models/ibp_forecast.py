from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class IbpForecast(Base):
    """A rep's IBP demand by variety and month, as exported in a SAC MDL_LC_FP_Q050 snapshot."""

    __tablename__ = "ibp_forecasts"
    __table_args__ = (
        UniqueConstraint(
            "country_code", "segment_id", "variety", "year", "month", "snapshot", name="uq_ibp_forecasts_key"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("segments.id"), index=True)
    variety: Mapped[str] = mapped_column(String(120))
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[str] = mapped_column(String(40), index=True)
    qty_ks: Mapped[float] = mapped_column(Float)
    value_usd: Mapped[float | None] = mapped_column(Float)
    planner_id: Mapped[str | None] = mapped_column(String(200))
    batch_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
