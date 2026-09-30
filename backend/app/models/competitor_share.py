from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CompetitorShare(Base):
    __tablename__ = "competitor_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mega_segment_id: Mapped[str] = mapped_column(String(10), index=True)
    competitor: Mapped[str] = mapped_column(String(80))
    year: Mapped[int] = mapped_column(Integer)
    share_pct: Mapped[float] = mapped_column(Float)
    value_eur: Mapped[float] = mapped_column(Float)
    trend: Mapped[str | None] = mapped_column(String(30))
