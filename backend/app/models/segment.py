from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Segment(Base):
    """Product-hierarchy micro-segment. IDs are global; country-specific figures live in the year tables."""

    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    description: Mapped[str] = mapped_column(String(200))
    species: Mapped[str | None] = mapped_column(String(80), index=True)
    cycle: Mapped[str | None] = mapped_column(String(60))
    color: Mapped[str | None] = mapped_column(String(30))
    ecology: Mapped[str | None] = mapped_column(String(60))
    mega_segment_id: Mapped[str] = mapped_column(String(10), index=True)
    mega_segment_desc: Mapped[str] = mapped_column(String(100))
    profile: Mapped[str] = mapped_column(String(30))
    # Demo mode only; real mode assigns reps through user_scopes.
    owner_id: Mapped[str | None] = mapped_column(String(200), index=True)
