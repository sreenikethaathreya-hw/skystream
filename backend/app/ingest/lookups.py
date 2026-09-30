from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Country, Segment


def normalize(value: str) -> str:
    return " ".join(str(value).replace("\xa0", " ").split()).upper()


@dataclass
class ImportContext:
    """Reference data validators need: country spellings and the product hierarchy already loaded."""

    country_aliases: dict[str, str] = field(default_factory=dict)
    segment_ids: set[int] = field(default_factory=set)
    segment_by_desc: dict[str, int] = field(default_factory=dict)
    mega_by_segment: dict[int, str] = field(default_factory=dict)
    grower_ha_cap: float = 500.0

    @property
    def mega_ids(self) -> set[str]:
        return set(self.mega_by_segment.values())

    def country(self, value) -> str | None:
        if value is None:
            return None
        return self.country_aliases.get(normalize(value))


async def load_context(db: AsyncSession, grower_ha_cap: float) -> ImportContext:
    ctx = ImportContext(grower_ha_cap=grower_ha_cap)
    for c in (await db.execute(select(Country))).scalars():
        for alias in [c.code, c.name, *(c.aliases or [])]:
            ctx.country_aliases[normalize(alias)] = c.code
    for s in (await db.execute(select(Segment))).scalars():
        ctx.segment_ids.add(s.id)
        ctx.segment_by_desc[normalize(s.description)] = s.id
        ctx.mega_by_segment[s.id] = s.mega_segment_id
    return ctx
