from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class EntryNote(Base):
    """A short message between the consensus lead and the rep about one demand entry."""

    __tablename__ = "entry_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[str] = mapped_column(ForeignKey("demand_entries.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    # app or chat
    via: Mapped[str] = mapped_column(String(10), default="app")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
