from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class RepTrackRecord(Base):
    __tablename__ = "rep_track_records"

    user_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    entries_resolved: Mapped[int] = mapped_column(Integer, default=0)
    bias_pct: Mapped[float | None] = mapped_column(Float)
    claim_hit_rate: Mapped[float | None] = mapped_column(Float)
    range_coverage: Mapped[float | None] = mapped_column(Float)
    confirmed: Mapped[int] = mapped_column(Integer, default=0)
    contradicted: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
