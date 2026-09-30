from sqlalchemy import Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MonthlyPlan(Base):
    __tablename__ = "monthly_plan"
    __table_args__ = (UniqueConstraint("segment_id", "year", "month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("segments.id"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    qty_ks: Mapped[float] = mapped_column(Float)
