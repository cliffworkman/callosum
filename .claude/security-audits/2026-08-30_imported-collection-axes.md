# Security audit — imported collection/group to axis conversion (backlog #57 Phase 6C)

**Date opened:** 2026-08-30
**Status:** **PASS — bounded local snapshot seam; manual browser interaction deferred**
**Surface:** new local collection preview/mutation API; persisted import provenance; Zotero hierarchy repair;
optional reuse of existing local axis-scoring jobs.

## Required review before closure

- Allowlisted import sources and axis kinds; bounded collection/membership/axis counts; hierarchy cycle and orphan
  rejection; axis-label caps.
- Explicit user action only. Curated is the default; keyword scoring is a separate unchecked choice with cost/time
  disclosure and uses the existing local scoring path without provider calls.
- Exact imported membership becomes manual assignments; nested papers roll up deterministically; repeat requests
  cannot duplicate axes; later imports cannot overwrite a user-owned axis.
- New mutation routes remain covered by the existing write/read-only middleware and QA route map.
- No new egress, credentials, file reads, scholarly logs, or citation/document semantics.

## Closure evidence

- Import sources and axis kinds are closed literals at both API and domain boundaries. Collection, membership,
  per-action axis, and label bounds have positive/adversarial tests.
- Parent links are restored in a two-pass transaction; absent parents, cross-source parents, cycles, and no-root
  graphs fail closed. A malformed graph cannot be flattened silently.
- Axis creation requires a POST from the explicit UI control. Curated stays default; local keyword scoring is an
  unchecked opt-in and reuses the existing authoritative `axis_score_jobs` lifecycle.
- Exact descendant membership becomes manual assignments. The provenance link makes repeat actions idempotent;
  re-import cannot modify a linked axis, and deleting an axis removes only the link.
- Final affected suite: **239 passed** in 286.81s. Ruff, Bandit, Tach, 573-file line-budget, 437/437 gated API
  coverage, website coverage, and diff checks passed.
- Final staged pre-commit passed every applicable hook. The added-line secret/private-path scan passed, and the
  gitignored personal EndNote fixture directory is absent from the index.
- Full collection succeeds at **2600 tests**. The serial full suite exceeded its fixed one-hour harness bound and
  the known isolated summary-overview circular import reproduced through modules unrelated to this surface; no
  full-suite pass is claimed.
- Route 93 owns the deferred real-browser checks. They were not run because the user requested one consolidated
  manual verification pass after the arc.

No new provider call, credential, filesystem path, raw scholarly content, or external service was introduced.
