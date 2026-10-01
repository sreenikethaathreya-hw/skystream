"""Helpers every chat tool shares: the result shape, UI rounding, policy lookup and scope errors."""

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException
from google.adk import Context
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.data_agent.policy import ChatPolicy, read_policy
from app.config import get_settings
from app.constants.demo import MONTH_NAMES
from app.models import DemandEntry, Segment
from app.services.context_service import COMMITTED_SOURCES, LIVE_STATUSES, current_period
from app.services.user_service import DEMO_COUNTRY

MAX_ROWS = 25

Result = dict[str, Any]


def ks(value: float | None) -> int | None:
    return None if value is None else round(value)


def pct(fraction: float | None) -> float | None:
    return None if fraction is None else round(fraction * 100, 1)


def error(message: str) -> Result:
    return {"status": "error", "error_message": message}


def table(source: str, columns: list[str], rows: list[list], link: tuple[str, str] | None = None, **extra) -> Result:
    out: Result = {"status": "success", "source": source, "columns": columns, "rows": rows, **extra}
    if link:
        out["link"] = {"label": link[0], "to": link[1]}
    return out


def month_name(month: int) -> str:
    return MONTH_NAMES[month - 1]


def policy_of(ctx: Context) -> ChatPolicy | None:
    return read_policy(ctx.state)


def out_of_scope(segment_id: int) -> Result:
    return error(f"Micro-segment {segment_id} is not in your scope or has no market this year.")


async def with_policy(ctx: Context, body: Callable[[ChatPolicy], Awaitable[Result]]) -> Result:
    policy = policy_of(ctx)
    if policy is None:
        return error("No access policy was set for this conversation.")
    try:
        return await body(policy)
    except HTTPException as exc:
        return error(str(exc.detail))


def capture_link(segment_id: int | None = None, month: int | None = None) -> str:
    params = [f"segment={segment_id}" if segment_id else "", f"month={month}" if month else ""]
    query = "&".join(p for p in params if p)
    return f"/capture?{query}" if query else "/capture"


def ledger_link(entry_id: str | None = None) -> str:
    return f"/ledger?entry={entry_id}" if entry_id else "/ledger"


def consensus_link(entry_id: str | None = None) -> str:
    return f"/consensus?entry={entry_id}" if entry_id else "/consensus"


def owns_segment(policy: ChatPolicy, segment: Segment) -> bool:
    """The segments a rep submits for: the seeded owner in demo, their user_scopes in real mode."""
    if policy.role != "rep":
        return False
    if get_settings().is_demo:
        return segment.owner_id == policy.user_id and policy.country_code == DEMO_COUNTRY
    return any(
        s.country_code == policy.country_code
        and (
            (s.scope_type == "micro" and s.scope_id == str(segment.id))
            or (s.scope_type == "mega" and s.scope_id == segment.mega_segment_id)
        )
        for s in policy.scopes
    )


async def my_segment_ids(db: AsyncSession, policy: ChatPolicy) -> list[int]:
    """A rep's own segments among the visible ones; leads and admins get every visible segment."""
    if policy.role != "rep":
        return list(policy.visible_segment_ids)
    segments = (await db.execute(select(Segment).where(Segment.id.in_(policy.visible_segment_ids)))).scalars()
    return [s.id for s in segments if owns_segment(policy, s)]


async def scoped_entry(db: AsyncSession, policy: ChatPolicy, entry_id: str) -> DemandEntry | Result:
    entry = await db.get(DemandEntry, entry_id)
    if entry is None or entry.country_code != policy.country_code or not policy.can_see(entry.segment_id):
        return error("That entry was not found in your scope.")
    if policy.role == "rep" and entry.user_id != policy.user_id:
        segment = await db.get(Segment, entry.segment_id)
        if segment is None or not owns_segment(policy, segment):
            return error("Reps can only open their own entries.")
    return entry


async def latest_entry(
    db: AsyncSession, policy: ChatPolicy, segment_id: int, month: int, sources: tuple[str, ...] = COMMITTED_SOURCES
) -> DemandEntry | None:
    period = await current_period(db, policy.country_code)
    return (
        await db.execute(
            select(DemandEntry)
            .where(
                DemandEntry.country_code == policy.country_code,
                DemandEntry.segment_id == segment_id,
                DemandEntry.year == period.year,
                DemandEntry.month == month,
                DemandEntry.source.in_(sources),
                DemandEntry.status.in_(LIVE_STATUSES),
            )
            .order_by(DemandEntry.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def resolve_entry(
    db: AsyncSession, policy: ChatPolicy, entry_id: str, segment_id: int, month: int
) -> DemandEntry | Result:
    """An entry by id, or the latest committed entry for a segment and month, checked against the policy."""
    if entry_id:
        return await scoped_entry(db, policy, entry_id.strip())
    if not segment_id or not 1 <= month <= 12:
        return error("Name the entry: give the micro-segment and month, or open the entry first.")
    if not policy.can_see(segment_id):
        return out_of_scope(segment_id)
    entry = await latest_entry(db, policy, segment_id, month)
    if entry is None:
        return error(f"There is no entry for micro-segment {segment_id} in {month_name(month)} yet.")
    return await scoped_entry(db, policy, entry.id)
