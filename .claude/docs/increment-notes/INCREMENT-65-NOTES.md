# Increment 65 Notes — Permanent delete (delete forever / empty Trash)

Completes inc-54's soft-delete: Trash existed but there was no way to actually empty it. A **trashed** paper
can now be **permanently purged** — its row, every dependent row, AND its embeddings + sqlite-vec vectors —
via per-paper **Delete forever** or **Empty Trash**.

## The orphan-safety contract (the whole point)
`embeddings.target_id` has **no FK** and the vector store had **no delete method**, so a naive
`DELETE FROM papers` left the paper/chunk embeddings + their vectors behind. A surviving vector whose
embedding/chunk/paper row is gone makes `retrieval._resolve_hit`'s `.one()` raise `NoResultFound` →
retrieval crashes. So purge must, **in one transaction**, remove the embeddings + vectors **before** the
paper row:

1. Collect the paper's chunk ids.
2. Collect `embeddings` rows where `target_type='paper' AND target_id=paper_id` **or**
   `target_type='chunk' AND target_id IN (chunk ids)`.
3. `vector_store.delete(...)` each (sqlite-vec rowid == embedding id), then `DELETE FROM embeddings` those.
4. `DELETE FROM papers WHERE id=?` — FK CASCADE removes chunks, annotations, attachments,
   cluster_node_papers, dismissed_duplicate_pairs, external ids, notes, tags, collection_papers,
   open_science_signals. (citation_mappings/evidence_quotes `chunk_id` are SET NULL → honest null-coord
   degradation for any old summary that cited the paper; summaries themselves aren't paper-FK'd, so they're
   left intact.)

## Implemented
- **`embeddings/vector_store.py`** — `VectorStore.delete(conn, *, embedding_id, dimension)` on the Protocol;
  `SQLiteVecVectorStore` (`DELETE FROM {table} WHERE rowid=?`, bound param, constant table name) and
  `InMemoryVectorStore` (`vectors.pop`).
- **`persistence/repository.py`** — `purge_paper(conn, paper_id, *, vector_store) -> bool` (**trashed-only**:
  returns False for a missing or *live* paper, so a live paper can never be purged in one step);
  `purge_all_trashed(conn, *, vector_store) -> int`; `_purge_paper_embeddings` helper. `VectorStore` typed
  via `TYPE_CHECKING` to keep persistence decoupled from the embeddings package at import time.
- **`api/routers/papers.py`** — `DELETE /papers/{paper_id}/permanent` (404 if not in Trash) +
  `POST /papers/trash/empty` (`{purged: N}`); `_vector_store(app)` helper (mirror of summaries.py). Both are
  3-segment / literal-suffix paths → no collision with `/papers/{paper_id}`.
- **Frontend** (`10_pdf_layer.jsx`, `40_app.jsx`, `styles.css`) — per-row **Delete forever** (danger) +
  **Empty Trash** (header, danger) in the Trash view, each behind a `window.confirm`. CSS reuses the
  established `.danger` modifier recipe on `.paper-restore` / `.trash-toggle` (token `--danger`/`--danger-line`,
  per DESIGN.md §2 + §4 #4 — no new hex). Rebuilt `callosum-app.html`.

**No migration** (pure DML; head stays `0006`). **No egress** (entirely local). **No new dependency.**

## Verification
- **pytest 232** (+4): purge removes embeddings rows + vectors and `search_similar` doesn't orphan-crash
  (a kept paper survives); a live paper is refused; the endpoint is trash-only (live→404, trashed→204,
  re-purge→404); empty-trash purges only trashed and leaves live papers. Route-surface invariant +2 routes.
- **Live E2E** (`.local/permanent_delete_e2e/`): seed 1 live + 2 trashed → Delete forever removes one →
  Empty Trash clears the rest → the live paper survives, 0 console errors; screenshot `result.png`.
- Audit `.claude/security-audits/2026-06-20_permanent-delete.md` — **PASS**.

## Manual verification script
1. Start the app; import/seed a few papers. Trash one or two (check boxes → **delete**).
2. Click **Trash**. Each row shows **Restore** and **Delete forever**; the header shows **Empty Trash**.
3. **Delete forever** on a paper → confirm → it vanishes from Trash and does not return on reload.
4. **Empty Trash** → confirm → "Trash is empty."; **← Library** still shows the live papers.

## Deferred (noted)
- Purge leaves the PDF **file on disk** (managed/linked) in place — deleting user files is riskier and out of
  scope here.
- Trashed-but-not-yet-purged papers can still surface in **new synthesis retrieval** (`_candidate_embedding_ids`
  doesn't filter `deleted_at`) — a separate, lower-risk retrieval-filter fix. (A *purged* paper is fully gone.)
- An "are you sure?" typed-confirmation (vs `window.confirm`) for Empty Trash, if desired later.
