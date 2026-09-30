"""Synthetic layers the spreadsheets do not contain: anonymization, monthly split, rep history.

Every seasonal curve here is an assumption to confirm with the SMEs, not company data.
"""

import numpy as np

SEED = 20260929
CURRENT_YEAR = 2026
CLOCK_START_MONTH = 9
BASE_WEIGHT = 0.015

PROFILE_PEAKS: dict[str, dict[int, float]] = {
    "spring": {9: 0.12, 10: 0.30, 11: 0.30, 12: 0.12},
    "autumn_early": {4: 0.12, 5: 0.30, 6: 0.28, 7: 0.10},
    "autumn_medium": {5: 0.10, 6: 0.30, 7: 0.30, 8: 0.12},
    "autumn_late": {7: 0.20, 8: 0.30, 9: 0.30, 10: 0.08},
    "autumn": {6: 0.20, 7: 0.30, 8: 0.25},
}

ACTUAL_DRIFT_2026 = {2482: 0.08, 2448: -0.12, 2481: -0.06}

OWNERS = {
    "rep-a": [2481, 2482, 2483, 2484],
    "rep-b": [2432, 2433, 2446, 2448, 2449],
}

REP_BEHAVIOUR = {
    "rep-a": {"bias": 0.01, "noise": 0.04, "half_width": 0.08},
    "rep-b": {"bias": 0.13, "noise": 0.07, "half_width": 0.04},
}

TEMPLATES = {
    "up": [
        (
            "Cooperative in Nijar confirmed a larger {variety} order for this transplant window.",
            "customer_win_loss",
            "own_customer_contact",
        ),
        (
            "Growers are switching from {competitor} after T. parvispinus losses last season.",
            "competitor_move",
            "distributor",
        ),
        (
            "Distributor reports bookings for {variety} running ahead of last year.",
            "customer_win_loss",
            "distributor",
        ),
    ],
    "down": [
        (
            "T. parvispinus pressure is pushing growers to delay transplanting.",
            "pest_disease",
            "own_customer_contact",
        ),
        (
            "{competitor} is discounting aggressively in El Ejido this month.",
            "price",
            "distributor",
        ),
        (
            "Water restrictions in Campo de Dalias are reducing planted area.",
            "weather_water",
            "public_statistics",
        ),
    ],
}
VARIETIES = ["Hokkaido", "Saitama", "Leontes", "Bokken", "Kaamos"]
COMPETITORS = ["Sur Seeds", "Limagrain"]


def profile_for(description: str) -> str:
    upper = description.upper()
    if "SPRING" in upper:
        return "spring"
    for stage in ("EARLY", "MEDIUM", "LATE"):
        if f"AUTUMN-{stage}" in upper:
            return f"autumn_{stage.lower()}"
    return "autumn"


def curve(profile: str) -> list[float]:
    raw = [BASE_WEIGHT + PROFILE_PEAKS[profile].get(m, 0.0) for m in range(1, 13)]
    total = sum(raw)
    return [w / total for w in raw]


class Anonymizer:
    """Scales Syngenta figures by one hidden factor plus per-row noise."""

    def __init__(self, rng: np.random.Generator) -> None:
        self._rng = rng
        self._factor = float(rng.uniform(0.88, 1.12))

    def scale(self, qty: float, value: float) -> tuple[float, float]:
        noise = 1 + float(self._rng.normal(0, 0.03))
        price_noise = 1 + float(self._rng.normal(0, 0.01))
        new_qty = round(qty * self._factor * noise)
        return float(new_qty), round(value * self._factor * noise * price_noise, 2)


def split_months(total: float, weights: list[float]) -> list[float]:
    parts = [round(total * w) for w in weights]
    parts[int(np.argmax(weights))] += round(total) - sum(parts)
    return [float(p) for p in parts]


def noisy_months(
    rng: np.random.Generator, plan: list[float], drift: float, sd: float
) -> list[float]:
    return [float(max(0, round(p * (1 + drift + float(rng.normal(0, sd)))))) for p in plan]


def history_entries(
    rng: np.random.Generator,
    monthly_plan: dict[int, list[float]],
    monthly_actual: dict[int, list[float]],
) -> list[dict]:
    entries: list[dict] = []
    for rep, segments in OWNERS.items():
        behaviour = REP_BEHAVIOUR[rep]
        for segment_id in segments:
            for month in range(1, CLOCK_START_MONTH):
                plan = monthly_plan[segment_id][month - 1]
                actual = monthly_actual[segment_id][month - 1]
                if plan < 50:
                    continue
                error = behaviour["bias"] + float(rng.normal(0, behaviour["noise"]))
                value = round(actual * (1 + error))
                half = behaviour["half_width"]
                claim_dir = "up" if value >= plan else "down"
                text, driver, source = TEMPLATES[claim_dir][int(rng.integers(0, 3))]
                variety = VARIETIES[int(rng.integers(0, len(VARIETIES)))]
                competitor = COMPETITORS[int(rng.integers(0, len(COMPETITORS)))]
                actual_dir = "up" if actual >= plan else "down"
                entries.append(
                    {
                        "userId": rep,
                        "segmentId": segment_id,
                        "year": CURRENT_YEAR,
                        "month": month,
                        "value": float(value),
                        "low": float(round(value * (1 - half))),
                        "high": float(round(value * (1 + half))),
                        "justification": text.format(variety=variety, competitor=competitor),
                        "claim": {
                            "driver": driver,
                            "direction": claim_dir,
                            "evidenceSource": source,
                            "variety": variety if "{variety}" in text else None,
                            "competitor": competitor if "{competitor}" in text else None,
                        },
                        "resolution": "confirmed" if claim_dir == actual_dir else "contradicted",
                    }
                )
    return entries
