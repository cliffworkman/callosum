# Increment 209 — A3: full-text PDF search (SQLite FTS5)

## Implemented

The seventh close-out of the cheapest-first wrap-up pass (A3): verbatim/lexical search over the already-extracted PDF
chunk text — the **exact-string complement** to the semantic axes/synthesis ("find 'ultimatum game' verbatim").

**Backend**
- **Migration `0026_chunks_fts`** (raw DDL via `op.execute`; the project's first trigger/virtual-table migration):
  an **external-content** FTS5 index `chunks_fts` over `chunks.text` (`content='chunks', content_rowid='id'` — no text
  duplication; `snippet()`/`bm25()` available) + the **sync trigger trio** on `chunks` (AFTER INSERT / DELETE / UPDATE)
  + a backfill of existing chunks. The **AFTER DELETE** trigger is the critical one — it catches the **FK CASCADE
  delete** from `purge_paper` (inc 65) that bypasses the Python layer. Guarded + idempotent (like 0021); a **real
  guarded `downgrade()`** drops the triggers + table (unlike the metadata-table migrations, 0001's `metadata`-loop
  can't drop an FTS5 table, so no double-drop — the inc-208 0025 lesson applied in reverse). `metadata.create_all`
  can't express FTS5, so the migration is the source of truth (runs on fresh DBs too).
- **`persistence/fulltext_repo.py`** (new): `_safe_match` sanitizes the raw query into a safe FTS5 MATCH string (each
  whitespace token with alphanumeric content → a double-quoted phrase, `"`→`""`, AND-ed) — quoting neutralizes every
  FTS5 operator so it can't be a syntax error or inject the query language; `search_chunks_fulltext` runs the bound
  `MATCH` over live papers (`deleted_at IS NULL`), bm25-ranked, capped at 50, `snippet()`-marked, wrapped in
  `try/except OperationalError → []` (never 500). Snippet markers are private-use chars (U+E000/E001).
- **`routers/fulltext.py`** (new): `GET /papers/fulltext?q=&limit=` → per-occurrence `FulltextHit`s
  (`paper_id/title/author/year/chunk_id/page_start/page_end/snippet/coordinate_precision="region"`). Registered in
  `app.py` **before** `papers.router` (so `/papers/fulltext` isn't captured by `/papers/{paper_id}` — the duplicates.py
  precedent).

**Frontend**
- A **"Full text (PDFs)"** option in the existing search-scope dropdown; the search placeholder becomes "search inside
  your PDFs…". When that scope is active + a query is present, `PaperList` swaps the library list for
  **`FulltextResults`** (new chunk `js/10c_fulltext.jsx`) — a **self-contained** component that does its own debounced
  `GET /papers/fulltext` fetch, so **`40_app.jsx` is untouched** (it already threads `query`/`librarySearchField`/
  `onOpenPdf`). Per-occurrence cards (reusing the inc-156 `.cite-card`/`.quote` recipe): title + author·year, the
  snippet with matched terms **bolded** (`.ft-mark`, split on the U+E000/E001 markers → React `<b>` nodes, no
  `dangerouslySetInnerHTML`), the page, and **Open at page** → `citationTarget` → `openPdf` (region precision — page
  scroll, no fabricated exact rect). An "exact wording, not meaning" hint + a "N matches in M papers" line + an empty
  state.

## Key technical detail

The CASCADE-delete-bypasses-Python problem (the chunks-immutable finding from the Explore pass) is solved by an SQLite
**trigger**, not a Python hook — the AFTER DELETE trigger fires on the FK CASCADE that `purge_paper` triggers. And the
query-safety is two-layered: token-quoting makes the FTS5 MATCH string operator-free (no syntax error / no query-lang
injection), plus a bound param (no SQLi) plus a try/except fallback (never 500). The frontend full-text mode is a
self-contained component precisely to avoid growing `40_app.jsx` (599/600).

## Manual verification script

`HF_HUB_OFFLINE=1 python -m pytest tests/test_fulltext.py -q` → 4 passed: `_safe_match` sanitization; the endpoint
returns a snippet+page hit + excludes trashed papers; malformed/empty queries (`"`, `*`, `NEAR(`, `^`, …) → 200 `[]`
never 500; the FTS triggers stay in sync across a chunk insert **and a paper-delete CASCADE**.
**Headed (no egress):** `.local/visual/drive_inc209_fulltext.py` — using the QA seed (renderable paper + seed.pdf,
chunk "…signal detection appears on page two"): scope → Full text → search "signal detection" → **1 hit, 2 bolded
matches, p. 2** → malformed `"` → 0 hits (no error) → Open at page → the PDF renders scrolled to page 2. 0
console/page/genai.

## Gates

- **pytest:** full suite green — **719 passed, 1 skipped** (+4 `tests/test_fulltext.py`).
- **ruff** check + format clean; frontend rebuilt; migration head **0026** via `alembic_head()`.
- **QA surface** — **142/142 API** (+1 `/papers/fulltext`) **+ 677/677 FE, 0 uncovered**; new
  `route_22_fulltext.md` (the API + the FE hit list + verbatim-not-semantic / region-honesty / malformed-no-500 /
  no-egress assertions).
- **Security audit `2026-06-29_fulltext-search.md` PASS** (sanitized + bound + fail-closed input; escaped output, no
  XSS; local-only no egress/SSRF; bounded; trashed-excluded; trigger-synced incl. CASCADE; no new dependency).
- **Principles non-triggering** (verbatim lexical lookup; no claim/rank/score — bm25 is an internal ordering, never a
  displayed verdict; coordinate-honest region open). **DESIGN.md** records the result-card recipe (rule #8). **Help
  corpus** gained a "Searching inside your PDFs" paragraph (`HELP-DOCS-SYNCED` → 209). **No new dependency** (FTS5 is
  core SQLite). **Rule-#1:** the full-text mode is a self-contained component → `40_app.jsx` stays 599/600;
  `10_pdf_layer.jsx` ends at 555.

## NEXT (continuing the close-out)

The cheapest-first A-items are now done (A9/A10/A8/A6/A5/A1/A3). Remaining: **A2** library-wide per-paper citation
counts (generalize My-Pubs Layer-3 OpenAlex counts to all cards — metadata egress, displayed-with-source, never a
silent rank) and **A7 Curated Axis** (the biggest A item — its own design pass). The deferred **B-items** (MCP server,
citation-context classifier) are larger, own design passes.
