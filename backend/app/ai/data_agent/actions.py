"""Write tools for the chat agent. Each one calls the same service the UI uses, so every existing check holds.

WriteGuardPlugin runs before these: role allowlists, the chatWritesAllowed setting, one write per turn, numbers
that must appear in the user's own message and justification or note text that must quote it. A successful
write returns an `action` the UI shows as a receipt; AuditPlugin records every attempt in chat_actions.
"""

import uuid

from google.adk import Context
from pydantic import ValidationError
from sqlalchemy import select

from app.ai.data_agent.policy import RULE_DRAFTS_KEY, ChatPolicy, current_user
from app.ai.data_agent.tool_support import (
    Result,
    capture_link,
    consensus_link,
    error,
    ks,
    latest_entry,
    month_name,
    out_of_scope,
    resolve_entry,
    scoped_entry,
    with_policy,
)
from app.database import async_session
from app.models import DemandEntry, LeadRule
from app.schemas.api import EntryIn, JustifyIn
from app.schemas.rules import RuleCompileIn, RuleCreateIn
from app.services import consensus_service, entry_service, note_service, rule_service
from app.services.consensus_service import OPEN_STATUSES
from app.services.context_service import COMMITTED_SOURCES, current_period
from app.services.user_service import user_names

DECISIONS = ("approve", "discuss", "challenge")


def _action(kind: str, target_type: str, target_id: str | int, summary: str, link: str, **figures) -> Result:
    return {
        "status": "success",
        "source": "Change made",
        "action": {
            "kind": kind,
            "target_type": target_type,
            "target_id": str(target_id),
            "summary": summary,
            "link": link,
        },
        "figures": figures,
    }


def _validation_message(exc: ValidationError) -> str:
    return "; ".join(e["msg"].removeprefix("Value error, ") for e in exc.errors())


async def submit_demand_entry(
    segment_id: int, month: int, value: float, low: float, high: float, price: float, justification: str,
    ctx: Context,
) -> Result:
    """Submits the rep's own demand number for a micro-segment and month, exactly as the rep typed it.

    Call this only when a rep explicitly asks in this message to submit, enter or record a number. Use the
    number, range, price and justification exactly as the user wrote them; if the number or a needed reason is
    missing, ask instead of filling it in. Only works when demand is typed in Skystream (not IBP).

    Args:
      segment_id: The micro-segment number.
      month: The open month 1 to 12.
      value: The demand number in KS, exactly as the user wrote it.
      low: The user's low in KS, or 0 if they gave no range.
      high: The user's high in KS, or 0 if they gave no range.
      price: The user's net price per KS in USD, or 0 if none.
      justification: The user's reason quoted exactly from their message, or an empty string.

    Returns:
      On success: {'status': 'success', 'action': {...}, 'figures': {...}}. On failure: {'status': 'error',
      'error_message': ...} (for example a flag fired and no justification was given).
    """

    async def body(policy: ChatPolicy) -> Result:
        if policy.role != "rep":
            return error("Only reps submit demand numbers.")
        if policy.demand_source == "ibp":
            return error("Demand comes from IBP: change the number in IBP, then ask me to justify it here.")
        if not policy.can_see(segment_id):
            return out_of_scope(segment_id)
        if value <= 0:
            return error("Tell me the number to submit, in KS.")
        try:
            request = EntryIn(
                country_code=policy.country_code, segment_id=segment_id, month=month, value=value,
                low=low or value, high=high or value, price=price or None,
                justification=justification.strip() or None,
            )
        except ValidationError as exc:
            return error(_validation_message(exc))
        async with async_session() as db:
            out = await entry_service.create_entry(db, current_user(policy), request)
        return _action(
            "entry_submitted", "entry", out.id,
            f"Submitted {out.value:,.0f} KS ({out.low:,.0f}-{out.high:,.0f}) for {out.segment_label}, "
            f"{month_name(out.month)}",
            capture_link(segment_id, month),
            entered_ks=ks(out.value), low_ks=ks(out.low), high_ks=ks(out.high), flags=len(out.flags),
            status=out.status, claim=out.claim.summary if out.claim else None,
        )

    return await with_policy(ctx, body)


