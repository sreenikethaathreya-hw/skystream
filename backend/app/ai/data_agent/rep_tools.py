"""Read-only chat tools for the sales rep's day: briefing, flags, what-if, context, claims and month close.

Every tool reads the caller's policy, refuses segments outside it and returns figures rounded like the UI.
None of them saves anything; preview_entry_impact and check_justification only run the app's own checks on
numbers and words the user typed.
"""

from collections import defaultdict

from google.adk import Context
from sqlalchemy import func, select

from app.ai.data_agent import glossary
from app.ai.data_agent.policy import ChatPolicy
from app.ai.data_agent.tool_support import (
    MAX_ROWS,
    Result,
    capture_link,
    error,
    ks,
    latest_entry,
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
from app.models import (
    Claim,
    DemandEntry,
    EntryNote,
    GrowerPotential,
    IbpForecast,
    LeadRule,
    MarketYear,
    PlanYear,
    Segment,
    UploadBatch,
    VarietyMap,
)
from app.schemas.api import EntryIn
from app.schemas.demand_math import EntryInput, Impact, SegmentContext, Thresholds
from app.services import entry_service
from app.services.consensus_service import exception_reasons
from app.services.context_service import (
    COMMITTED_SOURCES,
    current_period,
    latest_entries,
    segment_contexts,
    segment_label,
)
from app.services.demand_math import compute_impact
from app.services.entry_service import scope_filter
from app.services.rep_service import is_weak, track_records
from app.services.settings_service import get_app_settings
from app.services.user_service import UNASSIGNED, user_names

FLAG_CHECKS: dict[str, tuple[str, str]] = {
    "no_market": ("The segment has no market size this year, so share cannot be checked.", ""),
    "share_over_100": ("Implied full-year share above the whole market.", ""),
    "share_above_history": ("Implied share more than a margin above the highest historical share.",
                            "share_history_margin_pts"),
    "share_jump": ("The share change one entry causes on its own.", "share_jump_pts"),
    "implied_ha_over_market": ("Hectares the volume needs vs the hectares the market plants.", ""),
    "month_outlier": ("Distance from both the month's plan and last year, in sigmas.", "month_sigma_multiplier"),
    "against_market_trend": ("Demand moving against the planted-area trend.", "market_trend_pct"),
    "price_carrying": ("Price carrying the revenue change while volume falls.", "price_carrying_share"),
    "above_grower_potential": ("Mega-segment hectares on Syngenta seed vs CRM grower potential.", ""),
    "range_too_wide": ("The low-high spread as a share of the number.", "range_width_pct"),
    "price_outside_history": ("Net price vs the historical price band.", "price_band_pct"),
    "claim_direction_mismatch": ("The justification points the other way from the number.", ""),
    "claim_size_mismatch": ("The size the justification gives does not match the change in the number.", ""),
}
THRESHOLD_UNITS = {
    "share_history_margin_pts": (1, " pts"),
    "share_jump_pts": (1, " pts"),
    "month_sigma_multiplier": (1, " sigma"),
    "market_trend_pct": (100, "% area change"),
    "price_carrying_share": (100, "% of the revenue movement"),
    "range_width_pct": (100, "% of the number"),
    "price_band_pct": (100, "% beyond the price history"),
}


def threshold_text(field: str, thresholds: Thresholds) -> str:
    if not field:
        return "fixed check"
    scale, unit = THRESHOLD_UNITS[field]
    return f"{getattr(thresholds, field) * scale:g}{unit}"


def baseline_impact(c: SegmentContext, thresholds: Thresholds) -> Impact:
    """The picture with the latest entries (else plan) in every open month, as Capture shows it before typing."""
    open_month = c.clock_month if c.clock_month <= 12 else None
    month = open_month or 12
    baseline = c.submitted.get(str(month), c.monthly_plan[month - 1]) if open_month else 0.0
    return compute_impact(c, EntryInput(month=month, value=baseline, low=baseline, high=baseline), thresholds)


async def _labels(db, ids) -> dict[int, str]:
    rows = (await db.execute(select(Segment).where(Segment.id.in_(list(ids))))).scalars()
    return {s.id: segment_label(s) for s in rows}


async def get_my_briefing(ctx: Context) -> Result:
    """Lists what needs the caller's attention now, newest first.

    Use this for "what needs my attention", "what should I do today", "catch me up" or "is the month ready
    to close". For a rep: open months with no entry yet, IBP numbers waiting for a justification, entries the
    lead marked for discussion or challenged (with the latest note), pending claims and recently resolved
    claims. For a consensus lead or admin: open exceptions, entries waiting on reps, coverage gaps for the
    first open month and the latest notes from reps.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[item, segment, month, status, detail,
      entry_id], ...], 'counts': {...}}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        async with async_session() as db:
            period = await current_period(db, policy.country_code)
            mine = await my_segment_ids(db, policy)
            labels = await _labels(db, policy.visible_segment_ids)
            query = (
                select(DemandEntry, Claim)
                .outerjoin(Claim, Claim.entry_id == DemandEntry.id)
                .where(
                    DemandEntry.country_code == policy.country_code,
                    DemandEntry.segment_id.in_(mine),
                    DemandEntry.source.in_(COMMITTED_SOURCES),
                    DemandEntry.status != "superseded",
                )
                .order_by(DemandEntry.created_at.desc())
            )
            if policy.role == "rep":
                query = query.where(DemandEntry.user_id.in_([policy.user_id, UNASSIGNED]))
            pairs = (await db.execute(query)).all()
            ids = [e.id for e, _ in pairs]
            notes = (
                await db.execute(
                    select(EntryNote).where(EntryNote.entry_id.in_(ids)).order_by(EntryNote.created_at.desc())
                )
            ).scalars().all() if ids else []
            names = await user_names(db)
            records = await track_records(db) if policy.is_lead else {}

        latest_note = {}
        for n in notes:
            latest_note.setdefault(n.entry_id, n)
        open_month = period.clock_month if period.clock_month <= 12 else None
        rows: list[list] = []
        counts: dict[str, int] = defaultdict(int)
        this_year = [(e, c) for e, c in pairs if e.year == period.year]

        if open_month:
            covered = {e.segment_id for e, _ in this_year if e.month == open_month}
            for seg in sorted(set(mine) - covered):
                counts["no_entry_yet"] += 1
                rows.append(["No entry yet", labels.get(seg, str(seg)), month_name(open_month), "missing",
                             "First open month", None])

        for entry, claim in this_year:
            label = labels.get(entry.segment_id, str(entry.segment_id))
            note = latest_note.get(entry.id)
            note_text = f"{names.get(note.user_id, note.user_id)}: {note.body}" if note else ""
            if entry.status == "needs_justification":
                counts["needs_justification"] += 1
                rows.append(["IBP number needs a justification", label, month_name(entry.month), entry.status,
                             note_text or "Add a range and reason in Capture", entry.id])
            elif entry.status in ("discuss", "challenged"):
                counts[entry.status] += 1
                what = "Lead challenged this entry" if entry.status == "challenged" else "Lead wants to discuss"
                rows.append([what, label, month_name(entry.month), entry.status, note_text or "no note", entry.id])
            elif policy.is_lead and entry.status == "submitted":
                weak = is_weak(records.get(entry.user_id))
                reasons = exception_reasons(entry, claim, weak, names.get(entry.user_id, entry.user_id))
                if reasons:
                    counts["open_exceptions"] += 1
                    rows.append(["Exception to review", label, month_name(entry.month), entry.status,
                                 "; ".join(reasons), entry.id])
                else:
                    counts["routine"] += 1
            if policy.is_lead and note and note.user_id != policy.user_id:
                counts["notes_from_reps"] += 1

        if policy.role == "rep":
            for entry, claim in pairs:
                if claim is None:
                    continue
                label = labels.get(entry.segment_id, str(entry.segment_id))
                if claim.resolution == "pending":
                    counts["pending_claims"] += 1
                    rows.append(["Claim waiting for actuals", label, month_name(entry.month), "pending",
                                 claim.summary or "no summary", entry.id])
                elif claim.resolved_at is not None and counts["recently_resolved"] < 5:
                    counts["recently_resolved"] += 1
                    rows.append([f"Claim {claim.resolution}", label, month_name(entry.month), claim.resolution,
                                 claim.summary or "no summary", entry.id])

        return table(
            f"What needs your attention, {month_name(open_month) + ' ' + str(period.year) if open_month else 'year closed'}",
            ["To do", "Segment", "Month", "Status", "Detail", "Entry id"],
            rows[:MAX_ROWS],
            link=("Open Consensus", "/consensus") if policy.is_lead else ("Open in Capture", "/capture"),
            counts=dict(counts),
            open_month=month_name(open_month) if open_month else "year closed",
        )

    return await with_policy(ctx, body)


async def explain_entry_flags(segment_id: int, month: int, entry_id: str, ctx: Context) -> Result:
    """Explains why an entry was flagged: each flag or lead rule, what it checks and the limit it uses.

    Use this for "why is my entry flagged", "what does this flag mean" or "which rule fired". It never works
    out what number would clear a flag.

    Args:
      segment_id: The micro-segment number, or 0 when entry_id is given.
      month: The month 1 to 12, or 0 when entry_id is given.
      entry_id: The entry id if known (for example from the page the user is on), else an empty string.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[flag, severity, message, what_it_checks,
      limit], ...], 'figures': {...}}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        async with async_session() as db:
            entry = await resolve_entry(db, policy, entry_id, segment_id, month)
            if isinstance(entry, dict):
                return entry
            thresholds = (await get_app_settings(db)).thresholds
            rule_ids = [
                int(f["code"].split("_")[2]) for f in entry.flags or [] if f.get("code", "").startswith("lead_rule_")
            ]
            rules = {
                r.id: r for r in (await db.execute(select(LeadRule).where(LeadRule.id.in_(rule_ids)))).scalars()
            }
            labels = await _labels(db, [entry.segment_id])
        rows = []
        for flag in entry.flags or []:
            code = flag.get("code", "")
            if code.startswith("lead_rule_"):
                rule = rules.get(int(code.split("_")[2]))
                checks = f"Lead rule: {rule.text}" if rule else "A consensus lead's rule"
                limit = (
                    "the reason the rule requires" if code.endswith("_unmet") else (rule.description if rule else "")
                )
            else:
                checks, field = FLAG_CHECKS.get(code, ("A plausibility check", ""))
                limit = threshold_text(field, thresholds)
            rows.append([code, flag.get("severity"), flag.get("message"), checks, limit])
        impact = entry.impact or {}
        figures = {
            "segment": labels.get(entry.segment_id),
            "month": month_name(entry.month),
            "entered_ks": ks(entry.value),
            "low_ks": ks(entry.low),
            "high_ks": ks(entry.high),
            "month_plan_ks": ks(impact.get("monthExpected")),
            "month_last_year_ks": ks(impact.get("monthLastYear")),
            "month_historical_avg_ks": ks(impact.get("monthHistoryAvg")),
            "share_with_entry_pct": pct(impact.get("volumeShare")),
            "share_before_entry_pct": pct(impact.get("baselineShare")),
            "highest_historical_share_pct": pct(impact.get("maxHistoricalShare")),
            "implied_ha": ks(impact.get("impliedHa")),
            "market_ha": ks(impact.get("marketHa")),
            "status": entry.status,
            "flags_fired": len(rows),
        }
        return table(
            f"Flags on {labels.get(entry.segment_id, entry.segment_id)}, {month_name(entry.month)}",
            ["Flag", "Severity", "Message", "What it checks", "Limit"],
            rows,
            link=("Open in Capture", capture_link(entry.segment_id, entry.month)),
            figures=figures,
            entry_id=entry.id,
        )

    return await with_policy(ctx, body)


