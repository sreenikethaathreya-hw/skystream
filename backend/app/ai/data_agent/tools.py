"""Read-only data tools for the chat agent.

Each tool reads the caller's policy from `temp:policy`, refuses segments outside it, opens its own database
session and never writes. Values are rounded the way the UI shows them so the model can quote them verbatim.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException
from google.adk import Context
from sqlalchemy import select

from app.ai.data_agent.policy import ChatPolicy, read_policy
from app.constants.demo import MONTH_NAMES
from app.database import async_session
from app.models import Claim, CompetitorShare, DemandEntry
from app.schemas.demand_math import EntryInput, SegmentContext
from app.services.consensus_service import OPEN_STATUSES, exception_reasons
from app.services.context_service import latest_entries, segment_contexts, segment_label
from app.services.demand_math import compute_impact
from app.services.entry_service import list_entries, scope_filter
from app.services.rep_service import is_weak, list_track_records, track_records
from app.services.rule_service import list_rules
from app.services.settings_service import get_app_settings
from app.services.user_service import user_names

MAX_ROWS = 25
SUM_METRICS = ("plan_ks", "actual_ks", "last_year_ks", "latest_entry_ks")

Result = dict[str, Any]


def _ks(value: float | None) -> int | None:
    return None if value is None else round(value)


def _pct(fraction: float | None) -> float | None:
    return None if fraction is None else round(fraction * 100, 1)


def _error(message: str) -> Result:
    return {"status": "error", "error_message": message}


def _table(source: str, columns: list[str], rows: list[list], link: tuple[str, str] | None = None, **extra) -> Result:
    out: Result = {"status": "success", "source": source, "columns": columns, "rows": rows, **extra}
    if link:
        out["link"] = {"label": link[0], "to": link[1]}
    return out


def _month_name(month: int) -> str:
    return MONTH_NAMES[month - 1]


def _policy(ctx: Context) -> ChatPolicy | None:
    return read_policy(ctx.state)


def _out_of_scope(segment_id: int) -> Result:
    return _error(f"Micro-segment {segment_id} is not in your scope or has no market this year.")


async def _with_policy(ctx: Context, body: Callable[[ChatPolicy], Awaitable[Result]]) -> Result:
    policy = _policy(ctx)
    if policy is None:
        return _error("No access policy was set for this conversation.")
    try:
        return await body(policy)
    except HTTPException as exc:
        return _error(str(exc.detail))


async def list_segments(ctx: Context) -> Result:
    """Lists the micro-segments the user can ask about in the selected country and mega-segment.

    Use this first when the user names a segment by description instead of its number, or asks what
    segments exist.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[segment_id, label, description,
      plan_ks, market_ha], ...], 'year': year}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        async with async_session() as db:
            period, contexts = await segment_contexts(
                db, policy.country_code, policy.mega_segment_id, policy.visible_segment_ids
            )
        rows = [
            [seg.id, segment_label(seg), seg.description, _ks(c.plan_qty_ks), _ks(c.market_hectares)]
            for seg, c in sorted(contexts.values(), key=lambda pair: pair[0].id)
        ]
        return _table(
            f"Segments in scope, {period.year}",
            ["Segment", "Label", "Description", "Plan (KS)", "Market (ha)"],
            rows,
            year=period.year,
        )

    return await _with_policy(ctx, body)


def _month_history_avg(c: SegmentContext, month: int) -> float:
    values = [h.qty_ks[month - 1] for h in c.monthly_history if h.year < c.year]
    return sum(values) / len(values) if values else c.last_year_monthly[month - 1]