async def justify_ibp_entry(
    segment_id: int, month: int, low: float, high: float, justification: str, ctx: Context
) -> Result:
    """Adds the rep's range and justification to a number imported from IBP. The IBP number never changes.

    Call this only when a rep explicitly asks in this message to justify their IBP number. Use the range and
    reason exactly as the user wrote them; if the reason is missing, ask for it.

    Args:
      segment_id: The micro-segment number.
      month: The month 1 to 12 of the IBP entry.
      low: The user's low in KS, or 0 to keep the current low.
      high: The user's high in KS, or 0 to keep the current high.
      justification: The user's reason quoted exactly from their message.

    Returns:
      On success: {'status': 'success', 'action': {...}, 'figures': {...}}. On failure: {'status': 'error',
      'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if policy.role != "rep":
            return error("Only the rep who owns an IBP number can justify it.")
        if not policy.can_see(segment_id):
            return out_of_scope(segment_id)
        if not justification.strip():
            return error("Tell me the reason in your own words and I will add it.")
        async with async_session() as db:
            entry = await latest_entry(db, policy, segment_id, month, sources=("ibp",))
            if entry is None:
                return error(f"There is no IBP number for micro-segment {segment_id} in {month_name(month)}.")
            out = await entry_service.justify_entry(
                db, current_user(policy), entry.id,
                JustifyIn(justification=justification.strip()[:600], low=low or None, high=high or None),
            )
        return _action(
            "ibp_justified", "entry", out.id,
            f"Justified the IBP number {out.value:,.0f} KS for {out.segment_label}, {month_name(out.month)}",
            capture_link(segment_id, month),
            ibp_ks=ks(out.value), low_ks=ks(out.low), high_ks=ks(out.high), flags=len(out.flags),
            status=out.status, claim=out.claim.summary if out.claim else None,
        )

    return await with_policy(ctx, body)


async def add_entry_note(entry_id: str, segment_id: int, month: int, note: str, ctx: Context) -> Result:
    """Adds a note to an entry: a lead asking the rep something, or the rep answering the lead.

    Call this only when the user explicitly asks to leave, send or add a note or message. The note text must be
    quoted exactly from the user's message.

    Args:
      entry_id: The entry id if known, else an empty string.
      segment_id: The micro-segment number when no entry id is given, else 0.
      month: The month 1 to 12 when no entry id is given, else 0.
      note: The note, quoted exactly from the user's message.

    Returns:
      On success: {'status': 'success', 'action': {...}}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if not note.strip():
            return error("What should the note say?")
        async with async_session() as db:
            entry = await resolve_entry(db, policy, entry_id, segment_id, month)
            if isinstance(entry, dict):
                return entry
            saved = await note_service.add_note(db, current_user(policy), entry.id, note, via="chat")
        return _action(
            "note_added", "entry", entry.id, f"Note added to the {month_name(entry.month)} entry",
            consensus_link(entry.id) if policy.is_lead else capture_link(entry.segment_id, entry.month),
            note=saved.body,
        )

    return await with_policy(ctx, body)


