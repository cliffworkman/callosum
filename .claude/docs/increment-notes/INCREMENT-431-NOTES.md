# Increment 431 — evidence-bound comparison crosswalks and staleness

**Date:** 2026-07-31
**Status:** implemented

## Outcome

Callosum can run a local comparison against one immutable registration version and persist an inspectable crosswalk.
Every row carries the available evidence from both documents, its source locations, a bounded status/explanation,
uncertainty, exact search scope, and document/pipeline versions. There is no overall compliance, integrity, or risk
score and no author-level conclusion.

## Architecture and decisions

- `registration_comparison_runs` records registration/link/version/hash, article and optional supplement fingerprints,
  attachment/extraction/chunk source snapshots, commitment/retrieval/comparison versions, local embedding version,
  configuration, completion time, and stale reasons.
- `registration_comparison_rows` stores copied registration/publication values/evidence/locators, field, bounded status,
  timing detail, plain-language rationale, uncertainty, search scope, attachment checksum, and human review/note state.
  Copied evidence keeps a prior run inspectable after source/extractor changes.
- **Compare now** is a background job. Missing canonical commitments are generated locally; section/study retrieval and
  classification remain local. Cached local embedding weights are used, with no external-model prompt or egress.
- Deterministic comparators cover sample-size numbers, either/both exclusion thresholds, named outcome term overlap,
  named model families, and directional hypotheses. Exact/high-overlap items can be `aligned`; specific differences are
  `potentially-changed`. Semantically unresolved cases are `not-comparable`, not forced into a difference status.
- Other statuses are: planned item not located in publication, reported item not located in registration, disclosed
  deviation, underspecified registration/publication, ambiguous study mapping, and extraction uncertain.
- Article statements explicitly labeling a primary/secondary outcome can surface as one-sided “reported item not
  located in registration” rows. The absent side names the canonical fields searched; extraction non-detection is not
  represented as proof of absence.
- Registration timing is first class: prospective timing supported, timing unclear, appears after collection began/
  ended or analysis, and insufficient dates. “Appears”/“supported” wording reflects evidence limits; a registration is
  not called a preregistration merely because it is on OSF.
- Staleness is derived and persisted when a run is read: changed link hash/confirmed link, article or included-
  supplement attachment/checksum/chunk/extraction basis, or commitment/retrieval/comparison version. Stale runs remain
  inspectable and retain review state; they are never silently shown as current.
- Review state is per row (`unreviewed`, `reviewed`, `dismissed`) with an optional user note. No aggregate status is a
  positive certificate; even all `aligned` rows mean only that these extracted items/passages aligned.

## Rollback

Revert Increment 431. Migration 0063 has a no-op downgrade because comparison evidence, review decisions, and notes
must not be silently destroyed. Export run/row JSON and review notes before manually dropping either table. Earlier
registration versions, commitments, and retrieval remain independently usable.

## Verification

- Comparator/API/retrieval/commitment/document-scope gate: 30 passed.
- Crosswalk/migration/status consolidated gate: 50 passed.
- Ruff formatting and lint: clean.

