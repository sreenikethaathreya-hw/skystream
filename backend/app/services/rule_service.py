"""Consensus-lead rules: compile a sentence into fixed slots, backtest it, store it, and serve it with the cube."""

import math
import re
from collections import defaultdict
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.decision_provider import decision_policy, get_decision_provider
from app.ai.questions import DRIVER_LABELS, DRIVERS
from app.constants.demo import MONTH_NAMES
from app.models import Claim, DemandEntry, LeadRule, MonthlyActual, MonthlyPlan, PlanYear, Segment
from app.models.base import utcnow
from app.schemas.demand_math import EntryInput, LeadRuleSpec
from app.schemas.rules import (
    RuleCompileIn,
    RuleCreateIn,
    RuleDraftOut,
    RuleOut,
    RulePreviewExample,
    RulePreviewOut,
    RuleSlots,
    RuleStats,
)
from app.services.context_service import segment_label
from app.services.lead_rules import METRICS, metric_value, rule_fires
from app.services.settings_service import get_app_settings
from app.services.user_service import CurrentUser, user_names

MONTH_PATTERN = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)
SEASONS = {
    r"\bspring\b": [3, 4, 5],
    r"\bsummer\b": [6, 7, 8],
    r"\bautumn\b|\bin (?:the )?fall\b": [9, 10, 11],
    r"\bwinter\b": [12, 1, 2],
    r"\bq1\b": [1, 2, 3],
    r"\bq2\b": [4, 5, 6],
    r"\bq3\b": [7, 8, 9],
    r"\bq4\b": [10, 11, 12],
}
THRESHOLD_PATTERN = re.compile(
    r"([-+]?\d+(?:[.,]\d+)?)\s*(%|percent|per cent|percentage points|pts|points|pp)\b|"
    r"([-+]?\d+(?:[.,]\d+)?)\s*%",
    re.IGNORECASE,
)
RULE_DRIVERS = [d for d in DRIVERS if d != "other"]
SEVERITIES = ("warning", "critical")
COMPARATORS = ("above", "below")

def _month_number(token: str) -> int | None:
    if token.lower() == "may" and token != "May":
        return None
    return MONTH_NAMES.index(token[:3].title()) + 1


def parse_months(text: str) -> list[int] | None:
    months: set[int] = set()
    consumed = text
    for match in re.finditer(
        rf"\b({MONTH_PATTERN})\b\s*(?:-|–|to|through|thru|until)\s*\b({MONTH_PATTERN})\b", text, re.IGNORECASE
    ):
        start, end = _month_number(match.group(1)), _month_number(match.group(2))
        if start and end:
            m = start
            while True:
                months.add(m)
                if m == end:
                    break
                m = m % 12 + 1
            consumed = consumed.replace(match.group(0), " ")
    for match in re.finditer(rf"\b({MONTH_PATTERN})\b", consumed, re.IGNORECASE):
        number = _month_number(match.group(1))
        if number:
            months.add(number)
    for pattern, season in SEASONS.items():
        if re.search(pattern, text, re.IGNORECASE):
            months.update(season)
    return sorted(months) or None


def parse_threshold(text: str) -> float | None:
    match = THRESHOLD_PATTERN.search(text)
    if not match:
        return None
    raw = match.group(1) or match.group(3)
    return float(raw.replace(",", "."))


def month_span(months: list[int]) -> str:
    runs: list[list[int]] = []
    for m in sorted(months):
        if runs and m == runs[-1][-1] + 1:
            runs[-1].append(m)
        else:
            runs.append([m])
    if len(runs) > 1 and runs[0][0] == 1 and runs[-1][-1] == 12:
        runs = [runs[-1] + runs[0], *runs[1:-1]]
    return ", ".join(
        MONTH_NAMES[r[0] - 1] if len(r) == 1 else f"{MONTH_NAMES[r[0] - 1]}-{MONTH_NAMES[r[-1] - 1]}" for r in runs
    )


def describe(slots: RuleSlots, labels: dict[int, str], mega_name: str) -> str:
    label, unit, change = METRICS[slots.metric]
    where = (
        f"every micro-segment of {mega_name}"
        if slots.segment_ids is None
        else ", ".join(labels.get(s, str(s)) for s in slots.segment_ids)
    )
    when = f" in {month_span(slots.months)}" if slots.months else ""
    limit = f"{slots.threshold:+g}{unit}" if change else f"{slots.threshold:g}{unit}"
    text = f"For {where}{when}, flag entries where {label} is {slots.comparator} {limit}"
    if slots.required_driver:
        text += f"; the justification must cite {DRIVER_LABELS.get(slots.required_driver, slots.required_driver)}"
    if slots.severity == "critical":
        text += " (hard stop)"
    return text + "."


