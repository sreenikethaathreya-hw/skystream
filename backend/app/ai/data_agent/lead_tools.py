"""Read-only chat tools for the consensus lead: coverage, entry detail, reliability, rankings and the audit trail.

get_entry_detail, get_entry_history, get_rep_accuracy_history and draft_rtb also serve reps, limited to their
own entries; the rest are lead and admin only (ScopeGuardPlugin enforces LEAD_ONLY_TOOLS as well).
"""

from collections import defaultdict

from google.adk import Context
from sqlalchemy import select

from app.ai.data_agent.policy import ChatPolicy
from app.ai.data_agent.rep_tools import baseline_impact
from app.ai.data_agent.tool_support import (
    MAX_ROWS,
    Result,
    capture_link,
    consensus_link,
    error,
    ks,
    ledger_link,
    month_name,
    my_segment_ids,
    out_of_scope,
    pct,
    resolve_entry,
    table,
    with_policy,
)
from app.database import async_session
from app.models import ChatAction, Claim, DemandEntry, EntryNote, MonthlyActual
from app.services import consensus_service
from app.services.consensus_service import exception_reasons
from app.services.context_service import (
    COMMITTED_SOURCES,
    current_period,
    ibp_months,
    latest_entries,
    segment_contexts,
    segment_label,
)
from app.services.rep_service import is_weak, track_records
from app.services.settings_service import get_app_settings
from app.services.user_service import owners_by_segment, user_names

RANK_METRICS = (
    "entry_vs_plan_pct",
    "entry_vs_last_year_pct",
    "entry_vs_ibp_pct",
    "range_width_pct",
    "gap_to_plan_ks",
    "share_vs_plan_pts",
)
GROUP_BY = ("driver", "competitor", "evidence_source", "resolution", "rep")


def _lead_only(policy: ChatPolicy) -> Result | None:
    return None if policy.is_lead else error("Only consensus leads and admins can see that.")


