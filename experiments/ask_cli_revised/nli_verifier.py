"""Selectable local NLI verifier for the experimental Ask route.

``minilm`` is the shared application default and stays the default here: nothing changes unless a caller
selects ``deberta``. ``deberta`` swaps the one support scorer every Ask NLI call site shares (source
verification, child-overview screening and parent-synthesis screening all call
``rt.verifier.support_scorer``), so no downstream stage can keep scoring with MiniLM.

Model lineage (credit, per ``.claude/CREDIT-THE-LINEAGE.md``):

- Checkpoint: ``MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`` (Laurer, van Atteveldt, Casas & Welbers, 2024,
  "Less Annotating, More Classifying", *Political Analysis* 32(1)).
- Architecture: DeBERTaV3 (He, Gao & Chen, 2023, ICLR).
- Training data: MultiNLI (Williams, Nangia & Bowman, 2018), FEVER-NLI and ANLI (Nie et al., 2019/2020).

Model-specific settings, stated rather than inherited from MiniLM:

- Entailment threshold 0.50, the value evaluated in the Phase 34 scientific NLI bakeoff. It applies wherever
  this scorer's entailment probability is thresholded: the source verifier and both synthesis screens.
- Label order is entailment / neutral / contradiction (MiniLM's is contradiction / entailment / neutral).
  The shared scorer already reads ``id2label``; this module additionally refuses to load a checkpoint whose
  labels differ, so a wrong mapping cannot fall through to the positional MiniLM defaults.
- Premise is the source passage and hypothesis the claim, exactly as for MiniLM (unchanged shared code).
- The contradiction threshold (0.55), the similarity gate (0.70) and the exact-quote gate (1.0) are the
  shared defaults, unchanged. The bakeoff did not evaluate a DeBERTa-specific contradiction threshold.
- FP32 weights, as in the hardware bakeoff.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.backend.summarization.verification import EmbeddingSupportScorer, NLISupportScorer, VerificationConfig
from experiments.ask_cli_revised import timing

DEBERTA_NLI_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
DEBERTA_NLI_REVISION = "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"
DEBERTA_ID2LABEL = {0: "entailment", 1: "neutral", 2: "contradiction"}
DEBERTA_SUPPORT_THRESHOLD = 0.50
DEBERTA_VERIFICATION_CONFIG = VerificationConfig(support_threshold=DEBERTA_SUPPORT_THRESHOLD)
DEVICE_ENV = "CALLOSUM_ASK_NLI_DEVICE"  # auto (default) | cpu | cuda | mps
VERIFIERS = ("minilm", "deberta")
_PROBE = [("The sample included forty adults.", "Forty adults were included in the sample.")]


def resolve_device(requested: str | None = None) -> str:
    """The device to try first. ``auto`` prefers an accelerator this torch build actually supports."""
    requested = (requested or os.environ.get(DEVICE_ENV) or "auto").lower()
    if requested not in ("auto", "cpu", "cuda", "mps"):
        raise ValueError(f"unsupported NLI device {requested!r}")
    if requested == "cpu":
        return "cpu"
    import torch

    if requested in ("auto", "cuda") and torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if requested in ("auto", "mps") and mps is not None and mps.is_available():
        return "mps"
    return "cpu"


@dataclass
class DebertaSupportScorer(NLISupportScorer):
    """The shared NLI support scorer bound to the evaluated DeBERTa checkpoint, with a usage receipt.

    Scoring is the parent's, unchanged. The counters exist so a run can show that DeBERTa answered every
    pair: the parent substitutes embedding similarity when inference fails, and that substitution reports
    no contradiction score, which is what ``fallback_pairs`` counts.
    """

    calls: int = field(default=0, init=False)
    pairs_scored: int = field(default=0, init=False)
    fallback_pairs: int = field(default=0, init=False)
    load_receipt: dict = field(default_factory=dict, init=False)

    def support_and_contradiction_many(self, pairs: list[tuple[str, str]]) -> list[tuple[float, float | None]]:
        with timing.span("nli.scorer_call"):
            results = super().support_and_contradiction_many(pairs)
        self.calls += 1
        self.pairs_scored += len(results)
        self.fallback_pairs += sum(1 for _, contradiction in results if contradiction is None)
        return results

    def _load_model(self) -> object:
        if self._model is None:
            self._model = self._load_checked()
        return self._model

    def _load_checked(self) -> object:
        requested = self.device or "cpu"
        attempts = [requested] if requested == "cpu" else [requested, "cpu"]
        failure = None
        for device in attempts:
            try:
                model = self._construct(device)
                probe = [float(v) for v in model.predict(_PROBE, apply_softmax=True)[0]]
            except Exception as exc:  # noqa: BLE001 - an accelerator that cannot load or infer falls back to CPU
                if device == "cpu":
                    raise
                failure = f"{type(exc).__name__}: {str(exc)[:200]}"
                continue
            self.load_receipt = _receipt(model, self, requested=requested, device=device, failure=failure, probe=probe)
            return model
        raise AssertionError("unreachable: the CPU attempt either returns or raises")

    def _construct(self, device: str) -> object:
        from sentence_transformers import CrossEncoder

        model = CrossEncoder(
            self.model_name,
            revision=self.revision,
            device=device,
            local_files_only=self.local_files_only,
            backend=self.backend,
            model_kwargs={"use_safetensors": True},
        )
        labels = {int(k): str(v).lower() for k, v in model.model.config.id2label.items()}
        if labels != DEBERTA_ID2LABEL:
            raise ValueError(f"unexpected NLI label mapping {labels}; refusing to guess an entailment index")
        return model

    def receipt(self) -> dict:
        """Identity of the loaded model plus usage so far. Loads the model if nothing has yet."""
        self._load_model()
        return {
            **self.load_receipt,
            "calls": self.calls,
            "pairs_scored": self.pairs_scored,
            "embedding_fallback_pairs": self.fallback_pairs,
        }


def _receipt(model, scorer, *, requested, device, failure, probe) -> dict:
    parameter = next(model.model.parameters())
    config = model.model.config
    return {
        "verifier": "deberta",
        "model_name": scorer.model_name,
        "revision_requested": scorer.revision,
        "revision_loaded": getattr(config, "_commit_hash", None),
        "architecture": type(model.model).__name__,
        "id2label": {str(k): v for k, v in sorted(config.id2label.items())},
        "dtype": str(parameter.dtype),
        "device_requested": requested,
        "device": str(parameter.device),
        "device_fallback_reason": failure,
        "max_length": getattr(model, "max_length", None) or model.tokenizer.model_max_length,
        "probe_probabilities": probe,
        "support_threshold": DEBERTA_SUPPORT_THRESHOLD,
        "contradiction_threshold": DEBERTA_VERIFICATION_CONFIG.contradiction_threshold,
        "retrieval_threshold": DEBERTA_VERIFICATION_CONFIG.retrieval_threshold,
        "quote_threshold": DEBERTA_VERIFICATION_CONFIG.quote_threshold,
    }


def deberta_support_scorer(embedding_model, *, device: str | None = None) -> DebertaSupportScorer:
    return DebertaSupportScorer(
        model_name=DEBERTA_NLI_MODEL,
        revision=DEBERTA_NLI_REVISION,
        device=resolve_device(device),
        fallback_scorer=EmbeddingSupportScorer(embedding_model),
    )


def runtime_kwargs(verifier: str) -> dict:
    """Extra ``runtime.build_runtime`` arguments for ``verifier``. Empty for the default, so that call is unchanged."""
    if verifier not in VERIFIERS:
        raise ValueError(f"unknown NLI verifier {verifier!r} (expected one of {', '.join(VERIFIERS)})")
    if verifier == "minilm":
        return {}
    return {"verification_config": DEBERTA_VERIFICATION_CONFIG, "support_scorer_factory": deberta_support_scorer}


def screen_config(verifier: str) -> VerificationConfig | None:
    """The thresholds the synthesis screens apply for ``verifier``; ``None`` keeps the shared defaults."""
    return DEBERTA_VERIFICATION_CONFIG if verifier == "deberta" else None
