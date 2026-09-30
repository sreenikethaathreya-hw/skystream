from datetime import datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class DemoClock(Base):
    """Single-row simulated calendar. Actuals are revealed for months before (year, month)."""

    __tablename__ = "demo_clock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