async def preview_entry_impact(
    segment_id: int, month: int, value: float, low: float, high: float, price: float, ctx: Context
) -> Result:
    """Shows what a number the user typed would do to share, year-to-go and hectares, and which flags fire.

    Use this for "what if I enter ..." questions. Pass only numbers the user wrote in this message; never
    choose or adjust a number. Nothing is saved.

    Args:
      segment_id: The micro-segment number.
      month: The open month 1 to 12 the number is for.
      value: The demand number in KS exactly as the user wrote it.
      low: The low end of the user's range in KS, or 0 if they gave none.
      high: The high end of the user's range in KS, or 0 if they gave none.
      price: The net price per KS in USD if the user gave one, else 0.

    Returns:
      On success: {'status': 'success', 'figures': {...}, 'columns': [...], 'rows': [[flag, severity,
      message], ...]}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if not policy.can_see(segment_id):
            return out_of_scope(segment_id)
        if value <= 0:
            return error("Tell me the number you want to try, in KS.")
        lo, hi = (low or value), (high or value)
        if not lo <= value <= hi:
            return error("The range must include the number: low <= number <= high.")
        async with async_session() as db:
            result = await entry_service.analyze(
                db,
                EntryIn(
                    country_code=policy.country_code, segment_id=segment_id, month=month, value=value,
                    low=lo, high=hi, price=price or None,
                ),
            )
            labels = await _labels(db, [segment_id])
        i = result.impact
        figures = {
            "segment": labels.get(segment_id),
            "month": month_name(month),
            "entered_ks": ks(value),
            "low_ks": ks(lo),
            "high_ks": ks(hi),
            "range_given": bool(low or high),
            "month_plan_ks": ks(i.month_expected),
            "month_last_year_ks": ks(i.month_last_year),
            "share_with_entry_pct": pct(i.volume_share),
            "share_before_entry_pct": pct(i.baseline_share),
            "share_change_pts": round(i.share_jump_pts, 1),
            "plan_share_pct": pct(i.plan_volume_share),
            "full_year_estimate_ks": ks(i.fy_estimate),
            "full_year_plan_ks": ks(i.plan_fy),
            "gap_to_plan_ks": ks(i.gap_to_plan),
            "year_to_go_ks": ks(i.ytg_remaining),
            "implied_ha": ks(i.implied_ha),
            "market_ha": ks(i.market_ha),
            "flags_fired": len(result.flags),
            "saved": False,
        }
        return table(
            f"What-if for {labels.get(segment_id, segment_id)}, {month_name(month)} (not saved)",
            ["Flag", "Severity", "Message"],
            [[f.code, f.severity, f.message] for f in result.flags],
            link=("Open in Capture", capture_link(segment_id, month)),
            figures=figures,
        )

    return await with_policy(ctx, body)


async def get_market_notes(segment_id: int, ctx: Context) -> Result:
    """Gets the market and point-of-view notes, the plan comment and the planted-area trend for a segment.

    Use this for context before entering a number: what the market notes say, what the plan comment says,
    and whether planted area is growing or shrinking.

    Args:
      segment_id: The micro-segment number.

    Returns:
      On success: {'status': 'success', 'columns': ['Note', 'Text'], 'rows': [...], 'figures': {...}}.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if not policy.can_see(segment_id):
            return out_of_scope(segment_id)
        async with async_session() as db:
            period, contexts = await segment_contexts(db, policy.country_code, policy.mega_segment_id, [segment_id])
            if segment_id not in contexts:
                return out_of_scope(segment_id)
            market = (
                await db.execute(
                    select(MarketYear).where(
                        MarketYear.country_code == policy.country_code,
                        MarketYear.segment_id == segment_id,
                        MarketYear.year.in_([period.year, period.year - 1]),
                    )
                )
            ).scalars().all()
            plan = (
                await db.execute(
                    select(PlanYear).where(
                        PlanYear.country_code == policy.country_code,
                        PlanYear.segment_id == segment_id,
                        PlanYear.year == period.year,
                    )
                )
            ).scalar_one_or_none()
        seg, c = contexts[segment_id]
        by_year = {m.year: m for m in market}
        now, before = by_year.get(period.year), by_year.get(period.year - 1)
        rows = [[k.replace("_", " ").capitalize(), v] for k, v in ((now.notes or {}) if now else {}).items() if v]
        if plan and plan.comment:
            rows.append(["Plan comment", plan.comment])
        if c.market_trend_note:
            rows.append(["Market trend", c.market_trend_note])
        trend = (now.hectares - before.hectares) / before.hectares if now and before and before.hectares else None
        return table(
            f"Market notes for {segment_label(seg)}, {period.year}",
            ["Note", "Text"],
            rows,
            link=("Open in Capture", capture_link(segment_id)),
            figures={
                "market_ha": ks(now.hectares) if now else None,
                "market_ha_last_year": ks(before.hectares) if before else None,
                "area_change_pct": pct(trend),
                "market_qty_ks": ks(c.market_qty_ks),
            },
        )

    return await with_policy(ctx, body)


