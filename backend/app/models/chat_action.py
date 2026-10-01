from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class ChatAction(Base):
    """One change the chat assistant made or was refused, written by the AuditPlugin for every write attempt."""

    __tablename__ = "chat_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    session_id: Mapped[str] = mapped_column(String(128))
    invocation_id: Mapped[str] = mapped_column(String(128))
    tool: Mapped[str] = mapped_column(String(60))
    target_type: Mapped[str | None] = mapped_column(String(30))
    target_id: Mapped[str | None] = mapped_column(String(64), index=True)
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    # success, error or blocked
    status: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
