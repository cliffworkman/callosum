# Increment 54 Notes — Library delete (soft) + multi-select + Trash / Restore (backlog D)

Closed the biggest CRUD gap: there was **no way to delete a paper at all**. Delete is **soft + reversible**
(a Trash you can restore from), chosen because hard-delete is unsafe today and because the user wanted undo.

## Why soft (the decisive finding)
A hard `DELETE FROM papers` would **orphan** the paper's `embeddings` rows + sqlite-vec vectors —
`embeddings.target_id` has no FK and the vector store has no delete method — and an orphaned
paper-embedding **crashes** similarity search (`retrieval._resolve_hit` `.one()`s the now-missing paper).
Soft-delete keeps every row, so nothing orphans and it's fully restorable. Permanent delete / empty-trash
(which needs proper vector cleanup) is **deferred**.

## Implemented
### Backend
- **Migration `0004_paper_soft_delete`** (head 0003→0004): additive, idempotent nullable `papers.deleted_at`
  (mirrors 0003; auto-applied on startup). `schema.py` gains the column.
- **`repository.py`:** `list_papers(..., only_deleted=False)` filters `deleted_at IS NULL` (default) /
  `IS NOT NULL` (Trash); `get_papers_for_cluster_node` excludes trashed papers; `soft_delete_paper`
  (guarded UPDATE → rowcount) + `restore_paper`. `axis_suggestion.suggest_axes` excludes trashed papers.
- **`routers/papers.py`:** `GET /papers?deleted=true` (Trash listing); **`DELETE /papers/{id}`** → soft,
  404 if missing/already-trashed, else 204; **`POST /papers/{id}/restore`** → 404 if not trashed, else
  200 + detail. `get_paper` left unfiltered (Restore + detail resolve by id).

### Frontend (mirrors the inc-43 axis bulk pattern)
- **`40_app.jsx`:** `selectedLibraryIds` (Set) + `trashView` + `libRefresh`; the `/papers` fetch appends
  `&deleted=1` in Trash; handlers `toggleLibrarySelect` / `clearLibrarySelect` / `bulkDeletePapers`
  (`window.confirm` → `Promise.all(apiDelete)` → reload + clear + drop the Detail selection if trashed) /
  `restorePaper` / `toggleTrash`.
- **`10_pdf_layer.jsx` `PaperList`:** a **Trash ⇄ Library** toggle in the pane head; a **bulk-action bar**
  (reuses `.axis-bulk-bar`) when rows are selected; a per-row **checkbox** (`.paper-select`,
  `stopPropagation`) in library view; a per-row **Restore** button in Trash. The three row modes
  (normal / focus-mode / trash) are mutually exclusive so affordances never collide.
- CSS: `.lib-head`, `.trash-toggle`, `.paper-select` (absolute top-right), `.paper-restore` (+ `.paper`
  `position: relative`); reuses `.axis-bulk-bar`/`.axis-link`/`.axis-danger`.

## Key technical detail
`deleted_at` is the single source of truth: a timestamp = trashed (hidden from library + axes +
clustering, kept + restorable), NULL = live. Hidden everywhere it's *listed*, but `get_paper` still
resolves by id so Restore works. Nothing is ever removed, so there is no orphaning and the operation is
totally reversible.

## Manual verification script
1. Rebuild + restart uvicorn + hard-reload.
2. In the library, tick a couple of checkboxes → a bulk bar appears → **delete** (confirm) → they vanish
   and leave their axes. Click **Trash** → they're listed → **Restore** one → it returns to the library.

## Verification
- **pytest: 183** (+4): soft-delete hides + lists in Trash; restore; 404 paths; axis-cluster exclusion.
  Route-surface invariant + the migration-head tests updated to 0004.
- **Live E2E** (`.local/library_delete_e2e/`, no network): select 2 → bulk delete → 1 left → Trash lists 2
  → Restore one → library shows 2; **0 console errors**. Screenshot captured.
- **Audit:** `.claude/security-audits/2026-06-19_library-delete.md` → PASS.
- `10_pdf_layer.jsx` 237, `40_app.jsx` 241, `papers.py` 428, `repository.py` 429 — all < 600.

## Backlog
Done: **D** (library multi-select + soft-delete + Trash/Restore). **Deferred (noted):** permanent delete /
empty-trash (needs `VectorStore.delete` + `purge_paper` vector cleanup); excluding trashed papers from new
synthesis *retrieval*. Next: dedup (E); synthesis split (F); library merge (last); terms-as-first-class;
DESIGN.md `.btn-*` DRY.
