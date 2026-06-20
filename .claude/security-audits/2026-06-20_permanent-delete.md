# Security Audit — Permanent delete (delete forever / empty Trash) (increment 65)

**Date:** 2026-06-20
**Trigger:** New API endpoints (`DELETE /papers/{id}/permanent`, `POST /papers/trash/empty`) + a new
**irreversible data-destruction path** (a net-new feature spanning backend repo + vector store + routers +
frontend). No new schema/migration (pure DML).

## What changed
Completes inc-54's soft-delete: a **trashed** paper can now be **permanently purged** — its row plus every
dependent row AND its embeddings + sqlite-vec vectors are removed. Two entry points: per-paper "delete
forever" and "empty Trash" (purge all trashed). `VectorStore.delete` added; `repository.purge_paper` /
`purge_all_trashed` orchestrate; only-from-Trash gated.

## Threat review
- **Irreversibility / blast radius (the central risk).** Purge is **destructive and not undoable**. Mitigations:
  (1) **only reachable from Trash** — `purge_paper` no-ops (returns False → 404) on a *live* (non-trashed)
  paper, so a live paper can NEVER be purged in one step; the user must first soft-delete it. (2) The UI
  double-confirms (`window.confirm`) on both "delete forever" and "empty Trash". (3) The data being purged is
  already in Trash (the user already chose to delete it).
- **Orphan-safety (the correctness risk CLAUDE.md flagged).** `embeddings.target_id` has **no FK** and the
  vector store had no delete, so a naive `DELETE FROM papers` left the paper/chunk embeddings + their vectors
  behind → `retrieval._resolve_hit`'s `.one()` raises `NoResultFound` on a surviving vector. Purge fixes this
  by deleting, **in one transaction**, the paper's `embeddings` rows (target_type `paper`→paper_id,
  `chunk`→the paper's chunk ids) AND their vectors (sqlite-vec rowid == embedding id) **before** deleting the
  paper row (whose FK CASCADE removes chunks/annotations/attachments/cluster_node_papers/dismissed_pairs/…).
  Result: no dangling vector, no orphaned embedding → no retrieval crash. Proven by a unit test that purges a
  fully-indexed paper and then runs `search_similar` without raising.
- **SQL injection (rule #3):** all deletes use SQLAlchemy Core (`delete(...).where(...)`, bound `in_(...)`).
  The sqlite-vec delete is `DELETE FROM {table} WHERE rowid = ?` with the table name from the
  constant-derived `_table_name(dimension)` (never request data) and a **bound** rowid param.
- **Input validation (rule #4):** `paper_id` is a path int; purge validates the paper is trashed before
  acting. Empty-trash takes no body and only ever touches `deleted_at IS NOT NULL` rows.
- **Resource:** empty-trash loops over the trashed set (bounded by what the user trashed); each purge is a
  handful of deletes. No unbounded fan-out.
- **API surface:** two new mutation routes, added to the route-surface invariant allowlist
  (`tests/test_health.py`). Both are 3-segment / literal-suffix paths (`/papers/{id}/permanent`,
  `/papers/trash/empty`) so neither collides with `/papers/{paper_id}`. CORS unchanged (GET-only).
- **Egress:** none — entirely local (deletes rows + local vectors). No external call.
- **Secrets / file paths:** none touched. Purge does NOT delete files on disk (managed/linked PDFs are left
  in place — deleting user files is out of scope and riskier; noted as a deferred consideration).
- **Migration:** none (pure DML; head stays `0006`).

## Negative-path checks (results)
- Purge a **live** (non-trashed) paper → `purge_paper` returns False; endpoint **404**, paper row still present
  (`test_purge_paper_refuses_a_live_paper`, `test_permanent_delete_endpoint_only_from_trash`). **PASS.**
- Purge a **trashed** paper → 204; its `papers`/`chunks`/`embeddings` rows are gone, and its vectors are gone
  from the store while a *second* (kept) paper's rows + vectors survive
  (`test_purge_paper_removes_embeddings_and_vectors_without_orphaning`). **PASS.**
- After purge, `search_similar` runs **without raising** and resolves only the surviving paper — no orphaned
  vector/embedding (same test). **PASS.**
- Re-purging an already-purged id → **404** (idempotent at the API). **PASS.**
- `POST /papers/trash/empty` with 1 of 2 papers trashed → purges 1; Trash empties; the live paper is
  untouched (`test_empty_trash_purges_all_trashed_only`). **PASS.**
- **Live E2E** (`.local/permanent_delete_e2e/`): seed 1 live + 2 trashed → Trash shows "Delete forever" +
  "Empty Trash" → delete-forever removes one → Empty Trash clears the rest → the live paper survives, **0
  console errors**. **PASS.**

Full suite: **232 passed** (+4). No new dependency; no migration; no egress.

**Security Audit: PASS.** Residual (accepted, noted as deferred): purge does not delete the PDF *file* on
disk; and trashed-but-not-yet-purged papers can still surface in new synthesis retrieval (separate
`deleted_at` retrieval-filter fix).
