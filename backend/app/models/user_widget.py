from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class UserWidget(Base):
    """A table a user pinned from the chat: the read tool and its arguments, never the figures.

    Each view re-runs the tool under the viewer's current policy, so the widget stays fresh and in scope.
    """

    __tablename__ = "user_widgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    title: Mapped[str] = mapped_column(String(120))
    tool: Mapped[str] = mapped_column(String(60))
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    country_code: Mapped[str] = mapped_column(String(2))
    mega_segment_id: Mapped[str] = mapped_column(String(10))
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
