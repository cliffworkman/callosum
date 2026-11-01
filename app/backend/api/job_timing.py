"""Privacy-safe calibration identities for model-backed job stages."""

from __future__ import annotations

from typing import Any

from app.backend.api.job_store import timing_key

# Stages whose duration depends on the synthesis verifier (inc 619). G2: DeBERTa takes about 2.5x MiniLM2's time here.
VERIFIER_STAGES = frozenset({"verifying_citations"})


def stage_reporter(store: Any, job_id: str, calibration_key: str, *, verifier: str | None = None):
    """Adapt a workflow's stage callback to the shared JobStore contract. A non-baseline ``verifier`` gets its own
    calibration identity for the verification stage only, so its estimate never reuses MiniLM2 durations (until three
    receipts exist the Status estimate stays indeterminate); generation and other stages keep their history."""
    from app.backend.summarization.nli_profiles import BASELINE_NLI_PROFILE_KEY

    def report(key: str, label: str, size: int | None, variable: bool) -> None:
        separate = verifier is not None and verifier != BASELINE_NLI_PROFILE_KEY and key in VERIFIER_STAGES
        store.mark_stage(
            job_id,
            key,
            label,
            timing_key=f"{calibration_key}|nli-{verifier}"[:400] if separate else calibration_key,
            workload_size=size,
            variable=variable,
        )

    return report


def synthesis_timing_key(config: Any) -> str:
    """Separate provider/model/wire/endpoint/target shapes without exposing endpoint text."""
    from app.backend.llm.cache import canonical_hash
    from app.backend.llm.providers import completion_request_identity, requires_egress

    request = completion_request_identity(config)
    endpoint = canonical_hash({"endpoint": request.base_url or "provider-sdk-default"})[:16]
    return timing_key(
        "synthesis",
        config.provider,
        config.model,
        request.wire_format,
        endpoint,
        "remote" if requires_egress(config) else "device-local",
    )


def critical_read_timing_key(workflow: str, embed_model: Any, stance_scorer: Any) -> str:
    """Separate local model/backend/device shapes; omit unavailable optional labels."""
    return timing_key(
        workflow,
        getattr(embed_model, "name", type(embed_model).__name__),
        getattr(stance_scorer, "model_name", type(stance_scorer).__name__),
        getattr(stance_scorer, "device", None),
        getattr(stance_scorer, "backend", "torch"),
    )
