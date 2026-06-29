# Increment 208 — A1: saved searches + split the library-header menus → 10b_libmenus.jsx

## Implemented

The sixth close-out of the cheapest-first wrap-up pass (A1). A **saved search** persists a named bundle of the
existing library facets and recalls it from the header — a metadata predicate over the existing `GET /papers`
filters, **distinct from an axis** (a semantic lens; saved searches compute no claim/rank/score).

**Backend**
- **Migration 0025** (additive, guarded, mirrors 0021): a `saved_searches` table (`id`, `name` UNIQUE, `params` JSON,
  `created_at`). Head via `alembic_head()`.
- **`persistence/saved_search_repo.py`** (new; like tags_repo / dedup_repo, to keep repository.py under the cap):
  `list_saved_searches`, `upsert_saved_search` (overwrite-by-name → re-saving a name never duplicates),
  `delete_saved_search`.
- **`routers/saved_searches.py`** (new): `GET /saved-searches`, `POST /saved-searches {name, params}`,
  `DELETE /saved-searches/{id}`. The `params` are a **typed, `extra="forbid"` model** (`SavedSearchParams`:
  q/search_field/item_type/axis/tag/needs_review/signal/sort) — only known facet keys are stored (unknown → 422;
  blank name → 422), the boundary-validation (rule #4). Registered in `app.py`.

**Frontend**
- `40_app.jsx`: `savedSearches` state + `loadSavedSearches`; `currentSearchParams()` (gather the live facets),
  `applySavedSearch(p)` (set them all — search box + scope + sort + axis/tag/needs-review/signal — clearing trash/focus;
  sets `query` AND `debounced` so there's no 280ms double-fetch), `saveCurrentSearch(name)`, `deleteSavedSearch(id)`.
  Threaded into `libraryProps`.
- A **`SavedSearchMenu`** ("Saved ▾", mirroring `AddMenu`): a popover with **Save current search…** (a `window.prompt`
  name) + a row per saved search (click = apply, × = delete). One `.saved-search-*` CSS recipe reusing `.add-menu-pop`.

**Rule-#1 split (forced):** `SavedSearchMenu` pushed `10_pdf_layer.jsx` to **602/600**. Extracted both header dropdowns
(`AddMenu` + `SavedSearchMenu`) → new **`js/10b_libmenus.jsx`** (10_pdf_layer.jsx → **547**, 10b 62); `PaperList`
references them via the shared-IIFE function hoist. (`40_app.jsx` is at **599/600** — the new closest watch.)

## Key technical detail

The saved `params` are a small JSON blob validated by a typed `extra="forbid"` model at the write boundary, so junk
keys can't be stored; the *values* are re-validated by `GET /papers` when the search is applied (the facets are the
same ones the library list already accepts). The axis/tag facets store `{id,label/name,hideUncertain?}` so the filter
banner can render without a second lookup.

## Manual verification script

`HF_HUB_OFFLINE=1 python -m pytest tests/test_saved_searches.py -q` → 1 passed (create; list; **upsert-by-name** = no
duplicate; unknown-key → 422; blank name → 422; delete 204 then 404).
**Headed (no egress):** `.local/visual/drive_inc208_saved_search.py` — type a query → **Saved ▾ → Save current
search…** → it lists with `q="memory"` → clear the query → **apply** it → the search box restores to "memory" →
**×** delete → gone. **4/4 deterministic runs**, 0 console/page/genai. (Two test-harness notes: a real click→
`window.prompt` is racy under Playwright → the driver stubs `window.prompt`; and the debounced `/papers` refetch
re-renders `PaperList`, so the driver settles on `networkidle` before menu clicks to avoid a DOM-detach race.)

## Gates

- **pytest:** full suite green — **715 passed, 1 skipped** (+1 `tests/test_saved_searches.py`).
- **ruff** check + format clean; frontend rebuilt; migration head **0025** via `alembic_head()`.
- **QA surface** — **141/141 API** (+3: `/saved-searches` GET/POST/DELETE) **+ 675/675 FE, 0 uncovered**; new
  `route_21_saved_searches.md` (the 3 endpoints + the `extra="forbid"` 422 + the "distinct-from-an-axis, no score"
  assertion); `10b_libmenus.jsx` claimed by `route_00` (AddMenu) + `route_21` (SavedSearchMenu).
- **Audit:** none triggered (a local table + 3 local endpoints; no egress/fetch/dependency). **Principles non-triggering**
  (a saved facet-bundle, not a claim/signal; reinforces "no score" in the copy).
- **Help corpus** gained a "Saved searches" paragraph (`HELP-DOCS-SYNCED` → 208).

## NEXT (continuing the cheapest-first close-out)

**A3** — basic full-text PDF search (a SQLite **FTS5** index over the already-extracted `chunks` text, surfaced as a
search field with hit highlighting; the *exact-string* complement to the semantic axes). **Migration + a security
audit** (a new query surface — validate input). Then **A2** library-wide citation counts, and **A7 Curated Axis** (its
own design pass). **Rule-#1 watch:** `40_app.jsx` (**599/600**, closest — split before the next addition), `routers/
papers.py` (570), `30_viewer.jsx` (557).