async def get_grower_potential(ctx: Context) -> Result:
    """Gets CRM grower potential for the selected mega-segment's crop: hectares by variety and seed owner.

    Use this for questions about grower potential, which varieties growers plant, or the hectare ceiling the
    above_grower_potential flag compares against.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[variety, owner, hectares], ...],
      'figures': {...}}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        async with async_session() as db:
            crop = (
                await db.execute(
                    select(Segment.mega_segment_desc).where(Segment.mega_segment_id == policy.mega_segment_id).limit(1)
                )
            ).scalar_one_or_none()
            if crop is None:
                return error("No segments are loaded for this mega-segment.")
            rows = (
                await db.execute(
                    select(GrowerPotential.variety, GrowerPotential.owner, func.sum(GrowerPotential.hectares))
                    .where(GrowerPotential.country_code == policy.country_code, GrowerPotential.crop_local == crop.upper())
                    .group_by(GrowerPotential.variety, GrowerPotential.owner)
                    .order_by(func.sum(GrowerPotential.hectares).desc())
                )
            ).all()
            _, contexts = await segment_contexts(
                db, policy.country_code, policy.mega_segment_id, policy.visible_segment_ids[:1]
            )
        by_owner: dict[str, float] = defaultdict(float)
        for _, owner, ha in rows:
            by_owner[owner] += ha or 0.0
        ceiling = next(iter(contexts.values()))[1].mega.grower_ceiling_ha if contexts else None
        return table(
            f"Grower potential for {crop.title()}",
            ["Variety", "Seed owner", "Hectares"],
            [[v or "unnamed", o, ks(ha)] for v, o, ha in rows[:MAX_ROWS]],
            figures={
                "grower_ceiling_ha": ks(ceiling),
                **{f"{owner}_ha": ks(ha) for owner, ha in by_owner.items()},
            },
        )

    return await with_policy(ctx, body)


def _claim_gaps(claim, flags: int) -> list[str]:
    gaps = []
    if claim.driver in ("other", "unclear", "none"):
        gaps.append("No clear driver: say what changed (competitor, area, pest, weather, launch, customer, price).")
    if claim.driver == "competitor_move" and not claim.competitor:
        gaps.append("Name the competitor.")
    if not claim.evidence_source or claim.evidence_source == "none":
        gaps.append("Say where the evidence comes from (customer, distributor, trial, statistics).")
    if claim.specificity is not None and claim.specificity < 1.5:
        gaps.append("Too vague to check later: add who, what and how much.")
    if claim.verifiable is not None and claim.verifiable < 0.5:
        gaps.append("Hard to check against actuals.")
    if flags and claim.addresses_flags is not None and claim.addresses_flags < 0.5:
        gaps.append("Does not address the flags that fired.")
    gaps += [m.message for m in claim.mismatches]
    return gaps


async def check_justification(
    segment_id: int, month: int, justification: str, value: float, low: float, high: float, ctx: Context
) -> Result:
    """Reads the user's draft justification the way the app will and lists what is missing. Nothing is saved.

    Use this when the user asks whether their reason is good or specific enough. Pass the user's own words
    exactly; never write or improve the justification for them.

    Args:
      segment_id: The micro-segment number.
      month: The open month 1 to 12.
      justification: The user's draft, quoted exactly from their message.
      value: The number the user typed in KS, or 0 to use the latest entry for that month.
      low: The user's low in KS, or 0 to use the latest entry's.
      high: The user's high in KS, or 0 to use the latest entry's.

    Returns:
      On success: {'status': 'success', 'figures': {driver, direction, competitor, evidence, specificity,
      ...}, 'columns': ['Missing or weak'], 'rows': [...]}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if not policy.can_see(segment_id):
            return out_of_scope(segment_id)
        if not justification.strip():
            return error("Paste or type the justification you want checked.")
        async with async_session() as db:
            number, lo, hi = value, low, high
            if not number:
                entry = await latest_entry(db, policy, segment_id, month)
                if entry is None:
                    return error("Tell me the number this justification is for, or open the entry first.")
                number, lo, hi = entry.value, entry.low, entry.high
            lo, hi = lo or number, hi or number
            result = await entry_service.analyze(
                db,
                EntryIn(
                    country_code=policy.country_code, segment_id=segment_id, month=month, value=number, low=lo,
                    high=hi, justification=justification.strip()[:600],
                ),
            )
        claim = result.claim
        if claim is None:
            return error("The justification could not be read.")
        gaps = _claim_gaps(claim, len(result.flags))
        return table(
            "Justification check (not saved)",
            ["Missing or weak"],
            [[g] for g in gaps] or [["Nothing missing: the reason names a driver, evidence and a checkable claim."]],
            figures={
                "driver": claim.driver,
                "direction": claim.direction,
                "size": claim.magnitude_label,
                "competitor": claim.competitor,
                "variety": claim.variety,
                "evidence": claim.evidence_source,
                "specificity": claim.specificity_label,
                "flags_fired": len(result.flags),
                "summary": claim.summary,
                "read_by": claim.provider,
                "saved": False,
            },
        )

    return await with_policy(ctx, body)


