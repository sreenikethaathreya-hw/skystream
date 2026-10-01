"""Notes between the consensus lead and the rep on a demand entry: the lead asks, the rep answers."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DemandEntry, EntryNote, Segment
from app.schemas.api import EntryOut, NoteOut
from app.services.user_service import CurrentUser, can_submit, user_names


def _out(note: EntryNote, names: dict[str, str]) -> NoteOut:
    return NoteOut(
        id=note.id,
        entry_id=note.entry_id,
        user_id=note.user_id,
        user_name=names.get(note.user_id, note.user_id),
        body=note.body,
        via=note.via,
        created_at=note.created_at,
    )


async def notes_for(db: AsyncSession, entry_ids: list[str]) -> dict[str, list[NoteOut]]:
    if not entry_ids:
        return {}
    rows = (
        await db.execute(
            select(EntryNote).where(EntryNote.entry_id.in_(entry_ids)).order_by(EntryNote.created_at, EntryNote.id)
        )
    ).scalars()
    names = await user_names(db)
    out: dict[str, list[NoteOut]] = {}
    for note in rows:
        out.setdefault(note.entry_id, []).append(_out(note, names))
    return out


async def attach_notes(db: AsyncSession, entries: list[EntryOut]) -> list[EntryOut]:
    notes = await notes_for(db, [e.id for e in entries])
    for entry in entries:
        entry.notes = notes.get(entry.id, [])
    return entries


async def can_note(db: AsyncSession, user: CurrentUser, entry: DemandEntry) -> bool:
    if user.role in ("lead", "admin") or entry.user_id == user.id:
        return True
    segment = await db.get(Segment, entry.segment_id)
    return segment is not None and can_submit(user, entry.country_code, segment)


async def add_note(db: AsyncSession, user: CurrentUser, entry_id: str, body: str, via: str = "app") -> NoteOut:
    entry = await db.get(DemandEntry, entry_id)
    if entry is None or entry.status == "superseded":
        raise HTTPException(status_code=404, detail="Entry not found")
    if not await can_note(db, user, entry):
        raise HTTPException(status_code=403, detail="Only the consensus lead or the entry's rep can add a note")
    text = body.strip()
    if not text:
        raise HTTPException(status_code=422, detail="A note needs some text")
    note = EntryNote(entry_id=entry_id, user_id=user.id, body=text[:600], via=via)
    db.add(note)
    await db.commit()
    return _out(note, await user_names(db))


async def list_notes(db: AsyncSession, entry_id: str) -> list[NoteOut]:
    if await db.get(DemandEntry, entry_id) is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return (await notes_for(db, [entry_id])).get(entry_id, [])
