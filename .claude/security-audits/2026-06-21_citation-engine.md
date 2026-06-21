# Security audit — Citation & bibliography engine (citeproc-js), inc 106

**Date:** 2026-06-21
**Trigger:** Audit gate — a new third-party dependency (`citeproc` + bundled CSL data), new API endpoints, and a
new JS runtime/subprocess.
**Scope:** `package.json`/`package-lock.json`; `app/backend/citations/{citeproc_runner.js, render.py, csl/**}`;
`app/backend/api/routers/citations.py`; `app/backend/api/app.py` (router include); frontend `25_detail.jsx` +
`10_pdf_layer.jsx` + `40_app.jsx`.

## What changed
A backend **formatted-citation engine**: the existing `papers.csl_json` is rendered to formatted in-text
citations + bibliographies in real CSL styles via **citeproc-js**, run locally as a Node sidecar (the same
subprocess pattern as esbuild). Two endpoints (`GET /citations/styles`, `POST /citations/render`) power an in-app
surface (Details "Cite as …" + a bulk "Formatted bibliography…" download). No word processor yet.

## Threat review

| Area | Assessment |
|---|---|
| **Supply chain (new dep)** | `citeproc` pinned in `package.json`; `package-lock.json` committed; CI installs via `npm ci` (lockfile-exact). `npm install` reported **0 vulnerabilities**. citeproc-js is the widely-used reference CSL processor (used by Zotero). Bundled CSL **styles/locales** are committed **verbatim** from the official CSL repos (CC-BY-SA; `<rights>` preserved) — data, not executable. |
| **Subprocess / injection** | The sidecar is invoked with a **fixed arg list** `[node, citeproc_runner.js]`, `shell=False`; the request (CSL-JSON items + style + locale) is piped via **stdin as JSON** — no user input ever reaches a command line or a shell. |
| **Path safety** | The runner reads only `csl/styles/<style>.csl` + `csl/locales/locales-<locale>.xml`. `style` is **allowlisted** to `STYLE_IDS` in `render.py` *and* regex-validated (`^[a-z0-9-]+$`) + existence-checked in the runner before any read; `locale` is allowlisted to `LOCALES` (else falls back to en-US). No user-supplied paths → no traversal. |
| **Input validation** | `POST /citations/render` bounds `paper_ids` (`min_length=1, max_length=5000`); `render_papers` caps `MAX_ITEMS`; rows come from `get_papers_for_export` (**live papers only**). The rendered CSL-JSON is the user's **own local library** data. |
| **Output encoding / XSS** | citeproc emits HTML. The backend **sanitizes** it (`render._safe_html`): an allowlist of *bare* inline tags (`i/b/em/strong/sub/sup`) only — **all attributes dropped, all text escaped, every other tag (div/span/script/…) stripped** (its text kept, escaped). A plain-text variant is also returned. In-app display uses the sanitized HTML via `dangerouslySetInnerHTML` — the **same audited posture** as `clean_abstract_for_display` (inc 33) + the help corpus (inc 59). The bulk path writes sanitized HTML into a **downloaded `.html`** (not rendered in-app). Negative path: a CSL title containing `<script>` is escaped by citeproc *and* re-escaped/stripped by `_safe_html` → inert text. |
| **Data egress** | **None.** citeproc runs locally; styles are **bundled** (the fetch-on-demand long-tail is deferred to a later, consent-gated increment). No network call in this feature. The Gemini gate is untouched. |
| **CORS / surface** | The in-app frontend calls `POST /citations/render` **same-origin** (127.0.0.1) — unaffected by the GET-only CORS. **CORS is NOT changed** here; a cross-origin word-processor add-in (the Word increment) will revisit it then. Endpoints follow the app's existing 127.0.0.1 / no-auth posture. |
| **Secrets** | None involved. |
| **Resource caps** | One sync subprocess per request; input bounded; citeproc rendering is fast. |

## Negative-path checks (recorded)
- [x] Unknown style → **422** (`test_render_validation`).
- [x] No live/non-trashed papers → **422** (`test_render_validation`).
- [x] Node/citeproc absent → **503**, never 500 (`test_engine_unavailable_returns_503`, monkeypatching the dep path).
- [x] Rendered HTML sanitized to bare inline tags before any in-app render (`reference_html` asserted to contain
      `<i>` and **not** `<div>` in `test_render_apa_author_date`); plain-text variant provided.
- [x] Style/locale allowlisted (Python) + regex-validated + existence-checked (Node) → no path traversal.

## Outcome
Security Audit: **PASS.**
