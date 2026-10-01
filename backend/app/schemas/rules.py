from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class RuleCompileIn(CamelModel):
    country_code: str = Field(min_length=2, max_length=2)
    mega_segment_id: str = Field(min_length=1, max_length=10)
    text: str = Field(min_length=5, max_length=600)
    source_entry_id: str | None = None


class RuleSlots(CamelModel):
    metric: str
    comparator: str
    threshold: float
    months: list[int] | None = None
    segment_ids: list[int] | None = None
    required_driver: str | None = None
    severity: str


class RuleCreateIn(RuleCompileIn):
    slots: RuleSlots
    provider: str = Field(max_length=40)
    decisions: dict = Field(default_factory=dict)


class RulePreviewExample(CamelModel):
    entry_id: str
    label: str
    user_name: str
    value: float
    metric_value: float
    resolution: str | None


class RulePreviewOut(CamelModel):
    checked: int
    fired: int
    confirmed: int
    contradicted: int
    inconclusive: int
    pending: int
    catches_source: bool | None
    examples: list[RulePreviewExample]


class RuleDraftOut(CamelModel):
    ok: bool
    rejection: str | None = None
    slots: RuleSlots | None = None
    description: str | None = None
    provider: str
    confidences: dict[str, float]
    low_confidence_fields: list[str]
    decisions: dict
    preview: RulePreviewOut | None = None


class RuleStats(CamelModel):
    fired: int
    confirmed: int
    contradicted: int
    inconclusive: int
    pending: int


class RuleOut(CamelModel):
    id: int
    country_code: str
    mega_segment_id: str
    slots: RuleSlots
    text: str
    description: str
    provider: str
    source_entry_id: str | None
    source_label: str | None
    created_by: str
    created_by_name: str
    created_at: datetime
    active: bool
    retired_by_name: str | None
    retired_at: datetime | None
    stats: RuleStats
