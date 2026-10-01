import csv
import io
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants.demo import MONTH_NAMES
from app.models import DemandEntry, Segment
from app.services.context_service import COMMITTED_SOURCES, segment_label
from app.services.entry_service import scope_filter
from app.services.rep_service import is_weak, track_records
from app.services.upload_service import data_quality_sections
from app.services.user_service import user_names

HEADER = [
    "country",
    "segment_id",
    "segment",
    "year",
    "month",
    "low_ks",
    "mid_ks",
    "high_ks",
    "build_to",
    "build_ks",
    "rep",
    "reason",
    "source",
]


async def supply_csv(db: AsyncSession, country: str | None = None, mega: str | None = None) -> str:
    records = await track_records(db)
    segments = {s.id: s for s in (await db.execute(select(Segment))).scalars()}
    names = await user_names(db)
    query = (
        select(DemandEntry)
        .where(DemandEntry.source.in_(COMMITTED_SOURCES), DemandEntry.status == "approved")
        .order_by(DemandEntry.country_code, DemandEntry.segment_id, DemandEntry.year, DemandEntry.month)
    )
    entries = (await db.execute(scope_filter(query, country, mega))).scalars()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADER)
    for e in entries:
        wide = any(f["code"] == "range_too_wide" for f in e.flags or [])
        weak = is_weak(records.get(e.user_id))
        build_to = "low" if wide or weak else "mid"
        reason = "wide range" if wide else "weak track record" if weak else "confident line"
        writer.writerow(
            [
                e.country_code,
                e.segment_id,
                segment_label(segments[e.segment_id]),
                e.year,
                MONTH_NAMES[e.month - 1],
                round(e.low),
                round(e.value),
                round(e.high),
                build_to,
                round(e.low if build_to == "low" else e.value),
                names.get(e.user_id, e.user_id),
                reason,
                "IBP" if e.source == "ibp" else "Skystream",
            ]
        )
    return buffer.getvalue()


async def data_quality(db: AsyncSession) -> dict:
    """Demo: the seed builder's report. Real: the latest committed upload of each kind."""
    sections = await data_quality_sections(db)
    if get_settings().is_demo:
        path = get_settings().seed_dir / "ingest_report.json"
        seed_report = json.loads(path.read_text()) if path.exists() else {}
        return {**seed_report, **{f"upload: {k}": v for k, v in sections.items()}}
    return sections
