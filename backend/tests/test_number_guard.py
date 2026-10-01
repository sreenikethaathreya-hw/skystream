from app.ai.data_agent.number_guard import REDACTED, collect_numbers, find_unverified, redact


def test_quoted_numbers_pass_in_every_format() -> None:
    allowed = collect_numbers({"share_now_pct": 20.2, "year_to_go_ks": 14500, "jump": 14.8, "year": 2026})
    text = "Share is 20.2% in 2026, year-to-go 14,500 KS (14.5k), +14.8 pts."
    assert find_unverified(text, allowed) == []


def test_invented_number_is_found_and_redacted() -> None:
    allowed = collect_numbers({"share_now_pct": 20.2})
    text = "Share is 20.2% and will reach 35.0% next month."
    unverified = find_unverified(text, allowed)
    assert [t.value for t in unverified] == [35.0]
    assert redact(text, unverified) == f"Share is 20.2% and will reach {REDACTED}% next month."


def test_rounding_to_shown_precision_is_accepted() -> None:
    allowed = collect_numbers({"value": 14512.4, "pct": 20.24})
    assert find_unverified("About 14,512 KS at 20.2%", allowed) == []
    assert find_unverified("About 14,513 KS", allowed) != []


def test_small_counts_and_labels_inside_strings() -> None:
    allowed = collect_numbers({"rows": [["2482 · Autumn late Red", 3]]})
    assert find_unverified("Segment 2482 has 3 open months and 2 reps.", allowed) == []
    assert find_unverified("Segment 2499 is missing.", allowed) != []
