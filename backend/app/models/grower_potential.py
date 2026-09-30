from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GrowerPotential(Base):
    __tablename__ = "grower_potential"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    # CRM "Crop Local", which matches the mega-segment description (e.g. SWEET PEPPER BLOCKY PGH).
    crop_local: Mapped[str] = mapped_column(String(120), index=True)
    variety: Mapped[str | None] = mapped_column(String(80))
    owner: Mapped[str] = mapped_column(String(20))
    hectares: Mapped[float] = mapped_column(Float)
    density: Mapped[float] = mapped_column(Float)
    region: Mapped[str | None] = mapped_column(String(80))
