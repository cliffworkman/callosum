# Security and privacy audit — registration-comparison LLM triage

**Date:** 2026-08-01
**Increment:** 435
**Result:** PASS

## Boundary reviewed

The new endpoint is invoked only by **Triage rows with AI** on a current saved comparison. Opening the paper,
Transparency panel, Meta-Preregistration workspace, or comparison detail performs no model call. The endpoint uses the
existing configured-provider AI/data-egress gate and refuses before an injected evaluator can run when consent is off.
A local provider follows the existing non-egress provider path.

## Data minimization and validation

- Payloads contain at most 50 persisted rows and 60,000 serialized characters. Each registration/publication passage
  is capped at 900 characters; explanations, uncertainty, section names, and list lengths are separately bounded.
- The payload excludes whole documents, source locators, attachment/chunk identifiers, exact search receipts, user
  notes, and review/dismiss state.
- Model output is parsed as JSON, row IDs are checked against the submitted set, labels use a three-value allowlist,
  and text/list fields are length bounded. A model-supplied visibility boolean is ignored.
- `likely_noise` is the only label permitted to hide a row. Missing, malformed, duplicate, truncated, or unevaluated
  output fails open: the affected row remains in the focused view.

## Persistence and failure behavior

Annotations live in a separate table keyed to comparison rows and cannot overwrite deterministic statuses, evidence,
ordering, source locators, review state, or notes. Provider/model/prompt and an evidence fingerprint are retained.
Comparison, evidence, or prompt drift marks the layer stale and disables focused filtering. A stale comparison refuses
new triage. Provider/configuration failures are visible and leave the complete crosswalk available.

No score, author judgment, compliance/integrity conclusion, automatic discovery, arbitrary fetch, or new dependency is
introduced. Hermetic tests cover gate-before-evaluator behavior, bounded payloads, output coercion, persistence,
staleness, and fail-open display semantics.

## Rollback

Revert Increment 435 and rebuild the frontend. Migration 0064 intentionally has a no-op downgrade so the model-output
receipt is not silently destroyed; export and deliberately remove the annotation table only if data deletion is
desired. All registration links, versions, commitments, comparisons, evidence, notes, and review state remain intact.
