from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.chat import ChatSourceOut
from app.schemas.common import CamelModel


class WidgetPrefsIn(CamelModel):
    # Built-in widget ids, in display order. The registry lives in the web app; ids are only shape-checked here.
    visible: list[str] = Field(max_length=30)


class WidgetPrefsOut(CamelModel):
    visible: list[str]


class UserWidgetIn(CamelModel):
    title: str = Field(min_length=1, max_length=120)
    tool: str = Field(min_length=1, max_length=60)
    args: dict[str, Any] = {}
    country_code: str = Field(min_length=2, max_length=2)
    mega_segment_id: str = Field(min_length=1, max_length=10)


class UserWidgetRename(CamelModel):
    title: str = Field(min_length=1, max_length=120)


class UserWidgetOut(CamelModel):
    id: int
    title: str
    tool: str
    args: dict[str, Any]
    country_code: str
    mega_segment_id: str
    position: int
    created_at: datetime


class WidgetsOut(CamelModel):
    prefs: WidgetPrefsOut
    custom: list[UserWidgetOut]


class WidgetRunOut(CamelModel):
    status: str
    error: str | None = None
    sources: list[ChatSourceOut] = []

