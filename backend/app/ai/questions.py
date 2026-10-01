"""Jev question sets. The criteria text is the prompt surface; edit it deliberately."""

DRIVERS = {
    "pest_disease": "A pest or disease (e.g. T. parvispinus, viruses, thrips) changes planting or demand",
    "competitor_move": "A competitor gains or loses growers, launches, or changes its offer",
    "launch_phaseout": "A Syngenta variety launch, replacement or phase-out",
    "price": "Price, discounts or margin changes drive the number",
    "area_change": "Planted area in the segment grows or shrinks for structural reasons",
    "weather_water": "Weather, water availability or restrictions",
    "customer_win_loss": "A specific customer, cooperative or distributor order is won, lost or confirmed",
    "other": "None of the above",
}

DRIVER_LABELS = {
    "pest_disease": "pest or disease pressure",
    "competitor_move": "a competitor move",
    "launch_phaseout": "a launch or phase-out",
    "price": "price",
    "area_change": "a change in planted area",
    "weather_water": "weather or water",
    "customer_win_loss": "a customer win or loss",
    "other": "other factors",
}

EVIDENCE_LABELS = {
    "own_customer_contact": "direct customer contact",
    "distributor": "distributor",
    "field_trial": "field trial",
    "public_statistics": "public statistics",
    "market_notes": "market notes",
    "none": "none stated",
}

DIRECTIONS = {
    "up": "The rep expects demand to be higher than planned",
    "down": "The rep expects demand to be lower than planned",
    "neutral": "No change versus plan is argued",
}

MAGNITUDE_LEVELS = ["Negligible", "Small (under 5%)", "Moderate (5-20%)", "Large (over 20%)"]

EVIDENCE_SOURCES = {
    "own_customer_contact": "The rep spoke directly with a grower, cooperative or customer",
    "distributor": "Information came from a distributor or channel partner",
    "field_trial": "Field trial or demo plot results",
    "public_statistics": "Public agricultural statistics (MAPA, INE, ESYRCE)",
    "market_notes": "Existing market intelligence notes",
    "none": "No evidence source is stated",
}

SPECIFICITY_LEVELS = ["Vague", "Some detail", "Specific", "Specific and quantified"]

TRIAGE_OPTIONS = {
    "approve": "The number is plausible and well justified; approve without discussion",
    "discuss": "Plausible but needs a short discussion in the consensus meeting",
    "challenge": "Implausible or poorly justified; challenge the rep before approving",
}


SENTENCE_ONLY = "Judge only the JUSTIFICATION line; ignore the FLAGS and MARKET NOTES sections. "


def justification_questions(competitors: list[str], varieties: list[str], has_flags: bool) -> dict[str, dict]:
    questions: dict[str, dict] = {
        "driver": {
            "type": "choice",
            "instructions": SENTENCE_ONLY + "What is the main driver the rep gives for this demand number?",
            "criteria": DRIVERS,
        },
        "direction": {
            "type": "choice",
            "instructions": SENTENCE_ONLY + "Which direction does the rep argue versus plan?",
            "criteria": DIRECTIONS,
        },
        "magnitude": {
            "type": "score",
            "instructions": SENTENCE_ONLY + "How large an effect on demand does the rep describe?",
            "criteria": MAGNITUDE_LEVELS,
        },
        "competitor": {
            "type": "choice",
            "instructions": SENTENCE_ONLY
            + "Which competitor, if any, does the justification name or clearly imply?",
            "criteria": {**{c: f"Mentions {c}" for c in competitors}, "none": "No competitor named"},
        },
        "variety": {
            "type": "choice",
            "instructions": SENTENCE_ONLY + "Which Syngenta variety, if any, does the justification name?",
            "criteria": {**{v: f"Mentions {v}" for v in varieties}, "none": "No variety named"},
        },
        "evidence_source": {
            "type": "choice",
            "instructions": SENTENCE_ONLY + "Where does the rep's evidence come from?",
            "criteria": EVIDENCE_SOURCES,
        },
        "verifiable": {
            "type": "noul",
            "instructions": "Does the sentence make a claim that next month's sales, competitor shares or public statistics could confirm or refute?",
            "criteria": {"true": "Checkable against later data", "false": "Opinion that cannot be checked"},
        },
        "consistent_with_market_notes": {
            "type": "noul",
            "instructions": "Is the justification consistent with the MARKET NOTES section of the state?",
            "criteria": {"true": "Consistent with the notes", "false": "Contradicts or ignores the notes"},
        },
        "specificity": {
            "type": "score",
            "instructions": SENTENCE_ONLY + "How specific is the justification (names, places, quantities)?",
            "criteria": SPECIFICITY_LEVELS,
        },
    }
    if has_flags:
        questions["addresses_flags"] = {
            "type": "noul",
            "instructions": "Does the justification actually explain the FLAGS listed in the state?",
            "criteria": {
                "true": "Explains why the flagged number is still right",
                "false": "Does not address the flags",
            },
        }
    return questions


