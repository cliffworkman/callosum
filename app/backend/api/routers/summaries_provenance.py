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
    # inc 618: why this encoder ranked the evidence. All None on syntheses saved before inc 618 (not guessed).
    preference: str | None = None  # automatic | user
    fallback_reason: str | None = None
    index_verified_complete: bool | None = None
    note: str | None = None


# Past tense: a saved synthesis describes what happened when it ran.
_FALLBACK_NOTES = {
    "model_unavailable": "MiniLM was used because the Arctic S model was not yet downloaded and verified.",
    "indexing": "MiniLM was used while the Arctic S index was being built.",
    "catching_up": "MiniLM was used while newly added or changed passages were indexed for Arctic S.",
    "paused": "MiniLM was used because Arctic S indexing was paused.",
    "cancelled": "MiniLM was used because Arctic S indexing was cancelled.",
    "failed": "MiniLM was used because Arctic S indexing had stopped after repeated failures.",
}


def _retrieval_note(raw: dict) -> str | None:
    if raw.get("preference") == "user":
        return "Selected explicitly in Settings."
    return _FALLBACK_NOTES.get(raw.get("fallback_reason"))  # type: ignore[arg-type]


class VerificationProvenanceResponse(BaseModel):
    profile: str | None = None
    label: str | None = None
    model_name: str | None = None
    revision: str | None = None
    experimental: bool = False
    thresholds_calibrated_on: str | None = None
    embedding_fallback: bool | None = None  # False = recorded under the no-fallback contract; None = not recorded
    # inc 619: how this verifier was chosen. All None on syntheses saved before inc 619 (not guessed).
    preference: str | None = None  # automatic | user
    preferred_profile: str | None = None
    fallback_reason: str | None = None
    support_threshold: float | None = None
    contradiction_threshold: float | None = None
    note: str | None = None
    # A non-baseline verifier's `contradicted` is shown as a possible disagreement to review (G1 acceptance). Derived
    # from the recorded verifier itself, so MiniLM2 results keep their wording whatever the current default is.
    cautious_contradictions: bool = False


DEBERTA_CONTRADICTION_NOTE = "The model flags a possible disagreement with the source. Review the cited passage."

_VERIFIER_NOTES = {
    "not_qualified": "MiniLM2 verified this synthesis: automatic DeBERTa verification was not enabled.",
    "not_provisioned": "MiniLM2 verified this synthesis because the DeBERTa model was not yet downloaded and verified.",
    "not_verified": "MiniLM2 verified this synthesis because the DeBERTa model files could not be verified or loaded.",
    "insufficient_memory": "MiniLM2 verified this synthesis because there was not enough free memory for DeBERTa.",
    "memory_unmeasured": "MiniLM2 verified this synthesis because free memory could not be measured.",
}


def _verifier_note(raw: dict) -> str | None:
    if raw.get("preference") == "user":
        return "Selected explicitly in Settings."
    return _VERIFIER_NOTES.get(raw.get("fallback_reason"))  # type: ignore[arg-type]


def cautious_contradictions(scope_ref: Any) -> bool:
    raw = scope_ref.get("verification_nli") if isinstance(scope_ref, dict) else None
    profile = raw.get("profile") if isinstance(raw, dict) else None
    return isinstance(profile, str) and profile in NLI_PROFILES and profile != BASELINE_NLI_PROFILE_KEY


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


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
            preference=_text(retrieval_raw.get("preference")),
            fallback_reason=_text(retrieval_raw.get("fallback_reason")),
            index_verified_complete=(
                verified if isinstance(verified := retrieval_raw.get("index_verified_complete"), bool) else None
            ),
            note=_retrieval_note(retrieval_raw),
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
            preference=_text(verification_raw.get("preference")),
            preferred_profile=_text(verification_raw.get("preferred_profile")),
            fallback_reason=_text(verification_raw.get("fallback_reason")),
            support_threshold=_number(verification_raw.get("support_threshold")),
            contradiction_threshold=_number(verification_raw.get("contradiction_threshold")),
            note=_verifier_note(verification_raw),
            cautious_contradictions=cautious_contradictions(ref),
        )
    return ModelProvenanceResponse(
        recorded=retrieval is not None or verification is not None, retrieval=retrieval, verification=verification
    )
