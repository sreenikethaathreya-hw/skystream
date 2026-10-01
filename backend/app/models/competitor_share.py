from sqlalchemy import Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CompetitorShare(Base):
    __tablename__ = "competitor_shares"
    # Explicit name: the convention-generated one exceeds Postgres's 63-character identifier limit.
    __table_args__ = (
        UniqueConstraint(
            "country_code", "mega_segment_id", "competitor", "year", name="uq_competitor_shares_key"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    mega_segment_id: Mapped[str] = mapped_column(String(10), index=True)
    competitor: Mapped[str] = mapped_column(String(80))
    year: Mapped[int] = mapped_column(Integer)
    share_pct: Mapped[float] = mapped_column(Float)
    value_usd: Mapped[float] = mapped_column(Float)
    trend: Mapped[str | None] = mapped_column(String(30))
