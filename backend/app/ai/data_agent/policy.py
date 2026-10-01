"""The caller's access policy for one chat turn. The server writes it; the model never sees or sets it."""

from pydantic import BaseModel, Field

from app.services.user_service import CurrentUser, Scope

POLICY_KEY = "temp:policy"
# Only an ADK evalset's initial session sets this; the chat service always writes POLICY_KEY per turn.
EVAL_POLICY_KEY = "eval_policy"
ALLOWED_NUMBERS_KEY = "temp:allowed_numbers"
PAGE_CONTEXT_KEY = "temp:page_context"
WRITES_KEY = "temp:writes"
# Persists across turns so a lead can compile a rule in one message and activate it in the next.
RULE_DRAFTS_KEY = "rule_drafts"

LEAD_ONLY_TOOLS = frozenset(
    {
        "list_open_exceptions",
        "get_submission_coverage",
        "rank_segments",
        "summarize_claims",
        "get_supply_export",
        "compile_lead_rule",
    }
)
ADMIN_ONLY_TOOLS = frozenset({"get_upload_status", "list_user_scopes", "get_data_quality"})

REP_WRITE_TOOLS = frozenset({"submit_demand_entry", "justify_ibp_entry"})
LEAD_WRITE_TOOLS = frozenset({"decide_entry", "bulk_approve_routine", "activate_lead_rule", "retire_lead_rule"})
SHARED_WRITE_TOOLS = frozenset({"add_entry_note"})
WRITE_TOOLS = REP_WRITE_TOOLS | LEAD_WRITE_TOOLS | SHARED_WRITE_TOOLS
MAX_WRITES_PER_TURN = 1

# Numeric arguments that must appear in the user's own message: the model never authors a number.
USER_NUMBER_ARGS = ("value", "low", "high", "price")
USER_NUMBER_TOOLS = frozenset({"preview_entry_impact", "check_justification", "submit_demand_entry",
                               "justify_ibp_entry"})
# Text arguments that must be a contiguous quote of the user's message: the model never authors a claim.
VERBATIM_TEXT_ARGS = ("justification", "note", "rule_text")


class ScopeGrant(BaseModel):
    country_code: str
    scope_type: str
    scope_id: str


class PageContext(BaseModel):
    """What the user is looking at when they ask. Ids only, never figures."""

    page: str = Field(default="", max_length=30)
    segment_id: int | None = None
    month: int | None = Field(default=None, ge=1, le=12)
    entry_id: str | None = Field(default=None, max_length=36)
    rule_id: int | None = None

    def describe(self, labels: dict[int, str] | None = None) -> str:
        parts = []
        if self.page:
            parts.append(f"page {self.page}")
        if self.segment_id:
            label = (labels or {}).get(self.segment_id)
            parts.append(f"micro-segment {self.segment_id}" + (f" ({label})" if label else ""))
        if self.month:
            parts.append(f"month {self.month}")
        if self.entry_id:
            parts.append(f"entry id {self.entry_id}")
        if self.rule_id:
            parts.append(f"lead rule {self.rule_id}")
        return ", ".join(parts)


class ChatPolicy(BaseModel):
    user_id: str
    user_name: str
    role: str
    scopes: list[ScopeGrant] = []
    country_code: str
    mega_segment_id: str
    visible_segment_ids: list[int]
    is_demo: bool
    writes_allowed: bool = False
    demand_source: str = "manual"

    @property
    def is_lead(self) -> bool:
        return self.role in ("lead", "admin")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def can_see(self, segment_id: int) -> bool:
        return segment_id in self.visible_segment_ids


def policy_for(
    user: CurrentUser,
    country_code: str,
    mega_segment_id: str,
    segment_ids: list[int],
    is_demo: bool,
    writes_allowed: bool = False,
    demand_source: str = "manual",
) -> ChatPolicy:
    return ChatPolicy(
        user_id=user.id,
        user_name=user.name,
        role=user.role,
        scopes=[ScopeGrant(country_code=s.country_code, scope_type=s.scope_type, scope_id=s.scope_id) for s in user.scopes],
        country_code=country_code,
        mega_segment_id=mega_segment_id,
        visible_segment_ids=segment_ids,
        is_demo=is_demo,
        writes_allowed=writes_allowed,
        demand_source=demand_source,
    )


def read_policy(state) -> ChatPolicy | None:
    raw = state.get(POLICY_KEY) or state.get(EVAL_POLICY_KEY)
    if raw is None:
        return None
    return raw if isinstance(raw, ChatPolicy) else ChatPolicy.model_validate(raw)


def read_page_context(state) -> PageContext | None:
    raw = state.get(PAGE_CONTEXT_KEY)
    if not raw:
        return None
    return raw if isinstance(raw, PageContext) else PageContext.model_validate(raw)


def current_user(policy: ChatPolicy) -> CurrentUser:
    return CurrentUser(
        id=policy.user_id,
        name=policy.user_name,
        role=policy.role,
        title=policy.role.capitalize(),
        scopes=[Scope(s.country_code, s.scope_type, s.scope_id) for s in policy.scopes],
    )
