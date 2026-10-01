"""Template answers for the data chat when Gemini is not available. One intent, one tool, one sentence template.

Every number in an answer is copied from the tool result, so the same rule as the agent holds.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from app.ai.data_agent import lead_tools, rep_tools, tools
from app.ai.data_agent.policy import POLICY_KEY, ChatPolicy, PageContext
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
CHANGE_NEEDS_AGENT = {
    "submit_or_justify": (
        "Changes through the chat need the Gemini agent, which is off. Open Capture to submit a number or "
        "justify an IBP entry."
    ),
    "review_decision": (
        "Changes through the chat need the Gemini agent, which is off. Open Consensus to approve, discuss or "
        "challenge entries."
    ),
    "rule_authoring": (
        "Changes through the chat need the Gemini agent, which is off. Open Lead rules to write, test and "
        "activate a rule."
    ),
}
CHANGE_INTENTS = frozenset(CHANGE_NEEDS_AGENT)


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


async def answer(intent: str, text: str, policy: ChatPolicy, page: PageContext | None = None) -> OfflineAnswer:
    ctx = ToolState(state={POLICY_KEY: policy.model_dump()})
    results: list[tuple[str, dict]] = []

    async def call(fn, *args) -> dict:
        result = await fn(*args, ctx)
        results.append((fn.__name__, result))
        return result

    if intent == "forecast_request":
        return OfflineAnswer(FORECAST_REFUSAL, [])

    segment_id = _segment_id(text, policy) or (page.segment_id if page and page.segment_id else 0)
    month = _month(text) or (page.month if page and page.month else 0)

    if intent in CHANGE_INTENTS:
        return OfflineAnswer(CHANGE_NEEDS_AGENT[intent], [])

    if intent == "what_if":
        return OfflineAnswer(
            "What-if previews need the Gemini agent, which is off. Type the number in Capture: the share, "
            "year-to-go and flag tiles update as you type, and nothing is saved until you submit.",
            [],
        )

    if intent == "briefing":
        r = await call(rep_tools.get_my_briefing)
        if r["status"] != "success":
            return OfflineAnswer(r["error_message"], results)
        if not r["rows"]:
            return OfflineAnswer("Nothing needs your attention right now.", results)
        return OfflineAnswer(f"{len(r['rows'])} items need your attention; they are listed below.", results)

    entry_id = page.entry_id if page and page.entry_id else ""
    if intent == "explain_flag" and (entry_id or (segment_id and month)):
        r = await call(rep_tools.explain_entry_flags, segment_id, month, entry_id)
        if r["status"] != "success":
            return OfflineAnswer(r["error_message"], results)
        if not r["rows"]:
            return OfflineAnswer("No flags fired on that entry.", results)
        count = len(r["rows"])
        return OfflineAnswer(
            f"{count} {'flag' if count == 1 else 'flags'} fired on that entry; each one, what it checks and its limit "
            "are below.",
            results,
        )

    if entry_id and intent in ("entries_flags", "consensus", "claims_track_record", "other"):
        r = await call(lead_tools.get_entry_detail, entry_id, 0, 0)
        if r["status"] != "success":
            return OfflineAnswer(r["error_message"], results)
        f = r["figures"]
        return OfflineAnswer(
            f"{f['rep']}'s {f['month']} entry is {f['entered_ks']} KS ({f['low_ks']} to {f['high_ks']}), status "
            f"{f['status']}; Jev suggests {f['triage_suggests']}. The reasons, flags, claim and notes are below.",
            results,
        )

    if intent == "how_to":
        r = await call(rep_tools.explain_term, text)
        first = r["rows"][0]
        return OfflineAnswer(f"{first[0]}: {first[1]}", results)

    if segment_id and re.search(r"\bibp\b|committed|variet", text, re.IGNORECASE):
        r = await call(tools.get_ibp_forecast, segment_id)
        if r["status"] != "success":
            return OfflineAnswer(r["error_message"], results)
        if not r["rows"]:
            return OfflineAnswer("No IBP snapshot has been uploaded for that segment yet.", results)
        totals = ", ".join(f"{m} {q} KS" for m, q in r["month_totals_ks"].items())
        return OfflineAnswer(f"Committed in IBP for {r['source'].split(' for ')[-1]}: {totals}.", results)

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