async def list_claims(status: str, driver: str, competitor: str, rep_name: str, month: int, ctx: Context) -> Result:
    """Lists structured claims with how and when they are checked. A rep sees only their own claims.

    Use this for "which of my claims are pending", "which claims cited a competitor" or "why was my claim
    contradicted".

    Args:
      status: pending, confirmed, contradicted, inconclusive, or an empty string for any.
      driver: A driver such as competitor_move or area_change, or an empty string for any.
      competitor: Part of a competitor name, or an empty string for any.
      rep_name: Part of a rep's name (leads only), or an empty string for every rep.
      month: The entry month 1 to 12, or 0 for every month.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[segment, month, year, rep, driver,
      competitor, evidence, summary, resolution, actual_ks, in_range], ...], 'total_matching': n}.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        async with async_session() as db:
            query = (
                select(DemandEntry, Claim)
                .join(Claim, Claim.entry_id == DemandEntry.id)
                .where(DemandEntry.segment_id.in_(policy.visible_segment_ids), DemandEntry.status != "superseded")
                .order_by(DemandEntry.year.desc(), DemandEntry.month.desc())
            )
            query = scope_filter(query, policy.country_code, None)
            if policy.role == "rep":
                query = query.where(DemandEntry.user_id == policy.user_id)
            pairs = (await db.execute(query)).all()
            labels = await _labels(db, policy.visible_segment_ids)
            names = await user_names(db)
        wanted = [
            (e, c)
            for e, c in pairs
            if (not status or c.resolution == status.strip().lower())
            and (not driver or c.driver == driver.strip().lower())
            and (not competitor or competitor.strip().lower() in (c.competitor or "").lower())
            and (not month or e.month == month)
            and (not rep_name or rep_name.strip().lower() in names.get(e.user_id, e.user_id).lower())
        ]
        rows = []
        for e, c in wanted[:MAX_ROWS]:
            detail = c.resolution_detail or {}
            rows.append(
                [
                    labels.get(e.segment_id, str(e.segment_id)), month_name(e.month), e.year,
                    names.get(e.user_id, e.user_id), c.driver, c.competitor or "none", c.evidence_source or "none",
                    c.summary or "none", c.resolution, ks(detail.get("actual")),
                    {True: "yes", False: "no"}.get(detail.get("inRange"), "n/a"),
                ]
            )
        return table(
            "Claims",
            ["Segment", "Month", "Year", "Rep", "Driver", "Competitor", "Evidence", "Claim", "Resolution",
             "Actual (KS)", "Actual in range"],
            rows,
            link=("Open in Ledger", ledger_link()),
            total_matching=len(wanted),
        )

    return await with_policy(ctx, body)


async def lookup_variety(variety: str, ctx: Context) -> Result:
    """Finds which micro-segment a variety belongs to, from the variety map and IBP snapshots.

    Use this for "which segment is variety X in" or when the user names a variety instead of a segment.

    Args:
      variety: Part of the variety name, for example "Bokken".

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[variety, segment_id, segment, in_scope],
      ...]}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        needle = " ".join(variety.split()).upper()
        if len(needle) < 2:
            return error("Give at least two letters of the variety name.")
        async with async_session() as db:
            mapped = (
                await db.execute(
                    select(VarietyMap.variety, VarietyMap.segment_id).where(
                        VarietyMap.country_code == policy.country_code, func.upper(VarietyMap.variety).contains(needle)
                    )
                )
            ).all()
            forecast = (
                await db.execute(
                    select(IbpForecast.variety, IbpForecast.segment_id)
                    .where(IbpForecast.country_code == policy.country_code, func.upper(IbpForecast.variety).contains(needle))
                    .distinct()
                )
            ).all()
            labels = await _labels(db, {s for _, s in mapped + forecast})
        seen, rows = set(), []
        for name, seg in [*mapped, *forecast]:
            key = (name.upper(), seg)
            if key in seen:
                continue
            seen.add(key)
            visible = policy.can_see(seg)
            rows.append([name.title(), seg, labels.get(seg, str(seg)) if visible else "not in your scope",
                         "yes" if visible else "no"])
        return table(f"Varieties matching {variety.strip()}", ["Variety", "Segment id", "Segment", "In your scope"],
                     rows[:MAX_ROWS])

    return await with_policy(ctx, body)


