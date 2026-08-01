# Increment 430 — section- and study-aware publication retrieval

**Date:** 2026-07-31
**Status:** implemented

## Outcome

Each canonical registration commitment can retrieve candidate publication passages locally without searching every
attachment indiscriminately. The response records where Callosum searched and whether it had to broaden the search;
it does not decide whether a passage is aligned or changed.

## Architecture and decisions

- A compatibility map routes each canonical field to likely section families first: hypotheses to introduction/
  methods/results; sampling and stopping to participants/procedure/methods; outcomes to measures/outcomes/results;
  models and covariates to analysis/results; sensitivity/subgroups to results/supplements/discussion, and so on.
- Section normalization honors an explicit chunk section before fuzzy aliases in body text. This prevents a sentence
  mentioning “analysis” inside Discussion from silently changing the recorded section searched.
- Semantic ranking encodes only the commitment query and bounded local publication chunks with Callosum's local
  embedding model. The endpoint uses cached local weights only and sends no text to a provider. Similarity is a labeled
  retrieval signal, not a consistency/confidence score.
- Retrieval starts with compatible article sections. It expands to the whole article only if no bounded hit clears a
  conservative retrieval floor. The result records expected/actual section families and expansion state.
- Supplements are a distinct opt-in scope and are retrieved only when requested. Registration/protocol/other chunks
  are structurally unavailable through the explicit article/supplement repository calls.
- Each hit carries exact attachment/chunk/page/bbox, section family, search phase, text, and adjacent same-attachment
  context. Context expansion cannot turn adjacent chunks into ranked candidates.
- Study/Experiment/Trial-phase/Cohort labels are retained. An exact label restricts candidates to that study. Missing
  or multi-study mapping is marked `ambiguous` for later human inspection rather than silently comparing studies.
- The non-detection note states that failure to locate evidence in searched sections is not proof of non-reporting.

## Rollback

Revert Increment 430. No migration or persisted retrieval output is introduced; Increment 429 commitments remain.
Later comparison persistence must retain its copied search-scope metadata if this retriever is replaced.

## Verification

- Retrieval/commitment/document-scope/health gate: 25 passed.
- Ruff formatting and lint: clean.

