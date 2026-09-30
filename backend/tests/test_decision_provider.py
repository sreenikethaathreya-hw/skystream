from pathlib import Path

import pytest

from app.ai.decision_provider import DecisionProvider, JustificationInput
from app.ai.fixture_store import FixtureStore
from app.ai.questions import justification_questions
from app.config import Settings
from app.schemas.demand_math import Flag

SENTENCE = (
    "Two Almeria cooperatives are switching from Sur Seeds to Leontes because of T. parvispinus tolerance."
)


def _input(flags: list[Flag] | None = None) -> JustificationInput:
    return JustificationInput(
        sentence=SENTENCE,
        segment_label="2482",
        entry_summary="Sep demand 15,500 KS",
        flags=flags or [],
        market_notes="Sur seeds and Clause are leading. T. parvispinus impact.",
        competitors=["Limagrain", "Sur Seeds", "Rijk Zwaan"],
        varieties=["Leontes", "Hokkaido"],
        flag_direction="up",
    )


def _settings(tmp_path: Path, **overrides) -> Settings:
    return Settings(**{"fixtures_dir": tmp_path, "jev_api_key": None, "gemini_enabled": False, **overrides})


async def test_offline_decider_structures_the_demo_sentence(tmp_path: Path) -> None:
    provider = DecisionProvider(_settings(tmp_path, ai_mode="replay"))
    claim = await provider.structure_justification(_input())
    assert claim.provider == "offline decider"
    assert (claim.driver, claim.direction) == ("competitor_move", "up")
    assert (claim.competitor, claim.variety) == ("Sur Seeds", "Leontes")
    assert claim.evidence_source == "own_customer_contact"
    assert claim.addresses_flags is None


async def test_addresses_flags_question_only_asked_when_flags_fire(tmp_path: Path) -> None:
    provider = DecisionProvider(_settings(tmp_path, ai_mode="replay"))
    claim = await provider.structure_justification(_input([Flag(code="x", severity="warning", message="m")]))
    assert claim.addresses_flags is not None
    assert "addresses_flags" in claim.decisions


async def test_recorded_fixture_is_replayed(tmp_path: Path) -> None:
    settings = _settings(tmp_path, ai_mode="replay")
    provider = DecisionProvider(settings)
    data = _input()
    questions = justification_questions(data.competitors, data.varieties, False)
    state = (
        f"JUSTIFICATION: {data.sentence}\nSEGMENT: {data.segment_label}\n"
        f"ENTRY: {data.entry_summary}\nFLAGS:\n- none\nMARKET NOTES: {data.market_notes}"
    )
    recorded = {
        "model": "jev-1.13.0",
        "answers": {
            "driver": {"type": "choice", "choice": "pest_disease", "confidence": 0.93, "probabilities": {}},
            "direction": {"type": "choice", "choice": "up", "confidence": 0.97, "probabilities": {}},
            "competitor": {"type": "choice", "choice": "Sur Seeds", "confidence": 0.99, "probabilities": {}},
            "variety": {"type": "choice", "choice": "Leontes", "confidence": 0.98, "probabilities": {}},
            "magnitude": {"type": "score", "score": 2.2, "confidence": 0.7, "probabilities": {}},
        },
    }
    FixtureStore(tmp_path).put("justification", FixtureStore.key("justification", state, questions), recorded)
    claim = await provider.structure_justification(data)
    assert claim.provider == "jev (recorded)"
    assert claim.model == "jev-1.13.0"
    assert claim.driver == "pest_disease"


async def test_live_jev_failure_falls_back_to_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.ai import jev_client

    async def boom(self, state, questions):
        raise jev_client.JevError("timeout")

    monkeypatch.setattr(jev_client.JevClient, "ask", boom)
    provider = DecisionProvider(_settings(tmp_path, ai_mode="live"))
    claim = await provider.structure_justification(_input())
    assert claim.provider == "offline decider"


async def test_live_jev_answers_are_used_and_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.ai import jev_client

    async def fake_ask(self, state, questions):
        answers = {
            key: {"type": "choice", "choice": list(q["criteria"])[0], "confidence": 0.95, "probabilities": {}}
            if q["type"] == "choice"
            else {"type": "score", "score": 1.0, "confidence": 0.8, "probabilities": {}}
            if q["type"] == "score"
            else {"type": "noul", "noul": 0.9}
            for key, q in questions.items()
        }
        return {"model": "jev-1.13.0", "answers": answers}

    monkeypatch.setattr(jev_client.JevClient, "ask", fake_ask)
    provider = DecisionProvider(_settings(tmp_path, ai_mode="record"))
    claim = await provider.structure_justification(_input())
    assert claim.provider == "jev"
    assert claim.driver == "pest_disease"
    assert list(tmp_path.glob("justification/*.json"))


async def test_low_confidence_fields_are_reported_without_gemini(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.ai import jev_client

    async def unsure(self, state, questions):
        return {
            "model": "jev-1.13.0",
            "answers": {
                "driver": {"type": "choice", "choice": "other", "confidence": 0.4, "probabilities": {}},
                "direction": {"type": "choice", "choice": "up", "confidence": 0.9, "probabilities": {}},
                "competitor": {"type": "choice", "choice": "none", "confidence": 0.9, "probabilities": {}},
                "variety": {"type": "choice", "choice": "none", "confidence": 0.9, "probabilities": {}},
            },
        }

    monkeypatch.setattr(jev_client.JevClient, "ask", unsure)
    provider = DecisionProvider(_settings(tmp_path, ai_mode="live"))
    claim = await provider.structure_justification(_input())
    assert claim.low_confidence_fields == ["driver"]


async def test_gemini_fallback_overrides_low_confidence_choice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.ai import gemini_client, jev_client

    async def unsure(self, state, questions):
        return {
            "model": "jev-1.13.0",
            "answers": {
                "driver": {"type": "choice", "choice": "other", "confidence": 0.3, "probabilities": {}}
            },
        }

    async def extract(self, prompt, schema, timeout_seconds):
        return {"driver": "competitor_move"}

    async def write(self, prompt, max_words=120):
        return "Two cooperatives move from Sur Seeds to Leontes."

    monkeypatch.setattr(jev_client.JevClient, "ask", unsure)
    monkeypatch.setattr(gemini_client.GeminiClient, "extract", extract)
    monkeypatch.setattr(gemini_client.GeminiClient, "write", write)
    provider = DecisionProvider(_settings(tmp_path, ai_mode="live", gemini_enabled=True, gcp_project="demo"))
    claim = await provider.structure_justification(_input())
    assert claim.driver == "competitor_move"
    assert "gemini fallback" in claim.provider
    assert "driven by a competitor move" in claim.summary
    polished = await provider.polish_summary(SENTENCE, claim.summary)
    assert polished == "Two cooperatives move from Sur Seeds to Leontes."
