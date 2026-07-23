# Security Audit — Position-aware document-render endpoint (`POST /citations/render-document`, inc 107)

**Date:** 2026-06-21
**Feature:** A second citeproc-js render mode + endpoint that renders a word-processor document's **ordered
citation clusters** position-aware (numeric renumbering, author-date disambiguation). The shared contract every
word-processor adapter (LibreOffice → Word → Google Docs) will call. Backend-only.
**Files:** `app/backend/citations/citeproc_runner.js` (added a `mode:"document"` branch),
`app/backend/citations/render.py` (`_run_engine` → `_run`; new `render_document`),
`app/backend/api/routers/citations.py` (new endpoint + request models),
`tests/test_citations.py` (+4), `tests/test_health.py` (route allowlist +1).

## Trigger
Audit gate #1 (new API endpoint / request-schema). No new dependency, no new fetch/integration, no new
file-ingestion/write path, no auth change. Reuses the inc-106 sidecar + bundled CSL data.

## Threat review

- **Input validation / boundary (rule #4).** The request is `{citations:[{citationID?, items:[CSL-JSON]}],
  style, locale}`. Pydantic caps the shape: `citations` ≤ `MAX_CLUSTERS` (5000), each cluster's `items`
  1..`MAX_ITEMS_PER_CLUSTER` (50); `render_document` additionally caps **total** items at `MAX_ITEMS` (5000) and
  rejects any item lacking an `id` (422). `style` is checked against the `STYLE_IDS` **allowlist** before the
  sidecar is touched (422 on miss); `locale` not in the `LOCALES` allowlist silently falls back to `en-US`
  (citeproc tolerates a missing secondary locale). The CSL-JSON payloads are the user's **own document data**
  (the same shape `papers.csl_json` already holds and that inc-106 already renders).
- **Injection.** No SQL at all on this path (self-contained — **no library lookup**, no DB connection injected).
  The sidecar is invoked exactly like inc-106 / esbuild: a **fixed argv** `subprocess.run([node, _RUNNER], …)`
  with `shell=False`, the request passed as **JSON on stdin** (never interpolated into a command line). The
  runner reads stdin, validates `style` against `^[a-z0-9-]+$` **and** file existence before reading a `.csl`
  (no path traversal — the regex forbids `/`, `.`, `\`), and loads locales only from the bundled
  `csl/locales/` dir by a fixed name template. citeproc itself does no network or filesystem access beyond the
  `retrieveLocale`/`retrieveItem` callbacks we supply.
- **Output encoding.** citeproc returns HTML; every rendered string (per-cluster in-text + each bibliography
  entry) is passed through `_safe_html` (allowlist of bare inline tags `i/b/em/strong/sup/sub`; **all** text
  escaped; attributes + every other tag dropped) **and** `_to_text` for the plain-text field — the same posture
  audited in inc 33 / 59 / 106. The endpoint is consumed by adapters/tests, not yet rendered in the app, but the
  sanitized output means a future in-app `dangerouslySetInnerHTML` is already safe.
- **SSRF / external calls / egress.** **None.** Styles + locales are bundled verbatim under `app/backend/
  citations/csl/` (no fetch-on-demand); the render is fully local. The CSL-JSON never leaves the machine. This
  is **not** the Gemini library-text egress gate and correctly sits outside it.
- **Secret handling.** No secrets touched.
- **Resource caps.** Clusters ≤5000, items/cluster ≤50, total items ≤5000 (rejected before the subprocess). The
  subprocess is one short-lived `node` invocation; no unbounded loop, no recursion. (No explicit wall-clock
  timeout on `subprocess.run` — consistent with inc-106 / the esbuild sidecar; acceptable for a local,
  single-user, 127.0.0.1 tool. Flagged below as a shared follow-up, not a blocker.)
- **File-path safety.** No filesystem path is built from request data. The only paths are the constant runner
  path + the regex/existence-guarded `<style>.csl` / `locales-<locale>.xml` inside the bundled dir.
- **Fail-closed.** `node`/`citeproc` absent → `CitationEngineUnavailable` → **503**. Malformed input / unknown
  style / missing id → **422**. Any sidecar/engine error (caught last; `CitationEngineUnavailable` is a
  `RuntimeError` subclass, ordered first) → **502**. Never a 500; never a partial/guessed render.

## Negative-path checks (concrete)
- Unknown style → **422** (`test_render_document_validation`; also guarded twice — Pydantic-independent
  allowlist check in the router + `STYLE_IDS` check in `render_document`).
- Engine absent → **503** (covered by the inc-106 `test_engine_unavailable_returns_503` monkeypatch on the same
  `_run`/`_CITEPROC` path the document route shares).
- Item without `id` → `ValueError` → **422** (`render_document` raises before the subprocess).
- Over-cap clusters/items → **422** (Pydantic `max_length` + `render_document` total cap).
- Position-aware correctness pinned: IEEE renumbers `[1][2][3]` and the **same** citation gets a different number
  when the document order reverses; APA disambiguates `2020a`/`2020b` across the document
  (`test_render_document_ieee_numbering_and_renumber`, `test_render_document_apa_disambiguation`).

## Principles gate (rule #9)
Clears. A **deterministic render of the user's own document data** in their chosen CSL style — no LLM, no egress,
no claim/signal/judgment about the literature, no provenance/fact-vs-candidate posture changed. It is the
word-processor adapter substrate, not an assertion. Honors credit-the-lineage via the inc-106
`THIRD-PARTY-NOTICES.md` (unchanged — same citeproc-js + bundled CSL).

## Follow-ups (non-blocking)
- A shared `timeout=` on the citeproc/esbuild `subprocess.run` calls (defense-in-depth resource cap), if/when
  the app is ever hosted. Today it is local, single-user, 127.0.0.1.

## Result
**Security Audit: PASS** — additive, local, fail-closed, output-sanitized, input-capped; no egress, no new
dependency, no SQL, no file-path-from-input.

## Addendum (2026-07-23) — P1 item #11 (backlog #33/#34): bibliography editing

**Trigger:** audit gate #1 (request-schema change to this existing endpoint). Adds two new **optional,
additive** fields to `RenderDocumentRequest`: `uncited_items: list[UncitedItem] = []` (bibliography-only
"further reading" entries — same CSL-JSON shape as a `CitationItem`, `extra="allow"`, requires only `id`) and
`bibliography_exclude_ids: list[str] = []` (cited works to omit from the rendered bibliography while their
in-text citation is unaffected — e.g. a personal communication). Both mechanisms are **real, pre-existing
citeproc-js capabilities** (`engine.updateUncitedItems`, `engine.makeBibliography({exclude: [...]})` — confirmed
in `node_modules/citeproc/citeproc_commonjs.js`), newly wired through this endpoint; no new library, no new
egress, no new SQL.

- **Input validation / boundary (rule #4).** `uncited_items` capped at `MAX_ITEMS_PER_CLUSTER` (50);
  `bibliography_exclude_ids` capped at `MAX_CLUSTERS` (5000) — both existing, already-audited constants, no new
  magic numbers. Each uncited item is validated the same way a citation item already is: must carry an `id`
  (422 otherwise, via the same `ValueError` → 422 path `render_document` already uses). Exclude ids are coerced
  to `str` defensively before reaching the sidecar.
- **Injection / sidecar boundary.** Both new fields ride the exact same fixed-argv `node <runner>` subprocess
  with JSON on stdin — no new subprocess invocation, no new command construction. `bibsection.exclude` matches
  `item[field] === value` inside citeproc-js's own engine (a pure in-memory JS comparison over the already-
  trusted item objects this endpoint already builds) — the `field` used is always the literal string `"id"`,
  never taken from request data, so there is no way for a caller to make the filter target an arbitrary
  property.
- **Output.** Unaffected — the response shape (`citations`, `bibliography_text`, `bibliography_html`) is
  unchanged; the same `_safe_html`/`_to_text` sanitization already applies to every bibliography entry,
  including the new uncited ones (they flow through the identical `makeBibliography()` → sanitize path as any
  cited work).
- **Backward compatibility.** Both fields default to empty lists — an existing caller (any adapter that predates
  this change) sending no `uncited_items`/`bibliography_exclude_ids` at all gets byte-identical behavior to
  before (`test_render_document_bibliography_editing_fields_are_optional`).
- **Negative-path checks:** an uncited item missing `id` → 422
  (`test_render_document_uncited_item_missing_id_rejected`); a real end-to-end check that an excluded work's
  in-text citation still renders while its bibliography entry disappears, and that an uncited item appears in
  the bibliography with no matching in-text citation
  (`test_render_document_bibliography_exclude_removes_entry_but_keeps_in_text_citation`,
  `test_render_document_uncited_item_appears_in_bibliography_with_no_in_text_citation`).

**Security Audit (addendum): PASS** — additive, same fail-closed/sanitized/capped posture as the original audit;
no new attack surface introduced by either new field.