async def _mega_segments(db: AsyncSession, mega_id: str) -> list[Segment]:
    return list((await db.execute(select(Segment).where(Segment.mega_segment_id == mega_id))).scalars())


async def _source_entry(db: AsyncSession, body: RuleCompileIn, segment_ids: set[int]) -> DemandEntry | None:
    if not body.source_entry_id:
        return None
    entry = await db.get(DemandEntry, body.source_entry_id)
    if entry is None or entry.country_code != body.country_code.upper() or entry.segment_id not in segment_ids:
        raise HTTPException(status_code=404, detail="That entry is not in this country and mega-segment")
    return entry


def validate_slots(slots: RuleSlots, segment_ids: set[int]) -> None:
    problems = []
    if slots.metric not in METRICS:
        problems.append(f"unknown measure {slots.metric}")
    if slots.comparator not in COMPARATORS:
        problems.append("comparator must be above or below")
    if slots.severity not in SEVERITIES:
        problems.append("severity must be warning or critical")
    if not math.isfinite(slots.threshold) or abs(slots.threshold) > 1000:
        problems.append("limit must be a number between -1000 and 1000")
    if slots.months is not None and (not slots.months or any(m < 1 or m > 12 for m in slots.months)):
        problems.append("months must be 1-12")
    if slots.segment_ids is not None and (not slots.segment_ids or not set(slots.segment_ids) <= segment_ids):
        problems.append("micro-segments must belong to this mega-segment")
    if slots.required_driver is not None and slots.required_driver not in RULE_DRIVERS:
        problems.append(f"unknown reason {slots.required_driver}")
    if problems:
        raise HTTPException(status_code=422, detail="; ".join(problems))


async def compile_rule(db: AsyncSession, body: RuleCompileIn) -> RuleDraftOut:
    segments = await _mega_segments(db, body.mega_segment_id)
    if not segments:
        raise HTTPException(status_code=404, detail="Unknown mega-segment")
    by_id = {s.id: s for s in segments}
    source = await _source_entry(db, body, set(by_id))
    mega_name = segments[0].mega_segment_desc
    context = f"MEGA-SEGMENT: {mega_name}"
    if source:
        context += (
            f"\nMISSED ENTRY: {segment_label(by_id[source.segment_id])}, {MONTH_NAMES[source.month - 1]} "
            f"{source.year}, {source.value:,.0f} KS. Justification: {source.justification or 'none'}"
        )
    settings = await get_app_settings(db)
    decision = await get_decision_provider().compile_rule(body.text.strip(), context, decision_policy(settings))
    choices = decision.choices
    base = {
        "provider": decision.provider,
        "confidences": decision.confidences,
        "low_confidence_fields": decision.low_confidence_fields,
        "decisions": choices,
    }

    if choices["metric"] == "unsupported":
        return RuleDraftOut(
            ok=False,
            rejection=(
                "This reads as something the app cannot measure on a demand entry. Rules can check the month vs "
                "last year, plan or its historical average; share level or share change; range width; or price."
            ),
            **base,
        )
    threshold = parse_threshold(body.text)
    if threshold is None:
        return RuleDraftOut(
            ok=False,
            rejection="Say the limit as a number, for example '20%' or '10 pts'. The app never guesses a limit.",
            **base,
        )
    _, _, change = METRICS[choices["metric"]]
    if change and choices["comparator"] == "below":
        threshold = -abs(threshold)
    elif change:
        threshold = abs(threshold)

    micro = choices["applies_to"] == "micro_segment" and source is not None
    slots = RuleSlots(
        metric=choices["metric"],
        comparator=choices["comparator"],
        threshold=threshold,
        months=parse_months(body.text),
        segment_ids=[source.segment_id] if micro and source else None,
        required_driver=None if choices["required_driver"] == "none" else choices["required_driver"],
        severity=choices["severity"],
    )
    validate_slots(slots, set(by_id))
    labels = {s.id: segment_label(s) for s in segments}
    return RuleDraftOut(
        ok=True,
        slots=slots,
        description=describe(slots, labels, mega_name),
        preview=await backtest(db, body.country_code.upper(), segments, slots, source),
        **base,
    )