async def get_submission_coverage(month: int, ctx: Context) -> Result:
    """Shows, segment by segment, whether a committed number exists for a month and who owns the segment.

    Use this for "which segments have no entry yet", "is October ready to close" or "who has not submitted".

    Args:
      month: A month 1 to 12, or 0 for the first open month.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[segment, owners, entry_ks, status,
      source], ...], 'counts': {...}}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if (blocked := _lead_only(policy)) is not None:
            return blocked
        async with async_session() as db:
            period = await current_period(db, policy.country_code)
            chosen = month or period.clock_month
            if not 1 <= chosen <= 12:
                return error("The year is closed; there is no open month.")
            _, contexts = await segment_contexts(
                db, policy.country_code, policy.mega_segment_id, policy.visible_segment_ids
            )
            entries = await latest_entries(db, policy.country_code, period.year, list(contexts))
            owners = await owners_by_segment(db, policy.country_code, [s for s, _ in contexts.values()])
        rows, counts = [], defaultdict(int)
        for seg, _ in sorted(contexts.values(), key=lambda p: p[0].id):
            entry = entries.get((seg.id, chosen))
            if entry is None or entry.source not in COMMITTED_SOURCES:
                counts["missing"] += 1
                rows.append([segment_label(seg), ", ".join(owners.get(seg.id, [])) or "no rep", None, "missing", ""])
                continue
            counts[entry.status] += 1
            rows.append(
                [segment_label(seg), ", ".join(owners.get(seg.id, [])) or "no rep", ks(entry.value), entry.status,
                 "IBP" if entry.source == "ibp" else "typed"]
            )
        return table(
            f"Coverage for {month_name(chosen)} {period.year}",
            ["Segment", "Owners", "Entry (KS)", "Status", "Source"],
            rows,
            link=("Open Consensus", consensus_link()),
            counts=dict(counts),
            ready_to_close=counts["missing"] == 0
            and not any(counts[s] for s in ("needs_justification", "discuss", "challenged")),
        )

    return await with_policy(ctx, body)


async def get_entry_detail(entry_id: str, segment_id: int, month: int, ctx: Context) -> Result:
    """Gets everything about one entry: number and range, flags, structured claim, triage, the rep's record and notes.

    Use this to walk through an exception, to explain why Jev suggests approve, discuss or challenge, or (for a
    rep) to see why the lead challenged their own entry.

    Args:
      entry_id: The entry id if known, else an empty string.
      segment_id: The micro-segment number when no entry id is given, else 0.
      month: The month 1 to 12 when no entry id is given, else 0.

    Returns:
      On success: {'status': 'success', 'figures': {...}, 'columns': ['Item', 'Detail'], 'rows': [...]}.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        async with async_session() as db:
            entry = await resolve_entry(db, policy, entry_id, segment_id, month)
            if isinstance(entry, dict):
                return entry
            claim = (await db.execute(select(Claim).where(Claim.entry_id == entry.id))).scalar_one_or_none()
            notes = (
                await db.execute(select(EntryNote).where(EntryNote.entry_id == entry.id).order_by(EntryNote.created_at))
            ).scalars().all()
            records = await track_records(db)
            names = await user_names(db)
            _, contexts = await segment_contexts(db, policy.country_code, policy.mega_segment_id, [entry.segment_id])
        record = records.get(entry.user_id)
        rep = names.get(entry.user_id, entry.user_id)
        reasons = exception_reasons(entry, claim, is_weak(record), rep)
        triage = entry.triage or {}
        rows: list[list] = [["Reason for review", r] for r in reasons]
        rows += [["Flag", f.get("message")] for f in entry.flags or []]
        if claim:
            rows.append(["Claim", claim.summary or "none"])
            rows.append(["Claim resolution", claim.resolution])
        if entry.justification:
            rows.append(["Justification", entry.justification])
        rows += [[f"Note from {names.get(n.user_id, n.user_id)}", n.body] for n in notes]
        seg = contexts.get(entry.segment_id)
        figures = {
            "segment": segment_label(seg[0]) if seg else entry.segment_id,
            "month": month_name(entry.month),
            "year": entry.year,
            "rep": rep,
            "entered_ks": ks(entry.value),
            "low_ks": ks(entry.low),
            "high_ks": ks(entry.high),
            "source": f"IBP {entry.snapshot}" if entry.source == "ibp" else "typed in Skystream",
            "status": entry.status,
            "reviewed_by": names.get(entry.reviewed_by or "", entry.reviewed_by),
            "triage_suggests": triage.get("choice", "not triaged"),
            **{f"triage_{k}_pct": pct(v) for k, v in (triage.get("probabilities") or {}).items()},
            "claim_driver": claim.driver if claim else None,
            "claim_competitor": claim.competitor if claim else None,
            "claim_evidence": claim.evidence_source if claim else None,
            "rep_bias_pct": pct(record.bias_pct) if record else None,
            "rep_claim_hit_rate_pct": pct(record.claim_hit_rate) if record else None,
            "rep_weak_record": is_weak(record),
        }
        return table(
            f"Entry {segment_label(seg[0]) if seg else entry.segment_id}, {month_name(entry.month)} by {rep}",
            ["Item", "Detail"],
            rows,
            link=("Open in Consensus", consensus_link(entry.id))
            if policy.is_lead
            else ("Open in Capture", capture_link(entry.segment_id, entry.month)),
            figures=figures,
            entry_id=entry.id,
        )

    return await with_policy(ctx, body)


