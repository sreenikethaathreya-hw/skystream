"""Deterministic stand-in that answers Jev question sets in Jev's response shape.

Used when no Jev key is configured and no recorded fixture matches, so the demo never blocks.
"""

import re

DRIVER_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("competitor_move", ("switching", "switch from", "moving from", "competitor")),
    ("pest_disease", ("parvispinus", "pest", "virus", "thrips", "disease", "plague")),
    ("launch_phaseout", ("launch", "new variety", "phase-out", "phase out", "replacing")),
    ("price", ("price", "discount", "cheaper", "margin")),
    ("weather_water", ("water", "drought", "weather", "heat", "rain", "restriction")),
    ("area_change", ("area", "hectare", "surface", "planting less", "planting more")),
    ("customer_win_loss", ("cooperative", "customer", "order", "booking", "confirmed", "grower")),
]
UP_WORDS = (
    "more",
    "larger",
    "increase",
    "switching to",
    "ahead",
    "gain",
    "win",
    "expand",
    "confirmed",
    "higher",
    "extra",
    "grow",
    "switching from",
)
DOWN_WORDS = (
    "delay",
    "reduc",
    "lower",
    "loss",
    "fewer",
    "drop",
    "cut",
    "restriction",
    "discounting",
    "shrink",
    "less",
    "cancel",
)
EVIDENCE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("public_statistics", ("mapa", "ine ", "esyrce", "statistic", "ministry")),
    ("distributor", ("distributor", "agrupainver", "channel")),
    ("field_trial", ("trial", "demo plot")),
    ("own_customer_contact", ("cooperative", "customer", "grower", "met ", "visited", "called")),
    ("market_notes", ("notes", "report")),
]
PLACES = ("almeria", "almería", "nijar", "níjar", "el ejido", "dalias", "dalías", "murcia", "cooperative")
COMPETITOR_ALIASES = {
    "sur": "Sur Seeds",
    "clause": "Limagrain",
    "vilmorin": "Limagrain",
    "top seeds": "Panora Seeds",
}


def _choice(winner: str, options: list[str], confidence: float) -> dict:
    rest = (1 - confidence) / max(1, len(options) - 1)
    probabilities = {o: (confidence if o == winner else rest) for o in options}
    return {"type": "choice", "choice": winner, "confidence": confidence, "probabilities": probabilities}


def _score(level: int, levels: int, confidence: float = 0.75) -> dict:
    probabilities = {
        str(i): (confidence if i == level else (1 - confidence) / (levels - 1)) for i in range(levels)
    }
    score = sum(i * p for i, p in ((int(k), v) for k, v in probabilities.items()))
    return {"type": "score", "score": score, "confidence": confidence, "probabilities": probabilities}


def _noul(p: float) -> dict:
    return {"type": "noul", "noul": p}


def _first_match(text: str, table: list[tuple[str, tuple[str, ...]]]) -> str | None:
    return next((key for key, words in table if any(w in text for w in words)), None)


def _named(text: str, options: list[str]) -> str | None:
    for option in options:
        if option != "none" and option.lower() in text:
            return option
    for alias, name in COMPETITOR_ALIASES.items():
        if re.search(rf"\b{alias}\b", text) and name in options:
            return name
    return None


def answer_justification(sentence: str, questions: dict, notes: str, flag_direction: str | None) -> dict:
    text = sentence.lower()
    answers: dict[str, dict] = {}

    driver = _first_match(text, DRIVER_KEYWORDS)
    answers["driver"] = _choice(
        driver or "other", list(questions["driver"]["criteria"]), 0.9 if driver else 0.55
    )

    ups = sum(w in text for w in UP_WORDS)
    downs = sum(w in text for w in DOWN_WORDS)
    direction = "up" if ups > downs else "down" if downs > ups else "neutral"
    answers["direction"] = _choice(direction, list(DIRECTIONS_KEYS), 0.88 if ups != downs else 0.5)

    numbers = [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)\s*%", text)]
    if numbers:
        level = 3 if max(numbers) > 20 else 2 if max(numbers) >= 5 else 1
    elif direction == "neutral":
        level = 0
    else:
        level = 3 if any(w in text for w in ("major", "significant", "huge")) else 2
    answers["magnitude"] = _score(level, 4)

    competitor = _named(text, list(questions["competitor"]["criteria"]))
    answers["competitor"] = _choice(
        competitor or "none", list(questions["competitor"]["criteria"]), 0.92 if competitor else 0.8
    )
    variety = _named(text, list(questions["variety"]["criteria"]))
    answers["variety"] = _choice(
        variety or "none", list(questions["variety"]["criteria"]), 0.93 if variety else 0.8
    )

    source = _first_match(text, EVIDENCE_KEYWORDS)
    answers["evidence_source"] = _choice(
        source or "none", list(questions["evidence_source"]["criteria"]), 0.85 if source else 0.6
    )

    specifics = sum([bool(numbers), bool(competitor), bool(variety), any(p in text for p in PLACES)])
    answers["specificity"] = _score(min(3, specifics), 4)
    answers["verifiable"] = _noul(0.82 if specifics >= 1 or source == "own_customer_contact" else 0.3)

    shared = {
        w
        for w in ("parvispinus", "water", "price", "sur seeds", "limagrain")
        if w in text and w in notes.lower()
    }
    answers["consistent_with_market_notes"] = _noul(0.78 if shared else 0.55)

    if "addresses_flags" in questions:
        aligned = flag_direction is None or flag_direction == direction
        answers["addresses_flags"] = _noul(0.8 if aligned and specifics >= 2 else 0.45 if aligned else 0.2)
    return answers


