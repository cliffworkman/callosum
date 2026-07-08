# Increment 265 — Reversible un-merge (#16): the undo net for the inc-161 paper merge

## Context / course-correction

Backlog #17 ("library merge") was picked up as if net-new. Mid-build, an API-endpoint collision revealed that
**merge already shipped in inc 161** (`metadata/paper_merge.py` — N-way, field-by-field, non-destructive,
husks→Trash; `POST /papers/merge`; a frontend merge modal). The backlog even records it: *"non-destructive paper
merge (161, part of #17)."* The genuine open gap was **#16** — *reversibility*: the inc-161 merge moved
associations onto the survivor and trashed the husks, so restoring a husk from Trash gave an **empty shell**.
The user chose to reframe to #16. The parallel merge that had been built (`merge_repo` + `merge_allowlist`) was
**deleted** as redundant; the reversal machinery was retargeted to reverse the *real* inc-161 merge.

## Implemented

- **Schema** (`schema_merge.py`, migrations `0035`/`0036`): `merge_operations` (canonical/merged ids, `snapshot_json`,
  `status` active|undone, timestamps) + a `papers.merged_into` self-FK.
- **`paper_merge.merge_papers`** now records a self-contained reversal snapshot as it mutates, writes a
  `merge_operations` row, and marks each husk `merged_into`. Returns `MergeResult.merge_operation_id`.
- **`paper_unmerge.py`** (NEW): `unmerge(merge_operation_id)` replays the snapshot; `merge_origin(paper_id)` powers
  the Details affordance.
- **Endpoints** (`duplicates.py`): `POST /merge/{id}/undo`, `GET /papers/{id}/merge-origin`, and the undo handle
  on the merge response.
- **Lifecycle guards** (`repository.py`, `paper_lifecycle_repo.py`): the Trash list excludes merged-away papers;
  `purge_paper` refuses to purge either side of an active merge (never orphan the undo record); `purge_all_trashed`
  skips them.
- **Frontend** (`25_detail.jsx`, `styles.css`): the survivor's Details shows a "Merged from … — Un-merge" indigo
  (provenance) banner via `merge-origin`; Un-merge posts the undo and refreshes. Since merge navigates to the
  survivor, this is the immediate *and* persistent undo path — no separate toast system needed. Gated on `!readOnly`.

## Key technical detail

- **Union links are reversed by a before/after diff, not per-insert instrumentation.** The merge unions
  tags/collections/manual-axes onto the survivor (OR IGNORE); the snapshot records only the links the merge
  *added* = `survivor's membership set after − before`. Un-merge deletes exactly those (the husks kept their own
  copies, so they're untouched).
- **Un-merge is all UPDATE/DELETE — no row re-insertion.** That sidesteps the two hazards the (deleted) parallel
  version hit: SQLite DateTime rejecting a JSON-stringified timestamp on re-insert, and ROWID reuse colliding a
  re-insert. The survivor's record is restored **before** a husk reclaims a freed UNIQUE id (e.g. a DOI), so the
  UNIQUE constraint can't trip.
- **Merged-away is a distinct state, not Trash.** A husk gets **both** `deleted_at` (so the ~10 existing
  live-paper queries hide it for free) **and** `merged_into` (the marker that excludes it from the plain Trash
  list + blocks purge). Reachable only via Un-merge — a naive Trash-restore would give an empty shell.
- **N-way:** `merge_operations.merged_paper_id` stores the first husk (representative); `snapshot["husks"]` is the
  full list, which `merge_origin` reads for the titles.

## Behavior change (intended)

Merged-away copies no longer appear in the plain Trash list (inc-161 put them there). Updated the inc-161 endpoint
test to assert merged-away (not in live, not in Trash) + the undo handle.

## Manual verification script (frontend — run in a browser; no browser automation in the repo)

1. Start a scratch instance (a throwaway DB, a port other than the running :8888). Import/create two records of the
   same paper (e.g. a preprint + published version) with different DOIs + each with a PDF + a tag.
2. Select both → **merge** → pick the survivor, resolve fields, confirm. Confirm you land on the survivor and it
   holds **both PDFs** + both tags, and the merged-away copy is gone from the library **and** from Trash.
3. On the survivor's **Details**, confirm the indigo **"Merged from … — Un-merge"** banner names the merged-away
   copy. Open a citation/PDF from the survivor and confirm it still resolves (coordinate honesty intact after the
   re-point).
4. Click **Un-merge**. Confirm both records return to the library with their own PDFs/tags, the survivor's DOI +
   "Merged from…" note revert, and the banner disappears. (Backend flow already covered by
   `test_unmerge_endpoint_roundtrip`; this checks the rendering + the button.)

## Experience pass (rule #11 — corpus-builder / EndNote-migrant persona)

The headline user is the migrant merging a preprint into its published version (callosum's first external adopter
is exactly this — an EndNote migrant). Reception: the Un-merge banner is at the top of Details, indigo =
provenance, one click — discoverable and legible right where you land after merging. Intended use: the mistake a
migrant fears ("I merged the wrong two and lost the preprint's PDF") is now fully recoverable. **Finding (cheap,
fixed in-increment):** the help "Merging duplicates" section explicitly explains *why* merged-away copies aren't
in Trash + how to Un-merge. **Backlogged (not blocking):** a post-merge inline toast with an immediate Undo (the
Details banner already covers it, so this is a nicety) — tagged corpus-builder.

## Pytest

Full suite **1061 passed, 1 skipped** (`--ignore=tests/test_mcp_server.py`). New reversibility suite
`tests/test_library_merge.py` (schema + round-trip + merge-origin + Trash/purge guards + endpoint) + updated
`tests/test_paper_merge.py`; QA API surface coverage 209/209. Security audit `2026-07-07_library-merge-reversibility.md`
PASS.
