"""Per-user Capture widgets: which built-in widgets are shown, and tables pinned from the chat.

A pinned widget stores a read tool and its arguments, never figures. Running it rebuilds the caller's chat policy
for the widget's scope and calls the tool directly (no model), so the same scope and role checks apply as in chat.
"""

import inspect
import re
from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.data_agent.history import sources_and_links, with_call_args
from app.ai.data_agent.policy import (
    ADMIN_ONLY_TOOLS,
    LEAD_ONLY_TOOLS,
    PINNABLE_TOOLS,
    POLICY_KEY,
    ChatPolicy,
    policy_for,
)
from app.ai.data_agent.toolset import ALL_TOOLS
from app.ai.offline_chat import ToolState
from app.config import get_settings
from app.models import UserWidget, UserWidgetPref
from app.schemas.chat import ChatSourceOut
from app.schemas.widgets import (
    UserWidgetIn,
    UserWidgetOut,
    WidgetPrefsIn,
    WidgetPrefsOut,
    WidgetRunOut,
    WidgetsOut,
)
from app.services.context_service import resolve_scope, visible_segments
from app.services.settings_service import get_app_settings
from app.services.user_service import CurrentUser

MAX_CUSTOM_WIDGETS = 12
WIDGET_ID = re.compile(r"^[a-z][a-z0-9_]{0,39}$")

Tool = Callable[..., Awaitable[dict]]
PINNABLE: dict[str, Tool] = {fn.__name__: fn for fn in ALL_TOOLS if fn.__name__ in PINNABLE_TOOLS}


def _params(fn: Tool) -> list[str]:
    return [name for name in inspect.signature(fn).parameters if name != "ctx"]


def _check_tool(tool: str, args: dict, role: str) -> Tool:
    fn = PINNABLE.get(tool)
    if fn is None:
        raise HTTPException(status_code=400, detail="That table cannot be pinned as a widget")
    if (tool in LEAD_ONLY_TOOLS and role not in ("lead", "admin")) or (tool in ADMIN_ONLY_TOOLS and role != "admin"):
        raise HTTPException(status_code=403, detail="That table is not available to your role")
    expected = set(_params(fn))
    if set(args) != expected:
        raise HTTPException(status_code=400, detail=f"{tool} takes exactly: {', '.join(sorted(expected)) or 'nothing'}")
    return fn


async def get_widgets(db: AsyncSession, user: CurrentUser) -> WidgetsOut:
    pref = await db.get(UserWidgetPref, user.id)
    custom = (
        await db.execute(
            select(UserWidget).where(UserWidget.user_id == user.id).order_by(UserWidget.position, UserWidget.id)
        )
    ).scalars()
    return WidgetsOut(
        prefs=WidgetPrefsOut(visible=list(pref.visible) if pref else []),
        custom=[UserWidgetOut.model_validate(w) for w in custom],
    )


async def set_prefs(db: AsyncSession, user: CurrentUser, body: WidgetPrefsIn) -> WidgetPrefsOut:
    if any(not WIDGET_ID.match(w) for w in body.visible):
        raise HTTPException(status_code=400, detail="Widget ids are lower-case words joined by underscores")
    visible = list(dict.fromkeys(body.visible))
    pref = await db.get(UserWidgetPref, user.id)
    if pref is None:
        db.add(UserWidgetPref(user_id=user.id, visible=visible))
    else:
        pref.visible = visible
    await db.commit()
    return WidgetPrefsOut(visible=visible)


async def create_widget(db: AsyncSession, user: CurrentUser, body: UserWidgetIn) -> UserWidgetOut:
    _check_tool(body.tool, body.args, user.role)
    country, mega = await resolve_scope(db, user, body.country_code, body.mega_segment_id)
    count, last = (
        await db.execute(
            select(func.count(UserWidget.id), func.max(UserWidget.position)).where(UserWidget.user_id == user.id)
        )
    ).one()
    if count >= MAX_CUSTOM_WIDGETS:
        raise HTTPException(status_code=400, detail=f"You can pin up to {MAX_CUSTOM_WIDGETS} widgets; remove one first")
    widget = UserWidget(
        user_id=user.id,
        title=body.title.strip(),
        tool=body.tool,
        args=body.args,
        country_code=country,
        mega_segment_id=mega,
        position=(last or 0) + 1,
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return UserWidgetOut.model_validate(widget)


async def _own_widget(db: AsyncSession, user: CurrentUser, widget_id: int) -> UserWidget:
    widget = await db.get(UserWidget, widget_id)
    if widget is None or widget.user_id != user.id:
        raise HTTPException(status_code=404, detail="Widget not found")
    return widget


async def rename_widget(db: AsyncSession, user: CurrentUser, widget_id: int, title: str) -> UserWidgetOut:
    widget = await _own_widget(db, user, widget_id)
    widget.title = title.strip()
    await db.commit()
    await db.refresh(widget)
    return UserWidgetOut.model_validate(widget)


async def delete_widget(db: AsyncSession, user: CurrentUser, widget_id: int) -> None:
    widget = await _own_widget(db, user, widget_id)
    await db.delete(widget)
    await db.commit()


async def _policy(db: AsyncSession, user: CurrentUser, country: str, mega: str) -> ChatPolicy:
    country, mega = await resolve_scope(db, user, country, mega)
    segment_ids = [s.id for s in await visible_segments(db, user, country, mega)]
    app_settings = await get_app_settings(db)
    return policy_for(
        user, country, mega, segment_ids, get_settings().is_demo, demand_source=app_settings.demand_source
    )


async def run_widget(db: AsyncSession, user: CurrentUser, widget_id: int) -> WidgetRunOut:
    widget = await _own_widget(db, user, widget_id)
    tool, args = widget.tool, dict(widget.args or {})
    try:
        fn = _check_tool(tool, args, user.role)
        policy = await _policy(db, user, widget.country_code, widget.mega_segment_id)
    except HTTPException as exc:
        return WidgetRunOut(status="error", error=str(exc.detail))
    requested = [args.get("segment_id") or 0, *(args.get("segment_ids") or [])]
    if any(int(s) and not policy.can_see(int(s)) for s in requested):
        return WidgetRunOut(status="error", error="A segment in this widget is no longer in your scope.")
    # Release the read transaction: tools open their own sessions.
    await db.rollback()
    result = await fn(**args, ctx=ToolState(state={POLICY_KEY: policy.model_dump()}))
    if result.get("status") != "success":
        return WidgetRunOut(status="error", error=str(result.get("error_message", "The table could not be built.")))
    sources, _ = sources_and_links([(tool, with_call_args(result, args))])
    return WidgetRunOut(
        status="success", sources=[ChatSourceOut.model_validate(s, from_attributes=True) for s in sources]
    )