async def get_segment_baseline(segment_id: int, month: int, ctx: Context) -> Result:
    """Gets the current picture for one micro-segment: share, plan, year-to-go, hectares and history.

    Use this for questions about market share, plan, year-to-go, last year, the historical average for a
    month, or market potential (hectares) of a single segment.

    Args:
      segment_id: The micro-segment number, for example 2482.
      month: The month the user asks about, 1 to 12. Use 0 when the user names no month; the first open
        month is used.

    Returns:
      On success: {'status': 'success', 'figures': {...}, 'columns': [...], 'rows': [[year, syngenta_ks,
      market_ks, share_pct], ...]}. Shares are percentages, quantities are thousand seeds (KS).
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if not policy.can_see(segment_id):
            return _out_of_scope(segment_id)
        async with async_session() as db:
            period, contexts = await segment_contexts(db, policy.country_code, policy.mega_segment_id, [segment_id])
            thresholds = (await get_app_settings(db)).thresholds
        if segment_id not in contexts:
            return _out_of_scope(segment_id)
        seg, c = contexts[segment_id]
        asked = month if 1 <= month <= 12 else min(c.clock_month, 12)
        open_month = c.clock_month if c.clock_month <= 12 else None
        impact_month = asked if open_month and asked >= open_month else (open_month or 12)
        baseline = c.submitted.get(str(impact_month), c.monthly_plan[impact_month - 1]) if open_month else 0.0
        impact = compute_impact(
            c, EntryInput(month=impact_month, value=baseline, low=baseline, high=baseline), thresholds
        )
        market = {p.year: p.qty_ks for p in c.market_history}
        rows = [
            [p.year, _ks(p.qty_ks), _ks(market[p.year]), _pct(p.qty_ks / market[p.year]) if market[p.year] else None]
            for p in sorted(c.plan_qty_history, key=lambda p: p.year)
            if p.year in market
        ]
        actual = c.monthly_actual[asked - 1]
        figures = {
            "segment": segment_label(seg),
            "year": c.year,
            "open_from_month": _month_name(open_month) if open_month else "year closed",
            "share_now_pct": _pct(impact.volume_share),
            "plan_share_pct": _pct(impact.plan_volume_share),
            "last_year_share_pct": _pct(impact.last_year_volume_share),
            "avg_historical_share_pct": _pct(impact.avg_historical_share),
            "max_historical_share_pct": _pct(impact.max_historical_share),
            "full_year_estimate_ks": _ks(impact.fy_estimate),
            "full_year_plan_ks": _ks(impact.plan_fy),
            "actuals_to_date_ks": _ks(impact.actuals_to_date),
            "year_to_go_ks": _ks(impact.ytg_remaining),
            "months_remaining": impact.months_remaining,
            "month": _month_name(asked),
            "month_plan_ks": _ks(c.monthly_plan[asked - 1]),
            "month_actual_ks": _ks(actual),
            "month_last_year_ks": _ks(c.last_year_monthly[asked - 1]),
            "month_historical_avg_ks": _ks(_month_history_avg(c, asked)),
            "month_submitted_ks": _ks(c.submitted.get(str(asked))),
            "market_ha": _ks(impact.market_ha),
            "implied_ha": _ks(impact.implied_ha),
            "market_qty_ks": _ks(c.market_qty_ks),
        }
        return _table(
            f"Baseline for {segment_label(seg)}, {c.year}",
            ["Year", "Syngenta (KS)", "Market (KS)", "Share (%)"],
            rows,
            link=("Open in Capture", "/capture"),
            figures=figures,
        )

    return await _with_policy(ctx, body)


async def get_monthly_series(segment_id: int, ctx: Context) -> Result:
    """Gets the month-by-month plan, actuals, last year and latest rep entry for one micro-segment.

    Use this for plan-versus-actual questions, which months are closed, or how a segment is tracking over
    the year.

    Args:
      segment_id: The micro-segment number, for example 2482.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[month, plan_ks, actual_ks,
      last_year_ks, latest_entry_ks, entry_status], ...]} for all 12 months. Missing values are null.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if not policy.can_see(segment_id):
            return _out_of_scope(segment_id)
        async with async_session() as db:
            period, contexts = await segment_contexts(db, policy.country_code, policy.mega_segment_id, [segment_id])
            entries = await latest_entries(db, policy.country_code, period.year, [segment_id])
        if segment_id not in contexts:
            return _out_of_scope(segment_id)
        seg, c = contexts[segment_id]
        rows = []
        for m in range(1, 13):
            entry = entries.get((segment_id, m))
            rows.append(
                [
                    _month_name(m),
                    _ks(c.monthly_plan[m - 1]),
                    _ks(c.monthly_actual[m - 1]),
                    _ks(c.last_year_monthly[m - 1]),
                    _ks(entry.value) if entry else None,
                    entry.status if entry else None,
                ]
            )
        return _table(
            f"Monthly series for {segment_label(seg)}, {c.year}",
            ["Month", "Plan (KS)", "Actual (KS)", "Last year (KS)", "Latest entry (KS)", "Entry status"],
            rows,
            link=("Open in Ledger", "/ledger"),
            year=c.year,
            open_from_month=_month_name(c.clock_month) if c.clock_month <= 12 else "year closed",
        )

    return await _with_policy(ctx, body)


