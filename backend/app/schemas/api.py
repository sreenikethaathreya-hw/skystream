from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.claims import DecisionAnswer, StructuredClaim, TriageDecision
from app.schemas.common import CamelModel
from app.schemas.demand_math import Flag, Impact, SegmentContext, Thresholds


class UserOut(CamelModel):
    id: str
    name: str
    role: str
    title: str


class ClockOut(CamelModel):
    year: int
    month: int


class FirebaseConfigOut(CamelModel):
    api_key: str
    auth_domain: str
    project_id: str


class ConfigOut(CamelModel):
    data_mode: str
    firebase: FirebaseConfigOut | None


class MetaOut(CamelModel):
    data_mode: str
    me: UserOut
    users: list[UserOut]
    clock: ClockOut | None
    ai: dict[str, str | bool]
    thresholds: Thresholds
    currency: str


class ScopeOptionOut(CamelModel):
    country_code: str
    country_name: str
    species: str | None
    mega_segment_id: str
    mega_segment_desc: str
    segments: int


class CompetitorOut(CamelModel):
    name: str
    share_pct: float
    trend: str | None


class MonthEntryOut(CamelModel):
    id: str
    month: int
    value: float
    low: float
    high: float
    status: str
    user_id: str


class SegmentCubeOut(CamelModel):
    id: int
    label: str
    description: str
    color: str | None
    profile: str
    editable: bool
    owner_names: list[str]
    plan_basis: str
    last_year_basis: str
    plan_comment: str | None
    market_notes: dict[str, str | None]
    context: SegmentContext
    latest_entries: list[MonthEntryOut]


class CubeOut(CamelModel):
    country_code: str
    country_name: str
    mega_segment_id: str
    mega_segment_desc: str
    species: str | None
    currency: str
    year: int
    clock_month: int
    year_closed: bool
    thresholds: Thresholds
    competitors: list[CompetitorOut]
    varieties: list[str]
    segments: list[SegmentCubeOut]


class EntryIn(CamelModel):
    country_code: str = Field(default="ES", min_length=2, max_length=2)
    segment_id: int
    month: int = Field(ge=1, le=12)
    value: float = Field(ge=0)
    low: float = Field(ge=0)
    high: float = Field(ge=0)
    price: float | None = Field(default=None, gt=0)
    justification: str | None = Field(default=None, max_length=600)

    @model_validator(mode="after")
    def _range_brackets_value(self) -> "EntryIn":
        if not self.low <= self.value <= self.high:
            raise ValueError("low <= value <= high is required")
        self.country_code = self.country_code.upper()
        return self


class AnalyzeOut(CamelModel):
    impact: Impact
    flags: list[Flag]
    claim: StructuredClaim | None


class ClaimOut(CamelModel):
    driver: str
    direction: str
    magnitude: float | None
    competitor: str | None
    variety: str | None
    evidence_source: str | None
    verifiable: float | None
    consistent_with_notes: float | None
    specificity: float | None
    addresses_flags: float | None
    summary: str | None
    provider: str
    signal: str
    check_year: int
    check_month: int
    resolution: str
    resolution_detail: dict | None
    decisions: dict[str, DecisionAnswer]


class EntryOut(CamelModel):
    id: str
    user_id: str
    user_name: str
    country_code: str
    segment_id: int
    segment_label: str
    year: int
    month: int
    value: float
    low: float
    high: float
    price: float | None
    justification: str | None
    impact: dict | None
    flags: list[Flag]
    status: str
    source: str
    triage: TriageDecision | None
    reviewed_by: str | None
    created_at: datetime
    claim: ClaimOut | None


class TrackRecordOut(CamelModel):
    user: UserOut
    entries_resolved: int
    bias_pct: float | None
    claim_hit_rate: float | None
    range_coverage: float | None
    confirmed: int
    contradicted: int
    weak: bool


class ResolvedClaimOut(CamelModel):
    entry_id: str
    segment_label: str
    user_name: str
    resolution: str
    actual: float
    value: float
    in_range: bool
    supported_probability: float
    provider: str


class AdvanceOut(CamelModel):
    from_month: int
    to_month: int
    resolved: list[ResolvedClaimOut]
    confirmed: int
    contradicted: int
    inconclusive: int


class QueueItemOut(CamelModel):
    entry: EntryOut
    reasons: list[str]


class QueueOut(CamelModel):
    exceptions: list[QueueItemOut]
    routine: list[EntryOut]


class DecisionIn(CamelModel):
    decision: str = Field(pattern="^(approve|discuss|challenge)$")


class RtbIn(CamelModel):
    country_code: str = Field(default="ES", min_length=2, max_length=2)
    segment_id: int


class RtbOut(CamelModel):
    segment_id: int
    text: str
    provider: str
    cited_entry_ids: list[str]


class ScopeIn(CamelModel):
    country_code: str = Field(min_length=2, max_length=2)
    scope_type: str = Field(pattern="^(mega|micro)$")
    scope_id: str = Field(min_length=1, max_length=20)


class UserAdminIn(CamelModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(pattern="^(admin|lead|rep)$")
    active: bool = True
    scopes: list[ScopeIn] = []


class UserAdminOut(CamelModel):
    email: str
    name: str
    role: str
    active: bool
    last_seen_at: datetime | None
    scopes: list[ScopeIn]


class UploadKindOut(CamelModel):
    kind: str
    label: str
    source: str
    required: bool
    template: bool
    last_committed_at: datetime | None


class BatchOut(CamelModel):
    id: str
    kind: str
    filename: str
    uploaded_by: str
    status: str
    rows_read: int
    accepted: int
    rejected: int
    warnings: int
    report: dict
    commit_summary: dict | None
    created_at: datetime
    committed_at: datetime | None
