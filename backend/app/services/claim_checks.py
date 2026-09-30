"""Consistency between what the justification says and what the number does."""

from app.schemas.demand_math import Flag

# Upper and lower bounds of each magnitude level (share of plan), matching MAGNITUDE_LEVELS in app/ai/questions.py.
LEVEL_BOUNDS = [(0.0, 0.02), (0.02, 0.05), (0.05, 0.20), (0.20, float("inf"))]
LEVEL_NAMES = ["negligible", "small (under 5%)", "moderate (5-20%)", "large (over 20%)"]
MISMATCH_FACTOR = 2.5
MIN_DIRECTION_CHANGE = 0.05


def claim_mismatches(direction: str, magnitude: float | None, value: float, plan_month: float) -> list[Flag]:
    if plan_month <= 0:
        return []
    change = (value - plan_month) / plan_month
    size = abs(change)
    flags: list[Flag] = []

    number_direction = "up" if change > 0 else "down"
    if direction in ("up", "down") and size >= MIN_DIRECTION_CHANGE and direction != number_direction:
        flags.append(
            Flag(
                code="claim_direction_mismatch",
                severity="warning",
                message=(
                    f"The justification argues demand {direction}, but the number is {change:+.0%} vs the plan "
                    "for this month."
                ),
            )
        )

    if magnitude is not None:
        level = max(0, min(3, round(magnitude)))
        low, high = LEVEL_BOUNDS[level]
        # Vague sentences default to a moderate size, so understatement is only flagged for an explicit "large".
        understated = level == len(LEVEL_BOUNDS) - 1 and size < low / MISMATCH_FACTOR
        if size > high * MISMATCH_FACTOR or understated:
            flags.append(
                Flag(
                    code="claim_size_mismatch",
                    severity="warning",
                    message=(
                        f"The justification describes a {LEVEL_NAMES[level]} effect, but the number is "
                        f"{change:+.0%} vs the plan for this month."
                    ),
                )
            )
    return flags