async def list_demand_entries(segment_id: int, month: int, status: str, rep_name: str, ctx: Context) -> Result:
    """Lists recorded demand entries with their flags, structured claim and how the claim resolved.

    Use this for questions about what reps entered, which entries were flagged, justifications, or which
    claims were confirmed or contradicted by actuals.

    Args:
      segment_id: A micro-segment number, or 0 for every segment in scope.
      month: A month 1 to 12, or 0 for every month.
      status: One of submitted, approved, discuss, challenged, or an empty string for any status.
      rep_name: Part of a rep's name, for example "Rep A", or an empty string for every rep.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[segment, month, rep, value_ks, low_ks,
      high_ks, status, flags, claim, resolution], ...], 'total_matching': n}. At most 25 rows, newest first.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if segment_id and not policy.can_see(segment_id):
            return _out_of_scope(segment_id)
        async with async_session() as db:
            entries = await list_entries(
                db, policy.country_code, policy.mega_segment_id, segment_id=segment_id or None, limit=500
            )
        visible = set(policy.visible_segment_ids)
        matching = [
            e
            for e in entries
            if e.segment_id in visible
            and (not month or e.month == month)
            and (not status or e.status == status.strip().lower())
            and (not rep_name or rep_name.strip().lower() in e.user_name.lower())
        ]
        rows = [
            [
                e.segment_label,
                _month_name(e.month),
                e.user_name,
                _ks(e.value),
                _ks(e.low),
                _ks(e.high),
                e.status,
                "; ".join(f.message for f in e.flags) or "none",
                (e.claim.summary if e.claim else None) or "none",
                e.claim.resolution if e.claim else "no claim",
            ]
            for e in matching[:MAX_ROWS]
        ]
        return _table(
            "Demand entries",
            ["Segment", "Month", "Rep", "Value (KS)", "Low (KS)", "High (KS)", "Status", "Flags", "Claim", "Resolution"],
            rows,
            link=("Open in Ledger", "/ledger"),
            total_matching=len(matching),
        )

    return await _with_policy(ctx, body)


async def get_competitor_shares(ctx: Context) -> Result:
    """Gets competitor market shares by year for the selected country and mega-segment.

    Use this for questions about competitors, who leads the market, or how competitor shares moved.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[competitor, year, share_pct, trend], ...]}.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        async with async_session() as db:
            shares = (
                await db.execute(
                    select(CompetitorShare)
                    .where(
                        CompetitorShare.country_code == policy.country_code,
                        CompetitorShare.mega_segment_id == policy.mega_segment_id,
                    )
                    .order_by(CompetitorShare.year.desc(), CompetitorShare.share_pct.desc())
                )
            ).scalars()
            rows = [[s.competitor, s.year, round(s.share_pct, 1), s.trend or "none"] for s in shares]
        return _table(
            "Competitor shares",
            ["Competitor", "Year", "Share (%)", "Trend"],
            rows[: MAX_ROWS * 2],
        )

    return await _with_policy(ctx, body)


async def get_rep_track_records(rep_name: str, ctx: Context) -> Result:
    """Gets reps' track records: forecast bias, claim hit rate and range coverage from resolved entries.

    Use this for questions about how accurate a rep has been, whose claims were confirmed or contradicted,
    or which reps have a weak record.

    Args:
      rep_name: Part of a rep's name, for example "Rep B", or an empty string for every rep.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[rep, entries_resolved, bias_pct,
      claim_hit_rate_pct, range_coverage_pct, confirmed, contradicted, weak], ...]}.
      On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        async with async_session() as db:
            records = await list_track_records(db)
        rows = [
            [
                r.user.name,
                r.entries_resolved,
                _pct(r.bias_pct),
                _pct(r.claim_hit_rate),
                _pct(r.range_coverage),
                r.confirmed,
                r.contradicted,
                "yes" if r.weak else "no",
            ]
            for r in records
            if not rep_name or rep_name.strip().lower() in r.user.name.lower()
        ]
        return _table(
            "Rep track records",
            ["Rep", "Entries resolved", "Bias (%)", "Claim hit rate (%)", "Range coverage (%)", "Confirmed",
             "Contradicted", "Weak record"],
            rows,
            link=("Open Track record", "/reps"),
        )

    return await _with_policy(ctx, body)


async def list_lead_rules(ctx: Context) -> Result:
    """Lists the consensus lead's plain-language rules for the selected mega-segment and how often they fired.

    Use this for questions about lead rules, which checks apply to entries, or how rules have performed.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[rule_id, description, active, author,
      fired, confirmed, contradicted, pending], ...]}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        async with async_session() as db:
            rules = await list_rules(db, policy.country_code, policy.mega_segment_id)
        rows = [
            [
                r.id,
                r.description,
                "yes" if r.active else "no",
                r.created_by_name,
                r.stats.fired,
                r.stats.confirmed,
                r.stats.contradicted,
                r.stats.pending,
            ]
            for r in rules
        ]
        return _table(
            "Lead rules",
            ["Rule", "Description", "Active", "Author", "Fired", "Confirmed", "Contradicted", "Pending"],
            rows,
            link=("Open Lead rules", "/rules"),
        )

    return await _with_policy(ctx, body)


