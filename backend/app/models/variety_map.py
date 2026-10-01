from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VarietyMap(Base):
    """Which micro-segment a variety belongs to, for SAC exports that only carry the variety."""

    __tablename__ = "variety_map"
    __table_args__ = (UniqueConstraint("country_code", "variety", name="uq_variety_map_country_variety"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    # Stored normalized (upper case, single spaces) so export spellings match.
    variety: Mapped[str] = mapped_column(String(120))
    segment_id: Mapped[int] = mapped_column(ForeignKey("segments.id"))
