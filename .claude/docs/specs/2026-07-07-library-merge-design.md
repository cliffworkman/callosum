# Library Merge + Reversible Undo — Design Spec

**Backlog:** #17 (manual library merge) + #16 (paired undo / soft-delete safety net)
**Date:** 2026-07-07
**Status:** design approved (decisions locked below); pending spec review → writing-plans.

---

## Goal

Let the librarian **manually merge two library entries into one canonical record** — re-pointing every
attachment, chunk, annotation, note, tag, axis membership, finding, identifier, and derived signal from the
merged-away paper onto the survivor — and make that merge **fully reversible** via a snapshot-backed
un-merge. Merge is the app's single most destructive operation; reversibility (#16) is its safety net and is
built in the same increment, not bolted on later.

Deliberately **NOT gated behind duplicate detection.** Auto-dedup misses true duplicates (a preprint vs. its
published version; a re-import with a different DOI; an EndNote/Zotero migration that double-adds). Zotero and
Mendeley both let the user merge on demand; callosum matches that. The dedup review screen *may* offer a
"Merge" shortcut later, but merge itself stands alone.

## Locked decisions (from brainstorming)

1. **Safety model — fully reversible (un-merge).** A `merge_operations` record snapshots the exact pre-merge
   state (survivor metadata + every re-point + every dropped dedup + the merged-away paper) so **Un-merge**
   restores both records exactly. Serves charter value **A4** — *the user owns every irreversible act; their
   data and corrections are never silently overwritten.* Merge stops being irreversible.
2. **Canonical/metadata — field-by-field merge (Zotero-style).** The survivor `A` is the base; for each
   *conflicting* metadata field the user picks A's or B's value (or edits inline). Agreeing fields auto-fill.
   Associations union regardless (union loses nothing).
3. **Scope — 2-paper MVP.** Merge exactly two → one. Tightest blast radius for the most destructive op; the
   field picker is a simple A-vs-B choice. **N-paper (select 2+) is an explicit fast-follow**, not built now.

## Non-goals (this increment)

- N-paper merge (≥3 in one operation) — fast-follow once the reversible foundation is proven.
- A "smart" merge that auto-resolves metadata — the human resolves conflicts; the AI does not touch this.
- Re-running extraction/embedding/methods after merge — the survivor keeps its own derived data; unioned
  attachments do **not** auto-reprocess (see *Derived data* below). Re-derivation stays a manual/existing path.
- Merging across the dedup screen — separate, later.

---

## The re-point surface (load-bearing correctness)