async def list_open_exceptions(ctx: Context) -> Result:
    """Lists open entries that need the consensus lead's attention, with the reasons each was raised.

    Use this only when a consensus lead or admin asks what is open, flagged or waiting for review.

    Returns:
      On success: {'status': 'success', 'columns': [...], 'rows': [[segment, month, rep, value_ks, status,
      reasons, triage], ...], 'routine_count': n}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if not policy.is_lead:
            return _error("Only consensus leads and admins can see the open exceptions.")
        async with async_session() as db:
            query = (
                select(DemandEntry, Claim)
                .outerjoin(Claim, Claim.entry_id == DemandEntry.id)
                .where(DemandEntry.source == "live", DemandEntry.status.in_(OPEN_STATUSES))
                .order_by(DemandEntry.segment_id, DemandEntry.month)
            )
            pairs = (await db.execute(scope_filter(query, policy.country_code, policy.mega_segment_id))).all()
            records = await track_records(db)
            names = await user_names(db)
            _, contexts = await segment_contexts(
                db, policy.country_code, policy.mega_segment_id, policy.visible_segment_ids
            )
        rows, routine = [], 0
        for entry, claim in pairs:
            name = names.get(entry.user_id, entry.user_id)
            reasons = exception_reasons(entry, claim, is_weak(records.get(entry.user_id)), name)
            if not reasons:
                routine += 1
                continue
            seg = contexts.get(entry.segment_id)
            rows.append(
                [
                    segment_label(seg[0]) if seg else str(entry.segment_id),
                    _month_name(entry.month),
                    name,
                    _ks(entry.value),
                    entry.status,
                    "; ".join(reasons),
                    (entry.triage or {}).get("choice", "not triaged"),
                ]
            )
        return _table(
            "Open exceptions",
            ["Segment", "Month", "Rep", "Value (KS)", "Status", "Reasons", "Triage"],
            rows[:MAX_ROWS],
            link=("Open Consensus", "/consensus"),
            exception_count=len(rows),
            routine_count=routine,
        )

    return await _with_policy(ctx, body)


async def sum_segment_figures(metric: str, segment_ids: list[int], months: list[int], ctx: Context) -> Result:
    """Adds up a monthly quantity across micro-segments and months, so totals never need mental arithmetic.

    Use this whenever the user asks for a total, sum or average across several segments or months.

    Args:
      metric: One of plan_ks, actual_ks, last_year_ks or latest_entry_ks (the rep's latest entry, else plan).
      segment_ids: Micro-segment numbers to include; an empty list means every segment in scope.
      months: Months 1 to 12 to include; an empty list means all twelve.

    Returns:
      On success: {'status': 'success', 'total_ks': n, 'average_per_segment_ks': n, 'segments_counted': n,
      'columns': [...], 'rows': [[segment, total_ks], ...]}. On failure: {'status': 'error', 'error_message': ...}.
    """

    async def body(policy: ChatPolicy) -> Result:
        if metric not in SUM_METRICS:
            return _error(f"metric must be one of {', '.join(SUM_METRICS)}")
        hidden = [s for s in segment_ids if not policy.can_see(s)]
        if hidden:
            return _out_of_scope(hidden[0])
        bad_months = [m for m in months if not 1 <= m <= 12]
        if bad_months:
            return _error("months must be between 1 and 12")
        ids = segment_ids or policy.visible_segment_ids
        chosen = months or list(range(1, 13))
        async with async_session() as db:
            _, contexts = await segment_contexts(db, policy.country_code, policy.mega_segment_id, ids)

        def value(c: SegmentContext, m: int) -> float:
            if metric == "plan_ks":
                return c.monthly_plan[m - 1]
            if metric == "actual_ks":
                return c.monthly_actual[m - 1] or 0.0
            if metric == "last_year_ks":
                return c.last_year_monthly[m - 1]
            return c.submitted.get(str(m), c.monthly_plan[m - 1])

        per_segment = [
            (seg, sum(value(c, m) for m in chosen)) for seg, c in sorted(contexts.values(), key=lambda p: p[0].id)
        ]
        total = sum(v for _, v in per_segment)
        return _table(
            f"Sum of {metric} over {', '.join(_month_name(m) for m in chosen)}",
            ["Segment", "Total (KS)"],
            [[segment_label(seg), _ks(v)] for seg, v in per_segment],
            total_ks=_ks(total),
            average_per_segment_ks=_ks(total / len(per_segment)) if per_segment else 0,
            segments_counted=len(per_segment),
        )

    return await _with_policy(ctx, body)


TOOLS = [
    list_segments,
    get_segment_baseline,
    get_monthly_series,
    list_demand_entries,
    get_competitor_shares,
    get_rep_track_records,
    list_lead_rules,
    list_open_exceptions,
    sum_segment_figures,
]