async def get_rep_accuracy_history(rep_name: str, months: int, ctx: Context) -> Result:
    """Shows how a rep's resolved entries did month by month: bias, range coverage and claim outcomes.

    Use this for "has Rep B's bias changed", "is Rep A getting more accurate" or (a rep) "how have my last
    months gone". A rep only sees their own history.

    Args:
      rep_name: Part of a rep's name (leads), or an empty string for the caller (reps) or every rep (leads).
      months: How many recent resolved months to show, 1 to 24; 0 means 12.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[rep, year, month, resolved, bias_pct,
      in_range_pct, confirmed, contradicted], ...]}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        async with async_session() as db:
            names = await user_names(db)
            query = (
                select(DemandEntry, Claim)
                .join(Claim, Claim.entry_id == DemandEntry.id)
                .where(
                    DemandEntry.country_code == policy.country_code,
                    DemandEntry.segment_id.in_(policy.visible_segment_ids),
                    DemandEntry.status != "superseded",
                    Claim.resolution != "pending",
                )
            )
            if policy.role == "rep":
                query = query.where(DemandEntry.user_id == policy.user_id)
            pairs = (await db.execute(query)).all()
            actuals = {
                (a.segment_id, a.year, a.month): a.qty_ks
                for a in (
                    await db.execute(
                        select(MonthlyActual).where(
                            MonthlyActual.country_code == policy.country_code,
                            MonthlyActual.segment_id.in_(policy.visible_segment_ids),
                        )
                    )
                ).scalars()
            }

        def outcome(e: DemandEntry, c: Claim) -> tuple[float | None, bool | None]:
            detail = c.resolution_detail or {}
            if detail.get("errorPct") is not None:
                return detail["errorPct"], detail.get("inRange")
            actual = actuals.get((e.segment_id, e.year, e.month))
            if not actual:
                return None, None
            return (e.value - actual) / actual, e.low <= actual <= e.high

        needle = rep_name.strip().lower() if policy.is_lead else ""
        buckets: dict[tuple[str, int, int], list] = defaultdict(list)
        for e, c in pairs:
            name = names.get(e.user_id, e.user_id)
            if needle and needle not in name.lower():
                continue
            buckets[(name, e.year, e.month)].append((e, c))
        limit = max(1, min(months or 12, 24))
        recent = sorted({(y, m) for _, y, m in buckets}, reverse=True)[:limit]
        rows = []
        for (name, year, month), items in sorted(buckets.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
            if (year, month) not in recent:
                continue
            outcomes = [outcome(e, c) for e, c in items]
            errors = [err for err, _ in outcomes if err is not None]
            inside = [hit for _, hit in outcomes if hit is not None]
            rows.append(
                [
                    name, year, month_name(month), len(items),
                    pct(sum(errors) / len(errors)) if errors else None,
                    pct(sum(1 for i in inside if i) / len(inside)) if inside else None,
                    sum(1 for _, c in items if c.resolution == "confirmed"),
                    sum(1 for _, c in items if c.resolution == "contradicted"),
                ]
            )
        return table(
            "Accuracy by month",
            ["Rep", "Year", "Month", "Resolved", "Bias (%)", "In range (%)", "Confirmed", "Contradicted"],
            rows[: MAX_ROWS * 2],
            link=("Open Track record", "/reps"),
        )

    return await with_policy(ctx, body)


async def draft_rtb(segment_id: int, ctx: Context) -> Result:
    """Drafts a short reasons-to-believe narrative for a segment from confirmed claims and market context.

    Use this when a lead asks to draft reasons to believe (RTB) for the consensus meeting. The draft only cites
    facts already in the data.

    Args:
      segment_id: The micro-segment number.

    Returns:
      On success: {'status': 'success', 'text': ..., 'columns': ['Draft'], 'rows': [[text]], 'cited_entries': n}.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if not policy.can_see(segment_id):
            return out_of_scope(segment_id)
        async with async_session() as db:
            rtb = await consensus_service.draft_rtb(db, policy.country_code, segment_id)
        return table(
            "Reasons to believe (draft)",
            ["Draft"],
            [[rtb.text]],
            link=("Open Consensus", consensus_link()),
            text=rtb.text,
            written_by=rtb.provider,
            cited_entries=len(rtb.cited_entry_ids),
        )

    return await with_policy(ctx, body)


