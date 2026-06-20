# Increment 69 Notes — Sort the library

The main library only ever listed in import order (`papers.id` ASC). Added a **Sort** control so the user can
order the library by date added, title, publication year, or first author — a reference-manager basic that was
missing (the axes panel got sorting back in inc 43; the library never did).

## Implemented
- **`repository.py`** — `list_papers(..., sort="added")` orders by `_paper_sort_order(sort)`, which indexes an
  **allowlist** (rule #3 — the sort key never reaches SQL text; only constant column expressions do):
  - `added` (default) → `id ASC` (import order — preserves the prior behavior)
  - `recent` → `id DESC`
  - `title` → `lower(title) ASC`
  - `year_desc` / `year_asc` → year DESC/ASC, **NULL year sorts last** (`year IS NULL` first key)
  - `author` → `lower(first_author_family_name) ASC`, NULL author last
  Every non-id sort appends `id ASC` as a stable tiebreak so pagination is deterministic. Unknown keys fall
  back to `added`.
- **`api/routers/papers.py`** — a `sort` query param on `GET /papers` (default `"added"`), passed through.
  No new route (route-surface unchanged), no migration, no egress. Composes with `q` / `deleted` / `axis_id`
  / pagination (they're WHERE clauses; sort is the ORDER BY).
- **Frontend** — a **Sort** dropdown in the library pane-head (`10_pdf_layer.jsx`); `40_app.jsx` `librarySort`
  state + `changeSort` (resets to page 1) threaded into the `/papers` fetch (omitted when `"added"` so the
  default URL is unchanged) and the deps array; `.lib-sort*` CSS (token-based). Rebuilt `callosum-app.html`.

## Verification
- **pytest 236** (+1): `test_library_sort_orders` seeds Cherry/Apple/Banana (+ a year/author-less Durian) and
  asserts every sort key's exact order, NULL-last for year/author, and unknown-key → default.
- **Live E2E** (`.local/library_sort_e2e/`): the visible list re-orders by title (A–Z), year (newest), and
  recency as the dropdown changes, 0 console errors; screenshot.
- No audit gate (no new endpoint/fetch/ingestion; a read-only query param). Help corpus library section
  updated (`HELP-DOCS-SYNCED` → inc 69).

## Manual verification script
1. Open the app with several papers. The **Sort** dropdown sits under the search box.
2. Pick **Title (A–Z)** → the list reorders alphabetically; **Year (newest)** → newest first; **Recently
   added** → most recent import first. Papers missing a year/author fall to the bottom for those sorts.
3. Confirm sort composes: search for a term, switch to Trash, or filter by an axis — the chosen sort still
   applies.

## Deferred (noted)
- Persisting the chosen sort across reloads (localStorage), and a direction toggle on the column, if wanted.
