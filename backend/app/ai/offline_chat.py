"""Template answers for the data chat when Gemini is not available. One intent, one tool, one sentence template.

Every number in an answer is copied from the tool result, so the same rule as the agent holds.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from app.ai.data_agent import tools
from app.ai.data_agent.policy import POLICY_KEY, ChatPolicy
from app.services.rule_service import parse_months

FORECAST_REFUSAL = (
    "I can't forecast or suggest demand numbers. Every number in the ledger comes from the rep, with their own "
    "low-high range. I can show the plan, last year, the historical average and what has been entered so far."
)
HELP = (
    "I can answer questions about market share, plan, year-to-go, monthly actuals, rep entries and flags, "
    "claims and track records, competitor shares and lead rules. Name a micro-segment number from the table "
    "for segment-level answers."
)


@dataclass
class ToolState:
    """Stands in for ADK's Context when a tool is called outside the agent loop."""

    state: dict[str, Any] = field(default_factory=dict)


@dataclass
class OfflineAnswer:
    text: str
    results: list[tuple[str, dict]]


def _segment_id(text: str, policy: ChatPolicy) -> int:
    for token in re.findall(r"\b\d{3,6}\b", text):
        if int(token) in policy.visible_segment_ids:
            return int(token)
    return 0


def _month(text: str) -> int:
    months = parse_months(text) or []
    return months[0] if months else 0


def _rep_name(text: str, policy: ChatPolicy) -> str:
    match = re.search(r"\brep\s+([a-z])\b", text, re.IGNORECASE)
    if match:
        return f"Rep {match.group(1).upper()}"
    if policy.role == "rep" and re.search(r"\b(my|mine|i)\b", text, re.IGNORECASE):
        return policy.user_name
    return ""


async def answer(intent: str, text: str, policy: ChatPolicy) -> OfflineAnswer:
    ctx = ToolState(state={POLICY_KEY: policy.model_dump()})
    results: list[tuple[str, dict]] = []

    async def call(fn, *args) -> dict:
        result = await fn(*args, ctx)
        results.append((fn.__name__, result))
        return result

    if intent == "forecast_request":
        return OfflineAnswer(FORECAST_REFUSAL, [])

    segment_id = _segment_id(text, policy)
    month = _month(text)

    if intent in ("baseline_share", "plan_vs_actual") and not segment_id:
        listing = await call(tools.list_segments)
        if listing["status"] != "success":
            return OfflineAnswer(listing["error_message"], results)
        return OfflineAnswer("Which micro-segment? Here are the segments in your scope.", results)

    if intent == "baseline_share":
        r = await call(tools.get_segment_baseline, segment_id, month)
        if r["status"] != "success":
            return OfflineAnswer(r["error_message"], results)
        f = r["figures"]
        return OfflineAnswer(
            f"In {f['year']}, {f['segment']} is at {f['share_now_pct']}% volume share against a plan share of "
            f"{f['plan_share_pct']}% (last year {f['last_year_share_pct']}%). Year-to-go is {f['year_to_go_ks']} KS "
            f"with {f['months_remaining']} months open. The {f['month']} plan is {f['month_plan_ks']} KS and the "
            f"historical {f['month']} average is {f['month_historical_avg_ks']} KS.",
            results,
        )

    if intent == "plan_vs_actual":
        r = await call(tools.get_monthly_series, segment_id)
        if r["status"] != "success":
            return OfflineAnswer(r["error_message"], results)
        return OfflineAnswer(
            f"Here is the month-by-month plan, actuals and latest entries for {r['source'].split(' for ')[-1]}. "
            f"Open months start in {r['open_from_month']}.",
            results,
        )

    if intent == "entries_flags":
        r = await call(tools.list_demand_entries, segment_id, month, "", _rep_name(text, policy))
        if r["status"] != "success":
            return OfflineAnswer(r["error_message"], results)
        flagged = sum(1 for row in r["rows"] if row[7] != "none")
        return OfflineAnswer(
            f"{r['total_matching']} entries match; {flagged} of the {len(r['rows'])} shown carry flags.", results
        )

    if intent == "claims_track_record":
        r = await call(tools.get_rep_track_records, _rep_name(text, policy))
        if r["status"] != "success":
            return OfflineAnswer(r["error_message"], results)
        weak = [row[0] for row in r["rows"] if row[7] == "yes"]
        tail = f" Weak records: {', '.join(weak)}." if weak else " No rep has a weak record."
        return OfflineAnswer(f"Track records for {len(r['rows'])} reps are below.{tail}", results)

    if intent == "competitors":
        r = await call(tools.get_competitor_shares)
        if r["status"] != "success" or not r["rows"]:
            return OfflineAnswer(r.get("error_message", "No competitor shares are loaded for this scope."), results)
        name, year, share, _ = r["rows"][0]
        return OfflineAnswer(f"In {year}, {name} has the largest competitor share at {share}%.", results)

    if intent == "rules":
        r = await call(tools.list_lead_rules)
        if r["status"] != "success":
            return OfflineAnswer(r["error_message"], results)
        active = sum(1 for row in r["rows"] if row[2] == "yes")
        return OfflineAnswer(f"There are {len(r['rows'])} lead rules here, {active} of them active.", results)

    if intent == "consensus":
        r = await call(tools.list_open_exceptions)
        if r["status"] != "success":
            return OfflineAnswer(r["error_message"], results)
        return OfflineAnswer(
            f"{r['exception_count']} open entries need review and {r['routine_count']} are routine.", results
        )

    await call(tools.list_segments)
    return OfflineAnswer(HELP, results)
