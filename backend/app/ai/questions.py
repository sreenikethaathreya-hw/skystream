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
