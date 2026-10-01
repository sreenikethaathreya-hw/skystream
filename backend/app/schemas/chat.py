from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import CamelModel

Cell = str | int | float | bool | None


class PageContextIn(CamelModel):
    """What the user is looking at when they ask: ids only, never figures."""

    page: str = Field(default="", max_length=30)
    segment_id: int | None = None
    month: int | None = Field(default=None, ge=1, le=12)
    entry_id: str | None = Field(default=None, max_length=36)
    rule_id: int | None = None


class ChatMessageIn(CamelModel):
    text: str = Field(min_length=1, max_length=1000)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    mega_segment_id: str | None = Field(default=None, min_length=1, max_length=10)
    page_context: PageContextIn | None = None


class ChatSourceOut(CamelModel):
    tool: str
    label: str
    columns: list[str]
    rows: list[list[Cell]]
    # The call's arguments, so the UI can pin this table as a widget that re-runs the same tool.
    args: dict[str, Any] | None = None
    pinnable: bool = False


class ChatLinkOut(CamelModel):
    label: str
    to: str


class ChatActionOut(CamelModel):
    kind: str
    target_type: str
    target_id: str
    summary: str
    link: str | None = None


class ChatDownloadOut(CamelModel):
    label: str
    href: str


class ChatMessageOut(CamelModel):
    role: str
    text: str
    created_at: datetime
    numbers_redacted: bool = False
    provider: str | None = None
    sources: list[ChatSourceOut] = []
    links: list[ChatLinkOut] = []
    actions: list[ChatActionOut] = []
    downloads: list[ChatDownloadOut] = []


class ChatTurnOut(CamelModel):
    session_id: str
    answer: str
    intent: str
    provider: str
    numbers_redacted: bool
    sources: list[ChatSourceOut]
    links: list[ChatLinkOut]
    actions: list[ChatActionOut] = []
    downloads: list[ChatDownloadOut] = []


class ChatSessionOut(CamelModel):
    id: str
    title: str
    updated_at: datetime


class ChatHistoryOut(CamelModel):
    session: ChatSessionOut
    messages: list[ChatMessageOut]
