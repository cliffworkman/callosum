# Increment 433 — registration workflow completion hardening

**Date:** 2026-07-31
**Status:** implemented

## Outcome

The end-to-end registration workflow now fails closed at its less common state transitions. Empty commitment
extraction produces an inspectable `extraction-uncertain` row rather than an empty crosswalk; comparison timing reads
only the chunks recorded in that commitment's search receipt; every row records exact searched chunk IDs and
attachment checksums; and local attachment-role changes immediately refresh and invalidate the affected workflow.

## Hardening decisions

- OSF collection endpoints are followed through bounded pagination. The canonical snapshot now retains the complete
  retrieved schema-response history, revision metadata, registration DOI, publication DOI resources, storage-provider
  metadata, and a bounded recursive file manifest. Structured schema responses remain the primary comparison record;
  linked OSF file bytes are not silently downloaded because relevance requires a reader choice.
- Acquisition rechecks current provider availability after the download seam and rechecks user confirmation inside
  the write transaction. Comparison does the equivalent check before saving. A rejection or incorrect-match action
  therefore wins over an already-running background job.
- If a previously acquired content-hash version survives after its managed attachment is removed, explicit
  re-acquisition restores a new managed attachment onto the immutable version instead of crashing or duplicating the
  version.
- Reclassifying a local registration attachment away from `preregistration` makes its link unavailable and stales
  prior comparison runs. Reclassification back plus explicit confirmation restores the path.
- Printed/manual copies of the same normalized registration identity are one reference; the printed, page-anchored
  evidence wins while the persisted identity is retained.
- Timing accepts ISO or slash dates, incorporates AsPredicted's existing-data response and later registry response
  updates, and uses cautious `appears` wording. Explicit stopping-rule and named-covariate differences gained bounded
  deterministic checks.
- Contextual title/author overlap cannot promote a candidate when its date is after the publication year.

## Evaluation

Every curated fixture in `tests/fixtures/registration_evaluation_cases.json` now names an executable pytest function.
The manifest test parses and validates those targets, preserving separate stage dimensions and forbidding a composite
metric. Provider pagination/status changes, attachment restoration/role changes, empty extraction, source receipts,
timing scope, and background-state guards have direct hermetic tests.

## Rollback

Revert Increment 433's code/tests/docs and rebuild `callosum-app.html`. No migration or dependency was added. Existing
links, immutable versions, commitments, comparison evidence, and review notes remain readable by Increment 432; do not
delete them as part of rollback.

## Verification

- Focused registration/document-scope/frontend acceptance suite: **122 passed** before the final restoration case.
- Full suite, eight fixed workers: **1778 passed, 1 skipped** in 665.71 seconds.
- Ruff format/check, frontend rebuild, line-budget, diff hygiene: clean.
- Computed QA surface map: **351/351 API** and **1537/1537 frontend**, zero uncovered.
