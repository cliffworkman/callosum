# Security Audit — Persistent "not a duplicate" dismiss (increment 64)

**Date:** 2026-06-20
**Trigger:** New API endpoint (`POST /papers/duplicates/dismiss`) + a new persistence table
(`dismissed_duplicate_pairs`, migration 0006). (Also a behavior-preserving module split — see end.)

## What changed
- New `dismissed_duplicate_pairs` table (canonical `low < high` pair, FK CASCADE, unique). The
  duplicate-detection scan drops dismissed pairs **before** its union-find, so a pair the user marked "not a
  duplicate" never re-flags. New `POST /papers/duplicates/dismiss` persists a group's pairs; the frontend
  dismiss button calls it (keeping the immediate session-hide).

## Threat review
- **Read-only-ish, non-destructive, local-only.** The feature records a *preference* ("these are not
  duplicates") — it never deletes papers or data, and makes **no external call** (no egress/ingestion). The
  scan itself remains local + flag-only.
- **SQL injection (rule #3):** the dismiss insert and the scan's dismissed-pair filter use **SQLAlchemy
  bound-param** statements (`insert(...).values(...)`, `select(...).where(... in_(...))`) — no string
  interpolation. The filter compares Python tuples in memory.
- **Input validation (rule #4):** `paper_ids` is a Pydantic `list[int]` (min_length 2). The endpoint then
  filters to **existing, live (non-trashed) paper ids** via a bound `IN` query and requires ≥2 survivors
  (else 422) — so a non-existent/foreign id can't be stored (also guarded by the FK). Pairs are stored
  canonical `(min, max)`; re-dismissing is an idempotent no-op (`INSERT OR IGNORE`).
- **Resource:** one row per distinct dismissed pair; a group of N stores C(N,2) rows (N is tiny in
  practice). Bounded by real review activity.
- **API surface:** one new POST route, added to the route-surface invariant allowlist
  (`tests/test_health.py`). No new GET surface; CORS unchanged. The route is registered before
  `/papers/{paper_id}` (literal-segment precedence) — verified by the dismiss test passing.
- **Migration:** additive, idempotent (no-op on a fresh DB built by 0001's create_all), single linear head
  `0006`. FK `ondelete=CASCADE` so a future hard-delete cleans a paper's dismissals.
- **Recovery:** a dismiss is permanent with no in-app undo today (deferred). Low risk — it only *suppresses
  a future flag*, deletes nothing; a mistakenly-dismissed real duplicate can still be found/merged manually.

## Negative-path checks (results)
- Seed a shared-PMID pair → scan flags 1 group; dismiss → **re-scan flags 0 groups** (persistent). **PASS.**
- Re-dismissing the same pair (either order) → 204, still 0 groups (idempotent). **PASS.**
- `paper_ids` with <2 ids, or 2 ids where only 1 exists → **422**. **PASS.**
- Live E2E (`.local/dedup_dismiss_e2e/`): dismiss in the modal → re-open → the pair is no longer flagged,
  0 console errors. **PASS.**

Full suite: **228 passed**.

## Module split (rule #1, behavior-preserving)
Extending the dedup feature pushed `routers/papers.py` to 636 lines (> the 600-line cap). The cohesive
duplicates concern (models + `_DedupJobStore` + the scan/status/dismiss endpoints + `_run_dedup_job`) was
**moved verbatim** to `routers/duplicates.py` (157), bringing `papers.py` to 497. `app.py` imports
`_DedupJobStore` from the new module and includes its router **before** `papers.router`. No behavior change
(the full suite + route-surface invariant are green).

**Security Audit: PASS.**
