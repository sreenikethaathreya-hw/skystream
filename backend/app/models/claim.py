from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[str] = mapped_column(ForeignKey("demand_entries.id"), unique=True)
    driver: Mapped[str] = mapped_column(String(40))
    direction: Mapped[str] = mapped_column(String(10))
    magnitude: Mapped[float | None] = mapped_column(Float)
    competitor: Mapped[str | None] = mapped_column(String(80))
    variety: Mapped[str | None] = mapped_column(String(80))
    evidence_source: Mapped[str | None] = mapped_column(String(40))
    verifiable: Mapped[float | None] = mapped_column(Float)
    consistent_with_notes: Mapped[float | None] = mapped_column(Float)
    specificity: Mapped[float | None] = mapped_column(Float)
    addresses_flags: Mapped[float | None] = mapped_column(Float)
    summary: Mapped[str | None] = mapped_column(Text)
    decisions: Mapped[dict] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(30))
    signal: Mapped[str] = mapped_column(String(40))
    check_year: Mapped[int] = mapped_column(Integer)
    check_month: Mapped[int] = mapped_column(Integer)
    resolution: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    resolution_detail: Mapped[dict | None] = mapped_column(JSON)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