async def get_supply_export(ctx: Context) -> Result:
    """Gives the download link for the supply handoff CSV (approved low, mid and high per segment and month).

    Use this when a lead asks to export or hand off the supply ranges.

    Returns:
      On success: {'status': 'success', 'download': {...}}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if (blocked := _lead_only(policy)) is not None:
            return blocked
        return {
            "status": "success",
            "source": "Supply handoff",
            "download": {
                "label": "Download supply handoff CSV",
                "href": f"/export/supply.csv?country={policy.country_code}&mega={policy.mega_segment_id}",
            },
        }

    return await with_policy(ctx, body)


async def rank_segments(metric: str, order: str, month: int, limit: int, ctx: Context) -> Result:
    """Ranks segments by how far the latest entry sits from plan, last year or IBP, by range width, or by gap.

    Use this for "where does the rep entry differ most from IBP", "which segments are furthest above plan" or
    "which segments have the widest ranges". Differences are computed here; never work them out yourself.

    Args:
      metric: One of entry_vs_plan_pct, entry_vs_last_year_pct, entry_vs_ibp_pct, range_width_pct (all for one
        month), gap_to_plan_ks or share_vs_plan_pts (full year).
      order: "desc" for largest first or "asc" for smallest first.
      month: The month 1 to 12 for the entry metrics, or 0 for the first open month.
      limit: How many rows, 1 to 25; 0 means 10.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[segment, metric_value, entry_ks,
      reference_ks], ...]}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if (blocked := _lead_only(policy)) is not None:
            return blocked
        if metric not in RANK_METRICS:
            return error(f"metric must be one of {', '.join(RANK_METRICS)}")
        async with async_session() as db:
            period, contexts = await segment_contexts(
                db, policy.country_code, policy.mega_segment_id, policy.visible_segment_ids
            )
            chosen = month or period.clock_month
            if not 1 <= chosen <= 12:
                return error("Choose a month 1 to 12.")
            entries = await latest_entries(db, policy.country_code, period.year, list(contexts))
            ibp = await ibp_months(db, policy.country_code, period.year, list(contexts))
            thresholds = (await get_app_settings(db)).thresholds
        scored = []
        for seg, c in contexts.values():
            entry = entries.get((seg.id, chosen))
            value = entry.value if entry is not None and entry.source in COMMITTED_SOURCES else None
            if metric in ("gap_to_plan_ks", "share_vs_plan_pts"):
                impact = baseline_impact(c, thresholds)
                score = (
                    impact.gap_to_plan
                    if metric == "gap_to_plan_ks"
                    else (impact.volume_share - impact.plan_volume_share) * 100
                )
                scored.append((seg, score, ks(impact.fy_estimate), ks(impact.plan_fy)))
                continue
            if value is None:
                continue
            if metric == "range_width_pct":
                scored.append((seg, (entry.high - entry.low) / value * 100 if value else 0.0, ks(value), None))
                continue
            reference = {
                "entry_vs_plan_pct": c.monthly_plan[chosen - 1],
                "entry_vs_last_year_pct": c.last_year_monthly[chosen - 1],
                "entry_vs_ibp_pct": next((m.qty_ks for m in ibp.get(seg.id, []) if m.month == chosen), None),
            }[metric]
            if not reference:
                continue
            scored.append((seg, (value - reference) / reference * 100, ks(value), ks(reference)))
        scored.sort(key=lambda s: s[1], reverse=order.strip().lower() != "asc")
        n = max(1, min(limit or 10, MAX_ROWS))
        return table(
            f"Segments ranked by {metric}" + ("" if metric in ("gap_to_plan_ks", "share_vs_plan_pts")
                                               else f", {month_name(chosen)}"),
            ["Segment", metric, "Entry or estimate (KS)", "Reference (KS)"],
            [[segment_label(seg), round(score, 1), entry_ks, ref] for seg, score, entry_ks, ref in scored[:n]],
            ranked=len(scored),
        )

    return await with_policy(ctx, body)


