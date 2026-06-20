# Security Audit — Un-dismiss / manage dismissals (increment 67)

**Date:** 2026-06-20
**Trigger:** Two new API endpoints — `GET /papers/duplicates/dismissed` (read) and
`POST /papers/duplicates/undismiss` (removes dismissed pairs). Completes inc-64's persistent dismiss with an
in-app undo. No new table/migration.

## What changed
The user can now **see** the duplicate pairs they marked "not a duplicate" (inc 64) and **un-dismiss** them
(so the scan will flag them again). `GET .../dismissed` lists the pairs with paper titles;
`POST .../undismiss {paper_ids}` removes the canonical pairs among the given ids.

## Threat review
- **Non-destructive.** Un-dismiss removes a *preference* row (the pair stops being suppressed) — it deletes
  no paper/library data. The GET exposes only already-owned local data (paper ids + titles the user already
  sees in the library).
- **SQL injection (rule #3):** the list query (two bound `papers` alias joins) and the un-dismiss delete
  (bound `paper_id_low/high ==`) are SQLAlchemy Core — no string interpolation.
- **Input validation (rule #4):** `paper_ids` is a Pydantic `list[int]` (min_length 2). Un-dismiss computes
  canonical `(low, high)` pairs and deletes them; removing a non-existent dismissal is a harmless no-op
  (idempotent). No id is trusted into a path or SQL text.
- **Route precedence:** `GET /papers/duplicates/dismissed` is registered **before**
  `GET /papers/duplicates/{job_id}` (else "dismissed" would be captured as a job id) — verified by the new
  test hitting it and by the route-surface invariant. Both sit under `duplicates.router`, included before
  `papers.router`, so they win over `/papers/{paper_id}`.
- **Egress:** none — entirely local. **Resource:** the list is bounded by the dismissed-pair count; un-dismiss
  removes ≤ C(n,2) rows for the posted ids (n tiny). **Secrets/files:** none touched. **Migration:** none.

## Negative-path checks (results)
- Dismiss a pair → `GET .../dismissed` lists it (canonical low<high, with titles) → `POST .../undismiss` →
  list empty → re-scan **re-flags** the pair (`test_dismissed_pair_can_be_listed_and_undismissed`). **PASS.**
- Un-dismiss a pair that isn't dismissed → 204, no error (idempotent no-op; same test). **PASS.**
- `paper_ids` with <2 → 422 (same test). **PASS.**
- Route surface: exactly the two new routes added (`/papers/duplicates/dismissed` GET read +
  `/papers/duplicates/undismiss` POST), and `dismissed` resolves to the list endpoint (not captured as a
  `{job_id}`) — proven by the list test hitting it + `test_api_exposes_only_read_only_get_routes`. **PASS.**
- **Live E2E** (`.local/undismiss_e2e/`): scan flags 1 group → dismiss → "Previously dismissed (1)" → expand
  → un-dismiss → section gone → reopen modal → the pair is **flagged again**, 0 console errors. **PASS.**

Full suite: **235 passed** (+1). No migration; no egress.

## Module split (rule #1, behavior-preserving)
Adding the two dedup data-access functions pushed `repository.py` to **604** (>600). The cohesive dedup-dismiss
concern (all four functions operate on `dismissed_duplicate_pairs`) was **moved verbatim** to new
`app/backend/persistence/dedup_repo.py` (63), bringing `repository.py` to **555**; the two importers
(`clustering/duplicate_detection.py`, `api/routers/duplicates.py`) were repointed. Full suite green → behavior
preserved.

**Security Audit: PASS.**
