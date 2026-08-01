# Increment 435 — optional evidence-bounded comparison triage

## Outcome

Meta-Preregistration comparison runs now offer an explicit **Triage rows with AI** action modeled on Discover →
Funding. A successful run adds reversible row annotations and an **AI-focused** view; **All rows** always restores the
unchanged deterministic crosswalk.

## Design and epistemic boundary

- Labels are `prioritize`, `uncertain`, and `likely_noise`; they are reading aids, not revised comparison statuses.
- Only `likely_noise` can leave the focused view. Missing/malformed/unevaluated annotations fail open and stay visible.
- The model cannot alter evidence, source locations, row ordering, review/dismiss state, or notes.
- No overall score, compliance/integrity judgment, author judgment, or positive certificate is produced.
- General controls reuse Settings cards, rows, notes, buttons, and the existing segmented filter treatment.

## Privacy and persistence

The existing configured-provider/data-egress gate applies. The bounded payload contains saved comparison fields and
short paired passages only; it excludes documents, locators, chunk IDs, exact search receipts, notes, and review state.
Migration 0064 stores one annotation per row with provider, model, prompt version, rationale, and evidence fingerprint.
Document/comparison/prompt drift makes annotations stale and disables filtering until the current comparison is
triaged again.

## Tests

Hermetic backend tests cover payload minimization, output validation/fail-open behavior, gate-before-evaluator,
persistence without crosswalk mutation, and stale-run refusal. Frontend assembly coverage pins explicit invocation,
disclosure language, reversible views, fail-open filtering, styles, and mobile stacking. Route 83 and the registration
evaluation rubric include the triage path.

Validation completed with **76** focused backend/frontend tests, **10** migration/startup tests, **2** dedicated
Chromium routes, and the full suite at **1782 passed, 1 skipped**. Ruff format/check, frontend rebuild, the 600-line
budget, and the QA surface map (**352/352 API; 1545/1545 frontend**) are clean.

## Rollback

Revert Increment 435 and rebuild `callosum-app.html`. Migration 0064 preserves annotation receipts on downgrade; the
underlying registration workflow data is unaffected.