async def backtest(
    db: AsyncSession, country: str, segments: list[Segment], slots: RuleSlots, source: DemandEntry | None
) -> RulePreviewOut:
    """Re-run the rule over every recorded entry in scope, using stored impacts or the plan/actuals tables."""
    ids = [s.id for s in segments]
    rows = (
        await db.execute(
            select(DemandEntry, Claim)
            .outerjoin(Claim, Claim.entry_id == DemandEntry.id)
            .where(
                DemandEntry.country_code == country,
                DemandEntry.segment_id.in_(ids),
                DemandEntry.status != "superseded",
            )
        )
    ).all()

    async def table(model) -> list:
        return list(
            (
                await db.execute(select(model).where(model.country_code == country, model.segment_id.in_(ids)))
            ).scalars()
        )

    plan_month = {(r.segment_id, r.year, r.month): r.qty_ks for r in await table(MonthlyPlan)}
    actual_month = {(r.segment_id, r.year, r.month): r.qty_ks for r in await table(MonthlyActual)}
    plan_price = {(r.segment_id, r.year): r.net_price for r in await table(PlanYear)}
    names = await user_names(db)
    labels = {s.id: segment_label(s) for s in segments}

    def history_avg(seg: int, year: int, month: int, fallback: float) -> float:
        values = [v for (s, y, m), v in actual_month.items() if s == seg and m == month and y < year]
        return sum(values) / len(values) if values else fallback

    counts: dict[str, int] = defaultdict(int)
    examples: list[RulePreviewExample] = []
    checked = 0
    catches_source: bool | None = None
    for entry, claim in rows:
        if slots.segment_ids is not None and entry.segment_id not in slots.segment_ids:
            continue
        if slots.months is not None and entry.month not in slots.months:
            continue
        stored = entry.impact or {}
        key = (entry.segment_id, entry.year, entry.month)
        expected = stored.get("monthExpected", plan_month.get(key, 0.0))
        last_key = (entry.segment_id, entry.year - 1, entry.month)
        last_year = stored.get("monthLastYear", actual_month.get(last_key, plan_month.get(last_key, 0.0)))
        avg = stored.get("monthHistoryAvg") or history_avg(entry.segment_id, entry.year, entry.month, last_year)
        impact = SimpleNamespace(
            month_expected=expected,
            month_last_year=last_year,
            month_vs_avg_pct=(entry.value - avg) / avg if avg else 0.0,
            share_jump_pts=stored.get("shareJumpPts"),
            volume_share=stored.get("volumeShare"),
        )
        needed = {"volume_share_pct": impact.volume_share, "share_jump_pts": impact.share_jump_pts}
        if slots.metric in needed and needed[slots.metric] is None:
            continue
        value = metric_value(
            slots.metric,
            EntryInput(month=entry.month, value=entry.value, low=entry.low, high=entry.high, price=entry.price),
            impact,  # type: ignore[arg-type]
            plan_price.get((entry.segment_id, entry.year), 0.0),
        )
        if value is None:
            continue
        checked += 1
        fired = rule_fires(slots.comparator, slots.threshold, value)
        if source is not None and entry.id == source.id:
            catches_source = fired
        if not fired:
            continue
        resolution = claim.resolution if claim else None
        counts["fired"] += 1
        counts[resolution or "pending"] += 1
        if len(examples) < 6:
            examples.append(
                RulePreviewExample(
                    entry_id=entry.id,
                    label=f"{labels[entry.segment_id]} · {MONTH_NAMES[entry.month - 1]} {entry.year}",
                    user_name=names.get(entry.user_id, entry.user_id),
                    value=entry.value,
                    metric_value=value,
                    resolution=resolution,
                )
            )
    return RulePreviewOut(
        checked=checked,
        fired=counts["fired"],
        confirmed=counts["confirmed"],
        contradicted=counts["contradicted"],
        inconclusive=counts["inconclusive"],
        pending=counts["pending"],
        catches_source=catches_source,
        examples=examples,
    )


async def create_rule(db: AsyncSession, user: CurrentUser, body: RuleCreateIn) -> RuleOut:
    segments = await _mega_segments(db, body.mega_segment_id)
    if not segments:
        raise HTTPException(status_code=404, detail="Unknown mega-segment")
    by_id = {s.id: s for s in segments}
    source = await _source_entry(db, body, set(by_id))
    validate_slots(body.slots, set(by_id))
    labels = {s.id: segment_label(s) for s in segments}
    row = LeadRule(
        country_code=body.country_code.upper(),
        mega_segment_id=body.mega_segment_id,
        segment_ids=body.slots.segment_ids,
        months=body.slots.months,
        metric=body.slots.metric,
        comparator=body.slots.comparator,
        threshold=body.slots.threshold,
        required_driver=body.slots.required_driver,
        severity=body.slots.severity,
        text=body.text.strip(),
        description=describe(body.slots, labels, segments[0].mega_segment_desc),
        decisions=body.decisions,
        provider=body.provider,
        source_entry_id=source.id if source else None,
        created_by=user.id,
    )
    db.add(row)
    await db.commit()
    return (await list_rules(db, row.country_code, row.mega_segment_id, rule_id=row.id))[0]


