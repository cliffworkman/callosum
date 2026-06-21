# Increment 106 — Citation & bibliography engine (Phase 1 of word-processor integration)

The foundation of the word-processor-integration track (the biggest gap to day-one Zotero/Mendeley parity). Turns
the canonical `papers.csl_json` into **formatted** in-text citations + bibliographies in real CSL styles
(APA/MLA/Chicago/IEEE/Nature/Harvard) via **citeproc-js**, and surfaces it **in the app** — closing the "no
formatted citation styles" gap (the export at inc 70/103 was machine-readable only). The word-processor adapters
ride this exact engine (next: LibreOffice). User chose: engine + in-app surface first; LibreOffice as the first
adapter.

## Implemented
**Backend — new `app/backend/citations/` package + `routers/citations.py`:**
- **citeproc-js as a Node sidecar.** `citeproc` pinned in `package.json` (`dependencies`). `citeproc_runner.js`
  reads a request on **stdin** (`{items: CSL-JSON[], style, locale}`), runs `CSL.Engine` (a `sys` serving the
  passed items + the bundled locale), writes `{items:[{id,inText,reference}], bibliography:[…]}` on stdout —
  invoked the **same way as esbuild** (`render._run_engine` mirrors `frontend.py::_transpile_jsx`:
  `shutil.which("node")` + a `node_modules/citeproc` check + fixed-arg `subprocess.run`, stdin/stdout, fail-closed
  → `CitationEngineUnavailable`).
- **Bundled CSL styles + locales** under `app/backend/citations/csl/` (committed verbatim from the CSL repos,
  CC-BY-SA, `<rights>` preserved): APA 7, MLA 9, Chicago author-date 18, Chicago notes-bib 18, Harvard (Cite Them
  Right 12), IEEE, Nature; locales en-US, en-GB. (Vancouver persistently 404'd from this network — a one-file
  follow-up; IEEE/Nature cover numeric, incl. the tests.)
- **`render.py`** — the `STYLES` manifest (id allowlist), `list_styles()`, `render_papers(papers, *, style, locale)`
  (builds CSL items from `csl_json` + `id`, calls the sidecar, **sanitizes** the HTML), and the HTML→text /
  HTML→safe-HTML helpers. `_safe_html` keeps only **bare** inline tags (`i/b/em/strong/sub/sup`), escapes all text,
  drops attributes + every other tag — same allowlist posture as `clean_abstract_for_display` (inc 33).
- **Endpoints (sync, local, read-only, no egress):** `GET /citations/styles` (manifest + locales) +
  `POST /citations/render {paper_ids, style, locale}` → per-paper `in_text` + `reference_text`/`reference_html` and
  a combined `bibliography_text`/`bibliography_html`. Reuses `get_papers_for_export` (live papers only).
  Unavailable engine → 503; unknown style / no papers → 422; engine error → 502.

**Frontend:**
- **Details "Cite as …"** (`25_detail.jsx`, `CiteRow`): a **style dropdown** + a **live formatted-citation
  preview** (sanitized HTML, hanging indent) + **Copy** (plain text), alongside the existing BibTeX/RIS/CSL-JSON
  export links.
- **Bulk "bibliography…"** (`10_pdf_layer.jsx` bulk bar): pick a style → `bulkBibliography` (`40_app.jsx`) renders
  the selection and **downloads a formatted `.html`** bibliography (built from the sanitized `bibliography_html`).

**Toolchain/CI:** `package.json` += `citeproc`; CI's `npm ci` (inc 102) makes it available in tests. The `.csl`/
`.xml` data files are non-code (600-line rule exempt).

## Key technical detail
One central citeproc-js render = byte-identical output everywhere (the spec's "backend renders, adapters only
place"). The engine is **target-agnostic** — the LibreOffice/Word/Docs adapters will call the same render path;
this increment just wires it to the web app. citeproc returns HTML, so the boundary **sanitizes server-side**
before any in-app `dangerouslySetInnerHTML` (and the bulk path only injects sanitized HTML into a *downloaded*
file). **No egress** — styles are bundled (fetch-on-demand long-tail deferred + consent-gated later). Determinism
(pinned citeproc + committed styles) makes the render assertions stable.

## Manual verification script (delegated)
1. `npm install` (citeproc) → start the app → open a paper → Details → **Cite as → APA** shows the formatted
   reference (italic journal); **Copy** pastes it; switch to **IEEE** → numeric form.
2. Select several papers → bulk bar → **bibliography… → Chicago (author-date)** → a `.html` downloads; open it →
   a correctly-formatted, alphabetized reference list.

## Pytest
**416 passed, 1 skipped** (+5 `tests/test_citations.py`: APA author-date + IEEE numeric render, styles endpoint,
validation 422s, engine-unavailable 503; route-surface allowlist gained `/citations/styles` + `/citations/render`).
`ruff` clean; opt-in Playwright smoke (0 console errors); `callosum-app.html` rebuilt. Audit
`.claude/security-audits/2026-06-21_citation-engine.md` **PASS**; credit in `THIRD-PARTY-NOTICES.md`
(citeproc-js AGPL + CSL CC-BY-SA — the credit-the-lineage principle).

## Next (the track)
LibreOffice (UNO) adapter — the live-field loop (insert → render → update → flatten) on this engine; then Word
(Office.js, needs the CORS/origin change); then Google Docs (opt-in). Deferred: fetch-on-demand styles, Vancouver
+ more styles, rich-clipboard (italics) copy, CRediT builder, highlight-to-suggest/evaluate.
