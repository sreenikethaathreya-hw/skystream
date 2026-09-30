from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Country(Base):
    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    # Spellings seen in the exports, matched case-insensitively (e.g. "SPAIN", "España").
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
