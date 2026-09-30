from app.schemas.common import CamelModel


class DecisionAnswer(CamelModel):
    type: str
    choice: str | None = None
    confidence: float | None = None
    probabilities: dict[str, float] | None = None
    score: float | None = None
    noul: float | None = None


class StructuredClaim(CamelModel):
    driver: str
    direction: str
    magnitude: float | None
    magnitude_label: str | None
    competitor: str | None
    variety: str | None
    evidence_source: str | None
    verifiable: float | None
    consistent_with_notes: float | None
    specificity: float | None
    specificity_label: str | None
    addresses_flags: float | None
    summary: str
    provider: str
    model: str | None
    low_confidence_fields: list[str]
    decisions: dict[str, DecisionAnswer]
    latency_ms: int


class TriageDecision(CamelModel):
    choice: str
    confidence: float
    probabilities: dict[str, float]
    provider: str
