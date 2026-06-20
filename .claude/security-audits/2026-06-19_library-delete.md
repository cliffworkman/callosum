# Security audit — Library delete (soft) + Trash/Restore (increment 54)

**Date:** 2026-06-19
**Feature:** Soft-delete papers (multi-select + bulk) with a Trash view + Restore. New
`DELETE /papers/{id}` (soft), `POST /papers/{id}/restore`, `GET /papers?deleted=true`; migration 0004
(`papers.deleted_at`). Files: `schema.py`, `repository.py`, `axis_suggestion.py`, `routers/papers.py`,
`alembic/versions/0004_paper_soft_delete.py`, frontend `40_app.jsx` + `10_pdf_layer.jsx`.

**Audit triggers:** (1) new API endpoints; a schema migration; (5) 3+ files. No new external fetch,
ingestion, auth, or dependency.

## Threat review
- **Destructiveness — the headline.** Delete is **soft + reversible**: it only stamps
  `papers.deleted_at`; **no rows are removed and nothing is purged**, so there is no data loss and
  nothing orphans. A trashed paper is hidden from the library listing, axis clusters, and axis
  clustering (suggest), and Restore clears the stamp. This was a deliberate choice over hard-delete,
  which today would **orphan** the paper's `embeddings` rows + sqlite-vec vectors (no FK on
  `embeddings.target_id`, no vector-store delete method) and **crash** similarity search
  (`retrieval._resolve_hit` `.one()`s the missing paper). True permanent-delete / empty-trash — the
  only path with real destructive + orphaning risk — is **explicitly deferred** to a later increment
  that must add a `VectorStore.delete` + a `purge_paper` with vector cleanup.
- **Input validation.** Endpoints take a path `int` id only; `?deleted` is a bool. No free-text, no
  client-supplied SQL. `soft_delete_paper`/`restore_paper` are guarded UPDATEs (`WHERE id AND
  deleted_at IS [NOT] NULL`) → a missing/already-in-that-state paper returns rowcount 0 → **404**
  (no silent no-op, no 500).
- **SQL.** All reads/writes via SQLAlchemy Core bound parameters; the soft-delete filter is a
  parameter-free `deleted_at IS [NOT] NULL` predicate.
- **Migration.** Additive, idempotent nullable column (mirrors 0002/0003); single linear head 0003→0004;
  auto-applied on startup; a fresh DB already has the column from `create_all` (no-op).
- **Data egress.** None — entirely local SQLite. No Gemini/Crossref/network path touched.
- **Access scope.** A soft-deleted paper's `GET /papers/{id}` / `/pdf` / `/chunks` still resolve by id
  (unchanged `get_paper`) — needed for Restore + harmless (the paper is unreachable except via Trash);
  it is removed from every *listing*. Known limitation (noted, deferred): a trashed paper's chunks can
  still surface in *new synthesis retrieval* until `retrieval` filters `deleted_at`.
- **Resource use.** Bulk delete = one soft-UPDATE per selected id (client loop, bounded by the page).
- **Frontend.** Bulk delete is `window.confirm`-gated; the checkbox `stopPropagation`s; the three row
  modes (normal / focus / trash) are mutually exclusive so affordances don't collide.

## Negative-path checks (run)
- `pytest` (183): soft-delete hides from library + lists in Trash; restore returns it; delete-already-
  trashed / restore-a-live-paper / unknown-id all → 404; a trashed paper is excluded from axis clusters.
  Route-surface invariant updated.
- Live E2E (`.local/library_delete_e2e/`, no network): select 2 → bulk delete → library shows 1 →
  Trash lists 2 → Restore one → library shows 2; **0 console errors**.

## Result
**Security Audit: PASS.** Reversible soft-delete with no data loss or orphaning; guarded int-only inputs;
parameterised SQL; additive idempotent migration; no egress/dependency. The genuinely destructive
permanent-delete (with its vector-cleanup requirement) is deferred, not shipped.