async def retire_rule(db: AsyncSession, user: CurrentUser, rule_id: int) -> None:
    row = await db.get(LeadRule, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    if not row.active:
        raise HTTPException(status_code=409, detail="Rule is already retired")
    row.active, row.retired_by, row.retired_at = False, user.id, utcnow()
    await db.commit()


def _slots(row: LeadRule) -> RuleSlots:
    return RuleSlots(
        metric=row.metric,
        comparator=row.comparator,
        threshold=row.threshold,
        months=row.months,
        segment_ids=row.segment_ids,
        required_driver=row.required_driver,
        severity=row.severity,
    )


async def active_specs(db: AsyncSession, country: str, mega_id: str) -> list[LeadRuleSpec]:
    rows = (
        await db.execute(
            select(LeadRule)
            .where(LeadRule.country_code == country, LeadRule.mega_segment_id == mega_id, LeadRule.active.is_(True))
            .order_by(LeadRule.id)
        )
    ).scalars()
    names = await user_names(db)
    return [
        LeadRuleSpec(
            id=r.id,
            segment_ids=r.segment_ids,
            months=r.months,
            metric=r.metric,
            comparator=r.comparator,
            threshold=r.threshold,
            required_driver=r.required_driver,
            severity=r.severity,
            description=r.description,
            author=names.get(r.created_by, r.created_by),
        )
        for r in rows
    ]


async def list_rules(
    db: AsyncSession, country: str, mega_id: str, rule_id: int | None = None
) -> list[RuleOut]:
    query = select(LeadRule).where(LeadRule.country_code == country, LeadRule.mega_segment_id == mega_id)
    if rule_id is not None:
        query = query.where(LeadRule.id == rule_id)
    rules = list((await db.execute(query.order_by(LeadRule.active.desc(), LeadRule.id.desc()))).scalars())
    segments = {s.id: s for s in await _mega_segments(db, mega_id)}
    entries = (
        await db.execute(
            select(DemandEntry, Claim)
            .outerjoin(Claim, Claim.entry_id == DemandEntry.id)
            .where(
                DemandEntry.country_code == country,
                DemandEntry.segment_id.in_(list(segments)),
                DemandEntry.status != "superseded",
            )
        )
    ).all()
    stats: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for entry, claim in entries:
        for flag in entry.flags or []:
            match = re.fullmatch(r"lead_rule_(\d+)", flag.get("code", ""))
            if match:
                bucket = stats[int(match.group(1))]
                bucket["fired"] += 1
                bucket[(claim.resolution if claim else None) or "pending"] += 1
    sources = {
        e.id: e
        for e in (
            await db.execute(
                select(DemandEntry).where(DemandEntry.id.in_([r.source_entry_id for r in rules if r.source_entry_id]))
            )
        ).scalars()
    }
    names = await user_names(db)
    out = []
    for r in rules:
        source = sources.get(r.source_entry_id or "")
        s = stats[r.id]
        out.append(
            RuleOut(
                id=r.id,
                country_code=r.country_code,
                mega_segment_id=r.mega_segment_id,
                slots=_slots(r),
                text=r.text,
                description=r.description,
                provider=r.provider,
                source_entry_id=r.source_entry_id,
                source_label=(
                    f"{segment_label(segments[source.segment_id])} · {MONTH_NAMES[source.month - 1]} {source.year}, "
                    f"{source.value:,.0f} KS by {names.get(source.user_id, source.user_id)}"
                    if source and source.segment_id in segments
                    else None
                ),
                created_by=r.created_by,
                created_by_name=names.get(r.created_by, r.created_by),
                created_at=r.created_at,
                active=r.active,
                retired_by_name=names.get(r.retired_by, r.retired_by) if r.retired_by else None,
                retired_at=r.retired_at,
                stats=RuleStats(
                    fired=s["fired"],
                    confirmed=s["confirmed"],
                    contradicted=s["contradicted"],
                    inconclusive=s["inconclusive"],
                    pending=s["pending"],
                ),
            )
        )
    return out
