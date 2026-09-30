import csv
import io
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants.demo import DEMO_USERS, MONTH_NAMES
from app.models import DemandEntry, Segment
from app.services.context_service import get_clock, segment_label
from app.services.rep_service import is_weak, track_records


async def supply_csv(db: AsyncSession) -> str:
    clock = await get_clock(db)
    records = await track_records(db)
    segments = {s.id: s for s in (await db.execute(select(Segment))).scalars()}
    entries = (
        await db.execute(
            select(DemandEntry)
            .where(
                DemandEntry.year == clock.year, DemandEntry.source == "live", DemandEntry.status == "approved"
            )
            .order_by(DemandEntry.segment_id, DemandEntry.month)
        )
    ).scalars()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
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
        ]
    )
    for e in entries:
        wide = any(f["code"] == "range_too_wide" for f in e.flags or [])
        weak = is_weak(records.get(e.user_id))
        build_to = "low" if wide or weak else "mid"
        reason = "wide range" if wide else "weak track record" if weak else "confident line"
        user = DEMO_USERS.get(e.user_id)
        writer.writerow(
            [
                e.segment_id,
                segment_label(segments[e.segment_id]),
                e.year,
                MONTH_NAMES[e.month - 1],
                round(e.low),
                round(e.value),
                round(e.high),
                build_to,
                round(e.low if build_to == "low" else e.value),
                user.name if user else e.user_id,
                reason,
            ]
        )
    return buffer.getvalue()


def ingest_report() -> dict:
    path = get_settings().seed_dir / "ingest_report.json"
    return json.loads(path.read_text()) if path.exists() else {}