def answer_verification(numeric_support: bool) -> dict:
    return {"supported": _noul(0.84 if numeric_support else 0.18)}


def answer_triage(has_critical: bool, has_warning: bool, weak_record: bool, specificity: float) -> dict:
    if has_critical:
        winner, conf = "challenge", 0.86
    elif has_warning and (weak_record or specificity < 1.5):
        winner, conf = "discuss", 0.74
    elif has_warning or weak_record:
        winner, conf = "discuss", 0.62
    else:
        winner, conf = "approve", 0.9
    return {"triage": _choice(winner, ["approve", "discuss", "challenge"], conf)}


DIRECTIONS_KEYS = ("up", "down", "neutral")

CHAT_INTENT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "forecast_request",
        ("forecast", "predict", "projection", "will demand", "what should i enter", "suggest a number",
         "estimate for", "how much will", "next year's demand"),
    ),
    ("consensus", ("exception", "open entries", "waiting for review", "consensus", "to review", "queue")),
    ("rules", ("rule",)),
    ("competitors", ("competitor", "rijk", "enza", "sur seeds", "limagrain", "panora", "who leads")),
    ("claims_track_record", ("track record", "accurate", "accuracy", "hit rate", "bias", "contradicted",
                             "confirmed", "claim")),
    ("entries_flags", ("entry", "entries", "entered", "flag", "justification", "submitted")),
    ("plan_vs_actual", ("actual", "vs plan", "versus plan", "tracking", "monthly", "month by month")),
    ("baseline_share", ("share", "plan", "year-to-go", "year to go", "ytg", "hectare", "baseline",
                        "last year", "history", "average", "market")),
]
CHAT_INTENT_KEYS = (
    "baseline_share", "plan_vs_actual", "entries_flags", "claims_track_record", "competitors", "rules",
    "consensus", "forecast_request", "other",
)


def answer_chat_intent(text: str) -> dict:
    intent = _first_match(text.lower(), CHAT_INTENT_KEYWORDS)
    return {"intent": _choice(intent or "other", list(CHAT_INTENT_KEYS), 0.8 if intent else 0.5)}

RULE_METRIC_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("range_width_pct", ("range", "spread", "low-high", "low and high")),
    ("price_vs_plan_pct", ("price", "discount")),
    ("share_jump_pts", ("share jump", "share change", "share points", "share gain", "pts of share", "points of share")),
    ("volume_share_pct", ("share",)),
    ("month_vs_average_pct", ("average", "historical", "history")),
    ("month_vs_last_year_pct", ("last year", "prior year", "previous year", "year on year", "yoy")),
    ("month_vs_plan_pct", ("plan", "budget", "target")),
]
RULE_DOWN_WORDS = ("cut", "drop", "below", "less than", "decrease", "under", "lower", "fall", "reduc")
RULE_MEGA_WORDS = ("all ", "every", "whole", "any segment", "any micro", "across", "mega")
RULE_STRICT_WORDS = ("never", "block", "reject", "hard stop", "do not accept", "don't accept", "not accept", "refuse")
RULE_METRIC_KEYS = (
    "month_vs_last_year_pct",
    "month_vs_plan_pct",
    "month_vs_average_pct",
    "share_jump_pts",
    "volume_share_pct",
    "range_width_pct",
    "price_vs_plan_pct",
    "unsupported",
)


def answer_rule(text: str, drivers: list[str]) -> dict:
    lowered = text.lower()
    metric = _first_match(lowered, RULE_METRIC_KEYWORDS)
    if metric is None and re.search(r"\d", lowered):
        metric = "month_vs_plan_pct"
        metric_conf = 0.55
    else:
        metric_conf = 0.88 if metric else 0.7
    comparator = "below" if any(w in lowered for w in RULE_DOWN_WORDS) else "above"
    applies = "mega_segment" if any(w in lowered for w in RULE_MEGA_WORDS) else "micro_segment"
    clause = re.split(r"\bunless\b|\bwithout\b|\bexcept\b|\bmust (?:name|cite|give|explain)\b", lowered, maxsplit=1)
    driver = _first_match(clause[1], DRIVER_KEYWORDS) if len(clause) > 1 else None
    strict = any(w in lowered for w in RULE_STRICT_WORDS)
    return {
        "metric": _choice(metric or "unsupported", list(RULE_METRIC_KEYS), metric_conf),
        "comparator": _choice(comparator, ["above", "below"], 0.85),
        "applies_to": _choice(applies, ["micro_segment", "mega_segment"], 0.8),
        "required_driver": _choice(driver or "none", drivers, 0.85 if driver else 0.8),
        "severity": _choice("critical" if strict else "warning", ["warning", "critical"], 0.8),
    }
