from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class LeadRule(Base):
    """A consensus lead's plain-language lesson, compiled into a fixed-vocabulary check that runs on every entry."""

    __tablename__ = "lead_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    mega_segment_id: Mapped[str] = mapped_column(String(10), index=True)
    # None means every micro-segment / month in the mega-segment.
    segment_ids: Mapped[list | None] = mapped_column(JSON)
    months: Mapped[list | None] = mapped_column(JSON)
    metric: Mapped[str] = mapped_column(String(30))
    comparator: Mapped[str] = mapped_column(String(10))
    threshold: Mapped[float] = mapped_column(Float)
    required_driver: Mapped[str | None] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    decisions: Mapped[dict] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(40))
    source_entry_id: Mapped[str | None] = mapped_column(ForeignKey("demand_entries.id"))
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    retired_by: Mapped[str | None] = mapped_column(String(200))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