Every table that references a paper must be handled, or a merge orphans data (or un-merge can't restore it).
The surface, grouped by **policy**. `A` = survivor/canonical, `B` = merged-away. Table/column names come from
a hardcoded allowlist in the merge repo — **never** from request data (rule #3).

### Bucket 1 — Owned associations (re-point every B row → A; union)
One paper genuinely owns many of these; unioning loses nothing.

| Table | Key ref | Notes |
|---|---|---|
| `attachments` | `paper_id` FK | PDFs. Files on disk untouched; only `paper_id` flips. A ends with both papers' PDFs. |
| `chunks` | `paper_id` FK | Re-point. **Embeddings follow automatically** — `embeddings.target_id → chunks.id` (target_type `"chunk"`); the chunk row's id is unchanged, so every embedding + the sqlite-vec index stay valid with **zero embedding touch**. |
| `annotations` | `paper_id` FK | Union. |
| `notes` | `paper_id` FK | Union. |
| `paper_external_identifiers` | `paper_id` FK | Union, **dedup on identical `(identifier_type, value)`** (drop B's duplicate, recorded). |
| `wanted_items` | `paper_id` FK (nullable) | Re-point B's want → A; dedup if A already has an open want. |
| `ma_rows` | `paper_id` **plain Integer, no FK** | Meta-analysis extraction rows. Re-point B→A (a row links at most one paper; no dedup). |

### Bucket 2 — Set-membership (re-point with dedup on the unique/PK key)
A paper can appear **once**; on key collision, **drop B's row** (recorded for restore) instead of re-pointing.

| Table | Unique key | Dedup / conflict policy |
|---|---|---|
| `paper_tags` | PK `(paper_id, tag_id)` | Union tags; drop B's row where A already has that tag. |
| `suppressed_paper_tags` | PK `(paper_id, tag_id)` | Union suppressions. |
| `collection_papers` | PK `(collection_id, paper_id)` | Union memberships (axes/collections). Preserve a manual/curated flag if either side had one. |
| `reading_queue` | UNIQUE `paper_id` | If both queued, keep A's row (lower `position`), drop B's. |
| `my_publication_decisions` | UNIQUE `paper_id` | If both decided, **"confirmed" wins** over "rejected"; else keep A's. |
| `dismissed_duplicate_pairs` | `(paper_id_low, paper_id_high)`, CHECK low<high | **Special (two paper columns):** the `(A,B)` pair itself is dropped (they're now one paper). Other pairs `(B,X)` → re-canonicalize to `(min(A,X), max(A,X))`; drop if that collides with an existing pair or would form `(A,A)`. |

### Bucket 3 — Findings & review state (re-point + dedup, **preserve the human's review**)
Derived *candidates* that carry user review decisions — treat as user data, not disposable.

| Table | Unique key | Policy |
|---|---|---|
| `paper_findings` | UNIQUE `(paper_id, source, content_key)` | Re-point B→A; on collision keep the row that **carries a review decision** (`review_state` non-NULL wins; else keep A's). Never silently discard a reviewed finding. |

### Bucket 4 — Derived / re-derivable (snapshot B's rows, **drop them**, leave A's; regenerate on demand)
Pure caches keyed to a paper's content. A keeps its own; B's are snapshotted then dropped (so un-merge
restores them). Because A now also holds B's attachments, **A's signals may be stale** — this is honest and
re-derivable; the merge does not silently recompute. Surfaced to the user (see UX).

| Table | Key | Policy |
|---|---|---|
| `open_science_signals` | UNIQUE `(paper_id, signal_type, source)` | Snapshot B's, drop; A's stand; re-run methods to refresh. |
| `paper_citation_counts` | PK `paper_id` | Snapshot B's, drop; A's cached count stands (re-fetch to refresh). |
| `cluster_node_papers` | PK `(cluster_node_id, paper_id)` | Snapshot B's, drop. Clusters are regenerated wholesale on the next cluster run anyway. |
| `critical_review_candidates` | FK `paper_id` (backlog #12, in flight) | Snapshot B's, drop (scrutiny candidates are re-derivable per paper). *(Handled if/when #12 lands; listed so the allowlist stays complete.)* |

### Bucket 5 — JSON-scoped references (surgical id rewrite B→A; old JSON recorded)
References that live inside a JSON blob, not a column. Rewrite the id; record the pre-merge JSON for restore.

| Location | Shape | Policy |
|---|---|---|
| `summaries.scope_ref_json` | paper-scoped synthesis references a paper id | For a `scope_type="paper"` summary referencing B → rewrite to A. If A already has one, keep both (the synthesis list tolerates multiple; recorded either way). |
| `profile.starred_paper_ids` | JSON array of paper ids | Replace B with A (dedup if A already starred). |
| `profile.research_domains[].paper_ids` | nested JSON arrays | Replace B with A within each domain, dedup. |
| `agent_writes.target_paper_id` | plain Integer, no FK (audit log) | Re-point B→A so the "AI agent activity" revert log stays coherent. |

> `profile.dismissed_work_dois` / `dismissed_gap_works` are keyed by **DOI/OpenAlex id**, not paper id →
> unaffected by merge.

**Completeness check is a test, not prose.** A unit test enumerates every table with a `paper_id`-shaped
reference (via SQLAlchemy metadata reflection) and asserts each appears in exactly one bucket of the merge
allowlist — so a *future* table that references papers fails the test until it's classified. This is the
guard against the surface silently drifting (the same failure mode the line-budget gate fixed for rule #1).

---

## Data model (new)

Two additive, guarded migrations (the 0034/0035 idiom — `inspector.get_table_names()` guard, short CHECK
names so `env.py`'s naming convention expands them once, `downgrade(): return`).

### `merge_operations` (the reversible undo record)
```
id                 INTEGER PK
canonical_paper_id INTEGER FK papers.id ON DELETE CASCADE   -- the survivor A
merged_paper_id    INTEGER FK papers.id ON DELETE CASCADE   -- the merged-away B
snapshot_json      TEXT NOT NULL      -- the full reversal payload (below)
status             TEXT NOT NULL DEFAULT 'active'  -- active | undone   (CHECK: merge_status_valid)
created_at         DATETIME NOT NULL DEFAULT now
undone_at          DATETIME
INDEX ix_merge_operations_canonical (canonical_paper_id)
```

`snapshot_json` payload (everything un-merge needs, self-contained):
```jsonc
{
  "canonical_metadata_before": { /* A's papers row + csl_json before the field-picker applied */ },
  "merged_paper_row": { /* B's full papers row — belt-and-suspenders; B is soft-hidden, not deleted */ },
  "repoints":  [ {"table": "chunks", "id": 42, "from_paper_id": <B>}, ... ],   // bucket 1/2 rows moved B→A
  "drops":     [ {"table": "paper_tags", "row": { ...full row... }}, ... ],    // bucket 2/3 dedup drops + bucket 4 derived drops
  "json_edits":[ {"table": "profile", "column": "starred_paper_ids", "id": 1, "before": [...] }, ... ]
}
```

### `papers.merged_into` (new nullable self-FK column)
```
merged_into INTEGER FK papers.id  NULL default    -- NULL = not merged; set = merged away into that canonical
```
**The merged-away paper B is marked BOTH `deleted_at = now` AND `merged_into = A`.** This is the
low-blast-radius design: the codebase already filters `papers.deleted_at IS NULL` in **~10 live-paper
queries** (library list, search, counts, cluster/axis membership joins, reading-queue join, wanted, batch
producers…). Re-using `deleted_at` hides B from **every** one of them for free — no per-query change. The new
`merged_into` column is the *marker* that distinguishes a merged-away paper from a normally-trashed one, and it
needs to be honored in exactly **three** places:

1. **Trash list** (`repository.py:262`, the `only_deleted` branch) — add `AND merged_into IS NULL` so a
   merged-away paper never appears in Trash as a naively-restorable row (restoring it must route through
   *un-merge*, not a plain `restore_paper`, or associations stay re-pointed).
2. **`purge_paper`** (`paper_lifecycle_repo.py`) — guard: refuse to purge a paper whose `merged_into` is set
   (purging B would destroy the `merge_operations` undo record's target and break reversibility). Un-merge
   first.
3. **`purge_all_trashed`** — its id-select adds `AND merged_into IS NULL` so "Empty Trash" skips merged-away
   papers (belt-and-suspenders with the `purge_paper` guard).

- The survivor's Detail pane reads "merged from …" via `merge_operations WHERE canonical=A AND status='active'`.
- Un-merge clears **both** `deleted_at` and `merged_into` on B (fully live again).

> **Why re-use `deleted_at` instead of adding `merged_into IS NULL` to all ~10 live queries:** the soft-delete
> filter is already threaded through every surface that must hide B; adding a second predicate to each is a
> large, error-prone blast radius where *missing one* leaks a merged-away paper into a view. Setting
> `deleted_at` too gets that hiding for free; `merged_into` then only guards the 3 Trash/purge spots. A
> merged-away paper is, honestly, "removed from the live library" — the same state trash represents — just
> flagged with *why* and *how to reverse it*.

---

## Merge — the transaction (all-or-nothing)

`merge_papers(conn, *, canonical_id, merged_id, resolved_metadata) -> merge_operation_id`, wrapped in one
transaction so any failure rolls back with zero partial state:

1. Guard: A ≠ B; both exist, both live (`merged_into IS NULL`, not trashed).
2. Snapshot A's current metadata (`canonical_metadata_before`) and B's full row (`merged_paper_row`).
3. Apply `resolved_metadata` to A via the existing edit path (`metadata/paper_edits.py` + the CSL patch
   validators) — same field model + validation as the Detail editor, so merge can't write metadata the editor
   couldn't (consistency + reuse).
4. Walk the allowlist buckets 1→5, recording every `repoint` / `drop` / `json_edit` into the snapshot as it
   goes.
5. Set `B.deleted_at = now` **and** `B.merged_into = A` (soft-hidden from every live query + flagged as merged).
6. Insert the `merge_operations` row (status `active`, snapshot attached).
7. Return the op id.

## Un-merge — the reversal (all-or-nothing)

`unmerge(conn, *, merge_operation_id) -> None`, one transaction, reads the snapshot and reverses in order:

1. Guard: op exists, status `active`.
2. Restore A's `canonical_metadata_before`.
3. Move every `repoint` row back to B (by recorded row id).
4. Re-insert every `drop` row (to B).
5. Restore every `json_edit` (`before` value).
6. Clear `B.deleted_at = NULL` **and** `B.merged_into = NULL` (B fully live again).
7. Op status → `undone`, `undone_at = now`.

**Post-merge additions stay put.** Un-merge reverses only what the merge recorded — anything added to A
*after* the merge (a new annotation, a new tag) remains on A. Editing A's metadata after merge, then
un-merging, restores A's *pre-merge* metadata (the user is undoing the whole merge); this is stated in the
un-merge confirm.

---

## API surface (new — QA routes required, rule #10)

| Method + path | Purpose |
|---|---|
| `GET /papers/{a}/merge-preview/{b}` | Returns per-field `{field, value_a, value_b, agree}` for the editable metadata set + association counts `{attachments, chunks, annotations, notes, tags, axes, findings, identifiers}` + conflict warnings `[{kind, detail}]` (both queued; both My-Pubs-decided; stale-signals note). No mutation. |
| `POST /papers/merge` | Body `{canonical_id, merged_id, resolved_metadata:{field:value,...}}` → `{merge_operation_id, canonical_id}`. |
| `POST /merge/{op_id}/undo` | Reverses; `{restored_paper_id}`. |
| `GET /papers/{id}/merge-origin` | For the Detail affordance: `{merge_operation_id, merged_from_title, merged_at}` or `null`. |

All under the standard access-control/read-only middleware. Merge + undo are mutating → blocked by
`CALLOSUM_READ_ONLY` (403) and the access token when Remote access is on, like every write.

## Backend module layout (rule #1 — under 600 lines each)

- `app/backend/persistence/schema_merge.py` — the `merge_operations` table (+ `MERGE_STATUSES`) on the shared
  `schema_base` metadata; re-exported from `schema.py` (the schema_findings pattern). The `papers.merged_into`
  column is added to `papers` in `schema.py` directly (one column).
- `app/backend/persistence/merge_repo.py` — the allowlist (the bucket→table map), `merge_papers`, `unmerge`,
  `merge_preview`, `merge_origin`, and the metadata-reflection completeness helper. This is the heart; keep it
  focused. If it approaches the cap, split the allowlist walk from the CRUD.
- `app/backend/api/routers/merge.py` — the four endpoints + pydantic request/response models (a sibling
  router mounted in `app.py`, the paper_enrich pattern). If models push it near the cap, peel a
  `merge_models.py` leaf (the axes_models pattern).
- `alembic/versions/0036_merge_operations.py`, `0037_papers_merged_into.py` — additive/guarded.

## Frontend (new controls — QA frontend surfaces + Experience pass, rules #10/#11)

- **Entry:** a **Merge** action on the library multi-select (enabled when exactly 2 are selected in the MVP).
- **Merge dialog** (new chunk, e.g. `js/NN_merge.jsx`): loads `merge-preview`; renders the field-by-field
  picker (radio A/B + inline edit for conflicting fields; agreeing fields shown read-only/auto), the union
  preview line ("Combines N annotations · M tags · K axes · P PDFs onto the survivor"), any conflict warnings
  (incl. "the survivor's open-science signals won't auto-recompute — re-run Methods to refresh"), and a hard
  **Merge B into A** confirm.
- **Undo affordances:** (a) a **toast** on success — "Merged → [title]. Undo" (calls `/merge/{op}/undo`);
  (b) a **persistent** line in the survivor's Detail pane — "Merged from *[title]* on [date] — Un-merge"
  (reads `merge-origin`), so reversibility isn't just a toast window.

Rebuild via `python tools/build_frontend.py` after the chunk lands; the 600-cap is machine-checked.

---

## Gates

- **Principles (rule #9) — value A4.** The whole design *is* the aligned alternative: merge (irreversible,
  data-destroying) is made reversible + the field-picker guarantees no user correction is silently
  overwritten. No AI, no signal/verdict, no fact/candidate surface, no egress change → the charter's evaluative
  triggers don't fire; the load-bearing commitment here is data-safety/A4.
- **Security & data-safety audit (destructive op → audit gate).** Open `.claude/security-audits/
  2026-07-NN_library-merge.md`. Threat review: single-transaction atomicity (no partial merge); un-merge
  exactness (round-trip equality test is the proof); table/column allowlist is constant, never request-derived
  (rule #3); no new external fetch, no new file write (attachments only re-point `paper_id`; files stay on
  disk); parameterized SQL; the `merged_into` filter can't leak merged-away papers into any surface. Negative
  paths: merge A with itself (rejected); merge a trashed/already-merged paper (rejected); un-merge an
  already-undone op (rejected); merge across a mid-transaction failure (rolls back).
- **QA (rule #10):** four new API surfaces (hard-gated) + the merge dialog / undo controls (frontend
  checklist) → a QA route in the same increment asserting the honesty invariants still hold (the merged
  record's citations still open the right PDF/page — attachments + chunks re-pointed correctly).
- **Experience pass (rule #11):** dispatch the **corpus-builder** persona post-build — someone migrating a
  messy library (the EndNote/Zotero importer who now has visible duplicates) merging a preprint into its
  published version and confirming un-merge gets them back. This is the feature's headline user.

## Testing strategy

- **Repo round-trip (the core proof):** seed a paper A + paper B with rows in **every** bucketed table; merge;
  assert (a) A owns the union, (b) set-membership deduped correctly, (c) B is `merged_into=A` and gone from the
  live list, (d) derived B rows dropped; then **un-merge and assert byte-for-byte restoration** of both papers
  and every association (the reversibility guarantee).
- **Bucket edge cases:** dismissed-pair `(A,B)` dropped + `(B,X)` re-canonicalized; both-queued dedup keeps
  A; My-Pubs "confirmed" beats "rejected"; `paper_findings` review-state preserved on collision; JSON scope
  rewrite (starred ids, research_domains, summary scope, agent_writes).
- **Completeness guard:** the metadata-reflection test that fails if a `paper_id`-referencing table isn't in
  the allowlist.
- **API:** preview shape + conflict warnings; merge happy path; undo restores; negative paths (self-merge,
  merged/trashed operands, double-undo) return honest 4xx; read-only mode → 403 on merge/undo.
- **Atomicity:** inject a failure mid-merge (e.g., a forced integrity error) → assert full rollback, no
  `merge_operations` row, both papers untouched.
- `pytest` green is the gate; a manual verification script (start app, import a dup, merge, open a citation
  from the survivor to confirm the re-pointed PDF/page still resolves, un-merge, confirm both back).

## Open items / fast-follows (recorded, not built)

- **N-paper merge** (select ≥2) — extends the field picker to an N-way radio and the snapshot to N
  merged-away rows; the reversible model already generalizes.
- **Merge from the dedup review screen** — a "Merge these" shortcut that pre-loads the preview.
- **Auto-refresh derived signals** after merge — currently manual/honest-stale; a later "recompute now"
  affordance could re-run Methods on the survivor.
