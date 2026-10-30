"""Model provenance on a synthesis response: which retrieval encoder ranked its evidence and which NLI model verified
its claims, read only from what the run recorded in ``scope_ref_json``.

Never substituted from the current Settings: a row written before provenance was recorded comes back with
``recorded=False`` and no model names, never a guessed MiniLM. ``embedding_fallback`` is None on such rows, because
before the no-fallback contract a failed NLI call could silently fall back to embedding similarity and a pre-contract
row cannot rule that out.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.backend.embeddings.profiles import BASELINE_PROFILE_KEY, PROFILES
from app.backend.summarization.nli_profiles import BASELINE_NLI_PROFILE_KEY, NLI_PROFILES


class RetrievalProvenanceResponse(BaseModel):
    profile: str | None = None
    label: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    experimental: bool = False


class VerificationProvenanceResponse(BaseModel):
    profile: str | None = None
    label: str | None = None
    model_name: str | None = None
    revision: str | None = None
    experimental: bool = False
    thresholds_calibrated_on: str | None = None
    embedding_fallback: bool | None = None  # False = recorded under the no-fallback contract; None = not recorded


class ModelProvenanceResponse(BaseModel):
    recorded: bool
    retrieval: RetrievalProvenanceResponse | None = None
    verification: VerificationProvenanceResponse | None = None


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def model_provenance_from_ref(scope_ref: Any) -> ModelProvenanceResponse:
    ref = scope_ref if isinstance(scope_ref, dict) else {}
    retrieval_raw, verification_raw = ref.get("retrieval_embedding"), ref.get("verification_nli")
    retrieval = verification = None
    if isinstance(retrieval_raw, dict):
        profile = PROFILES.get(retrieval_raw.get("profile"))  # type: ignore[arg-type]
        retrieval = RetrievalProvenanceResponse(
            profile=_text(retrieval_raw.get("profile")),
            label=profile.label if profile else None,
            model_name=_text(retrieval_raw.get("model_name")),
            model_version=_text(retrieval_raw.get("model_version")),
            experimental=bool(profile and profile.key != BASELINE_PROFILE_KEY),
        )
    if isinstance(verification_raw, dict):
        nli = NLI_PROFILES.get(verification_raw.get("profile"))  # type: ignore[arg-type]
        fallback = verification_raw.get("embedding_fallback")
        verification = VerificationProvenanceResponse(
            profile=_text(verification_raw.get("profile")),
            label=nli.label if nli else None,
            model_name=_text(verification_raw.get("model_name")),
            revision=_text(verification_raw.get("revision")),
            experimental=bool(nli and nli.key != BASELINE_NLI_PROFILE_KEY),
            thresholds_calibrated_on=_text(verification_raw.get("thresholds_calibrated_on")),
            embedding_fallback=fallback if isinstance(fallback, bool) else None,
        )
    return ModelProvenanceResponse(
        recorded=retrieval is not None or verification is not None, retrieval=retrieval, verification=verification
    )
