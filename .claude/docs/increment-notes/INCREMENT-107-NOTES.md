# Increment 107 — Position-aware document-render layer (word-processor adapter substrate)

## Implemented
The inc-106 engine renders each citation **in isolation** (`makeCitationCluster`) — right for the in-app
"Cite as …" / bulk bibliography (a selection), but **wrong for a live word-processor document**: numeric styles
must renumber `[1][2][3]` by document order, and author-date styles must disambiguate (`2020a`/`2020b`) across the
whole document. This increment adds the **position-aware document-render layer** — the shared contract every
word-processor adapter (LibreOffice next, then Word, then Google Docs) will call. Backend-only; fully
pytest-testable; **no frontend change** (so no rebuild).

- **`app/backend/citations/citeproc_runner.js`** — a new `mode:"document"` branch using citeproc's
  **`rebuildProcessorState(clusters, "html")`** (the standard "render this saved ordered set" call — how Zotero
  renders a document). It flattens each cluster's embedded CSL-JSON into the item store, builds positional
  clusters (`{citationID, citationItems:[{id}], properties:{noteIndex:0}}`), and maps the returned
  `[citationID, noteIndex, renderedString]` rows → `{citations:[{citationID, html}], bibliography:[…]}`. The
  inc-106 per-item path (`updateItems` + `makeCitationCluster`) stays the **default, unchanged**.
- **`app/backend/citations/render.py`** — refactored the subprocess call `_run_engine(items,…)` → **`_run(request:
  dict)`** (both `render_papers` and the new function build their own request + call it). New **`render_document(
  citations, *, style, locale)`**: validates style/locale against the existing allowlist; caps clusters
  (`MAX_CLUSTERS=5000`), items-per-cluster (`MAX_ITEMS_PER_CLUSTER=50`), and total items (`MAX_ITEMS=5000`);
  rejects an item with no `id`; builds `{mode:"document", …, citations:[{citationID, items:[CSL-JSON]}]}`;
  sanitizes each rendered string (`_safe_html`) + text (`_to_text`); returns `{style, locale,
  citations:[{citationID, text, html}], bibliography_text, bibliography_html}`. **Self-contained** — renders from
  the passed CSL-JSON payloads (each document field carries its own), so **no library lookup / no DB connection**.
- **`app/backend/api/routers/citations.py`** — **`POST /citations/render-document`** `{citations:[{citationID?,
  items:[CSL-JSON]}], style, locale}` → `render_document`. Same status contract as `/citations/render`:
  `CitationEngineUnavailable`→503, `ValueError`→422 (caps / unknown id / unknown style), `RuntimeError`→502;
  unknown style also rejected pre-engine (422). New `CitationCluster` / `RenderDocumentRequest` Pydantic models
  (caps enforced at the boundary).
- **`tests/test_citations.py`** (+3): IEEE numbering `[1][2][3]` **and** renumber-on-reorder (the same citation
  goes `[1]`→`[3]` when the document order reverses) + bibliography line count; APA `2020a`/`2020b` disambiguation
  across the document; unknown-style → 422. **`tests/test_health.py`** — route allowlist +
  `("/citations/render-document", POST)`.

## Key technical detail
`rebuildProcessorState` is the position-aware API (vs `makeCitationCluster`, which renders one cluster in
isolation with no document context). It returns the rendered in-text for **every** cluster as
`[citationID, noteIndex, renderedString]`, having already applied document-wide numbering + disambiguation — so
the adapter does the dumb part (find fields, place text) and the engine does the smart part (renumber, disambiguate,
build the bibliography). The render is **stateless per request**: the adapter always POSTs the *full* ordered
cluster set and gets back the *full* consistent render, so there is no server-side document state to keep in sync.

## Manual verification script
(Optional — backend-only; pytest is the gate.) With Node + `citeproc` installed (`npm install`):
1. `uvicorn app.backend.api.app:app --port 8080`
2. `POST http://127.0.0.1:8080/citations/render-document` with body
   `{"style":"ieee","citations":[{"citationID":"A","items":[{"id":"a","type":"article-journal","title":"X","author":[{"family":"Vaswani"}],"issued":{"date-parts":[[2017]]}}]}, {"citationID":"B","items":[{"id":"b","type":"article-journal","title":"Y","author":[{"family":"Devlin"}],"issued":{"date-parts":[[2019]]}}]}]}`
   → `citations[*].text` are `[1]`, `[2]`; `bibliography_text` has 2 lines.
3. Reverse the two clusters → the labels swap with position (A becomes `[2]`).
4. Switch `"style":"apa"` with two same-author/same-year items → `(Smith, 2020a)` / `(Smith, 2020b)`.

## Pytest
**419** passing (+3 over inc 106's 416; 1 skipped opt-in browser smoke, unchanged). `ruff` clean. Audit
`.claude/security-audits/2026-06-21_citation-render-document.md` **PASS**.

## Non-goals (deferred)
- The **LibreOffice (UNO) adapter** — the live-field loop (insert → render → update → flatten) riding this
  endpoint. **Next increment.**
- Note-style footnote management (noteIndex 0 → in-text styles only this increment; the adapter manages footnotes
  for note styles later). Locators/prefixes/suffixes. Fetch-on-demand styles. A `subprocess` wall-clock timeout
  (shared with the inc-106/esbuild sidecars; flagged in the audit — local-only, non-blocking).