async def summarize_claims(group_by: str, month: int, ctx: Context) -> Result:
    """Counts claims by driver, competitor, evidence, resolution or rep, with how many were confirmed.

    Use this for "what drivers are reps citing this month", "which competitors come up most" or "which
    evidence sources hold up".

    Args:
      group_by: One of driver, competitor, evidence_source, resolution or rep.
      month: The entry month 1 to 12 in the planning year, or 0 for every month and year.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[group, claims, confirmed, contradicted,
      pending], ...]}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if (blocked := _lead_only(policy)) is not None:
            return blocked
        if group_by not in GROUP_BY:
            return error(f"group_by must be one of {', '.join(GROUP_BY)}")
        async with async_session() as db:
            period = await current_period(db, policy.country_code)
            query = (
                select(DemandEntry, Claim)
                .join(Claim, Claim.entry_id == DemandEntry.id)
                .where(
                    DemandEntry.country_code == policy.country_code,
                    DemandEntry.segment_id.in_(policy.visible_segment_ids),
                    DemandEntry.status != "superseded",
                )
            )
            if month:
                query = query.where(DemandEntry.year == period.year, DemandEntry.month == month)
            pairs = (await db.execute(query)).all()
            names = await user_names(db)
        groups: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for e, c in pairs:
            key = names.get(e.user_id, e.user_id) if group_by == "rep" else getattr(c, group_by) or "none"
            groups[key]["claims"] += 1
            groups[key][c.resolution] += 1
        rows = [
            [k, g["claims"], g["confirmed"], g["contradicted"], g["pending"]]
            for k, g in sorted(groups.items(), key=lambda kv: -kv[1]["claims"])
        ]
        return table(
            f"Claims by {group_by}" + (f", {month_name(month)} {period.year}" if month else ""),
            [group_by.replace("_", " ").capitalize(), "Claims", "Confirmed", "Contradicted", "Pending"],
            rows[:MAX_ROWS],
            link=("Open in Ledger", ledger_link()),
            total_claims=len(pairs),
        )

    return await with_policy(ctx, body)


async def get_entry_history(segment_id: int, month: int, ctx: Context) -> Result:
    """Shows every submission for a segment and month this year, including replaced ones, who reviewed them and
    which changes came through the chat assistant.

    Use this for "who approved this and when", "what changed between the two October submissions" or an audit.

    Args:
      segment_id: The micro-segment number.
      month: The month 1 to 12.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[submitted_at, rep, value_ks, low_ks,
      high_ks, status, source, reviewed_by, reviewed_at], ...], 'chat_changes': [...]}.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if not policy.can_see(segment_id):
            return out_of_scope(segment_id)
        if not 1 <= month <= 12:
            return error("Choose a month 1 to 12.")
        async with async_session() as db:
            if policy.role == "rep" and segment_id not in await my_segment_ids(db, policy):
                return error("Reps can only see the history of their own segments.")
            period = await current_period(db, policy.country_code)
            entries = (
                await db.execute(
                    select(DemandEntry)
                    .where(
                        DemandEntry.country_code == policy.country_code,
                        DemandEntry.segment_id == segment_id,
                        DemandEntry.year == period.year,
                        DemandEntry.month == month,
                    )
                    .order_by(DemandEntry.created_at)
                )
            ).scalars().all()
            actions = (
                await db.execute(
                    select(ChatAction)
                    .where(ChatAction.target_id.in_([e.id for e in entries]), ChatAction.status == "success")
                    .order_by(ChatAction.created_at)
                )
            ).scalars().all() if entries else []
            names = await user_names(db)
        rows = [
            [
                e.created_at.strftime("%Y-%m-%d %H:%M"), names.get(e.user_id, e.user_id), ks(e.value), ks(e.low),
                ks(e.high), e.status, "IBP" if e.source == "ibp" else e.source,
                names.get(e.reviewed_by or "", e.reviewed_by or ""), e.reviewed_at.strftime("%Y-%m-%d %H:%M")
                if e.reviewed_at else "",
            ]
            for e in entries
        ]
        return table(
            f"History for micro-segment {segment_id}, {month_name(month)} {period.year}",
            ["Submitted", "Rep", "Value (KS)", "Low (KS)", "High (KS)", "Status", "Source", "Reviewed by",
             "Reviewed at"],
            rows,
            link=("Open in Ledger", ledger_link()),
            chat_changes=[
                f"{a.created_at.strftime('%Y-%m-%d %H:%M')} {names.get(a.user_id, a.user_id)}: {a.tool}"
                for a in actions
            ],
        )

    return await with_policy(ctx, body)


LEAD_TOOLS = [
    get_submission_coverage,
    get_entry_detail,
    get_rep_accuracy_history,
    draft_rtb,
    get_supply_export,
    rank_segments,
    summarize_claims,
    get_entry_history,
]
