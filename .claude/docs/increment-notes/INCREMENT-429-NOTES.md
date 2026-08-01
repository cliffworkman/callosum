# Increment 429 — canonical registration commitments

**Date:** 2026-07-31
**Status:** implemented

## Outcome

Each immutable registration version can be converted locally into bounded, evidence-bearing plan commitments. The
output is a set of inspectable extraction proposals—not a whole-document judgment and not a comparison to the paper.

## Architecture and decisions

- `registration_commitments` persists one canonical field per source question/passage and extraction version. Rows
  retain structured value, verbatim evidence, question/section/source key, attachment/chunk/page/bbox locator,
  extraction method/confidence, study label where detected, and the exact registration content hash.
- The canonical vocabulary covers study identity/timing, questions/hypotheses/designation, design/conditions/
  manipulations/outcomes, sampling/power/stopping, eligibility/randomization/blinding, transformations/models/
  covariates/interactions/multiplicity/missing data, sensitivity/subgroups, and amendment/deviation statements.
- OSF questions are mapped from preserved schema labels and response keys. AsPredicted's numbered questions have a
  provider-specific deterministic map. Registration title/timestamp and revision metadata stay first-class fields.
- Local/free-text PDFs are segmented and conservatively mapped by explicit headings/phrases from the exact
  registration attachment. Unmappable passages are omitted rather than forced into a field; local mappings carry
  lower confidence than structured registry mappings.
- Each answer is linked back to an exact registration chunk/page when local extraction can locate it; structured
  question identifiers remain available when a page is not meaningful.
- The extractor uses no LLM and makes no network request. Future model-assisted mapping, if added, must use the
  existing user-controlled AI/egress gate and remain a proposal.
- Re-running the same extraction version replaces only that version's rows. A future extraction version can coexist,
  allowing downstream comparisons to identify/stale against their original extractor basis.

## Epistemic boundary

Canonical placement means “Callosum mapped this registration evidence to this plan field.” It does not assert that
the plan is clear, prospective, correct, complete, or followed. Extraction confidence describes the mapping, not the
quality or integrity of a study.

## Rollback

Revert Increment 429. Migration 0062 has a no-op downgrade so evidence/version provenance is not silently destroyed.
Before manually dropping `registration_commitments`, export rows used by any later comparison result. Increment 428's
registration documents remain independently inspectable.

## Verification

- Commitment/acquisition/document-scope/health gate: 29 passed.
- Migration/model/commitment gate: 20 passed.
- Ruff formatting and lint: clean.

