"""Curated definitions and how-tos for explain_term. Plain language, no figures, each with the page to open."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Term:
    name: str
    aliases: tuple[str, ...]
    definition: str
    link: str


TERMS: tuple[Term, ...] = (
    Term(
        "Volume share",
        ("share", "market share", "full-year share"),
        "Syngenta's full-year quantity (actuals to date plus the rep's numbers for open months, else plan) "
        "divided by the micro-segment's market quantity.",
        "/capture",
    ),
    Term(
        "Year-to-go",
        ("ytg", "gap to plan", "year to go"),
        "What is still needed in the open months to reach the full-year plan, after actual sales so far.",
        "/capture",
    ),
    Term(
        "Implied hectares",
        ("hectares", "implied ha", "area"),
        "The planted area the full-year quantity would cover at the segment's seed density, compared with "
        "the hectares the market plants.",
        "/capture",
    ),
    Term(
        "Range",
        ("low-high range", "low and high", "range width"),
        "The rep's own low and high around the number. Supply planning builds to the low end when the range "
        "is wider than the admin's range-width threshold.",
        "/capture",
    ),
    Term(
        "Plausibility flag",
        ("flag", "flags", "warning", "critical"),
        "A fixed check on an entry (share above history, share jump, month outlier, hectares above market, "
        "against the market trend, price carrying the number, grower potential, range too wide, price outside "
        "history). Any flag means the entry needs a justification.",
        "/capture",
    ),
    Term(
        "Lead rule",
        ("rule", "rules", "consensus rule"),
        "A consensus lead's sentence compiled into a fixed check, for example a limit on the month vs last "
        "year. It fires like a built-in flag and can require a named reason.",
        "/rules",
    ),
    Term(
        "Structured claim",
        ("claim", "justification", "reason"),
        "The rep's justification read into checkable slots: driver, direction, size, competitor, variety and "
        "evidence. It is checked against actuals when the month closes.",
        "/ledger",
    ),
    Term(
        "Claim resolution",
        ("confirmed", "contradicted", "inconclusive", "resolution"),
        "When actuals arrive, each claim is marked confirmed, contradicted or inconclusive by comparing what "
        "it said with what happened.",
        "/ledger",
    ),
    Term(
        "Track record",
        ("bias", "hit rate", "claim hit rate", "accuracy"),
        "Per rep: bias (how far numbers ran above or below actuals), claim hit rate (share of resolved claims "
        "confirmed) and range coverage. A weak record sends the rep's entries to the consensus queue.",
        "/reps",
    ),
    Term(
        "Range coverage",
        ("coverage", "in range"),
        "The share of a rep's resolved entries where the actual landed inside the rep's own low-high range.",
        "/reps",
    ),
    Term(
        "Consensus queue",
        ("exceptions", "routine", "queue", "consensus"),
        "Open entries split into exceptions (flags, vague or off-target claims, weak record, IBP numbers "
        "waiting for a reason) and routine entries the lead can approve in bulk.",
        "/consensus",
    ),
    Term(
        "IBP number",
        ("ibp", "sac", "committed number"),
        "Reps commit demand by variety in IBP. Skystream imports the latest snapshot as the rep's entry; the "
        "rep only adds a range and a justification here. Change the number itself in IBP.",
        "/capture",
    ),
    Term(
        "How to justify an IBP entry",
        ("justify ibp", "justify an ibp entry", "needs justification"),
        "Open Capture, pick the segment and month marked 'needs justification', add your low-high range and "
        "a reason that names the driver and evidence, then press Justify. You can also tell the assistant the "
        "range and reason in your own words.",
        "/capture",
    ),
    Term(
        "How to submit a number",
        ("submit", "enter a number", "typed entry"),
        "When the demand source is manual, open Capture, pick the segment and month, type the number and "
        "range, add a justification if flags fire, then Submit. The assistant can submit only the exact "
        "numbers and words you type.",
        "/capture",
    ),
    Term(
        "Reasons to believe",
        ("rtb", "reasons to believe"),
        "A short narrative for the consensus meeting drafted from confirmed claims, market size and "
        "competitor context. It cites evidence and never adds numbers.",
        "/consensus",
    ),
    Term(
        "Supply handoff",
        ("supply", "supply csv", "export"),
        "The approved low, mid and high numbers per segment and month, exported as CSV for supply planning.",
        "/consensus",
    ),
)


def lookup(term: str) -> list[Term]:
    needle = term.strip().lower()
    if not needle:
        return list(TERMS)
    exact = [t for t in TERMS if needle == t.name.lower() or needle in t.aliases]
    if exact:
        return exact
    return [
        t
        for t in TERMS
        if needle in t.name.lower()
        or any(needle in a or a in needle for a in t.aliases)
        or t.name.lower() in needle
    ]
