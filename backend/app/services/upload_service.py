"""Admin uploads: validate into a preview batch, then commit (or discard) it."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.decision_provider import decision_policy
from app.config import get_settings
from app.ingest.commit import COMMITTERS
from app.ingest.lookups import load_context
from app.ingest.reader import read_upload
from app.ingest.registry import UPLOAD_KINDS
from app.ingest.report import ImportFailure
from app.ingest.template_files import TEMPLATES
from app.models import DemoClock, UploadBatch
from app.models.base import utcnow
from app.schemas.api import BatchOut, UploadKindOut
from app.services.monthly_plan_service import rebuild_monthly_plan
from app.services.resolution_service import resolve_month
from app.services.settings_service import get_app_settings
from app.services.track_record_service import recompute_track_records
from app.services.user_service import CurrentUser

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
PLAN_REBUILD_KINDS = {"plan", "seasonality", "actuals"}


def batch_out(batch: UploadBatch) -> BatchOut:
    return BatchOut.model_validate(batch)


async def list_kinds(db: AsyncSession) -> list[UploadKindOut]:
    committed = (
        (await db.execute(select(UploadBatch).where(UploadBatch.status == "committed"))).scalars().all()
    )
    latest: dict[str, object] = {}
    for b in committed:
        if b.committed_at and (b.kind not in latest or b.committed_at > latest[b.kind]):
            latest[b.kind] = b.committed_at
    return [
        UploadKindOut(
            kind=k.kind,
            label=k.label,
            source=k.source,
            required=k.required,
            template=k.kind in TEMPLATES,
            last_committed_at=latest.get(k.kind),
        )
        for k in UPLOAD_KINDS.values()
    ]


async def preview(db: AsyncSession, user: CurrentUser, kind: str, filename: str, content: bytes) -> BatchOut:
    spec = UPLOAD_KINDS.get(kind)
    if spec is None:
        raise HTTPException(status_code=400, detail=f"Unknown upload kind '{kind}'")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Files are limited to 25 MB")
    settings = await get_app_settings(db)
    ctx = await load_context(db, settings.grower_ha_cap)
    batch = UploadBatch(kind=kind, filename=filename, uploaded_by=user.id, status="previewed")
    try:
        frame = read_upload(content, filename, list(spec.sheets))
        rows, report = spec.validator(frame, ctx)
        batch.rows_read, batch.accepted, batch.rejected = report.rows_read, report.accepted, report.rejected
        batch.warnings = report.warning_count
        batch.report = {
            **report.to_dict(),
            "countries": sorted({r["countryCode"] for r in rows if "countryCode" in r}),
        }
        batch.payload = rows
        if not rows:
            batch.status = "failed"
            batch.report["error"] = "No valid rows to load"
    except ImportFailure as exc:
        batch.status = "failed"
        batch.report = {"kind": kind, "error": str(exc)}
    db.add(batch)
    await db.commit()
    return batch_out(batch)


async def _get_batch(db: AsyncSession, batch_id: str) -> UploadBatch:
    batch = await db.get(UploadBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    if batch.status != "previewed":
        raise HTTPException(status_code=409, detail=f"This upload is already {batch.status}")
    return batch


async def discard(db: AsyncSession, batch_id: str) -> BatchOut:
    batch = await _get_batch(db, batch_id)
    batch.status, batch.payload = "discarded", None
    await db.commit()
    return batch_out(batch)


async def _supersede_earlier(db: AsyncSession, batch: UploadBatch) -> None:
    countries = set(batch.report.get("countries", []))
    earlier = (
        await db.execute(
            select(UploadBatch).where(
                UploadBatch.kind == batch.kind, UploadBatch.status == "committed", UploadBatch.id != batch.id
            )
        )
    ).scalars()
    for old in earlier:
        if set(old.report.get("countries", [])) <= countries:
            old.status = "superseded"


async def _close_actual_months(db: AsyncSession, rows: list[dict]) -> dict:
    settings = await get_app_settings(db)
    policy = decision_policy(settings)
    months = sorted({(r["countryCode"], r["year"], r["month"]) for r in rows})
    resolved = []
    for country, year, month in months:
        resolved += await resolve_month(db, year, month, policy, country)
    if get_settings().is_demo:
        clock = await db.get(DemoClock, 1)
        in_year = [m for _, y, m in months if clock is not None and y == clock.year]
        if clock is not None and in_year:
            clock.month = max(clock.month, max(in_year) + 1)
    await db.flush()
    await recompute_track_records(db)
    return {
        "monthsClosed": [f"{c} {y}-{m:02d}" for c, y, m in months],
        "claimsResolved": len(resolved),
        "confirmed": sum(r.resolution == "confirmed" for r in resolved),
        "contradicted": sum(r.resolution == "contradicted" for r in resolved),
        "inconclusive": sum(r.resolution == "inconclusive" for r in resolved),
    }


async def commit(db: AsyncSession, batch_id: str) -> BatchOut:
    batch = await _get_batch(db, batch_id)
    rows = batch.payload or []
    summary = await COMMITTERS[batch.kind](db, rows)
    await db.flush()
    countries = {r["countryCode"] for r in rows if "countryCode" in r}
    rebuild = batch.kind in PLAN_REBUILD_KINDS and not (batch.kind == "actuals" and get_settings().is_demo)
    if rebuild:
        summary["monthlyPlanBasis"] = await rebuild_monthly_plan(db, countries)
    if batch.kind == "actuals":
        summary.update(await _close_actual_months(db, rows))
    await _supersede_earlier(db, batch)
    batch.status, batch.committed_at, batch.commit_summary, batch.payload = (
        "committed",
        utcnow(),
        summary,
        None,
    )
    await db.commit()
    return batch_out(batch)


async def history(db: AsyncSession, limit: int = 50) -> list[BatchOut]:
    batches = (
        (await db.execute(select(UploadBatch).order_by(UploadBatch.created_at.desc()).limit(limit)))
        .scalars()
        .all()
    )
    return [batch_out(b) for b in batches]


async def data_quality_sections(db: AsyncSession) -> dict:
    committed = (
        (
            await db.execute(
                select(UploadBatch)
                .where(UploadBatch.status == "committed")
                .order_by(UploadBatch.committed_at)
            )
        )
        .scalars()
        .all()
    )
    sections: dict[str, dict] = {}
    for b in committed:
        report = b.report or {}
        sections[b.kind] = {
            "file": b.filename,
            "committedAt": b.committed_at.isoformat() if b.committed_at else None,
            "rowsRead": b.rows_read,
            "accepted": b.accepted,
            "rejected": b.rejected,
            **{w["message"]: w["count"] for w in report.get("warnings", [])},
            **report.get("info", {}),
        }
    return sections
