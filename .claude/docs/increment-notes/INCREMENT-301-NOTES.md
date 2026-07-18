# Increment 301 — six misc UX fixes (Trash search · read-mode menu bar · Discover recall · duplicate card · invert sort · missing-PDF filter)

A batch of small, independent UX improvements. None touches an honesty invariant (search/sort/filter/view-state); one
adds a `/papers` filter param.

## Implemented

1. **Trash gets the full search/filter set** (`10_pdf_layer.jsx`): the **read** + **priority** filter dropdowns
   (and the new missing-PDF facet) are no longer gated `!trashView`. The backend `list_papers` already applied
   `read_status`/`priority`/`item_type` on the `only_deleted` branch — verified + now tested.
2. **Menu bar hidden in read mode** (`40_app.jsx`): `{!readingMode && <MenuBar/>}`, mirroring the sidebar/detail
   panes the reader already hides; the reader's own Reading toggle exits it.
3. **Discover → Search reloads the last search on access** (`30d_discover.jsx`): an effect keyed on `active` re-runs
   `history[0]` when nothing is currently shown (guarded — never clobbers an in-progress/shown search; no re-run loop).
4. **A completed merge drops its duplicate card** (`19_duplicates.jsx` + `40_app.jsx`): on `onMerged`, the merged
   group's ids flow to `DuplicatesModal`, which hides that group via the existing session `dismissed` set.
5. **Invert-sort direction toggle** (`10_pdf_layer.jsx` + `styles.css`): the Sort dropdown collapses to fields (Date
   added · Title · Year · Author) with a **▲/▼** toggle that maps to the existing backend sort keys
   (added↔recent, title↔title_desc, year_asc↔year_desc, author↔author_desc) — **no backend change**. The three
   explicitly one-way sorts (Most cited · By priority · Unread first) stay whole (their Principles-guarded design).
6. **Missing-PDF filter** (`routers/papers.py` + `repository.py` + `03_library.jsx` + `10_pdf_layer.jsx`): a
   `missing_pdf: bool` param on `GET /papers` → a `NOT EXISTS` for a PDF attachment with a resolved local path
   (matching Text-Health `no_local_pdf`); parameterized (rule #3); composes with search/type/read/priority/sort/
   pagination and works in Trash. A "◫ Missing PDF" toggle facet drives it.

## Line-cap split (rule #1)

`repository.py` was at the 600-cap edge (599); the F6 filter tipped it to 613, so **`get_papers_for_export` +
`list_item_types` moved to the new leaf `persistence/paper_query_repo.py`** and are re-exported from `repository`
(the inc-137/220/262 pattern — zero call-site change). `repository.py` back to ~595.

## Gates

- **Principles (#9):** none produce a claim/signal — search/sort/filter/view-state. "Missing PDF" is a factual
  attribute (mirrors the existing no_local_pdf flag), not a judgment. No egress/provenance change.
- **QA (#10):** `build_surface_map.py check` → 248 API / 1155 FE, **0 uncovered** (the new `missing_pdf` param + the
  new controls are covered by the existing papers/library routes).
- **DESIGN (#8):** the sort toggle + facet reuse the `.lib-sort` recipe + the accent-soft active-facet state; no new
  tokens.

## Manual verification (app on :8888, backend restarted)

Trash → the read/priority/missing-PDF filters appear and apply. Enter read mode → the menu bar vanishes; the reader's
Reading toggle restores it. Open Discover → Search → your last search re-runs. Merge a duplicate → its card
disappears. The Sort ▲/▼ toggle flips any of the four fields. "◫ Missing PDF" filters to PDF-less papers and composes
with search/sort.

## Pytest

`tests/test_papers.py` +2 (`missing_pdf` filter incl. non-PDF + no-local-file cases; trash listing applies the
priority filter) — the whole file green; `tests/test_frontend_assembly.py` +1 (all six UI features). Full
`pytest -n auto` green (count in changes.md); ruff (both) + line-budget + QA 0-uncovered clean.
