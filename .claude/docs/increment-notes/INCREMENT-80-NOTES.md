# Increment 80 — The "Unsorted" library view (a needs-review filter)

## Implemented
A reference-manager housekeeping view: a library filter that surfaces the papers whose **metadata still needs
review** — raw PDF scaffolds, Crossref-unresolved imports, and papers with no recorded source — so they don't
silently disappear into the library. (INCREMENT-22-NOTES already noted unresolved records were "queryable as
needing metadata"; this exposes that as a UI view.) Aligned with "silence is not a certificate": an unresolved
paper is shown as needing attention, not quietly mixed in as if it were fully catalogued.

- `app/backend/persistence/repository.py` — `list_papers(..., needs_review: bool = False)`; when set, filters to
  `imported_source IN NEEDS_REVIEW_SOURCES OR imported_source IS NULL`. New module constant
  `NEEDS_REVIEW_SOURCES = ("pdf-scaffold", "crossref-unresolved")` (a local literal allowlist — bound-param `IN`,
  rule #3; kept local to avoid an `enrichment → repository` import cycle). Composes with the existing
  deleted/q/axis_id/tag_id/pagination clauses (trashed papers stay excluded).
- `app/backend/api/routers/papers.py` — a `needs_review: bool = Query(default=False)` param on `GET /papers`,
  threaded into `list_papers`. No new route, no migration, no egress.
- `app/frontend/js/40_app.jsx` — `libraryNeedsReview` view-state (mirrors `trashView`): a `toggleNeedsReview`
  (exclusive with trash/axis/tag/focus, but keeps checkbox-select usable) + `clearNeedsReview`; the `/papers`
  fetch adds `needs_review=true`; threaded into `LibraryFrame` → `PaperList`.
- `app/frontend/js/10_pdf_layer.jsx` — an **Unsorted** toggle in the library header (reuses `.trash-toggle`, no
  new CSS — the active state flips the label to "← Library", mirroring the Trash button) + a clearable banner
  (reuses the inc-63 `.focus-card`) explaining the view.
- Rebuilt `callosum-app.html`.

## Key technical detail
"Needs review" is a **fixed allowlist of `imported_source` values plus NULL**, not a heuristic: `pdf-scaffold`
(raw ingest, never enriched) and `crossref-unresolved` (Crossref couldn't match the DOI) are the unresolved
states the pipeline writes; `NULL` covers papers minted without a source. Resolved states (`crossref`,
`user-edited`, `zotero`, `wanted-oa`) are excluded. The constant lives in `repository.py` (not imported from
`enrichment.py`) because `enrichment` already imports `repository` — importing back would cycle; the string
literals are stable (they're the values stored in the DB), so a local copy with a pointer comment is the safe
choice. The filter is a **view** (like Trash) — mutually exclusive with the trash/axis/tag filters and focus
mode, but it keeps checkbox multi-select on, so you can select-all the unsorted papers and bulk re-resolve /
export / delete them.

## Manual verification script
1. Hard-refresh the app (Ctrl+Shift+R) to load the rebuilt frontend.
2. Library header → click **Unsorted**. The list narrows to scaffold / unresolved / no-source papers; a banner
   reads "Unsorted — papers whose metadata still need review …" with a **clear** link; the header button reads
   "← Library".
3. Click an unsorted paper → 🔎 re-resolve (or edit it) so it becomes `crossref`/`user-edited`; toggle Unsorted
   off and on → it's gone from the view. Confirm Trash / an axis filter clears the Unsorted view (mutually
   exclusive). _(Visual check delegated to the user — no in-repo browser automation this session.)_

## Pytest
**362 passed, 1 skipped** (+1: `test_papers_list_needs_review_filter` — the three unsorted states are returned,
resolved/user-edited excluded, default lists all live, trashed stay excluded). `ruff` clean. No migration, no
new endpoint, no egress (a read-only query param on the existing `/papers` listing).