async def get_portfolio_summary(ctx: Context) -> Result:
    """Summarises every segment the caller owns (a rep) or sees (a lead): plan, estimate, gap and share.

    Use this for "across my segments, how far am I from plan" or "which of my segments are behind". Totals are
    added up here, so never add them yourself.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[segment, plan_ks, estimate_ks, gap_ks,
      year_to_go_ks, share_pct, plan_share_pct, open_month_status], ...], 'totals': {...}}.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        async with async_session() as db:
            ids = await my_segment_ids(db, policy)
            if not ids:
                return error("You have no segments to summarise in this scope.")
            period, contexts = await segment_contexts(db, policy.country_code, policy.mega_segment_id, ids)
            thresholds = (await get_app_settings(db)).thresholds
            entries = await latest_entries(db, policy.country_code, period.year, ids)
        open_month = period.clock_month if period.clock_month <= 12 else None
        rows, plan_total, estimate_total, gap_total, ytg_total = [], 0.0, 0.0, 0.0, 0.0
        for seg, c in sorted(contexts.values(), key=lambda p: p[0].id):
            impact = baseline_impact(c, thresholds)
            entry = entries.get((seg.id, open_month)) if open_month else None
            plan_total += impact.plan_fy
            estimate_total += impact.fy_estimate
            gap_total += impact.gap_to_plan
            ytg_total += impact.ytg_remaining
            rows.append(
                [
                    segment_label(seg), ks(impact.plan_fy), ks(impact.fy_estimate), ks(impact.gap_to_plan),
                    ks(impact.ytg_remaining), pct(impact.volume_share), pct(impact.plan_volume_share),
                    entry.status if entry else ("no entry" if open_month else "year closed"),
                ]
            )
        return table(
            f"Portfolio, {period.year}",
            ["Segment", "Plan (KS)", "Full-year estimate (KS)", "Gap to plan (KS)", "Year-to-go (KS)", "Share (%)",
             "Plan share (%)", f"{month_name(open_month) if open_month else 'Open month'} status"],
            rows,
            link=("Open in Capture", "/capture"),
            totals={
                "plan_ks": ks(plan_total),
                "full_year_estimate_ks": ks(estimate_total),
                "gap_to_plan_ks": ks(gap_total),
                "year_to_go_ks": ks(ytg_total),
                "segments": len(rows),
            },
        )

    return await with_policy(ctx, body)


async def get_month_close_summary(month: int, ctx: Context) -> Result:
    """Recaps a closed month: each entry against the actual, whether it landed in range, and how claims resolved.

    Use this for "what happened when September closed" or "how did my October numbers do".

    Args:
      month: A closed month 1 to 12, or 0 for the most recently closed month.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[segment, rep, entered_ks, low_ks, high_ks,
      actual_ks, in_range, error_pct, claim_resolution], ...], 'totals': {...}}.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        async with async_session() as db:
            period = await current_period(db, policy.country_code)
            closed = month or min(period.clock_month, 13) - 1
            if not 1 <= closed <= 12 or closed >= period.clock_month:
                return error("That month is not closed yet; actuals arrive when it closes.")
            ids = await my_segment_ids(db, policy)
            _, contexts = await segment_contexts(db, policy.country_code, policy.mega_segment_id, ids)
            query = (
                select(DemandEntry, Claim)
                .outerjoin(Claim, Claim.entry_id == DemandEntry.id)
                .where(
                    DemandEntry.country_code == policy.country_code,
                    DemandEntry.year == period.year,
                    DemandEntry.month == closed,
                    DemandEntry.segment_id.in_(ids),
                    DemandEntry.status != "superseded",
                )
            )
            if policy.role == "rep":
                query = query.where(DemandEntry.user_id == policy.user_id)
            pairs = (await db.execute(query)).all()
            names = await user_names(db)
        rows, entered, actual_total, in_range = [], 0.0, 0.0, 0
        for e, c in sorted(pairs, key=lambda p: p[0].segment_id):
            ctx_pair = contexts.get(e.segment_id)
            actual = ctx_pair[1].monthly_actual[closed - 1] if ctx_pair else None
            inside = actual is not None and e.low <= actual <= e.high
            entered += e.value
            actual_total += actual or 0.0
            in_range += int(inside)
            rows.append(
                [
                    segment_label(ctx_pair[0]) if ctx_pair else str(e.segment_id), names.get(e.user_id, e.user_id),
                    ks(e.value), ks(e.low), ks(e.high), ks(actual), "yes" if inside else "no",
                    pct((e.value - actual) / actual) if actual else None, c.resolution if c else "no claim",
                ]
            )
        return table(
            f"{month_name(closed)} {period.year} close",
            ["Segment", "Rep", "Entered (KS)", "Low (KS)", "High (KS)", "Actual (KS)", "Actual in range",
             "Error (%)", "Claim"],
            rows,
            link=("Open in Ledger", ledger_link()),
            totals={
                "entries": len(rows),
                "entered_ks": ks(entered),
                "actual_ks": ks(actual_total),
                "in_range": in_range,
            },
        )

    return await with_policy(ctx, body)