async def decide_entry(
    entry_id: str, segment_id: int, month: int, rep_name: str, decision: str, note: str, ctx: Context
) -> Result:
    """Records the consensus lead's decision on an open entry: approve, discuss or challenge.

    Call this only when a lead explicitly asks in this message to approve, challenge or mark an entry for
    discussion. If several entries match, the tool lists them instead of acting; ask which one.

    Args:
      entry_id: The entry id if known, else an empty string.
      segment_id: The micro-segment number when no entry id is given, else 0.
      month: The month 1 to 12 when no entry id is given, else 0.
      rep_name: Part of the rep's name to tell entries apart, or an empty string.
      decision: approve, discuss or challenge.
      note: An optional note for the rep, quoted exactly from the user's message, or an empty string.

    Returns:
      On success: {'status': 'success', 'action': {...}} or, when ambiguous, {'status': 'success',
      'needs_choice': true, 'rows': [...]}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if not policy.is_lead:
            return error("Only consensus leads and admins decide on entries.")
        choice = decision.strip().lower()
        if choice not in DECISIONS:
            return error("The decision must be approve, discuss or challenge.")
        async with async_session() as db:
            names = await user_names(db)
            if entry_id:
                found = await scoped_entry(db, policy, entry_id.strip())
                if isinstance(found, dict):
                    return found
                candidates = [found]
            else:
                if not segment_id or not 1 <= month <= 12:
                    return error("Say which entry: the micro-segment and month, or open it first.")
                if not policy.can_see(segment_id):
                    return out_of_scope(segment_id)
                period = await current_period(db, policy.country_code)
                candidates = (
                    await db.execute(
                        select(DemandEntry).where(
                            DemandEntry.country_code == policy.country_code,
                            DemandEntry.segment_id == segment_id,
                            DemandEntry.year == period.year,
                            DemandEntry.month == month,
                            DemandEntry.source.in_(COMMITTED_SOURCES),
                            DemandEntry.status.in_(OPEN_STATUSES),
                        )
                    )
                ).scalars().all()
                if rep_name.strip():
                    needle = rep_name.strip().lower()
                    candidates = [e for e in candidates if needle in names.get(e.user_id, e.user_id).lower()]
            if not candidates:
                return error("No open entry matches that description.")
            if len(candidates) > 1:
                return {
                    "status": "success",
                    "source": "Matching entries",
                    "needs_choice": True,
                    "columns": ["Entry id", "Rep", "Month", "Value (KS)", "Status"],
                    "rows": [
                        [e.id, names.get(e.user_id, e.user_id), month_name(e.month), ks(e.value), e.status]
                        for e in candidates
                    ],
                }
            entry = candidates[0]
            await consensus_service.decide(db, current_user(policy), entry.id, choice)
            if note.strip():
                await note_service.add_note(db, current_user(policy), entry.id, note, via="chat")
        verb = {"approve": "Approved", "discuss": "Marked for discussion", "challenge": "Challenged"}[choice]
        return _action(
            f"entry_{choice}", "entry", entry.id,
            f"{verb}: {names.get(entry.user_id, entry.user_id)}'s {month_name(entry.month)} entry for micro-segment "
            f"{entry.segment_id}",
            consensus_link(entry.id),
            value_ks=ks(entry.value), note=note.strip() or None,
        )

    return await with_policy(ctx, body)


async def bulk_approve_routine(ctx: Context) -> Result:
    """Approves every routine entry in the consensus queue (entries with no flags or other concerns).

    Call this only when a lead explicitly asks in this message to approve all routine entries.

    Returns:
      On success: {'status': 'success', 'action': {...}, 'figures': {'approved': n}}.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if not policy.is_lead:
            return error("Only consensus leads and admins approve entries.")
        async with async_session() as db:
            count = await consensus_service.bulk_approve(
                db, current_user(policy), policy.country_code, policy.mega_segment_id
            )
        return _action(
            "bulk_approved", "queue", policy.mega_segment_id, f"Approved {count} routine entries",
            consensus_link(), approved=count,
        )

    return await with_policy(ctx, body)


