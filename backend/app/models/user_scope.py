from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserScope(Base):
    """What a user covers: a whole mega-segment or a single micro-segment in one country."""

    __tablename__ = "user_scopes"
    __table_args__ = (UniqueConstraint("user_id", "country_code", "scope_type", "scope_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id", ondelete="CASCADE"), index=True)
    country_code: Mapped[str] = mapped_column(String(2))
    # "mega" (scope_id = mega-segment code such as SP01) or "micro" (scope_id = micro-segment id)
    scope_type: Mapped[str] = mapped_column(String(10))
    scope_id: Mapped[str] = mapped_column(String(20))
