from sqlalchemy import Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Seasonality(Base):
    """Uploaded monthly weights (normalized to 1 per key) used to split the yearly plan into months."""

    __tablename__ = "seasonality"
    __table_args__ = (UniqueConstraint("country_code", "scope_type", "scope_id", "month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    scope_type: Mapped[str] = mapped_column(String(10))
    scope_id: Mapped[str] = mapped_column(String(20))
    month: Mapped[int] = mapped_column(Integer)
    weight: Mapped[float] = mapped_column(Float)
