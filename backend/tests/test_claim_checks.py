from app.services.claim_checks import claim_mismatches

SMALL, MODERATE, LARGE = 1.0, 2.0, 3.0


def codes(direction: str, magnitude: float | None, value: float, plan: float = 1000) -> list[str]:
    return [f.code for f in claim_mismatches(direction, magnitude, value, plan)]


def test_small_effect_with_tenfold_number_is_a_size_mismatch() -> None:
    assert codes("up", SMALL, 10_000) == ["claim_size_mismatch"]


def test_moderate_effect_matching_the_number_is_consistent() -> None:
    assert codes("up", MODERATE, 1_120) == []


def test_moderate_effect_on_a_number_at_plan_is_not_flagged() -> None:
    assert codes("up", MODERATE, 1_000) == []


def test_large_effect_with_tiny_change_is_a_size_mismatch() -> None:
    assert codes("up", LARGE, 1_030) == ["claim_size_mismatch"]


def test_direction_contradicting_the_number_is_flagged() -> None:
    assert "claim_direction_mismatch" in codes("down", MODERATE, 1_150)


def test_small_moves_do_not_trigger_direction_mismatch() -> None:
    assert codes("down", SMALL, 1_030) == []


def test_missing_plan_or_magnitude_is_ignored() -> None:
    assert codes("up", None, 1_100) == []
    assert codes("up", SMALL, 5_000, plan=0) == []
