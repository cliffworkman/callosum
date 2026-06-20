# Security audit — Duplicate detection (increment 56)

**Date:** 2026-06-19
**Feature:** A library duplicate scan. New `POST /papers/duplicates` (async job) + `GET
/papers/duplicates/{job_id}` return likely-duplicate groups (layered identifier → title+author+year →
embedding) for review; flag-only. Files: `app/backend/clustering/duplicate_detection.py` (new),
`app/backend/api/routers/papers.py`, `app/backend/api/app.py`, frontend `19_duplicates.jsx` +
`10_pdf_layer.jsx` + `40_app.jsx`.

**Audit triggers:** (1) new API endpoints; (5) a feature spanning 3+ files. No new external fetch, no
ingestion, no migration, no new dependency (numpy already present).

## Threat review
- **Destructiveness.** Detection is **read-only + ephemeral** — it computes groups in memory and persists
  nothing, and it **never auto-deletes or auto-merges** (the backlog invariant). The only mutating action
  is the user clicking "delete" in the review modal, which calls the existing **soft-delete**
  (`DELETE /papers/{id}` → Trash, reversible, audited inc-54). Merge stays deferred.
- **Input validation.** `POST /papers/duplicates` takes no body; the poll takes a job id (dict lookup;
  unknown → 404). No client free-text reaches the scan — it operates only on the library's own rows.
- **SQL.** Reads via SQLAlchemy Core `select()` (live papers only — `deleted_at IS NULL`); no writes.
- **Data egress (invariant #3).** **Entirely local** — the embedding layer uses the local model
  in-memory; **no Gemini / network call**. Nothing leaves the machine.
- **Resource use.** The scan runs in a background job (mirrors `/axes/suggest`). The embedding layer is
  O(N²) (`V @ V.T`) but **guarded** (`MAX_EMBED_PAPERS = 3000` → skip above that); identifier/title layers
  are hash-grouped (near-linear). Confidence/threshold constants (EMBEDDING_SIM 0.92) keep the fuzzy layer
  from flagging same-topic papers (the backlog's concern).
- **Route safety.** `/papers/duplicates` + `/papers/duplicates/{job_id}` are registered before
  `/papers/{paper_id}`; the literal "duplicates" segment + distinct segment counts mean no shadowing of the
  int-id paper routes (verified by the route-surface test + the live E2E resolving correctly).
- **Output handling.** Group paper refs (id/title/authors/year/venue) render as React text (auto-escaped).

## Negative-path checks (run)
- `pytest` (199): unit tests for each layer (shared-PMID, title+author+year, embedding ≥0.92), union-find
  merge, no-dupes→empty, trashed-excluded; endpoint flags a shared-identifier pair + empty when none.
  Route-surface invariant updated.
- Live E2E (`.local/duplicates_e2e/`, fake model, **no network**): scan → one group → delete the redundant
  copy → group resolves + the paper leaves the library (Trash); **0 console errors**.

## Result
**Security Audit: PASS.** Read-only, ephemeral, entirely local scan that only flags; the sole mutation is
the user-driven, reversible soft-delete; bounded compute; no egress, no new dependency.
