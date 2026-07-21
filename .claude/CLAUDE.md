# CLAUDE.md — callosum base of operations

This file is the session-start briefing for any Claude Code session opened at the callosum
project root. It describes what callosum is, the non-negotiable design invariants every
change must honor, how to run and verify the project, the rules every edit follows, and the
operational conventions that keep the project sane across sessions. **Read it before changing
anything.**

`.claude/` (this file's home) is **dev-only working space — never part of the shipped
application.** Temporary scripts, backups, research, audits, and plan files all live here.

---

## Project overview

**callosum** is a **local-first, AI-assisted reference manager for scholarly PDFs**, built
around one thesis: *LLM summaries are only trustworthy if every citation is independently
verified against the source PDF.* You import a library (Zotero first), the app extracts and
chunks each PDF with page + bounding-box coordinates, embeds everything locally, clusters
papers along user-defined semantic axes, and generates citation-grounded summaries where
**every sentence is checked back against the source and shown with its evidence** (quote,
page, confidence).

It is currently at **Increment 325** (see Increment workflow) with **1323 pytest tests
passing** (+ 1 skipped + the optional `mcp` suite; + opt-in browser smoke + the inc-120 Codex-driven QA route suite). It is a working MVP backed by a
thorough planning suite in `.claude/docs/`.
(Increments 109–116 — frontend/UX TDL items incl. the inc-110 PDF page-view — are journaled in `RECOVERY-LOG.md`;
the full per-increment narrative for all other increments now lives in the relocated
`.claude/session-kickoff-log.md`, and the detailed per-increment diary in `.claude/docs/increment-notes/`.)

**Stack:**
- **Backend:** Python 3.11+, FastAPI + Uvicorn (`app/backend/api/app.py`).
- **Persistence:** SQLite via SQLAlchemy Core 2.0; Alembic migrations (`alembic/`).
- **Vectors:** `sqlite-vec` (in-process, no separate daemon) + sentence-transformers
  (default embed model `all-MiniLM-L6-v2`; `bge-base-en-v1.5` also supported).
- **Clustering:** scikit-learn agglomerative clustering + local axis scoring.
- **Methods (deterministic, local, no-LLM):** statcheck NHST p-value recomputation (`scipy.stats`), inc 95.
- **Citations (formatted):** **citeproc-js** run as a Node sidecar (same subprocess pattern as esbuild) over
  bundled CSL styles/locales → formatted in-text citations + bibliographies from `papers.csl_json`
  (`app/backend/citations/`, inc 106). The **word-processor-integration spine** (adapters ride this engine):
  inc 106 renders a *selection* per-item; **inc 107 adds position-aware *document* render** (`render_document` /
  `POST /citations/render-document`, `rebuildProcessorState` — numeric renumbering + author-date disambiguation
  across an ordered document — the contract the LibreOffice/Word/Docs adapters call). Local, no egress.
  `citeproc` is an npm dep (`package.json`); see `THIRD-PARTY-NOTICES.md`. **inc 108** ships the **first adapter**:
  a LibreOffice (UNO) cite-while-you-write macro (`adapters/libreoffice/`) that places ReferenceMark live fields +
  rides `render-document` — client-side, no server change.
- **PDF:** PyMuPDF (`fitz`) for text + bbox extraction.
- **LLM (selective, multi-provider — inc 149; unified editable roster — inc 256):** all generators route through
  one `app/backend/llm/providers.py::complete(config, prompt)` seam. The provider set is **one editable list**
  (`app/backend/providers_store.py`): four pre-seeded builtins — **Gemini** (`google-genai`, default
  `gemini-2.5-flash-lite`) / **OpenAI** / **Anthropic** / a **local** OpenAI-compatible endpoint (Ollama etc.) —
  **plus user-added custom providers** `{name, base_url, api_key, wire_format ∈ messages|chat_completions|responses,
  models[]}` (any OpenAI/Anthropic-compatible endpoint: DeepSeek, Together, Groq, OpenRouter, vLLM). The builtins
  are **synthesized on read** (never persisted); only `custom_providers` + id-keyed secrets are stored (additive,
  no migration; the active selection reuses the flat inc-149 `provider`/`model` fields). `complete()` dispatches on
  `config.wire_format` (gemini-SDK / `{base}/v1/messages` / `{base}/v1/chat/completions` / `{base}/v1/responses`),
  all non-gemini via **httpx** (no new dep). LLM is **generation only** (summary, axis-terms, research summary,
  overview, help, and — inc 259 — **assisted extraction**) and **OFF by default** (egress gate, invariant #3). The
  **assisted-extraction funnel** (inc 259: `routers/workbench.py` propose/accept/reject
  + `integrations/gemini/extraction_assistant.py` + `app/backend/workbench_assist.py`) has the LLM *propose* meta-analysis
  cell values as **candidates** (the isolated `ma_proposals` table + `ma_cells.origin`, migration 0034) that a human
  verifies/accepts before any enters the trusted `ma_cells`/converter/exports — **AI funnel, human filter**; each
  candidate's anchor is decided **deterministically-locally** (`locate_quote` → exact/region/unanchored, invariant #2),
  never by the model, and egress rides the same `EgressGatedExtractionAssistant`. **Egress is endpoint-based** (inc 256):
  `requires_egress(config)` gates any **non-loopback** base URL exactly like Gemini, while a **loopback** provider
  (local or a custom `127.0.0.1` endpoint) runs with **zero egress** — so an arbitrary user URL honors #3 for free.
  Verification NLI runs locally (`cross-encoder/nli-MiniLM2-L6-H768`).
- **Frontend:** modular source under `app/frontend/` (`index.html` shell + `styles.css` +
  ordered `js/*.jsx` React chunks, React/ReactDOM + pdf.js via CDN), assembled by
  `app/backend/api/frontend.py`: the JSX chunks are concatenated and **precompiled to plain JS by
  esbuild at build time** (inc 102 — `package.json` pins esbuild; `npm install` once), then injected
  into one `<script>`. (Through inc 101 the JSX was transpiled in-browser by `babel-standalone`;
  precompiling dropped that ~500KB CDN download + runtime transform + its dev-console warnings.)
  `tools/build_frontend.py` rebuilds the single-file `callosum-app.html`; FastAPI serves it at `/`
  by default, falling back to live assembly if it's absent. No bundler (just a transpile pass), no
  extra file-serving surface (esbuild emits one IIFE, so the chunks' shared scope is preserved); the
  **server stays Python-only** — it serves the prebuilt file, never running Node at serve time.
  **Run `npm install` once, then re-run `python tools/build_frontend.py` after editing anything under
  `app/frontend/`.**
- **HTTP client:** httpx (external metadata/discovery APIs).

> **README:** brought current in **inc 178** (the contributor front door — accurate feature list + the
> `npm install`/`build_frontend` step + privacy/security notes). Shipped as a **draft pending the maintainer's
> voice pass + a screenshot** (a `<!-- TODO(maintainer) -->` placeholder marks the screenshot). Still defer to this
> file + the code for the authoritative current state; keep the README current opportunistically.

---

## Core design invariants (NON-NEGOTIABLE)

These are the soul of the project. A change that violates one is wrong even if it passes
tests. The analogue of a brand promise: never break it.

1. **External LLM output is never authoritative citation evidence.** Gemini proposes summary
   sentences and *candidate* citations; the app then **independently verifies** each sentence
   against the source via local embedding similarity + NLI stance classification + verbatim
   quote extraction (`app/backend/summarization/verification.py`,
   `VerificationConfig`: retrieval ≥ 0.7, quote = 1.0, support ≥ 0.55). A sentence is shown
   as verified, contrasted, or **flagged** — never silently trusted.

2. **The coordinate honesty contract.** A citation's `coordinate_precision` is one of
   `exact` / `region` / `null`. **Exact** draws precise bbox rectangles; **region** scrolls to
   the page and shows an approximate-location note; **null** opens the page (if known) and
   draws nothing. Region-level or absent coordinates are **never** presented as exact passage
   highlights. The stored coordinate system is `pdf-points-top-left` (`COORDINATE_SYSTEM` in
   `app/backend/pdf_processing/extraction.py`); overlays are positioned as percentages of the
   page so they stay aligned across zoom. Rotated pages: open the page, draw no exact rect.

3. **Local-first, egress-off by default.** All heavy lifting — extraction, embeddings, vector
   search, clustering, verification — runs **locally**, and the app stays useful **offline**
   after import. The *only* thing that can leave the machine is Gemini summary generation, and
   it is **disabled unless the user explicitly opts in** via `CALLOSUM_ALLOW_DATA_EGRESS`
   (`1`/`true`/`yes`); otherwise `DataEgressDisabledError` is raised
   (`integrations/gemini/generator.py`). Never add a code path that sends library text to a
   remote service without routing through that consent gate.

4. **Evidence always shown; verification is probabilistic, not proof.** Confidence scores,
   quotes, and page numbers are always visible. The score reflects semantic + lexical overlap,
   not logical entailment — the user sees the quote and decides. Never hide a low-confidence or
   flagged claim.

---

## Principles alignment gate (read `.claude/PRINCIPLES.md`)

The Core design invariants above are the load-bearing few; **`.claude/PRINCIPLES.md` is the full charter** —
ten commitments (every claim carries its evidence; signal not verdict; facts ≠ candidates; the deterministic
substrate is the source of truth and the model only narrates it; the human is the filter / the AI is the
funnel; silence is not a certificate; no opaque composite scores; inspectability over authority; defaults are
the user's; local-first & provider-swappable), the strict **THEORY contract**, and four worked
**aligned-vs-misaligned** examples. The misaligned path is almost always the smaller, faster, demo-friendlier
one — so it has to be declined on purpose.

**The gate is a *reflective pause*, not an absolute block.** Before you **add or remove** functionality that
produces a claim / signal / judgment about the literature, or that changes the inspectability, provenance,
fact-vs-candidate, or egress posture:

1. **Name the principle(s) it touches** and the worked example in PRINCIPLES.md it most resembles — read that
   example's real implementation (it points at one) before building the analogous thing.
2. **Name the misalignment it is most at risk of** — usually the easier implementation.
3. **If the change is at odds with a principle, don't just flag it — propose the aligned alternative.** The
   deliverable is *what could be right*: a design that honors the feature's intent while cohering to the
   principles. Surfacing the conflict is the cheap half; the valuable half is the version that keeps the
   commitment. (*Easy to see what's wrong; harder and more valuable to see what could be right.*)

If a feature genuinely cannot be built to honor the principles, that is a **finding about the feature, not a
reason to relax them** — report it as such. This applies to **removals** too: deleting an evidence surface, a
confidence display, a provenance field, or a fact/candidate distinction is itself a principle-level change.

**Values layer — `.claude/APPROACH-AVOIDANCE.md` (the deeper, *conditional* layer).** Beneath the charter sits
the **value substrate** — the commitments that *generate* the principles (8 approach values + standalone
avoidance boundaries + a four-way drift typology). It is reached for **only when the principle pass above
doesn't resolve or doesn't trigger** — i.e. for a **novel / value-level / future-track** change — **never** as
a second mandatory read on an ordinary gated edit (PRINCIPLES + the Core invariants stay the first, primary
pass; this layer adds depth without taxing the cases the principles already cover). Consult it when:
- **No principle or worked example fits** (a genuinely novel case) → **derive the check from the relevant value.**
- The change touches **value-level** posture the principle triggers can miss: **access / licensing /
  distribution (equity), the acquisition boundary, anything that could introduce accusation, or a
  cost-vs-verification/consent trade-off** — or it **adopts an emergent value** (a commitment not yet in the
  built artifact).
- It is **future-track / planned** work → run A-A's **drift typology** (confirmed / extended / emergent /
  divergent); **flag emergent values** ("adopt deliberately, don't drift into it") and **divergent tensions**.
- **Veto-level:** A-A's **standalone hard boundaries** (no paywall circumvention; no reaching into other
  tools' protected stores; no accusation of individuals) are **veto-level**, alongside the Core invariants —
  they have no "aligned alternative"; they are lines the tool does not cross.

Same philosophy throughout: a **reflective pause, not a block**, and *propose the aligned alternative, don't
just object*. A feature that cannot honor the values is a **finding about the feature** too.

---

## Rule priority & exceptions

When instructions conflict, apply this order:

1. **Security + data safety** (incl. the egress gate) — never bypass.
2. **Verification requirements** — follow unless the tooling is genuinely unavailable; if so,
   say so explicitly and flag it as a follow-up.
3. **Workflow defaults** (planning, backups, hygiene) — adaptable for trivial edits.

If a hard requirement can't be met, report: what failed, the impact, and the follow-up action.

---

## Commands

Run from the project root. The shell is **PowerShell** (Windows).

| Command | Description |
|---|---|
| `$env:CALLOSUM_DB_URL = "sqlite:///C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum/.local/validation-summarize/validation.sqlite"` | Point the app at a SQLite DB (default if unset: `sqlite:///.local/validation/validation.sqlite`) |
| `uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080` | Start the FastAPI app; then open `http://127.0.0.1:8080/` |
| `npm install` | Install the build-time frontend toolchain (pinned `esbuild`) — required once before `tools/build_frontend.py` / live assembly (inc 102) |
| `python tools/build_frontend.py` | Rebuild `callosum-app.html` from `app/frontend/` (esbuild-precompiles the JSX) — run after any `app/frontend/` edit |
| `pytest tests/test_<area>.py -q` | **Default dev loop — run only the changed area's tests** (seconds, not ~45 min). See the Verification protocol §1. |
| `pytest --testmon -q` | Run only tests whose covered code changed since the last run (pytest-testmon, inc 300; first run builds `.testmondata`) |
| `pytest -n auto -q` | Full suite in **parallel** (pytest-xdist, inc 300) — ~3-4× faster; use before merge (CI runs this) |
| `pytest` | Full test suite, **serial** (`testpaths=tests`, `pythonpath=.`) — slow; prefer `-n auto` for full runs |
| `pytest tests/test_api.py -k summary` | Run a focused subset (by name) |
| `alembic upgrade head` | Apply DB migrations |
| `alembic revision -m "<desc>"` | Create a new migration (no down-migrations by design) |
| `python tools/validation_harness.py` | Run the PDF→extract→embed→retrieve→summarize validation harness (writes a `validation.sqlite` + report + debug images under `.local/`) |
| `python tools/enrich_metadata.py` | Batch metadata enrichment (OpenAlex/Crossref) |
| `python tools/backfill_keyword_tags.py` | Backfill Crossref `subject` categories as `keyword:crossref` tags across the library (cache-first; tag-only; idempotent — inc 73) |
| `$env:GOOGLE_API_KEY = "..."; $env:CALLOSUM_ALLOW_DATA_EGRESS = "1"` | Enable Gemini summary generation (off by default) |

`CALLOSUM_FRONTEND_PATH` overrides the served frontend with a single prebuilt HTML file; unset (the
default) assembles the modular source under `app/frontend/` at serve time.

---

## Directory layout

IF NEEDED, see "directory-layout.md."

---

## The rules

### 1. 600-line hard limit on application source

Any file under `app/` or `integrations/` must stay **under 600 lines**. Files approaching it
are split proactively; a file that crosses it MUST be modularized before the next feature
lands in it. Split by concern — routers, repositories, pipeline stages, adapters — and keep
shared/core code loading first.

**Exempt-but-watched:** `tests/` and `tools/` (the validation harness is allowed to be large),
and non-code (Markdown, SQL, config).

**Standing split tasks:** none — the tree is **fully under the 600-line cap.** (The long-flagged
`app/frontend/js/15_axes.jsx` violation — 614 since inc 211/212 — was cleared in **inc 222**: the axis-card subsystem
[`AxisItem` + its presentational helpers `axisConfidenceLabel`/`AxisTierBadge`/`AxisPaperRow`/`AxisCutoffFlipper`/
`_tierRank`] moved verbatim → new `js/15b_axis_card.jsx` [224]; `15_axes.jsx` 614→**395** [`AxesPanel` + `MyPubsPrompt`
+ `registerPaneTab`]. Hoists across the shared IIFE — the inc-208 `10b_libmenus.jsx` precedent. Behavior-preserving,
proven by baseline-then-after on `drive_inc212_dragreorder.py` + `drive_inc204_hide_uncertain.py`.) **Inc 221** split the App god-component
`app/frontend/js/40_app.jsx` (599→**212**): the library-list subsystem (filters/fetch/bulk/saved-searches/chips/findings)
→ `js/03_library.jsx`'s **`useLibrary`** hook (351; the focus↔library cycle broken with two refs). **Inc 167** split `app/frontend/js/40_app.jsx` (630→551:
the axis focus-mode → `js/39_focus.jsx`'s `useFocusMode` hook; the citation-download helpers → `js/00_lib.jsx`) —
**frontend chunks count too** (they're under `app/`). **Inc 176** extracted the Notes panel from `js/30_viewer.jsx`
(595→573) into `js/30b_notes.jsx` (`AnnotationsPanel`); the reading-pane run (175–179) re-grew it to 599/600, then **inc 182 extracted `LibraryFrame` → `js/30c_frame.jsx`**
(30_viewer 599→**557**). **Inc 207** split `js/25_detail.jsx` (609→**522**): `TagsRow` → new `js/25b_tags.jsx`. **Inc 208** split
`js/10_pdf_layer.jsx` (602→**547**, over the cap when the SavedSearchMenu landed): both library-header dropdowns
(`AddMenu` + `SavedSearchMenu`) → new `js/10b_libmenus.jsx` (62) — called via the shared-IIFE function hoist.
**Inc 209** kept the full-text mode self-contained (`js/10c_fulltext.jsx`'s `FulltextResults` does its own fetch) so
`js/40_app.jsx` stayed at 599 + `js/10_pdf_layer.jsx` rose only to **555** (the scope option + the swap branch).
**Inc 210** (A2 citation counts): `CitationCountsButton` → `js/10b_libmenus.jsx` (**93**); `js/10_pdf_layer.jsx`
**562** (chip + Most-cited option + control); `js/40_app.jsx` held at **599/600** (the new prop folded onto an
existing line — split before the next addition there). **Inc 211** (A7 SP1 curated axis): `js/15_axes.jsx` grew to
**551** (the `isCurated` branch + freeze/convert/reorder) — comfortably under; `js/40_app.jsx` untouched.
**Watch (re-measure):** `js/30_viewer.jsx` (**580**, +23 from the inc-215 minimap; was 557, NOT the stale-noted
599/600 — inc-182's LibraryFrame extraction had relieved it), `js/10_pdf_layer.jsx` (**581**) — the closest frontend
chunks now that inc-221 took `js/40_app.jsx` to **212** and inc-222 took `js/15_axes.jsx` to **395**. **Inc 214** split `routers/papers.py` (604→**510**, over the cap when the #5 `extra_urls`
field landed): the request-normalisation cluster (`edits_from_request` + `_clean_*`/`_validate_csl_patch` + the caps
constants) → new `routers/paper_edit_input.py` (111; duck-typed on the request → no import cycle). **Inc 137** split
`schema.py` (611→558, over the cap
since inc 130/132): the findings/signals/retraction/gap tables moved to `persistence/schema_findings.py` on a
shared `persistence/schema_base.py` `metadata`, re-exported from `schema.py` (zero blast radius). **Inc 91** split
`repository.py` (625→538, → `persistence/annotations_repo.py`) and `routers/papers.py` (600→539, → `routers/paper_files.py`).
**Inc 220** split `repository.py` (662→**565**, a pre-existing violation the watch note had drifted on at "~556"; the
read/priority feature landed in it): the paper-lifecycle cluster (trash/purge/tier + the new read/priority setters)
→ `persistence/paper_lifecycle_repo.py` (121) and the synthesis CRUD → `persistence/summaries_repo.py` (61), both
**re-exported** from `repository` (`# noqa: E402,F401`; zero call-site change — the inc-137 pattern).
**Inc 226** split `routers/papers.py` (598→**528**, was at the 600 cap when the per-identifier `source` field landed):
the enrichment-action endpoints (`reresolve_paper` + `fill_metadata` + `FillMetadataResponse` + `_crossref`) → new
`routers/paper_enrich.py` (113; imports `PaperDetailResponse`/`_detail_for` from papers.py, no cycle).
**Inc 256** split `js/35_settings.jsx` (604→**471**, over the cap when the unified-provider-roster UI landed): the
whole AI-features block (`AiSettings` + `ProviderRow` + `AddProviderForm`/`ProviderFields`/`ProviderModelsEditor`)
→ new `js/35b_providers.jsx` (**362**) via the shared-IIFE function hoist (the inc-208/222 precedent — `AiSettings()`
is called unchanged from `SettingsModal`).
**Inc 262** cleared two pre-existing violations (backlog #47; both had drifted over-cap through inc 261 while the
watch-list stayed stale): `routers/methods.py` (619→**450**) peeled the retraction endpoint cluster (per-DOI
detection + the Retraction Watch DB mirror) → new `routers/methods_retraction.py` (186; shares `request.app.state`,
mounted beside `methods.router` in `app.py` — the inc-226 `paper_enrich.py` sibling-router pattern; also removed
the dead `import logging`/`_log`), and `persistence/schema.py` (628→**558**) extracted the summary/citation-mapping/
evidence-quote table group → new `persistence/schema_summaries.py` (107) on the shared `schema_base` `metadata`
(the inc-137 pattern; the `enum_check`/`non_empty_check` helpers + `CITATION_MAPPING_STATUSES` moved to
`schema_base` too so both files share one definition without a circular import; re-exported from `schema.py`).
**Inc 264** cleared two more drifted files — caught by the new line-budget gate, not a human: `routers/axes.py`
(609→**513**) peeled its 14 request/response models + their field-cap constants → new leaf `routers/axes_models.py`
(125; imports only pydantic/stdlib, re-imported into axes.py — the inc-137 leaf pattern), and `js/10_pdf_layer.jsx`
(604→**507**) moved the paper-card cluster (`ClipboardIcon`/`CheckIcon`/`PaperCopyButton`/`PaperCard`) → new
`js/10d_papercard.jsx` (100; the inc-208/222 shared-IIFE hoist).
**The 600-cap is now machine-enforced (backlog #20 ratchet step 1) — the hand-maintained watch list is retired.**
`tools/check_line_budget.py` fails on any over-cap `app/`/`integrations/` `.py`/`.jsx`, wired into a **git
pre-commit hook** (`tools/git-hooks/pre-commit`; install once per clone: `git config core.hooksPath tools/git-hooks`)
**and CI**. Run **`python tools/check_line_budget.py --list`** for the live closest-to-cap files instead of trusting
prose — the old watch list kept drifting stale (it missed axes.py at 609 and 10_pdf_layer.jsx at 604), which is
exactly why the check is now automated.
(The editable Detail pane lives in its own chunk `app/frontend/js/25_detail.jsx`; the edit-mapping logic is
`app/backend/metadata/paper_edits.py`.)

**Watch (exempt but large):** `tools/validation_harness.py` (~898 — inc 37 extracted the report
dataclasses + markdown renderer to `tools/validation/`; the probes remain, a candidate for a future
per-probe split). Tests are now per-resource (`tests/test_papers.py`, etc.) sharing
`tests/conftest.py` + `tests/api_helpers.py`.

### 2. Secrets in the environment, never in code

`GOOGLE_API_KEY` (Gemini) and `CALLOSUM_DB_URL` come from the environment. Never commit a key
or hardcode one in a `.py` file. Non-secret constants (model names, thresholds, table names)
are fine as literals. When a `.env` is introduced, it must be gitignored. **BYOK (inc 146):** a user can also
set the Gemini key + egress consent from Settings; they persist either in the **OS keychain** (inc 152, optional `keyring`) or in a local file at
`~/.callosum/app-settings.json` (`app/backend/app_settings.py`; override `CALLOSUM_SETTINGS_PATH`) — outside the repo
+ the synced Dropbox folder; multi-provider (Gemini/OpenAI/Anthropic/local) since inc 149.
The key is **write-only over the wire** (`GET /settings` returns a set/not-set status, never the value), never
logged, and `GeminiConfig.from_environment()` overlays it over the env fallback. Egress stays default-off.

### 3. Parameterized SQL only

Use SQLAlchemy Core bound parameters. Never interpolate user/external input into SQL text.
Table and column names come from constants or allowlists, never from request data. This
discipline is what keeps a single flaw from becoming a compromise if callosum ever goes public.

### 4. Validate untrusted input at the boundary

PDFs and external-API responses are **untrusted**:
- **PDFs:** validate/decode on ingest (`app/backend/pdf_processing/ingest.py`), cap sizes,
  never build a filesystem path from an unsanitized user-supplied name.
- **External APIs** (OpenAlex, Crossref, Gemini, sci-hub/Unpaywall): validate response shape,
  set httpx timeouts, fail closed. The local-app threat model is **resource exhaustion** and
  **untrusted-content handling**, not SQLi — but rule #3 still holds.

### 5. Delete dead code immediately

If a function, file, variable, or asset is unused, remove it — don't comment it out or rename
it with a leading underscore. Zip snapshots + Dropbox history are the recovery net. Leave every
file you touch leaner than you found it. The project is pre-release with one user — there is no
backwards-compatibility debt to preserve.

### 6. Keep CLAUDE.md current

When a change affects architecture, conventions, the directory layout, commands, the design
invariants, or any workflow documented here, **update this file in the same session**. Drift
here is how institutional knowledge rots.

### 7. Minimal diffs; understand before changing

Make the smallest change that solves the problem. No drive-by refactors bundled into a feature
change. Read and comprehend the relevant code — and this file — before modifying. Rules apply to
the edit you're about to make; they aren't retroactively reinterpreted.

### 8. Design consistency: read `DESIGN.md` before any CSS change

**Before editing `app/frontend/styles.css` or any inline `style={{…}}`, read
[`.claude/DESIGN.md`](DESIGN.md)** — the design dictionary (tokens, element recipes, the fixed semantics
of color/type, and the consolidation worklist). New controls conform to an existing recipe + reference a
token; never re-type a raw hex a token already names, and don't borrow one semantic color for another
(indigo = provenance/primary; green = verified; amber `--flag` = unresolved/uncertain/region status; red
`--danger` = destructive). If a change reveals a new inconsistency, record it in `DESIGN.md`'s Pass-2
worklist. This exists to stop design-by-committee drift as new UI lands in the existing codebase.

### 9. Principle fidelity: run the Principles alignment gate before claim/signal features

**Before adding or removing any functionality that produces a claim/signal/judgment about the literature — or
that changes inspectability, provenance, the fact-vs-candidate distinction, or the egress posture — run the
[Principles alignment gate](#principles-alignment-gate-read-claudeprinciplesmd)** (read `.claude/PRINCIPLES.md`
first). Name the principle(s) touched + the worked example it resembles; name the easier, misaligned path; and
when at odds, **propose the aligned alternative** — design *what could be right*, don't just object. A feature
that can't honor the principles is a finding about the feature. For **novel / value-level / future-track**
changes (where no principle directly fits), the gate also consults the deeper **values layer**
(`.claude/APPROACH-AVOIDANCE.md`) — derive the check from the value, run its drift typology, and honor its
veto-level boundaries; it is conditional, not a second mandatory read.

### 10. QA coverage: read `.claude/QA-POLICY.md` before changing an end-user surface

**Before adding or altering any end-user surface — a new API endpoint, a changed request/response contract, a
new interactive control, a new view-state, or a new async job — read [`.claude/QA-POLICY.md`](QA-POLICY.md) and
add or extend a QA route in the same increment.** QA coverage is a **computed property**:
`python tools/qa/build_surface_map.py check` diffs the surfaces declared by the routes in `.claude/qa-routes/`
against the surfaces that actually exist (88 API + ~460 frontend at inc 119). An uncovered **API** surface fails
the check (hard gate); uncovered **frontend** elements are reported as a checklist. Shipping a surface without a
route is the QA analogue of CLAUDE.md drift. Every route also asserts the project's honesty invariants (egress
gate, coordinate honesty, signal-not-verdict), so QA tests the soul of the app, not just that buttons click.
Security-class findings open a `.claude/security-audits/` stub via the existing audit gate — QA feeds it, never
duplicates it. The Codex-`exec` supervisor (`tools/qa/supervisor.py`) runs the routes and deposits reports to the
watched `.claude/qa-inbox/`; you are the triage-and-fix half (Session-kickoff step #11).

### 11. End-user experience: read `.claude/EXPERIENCE-PASS.md` before calling a user-facing change done

**Before any user-facing change is "done" — a new feature, a revised flow, a moved control, a new signal/output —
run the [end-user experience pass](EXPERIENCE-PASS.md).** Where DESIGN (#8) asks *does it look right*, PRINCIPLES
(#9) *is it honest*, and QA (#10) *does the surface work + is it covered*, this asks **does it actually serve the
user** — a change can pass all three and still strand a real person mid-task (a correct signal with no obvious path
to the action it implies; a feature buried where no one finds it; a number with no way to reach the evidence
behind it). **Inhabit the end user of the thing you touched** and ask: (1) **reception** — is it discoverable,
legible, is the next step obvious; (2) **intended use** — what does the user reach for next, does the built thing
support it or dead-end (vigilance: a desire that conflicts with our commitments — accusation, paywall
circumvention, an opaque score — is **declined** per #9 + APPROACH-AVOIDANCE, not served). For a **newly
rolled-out or materially-changed** feature, **dispatch a persona-grounded experience agent** (or more than one) per
the doc's mechanism — a subagent *in character* as a concrete user with a goal-in-the-moment (e.g. the **deadline
citer** vetting a paper's stats before citing it), driving the feature and reporting what's left to be desired. A
**reflective pause, not a block**; the output is a finding — fix what's cheap in the same increment, else file a UX
follow-up to `INCREMENT-BACKLOG.md` (tagged to the persona it blocks) and record the pass in the increment notes.

---

## Increment workflow

callosum is built in **numbered increments** (currently at 325). Each increment of real work
produces an `INCREMENT-NN-NOTES.md` in **`.claude/docs/increment-notes/`** (all notes, oldest→newest,
live there) with this shape:

- **Implemented** — what changed, in which files.
- **Key technical detail** — the non-obvious math/contract (e.g., the coordinate transform).
- **Manual verification script** — exact steps to reproduce the check (start app, load X,
  click Y, confirm Z).
- **Pytest** — the passing count.

When you complete a meaningful increment, write its notes file in this shape and bump the
number. These notes are the running design diary; read the most recent few at session start.
**Keep this briefing small:** the per-increment *narrative* lives in `.claude/docs/increment-notes/`
(the historical narrative CLAUDE.md once carried in a footer is archived in
`.claude/session-kickoff-log.md`) — CLAUDE.md itself carries **no per-increment footer**; don't
recreate one here.

---

## Verification protocol

No change is "done" without verification appropriate to the surface it touches.

1. **pytest is the primary gate — but run it *targeted*, not whole, during dev (inc 300).** The full serial suite is
   ~45 min; **don't run everything for a localized change.** The suite is split per-resource, so:
   - **While developing:** run only the changed area's file(s) — `pytest tests/test_<area>.py -q` (feed →
     `test_feed.py`, discovery → `test_discovery.py`, queue → `test_reading_queue.py`, …); for any `app/frontend/`
     edit also run `pytest tests/test_frontend_assembly.py -q`. Or let **`pytest --testmon -q`** pick the affected
     tests automatically (change-based selection). These finish in **seconds**.
   - **Before merging / calling a multi-file change done:** run the full suite once — **`pytest -n auto -q`**
     (parallel, ~3-4× faster) — and it must be green. CI also runs `pytest -n auto -q`, so you can lean on CI for the
     full gate. Add/update tests for new behavior (the suite covers API, persistence, PDF extraction, embeddings,
     clustering, summarization, NLI). Report the actual pass count from whichever run you cite.
2. **Pipeline / retrieval / extraction changes:** run `python tools/validation_harness.py`
   against the library and eyeball the generated report + debug images in `.local/`. This is
   how extraction accuracy, chunking, embedding, and retrieval quality are checked end-to-end.
3. **UI changes (`app/frontend/*`):** start the app and run a **manual verification script**
   (the INCREMENT-29 pattern) — load a real synthesis, exercise the control you changed,
   confirm citations open the right PDF/page and that exact/region/null precision renders per
   the honesty contract. There is **no browser-automation dependency in the repo**; the
   Playwright MCP is session-level and optional. If you can't run a visual check, say so and
   flag it as a follow-up — don't claim a UI change is done on a static read alone.
4. **API/backend changes:** hit the endpoint, confirm status + response shape; for DB-writing
   paths, query before/after and confirm the delta.

---

## Workflow best practices

1. **Planning mode first for non-trivial work** (3+ files, architectural change, risky
   refactor). Single-file edits and typo fixes: execute directly.
2. **Understand before changing** — read the code and this file first.
3. **Minimal diffs** — no drive-by refactors in a feature change.
4. **Clean as you go** — remove dead code you encounter (rule #5).
5. **Security first** — never weaken an invariant; invoke the audit gate when triggered.
6. **Timestamped backups before risky edits** — zip snapshot or copy affected files into
   `.claude/backups/` before large refactors, schema migrations, or deletions.
7. **Verify, don't assume** — see the Verification protocol.

---

## Security baseline & audit gate

callosum is **local, single-user, no network exposure** today, but it is designed so it *could*
be made public later — so the discipline below is enforced now, not retrofitted.

**Currently in place:**
- No remote exposure; the app binds to `127.0.0.1` and CORS is restricted to
  `localhost`/`127.0.0.1`, GET-only, no credentials (`app/backend/api/app.py`).
- **Egress off by default** — Gemini calls require explicit `CALLOSUM_ALLOW_DATA_EGRESS`
  consent (invariant #3); the API key lives in `GOOGLE_API_KEY`, never in code.
- **Optional account is opt-in + identity-only (accounts SP1, inc 194).** "Sign in with ORCID"
  (`app/backend/api/auth/`, OIDC + PKCE) is **default-OFF** (no issuer/client_id env → no sign-in) and sends **no
  library text** — it verifies identity + populates My-Pubs only. Tokens are write-only (keychain/file, never in
  `GET /settings`); the redirect is loopback-validated; the `/oauth/callback` navigation is the only new gate
  exemption (opaque code+state).
- **Opt-in, E2E-encrypted cross-device sync (accounts SP3, incs 197–202).** The crypto + engine are local/no-egress
  (197–201); the **egress channel** is the opt-in `/sync/*` endpoints + the self-hostable **`sync_server/`** (inc 202):
  **default-off**, runs only when enabled + configured + signed-in, and **only opaque AES-GCM ciphertext** leaves (the
  DEK never does — E2E; the server can't read it). The Gemini library-text gate (#3) is a *separate* channel, untouched.
  Audits `2026-06-29_sync-crypto-sp3a.md` + `…_sync-engine-sp3b.md` + `…_sync-server.md` (PASS, + a 2026-07-20
  addendum on the latter). **SP3c (the Settings → Sync UI + conflict review) shipped incs 310–311** — conflict
  list/resolve endpoints, the setup/enable/run UI, and a conflict-review panel; browser-verified with Playwright.
  **The maintainer's own account platform is live (inc 312, 2026-07-20):** Authentik + `sync_server` self-hosted on
  a home LAN box, exposed via an outbound-only Cloudflare Tunnel (no hosting cost) — a real ORCID sign-in and a
  real 1,514-record sync both verified end-to-end. Getting the live round-trip working surfaced + fixed three real
  bugs (zero-leeway JWT timestamp checks, a JWKS-verifier issuer-string mismatch, and `/sync/run` never refreshing
  a stale access token) — see `INCREMENT-312-NOTES.md`. Follow-ons (yours, not code): per-user rate-limiting/
  retention on the server before any public/multi-tenant deploy (this remains a single-maintainer self-host).
- SQLAlchemy bound parameters (rule #3); PDF + external-input validation at the boundary
  (rule #4).

**Audit gate for major additions.** Any one of these triggers a security review **before** the
work is called done:
1. A new API endpoint or major request-schema change.
2. A new external fetch/integration (a new metadata/discovery/LLM service).
3. A new file-ingestion or file-write path.
4. Any new auth/session/authorization logic (e.g., when adding multi-user / public access).
5. A net-new feature spanning 3+ files or ~300+ added LOC.
6. A new third-party dependency.

**Required audit actions:**
1. Create `.claude/security-audits/YYYY-MM-DD_<feature>.md`.
2. Document the threat review: input validation, output encoding, injection, SSRF / external
   calls, secret handling, data egress, resource caps, file-path safety, supply-chain (pin deps).
3. Run negative-path checks (malformed input, oversized files, unauthorized access, egress
   while disabled) and record the concrete results.
4. End with **Security Audit: PASS** or **Security Audit: RISK ACCEPTED BY USER**. Unresolved
   risk blocks the change until the user signs off.

**Before any public/internet-facing deployment** (not done today — track it):
- **Auth + rate-limiting now EXIST as an opt-in foundation (inc 168, default-OFF):** `AccessControlMiddleware`
  (`app/backend/api/access_control.py`) — when **Remote access** is enabled (Settings, for the Google Docs add-on
  via a cloudflared tunnel), a constant-time **bearer token** is required on every endpoint except `GET /health` +
  `GET /` (the static shell), plus a hand-rolled sliding-window **rate limiter** (429). Default-off → a pure
  pass-through (zero change for localhost-only users). The token is stored like the BYOK key (keychain/file,
  write-only over the wire); the frontend sends it via a same-origin fetch shim (`00_lib.jsx`, token in
  localStorage, never injected into HTML). Recovery hatch: `CALLOSUM_DISABLE_REMOTE_ACCESS=1` — **or the in-app
  lockout recovery (inc 254):** a 401 raises one honest `AccessLockOverlay` (`01_recovery.jsx`) offering paste-the-token
  or `POST /access/recover` — a **gate-exempt-but-rate-limited, disable-only** path that proves local-machine possession
  via a one-time code written to `~/.callosum/recovery-code.txt` (returns only the path; only ever turns Remote access
  OFF; never reveals the token). Audit `2026-07-02_access-recovery.md` PASS. **The cloudflared
  ingress allowlist (forward ONLY the cite endpoints — `/papers`, `/papers/export`, `/citations/*`) is a REQUIRED
  SP1 control** so the file-read/scan routes + `/` are unreachable via the tunnel (recorded in the inc-168 audit).
  Re-audit before a *general* hosted deployment (this foundation targets the single-user add-on tunnel, not
  multi-tenant hosting).
- **Read-only mobile reading (B5 SP1, inc 237, default-OFF):** `CALLOSUM_READ_ONLY=1` (an env var) makes the
  `AccessControlMiddleware` return **403** for every mutating method (anything but GET/HEAD/OPTIONS) — the *method*
  boundary the cloudflared path allowlist can't provide (a path like `/papers/5` serves both a GET read and a DELETE
  write; cloudflared matches path only). The recommended deploy runs a **second, read-only callosum** for the tunnel
  (the inc-170 isolated-instance pattern) with `CALLOSUM_READ_ONLY=1` + Remote access on, behind the read-only
  cloudflared ingress (`adapters/mobile/`, defense in depth) — the desktop instance stays read-write. Audit
  `2026-07-01_mobile-reading.md` PASS.
- The localhost-only CORS + PDF/file-serving paths must be re-reviewed for a hosted context.
- **`POST /library/scan` reads a user-supplied folder server-side** (inc 87), **watched folders (inc 98)
  persist those paths + auto-read them on launch** (`POST /library/watched/rescan`), and **the library folder
  (`library_dir()` = `CALLOSUM_LIBRARY_DIR` / project `library/`) is auto-read on every launch/focus rescan
  (inc 160)** — fine on 127.0.0.1 (the server is the user's machine), but a remote caller could enumerate/read
  server files. **Gate or remove these before any hosted deployment.**
- Re-audit the egress gate, secret storage, and per-IP resource caps.

---

## File containment policy

**All temporary, working, and Claude-generated files go inside `.claude/`** (scratch scripts,
working copies, audit outputs, diagnostic probes, plan backups). **Generated databases, debug
images, and validation runs go inside `.local/`** (gitignored). Never scatter scratch files
across `app/`, `integrations/`, `tools/`, or the project root, where they get confused with
real code. If in doubt, put it in `.claude/`.

---

## Codebase hygiene & storage economy

- **`.local/` and `.claude/backups/` bloat fastest.** Validation runs write a `validation.sqlite`
  + a report + debug-image PNGs per run; zip snapshots accumulate. Prune old runs and snapshots
  (see Backup lifecycle).
- The `library/` PDFs (~77 files) and all `.local/` DBs are gitignored — they are data, not code.
- Delete dead code and stray artifacts as you go (rule #5).

---

## Backup & snapshot protocol

callosum is a **git repo** (remote `origin` → `github.com/cliffworkman/callosum`, public, AGPL-3.0):

1. **Git + GitHub is the primary, off-machine backup.** **Convention: commit + push at the end of each work
   session by default** (no need to be asked) so the remote — the user's geographically-orthogonal backup —
   never drifts behind; a single catch-up commit for a span is fine (the per-increment story lives in
   `changes.md` + the increment notes). The base "commit/push only when asked" default is overridden for the
   end-of-session case on this project. **Before pushing, run `ruff format` (not just `ruff check`)** — CI's
   lint job runs `ruff format --check .` too (see the verification note below) — and confirm CI goes green.
2. **Zip snapshots** of the working tree land in `.claude/backups/` (`callosum_HHMMpm.zip`,
   `callosum_inc29.zip` style). Take one before a risky refactor or at the end of a substantial
   increment.
3. **Dropbox version history** is the always-on safety net for individual files.
4. **Plan-file backups:** plan files at `~/.claude/plans/*.md` are per-conversation and get
   cleared. For any plan worth continuing, copy it to
   `.claude/backups/plans/YYYY-MM-DD_<short-description>.md` and keep it updated. On startup,
   check there when the user asks to continue earlier work.

---

## Change tracking

Keep `.claude/changes.md` as a running, human-readable log of every non-trivial change
(increment notes are the design diary; this is the chronological "what & why" record).

```markdown
## 2026-06-16 — short title
- **Files:** `path/a`, `path/b`
- **What:** one-sentence description
- **Why:** one-sentence motivation
- **Revert:** restore from `.claude/backups/<snapshot>.zip` OR specific instructions
```

Skip trivial edits (typos, whitespace). Log everything else.

**Help-doc sync marker.** The served help corpus (`app/backend/help/help_content.md`) must track user-facing
behavior. To find what's changed since it was last refreshed *without* re-scanning the code, `changes.md`
carries a `<!-- HELP-DOCS-SYNCED … -->` marker line at the top of the entry of any increment that brought the
corpus current. Because the log is **newest-first**, every entry **above the topmost marker** is a change
made since the last help sync — the candidate set to review. When an increment updates the corpus, move the
sync point forward by adding a new marker at the top of its entry. (See the Session-kickoff check.)

---

## Backup lifecycle

`.claude/` and `.local/` accumulate. Keep them lean:

- `.claude/backups/*.zip` — older than 30 days → delete (keep the latest per increment).
- `.local/` validation runs (DBs + debug images) — delete once their report has been acted on;
  hard-prune anything older than ~30 days.
- `.claude/security-audits/` and `.claude/backups/plans/` — **keep indefinitely** (institutional
  memory).

---

## MCP server usage

callosum ships **no committed `.mcp.json`.** The only session-level MCP tool used in practice is
**Playwright**, for optional manual UI checks of the assembled frontend — it is not a project
dependency, and the repo never relies on it. If you expect an MCP server and it isn't available,
say so and adjust the plan. Keep this section updated if a project-level MCP config is added.

---

## Reference docs

The planning + research suite under `.claude/` is the institutional-memory layer — consult it
before large design changes:

| Path | Content |
|---|---|
| `.claude/PRINCIPLES.md` | **The project charter — read before ANY claim/signal/judgment feature (rule #9 / Principles alignment gate): the 10 commitments, the THEORY contract, and four aligned-vs-misaligned worked examples. When at odds, propose the aligned alternative.** |
| `.claude/APPROACH-AVOIDANCE.md` | **The value substrate *beneath* the charter — the deeper, *conditional* layer of the gate (consulted for novel / value-level / future-track changes only, not every gated edit): 8 approach values + standalone veto-level avoidance boundaries (no paywall circumvention / no reaching into other tools' stores / no accusation of individuals) + the confirmed/extended/emergent/divergent drift typology. Derive the check from the value when no principle directly applies.** |
| `.claude/CREDIT-THE-LINEAGE.md` | **Values-layer cross-cutting principle (inbox-captured 2026-06-21): any tool that implements/operationalizes/is-built-on identifiable scholarly work must credit it *in-context* + offer the source paper(s) to the library (one-click), and credit a prior *tool* by citation + library-add, never by appropriating its name. Apply to every method-implementing feature; the retroactive credit-help backfill is in the backlog. Not yet wired as a hard rule-#9 gate trigger.** |
| `.claude/DESIGN.md` | **Design dictionary — read before ANY CSS/inline-style change (rule #8): tokens, element recipes, fixed color/type semantics, consolidation worklist** |
| `.claude/QA-POLICY.md` | **The QA contract — read before changing any end-user surface (rule #10): the fixture contract, the computed coverage gate (`tools/qa/build_surface_map.py`), the honesty-invariant assertions, the severity rubric, and the Codex-exec supervisor + watched-inbox loop. Add/extend a QA route in the same increment as a surface change.** |
| `.claude/EXPERIENCE-PASS.md` | **The end-user experience pass — read before calling any user-facing change done (rule #11): the two questions (reception / intended-use, the latter bounded by the #9 + A-A vetoes), the persona-grounded experience-agent mechanism (dispatch a subagent in-character as a concrete user with a goal-in-the-moment), the extensible persona/scenario library (deadline citer / corpus builder / skeptical synthesizer), and the statcheck worked example. A reflective pause → a finding (fix-cheap or backlog). The 4th gate: DESIGN=looks, PRINCIPLES=honest, QA=works+covered, EXPERIENCE=serves the user.** |
| `.claude/docs/future-tracks/` | The 7 longer-horizon track docs (statcheck/open-science, word-plugin, highlight-to-suggest/evaluate, full-text acquisition, my-publications, theory/methods, plugins, gapfinder, library Feed/Search). Referenced by `INCREMENT-BACKLOG.md`. |
| `app/backend/help/help_content.md` | **The served help corpus (inc 59) — the source of truth for user-facing help.** Edit here (then it renders in the `?` modal). Keep current via the `HELP-DOCS-SYNCED` marker. |
| `.claude/HELP.md` | Historical tip text (superseded by the served corpus above; kept as a dev note) |
| `.claude/docs/INCREMENT-BACKLOG.md` | The running nearer-term to-do list — **open items only** (reference-manager-first). Shipped/closed items live in `INCREMENT-BACKLOG-DONE.md` (split 2026-06-20). |
| `.claude/docs/product-scope.md` | What's in/out of scope |
| `.claude/docs/architecture.md` | Intended architecture |
| `.claude/docs/data-contracts.md` | Schema + payload contracts |
| `.claude/docs/risk-register.md` | Known risks + mitigations |
| `.claude/deprecated/roadmap.md` | **Archived (Phase 6, 2026-06-20, stale)** — the old staged skeleton→discovery roadmap; current status lives in the increment diary + `INCREMENT-BACKLOG.md`. |
| `.claude/docs/glossary.md` | Domain terms |
| `.claude/docs/increment-notes/INCREMENT-NN-NOTES.md` | Per-increment design diary (all increments, oldest→newest) |
| `.claude/docs/research/opus4.8_deepresearch_callosum_plan.md` | Architecture + tech survey baseline |
| `.claude/docs/research/opus4.8_deepresearch_callosum_feedback.md` | Review of the planning skeleton |
| `.claude/deprecated/backlog-future-tracks.md` | **Archived (Phase 6, 2026-06-20)** — earlier capture of the external tracks, superseded by `.claude/docs/future-tracks/` (the canonical source). |

---

## Architectural decision log

IF NEEDED, see ".\architectural-decisions-log.md"

---

## Session kickoff

When starting any non-trivial work:

1. **Read this file in full.** Rules apply to the edit you're about to make, not to history.
2. **Scan the most recent notes in `.claude/docs/increment-notes/`** and `.claude/changes.md` — they tell you
   what shifted recently and what the current state is.
3. **Confirm the environment:** Python 3.11+, deps installed (`requirements.txt` /
   `requirements-dev.txt`), `CALLOSUM_DB_URL` pointed at the right SQLite DB.
4. **If a plan file gets created**, back it up to `.claude/backups/plans/` immediately.
5. **For security-sensitive edits** (new endpoint, new external fetch, new ingestion path,
   any future auth), open a `.claude/security-audits/` stub at task-start and fill it as you go.
6. **For UI edits**, plan the manual verification script up front; flag it if you can't run it.
7. **Check whether the help docs need updating.** Grep `.claude/changes.md` for the topmost
   `<!-- HELP-DOCS-SYNCED … -->` marker; if any entry **above** it changed user-facing behavior (a new
   feature, a renamed control, a changed workflow), the served help corpus
   (`app/backend/help/help_content.md`) is likely stale — flag it to the user and offer to refresh the
   affected section(s). (Leverages the changelog instead of a blind code scan.)
8. **Run the Principles alignment gate (rule #9) for any claim/signal/judgment feature.** Read
   `.claude/PRINCIPLES.md`; name the principle(s) + the worked example it resembles + the misaligned easy
   path; when at odds, **propose the aligned alternative**, don't just object. For **novel / value-level /
   future-track** work, also consult the deeper values layer `.claude/APPROACH-AVOIDANCE.md` (derive from the
   value; run its drift typology; honor its veto-level boundaries).
9. **Check the future-tracks watched inbox** (Phase 8). Glance at `.claude/docs/future-tracks-import/`. It
   normally sits empty bar its `README.md` + the items the README's **Parked** list names — **anything else is
   unprocessed input a prior session or the user dropped in.** For each new file, **surface it to the user**
   (report it, never act silently) and handle it per the inbox `README.md`: a genuine **future-track** → run the
   Principles + `APPROACH-AVOIDANCE.md` gate framing, fold it into `INCREMENT-BACKLOG.md` + the
   `future-tracks/README.md` index, then **move** it to `future-tracks/`; a **meta / CLAUDE.md directive** →
   action it, then remove it; a **counsel-gated / sensitive** drop → leave it **parked** (it stays in the
   gitignored inbox, named in the README's Parked list — never auto-processed or published).
10. **Check the QA inbox.** Glance at `.claude/qa-inbox/` (gitignored, local-only — like the future-tracks
   inbox). It is normally empty bar `_processed/`. For each unprocessed `<run-id>/`, read its `run-summary.md`
   (Critical/High first): **fix Critical/High in-session**, file Medium/Low to `INCREMENT-BACKLOG.md`, open a
   `security-audits/` stub for any security-class finding, then move the run to `.claude/qa-inbox/_processed/`.
   Do not act on a run silently — surface what you found and what you're fixing. The supervisor
   (`tools/qa/supervisor.py`) deposits these via headless Codex `exec` runs (the QA-POLICY loop, rule #10).
11. **When in doubt, ask.** This project is pre-release with one user — a 30-second confirmation
   is cheaper than a wrong turn.

IF NEEDED, see ".\session-kickoff-log.md"
