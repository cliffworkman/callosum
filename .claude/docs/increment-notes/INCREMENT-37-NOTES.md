# Increment 37 Notes — Modularize the monolith files

Behavior-preserving refactor to bring the oversized files under the 600-line rule and make the
codebase reviewable in directed passes (one concern per descriptively-named file). **No endpoint,
response-shape, schema, or behavior change.** Guardrails held green after every phase: `pytest`
(129), the route-surface invariant test (no endpoint drift), and the inc-36 headless E2E (frontend).

## Phase 1 — `app/backend/api/app.py` (1108 → 113), split into a factory + routers
- `app.py` is now a thin factory: `create_app`, lifespan (startup auto-migrate), CORS, state wiring,
  `include_router(...)`, the `/` frontend route, and `app = create_app()`.
- New: `dependencies.py` (`get_connection`); `startup.py` (logger + `_loud`/`_alembic_config`/
  `_head_revision`/`_current_revision`/`_upgrade_database_to_head` + `PROJECT_ROOT`);
  `routers/{health,papers,annotations,axes,summaries}.py` — each co-locates its Pydantic models +
  helpers + handlers (a `health.py` also owns `_database_status`).
- Only logic change: the two `/summarize*` handlers read the job store via `request.app.state`
  instead of the `create_app` closure (so they live in a module-level router). Sizes: summaries 387,
  papers 302, annotations 204, startup 102, health 59, axes 68, dependencies 12.
- `test_startup_migration.py` now binds `app.backend.api.startup` (where the migration code moved).

## Phase 2 — `app/backend/pdf_processing/extraction.py` (662 → 555) + `quote_matching.py` (130)
- Lifted the quote→coordinate matching (`locate_quote`, `_word_tokens_for_pdf`, `_line_rectangles`,
  `QuoteMatch`) into `quote_matching.py`; it imports the canonicalization + `_WordToken` +
  `_rect_to_dict`/`_normalize_space` from `extraction.py` (one-directional, no cycle).
- `__init__.py` re-exports `locate_quote`/`QuoteMatch` from the new module; importers updated
  (`location.py`, `tools/validation_harness.py`, `test_pdf_processing.py`, `test_summarization.py`).
  The pdf test's `_word_tokens_for_pdf` monkeypatch now targets `quote_matching`.

## Phase 3 — `tests/test_api.py` (~1160) → conftest + per-resource (AST splitter, no transcription)
- `tests/conftest.py` (the `temp_db_url` fixture) + `tests/api_helpers.py` (shared seeds/fakes:
  `_seed_library`, `_seed_summarization_library`, `_summarization_app`, `ApiFakeEmbeddingModel`,
  `ConstantSupportScorer`, `_api_vector`, `_annotation_body`) + `test_{health,papers,axes,
  annotations,summaries}.py`. Same 36 api tests, redistributed; suite count unchanged (129).

## Phase 4 — `tools/validation_harness.py` (1298 → 898) — reports + renderer extracted
- New `tools/validation/reports.py` (the report dataclasses) + `report_renderer.py`
  (`render_markdown_report`); the harness re-exports them so `from tools.validation_harness import …`
  and the 532-line harness test still resolve. **The probes + orchestrator remain in
  `validation_harness.py` (898 lines).** `tools/` is exempt from the 600-line rule; the dense
  probe↔orchestrator coupling + deep test reliance make a per-probe split higher-risk for low
  rule-value, so it is **deferred** (a clean follow-up). The two most self-contained concerns (data
  model + markdown rendering, ~450 lines) are now separately reviewable.

## Phase 5 — `callosum-app.html` (2023) → modular `app/frontend/` assembled at serve time
- Source: `app/frontend/index.html` (shell template, favicon base64 inline) + `styles.css` (496) +
  `js/{00_lib,10_pdf_layer,20_synthesis,30_viewer,40_app}.jsx` (≤499 each; logo base64 inline in
  `10_pdf_layer.jsx`).
- New `app/backend/api/frontend.py::build_frontend_document` reads the template + CSS + the sorted
  `js/*.jsx` and assembles them into ONE document at `/` — the JSX is concatenated into a single
  `<script type="text/babel">` (no module boundaries) so the shared global scope is **identical** to
  the former single file. Cached after first build. The splitter asserted byte-faithful reassembly
  (assembled doc = 2023 lines, same as the original).
- Default now assembles; `CALLOSUM_FRONTEND_PATH`/`frontend_path` still overrides with a single
  prebuilt file (back-compat — the frontend tests use this). `callosum-app.html` was **deleted**
  (rule #5). `tools/inline_brand_assets.py` was updated to re-inline into the new source.
- **No new file-serving surface** (no `StaticFiles`, no per-asset routes) — preserves the project's
  frontend invariants. See `.claude/security-audits/2026-06-17_frontend-assembly.md`.
- **Follow-up (same day):** `callosum-app.html` is preserved as a **generated build artifact** —
  `tools/build_frontend.py` rebuilds it from `app/frontend/` (verified **byte-identical** to the
  pre-split original, CRLF preserved), and `/` serves it by default (with live assembly as the
  fallback). This keeps file-based frontend testing working. Trade-off: re-run `build_frontend.py`
  after editing `app/frontend/` (the live-assembly fallback keeps the running server correct
  meanwhile). The earlier "delete callosum-app.html / default to serve-time assembly" decision is
  superseded by this.

## Key technical detail
The frontend split is only safe because assembly **concatenates the JSX chunks in filename order
into one script** — the numeric prefixes (`00_…40_`) encode the definition order React needs (every
top-level `const`/`function` defined before `App` uses it). Splitting into separate `<script>` tags
(or ES modules) would break the shared global lexical scope; serve-time concatenation does not.

## Verification
- `pytest`: **129 passed** after every phase (route-surface invariant green throughout → no endpoint
  drift). Final: no file under `app/` or `integrations/` exceeds 600 lines (largest `extraction.py`
  555).
- inc-36 headless E2E re-run against the **assembled** frontend: gating + save + live-refresh +
  **reload-drift 0.0px + 0 console errors** (proves faithful in-browser reassembly).
- `tools/validation_harness.py --help` / import OK; brand-assets tool locates both assets.

## Rough edges / deferred
- `tools/validation_harness.py` remains 898 lines (exempt). Per-probe split (pdf/zotero/retrieval/
  axis/summarization) deferred — offered as a focused follow-up.
- Several router/test modules carry a few unused imports inherited from the original shared header
  (harmless; tools/tests aren't held to the app-source bar).
