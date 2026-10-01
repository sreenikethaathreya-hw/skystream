"""The caller's access policy for one chat turn. The server writes it; the model never sees or sets it."""

from pydantic import BaseModel

from app.services.user_service import CurrentUser, Scope

POLICY_KEY = "temp:policy"
# Only an ADK evalset's initial session sets this; the chat service always writes POLICY_KEY per turn.
EVAL_POLICY_KEY = "eval_policy"
ALLOWED_NUMBERS_KEY = "temp:allowed_numbers"
LEAD_ONLY_TOOLS = frozenset({"list_open_exceptions"})


class ScopeGrant(BaseModel):
    country_code: str
    scope_type: str
    scope_id: str


class ChatPolicy(BaseModel):
    user_id: str
    user_name: str
    role: str
    scopes: list[ScopeGrant] = []
    country_code: str
    mega_segment_id: str
    visible_segment_ids: list[int]
    is_demo: bool

    @property
    def is_lead(self) -> bool:
        return self.role in ("lead", "admin")

    def can_see(self, segment_id: int) -> bool:
        return segment_id in self.visible_segment_ids


def policy_for(
    user: CurrentUser, country_code: str, mega_segment_id: str, segment_ids: list[int], is_demo: bool
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
    )


def read_policy(state) -> ChatPolicy | None:
    raw = state.get(POLICY_KEY) or state.get(EVAL_POLICY_KEY)
    if raw is None:
        return None
    return raw if isinstance(raw, ChatPolicy) else ChatPolicy.model_validate(raw)


def current_user(policy: ChatPolicy) -> CurrentUser:
    return CurrentUser(
        id=policy.user_id,
        name=policy.user_name,
        role=policy.role,
        title=policy.role.capitalize(),
        scopes=[Scope(s.country_code, s.scope_type, s.scope_id) for s in policy.scopes],
    )
