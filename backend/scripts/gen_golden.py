"""Regenerate tests/fixtures/demand_math_cases.json from the seed data and the Python math.

Run from backend/: `uv run python scripts/gen_golden.py`. The TS suite asserts the same outputs.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.schemas.demand_math import EntryInput  # noqa: E402
from app.services.cube_builder import build_mega, build_segment_context  # noqa: E402
from app.services.demand_math import compute_impact  # noqa: E402
from app.services.flags import evaluate_flags  # noqa: E402
from app.services.seed_service import read_seed, reference_from_seed  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "demand_math_cases.json"


def main() -> None:
    seed_dir = get_settings().seed_dir
    ref = reference_from_seed(seed_dir)
    meta = read_seed(seed_dir, "meta")
    year, clock = meta["currentYear"], meta["clockStartMonth"]
    mega = build_mega(ref, year)

    def ctx(segment_id: int, submitted: dict[int, float] | None = None):
        return build_segment_context(ref, segment_id, year, clock, submitted or {}, mega)

    def plan_month(segment_id: int, month: int) -> float:
        return ctx(segment_id).monthly_plan[month - 1]

    p2482 = plan_month(2482, 9)
    p2448 = plan_month(2448, 10)
    cases = [
        ("2482 at plan", ctx(2482), EntryInput(month=9, value=p2482, low=p2482 * 0.95, high=p2482 * 1.05)),
        (
            "2482 raised 25%",
            ctx(2482),
            EntryInput(month=9, value=p2482 * 1.25, low=p2482 * 1.15, high=p2482 * 1.3),
        ),
        ("2482 unrealistic", ctx(2482), EntryInput(month=9, value=40000, low=38000, high=42000)),
        (
            "2482 wide range, high price",
            ctx(2482),
            EntryInput(month=9, value=p2482, low=p2482 * 0.6, high=p2482 * 1.2, price=900),
        ),
        (
            "2482 volume cut at premium price",
            ctx(2482),
            EntryInput(month=9, value=p2482 * 0.5, low=p2482 * 0.45, high=p2482 * 0.55, price=560),
        ),
        (
            "2448 raised in shrinking area",
            ctx(2448),
            EntryInput(month=10, value=p2448 * 3, low=p2448 * 2.8, high=p2448 * 3.2),
        ),
        (
            "2432 with submitted months",
            ctx(2432, {10: 2600.0, 11: 2500.0}),
            EntryInput(month=12, value=1300, low=1200, high=1400),
        ),
    ]

    payload = []
    for name, context, entry in cases:
        impact = compute_impact(context, entry)
        flags = evaluate_flags(context, entry, impact)
        payload.append(
            {
                "name": name,
                "context": context.model_dump(by_alias=True),
                "entry": entry.model_dump(by_alias=True),
                "expected": impact.model_dump(by_alias=True),
                "expectedFlags": [f.code for f in flags],
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1))
    for case in payload:
        print(f"{case['name']}: {case['expectedFlags']}")


if __name__ == "__main__":
    main()
