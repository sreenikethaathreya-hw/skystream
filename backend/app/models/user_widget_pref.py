from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class UserWidgetPref(Base):
    """Which built-in Capture widgets a user shows, in the order they added them. Every widget starts hidden."""

    __tablename__ = "user_widget_prefs"

    # Demo users are not rows in app_users, so this is a plain id like chat_actions.user_id.
    user_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    visible: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