async def explain_term(term: str, ctx: Context) -> Result:
    """Explains a term or a how-to from the app's glossary, with the page to open.

    Use this for "what is range coverage", "what does year-to-go mean" or "how do I justify an IBP entry".

    Args:
      term: The word or question, for example "range coverage" or "justify ibp". An empty string lists all.

    Returns:
      On success: {'status': 'success', 'columns': ['Term', 'Meaning'], 'rows': [...]}.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        found = glossary.lookup(term)
        if not found:
            found = list(glossary.TERMS)
        first = found[0]
        return table(
            "Glossary",
            ["Term", "Meaning"],
            [[t.name, t.definition] for t in found[:MAX_ROWS]],
            link=(f"Open {first.link.strip('/').capitalize() or 'page'}", first.link),
        )

    return await with_policy(ctx, body)


async def get_data_status(ctx: Context) -> Result:
    """Says which months are open, whether the year is closed, where demand comes from and when data last loaded.

    Use this for "which months are open", "when were actuals last uploaded" or "is the IBP snapshot current".

    Returns:
      On success: {'status': 'success', 'figures': {...}, 'columns': [...], 'rows': [[kind, last_loaded], ...]}.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        async with async_session() as db:
            period = await current_period(db, policy.country_code)
            settings = await get_app_settings(db)
            latest = (
                await db.execute(
                    select(UploadBatch.kind, func.max(UploadBatch.committed_at))
                    .where(UploadBatch.status == "committed")
                    .group_by(UploadBatch.kind)
                )
            ).all()
        rows = [[kind, when.date().isoformat() if when else "never"] for kind, when in sorted(latest)]
        if policy.is_demo and not rows:
            rows = [["demo seed", "loaded with the demo; the clock advances months"]]
        return table(
            "Data status",
            ["Data", "Last loaded"],
            rows,
            figures={
                "year": period.year,
                "open_from_month": month_name(period.clock_month) if period.clock_month <= 12 else "year closed",
                "demand_source": "IBP (SAC upload)" if settings.demand_source == "ibp" else "typed in Capture",
                "mode": "demo" if policy.is_demo else "real",
            },
        )

    return await with_policy(ctx, body)


REP_TOOLS = [
    get_my_briefing,
    explain_entry_flags,
    preview_entry_impact,
    get_market_notes,
    get_grower_potential,
    check_justification,
    list_claims,
    lookup_variety,
    get_portfolio_summary,
    get_month_close_summary,
    explain_term,
    get_data_status,
]
