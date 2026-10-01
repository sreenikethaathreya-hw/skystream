"""Read-only chat tools for data admins (uploads, access, data quality) plus the settings explainer for everyone.

Admins change uploads, users and settings only on the admin pages; these tools link there.
"""

from google.adk import Context
from sqlalchemy import select

from app.ai.data_agent.policy import ChatPolicy
from app.ai.data_agent.rep_tools import FLAG_CHECKS, THRESHOLD_UNITS, threshold_text
from app.ai.data_agent.tool_support import MAX_ROWS, Result, error, table, with_policy
from app.config import get_settings
from app.constants.demo import DEMO_USERS
from app.database import async_session
from app.models import AppUser, Segment, UploadBatch, UserScope
from app.services import export_service
from app.services.context_service import segment_label
from app.services.settings_service import get_app_settings


def _admin_only(policy: ChatPolicy) -> Result | None:
    return None if policy.is_admin else error("Only data admins can see that.")


async def get_upload_status(ctx: Context) -> Result:
    """Lists recent uploads by kind: when each was committed, by whom, and which previews failed or wait.

    Use this when an admin asks what was uploaded, what failed or what still waits to be committed.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[kind, filename, status, accepted, rejected,
      warnings, uploaded_by, when], ...]}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if (blocked := _admin_only(policy)) is not None:
            return blocked
        async with async_session() as db:
            batches = (
                await db.execute(select(UploadBatch).order_by(UploadBatch.created_at.desc()).limit(MAX_ROWS))
            ).scalars().all()
        rows = [
            [
                b.kind, b.filename, b.status, b.accepted, b.rejected, b.warnings, b.uploaded_by,
                (b.committed_at or b.created_at).strftime("%Y-%m-%d %H:%M"),
            ]
            for b in batches
        ]
        waiting = sum(1 for b in batches if b.status == "previewed")
        return table(
            "Recent uploads",
            ["Kind", "File", "Status", "Accepted", "Rejected", "Warnings", "Uploaded by", "When"],
            rows,
            link=("Open Admin: data", "/admin/data"),
            waiting_to_commit=waiting,
            failed=sum(1 for b in batches if b.status == "failed"),
        )

    return await with_policy(ctx, body)


async def list_user_scopes(segment_id: int, user_name: str, ctx: Context) -> Result:
    """Shows who can see and submit what: users, roles and their country and segment scopes.

    Use this for "who covers 2482" or "what can Rep A submit".

    Args:
      segment_id: A micro-segment number to find who covers it, or 0 for every user.
      user_name: Part of a user's name or email, or an empty string for every user.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[user, role, active, scopes], ...]}.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if (blocked := _admin_only(policy)) is not None:
            return blocked
        needle = user_name.strip().lower()
        async with async_session() as db:
            segment = await db.get(Segment, segment_id) if segment_id else None
            if segment_id and segment is None:
                return error(f"Micro-segment {segment_id} does not exist.")
            if get_settings().is_demo:
                owned = (await db.execute(select(Segment).order_by(Segment.id))).scalars().all()
                rows = []
                for u in DEMO_USERS.values():
                    mine = [s for s in owned if s.owner_id == u.id]
                    scopes = "all segments" if u.role != "rep" else ", ".join(segment_label(s) for s in mine)
                    covers = segment is None or u.role != "rep" or segment.owner_id == u.id
                    if covers and (not needle or needle in u.name.lower() or needle in u.id):
                        rows.append([u.name, u.role, "yes", scopes or "none"])
            else:
                users = (await db.execute(select(AppUser).order_by(AppUser.role, AppUser.name))).scalars().all()
                scopes = (await db.execute(select(UserScope))).scalars().all()
                rows = []
                for u in users:
                    mine = [s for s in scopes if s.user_id == u.id]
                    covers = segment is None or u.role != "rep" or any(
                        (s.scope_type == "micro" and s.scope_id == str(segment.id))
                        or (s.scope_type == "mega" and s.scope_id == segment.mega_segment_id)
                        for s in mine
                    )
                    if covers and (not needle or needle in u.name.lower() or needle in u.id):
                        rows.append([
                            u.name, u.role, "yes" if u.active else "no",
                            ", ".join(f"{s.country_code} {s.scope_type} {s.scope_id}" for s in mine) or "none",
                        ])
        return table(
            "Users and scopes" + (f" covering micro-segment {segment_id}" if segment_id else ""),
            ["User", "Role", "Active", "Scopes"],
            rows[:MAX_ROWS],
            link=("Open Admin: users", "/admin/users"),
        )

    return await with_policy(ctx, body)


async def get_settings_summary(ctx: Context) -> Result:
    """Explains the plausibility thresholds and which flag each one drives; admins also see the other settings.

    Use this for "what is the share jump threshold", "why does range too wide fire" or "how is Skystream set up".

    Returns:
      On success: {'status': 'success', 'columns': ['Setting', 'Value', 'Drives'], 'rows': [...]}.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        async with async_session() as db:
            settings = await get_app_settings(db)
        drives = {field: code for code, (_, field) in FLAG_CHECKS.items() if field}
        rows = [
            [field.replace("_", " "), threshold_text(field, settings.thresholds), drives.get(field, "")]
            for field in THRESHOLD_UNITS
        ]
        if policy.is_admin:
            rows += [
                ["demand source", settings.demand_source, "where reps' numbers come from"],
                ["external AI allowed", "yes" if settings.external_ai_allowed else "no", "Jev on real text"],
                ["chat changes allowed", "yes" if settings.chat_writes_allowed else "no", "assistant write tools"],
                ["claim baseline", settings.claim_baseline, "what claims are checked against"],
                ["actuals hold days", str(settings.actuals_hold_days), "delay before claims resolve"],
                ["planning year", str(settings.current_year), "open year"],
            ]
        return table(
            "Settings",
            ["Setting", "Value", "Drives"],
            rows,
            link=("Open Admin: settings", "/admin/settings") if policy.is_admin else None,
        )

    return await with_policy(ctx, body)


async def get_data_quality(ctx: Context) -> Result:
    """Summarises the data-quality report: per upload or seed section, the headline counts and warnings.

    Use this when an admin asks about data quality, missing data or rejected rows.

    Returns:
      On success: {'status': 'success', 'columns': ['Section', 'Item', 'Value'], 'rows': [...]}.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if (blocked := _admin_only(policy)) is not None:
            return blocked
        async with async_session() as db:
            report = await export_service.data_quality(db)
        rows = []
        for section, value in report.items():
            if isinstance(value, dict):
                for key, item in value.items():
                    if isinstance(item, str | int | float | bool) or item is None:
                        rows.append([section, key, item])
            elif isinstance(value, str | int | float | bool):
                rows.append([section, "", value])
        return table("Data quality", ["Section", "Item", "Value"], rows[: MAX_ROWS * 2],
                     link=("Open Data quality", "/data-quality"))

    return await with_policy(ctx, body)


ADMIN_TOOLS = [get_upload_status, list_user_scopes, get_settings_summary, get_data_quality]
