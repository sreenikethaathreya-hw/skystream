"""Single entry point for model calls: Jev for typed decisions, Gemini for prose and fallback."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from app.ai import offline_decider
from app.ai.fixture_store import FixtureStore
from app.ai.gemini_client import GeminiClient, GeminiError
from app.ai.jev_client import JevClient, JevError
from app.ai.questions import (
    DRIVER_LABELS,
    EVIDENCE_LABELS,
    MAGNITUDE_LEVELS,
    SPECIFICITY_LEVELS,
    justification_questions,
    triage_question,
    verification_question,
)
from app.config import Settings, get_settings
from app.schemas.claims import DecisionAnswer, StructuredClaim, TriageDecision
from app.schemas.demand_math import Flag

logger = logging.getLogger(__name__)

GATED_CHOICES = ("driver", "direction", "competitor", "variety")
GATED_SCORES = {"magnitude": MAGNITUDE_LEVELS, "specificity": SPECIFICITY_LEVELS}


@dataclass
class JustificationInput:
    sentence: str
    segment_label: str
    entry_summary: str
    flags: list[Flag]
    market_notes: str
    competitors: list[str]
    varieties: list[str]
    flag_direction: str | None


@dataclass(frozen=True)
class DecisionPolicy:
    """Per-request rules: whether text may go to Jev's hosted API, and when to fall back to Gemini."""

    allow_jev: bool = True
    choice_threshold: float = 0.8
    score_threshold: float = 0.4


def decision_policy(app_settings) -> DecisionPolicy:
    return DecisionPolicy(
        allow_jev=app_settings.external_ai_allowed,
        choice_threshold=app_settings.jev_confidence_threshold,
        score_threshold=app_settings.jev_score_confidence_threshold,
    )


def default_policy() -> DecisionPolicy:
    settings = get_settings()
    return DecisionPolicy(
        allow_jev=settings.external_ai_allowed or settings.is_demo,
        choice_threshold=settings.jev_confidence_threshold,
        score_threshold=settings.jev_score_confidence_threshold,
    )


@dataclass
class _Decision:
    answers: dict
    provider: str
    model: str | None


def _level(score: float | None, labels: list[str]) -> str | None:
    if score is None:
        return None
    return labels[max(0, min(len(labels) - 1, round(score)))]


class DecisionProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jev = JevClient(settings)
        self._gemini = GeminiClient(settings)
        self._store = FixtureStore(settings.fixtures_dir)
        self._cache: dict[str, _Decision] = {}
        self._claims: dict[str, StructuredClaim] = {}

    @property
    def mode(self) -> str:
        if self._settings.ai_mode == "auto":
            return "live" if self._jev.available else "replay"
        return self._settings.ai_mode

    def status(self) -> dict[str, str | bool]:
        return {
            "mode": self.mode,
            "jevConfigured": self._jev.available,
            "jevModel": self._settings.jev_model,
            "geminiConfigured": self._gemini.available,
            "geminiModel": self._settings.gemini_model,
        }

    async def _decide(
        self, kind: str, state: str, questions: dict, offline: Callable[[], dict], policy: DecisionPolicy
    ) -> _Decision:
        key = FixtureStore.key(kind, state, questions)
        cache_key = f"{key}:{policy.allow_jev}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        decision: _Decision | None = None
        if self.mode in ("live", "record") and policy.allow_jev:
            try:
                started = time.perf_counter()
                result = await self._jev.ask(state, questions)
                logger.info(
                    "Jev %s answered %d questions in %.0f ms",
                    kind,
                    len(questions),
                    (time.perf_counter() - started) * 1000,
                )
                decision = _Decision(result["answers"], "jev", result.get("model"))
                if self.mode == "record":
                    self._store.put(kind, key, result)
            except JevError as exc:
                logger.warning("Jev unavailable, using offline decider: %s", exc)
        if decision is None:
            recorded = self._store.get(kind, key)
            if recorded:
                decision = _Decision(recorded["answers"], "jev (recorded)", recorded.get("model"))
            else:
                decision = _Decision(offline(), "offline decider", None)
        self._cache[cache_key] = decision
        return decision

    async def structure_justification(
        self, data: JustificationInput, policy: DecisionPolicy | None = None
    ) -> StructuredClaim:
        policy = policy or default_policy()
        started = time.perf_counter()
        questions = justification_questions(data.competitors, data.varieties, bool(data.flags))
        flag_lines = "\n".join(f"- {f.message}" for f in data.flags) or "- none"
        state = (
            f"JUSTIFICATION: {data.sentence}\nSEGMENT: {data.segment_label}\n"
            f"ENTRY: {data.entry_summary}\nFLAGS:\n{flag_lines}\nMARKET NOTES: {data.market_notes}"
        )
        claim_key = f"{FixtureStore.key('claim', state, questions)}:{policy}"
        if claim_key in self._claims:
            return self._claims[claim_key].model_copy(update={"latency_ms": 0})
        decision = await self._decide(
            "justification",
            state,
            questions,
            lambda: offline_decider.answer_justification(
                data.sentence, questions, data.market_notes, data.flag_direction
            ),
            policy,
        )
        answers = {k: dict(v) for k, v in decision.answers.items()}
        provider = decision.provider

        low = [
            f
            for f in GATED_CHOICES
            if f in answers and (answers[f].get("confidence") or 0) < policy.choice_threshold
        ] + [
            f
            for f in GATED_SCORES
            if f in answers and (answers[f].get("confidence") or 0) < policy.score_threshold
        ]
        if low and self._gemini.available:
            try:
                override = await self._gemini.extract(
                    f"Extract fields from this sales rep justification.\n{state}",
                    {
                        "type": "OBJECT",
                        "properties": {
                            f: {"type": "STRING", "enum": self._options(f, questions)} for f in low
                        },
                        "required": low,
                    },
                    timeout_seconds=self._settings.gemini_fallback_timeout_seconds,
                )
                for field_name, value in override.items():
                    if field_name in GATED_SCORES:
                        level = float(GATED_SCORES[field_name].index(value))
                        answers[field_name] = {**answers[field_name], "score": level, "confidence": 1.0}
                    else:
                        answers[field_name] = {**answers[field_name], "choice": value, "confidence": 1.0}
                provider = f"{provider} + gemini fallback"
            except (GeminiError, ValueError) as exc:
                logger.warning("Gemini fallback failed: %s", exc)

        def choice(name: str) -> str | None:
            value = answers.get(name, {}).get("choice")
            return None if value in (None, "none") else value

        magnitude = answers.get("magnitude", {}).get("score")
        specificity = answers.get("specificity", {}).get("score")
        claim = StructuredClaim(
            driver=choice("driver") or "other",
            direction=choice("direction") or "neutral",
            magnitude=magnitude,
            magnitude_label=_level(magnitude, MAGNITUDE_LEVELS),
            competitor=choice("competitor"),
            variety=choice("variety"),
            evidence_source=choice("evidence_source"),
            verifiable=answers.get("verifiable", {}).get("noul"),
            consistent_with_notes=answers.get("consistent_with_market_notes", {}).get("noul"),
            specificity=specificity,
            specificity_label=_level(specificity, SPECIFICITY_LEVELS),
            addresses_flags=answers.get("addresses_flags", {}).get("noul"),
            summary="",
            provider=provider,
            model=decision.model,
            low_confidence_fields=[f for f in low if "gemini" not in provider],
            decisions={k: DecisionAnswer.model_validate(v) for k, v in answers.items()},
            latency_ms=0,
        )
        claim.summary = self._template_summary(claim)
        claim.latency_ms = round((time.perf_counter() - started) * 1000)
        self._claims[claim_key] = claim
        return claim

    @staticmethod
    def _options(field_name: str, questions: dict) -> list[str]:
        if field_name in GATED_SCORES:
            return GATED_SCORES[field_name]
        return list(questions[field_name]["criteria"])

    @staticmethod
    def _template_summary(claim: StructuredClaim) -> str:
        return (
            f"{claim.direction.capitalize()} vs plan, {(claim.magnitude_label or 'unsized').lower()} effect, "
            f"driven by {DRIVER_LABELS.get(claim.driver, claim.driver)}"
            + (f"; names {claim.competitor}" if claim.competitor else "")
            + (f"; variety {claim.variety}" if claim.variety else "")
            + f". Evidence: {EVIDENCE_LABELS.get(claim.evidence_source or 'none', 'none stated')}."
        )

    async def polish_summary(self, sentence: str, template: str) -> str | None:
        """Gemini rewrite of the claim summary. Runs after submit so it never sits on the entry path."""
        if not self._gemini.available:
            return None
        try:
            return await self._gemini.write(
                "Rewrite this sales rep justification as one neutral, checkable claim sentence. "
                f"Do not add facts.\nJustification: {sentence}\nStructured: {template}",
                max_words=35,
            )
        except GeminiError as exc:
            logger.warning("Gemini summary failed: %s", exc)
            return None

    async def verify_claim(
        self, claim_text: str, evidence_text: str, numeric_support: bool, policy: DecisionPolicy | None = None
    ) -> tuple[float, str]:
        state = f"CLAIM: {claim_text}\nEVIDENCE: {evidence_text}"
        decision = await self._decide(
            "verification",
            state,
            verification_question(),
            lambda: offline_decider.answer_verification(numeric_support),
            policy or default_policy(),
        )
        return float(decision.answers["supported"]["noul"]), decision.provider

    async def triage(
        self,
        entry_text: str,
        has_critical: bool,
        has_warning: bool,
        weak_record: bool,
        specificity: float,
        policy: DecisionPolicy | None = None,
    ) -> TriageDecision:
        decision = await self._decide(
            "triage",
            entry_text,
            triage_question(),
            lambda: offline_decider.answer_triage(has_critical, has_warning, weak_record, specificity),
            policy or default_policy(),
        )
        answer = decision.answers["triage"]
        return TriageDecision(
            choice=answer["choice"],
            confidence=answer.get("confidence", 0.0),
            probabilities=answer.get("probabilities", {}),
            provider=decision.provider,
        )

    async def write_prose(self, prompt: str, fallback: str, max_words: int = 160) -> tuple[str, str]:
        if not self._gemini.available:
            return fallback, "template"
        try:
            return await self._gemini.write(prompt, max_words=max_words), "gemini"
        except GeminiError as exc:
            logger.warning("Gemini prose failed: %s", exc)
            return fallback, "template"


@lru_cache
def get_decision_provider() -> DecisionProvider:
    return DecisionProvider(get_settings())
