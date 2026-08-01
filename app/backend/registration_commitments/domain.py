from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CANONICAL_FIELD_TYPES = (
    "study-identity",
    "registration-timing",
    "research-question",
    "hypothesis",
    "confirmatory-exploratory-designation",
    "design",
    "condition",
    "manipulation",
    "primary-outcome",
    "secondary-outcome",
    "sample-size-target",
    "power-analysis",
    "stopping-rule",
    "inclusion-criterion",
    "exclusion-criterion",
    "randomization",
    "blinding",
    "data-transformation",
    "statistical-model",
    "covariate",
    "interaction",
    "multiple-comparison-procedure",
    "missing-data-procedure",
    "robustness-sensitivity-analysis",
    "planned-subgroup-analysis",
    "deviation-amendment-statement",
)


@dataclass(frozen=True)
class CommitmentCandidate:
    field_type: str
    study_label: str | None
    structured_value: dict[str, Any]
    evidence_text: str
    source_section: str | None
    source_key: str
    page: int | None
    chunk_id: int | None
    source_locator: dict[str, Any]
    extraction_method: str
    extraction_confidence: str
