# Increment 10 Notes

## Implemented

- Added `NLISupportScorer` satisfying the existing `SupportScorer` protocol.
- Kept `EmbeddingSupportScorer` as the default verifier support scorer.
- Added optional embedding/fallback support when the NLI model is unavailable.
- Added a `support_scorer` parameter to `summarize_scope()` so orchestration can opt into NLI without hard-coding a model.
- Added hermetic tests for scorer swappability, topical-but-unentailed failure, entailed success, and fallback behavior.

## NLI Model

- Chosen default model: `cross-encoder/nli-MiniLM2-L6-H768`.
- Rationale: it is a sentence-transformers CrossEncoder NLI model, smaller than DeBERTa-base class NLI models, and suitable as an opt-in local verifier upgrade.
- Footprint/download behavior: weights are not committed; first real use may download model files through `sentence-transformers` unless `local_files_only=True` is set.
- Dependency impact: no new dependency was added because `sentence-transformers` is already in `pyproject.toml`.

## Entailment Confidence

- Input order is `premise=passage`, `hypothesis=sentence`.
- `CrossEncoder.predict(..., apply_softmax=True)` is used.
- Confidence is the entailment class probability.
- The scorer reads `model.model.config.id2label` when available; otherwise it falls back to the sentence-transformers NLI convention from the docs: `[contradiction, entailment, neutral]`.

## Fallback And Default

- `LocalCitationVerifier` still defaults to `EmbeddingSupportScorer`.
- `NLISupportScorer` is opt-in via the existing `support_scorer` seam.
- If `NLISupportScorer` cannot load or run its model and a `fallback_scorer` is configured, it returns the fallback scorer's value.
- If no fallback is configured, the model error is raised.

## Deferred / Out Of Scope

- No schema changes.
- No Gemini/LLM support grading.
- No UI, FastAPI, discovery, full-text acquisition, streaming, or multi-model ensembles.
- Contradiction-specific status remains deferred; low entailment currently prevents `verified` and records the existing non-verified status.

## Ambiguities / Questions

- None surfaced.

## Raw Pytest Output

NLI support suite:

```text
....                                                                     [100%]
4 passed in 4.53s
```

Summarization plus NLI support suites:

```text
.........                                                                [100%]
9 passed in 5.51s
```

Full suite:

```text
............................................                             [100%]
44 passed in 28.61s
```
