from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel

Cell = str | int | float | bool | None


class ChatMessageIn(CamelModel):
    text: str = Field(min_length=1, max_length=1000)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    mega_segment_id: str | None = Field(default=None, min_length=1, max_length=10)


class ChatSourceOut(CamelModel):
    tool: str
    label: str
    columns: list[str]
    rows: list[list[Cell]]


class ChatLinkOut(CamelModel):
    label: str
    to: str


class ChatMessageOut(CamelModel):
    role: str
    text: str
    created_at: datetime
    numbers_redacted: bool = False
    provider: str | None = None
    sources: list[ChatSourceOut] = []
    links: list[ChatLinkOut] = []


class ChatTurnOut(CamelModel):
    session_id: str
    answer: str
    intent: str
    provider: str
    numbers_redacted: bool
    sources: list[ChatSourceOut]
    links: list[ChatLinkOut]


class ChatSessionOut(CamelModel):
    id: str
    title: str
    updated_at: datetime


class ChatHistoryOut(CamelModel):
    session: ChatSessionOut
    messages: list[ChatMessageOut]
