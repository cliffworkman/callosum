# Increment 89 — Search across all fields + a search-scope dropdown

## Implemented
Two related search upgrades (user request): (1) **fix the all-authors bug** — search only looked at `title` +
`first_author_family_name`, so a non-first author (e.g. the user as 2nd–nth author on 34 of their 40 papers)
was unfindable; (2) a **scope dropdown** next to the search box (All fields / Title / Author / Journal). The
full bibliographic record lives in `csl_json` (every author, journal, year, DOI, publisher, ISSN, …), so
searching its text surfaces everything we now store.

- `app/backend/persistence/repository.py` — `list_papers(..., search_field="all")` + a `_search_clause(field,
  pattern)` helper over a `SEARCH_FIELDS` **allowlist** (rule #3 — `field` is a key, never interpolated; the
  pattern is bound):
  - `title` → `lower(title)`.
  - `author` → `lower(first_author_family_name)` OR `lower(cast(csl_json, String))` — the cast surfaces **every**
    author in `csl_json["author"]`; the scalar is belt-and-suspenders (no regression for the old first-author match).
  - `journal` → `lower(venue)`.
  - `all` (default) → title OR venue OR first_author OR abstract OR the whole `csl_json` text.
- `app/backend/api/routers/papers.py` — a `search_field` query param on `GET /papers`, threaded to `list_papers`.
- Frontend: a **"Search in"** dropdown (All fields / Title / Author / Journal) in the search row
  (`10_pdf_layer.jsx`, reuses the `.lib-sort` select recipe); `40_app.jsx` `librarySearchField` state → the
  `/papers` fetch (`search_field` when ≠ all + a search term) + page reset; placeholder updated to "Search title,
  author, journal…". Rebuilt `callosum-app.html`.

## Key technical detail
The fix is searching `csl_json` (the canonical full record) instead of only the scalar projections — a
`CAST(csl_json AS TEXT) LIKE` (SQLite stores JSON as text). This is comprehensive (all authors + journal + year +
DOI + …) without a migration or a denormalized column. Trade-offs accepted for v1: `author` scope matches the
whole `csl_json` (so a query that appears in a paper's title/venue could match under "Author") — fine for name
searches; a precise per-author `json_each` query is a future refinement. `all` also searches the `abstract`
(JATS) so its tag names are technically matchable — negligible for real-word queries. No new egress, no migration.

## Manual verification script
1. Hard-refresh (Ctrl+Shift+R).
2. Search your surname with the scope on **All fields** (default) → all papers where you're *any* author appear
   (not just first-authored). Switch the scope to **Author** / **Journal** / **Title** and confirm it narrows.
   _(Visual check delegated to the user.)_

## Pytest
**384 passed, 1 skipped** (+1: `test_search_covers_all_authors_and_scopes` — a non-first author is found under
"all" + "author", not under "title"; "journal" matches the venue; the existing first-author q-test still passes).
`ruff` clean. No migration, no new endpoint, no egress.