async def compile_lead_rule(rule_text: str, source_entry_id: str, ctx: Context) -> Result:
    """Reads a lead's rule sentence into a fixed check and backtests it. Saves a draft; activates nothing.

    Use this when a lead asks to make, write or draft a rule. Pass the lead's sentence exactly as written; the
    limit and months are read from the words, and a rule without a number is rejected. Show the read-back and
    backtest, then wait for the lead to ask you to activate it.

    Args:
      rule_text: The lead's rule, quoted exactly from their message.
      source_entry_id: The entry id the rule should have caught, or an empty string.

    Returns:
      On success: {'status': 'success', 'draft_id': ..., 'figures': {description, checked, fired, confirmed,
      contradicted, ...}}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if not policy.is_lead:
            return error("Only consensus leads and admins write rules.")
        text = rule_text.strip()
        if len(text) < 5:
            return error("Say the rule as a sentence, with its limit, for example '... above 20% over last year'.")
        compile_in = RuleCompileIn(
            country_code=policy.country_code, mega_segment_id=policy.mega_segment_id, text=text[:600],
            source_entry_id=source_entry_id.strip() or None,
        )
        async with async_session() as db:
            draft = await rule_service.compile_rule(db, compile_in)
        if not draft.ok or draft.slots is None:
            return error(draft.rejection or "That rule could not be read.")
        draft_id = uuid.uuid4().hex[:8]
        create = RuleCreateIn(
            **compile_in.model_dump(), slots=draft.slots, provider=draft.provider[:40], decisions=draft.decisions
        )
        drafts = dict(ctx.state.get(RULE_DRAFTS_KEY) or {})
        drafts[draft_id] = create.model_dump(mode="json")
        ctx.state[RULE_DRAFTS_KEY] = drafts
        preview = draft.preview
        return {
            "status": "success",
            "source": "Rule draft (not active)",
            "draft_id": draft_id,
            "columns": ["Read-back"],
            "rows": [[draft.description]],
            "figures": {
                "description": draft.description,
                "checked_entries": preview.checked if preview else 0,
                "would_have_fired": preview.fired if preview else 0,
                "confirmed": preview.confirmed if preview else 0,
                "contradicted": preview.contradicted if preview else 0,
                "pending": preview.pending if preview else 0,
                "catches_source_entry": preview.catches_source if preview else None,
                "low_confidence": ", ".join(draft.low_confidence_fields) or "none",
            },
        }

    return await with_policy(ctx, body)


async def activate_lead_rule(draft_id: str, ctx: Context) -> Result:
    """Activates a rule draft compiled earlier in this conversation, so it checks every new entry.

    Call this only when the lead explicitly asks to activate, turn on or save the rule they just reviewed.

    Args:
      draft_id: The draft_id compile_lead_rule returned.

    Returns:
      On success: {'status': 'success', 'action': {...}}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if not policy.is_lead:
            return error("Only consensus leads and admins activate rules.")
        drafts = dict(ctx.state.get(RULE_DRAFTS_KEY) or {})
        raw = drafts.get(draft_id.strip())
        if raw is None:
            return error("There is no rule draft with that id in this conversation; compile the rule first.")
        create = RuleCreateIn.model_validate(raw)
        if create.country_code != policy.country_code or create.mega_segment_id != policy.mega_segment_id:
            return error("That draft belongs to another country or mega-segment.")
        async with async_session() as db:
            rule = await rule_service.create_rule(db, current_user(policy), create)
        drafts.pop(draft_id.strip(), None)
        ctx.state[RULE_DRAFTS_KEY] = drafts
        return _action("rule_activated", "rule", rule.id, f"Activated lead rule {rule.id}: {rule.description}",
                       f"/rules?rule={rule.id}")

    return await with_policy(ctx, body)


async def retire_lead_rule(rule_id: int, ctx: Context) -> Result:
    """Retires an active lead rule so it stops checking new entries. Past flags stay in the ledger.

    Call this only when the lead explicitly asks to retire, remove or turn off a rule.

    Args:
      rule_id: The rule number from list_lead_rules.

    Returns:
      On success: {'status': 'success', 'action': {...}}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if not policy.is_lead:
            return error("Only consensus leads and admins retire rules.")
        async with async_session() as db:
            rule = await db.get(LeadRule, rule_id)
            if rule is None or rule.country_code != policy.country_code or rule.mega_segment_id != policy.mega_segment_id:
                return error(f"Lead rule {rule_id} is not in this country and mega-segment.")
            await rule_service.retire_rule(db, current_user(policy), rule_id)
        return _action("rule_retired", "rule", rule_id, f"Retired lead rule {rule_id}", f"/rules?rule={rule_id}")

    return await with_policy(ctx, body)


ACTION_TOOLS = [
    submit_demand_entry,
    justify_ibp_entry,
    add_entry_note,
    decide_entry,
    bulk_approve_routine,
    compile_lead_rule,
    activate_lead_rule,
    retire_lead_rule,
]