RULE_METRICS = {
    "month_vs_last_year_pct": "Compares the entered month with the same month last year",
    "month_vs_plan_pct": "Compares the entered month with the plan for that month",
    "month_vs_average_pct": "Compares the entered month with its historical average across years",
    "share_jump_pts": "How many share points one entry adds or removes",
    "volume_share_pct": "The full-year market share level",
    "range_width_pct": "How wide the rep's low-high range is",
    "price_vs_plan_pct": "The net price entered compared with the plan price",
    "unsupported": "None of these; the rule is about something else (people, timing, documents, process)",
}

RULE_COMPARATORS = {
    "above": "Flag when the measure is too high (increases, more than, above, over)",
    "below": "Flag when the measure is too low (cuts, drops, less than, below, under)",
}

RULE_SCOPES = {
    "micro_segment": "Only the micro-segment the lead is reviewing",
    "mega_segment": "Every micro-segment in the mega-segment (all, every, any, whole crop)",
}

RULE_SEVERITIES = {
    "warning": "Ask for a justification and discuss it",
    "critical": "Treat as a hard stop to challenge before approving (never, reject, block, do not accept)",
}

RULE_ONLY = "Judge only the RULE line; the other lines are context. "


def rule_questions() -> dict[str, dict]:
    return {
        "metric": {
            "type": "choice",
            "instructions": RULE_ONLY + "Which measure of a demand entry does the rule check?",
            "criteria": RULE_METRICS,
        },
        "comparator": {
            "type": "choice",
            "instructions": RULE_ONLY + "Does the rule catch numbers that are too high or too low?",
            "criteria": RULE_COMPARATORS,
        },
        "applies_to": {
            "type": "choice",
            "instructions": RULE_ONLY + "Which micro-segments should the rule cover?",
            "criteria": RULE_SCOPES,
        },
        "required_driver": {
            "type": "choice",
            "instructions": RULE_ONLY
            + "Which reason, if any, must the rep's justification give for the entry to be acceptable?",
            "criteria": {**{k: v for k, v in DRIVERS.items() if k != "other"}, "none": "No particular reason is required"},
        },
        "severity": {
            "type": "choice",
            "instructions": RULE_ONLY + "How strict is the lead being?",
            "criteria": RULE_SEVERITIES,
        },
    }


def verification_question() -> dict[str, dict]:
    return {
        "supported": {
            "type": "noul",
            "instructions": "Given the EVIDENCE, did the CLAIM turn out to be true?",
            "criteria": {
                "true": "The evidence supports the claim",
                "false": "The evidence contradicts the claim",
            },
        }
    }


def triage_question() -> dict[str, dict]:
    return {
        "triage": {
            "type": "choice",
            "instructions": "What should the consensus lead do with this demand entry?",
            "criteria": TRIAGE_OPTIONS,
        }
    }
