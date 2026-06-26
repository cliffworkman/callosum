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

It is currently at **Increment 144** (see Increment workflow) with **524 pytest tests
passing** (+ opt-in browser smoke + the inc-120 Codex-driven QA route suite). It is a working MVP backed by a
thorough planning suite in `.claude/docs/`.
(Increments 109–116 — frontend/UX TDL items incl. the inc-110 PDF page-view — are journaled in `RECOVERY-LOG.md`
rather than this file's footer; the footer's detailed narrative resumes at increment 117.)

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
- **LLM (selective):** `google-genai` → Gemini `gemini-2.5-flash-lite`, **summary generation
  only**, OFF by default (see Core design invariants). Verification NLI runs locally
  (`cross-encoder/nli-MiniLM2-L6-H768`).
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

> **Gotcha:** `README.md` is **stale** — it still says "planning skeleton / planning mode."
> It does not reflect the current implemented state. Trust this file and the code, not the
> README (and fix the README opportunistically).

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
| `pytest` | Run the full test suite (`testpaths=tests`, `pythonpath=.`) |
| `pytest tests/test_api.py -k summary` | Run a focused subset |
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

```
callosum/
├── .claude/                       ← dev-only working space; NOT part of the app
│   ├── CLAUDE.md                  (this file)
│   ├── PRINCIPLES.md              (the project charter — the Principles alignment gate, rule #9)
│   ├── APPROACH-AVOIDANCE.md      (the value substrate beneath PRINCIPLES — the gate's deeper conditional layer)
│   ├── CREDIT-THE-LINEAGE.md      (values-layer cross-cutting principle — credit + library-add the scholarly work a tool stands on; inbox-captured 2026-06-21)
│   ├── DESIGN.md                  (the design dictionary — rule #8)
│   ├── QA-POLICY.md               (the QA contract — rule #10 / the surface-coverage gate)
│   ├── qa-routes/                 (QA route scripts the Codex-exec supervisor traverses; route_NN_*.md, NN
│   │                              encodes complexity order; _TEMPLATE.md is the contract shape — inc 120)
│   ├── qa-inbox/                  (gitignored, local-only: <run-id>/ deposits — md reports + screenshots +
│   │                              run-summary.md; _processed/ = triaged runs; the watched dropzone — inc 120)
│   ├── docs/                      (planning suite: product-scope, data-contracts, architecture, risk-register,
│   │   ├── increment-notes/       glossary, INCREMENT-BACKLOG, README; increment-notes/ = the per-increment diary;
│   │   ├── future-tracks/         future-tracks/ = longer-horizon docs; future-tracks-import/ = the watched inbox
│   │   ├── future-tracks-import/  (session-kickoff watch rule, Phase 8; gitignored — local-only dropzone);
│   │   └── research/              research/ = deep-research planning + feedback baselines + ref-manager surveys.
│   │                              NB roadmap.md + backlog-future-tracks.md were archived → deprecated/)
│   ├── deprecated/                (vestigial scaffolding archived here, not deleted)
│   ├── backups/                   (timestamped zip snapshots: callosum_HHMMpm.zip;
│   │   └── plans/                 plus plan-file backups — this is the recovery net)
│   ├── security-audits/           (per-feature threat-review write-ups — see audit gate)
│   ├── changes.md                 (running human-readable change log)
│   └── media/                     (brand-asset PNG sources — logo/favicon variants; re-inlined by tools/inline_brand_assets.py)
├── app/
│   ├── backend/                   ← all backend implementation
│   │   ├── api/                   (app.py [thin create_app factory + lifespan + CORS + frontend route],
│   │   │                          startup.py [logging + Alembic auto-migrate], dependencies.py,
│   │   │                          job_store.py [generic async-job store: Job/JobStore[R]],
│   │   │                          frontend.py [serve-time assembler], routers/{health,papers,paper_files [PDF
│   │   │                          file-serving, inc 91],methods [statcheck, inc 95],citations [formatted-citation
│   │   │                          engine, inc 106],duplicates,acquisition,wanted,my_publications,library,
│   │   │                          annotations,tags,axes,summaries,findings [FACT/CANDIDATE store, inc 130],
   │                          gaps [literature gap-finder, inc 135],help}.py [models + handlers])
│   │   ├── persistence/           (schema.py [SQLAlchemy Core core tables] + schema_base.py [shared metadata] +
│   │   │                          schema_findings.py [findings/signals/retraction/gap tables; re-exported from
│   │   │                          schema — inc 137 split to keep schema.py < 600], gap_repo.py [gap_candidates
│   │   │                          cache, inc 137], database.py, repository.py,
│   │   │                          dedup_repo.py [dismissed-duplicate-pairs data access, inc 67],
│   │   │                          tags_repo.py [tag data access, inc 71], acquisition_repo.py [OA attachment labels, inc 74],
│   │   │                          wanted_repo.py [wanted-list data access, inc 76], profile_repo.py [My Publications profile + decisions, inc 78],
│   │   │                          annotations_repo.py [native-annotation data access, inc 91],
│   │   │                          signals_repo.py [open_science_signals: statcheck + retraction status, inc 97/131],
│   │   │                          watched_repo.py [watched_folders, inc 98],
   │   │                          findings_repo.py [paper_findings: FACT/CANDIDATE contract, inc 130],
   │   │                          retraction_repo.py [retraction_records: local Retraction Watch mirror, inc 132])
│   │   ├── pdf_processing/        (extraction.py [PyMuPDF text + canonicalize], quote_matching.py
│   │   │                          [locate_quote → bbox rects], ingest.py, library_scan.py [folder scan, inc 87],
│   │   │                          location.py, cli.py)
│   │   ├── embeddings/            (models.py, pipeline.py, vector_store.py [sqlite-vec], retrieval.py)
│   │   ├── clustering/            (abstract_clustering.py, axis_scoring.py [scoring engine],
│   │                          axis_assignments.py [manual-override + state API], axis_suggestion.py,
│   │                          axis_operations.py, duplicate_detection.py, tag_suggestion.py [inc 72],
│   │                          my_publications.py [own-papers resolver + import hook, inc 78],
   │                          gapfinder.py [backward citation gap-finder, inc 135])
│   │   ├── methods/               (statcheck.py [NHST p-value recomputation, inc 95], pcurve.py [inc 126], grim.py
   │   │                          [GRIM/GRIMMER, inc 127], retraction.py [multi-source retraction → FACT, inc 131])
│   │   ├── citations/             (render.py [citeproc-js sidecar wrapper: render_papers (per-item, inc 106) +
│   │   │                          render_document (position-aware, inc 107) + style manifest + HTML sanitizer],
│   │   │                          citeproc_runner.js [Node sidecar; per-item + mode:"document"], csl/{styles,locales} [bundled CSL data, CC-BY-SA])
│   │   ├── summarization/         (pipeline.py, generators.py, verification.py)
│   │   ├── llm/                   (egress.py [provider-neutral DataEgressDisabledError + seam-gate wrappers, inc 58];
│   │   │                          cache.py [content-addressed summary-generation cache, inc 61]; usage.py [token logging])
│   │   ├── help/                  (help_content.md [served corpus, inc 59], corpus.py [loader + allowlisted
│   │   │                          md→html], assistant.py [HelpAssistant Protocol + dataclasses, inc 60])
│   │   ├── importers/             (zotero.py)
│   │   ├── metadata/              (doi.py, enrichment.py, abstract_display.py, paper_edits.py,
│   │   │                          citation_export.py [→BibTeX/RIS/CSL-JSON, inc 70],
│   │   │                          citation_import.py [←parse BibTeX/RIS/CSL-JSON, inc 93])
│   │   └── acquisition/           (registry.py [OaLocation OA-only seam + cascade], fetch.py [download/validate/
│   │                              name/import], wanted.py [wanted-list re-check service, inc 76], resolvers/{openalex,
│   │                              doaj,europepmc,crossref,core,arxiv,biorxiv,osf}_resolver.py; the OA acquisition
│   │                              clean lane, inc 74 + cascade inc 75 + wanted list inc 76)
│   ├── frontend/                  ← the UI SOURCE: index.html shell + styles.css + js/*.jsx chunks
│   │                              (assembled by app/backend/api/frontend.py; build → callosum-app.html)
│   └── desktop-shell/             (placeholder — Tauri, post-V1)
├── adapters/                      ← word-processor adapters (CLIENT code, ships into the word processor; NOT the
│   └── libreoffice/               app, NOT a server integration). inc 108: callosum_cite.py [UNO cite-while-you-write
│                                  macro], README.md, selftest_uno.py [headless round-trip harness]. Word/Docs next.
├── integrations/                  (external adapters: zotero, crossref, gemini, openalex, doaj, europepmc, core,
│                                  arxiv, biorxiv, osf, retraction_watch [RW DB download, inc 132] [impl];
│                                  api_cache.py [shared cache helper]; semantic-scholar, grobid, mendeley [planned])
├── research/                      (planning + research docs; Track-D acquisition rate-limit records)
├── ops/                           (deployment notes — planning state; gets real content pre-deploy)
├── tools/                         (validation_harness.py + validation/ [reports.py, report_renderer.py],
│                                  enrich_metadata.py, inline_brand_assets.py, build_frontend.py; qa/ [inc 120:
│                                  build_surface_map.py = surface-coverage gate, supervisor.py = Codex-exec
│                                  dispatcher, _qa_serve.py = seeded throwaway server, route_runner_prompt.md])
├── tests/                         (pytest suite — per-resource files + conftest.py + api_helpers.py; 303 passing;
│                                  tests/e2e/ = opt-in Playwright browser smoke, CALLOSUM_RUN_E2E=1)
├── alembic/                       (env.py + versions/0001_persistence_core … 0020_suppressed_paper_tags)
├── alembic.ini, pyproject.toml, requirements.txt, requirements-dev.txt
├── package.json, package-lock.json  ← JS deps: esbuild (frontend build, inc 102) + citeproc (citation engine, inc 106); node_modules/ gitignored
├── THIRD-PARTY-NOTICES.md           ← credit-the-lineage: citeproc-js (AGPL) + bundled CSL styles (CC-BY-SA), inc 106
├── callosum-app.html              ← GENERATED from app/frontend/ by tools/build_frontend.py; served at /
├── library/                       (77 scholarly PDFs; "Author et al. - YEAR - Journal.pdf"; gitignored)
└── .local/                        (generated validation DBs + debug images; gitignored)
```

`.gitignore` excludes `.local/`, `.pytest_cache/`, `__pycache__/`, `*.py[cod]`, `*.sqlite`,
`*.db`, `*.pdf`. **callosum IS a git repo** (remote `origin` → `github.com/cliffworkman/callosum`,
public, AGPL-3.0; CI in `.github/workflows/ci.yml`). Recovery is git history + the off-machine
GitHub backup, plus zip snapshots + Dropbox version history (see Backup & snapshot protocol).

---

## The rules

### 1. 600-line hard limit on application source

Any file under `app/` or `integrations/` must stay **under 600 lines**. Files approaching it
are split proactively; a file that crosses it MUST be modularized before the next feature
lands in it. Split by concern — routers, repositories, pipeline stages, adapters — and keep
shared/core code loading first.

**Exempt-but-watched:** `tests/` and `tools/` (the validation harness is allowed to be large),
and non-code (Markdown, SQL, config).

**Standing split tasks:** none currently over the limit. **Inc 137** split `schema.py` (611→558, over the cap
since inc 130/132): the findings/signals/retraction/gap tables moved to `persistence/schema_findings.py` on a
shared `persistence/schema_base.py` `metadata`, re-exported from `schema.py` (zero blast radius). **Inc 91** split
`repository.py` (625→538, → `persistence/annotations_repo.py`) and `routers/papers.py` (600→539, → `routers/paper_files.py`).
**Watch (re-measure before trusting):** `clustering/my_publications.py` (~594, **closest** — split before the next
backend addition there), `repository.py` (~556), `routers/papers.py` (~554), `extraction.py` (~551),
`routers/axes.py` (~537) — all under 600, but check `wc -l` before adding to them.
(The editable Detail pane lives in its own chunk `app/frontend/js/25_detail.jsx`; the edit-mapping logic is
`app/backend/metadata/paper_edits.py`.)

**Watch (exempt but large):** `tools/validation_harness.py` (~898 — inc 37 extracted the report
dataclasses + markdown renderer to `tools/validation/`; the probes remain, a candidate for a future
per-probe split). Tests are now per-resource (`tests/test_papers.py`, etc.) sharing
`tests/conftest.py` + `tests/api_helpers.py`.

### 2. Secrets in the environment, never in code

`GOOGLE_API_KEY` (Gemini) and `CALLOSUM_DB_URL` come from the environment. Never commit a key
or hardcode one in a `.py` file. Non-secret constants (model names, thresholds, table names)
are fine as literals. When a `.env` is introduced, it must be gitignored.

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

callosum is built in **numbered increments** (currently at 108). Each increment of real work
produces an `INCREMENT-NN-NOTES.md` in **`.claude/docs/increment-notes/`** (all notes, oldest→newest,
live there) with this shape:

- **Implemented** — what changed, in which files.
- **Key technical detail** — the non-obvious math/contract (e.g., the coordinate transform).
- **Manual verification script** — exact steps to reproduce the check (start app, load X,
  click Y, confirm Z).
- **Pytest** — the passing count.

When you complete a meaningful increment, write its notes file in this shape and bump the
number. These notes are the running design diary; read the most recent few at session start.

---

## Verification protocol

No change is "done" without verification appropriate to the surface it touches.

1. **pytest is the primary gate.** `pytest` must be green before any change is "done." Add or
   update tests for new behavior (the suite already covers API, persistence, PDF extraction,
   embeddings, clustering, summarization, and NLI verification).
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
- There is **no authentication and no rate limiting.** Add both before exposing the app.
- The localhost-only CORS + PDF/file-serving paths must be re-reviewed for a hosted context.
- **`POST /library/scan` reads a user-supplied folder server-side** (inc 87), and **watched folders (inc 98)
  persist those paths + auto-read them on launch** (`POST /library/watched/rescan`) — fine on 127.0.0.1 (the
  server is the user's machine), but a remote caller could enumerate/read server files. **Gate or remove these
  before any hosted deployment.**
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

| Decision | Rationale |
|---|---|
| THEORY/METHODS side panes = accordion on a module registry (inc 121, the "next major upgrade" UI-shell half) | Replaced the fixed left `Sidebar` (Axes+Tags) + right `RightPane` (inc-57 Synthesis/Details drag-split) with two **accordions** driven by an extensible **registry** (`05_panes.jsx`: `registerPaneSection({id,label,paneId,order,render})` + `<PaneAccordion>`). **Left = THEORY** (Axes/Synthesis/Tags, AXES default); **right = METHODS** (Details). Sections **self-register from their own chunks** (load order 05<10<15<20<25 ⇒ registry-first; `order` = display position; adding a section is one call, **zero `PaneAccordion` edits** — proven with a throwaway chunk). **Mount-but-hide** keeps an in-progress synthesis alive across a switch; open section persists (`callosum.theoryOpen`/`methodsOpen`). **Soft labels** (section headers only; `paneId` is the internal architecture + future rename). Behavior-preserving except **Tags now always shows** (empty-state hint) for discoverability. **(Superseded by inc 139: the registry gained tabs-within-a-section — Tags is now the second tab of the AXES section, not its own section; METHODS reordered Data-consistency before Statistics-check. See DESIGN.md §5.)** **esbuild DCEs unreferenced top-level functions** (a registered-but-unused component is stripped until used → wire the consumer in the same change; raw-assembly inclusion is the gate, not bundle-grep). `25_detail.jsx` was already 625 (>600) → the Details registration lives in `05_panes.jsx` to not worsen it; a split is queued (the statcheck→METHODS move relieves it). Frontend-only; Principles gate non-triggering. DESIGN.md §5 = the placement rubric + registry pattern + AI-usage principle. Verified headed (`:8097`, 0 console errors). **NEXT (user-queued):** statcheck Settings→a METHODS section (the first real METHODS module); investigate synthesis showing no text summary. |
| My Publications citing articles & citation counts (SP3 of the My-Pubs overhaul, inc 119 — overhaul complete) | TDL #14. Each own-pub card shows its **OpenAlex cited-by count** (verbatim + attributed — never a Callosum composite/verdict; declined #7/#2) + a **"Most cited"** sort; clicking opens a **citing-articles modal** (papers OpenAlex records as citing it — **candidates**, coverage stated, #3/#6) with per-row **Import** + a confirm-gated **Import all** → **metadata-only**, deduped, into the **general** library (not My Pubs; PDF stays the OA-only lane → no paywall circumvention, A-A veto held). Backend: `AuthorWork.openalex_work_id` (was discarded), `paper_citations` on the dashboard, `OpenAlexAuthorClient.fetch_citing_works` (`cites:<id>`, cached, capped 100, fail-closed) + `GET /my-publications/citing/{work_id}` + `import_citing_work` + `POST /my-publications/citing/import`; **`resolve` now `fetch_author_works(refresh=True)`** so a Refresh repopulates counts + work ids. Egress = **public metadata, bounded/cached/on-demand** (#10), NOT the Gemini gate. Principles gate run (spec §2, aligned); audit `2026-06-24_mypubs-citing.md` PASS; no migration. New chunk `34_mypubs_citing.jsx`. Verified headed (Playwright, `:8097` — real `cites:` fetch). **Watch:** `clustering/my_publications.py` at 587/600 — split before the next backend addition there. **This completes the My Publications overhaul (SP1 inc 117 + SP2 inc 118 + SP3 inc 119 = TDL #1 + #3–18).** |
| My Publications organized by research domain (SP2 of the My-Pubs overhaul, inc 118) | TDL #9/#15/#16/#17/#18. A **Group by domain** toggle regroups the publications under per-domain headers (dashboard list) / collapsible subheadings (sidebar axis card), **"Other"** group last, **starred-first** within each. **Rename domains** inline (the box pre-suggests the closest **axis** name by term overlap); custom names **persist across Re-decompose** by paper-overlap (Jaccard ≥ 0.5) — a `custom` flag in the existing `research_domains` JSON + `_reapply_custom_labels`, so **no migration**. **#18:** selecting a domain locks the Overview flip-chart to Publications (filtered) + disables the Citations pill. Backend additive: `Domain.paper_ids` + `DashboardResponse.starred_ids` on the dashboard, a per-paper **`ClusterPaperResponse.domain`** gated to the my-pubs `/axes/{id}/clusters` (mirrors inc-84 `starred` — so the sidebar groups with no new route/fetch), and one new endpoint `POST /my-publications/domains/rename` (local profile-JSON write; audit PASS). No egress, no Principles trigger (organizational, not a new claim/signal). Verified headed (Playwright, `:8097`). **SP3** = citing articles + citation counts (#14, a new OpenAlex cited-by fetch → trips both gates). |
| My Publications dashboard restructured into a browsable publications library (SP1 of the My-Pubs overhaul, inc 117) | TDL line 1 + #1/#3–8/#10–13. New order **Overview → summary → Publications → domains → OpenAlex card** (provenance/sync demoted to a footer; metrics & pubs lead — user's call). **Overview** is collapsible (2×2 metrics + **one** Publications⇄Citations flip-chart, last 10 yrs `'NN` — replaced the two side-by-side charts). **Publications** reuses the library's own machinery: a shared **`PaperCard`** extracted from the 40-prop `PaperList` monolith + **`GET /papers?axis_id=<my-pubs>`** (so search/sort/cards/bulk parity come for free; `MyPubsPublications` in `33_mypubs_pubs.jsx` is a thin wrapper, `limit=200` = the endpoint cap). The **OpenAlex card** holds as-of/gap/2-yr-mean-citedness/affiliation/profile-link/Refresh + the missing-works **modal** trigger (`32_mypubs_missing.jsx`). Backend additive only: `openalex_extra` + `starred_count` on the dashboard response, parsed from the **already-cached** OpenAlex author object — **no new endpoint, migration, or egress → no audit/Principles gate** (OpenAlex figures stay verbatim + attributed, inc-81 posture). Two bugs caught: `/papers` 422 on `limit>200`; the "Review →" button was unreachable when all missing works were dismissed (now shows "Dismissed (N) →"). The domains section sits below the list transitionally; **SP2** reworks it (group-by-domain, AXES subheadings, rename-vs-axes, chart-filter). **SP3** = citing articles + citation counts (#14, a new OpenAlex cited-by fetch → will trip both gates). Verified headed (Playwright, `:8099` live data). |
| LibreOffice (UNO) citation adapter = a thin client-side field-placer on the inc-107 render-document contract; the first word-processor adapter (inc 108) | The first piece that places citations **inside a word processor**. A drop-in LibreOffice Writer **Python UNO macro** (`adapters/libreoffice/callosum_cite.py`) — new top-level **`adapters/`** tree (client code that ships into the user's LibreOffice; NOT the FastAPI app, NOT a server-side `integrations/` client). It is a **thin field-placer** (the spec's contract): place/track a live field, read the full ordered set, write back what the backend rendered — it **never formats** (citeproc does, so output matches the in-app "Cite as…"). Live fields = **ReferenceMarks** whose name carries the cited work's **CSL-JSON** (base64), the Zotero `CSL_CITATION` **pattern** (credited, not code → `THIRD-PARTY-NOTICES.md`). Four entry points: Insert (paper id → `/papers/export csl-json` → ReferenceMark), Refresh (full-document-order scan via `XTextRangeCompare` → `POST /citations/render-document` → write back in-text + bibliography), SetStyle (validated vs `/citations/styles`, persisted as doc user-properties), Flatten (live→static). **No server change** — no new endpoint/migration/route/egress (talks only to 127.0.0.1); stdlib `urllib` (LO's bundled Python has no pip). **Verification:** the headless UNO round-trip (`.local/lo_roundtrip/`, real LibreOffice → IEEE `[1]/[2]`, APA author-date, flatten preserves text — SELFTEST OK) + 5 pytest pure-logic tests. **Four UNO traps found+fixed** (worth knowing for the next adapters): `loadComponentFromURL` needs `Hidden=True`; clearing the bib invalidates its bookmark anchor (reuse the cursor); `setString` on a ReferenceMark anchor **destroys the mark** (recreate it around the new text); holding `ReferenceMarks` collection items across a mutation hangs on a stale handle (capture names, re-fetch) + removing a mark deletes its text (flatten re-inserts it). Audit `.claude/security-audits/2026-06-21_libreoffice-adapter.md` PASS. **Next:** Word (Office.js — needs the CORS/origin change) then Google Docs (cloud opt-in). |
| Position-aware document render = a 2nd citeproc mode (`rebuildProcessorState`) + endpoint; the word-processor adapter contract (inc 107) | The inc-106 engine renders each cite **in isolation** (`makeCitationCluster`) — right for a *selection* (in-app "Cite as …" / bulk bibliography), **wrong for a live document** (numeric styles must renumber `[1][2][3]` by order; author-date must disambiguate `2020a`/`2020b` across the whole doc). Inc 107 adds the **position-aware** layer every word-processor adapter calls: the runner gains a **`mode:"document"`** branch using citeproc's **`rebuildProcessorState(clusters,"html")`** (the standard "render this ordered saved set" call — how Zotero renders a doc), returning per-cluster in-text `[citationID,noteIndex,string]` + `makeBibliography()`; the inc-106 per-item path is the unchanged default. `render.py` refactors the subprocess into **`_run(request)`** (both modes build their own request) + adds **`render_document(citations,*,style,locale)`** — **self-contained** (renders from the passed CSL-JSON payloads, **no library lookup / no DB**), caps clusters/items-per-cluster/total, sanitizes output (`_safe_html`). **`POST /citations/render-document`** `{citations:[{citationID?,items:[CSL-JSON]}],style,locale}` — *the adapter contract*: an adapter scans the doc for citation fields (each carrying its embedded CSL-JSON), POSTs them **in document order**, gets back the **position-aware** in-text per field + the bibliography to write back. Stateless per request (always the full ordered set → no server-side doc state). Same status contract as `/citations/render` (503/422/502, never 500). **No frontend change, no migration, no egress, no new dependency.** Audit `.claude/security-audits/2026-06-21_citation-render-document.md` PASS. **Next:** the LibreOffice (UNO) adapter — the live-field loop (insert→render→update→flatten) on this endpoint. |
| Citation & bibliography engine = citeproc-js rendered backend-side via a Node sidecar; the word-processor spine (inc 106) | The biggest gap to Zotero/Mendeley parity. **citeproc-js** (the reference CSL processor) runs as a **Node sidecar** — invoked exactly like esbuild (`render.py::_run_engine` mirrors `frontend.py::_transpile_jsx`: `shutil.which("node")` + fixed-arg `subprocess.run`, request JSON on stdin, result on stdout, fail-closed → `CitationEngineUnavailable`/503). One central render = byte-identical output everywhere (the **adapters will only place fields, never format** — LibreOffice → Word → Google Docs ride this same engine). Reuses `papers.csl_json` + `get_papers_for_export`. CSL **styles/locales are bundled** verbatim under `app/backend/citations/csl/` (CC-BY-SA, `<rights>` preserved; **no fetch-on-demand → no egress** this increment). citeproc HTML is **sanitized server-side** (`_safe_html`: bare inline tags only, attrs/other-tags dropped, text escaped) before any in-app `dangerouslySetInnerHTML` — same posture as inc-33/59. Endpoints `GET /citations/styles` + `POST /citations/render`; in-app surface = Details "Cite as …" (style dropdown + live preview + copy) + a bulk "bibliography…" `.html` download. `citeproc` pinned in `package.json`; CI `npm ci` covers tests; data files exempt from the 600-line rule. Honors **credit-the-lineage** (`THIRD-PARTY-NOTICES.md`). Audit `.claude/security-audits/2026-06-21_citation-engine.md` PASS. **Next:** the LibreOffice (UNO) adapter (the live-field loop). |
| Default axis cutoff in Settings + a tag source filter — both frontend-only over existing data (inc 105) | Two chores. (1) A **`callosum.axisCutoffDefault`** localStorage pref (Settings → Axes slider, clamped [0.2,0.6], default 0.35; mirrors the inc-77 hide-uncertain pattern) threads App→Sidebar→AxesPanel→`AxisItem`, whose cutoff flipper falls back to it when `axis.scoring_gain == null` (a stored per-axis gain still wins; AxesPanel keys cards on the default so a change re-inits unscored cards). Sets what the flipper *proposes*; no backend change (unscored read-time tiering still uses the backend 0.35 until scored). (2) The sidebar `TagsPanel` gained an **All / Yours / Keywords** segmented control filtering by the inc-100 `source` (`tagIsImported`), shown only when both kinds exist — purely client-side over the already-fetched `/tags`. No migration, no egress, no new endpoint; pytest 411 unchanged. |
| Side panels have min widths (left 300 / right 415) + Spotify-style pull-to-collapse; header buttons regrouped (inc 104) | `40_app.jsx` constants `LEFT_MIN=300/RIGHT_MIN=415` (+ `*_MAX`, `*_COLLAPSE_AT = min−80`). The `leftW`/`rightW` init clamps the persisted value up to the min; each divider's drag computes the unclamped `proposed` width and **auto-collapses** the panel (`setLeftOpen/​setRightOpen(false)`) when `proposed < COLLAPSE_AT`, else clamps to `[MIN,MAX]`. The panel "sticks" at its min then snaps shut once pulled ~80px past — works because `_beginDrag` uses document-level listeners (the grip unmounting mid-drag doesn't end the drag; re-expand within one drag works, else the collapse chevron). Auto-collapse persists like a chevron collapse; widths stay ≥ min. **CSS:** `.icon-help` → `top:19px;right:33px` (down 7/left 4, then both nudged left 15px); `.icon-gear` → `top:19px;right:60px` (same Y, 27px left of help — the two become a right-aligned pair, top-left vacated). Both buttons also gained an **always-on outline** (`border:1px solid currentColor`, the icon color at rest; hover still → `--line-2` border + `--accent` text + `--panel` bg). Frontend-only; tokens-untouched position values (rule #8). |
| Per-card "copy BibTeX" clipboard button restores card-citation copy after the inc-98 `user-select:none` (inc 103) | inc-98's `.paper { user-select:none }` (needed so a double-click opens without word-selecting the title) removed text-copy from cards, so a small **clipboard SVG button** (`PaperCopyButton` in `10_pdf_layer.jsx`) sits just left of the checkbox (`.paper-copy` absolute at `top:10px;right:36px`, vs the checkbox at `right:14px`; `.paper-title` got `padding-right:46px` to clear both). It copies the paper's **BibTeX** via the tested inc-70 `POST /papers/export {paper_ids:[id], format:"bibtex"}` → `navigator.clipboard` (mirrors the Details `CiteRow`; `stopPropagation` so copy never selects/opens; icon → ✓ for ~1.5s). Shown only in `selecting` mode (the normal library view), matching "alongside the checkbox"; the checkbox is untouched. **Frontend-only — no backend/endpoint/migration/egress** (reuses a validated local read-only endpoint). Two inline Feather SVGs (the user asked for an SVG; most icons are emoji). |
| Frontend JSX is precompiled by esbuild at build time; the in-browser Babel transformer is dropped (inc 102) | The served page used `babel-standalone` (cdnjs) to transpile `<script type="text/babel">` JSX **in the browser at runtime** (the inc-37 design), which emitted two dev-console messages (a "precompile for production" warning + a `babel.min.js.map` 404 source-map error) and cost a ~500KB download + runtime transform. Now `frontend.py` concatenates the chunks (`assemble_jsx`) and **precompiles them with esbuild** (`_transpile_jsx`: `node node_modules/esbuild/bin/esbuild --loader=jsx --jsx=transform --jsx-factory=React.createElement --jsx-fragment=React.Fragment --format=iife --target=esnext`, JSX piped via stdin — fixed arg list, no shell) into one `<script>`; the Babel CDN line is gone from `index.html`. esbuild is a **build-time** dep (`package.json` pins 0.28.1; `npm install`/`npm ci`; `node_modules/` gitignored); the **server stays Python-only** — it serves the prebuilt `callosum-app.html` and never runs Node at serve time (the rare live-assembly fallback transpiles on demand and degrades to the unavailable-response if esbuild is absent — `app.py` try/except, never a 500). The IIFE keeps every chunk in one shared scope (identical runtime to the old single text/babel script). Output is byte-stable per pinned esbuild version, so the `callosum-app.html`-in-sync test still holds; `test_every_js_chunk_is_included` checks `assemble_jsx()` (raw) so completeness needs no toolchain. CI gained `setup-node` + `npm ci`. Verified: `node --check` on the output + the opt-in Playwright smoke (0 console errors). Audit `.claude/security-audits/2026-06-21_precompile-esbuild.md` PASS. (The third console line the user saw — `XrayWrapper … content-script.js` — is an external **browser extension**, not callosum.) |
| Reading mode = a transient view that collapses both panels + dividers; restores the prior layout on exit (inc 101) | A one-click distraction-free reader (the inc-100/101 carrot), built on the inc-42 collapsible panels. `readingMode` state in `40_app.jsx`: `toggleReading` snapshots `leftOpen`/`rightOpen`, collapses both, and on exit restores the snapshot (so an asymmetric layout returns intact); `cols` zeroes the divider tracks too and `.app.reading .divider{display:none}` hides their chevrons, leaving the center pane only. **Not persisted** (a reload returns to normal — never strands the user with hidden chrome). The `.frame-reading` toggle (right of the tab bar) + **Esc** (guarded to defer to an open modal) are the only ways back, since the sidebar — and its ⚙/❓ — is hidden. Frontend-only; no backend/migration/egress/new token (tokens-only CSS, rule #8). |
| Tag provenance is shown by style + tooltip, not a label; statcheck flagged-count is a header chip (inc 100) | Two read-only projections of already-persisted facts. (1) The `import_source` stored per tag (inc 73) is exposed on the tag responses (`PaperTagRef.source` / `TagRef`/`TagSummary.source`) and drives a **muted style + a source tooltip** on imported keyword tags (Crossref/OpenAlex/Zotero) vs the accent-colored tags you typed — the user asked to differentiate sources **aesthetically** to avoid cluttering Details with labels (strengthens the inc-73 fact-vs-candidate distinction; "inspectability over authority"). (2) `signals_repo.count_statcheck_flagged` + `GET /methods/statcheck/summary` feed a **⚠ N flagged** Library-header chip that jumps to the inc-97 flagged-papers **filter** — a more prominent door to a Settings-only feature (still a list-to-review, never a rank/score/verdict; the no-accusation boundary holds). Both: **no migration, no egress, no LLM**; the tag `source` field is additive (default null); the count is cache-only (the inc-97 batch stays the only persister). |
| Tests derive the Alembic head from the scripts (`api_helpers.alembic_head()`), never a hardcoded revision (inc 99) | A migration that bumps the head used to require editing a hardcoded `"00NN_…"` constant in `test_health.py` + `test_startup_migration.py` — and a missed edit only went red on the *full* suite (bit inc 91 + inc 98). `alembic_head()` (`ScriptDirectory…get_current_head()`) makes the head assertions follow the scripts, so a new migration needs zero test edits for the head. **Convention: never hardcode the Alembic head in a test — use `alembic_head()`.** |
| Watched folders = persist scanned folders + auto-rescan on launch; "watching" without a live OS watcher (inc 98) | Zotero/Mendeley-style without the complexity. New `watched_folders` table (migration **0014**, guarded) + `persistence/watched_repo.py`; **scanning a folder registers it** as watched (`add_watched_folder`) and stamps `last_scanned`. `GET/DELETE /library/watched` (un-watch is non-destructive — keeps papers) + `POST/GET /library/watched/rescan` (async, re-scan ALL watched folders, reusing the inc-87 scan body via a shared `_process_scan_result` + the `library_scan_jobs` store). The frontend auto-triggers a rescan **on launch** (default-on Settings toggle), plus a "Re-scan all". Safe to re-scan the library folder because `scan_library_folder` content-dedups by `file_sha256` (Zotero stores the same hash) → no duplicates. **NOT a live OS file-watcher** (no `watchdog`; on-launch + manual only) — deferred. Server-side folder read (persisted + auto-read) extends the inc-87 deployment-gate note. Audit `.claude/security-audits/2026-06-21_watched-folders.md` PASS. (Same increment: the double-click-to-open bug — the inc-82 `getSelection` guard suppressed opening when the title was double-clicked; now `onDoubleClick` always opens. **Post-inc-101 follow-up:** `onDoubleClick` always opening still left the browser word-selecting the title on each open, so `.paper` got `user-select: none` — double-click opens with no highlight; card text isn't drag-selectable but stays copyable in Details.) |
| statcheck library-wide lens = persist a per-paper summary + a batch run + a library FILTER (never a rank/score) (inc 97) | Turns the inc-95 per-paper check into library triage. New `persistence/signals_repo.py` (first writer of the pre-built `open_science_signals` table — no migration) upserts **one summary row per paper** (`signal_type/source="statcheck"`, `status=inconsistent` iff any test flagged, counts in `evidence_snippet`) via `insert(...).prefix_with("OR REPLACE")` on the unique `(paper_id, signal_type, source)` (idempotent re-runs). An async **`POST /methods/statcheck/run`** (`routers/methods.py`, `statcheck_jobs`) batch-checks every live paper (the **only** persister; the inc-95 per-paper GET stays live/read-only); a `signal` query param on `GET /papers` → `SIGNAL_FILTERS` allowlist → a bound IN-subquery (rule #3). UI: a Settings "Statistics check → Check all papers" section + a **"Show flagged papers"** link → a mutually-exclusive library **view** + a non-accusatory banner. **Principles gate (rule #9):** the aggregate is a **filter to review, never a rank/score (#7) or a "bad papers" verdict (#2 + no-accusation veto)** — the declined easy path was a reproducibility-score leaderboard. No migration, no egress, no LLM. Audit `.claude/security-audits/2026-06-21_statcheck-library.md` PASS. |
| Sidebar Tags browser + Details "More → + add field" (inc 96) | Two frontend-only chores reusing tested endpoints. (1) A **`TagsPanel`** in the left sidebar (below Axes) lists every tag + its paper count, click to filter the library (reuses `GET /tags` + the inc-71 `filterToTag`); a `tagRefresh` nonce + an `onTagsChanged` callback (App→RightPane→DetailContent→TagsRow) keep it in sync with per-paper tag edits. (2) The Details **"More"** section now always renders + has an **`AddFieldRow`** to add an arbitrary bibliographic field by hand, reusing the inc-49 validated generic `csl` patch (`PATCH /papers/{id}` — letter-led `[A-Za-z0-9_-]` keys; reserved/core keys 422). **No Python changed** (both ride existing tested paths); no migration, no egress, no new endpoint. |
| statcheck = a deterministic, local, no-LLM per-paper signal; on-demand, no persistence, no composite score, no accusation (inc 95) | The carrot + Track A's v1. `methods/statcheck.py` (new `methods/` package) recomputes reported APA NHST p-values (t/F/r/χ²/z) from the paper's extracted chunk text via `scipy.stats`, classifying each test **consistent / inconsistent / decision-error** with **rounding + one-tailed tolerance** so correct reporting isn't false-flagged. `GET /papers/{id}/statcheck` (`routers/methods.py`, sync read-only; no chunks → `checked:0`). The Details "Statistical reporting" section shows per-test rows (verbatim match + recomputed p + a green/amber `.cite-status` pill) + transparent **counts** (never a composite "reproducibility score" — the A-A "scoring temptation" divergence, declined) + the **non-accusatory** coverage caveat (amber not red; "a prompt to look, not a verdict"; inline-APA-only so absence ≠ clean), routing each row to its page (page-open, not a fake exact highlight). **PRINCIPLES Example 3 / extends value A6; honors the veto-level no-accusation boundary.** `scipy` made an explicit dep (already transitive via scikit-learn; needed for the t/F/χ² CDFs). **No persistence (v1)** — the `open_science_signals` table + a library-wide facet defer to the findings subsystem. **No migration, no egress, no LLM.** Audit `.claude/security-audits/2026-06-21_statcheck.md` PASS. |
| Library-header "+ Add ▾" menu + persistent/descending Sort (inc 94) | Two small UX chores. (1) The six-action library header folds its two "bring papers in" actions (Scan folder + Import) into one **"+ Add ▾"** dropdown (`AddMenu` in `10_pdf_layer.jsx`: a `.trash-toggle`-styled trigger + an outside-click-closing `.add-menu-pop` popup; token-based CSS) → 6 actions → 5. (2) The **Sort** choice now persists to `localStorage["callosum.librarySort"]` (mirrors the theme / hide-uncertain prefs), and **Title (Z–A)** / **Author (Z–A)** were added via new `title_desc`/`author_desc` keys in the `_paper_sort_order` allowlist (rule #3; NULL author still last, `papers.id` tiebreak). Frontend-only bar the one allowlist addition; **no migration, no egress, no new endpoint.** |
| BibTeX / RIS / CSL-JSON import = hand-rolled parsers → CSL → dedup → create → embed; entirely local, no egress (inc 93) | The inverse of inc-70 export + reference-manager-first parity (also covers Mendeley/EndNote, which export these). `metadata/citation_import.py` hand-rolls all three parsers (**no new dependency** — project ethos, cf. the inc-75 arXiv parser): each yields a **CSL dict** (inverting `citation_export`'s field/type maps), then `csl_record_to_paper_fields` → `create_paper` kwargs (`csl_json` stored whole → CSL-JSON round-trips losslessly; `item_type` = CSL type so the inc-91 Type facet labels it). `import_citations` dedups via `find_existing_paper_by_identity` (DOI → title+year+author) in per-record `begin_nested()` savepoints (a bad entry is skipped+counted, never fatal); caps bytes + record count. **Entirely local — NO egress** (the file is authoritative; no Crossref/Gemini), and the browser POSTs the file **text in the JSON body** (no multipart/upload surface, and no server-side file path → no traversal surface, unlike the inc-87 scan). `<fmt>-import` is outside enrichment's update allowlist (won't clobber the file's metadata, like user-edits). Async job + frontend reuse the inc-87 scan scaffolding (`POST/GET /library/import` in `routers/library.py`; `28_import.jsx` clones `ScanModal`). Audit `.claude/security-audits/2026-06-21_citation-import.md` PASS. v1 deferred: PDF-attach on import, optional enrich/My-Pubs hook, hardened BibTeX (`@string`/`#`-concat/`(`-delimited). |
| Un-dismiss for My-Publications missing works = `build_dashboard.dismissed_works` + `POST /works/undismiss`; pure profile-JSON edit (inc 92) | Completes inc-85's review queue with the undo inc-67 added for duplicates. `profile_repo.undismiss_work` removes a normalized DOI from `profile.dismissed_work_dois` (mirror of `dismiss_work`; empty → NULL); `build_dashboard` returns a new **`dismissed_works`** (the author's cached works whose DOI ∈ dismissed, via `_dashboard_dismissed_works` — titles come from the cached OpenAlex works, so a DOI no longer in the works list just isn't shown) alongside `missing_works`, sharing one dismissed-set computation. `DashboardResponse.dismissed_works` reuses the `MissingWork` model; `POST /my-publications/works/undismiss` (local, idempotent, 204) mirrors the dismiss endpoint; the dashboard gains a collapsible "Previously dismissed" section with **Restore**. Cache-only (no network), no migration, no egress — facts-vs-candidates preserved (the human restores; nothing auto-acts). |
| Filter the library by item type = an `item_type` param on `GET /papers` + a `GET /papers/item-types` facet endpoint; preceded by splitting two over-limit files (inc 91) | Same param family as inc-69 sort / inc-63/71 axis-tag filters: `list_papers(item_type=…)` adds `WHERE item_type == :bound` (rule #3 — exact equality on a bound value, no allowlist needed), composing with q/deleted/axis/tag/needs-review/sort. The Type dropdown is driven by `list_item_types` (distinct **live** types + counts, NULL excluded) so it only offers **honest** facets that exist — a `_typeLabel` map prettifies CSL types ("article-journal" → "Journal article (32)"). `.searchbar` gained `flex-wrap` for the 4th control. **Forced module splits first (rule #1):** adding this surfaced that `repository.py` (625) + `routers/papers.py` (600) were at/over the 600-line cap, so before the feature, native-annotations data-access moved verbatim → `persistence/annotations_repo.py` (repository.py→538; precedent dedup_repo/tags_repo) and PDF file-serving moved → `routers/paper_files.py` (papers.py→539; precedent duplicates.py). The PDF route kept its path (`/papers/{paper_id}/pdf`), so the only route-surface change is the new `/papers/item-types`. **No migration, no egress.** Trade-off (v1): the facet list is library-wide, not scoped to the active axis/tag/trash view. |
| Library search covers the whole `csl_json` record (all authors + every field), scoped by an allowlisted `search_field` param (inc 89) | Search was title + `first_author_family_name` only, so a co-author's name found just first-authored papers (the user's surname returned 6 of 40) and none of the fields the Detail pane has since added were searchable. `repository._search_clause(field, pattern)` now searches `lower(cast(csl_json AS String)) LIKE` — the full bibliographic record holds every author, journal, year, DOI, publisher, … — with `first_author_family_name` kept as belt-and-suspenders (no regression). A `search_field` allowlist (`all`/`title`/`author`/`journal`; key indexes a constant, never interpolated — rule #3; pattern bound) drives a scope **dropdown** beside the search box (default **all**). Same class as the inc-69 sort / inc-80 needs-review param: a query param on `GET /papers`, composes with sort/deleted/axis/tag/pagination. **No migration, no new endpoint, no egress.** Trade-offs (v1): the `author` scope matches the whole record (a name query in a title/venue could match) and `all` includes the JATS `abstract` — fine for real queries; a precise per-author `json_each` query is a future refinement. |
| Scan a library folder = an app-level orchestrator over the existing ingest primitives; linked in-place, checksum-dedup, async (inc 87) | The first app-level "ingest a folder of PDFs" (previously only the Zotero importer + the dev validation harness). New `pdf_processing/library_scan.py::scan_library_folder` reuses `attach_pdf_to_paper` (extract+chunk) + `file_sha256` + the indexed `attachments.checksum`: **new** = checksum not in the library → `create_paper("pdf-scaffold")` + `attach_pdf_to_paper(storage_mode="linked", import_source="library-scan")` in a per-file **savepoint** (a corrupt PDF is isolated, not fatal); **unchanged** = checksum present (re-scan idempotent); **removed** = a previously-scanned path gone → `availability="missing"` (non-destructive). PDFs stay in place (**linked** — nothing copied). The async job (`library_scan_jobs`, `routers/library.py`) then enriches new papers from Crossref (unresolved → the inc-80 Unsorted view) + embeds new chunks/papers. **No migration** (reuses `attachments`); only egress is the Crossref DOI lookup (NOT the Gemini gate); the folder is read **server-side** — fine on 127.0.0.1, but gate before any hosted deploy (Security baseline). v1 = new/unchanged/removed; **changed** in-place files add a new paper (true re-ingest deferred — needs inc-65 vector cleanup); **watch**/auto + a persisted watched-folder are deferred. Audit `.claude/security-audits/2026-06-21_library-scan.md` PASS. |
| My Publications missing-works review/import = guardrailed, metadata-only import of the author's own indexed works (inc 85) | The dashboard gap ("79 indexed · 40 in library") becomes a **review queue** (`build_dashboard.missing_works` = cached author works whose DOI ∉ live library ∉ `profile.dismissed_work_dois`, sorted by citations; cache-only). **Import** (`import_missing_work`) reuses the inc-74–76 lane but is **metadata-only** (`create_paper` + `enrich_paper_metadata_from_crossref(force=True)` — `openalex-import` isn't in the auto-update allowlist, so force, like re-resolve; the OA-**PDF** path stays the separate "Acquire OA copy"). **Guardrail:** the DOI must be one of the resolved author's cached works → no arbitrary-DOI minting (else 422). My-Pubs membership is added **directly** via `_add_confirmed_member` (cache-independent — not via `maybe_add_to_my_publications`, which re-derives from the cached works), so it works regardless of cache warmth / Crossref outcome; an imported work then matches a live paper and drops from the queue. **Reject** = `dismiss_work` (a normalized DOI in `profile.dismissed_work_dois` JSON, migration **0013**). Facts-vs-candidates (the human imports/dismisses — no auto-action); only egress is the Crossref DOI lookup (not the Gemini gate); the list + dismiss are local. `POST /my-publications/works/{import,dismiss}`. Audit `.claude/security-audits/2026-06-21_my-pubs-missing-works.md` PASS. |
| Star key publications = an isolated `profile.starred_paper_ids` JSON list; the AI summary can scope to it (inc 84) | ⭐ star key papers in the My Pubs sidebar card (the star state surfaces on the `my_publications` axis clusters response — `ClusterPaperResponse.starred`, gated to that axis so the generic endpoint does no extra work for standard axes). `POST /my-publications/star`; the generate endpoint's `starred_only` body → `my_publication_documents(only_paper_ids=…)` (empty starred + starred_only → 422). Stored as `profile.starred_paper_ids` JSON (migration **0012**; like `research_domains`) — no new table, no coupling to the membership machinery. LLM-free plumbing (the summary path is the inc-81 gated seam). |
| My Publications domain decomposition (Part 2, Layer 2) = local clustering stored as an isolated JSON artifact, NOT child cluster_nodes (inc 83) | Layer 2 clusters the user's CONFIRMED own-papers into research **domains** (impact-by-domain + a dashboard chart re-filter), reusing the inc-52 axis-suggestion machinery (`model.encode_texts` → `AgglomerativeAbstractClusterer` → c-TF-IDF labels). The spec suggested child cluster_nodes under the my_publications axis, but **`axis_score_state` counts members by `axis_id` across ALL of an axis's nodes** — so children would double-count the inc-78 card badge + skew the inc-79 `uncertain_count`. So the decomposition is persisted as **`profile.research_domains` JSON** (`[{label, terms, paper_ids}]`, like `name_variants`) — isolated, zero impact on the membership/count machinery (migration **0011**). **LLM-free** (clustering is local); the only egress is the OpenAlex works **refresh** (`fetch_author_works(refresh=True)` adds per-work `cited_by_count` for impact-by-domain) — metadata egress, already audited (inc 78), NOT the Gemini gate. Impact-by-domain is an honest citation **sum** (no composite score); domains show their member papers + the terms that named them (inspectable); the 0.25 name-only candidates are excluded. `decompose_domains` is async (`mypubs_domain_jobs`); the dashboard read stays cache-only/egress-free; the chart re-filter is client-side from each domain's `paper_years`. Layers 3–4 deferred. |
| My Publications dashboard (Part 2, Layer 1) = a cache-only, egress-free read; metrics are OpenAlex's verbatim figures; the AI summary is the only (gated) egress (inc 81) | The impact dashboard reads ONLY already-cached OpenAlex data + the local library (`build_dashboard` via `cached_author`, which never fetches; gated on `profile.openalex_author_id` ⟹ the cache is warm from a prior Settings→Refresh), so opening the tab makes **zero network calls** ("explicit refresh, never on plain tab open"). Headline metrics (citations/h-index/i10/works) are OpenAlex's **authoritative figures over the whole indexed record** — shown verbatim + attributed ("source: OpenAlex · as of <date>"), never a callosum-invented composite "impact score" (computing them over the library subset is forbidden — it would disagree with Scholar + erode trust); the indexed-vs-library gap is a fact + import nudge. The author object inc-78 already cached carries `cited_by_count`/`summary_stats`/`counts_by_year`, so the stats need **no new API call** (re-parsed via an enriched `_author_from_obj`; a shared `_author_cache_key` keeps `resolve_author`/`cached_author` from drifting). The **editable AI research summary** is the sole egress — LLM narration over the user's OWN publication titles/abstracts (library text), gated at the inc-58 seam (`EgressGatedResearchSummaryGenerator`; egress-off → 503), marked an editable non-load-bearing draft. The tab reuses the LibraryFrame tab system (`type:"dashboard"`); charts are hand-rolled SVG (no chart library, per spec). Migration **0010** (`profile.research_summary`). Layers 2–4 deferred. |
| "Unsorted" library view = a `needs_review` query param on `GET /papers`, filtering an `imported_source` allowlist (inc 80) | Surfaces papers whose metadata still needs review (raw `pdf-scaffold`, `crossref-unresolved`, or NULL source) instead of letting them disappear into the library — aligned with "silence is not a certificate." Same class of change as the inc-63 axis filter / inc-69 sort: `list_papers(needs_review=…)` filters `imported_source IN NEEDS_REVIEW_SOURCES OR IS NULL` (a **local literal allowlist** in `repository.py` — bound-param `IN`, rule #3; kept local to avoid an `enrichment → repository` import cycle, since the strings are stable DB values). Composes with the deleted/q/axis/tag/pagination clauses (trashed excluded). Frontend: a `libraryNeedsReview` view-state mirroring `trashView` (exclusive with trash/axis/tag/focus but keeps checkbox-select on → select-all → bulk re-resolve/export/delete) + an **Unsorted** header toggle (reuses `.trash-toggle`, label flips to "← Library", no new CSS) + a clearable `.focus-card` banner. **No migration, no new endpoint, no egress.** |
| My Publications = an OpenAlex-resolved, LLM-free auto-axis with facts-vs-candidates + confirm-and-learn (inc 78) | The own-papers axis makes an **authorship claim**, so it follows the facts-vs-candidates principle: ORCID/DOI matches are **confirmed members** (`cluster_node_papers.confidence` 0.95 → "assigned"); name-only matches are **candidates** (0.25 → the existing "uncertain" tier), confirmed/rejected by the human and **persisted** in `my_publication_decisions` (a rejected paper is never re-proposed; a confirmed one becomes a manual `confidence IS NULL` member surviving every re-match). The resolver (`clustering/my_publications.py`) rewrites only the AUTO memberships each run (preserves manual). **LLM-free** (author disambiguation is structured-metadata work — zero tokens); OpenAlex author/works lookup is **metadata egress** (public name/ORCID/DOIs, like the Crossref DOI lookup), explicitly **NOT** the Gemini library-text gate. New `integrations/openalex/author.py` (`OpenAlexAuthorClient`, fail-closed + cached), `persistence/profile_repo.py` (single-row profile + decisions), migration **0009** (`axes.kind` + `profile` + `my_publication_decisions`). The import hook (`enrichment.py`) is a **cache-based, lazy-imported, try/except-guarded no-op when unused** → strictly additive (existing import/axis/summary paths untouched). The pinned card reuses `AxisItem` branched on `kind` (no fork). Part 2 (the impact dashboard tab) is deferred. |
| Acquisition bright lines enforced structurally via the `OaLocation` seam (inc 74) | The legally-clear OA-acquisition lane must never become a generic/non-OA fetcher. Rather than enforce that by convention, the `Resolver` Protocol returns a **frozen `OaLocation`** whose `oa_color` is **required** (gold/green/bronze; **no "closed"/"none" member**) and the downloader `download_oa_pdf(location: OaLocation)` takes the dataclass — there is **no function that fetches a bare URL**. So OA-ness is decided by the database (OpenAlex), never by callosum, and an arbitrary/non-OA fetch is structurally inexpressible (same seam-enforcement idea as the inc-58 egress gate; pinned by structural tests). Fetched copies land in the **local library** (`managed` storage, named per the existing `Authors - Year - Venue.pdf` convention) — nothing server-side. Honors the `APPROACH-AVOIDANCE.md` no-paywall-circumvention veto + realizes the A8 access-equity value. New `app/backend/acquisition/` + `integrations/openalex/` + migration 0007. The legally-ambiguous lane is deferred (counsel-gated), **absent** from this build. New resolvers (inc B) register into `build_default_registry` without editing the cascade. |
| OA resolver cascade fanned out to 7 sources, gold→green→preprint, first authorized copy wins (inc 75) | Increment B realizes the inc-74 seam's promise: `build_default_registry` registers OpenAlex (primary, best-of) then **DOAJ** (gold) → **Europe PMC** (OA full text) → **Crossref-OA** (publisher PDF + registered license) → **CORE** (green repo) → **arXiv** → **bioRxiv/medRxiv** → **OSF/PsyArXiv** (preprints). Each is the same shape as the OpenAlex adapter (injectable `fetcher` Protocol, `external_api_cache` under a distinct provider, `lookup_oa → OaLocation|None`, fail-closed) + a thin resolver; the `resolve()` loop is **untouched** (new sources only `register()`). OA-ness stays each database's assertion — a source with no honest https direct-PDF returns **None**, never a landing page or a guess (DOAJ requires a real PDF link; Europe PMC requires `isOpenAccess=Y`; Crossref-OA requires a registered license, CC→gold else bronze). Shared `integrations/api_cache.py` (the pre-existing openalex/crossref keep their private copies — not refactored). **CORE** needs `CALLOSUM_CORE_API_KEY` (Bearer header, never in a URL/cache/log; **absent → silent no-op**). **arXiv** reads the Atom id with a targeted regex, NOT a stdlib XML parser (XXE/entity surface on untrusted input, rule #4) → **no new dependency**. No new endpoint/migration/frontend (the Acquire button + OA chips already work); migration head stays 0007. Audit `.claude/security-audits/2026-06-20_oa-acquisition-b.md` PASS. Increment C (wanted-list + OA-only re-check) is next. |
| Wanted list + auto-acquiring OA re-check + coverage (inc 76) | Completes the acquisition arc's **track** loop. A persistent `wanted_items` table (migration **0008**; library-linked `paper_id` set, or external `paper_id` NULL with its own doi/pmid/title) backs a unified wanted list that auto-includes PDF-less library papers (`sync_from_library`) and accepts external adds. A manual async **re-check** (`acquisition/wanted.py::run_recheck`, kept out of the router for testability) runs the **same registry cascade** over open wants and **auto-acquires** hits — library wants fill the existing paper; external wants `create_paper` then `import_oa_pdf` (which enriches from Crossref). The OA-only bright line is **free + structural**: the re-check resolves only through the `ResolverRegistry` (which can return only an `OaLocation`), so there is no non-OA/arbitrary-URL path (test-pinned). External wants are fulfilled **only with a doi/pmid** (title-only → skipped `needs-id`) so a paper is never minted from a fuzzy match; soft-deleted papers are excluded from sync/coverage/re-check; per-item errors never abort a run; a logged per-run cap bounds bulk fetching. New `persistence/wanted_repo.py` + `acquisition/wanted.py` + `routers/wanted.py` (`/wanted` CRUD + sync-library + coverage + async recheck) + `26_wanted.jsx` (a Wanted modal in the lib-head). **No new dependency.** Audit `.claude/security-audits/2026-06-20_wanted-list.md` PASS. This completes Acquisition A/B/C. |
| Generic `JobStore[R]` for async jobs + ruff is the linter (release-readiness Phase 5, 2026-06-20) | The four async-job subsystems (summarize, axis score, axis suggest, dedup) each carried a near-identical `_XJob` dataclass + `_XJobStore` class differing only in the result type — consolidated into one thread-safe generic `app/backend/api/job_store.py` (`Job`/`JobStore[R]`), instantiated per-subsystem in `create_app` and typed `JobStore[XResponse]` at each use. **New async jobs reuse `JobStore`, don't re-roll a store.** Linting/formatting is **ruff** (config in `pyproject.toml`: line-length 120, `select=E,F,W,I,B`, `ignore=E501`, bugbear `extend-immutable-calls` for FastAPI `Depends`/`Query`/… so B008 doesn't false-positive); `requirements-dev.txt` carries the dev/CI toolchain (pytest, httpx, ruff, pip-audit, playwright, pytest-playwright). Run `ruff check --fix .` + `ruff format .` before committing. |
| Local-first FastAPI + SQLite, browser frontend | Lowest-friction local-first path; keeps everything free and offline-capable; no server to operate. |
| `sqlite-vec` as the vector store (not a separate vector DB) | In-process, single-file, zero daemon — fits the local-first, single-user model and the SQLite metadata store. |
| **Post-generation verification over trusting LLM citations** | The core thesis: LLMs hallucinate citations. Every summary sentence is re-checked locally (embedding + NLI + verbatim quote) and shown with evidence. See invariant #1. |
| **Gemini egress off by default** (`CALLOSUM_ALLOW_DATA_EGRESS`) | Library text must never leave the machine without explicit consent; default-deny with `DataEgressDisabledError`. Local models do everything else. |
| `pdf-points-top-left` coordinates + percentage overlays | A single canonical coordinate space (stored once) rendered as page-percentages keeps highlights aligned across zoom and responsive resizing; rotated pages degrade to page-open-only. |
| exact / region / null `coordinate_precision` | Honesty contract — the UI must never present an approximate or absent location as an exact quote highlight. |
| Modular `app/frontend/` source + a rebuilt single-file `callosum-app.html` artifact (inc 37) | Splitting the 2023-line monolith for directed review while preserving the single file (file-based UI testing expects it). Source of truth: `app/frontend/` (`index.html` shell + `styles.css` + ordered `js/*.jsx`). `app/backend/api/frontend.py` concatenates them into one document (JSX into a single `<script>`, so the shared global scope is identical to the old file); `tools/build_frontend.py` writes that to `callosum-app.html` (byte-identical to the pre-split file). `/` serves the built `callosum-app.html` when present (default), else assembles live (never broken); `CALLOSUM_FRONTEND_PATH` overrides. Trade-off vs the old "no build step" rule: editing the UI now means re-running `build_frontend.py` (the live-assembly fallback keeps the server correct meanwhile) — no bundler, still no extra file-serving surface. **Superseded in part by inc 102:** the JSX is now esbuild-**precompiled** at build time (the `<script type="text/babel">` + babel-standalone CDN are gone); `build_frontend.py` now requires the `npm install`ed esbuild, and the "byte-identical to the old hand-maintained file" property no longer holds (the script is transpiled). |
| Supervised axes expose `axis_scoring.py` with NO migration (inc 38) | Manual-vs-scored assignment = `cluster_node_papers.confidence IS NULL` (manual override) vs a float (scored) — the column was already nullable and the scorer always writes a float, so no schema change. Staleness reuses the axis embedding's stored `source_text_version` + `normalization` (recompute the current axis text-version, compare) — no stored flag needed. Scoring runs async (mirrors the summarize job; fully local, no egress); tiering is calibrated per the inc-39 row (absolute 0.7/0.5 thresholds were unreachable for MiniLM and replaced by relative natural-break). Re-score preserves manual adds (snapshot NULL rows → restore after `score_axis` rewrites the scored set), honoring "the human overrides the embedding". |
| Axis tiering is RELATIVE (natural-break), not absolute (inc 39) | `all-MiniLM-L6-v2` cosine between a short axis phrase and paper metadata is compressed near 0 (observed max ~0.37, median 0.02), so absolute 0.5/0.7 cutoffs assigned nothing. New `assignment_mode="natural_break"` + `SUPERVISED_AXIS_CONFIG` (floor 0.2, minimum_gap 0.03): **assigned** = the cluster above the largest gap in this axis's ranking (≥ floor); **uncertain** = the rest of the eligible; never-empty fallback shows the closest few. The 0.2 floor is a documented MiniLM constant. Tiers are **recomputed on read** from the stored confidences (`natural_break_assigned_ids`, same config) so read == score with NO persisted tier column / migration. Raw similarity still shown honestly. Axis text is **punctuation-normalized** before embedding (inc 40, `strip_punctuation` in `embeddings/models.py`) so phrasings differing only in punctuation/spacing (e.g. "anomalous-is-bad" ≡ "anomalous is bad") embed identically; axis-side only (papers unchanged). |
| Gemini axis synonym suggester is egress-gated + human-curated (inc 41) | `POST /axes/suggest-terms` (sync, stateless) proposes related terms via Gemini; the user curates them in a modal and the chosen terms fold into the axis **description** (reuses the existing axis-text→embed + staleness paths — no new persistence/migration). Mirrors `GeminiSummaryGenerator`: opt-in via `CALLOSUM_ALLOW_DATA_EGRESS` (off → 503 before any genai call), only the user's own axis text leaves the machine, model output is deduped/capped/echo-stripped, failures → 502 (never 500). The suggester is injectable (`api.state.axis_term_suggester`) so tests are hermetic. |
| Git + GitHub (public, AGPL-3.0) is the off-machine backup; zip snapshots + Dropbox are secondary | Git was adopted in the release-readiness arc (~inc 74; remote `github.com/cliffworkman/callosum` + CI). Convention: **commit + push at end of each work session by default** (the user's geographically-orthogonal backup must not drift behind — see Backup & snapshot protocol). Zip snapshots + Dropbox version history remain as local belt-and-suspenders. |
| Increment-based development with `INCREMENT-NN-NOTES.md` | A lightweight, durable design diary that survives session resets and records the manual verification for each change. |
| 600-line hard limit on app source | Keeps files scannable, responsibilities separated, and review tractable; forces per-concern modularity. |
| One shared `annotations` table for imported + user + synthesis (inc 30) | The Zotero importer already owned `annotations`; rather than fork it, native highlights extend it with nullable columns and a `source` discriminator (imported rows leave it NULL; viewer lists `source IN ('user','synthesis')`). Keeps one home for all annotation origins. |
| User highlights reuse the increment-29 overlay model in a separate layer (inc 30) | Highlights store `pdf-points-top-left` bboxes and render as page-percentages (zoom-robust), in their own `.pdf-annotation-layer` distinct from the citation layer so the two never clobber each other; delete via click hit-testing keeps the text layer free for selection. |
| Highlight notes + management panel; `PATCH /annotations/{id}` (inc 31) | First update endpoint — partial (note/color only; geometry immutable), `model_fields_set` distinguishes omit vs explicit-null note, note capped at 4000. The management panel is a collapsible **inside the PdfViewer** (not a RightPane tab) so it's inherently scoped to the open PDF and can jump+flash locally without cross-component target plumbing. |
| Brand assets in `app/media/*.png`, inlined as base64 in the frontend source (inc 32; relocated inc 37) | `logo.png` (sidebar header) + `favicon.png` are embedded as `data:` URIs rather than served via a `/media` route/mount — no new file-serving surface, frontend stays self-contained. Post-inc-37 the favicon lives inline in `app/frontend/index.html` and the logo in a `app/frontend/js/*.jsx` chunk; `tools/inline_brand_assets.py` re-inlines from the PNGs (the source of truth). |
| JATS abstracts: store raw, render structured (inc 33) | `papers.abstract` keeps the raw Crossref JATS XML fragment; `clean_abstract_for_display` (`app/backend/metadata/abstract_display.py`, stdlib `HTMLParser`) produces a derived `abstract_display` — a small **allowlisted, attribute-free** HTML string (`p/em/strong/sub/sup`, text escaped, unknown tags dropped). Same store-raw/clean-a-copy ethos as quote canonicalization. **inc 55:** since inc-49 made the Detail pane an editable **textarea**, it now binds to a new tag-free **`abstract_text`** (`abstract_plain_text`, the same lenient parser → plain text) — NOT the HTML `abstract_display` (the `dangerouslySetInnerHTML` render is retired from the editable pane). The same `abstract_plain_text` also feeds `axis_suggestion._paper_tokens` so JATS tag names never become suggested terms. (The abstract's JATS noise still lives in `paper_embedding_text` → embeddings; cleaning that is deferred — needs a `PAPER_TEXT_VERSION` bump + re-embed.) |
| Auto-migrate the DB to head on startup — loud + honest health (2026-06-17) | `create_app`'s lifespan runs `alembic upgrade head` (absolute `script_location`, failure logged-not-fatal) against the configured DB before serving, so a database that predates a migration self-heals instead of 500-ing on writes. It is **loud** (`_loud()` → INFO check, WARNING "auto-migrated X→Y", INFO "already at head", ERROR on failure) on stdout — `_loud` re-enables the `callosum` logger because Alembic's `env.py` `fileConfig` historically silenced it mid-migrate. **Release-readiness Phase 4 fix (2026-06-20):** `env.py` now passes `fileConfig(..., disable_existing_loggers=False)` so a migration no longer disables app loggers at all — it previously left `callosum.llm.usage` disabled after a real startup migration, silently killing inc-61 token-usage logging until restart (`_loud` only revived the `callosum` parent). `_loud` is kept as defense-in-depth; regression-tested by `tests/test_usage_logging.py::test_logger_survives_alembic_migration`. `/health` is honest: `db_migrated` now means **at head** (current revision == head), plus `db_revision`/`db_head_revision`. Frontend mutating calls also surface failures (`console.warn` + a `.pdf-toast`). |
| Multi-line highlight compositing: per-annotation isolated group + multiply (inc 35) | Each annotation's per-line rects are painted **opaque** inside one `.pdf-user-highlight-group` (`position:absolute; inset:0; isolation:isolate; mix-blend-mode:multiply; opacity:0.7`) — opaque same-color rects union with NO overlap doubling, then the group composites once (uniform on every row, darkens toward the text). Per-fill `multiply` does NOT work (it compounds at overlaps). Don't add per-fill alpha/borders (they reintroduce the band/seams); tune strength via the group `opacity`. Geometry/percentage model unchanged. Citation overlay left as-is (low-alpha/bordered/transient → no visible doubling). |
| PDF page render: single-source the scale, DPR-aware, no responsive shrink (inc 34) | Every per-page layer (canvas, `.textLayer`, overlay layers, wrapper) derives from ONE `getViewport({scale})` with the **exact un-floored** CSS size (`cssW=viewport.width`, `cssH=viewport.height`); the canvas backing store is device-resolution (`round(css*dpr)` + render `transform:[dpr,0,0,dpr,0,0]`) with its CSS box set to the exact size; `--scale-factor = scale`. Do NOT floor one layer differently or shrink the canvas responsively (that desyncs the fixed-px text layer → progressive drift) — a too-wide page scrolls (`.pdf-scroll{overflow:auto}`). Zoom re-renders (never CSS-transforms a stale layer); a `matchMedia` DPR listener re-renders on HiDPI/browser-zoom change. The %-based highlight overlays stay correct across all of this. |
| Axis staleness = ANY stored embedding matches the current text, not newest-by-id (2026-06-19 fix) | `_embed_axis` accrues one embedding row per distinct scored text version and never prunes them, so judging freshness by the **newest row by id** made an axis read "re-score" forever when a merge/edit cycle revisited a prior text version (the stale row then has a higher id than the row matching the current text). `axis_score_state` now considers the axis fresh if **any** stored embedding's `source_text_version` matches the current text — and `score_axis` always embeds the current text, so a match means the live assignments reflect it. Self-heals existing DBs on read. Rows still accumulate (harmless — axis vectors are recomputed each score, never read from the store for scoring; a prune is a possible future tidy). |
| Author/index keywords as first-order tags = capture Crossref `subject`; mirror to `keyword:crossref` tags (inc 73) | Privilege the concept work authors/indexers already did. `_crossref_message_to_csl` now keeps `message.subject` in `csl_json`; `enrichment.apply_crossref_subject_tags` mirrors it to tags (provenance `keyword:crossref`) inside `enrich_paper_metadata_from_crossref` — so **🔎 re-resolve** + batch enrich auto-tag. `tags_repo.add_tag_to_paper` gained an `import_source` param (set on **create** only — a user tag is never relabeled) + `add_tags_to_paper`. **Full backfill** for the existing library via `tools/backfill_keyword_tags.py` (cache-first via `resolve_doi`; re-resolves the rest; **tag-only — never clobbers metadata**; idempotent). DOI-only to public Crossref (NOT the egress gate, per inc 49); **no migration, no new endpoint**. The inc-72 c-TF-IDF suggester is the second-order gap-filler; Zotero tags already import (inc 71). Bugfix: `TagsRow` re-syncs on a detail refetch (so 🔎-added chips show without a paper switch). **Deferred:** a provenance UI (`source` on the tag response; group/style/protect by source) + OpenAlex/PubMed sources + the tags↔findings cross-cut (see `INCREMENT-BACKLOG.md`). |
| Auto-suggest tags = local c-TF-IDF over the library (no Gemini); the per-paper analogue of axis suggestion (inc 72) | `clustering/tag_suggestion.py::suggest_tags_for_paper` ranks a paper's terms by **tf·idf** vs the live library (`tf · (log((N+1)/(df+1))+1)`), reusing `axis_suggestion._paper_tokens` (shared content tokenizer — keeps tags & axis terms one vocabulary), excluding the paper's current tags. **Purely local — no embeddings, no clustering, no egress/Gemini** (user's explicit choice; the egress-gated Gemini polish from `axis_suggestion.apply_labels` is deliberately omitted, addable later). `GET /papers/{id}/suggested-tags` (sync, read-only). Frontend: a ✨ Suggest button → candidate `.term-chip`s the user clicks to accept (via the inc-71 add path). **Follow-up (user):** treat imported **author keywords as first-order tags** (this c-TF-IDF is the second-order gap-filler); see `INCREMENT-BACKLOG.md` "Author keywords as first-order tags" + the tags↔findings/system-facts cross-cut. |
| Tags = free-form labels on the pre-existing `tags`/`paper_tags` tables; data access split to `tags_repo.py` (inc 71) | Lightweight manual labels (the complement to semantic axes). The tables already existed (Zotero importer populates them via `_upsert_tags`), so **no migration** — just a UI + endpoints. New `persistence/tags_repo.py` (`repository.py` was at 591, so the cohesive tag concern got its own module, like inc-67's `dedup_repo.py`): `get_tags_for_paper`, `list_tags` (+counts), `add_tag_to_paper` (trim/cap, **get-or-create** by UNIQUE name, `INSERT OR IGNORE` link → idempotent), `remove_tag_from_paper` (+**prune orphan tag**). `GET /tags`, `POST`/`DELETE /papers/{id}/tags*` (`routers/tags.py`); `PaperDetailResponse.tags`; a `tag_id` filter on `GET /papers` (IN subquery, mirrors inc-63 axis filter). Local, bound-param, non-destructive (manages links; pruned orphan tags only); names rendered as plain text (no XSS). Frontend: Details `TagsRow` (chip name→`filterToTag`, ×→remove, add-input + `/tags` datalist) + the axis-filter UI mirrored (`libraryTagFilter`, mutually exclusive with the axis filter) + a "Filtered to tag …" banner. |
| Citation export = stored `csl_json` → BibTeX/RIS/CSL-JSON; one endpoint serves download + copy (inc 70) | The first way to get citations **out**. `app/backend/metadata/citation_export.py` (pure formatters: `to_bibtex`/`to_ris`/`to_csl_json` + `render_citations` dispatch) reads `csl_json` (scalar-column fallback; abstract via `abstract_plain_text` → JATS-stripped) and **escapes its output format**. `POST /papers/export {paper_ids, format: Literal}` → `get_papers_for_export` (bound-param `IN`, **live papers only**) → returns a `Response` with the format's media type + a **constant** `Content-Disposition` filename. **Read-only, local (no egress), no migration.** BibTeX entry type from CSL type; key = `citation_key` else `{family}{year}`, **deduped**. The frontend can't use `apiPost` (it forces `.json()`), so a **raw fetch** does blob→`<a download>` (bulk bar picker) and text→`navigator.clipboard` (Details "Cite" row, reuses the inc-68 `.btn-link`; clipboard OK on the 127.0.0.1 secure context). |
| Sort the library = a `sort` query param on `GET /papers`, key from an allowlist (inc 69) | The library only ever listed in import order. `repository._paper_sort_order(sort)` maps a `sort` key (`added`/`recent`/`title`/`year_desc`/`year_asc`/`author`) to ORDER BY **constant column expressions** — the key indexes an **allowlist**, never reaching SQL text (rule #3); unknown → default `added` (= prior `id ASC`). NULL year/author sort **last** (`col IS NULL` first key); `papers.id` is always the final stable tiebreak (deterministic pagination). A `sort` query param on `GET /papers` (no new route, no migration, no egress) composes with q/deleted/axis_id/pagination (ORDER BY vs WHERE). Frontend: a Sort dropdown in the library pane-head (`librarySort` state, resets to page 1; omitted from the URL when `added`). |
| Filter the library by axis = an `axis_id` filter on `GET /papers` + a clickable count badge (inc 63) | Clicking an axis's **count badge** (`15_axes.jsx`, now a button) sets `40_app.jsx` `libraryAxisFilter` `{id,label}` → the `/papers` fetch adds `&axis_id=N` → the Library narrows to that axis's papers, with a clearable "Filtered to axis …" banner (reuses the inc-50 `.focus-card`). Server-side: `repository.py::list_papers(axis_id=…)` = a **bound-param `IN` subquery** over `cluster_node_papers`→`cluster_nodes` (unions the axis's cluster nodes; composes with the `deleted_at`/`q`/pagination clauses → trashed excluded; rule #3). The filter is a *view* (mutually exclusive with trash/focus — they clear each other — but keeps `selecting` on), so it pairs with inc-62: filter → **select all** (new `.lib-select-all`, current page) → **summarize** = a verified synthesis of a topic cluster. No new endpoint/egress/ingestion/migration (route path unchanged → route-surface invariant intact); read-only. |
| Multi-paper summary = wire the library checkbox selection to the papers-scope synthesis; round-robin chunk coverage (inc 62) | The library bulk bar's **summarize** button drives the always-on Synthesis pane to run the existing `/summarize` **papers** scope over the checkbox-selected ids (`40_app.jsx` `pendingSummarize` nonce → `RightPane` → `20_synthesis.jsx` `useEffect` → shared `launch()`), with an "N selected papers" scope-note badge; reuses the verification spine + inc-61 cache (no new endpoint/egress/ingestion/migration). **Coverage fix:** `pipeline.py::_round_robin_by_paper` interleaves chunks across the selected papers before the `top_k` slice for a multi-paper **no-query** scope (a plain `rows[:top_k]` is chunk-id-ordered → fills from the lowest-id paper and ignores the rest); **≤1 paper → identity**, query scope untouched (it already spreads via ranking); also improves the cluster-node scope. Client `top_k = min(max(8, n), 24)` (each selected paper gets ≥1 chunk, bounded). The **critical-review supplement** stays deferred behind the Auditability standard. |
| LLM token spend = a content-addressed SQLite cache on the summary path; verification always re-runs; egress unchanged (inc 61) | A cache hit costs zero tokens (the dominant lever). `CachedSummaryGenerator` (`app/backend/llm/cache.py`) wraps the token-expensive `generate()` step keyed by `sha256(canonical_json({cache_signature, chunk set [id, chunk_version, text], scope_ref}))` — `cache_signature` = `gemini-summary-generator/<model>/<SUMMARY_PROMPT_VERSION>`. Any input change → new key → automatic miss (NO explicit invalidation; negative results cached free). Stored in `llm_cache` (migration 0005). **Correctness:** layered `EgressGated(Cached(real))` so egress-off errors before the cache is consulted (gate unchanged); uses the pipeline's existing `conn` (a 2nd SQLite connection mid-txn would lock); **verification (`pipeline.py:85–94`) re-runs on every result, cached or fresh** — a hit replays cached *candidates* and re-verifies them, never serving a stale verdict. `generate()` gained an optional `conn` kwarg (internal Protocol, backward-compatible). `SUMMARY_PROMPT_VERSION` is in the key, so editing the prompt/model can't serve old outputs. Usage logging (`llm/usage.py`) at all 4 sites instruments token spend. Other levers (cache extension to help/labeler/suggester, output caps, top_k, provider prefix caching, Batch API) are **proposed + deferred for review**. |
| AI help assistant = a SEPARATE consent gate (not the library egress flag), seam-enforced, references deep-link the docs (inc 60) | `POST /help/ask` answers a help question from the **public** help corpus and returns references the UI deep-links via `flashHelpSection`. It is gated by its **own** `CALLOSUM_HELP_ASSISTANT_ENABLED` (new `GeminiConfig.help_assistant_enabled`), **independent** of `CALLOSUM_ALLOW_DATA_EGRESS` — it sends only the question + public help docs, never library text, so it works with the library gate off (proven by a test + a library-egress-off live E2E). Provider-neutral `HelpAssistant` Protocol (`app/backend/help/assistant.py`) + `GeminiHelpAssistant` (`integrations/gemini/help_assistant.py`, **NO RAG** — whole corpus stuffed via `help_corpus_prompt()`); enforced at the inc-58 seam (`EgressGatedHelpAssistant` + `HelpAssistantDisabledError` in `egress.py`; provider self-check is defense-in-depth). Multi-turn (stateless; frontend passes history, capped at the boundary); defensive parse (failure → answer text, no refs, never 500); the router **drops any `section_id` not in the live corpus**. Additive — no existing path/API shape touched. |
| Help content = a served markdown corpus + a navigable modal; static tips retired (inc 59) | The in-app help is now `app/backend/help/help_content.md` (markdown asset, sections delimited by `<!-- section: <id> -->` markers giving **stable anchor ids** independent of heading text), parsed by `app/backend/help/corpus.py` into `HelpSection(id, title, html, text)` and served by `GET /help/corpus` (stateless, no DB, **no egress** — docs render offline / when the assistant is off). `render_html` is a small **allowlisted** markdown renderer (no new dependency: p, ul/li, strong/em/code, h3, a[href] limited to http(s)/`#`; all text escaped — same posture as `clean_abstract_for_display`); the frontend (`18_help.jsx`) renders it with `dangerouslySetInnerHTML` (safe: app-owned static + escaped). The modal is a TOC + sections; `flashHelpSection(id)` (hoisted, reuses the `jumpToAnnotation` flash) scrolls-to + highlights a section — the hook the inc-60 help-assistant references reuse. First draft generated by **Codex** (token-saving), reviewed against the code, then shipped. `help_corpus_prompt()` (the stuffed corpus) is defined now for the inc-60 assistant. The corpus is kept current via the `HELP-DOCS-SYNCED` changelog marker (see Change tracking). |
| Data-egress enforcement is a provider-neutral gate at the DI seam, not per-provider convention (inc 58) | `DataEgressDisabledError`'s canonical home moved to `app/backend/llm/egress.py` (re-exported from `integrations/gemini/generator.py`, so every existing import path resolves to the same class). Three egress-gating wrappers (`EgressGated{SummaryGenerator,AxisTermSuggester,AxisClusterLabeler}`) conform to the existing protocols and are applied in the **router factories** (`_summary_generator`, `_axis_term_suggester`, `_axis_cluster_labeler`), so the gate covers the **injected** provider AND the default — closing the hole where a `create_app(...)`-injected provider was returned unchecked (protected only by the provider self-gating by convention). The wrappers read the same `GeminiConfig.from_environment().data_egress_enabled` flag; egress-on → delegate unchanged; egress-off → raise the same `DataEgressDisabledError` (summaries job `error`; suggest-terms 503 via the existing handler; labeler → `apply_labels` local fallback, never 503). Providers keep their internal checks as **defense-in-depth**. Tests model consent via an autouse conftest fixture (`CALLOSUM_ALLOW_DATA_EGRESS=1` default; egress-off tests `delenv`). No migration, no new route, no API-shape change. (`tools/validation_harness.py` builds Gemini directly — a dev tool, not the seam — left to its self-check.) |
| Right pane = vertical Synthesis/Details split (not tabs); draggable `detailH` persisted (inc 57) | `RightPane` (`20_synthesis.jsx`) is a flex column (`.pane-split`): **Synthesis always on top** (`.rp-synth`, flex:1, own scroll) and — **only when a paper is selected** — its editable **Details** below (`.rp-detail`, fixed `detailH`, own scroll) with a `.divider-h` drag grip between. No more Synthesis/Detail tabs (retired with their CSS). `detailH` persists to `localStorage["callosum.detailH"]` (clamp [180,760]). Reuses the inc-42 resizer — `_beginDrag` now passes **both** `clientX` and `clientY` (horizontal side callers still use x; the vertical split uses y; the helpers are hoisted globals so the earlier chunk can call them). Frontend-only; DetailContent/SynthesisPane unchanged; Details aren't mounted when nothing's selected (Synthesis fills the pane). |
| Un-dismiss / manage dismissals = list + remove dismissed pairs; dedup-dismiss data access split out (inc 67) | Adds the in-app undo inc-64 deferred: the Duplicates modal's **Previously dismissed** section lists the pairs you marked "not a duplicate" (joined to `papers` for titles) and **un-dismisses** them so the scan flags them again. `GET /papers/duplicates/dismissed` (registered **before** `/papers/duplicates/{job_id}` so the literal "dismissed" isn't captured as a job id) + `POST /papers/duplicates/undismiss {paper_ids}` (non-destructive — drops a preference; idempotent; local; bound-param). No migration (reuses the inc-64 table). **Forced module split (rule #1):** the two new data-access fns pushed `repository.py` to 604 (>600), so the cohesive dedup-dismiss concern (4 fns on `dismissed_duplicate_pairs`) was **moved verbatim** to new `persistence/dedup_repo.py` (63; repository.py→555); the two importers (`clustering/duplicate_detection.py`, `routers/duplicates.py`) repointed. |
| "Not a duplicate" dismiss = persistent pair table, dropped before union-find; flag-only, local (inc 64) | A session-only dismiss (inc 56) re-flagged the same false positives every scan. Now `POST /papers/duplicates/dismiss` stores the group's canonical `(low<high)` pairs in **`dismissed_duplicate_pairs`** (migration 0006; FK CASCADE + unique), and `find_duplicate_groups` **drops dismissed pairs before the union-find** so the group never re-forms. Non-destructive (records a preference, never deletes), **local** (no egress), bound-param `INSERT OR IGNORE` (rule #3); the endpoint validates `paper_ids` to ≥2 existing live papers (else 422). Extending dedup pushed `routers/papers.py` to 636 (>600) so the duplicates concern was **moved verbatim** to **`routers/duplicates.py`** (157; papers.py→497), included **before** `papers.router` so `/papers/duplicates*` wins. Deferred: an un-dismiss / "manage dismissals" UI; per-pair (vs whole-group) granularity; library **merge**. |
| Duplicate detection = layered (identifier→title→embedding) + union-find, flag-only, local (inc 56) | `POST /papers/duplicates` (async job, mirrors `/axes/suggest`) → `find_duplicate_groups` (`app/backend/clustering/duplicate_detection.py`): three layers — shared `csl_json` PMID/arXiv (DOI can't collide, it's UNIQUE) conf 0.99 → identical canonical title (`normalize_text(strip_punctuation)`) + author + year (0.97; year-differs 0.85) → embedding cosine ≥0.92 (high → not same-topic; reuses axis_suggestion's in-memory numpy `V@V.T`, guarded `MAX_EMBED_PAPERS`) — merged via **union-find** into groups. Live papers only; **ephemeral** (nothing persisted); **flag-only** — never auto-deletes/merges. Entirely local (no Gemini/egress). The review modal (`19_duplicates.jsx`, "Duplicates" button in `.lib-head`) lets the user **delete** the redundant copy (reuses the inc-54 soft-delete → Trash, reversible), **open**, or **dismiss** (session-only). Routes registered before `/papers/{paper_id}` (literal "duplicates" segment). Library **merge** + persistent "not a duplicate" deferred. |
| Permanent delete = trashed-only purge that removes embeddings + vectors before the paper row; supersedes inc-54's hard-delete deferral (inc 65) | Completes inc-54: a **trashed** paper can be permanently deleted (per-paper **Delete forever** or **Empty Trash**). The unsafe part inc-54 deferred was orphan-crash: `embeddings.target_id` has **no FK** + the store had **no delete**, so deleting just the paper left embeddings + sqlite-vec vectors behind → an orphaned paper-embedding crashes `retrieval._resolve_hit`'s `.one()`. Fix: new `VectorStore.delete`; `repository.purge_paper` deletes the paper's embeddings rows (`target_type` paper→id, chunk→its chunk ids) **and** their vectors **before** `DELETE FROM papers` (FK CASCADE handles chunks/annotations/attachments/cluster_node_papers/dismissed_pairs/…), all in one txn → no orphan. **Trashed-only** (`purge_paper` returns False on a live paper → 404) so a live paper can't be purged in one step; UI double-confirms. `DELETE /papers/{id}/permanent` + `POST /papers/trash/empty`; local-only, **no migration** (pure DML). Deferred: doesn't delete the on-disk PDF. (The trashed-but-not-purged retrieval leak was closed in inc 66.) |
| Retrieval excludes trashed papers (inc 66) | A soft-deleted (in-Trash, not-yet-purged) paper must not be cited in a **new** synthesis. The synthesis path is NOT `search_similar` — `summarization/pipeline.py::_source_chunks_for_scope` builds its own candidate SQL, and the **query** scope was `select(chunks)` with no paper filter (every paper). Fixed there with a live-paper filter (`paper_id IN (papers WHERE deleted_at IS NULL)`) — covers query, hardens papers/cluster scopes. Also hardened the general `retrieval._candidate_embedding_ids` primitive (excludes paper/chunk embeddings of trashed papers; used by the validation harness). Backend-only, no migration; behavior-preserving when nothing is trashed. A *purged* paper (inc 65) is already fully gone. |
| Paper delete = soft (`papers.deleted_at`) + Trash/Restore; hard-delete deferred (orphans embeddings/vectors) (inc 54) | There was no way to delete a paper. Delete is **soft + reversible**: `DELETE /papers/{id}` stamps `papers.deleted_at` (migration 0004, additive nullable, head 0004), hiding the paper from the library listing, axis clusters, and clustering (`suggest_axes`) but keeping every row. `POST /papers/{id}/restore` clears it; `GET /papers?deleted=true` is the Trash listing. **Hard-delete is deliberately NOT shipped** — `embeddings.target_id` has no FK and the vector store has no delete method, so a hard cascade orphans the paper's embeddings + sqlite-vec vectors and an orphaned paper-embedding **crashes** `retrieval._resolve_hit`; permanent-delete / empty-trash is its own deferred increment (needs `VectorStore.delete` + a `purge_paper`). `get_paper` stays unfiltered (Restore + detail resolve by id). Frontend: checkbox multi-select + bulk bar (mirrors inc-43) + a Trash⇄Library toggle + per-row Restore (`10_pdf_layer.jsx`/`40_app.jsx`); the three row modes (normal/focus/trash) are mutually exclusive. Known deferred limitation: trashed papers can still surface in *new synthesis retrieval* until `retrieval` filters `deleted_at`. |
| Suggest optimal axes = local clustering + coverage-with-diversity + egress-gated Gemini labels (never 503) (inc 52) | `POST /axes/suggest` (async job, mirrors score) clusters the library's in-memory paper embeddings (`AgglomerativeAbstractClusterer`), drops clusters a current axis already covers (**novelty** ≥0.6 cosine) + skips near-duplicate clusters (**MMR-lite** ≥0.5), and labels each from its OWN papers (**local c-TF-IDF**). `app/backend/clustering/axis_suggestion.py` holds the math; `apply_labels` optionally polishes with `GeminiAxisClusterLabeler` (egress-gated before any genai import; sends only ≤12 representative TITLES) and **catches any failure → local label**, so the endpoint is **always local-capable and never 503s** (unlike `/axes/suggest-terms`). Suggestions are ephemeral; the user curates (rename + toggle term chips, selected-by-default) and creates via the existing `POST /axes` (`17_axes_suggest.jsx` ✨ modal). No migration; no new dependency (numpy/sklearn already present). |
| Manual axis assignment = `confidence IS NULL`, now authoritative + durable; ✓-confirm reuses the add endpoint (inc 50) | A human override (manual add / ✓-confirm of an uncertain paper) is stored as `cluster_node_papers.confidence = NULL`. Two `axis_scoring.py` fixes make this durable: `add_manual_assignment` **upserts** an existing scored row to NULL (so `POST /axes/{id}/papers` *confirms* an uncertain paper, not just adds a new one), and `restore_manual_assignments` **forces NULL even when present** after a re-score (so a manual pick that also scores above the floor doesn't silently revert to scored — also fixed a latent bug). B: the ASSIGNED tag is dropped (assigned = no tag; amber = uncertain; dashed = manual). C: the axis **＋** opens a **library focus-mode** (reminder card + per-row +add/−remove, **staged → Save**) reusing the same add/remove endpoints; the inc-38 in-card `AddPaperPicker` is retired. No new endpoint/migration/egress. |
| Editable Details edit `csl_json` (the canonical record); columns are projections; merge-not-reproject (inc 49) | The Mendeley-style editor needs NO migration because `papers.csl_json` already holds the full CSL record (and is returned wholesale) — volume/issue/page/dates/URL/ISSN/ISBN/PMID/arXiv/type live there; the scalar columns (title/year/venue/doi/…) are projections. `PATCH /papers/{id}` → `build_paper_update` (`app/backend/metadata/paper_edits.py`, pure) **copies** csl_json and merges ONLY changed keys + syncs the affected columns — a deliberate partial merge, NOT a blind full re-projection (which would wipe untouched fields). The curated core fields are always shown; a **"More"** section auto-surfaces any *extra scalar field a DOI populated* (the DOI decides what shows) via a length/charset/reserved-key-validated generic `csl` patch. DOI-UNIQUE clash → 409; empty title/no fields → 422. Frontend: inline always-editable fields (`.detail-edit`, auto-save on blur) in `app/frontend/js/25_detail.jsx`. |
| User-edits are provenance-stamped + protected from batch clobber; re-resolve forces (inc 49) | A hand-edit sets `imported_source="user-edited"`, which is **deliberately NOT** in `_can_update_from_crossref`'s allowlist → the batch library enrich skips user-edited papers (backlog G's "don't silently clobber edits"). The explicit per-paper `POST /papers/{id}/re-resolve` passes `force=True` to override the guard (the user asked) and **overwrites** the record from Crossref. Re-resolve sends **only the DOI** to public Crossref (exactly as import does) — NOT the Gemini library-text egress gate, so it is correctly not behind `CALLOSUM_ALLOW_DATA_EGRESS`; a Crossref/network miss returns `crossref-unresolved` gracefully (200, never 500). Crossref client is injectable (`create_app(crossref_client=…)`) for hermetic tests. |
| The tier cutoff acts on the displayed (2-decimal) confidence (inc 48) | `_confidence_from_cosine_distance` rounds to 2dp, so a paper's stored confidence == what the UI shows (`toFixed(2)`) == the value compared to the cutoff. Prevents the confusion where a 0.349 raw score displayed as "0.35" but was tagged UNCERTAIN (0.349 < 0.35). Round at the source so storage + score-time tier + read-time re-tier + display all use the identical number. |
| Connection status is encoded by the logo, not a text line (inc 47) | The brand logo is a `.brand-logo` `<div>` whose `background-image` swaps among four `--logo-*` tokens by `[data-theme]` × a `.connected` class (the "on" variants add a green dot in the brain's cell-body); driven by `conn.state === "ok"`. Retired the `ConnStatus` text line + `.conn`/`.led` CSS. The four logo base64 live in CSS `:root` vars (filled by `inline_brand_assets.py`), **NOT** the inline Babel script — four logos there would exceed Babel-standalone's 500KB deopt cap. Oversized PNG exports are recompressed losslessly (~57KB). |
| Dark mode = `data-theme` + CSS-variable overrides; the PDF page stays light (inc 46) | The dark theme overrides token *values* under `:root[data-theme="dark"]` (warm-dark) — because every chrome color flows through a token (the DESIGN.md consolidation), nothing else changes. `data-theme` is set on `<html>` by a **no-flash** `<script>` in `index.html`'s head before paint (`localStorage["callosum.theme"]`, else `prefers-color-scheme`); the Settings modal toggle writes the same. The **rendered PDF page is deliberately NOT themed** (its `#fff` + on-page overlay rgba + `--accent-overlay` stay constant — it's the document, not chrome); only app chrome themes. `--on-fill` flips (light fills → dark text) so primary buttons/badges stay legible. Theme-matched logo swaps via two CSS-toggled `<img>`; keep inlined PNGs small (they live in the 500KB-capped inline Babel script — `logo_dm.png` was recompressed 427KB→57KB). |
| Canonical `.btn-*` classes; consolidate by selector-grouping, not className migration (inc 68) | DESIGN.md §3 #5 (the ~10 near-duplicate button blocks). Added `.btn`/`.btn-primary`/`.btn-ghost`/`.btn-link`/`.btn-icon` + `.danger` as the single source of truth, and folded the cleanly-identical ad-hoc classes into them by **grouping their selectors** (`.axis-btn`+`.synth-actions button` primary; `.pginate button` ghost; `.axis-link` link; `.axis-icon-btn` icon) — only where every grouped property is byte-identical → **CSS-only, zero visual change, no JSX touched** (`.axis-link` has dozens of call sites; a className migration would be huge + regression-prone). Size-divergent ghost/icon buttons (`.axis-sort`, `.pdf-zoom button`, `.source-jump`, `.history-delete`, `.hl-editor button`, `.axis-new`, `.axis-x`, `.frame-tab-close`) left as-is — folding them would value-shift their look, so their migration (change JSX className → `.btn-*`) is deferred. Verified by computed-style equality in a live E2E (stronger than a screenshot). |
| Design dictionary (`DESIGN.md`) gates CSS changes (2026-06-19) | A two-pass design-principles doc (Pass 1 = the CSS as-is; Pass 2 = inconsistencies + canonical recipes + a consolidation worklist) tethers styling so new controls conform instead of drifting. **CLAUDE.md rule #8 requires reading it before any CSS / inline-style edit.** Built deliberately *before* the upcoming UI wave (sidebar density, settings + dark mode, synthesis redesign) so the standard is set first; Pass-2's "consolidate scattered hex into tokens" is also groundwork for dark-mode theming. Fixed color semantics: indigo `--accent` = provenance/primary; green `--verified` = grounded; amber `--flag` = unresolved/uncertain/region (status); red `--danger` = destructive. |
| Axis count badge encodes scoring status by color; no status text line (2026-06-19) | The per-axis count badge's **background color is the scoring-status indicator** — `--verified` (green) scored+fresh / `--flag` (amber) stale→re-score / muted neutral not-scored — and the textual `.axis-state` line ("scored" / "description changed — re-score" / "not scored yet") was removed to reclaim sidebar density (status now lives in the badge color + its tooltip). Supersedes inc-45's fixed-amber badge. |
| Axis assignment cutoff is absolute + per-axis adjustable, default 0.35 (inc 45) | Re-adopted an **absolute** cutoff (ASSIGNED = similarity ≥ cutoff; UNCERTAIN = `[0.20, cutoff)`) for the supervised badge, superseding inc-39's relative natural-break — which was **systematically too exclusive** on the smooth similarity declines real axes produce (the largest gap sits near the top → only 2–6 assigned). Viable now because inc-44's term curation lifted similarities to ~0.5–0.57 (well above inc-39's ~0.37). The cutoff ("gain") is **user-adjustable per re-score** (a flipper) and **persisted per axis** (`axes.scoring_gain`, nullable; NULL = `DEFAULT_AXIS_CUTOFF` 0.35; additive migration 0003). The read re-tiers from stored confidences against the axis's cutoff (no persisted tier); the 0.20 visibility floor + never-empty fallback are kept (never-empty gated to the absolute mode so `largest_gap`/`top_n` are unaffected). Recalibratable; eventual home = a Settings increment. |
| Axis title is cosmetic; the description (its `Related:` terms) is the embedded query (inc 44) | The title is a human-readable display name and is NO LONGER embedded — `_axis_text` returns the description only (which carries the curated terms via the `Related:` convention, primary term first), with a **fallback to the label when the description is blank** so legacy/label-only axes still score and **no migration is needed**. Editing/creating happens in one `AxisEditModal` (`14_axes_edit.jsx`); suggested terms are **deselected by default** (the human opts in — model as aid, not crutch) and selected terms sort to the top. Existing axes show stale → re-score once. Trade-off: a rename no longer changes scoring (intended); the curated terms are the query. |
| Axis merge = fold into a surviving row, but compose content from all sources; carry folded labels as `Related:` terms (inc 43) | The user rejected "one whole axis wins": merge keeps one axis row (its identity/`created_at`) but its label+description are curated in a **comparison view** from every selected axis. To avoid a "gap in the terms contributing to scoring", each **folded axis's label is seeded as a default-on `Related:` term** so the survivor's re-score embeds text spanning all sources' vocabulary — keeping the papers each independent axis surfaced discoverable. Only **manual** (confidence-NULL) assignments are hard-preserved (unioned); scored assignments are recomputed by the mandatory re-score, never carried over stale. `merge_axes` lives in new `app/backend/clustering/axis_operations.py` (composition only) to keep `axis_scoring.py` < 600; bulk delete is a client-side loop over the existing `DELETE /axes/{id}` (no new endpoint). |

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

---

*Last updated: 2026-06-26 — increment 144 (export / copy a paper's highlights + notes — Close reader dogfood): the
4th build in the slate. A dispatched **Close reader** persona agent drove the read→highlight→note→navigate→return
flow and found the reading experience is genuinely good (page comfort, select→note in one gesture, a Notes panel
that lists + jumps + flashes, marks that persist + re-find) — but **no way to get the marks *out***: they're trapped
in the panel (no copy-all, no per-paper digest, no markdown export). Fix (frontend-only, `30_viewer.jsx`): **Copy** +
**Export .md** buttons in the Notes panel head (shown when ≥1 highlight) assemble a Markdown **digest** from the
already-loaded annotations (`# title`, `**p.N** — <highlighted text>`, the note as a `> blockquote`, page-ordered) —
`copyDigest` via `navigator.clipboard` + `exportDigest` via a blob `*-notes.md` download (the inc-70 pattern). No
backend endpoint / new data (the annotation list already carries quote+note+page; a reusable export endpoint is a
deferred follow-up). pytest **524** unchanged (frontend-only; the pure `buildAnnotationDigest` is **node-verified**,
the flow **headed-verified**); `ruff` clean; build + assembly green; surface **106/106 API + 536/536 FE, 0 uncovered**.
**Verified headed, no egress** (`.local/visual/drive_inc144_marks.py` — seeds a real 2-page PDF + 2 marks, opens the
viewer → Notes panel → Copy → the exact digest is read back off the clipboard; 0 console/page/genai). Remaining
close-reader findings filed to the backlog (keyboard zoom + next/prev-mark hotkeys; noted-only filter + note-text
search; fit-page + remembered scroll position; free-form note colors; a minimap highlight marker). Notes:
`INCREMENT-144-NOTES.md`. **NEXT (the slate, last):** inc 145 **Skeptical synthesizer ↔ multi-paper focus query (#7)**
(needs egress to test live). **Then BYOK** (user-prioritized after the slate).

Earlier — increment 143 (deleting an imported keyword tag is durable — Librarian experience pass +
backlog #3): the 3rd build in the slate. A dispatched **Librarian** persona agent drove the tag-curation + 🔎 re-resolve
flow and found: tags don't *duplicate* and imported-vs-typed is clear (those work), but **deleting an imported keyword
tag isn't durable** — `apply_crossref_subject_tags` re-adds *every* `subject`, so re-resolve (the cleanup button)
silently **resurrects** a keyword the librarian deliberately removed. Fix (backend-only, the tag analogue of the inc-49
user-edit guard): a per-paper **`suppressed_paper_tags`** table (migration **0020**, additive/guarded) keyed by
`(paper_id, tag_name)`; `remove_tag_from_paper` reads the removed tag's source *before* the orphan-prune and, if it's
an imported `keyword:*` tag, records a suppression; `add_tag_to_paper` **clears** it (re-adding = the user wants it);
`apply_crossref_subject_tags` filters `subject` by the suppressed set, so 🔎 re-resolve **and** `backfill_keyword_tags.py`
honor the deletion. Gated to keyword sources (removing a **user** tag never suppresses). No new endpoint/response/egress/
surface (rides the existing `DELETE /papers/{id}/tags/{tag_id}` + re-resolve). pytest **524** (+2: delete-keyword-not-
re-added round-trip; user-removal-doesn't-suppress); `ruff` clean; migration head **0020** (derived by `alembic_head()`,
no test edit); apply-callers unchanged. **Backend-only → unit-verified the exact librarian scenario** (import → delete →
re-resolve → stays gone → re-add → cleared); the UI (TagsRow ×, 🔎) is unchanged. Remaining librarian findings filed to
backlog #3/#9 (a re-resolve-overwrites-metadata confirm; an always-on source label; a diff toast; a tag-lock). Notes:
`INCREMENT-143-NOTES.md`. **NEXT (the slate):** inc 144 **Close reader ↔ dogfood the reading flow**; inc 145
**Skeptical synthesizer ↔ multi-paper focus query**. **Then BYOK** (user-prioritized after the slate).

Earlier — increment 142 (determinate import/scan progress — Migrator experience pass + backlog #4):
the 2nd build in the "build + persona-test 4 features" exercise (after inc 141). A dispatched **Migrator** persona
agent drove the import/scan onboarding flow and found the bar was an **indeterminate pulse** ("looks identical at item
3 and item 380") — for a few-hundred-item import the migrator's #1 anxiety ("stuck? how far?") went unanswered (the
backlog's "add a progress bar" was already partly met by the indeterminate bar — the pass found the *real* gap). Built
**determinate "X / N" progress**: `JobStore` gained `JobProgress{current,total,label}` + `mark_progress`;
`embed_papers`/`embed_chunks` (the slow phase) + `scan_library_folder` (per file) take an opt-in `on_progress(current,
total)` callback the scan/import jobs wire through ("Reading PDFs" → "Fetching metadata" → "Embedding papers"); the
`Scan`/`ImportJobResponse` expose `progress`; the modals render a real fill + "Embedding papers — X / N" (the
`.progress-fill-det` modifier kills the sweep) instead of the pulse. Plus a **"Review unsorted →"** door in the scan
done-summary (`added>0`) → the inc-80 Unsorted view. **Opt-in + additive** (other jobs stay indeterminate → zero
blast radius). pytest **522** (+3: `test_job_store` ×2, `embed_papers` per-paper progress); `ruff` clean; build +
assembly green; surface **106/106 API + 532/532 FE, 0 uncovered**; no new endpoint/migration/egress. **Verified
headed, no egress** (`.local/visual/drive_inc142_progress.py` — a slowed-fake-model server imports an 8-record .bib →
the bar shows "Embedding papers — 4 / 8" mid-run + finishes "8 imported"; 0 console/page/genai). Remaining migrator
findings filed to backlog #4 (a skipped/failed-detail list; per-item filename + ETA; a cancel button). Notes:
`INCREMENT-142-NOTES.md`. **NEXT (the slate):** inc 143 **Librarian ↔ protect imported/system tags from clobber (#3)**;
then inc 144 **Close reader ↔ dogfood the reading flow**; inc 145 **Skeptical synthesizer ↔ multi-paper focus query**.
**Then BYOK** (Gemini API key in Settings) — **user-prioritized to the top of the pile after the slate.**

Earlier — increment 141 (statcheck flagged→detail path — the experience-pass fix): the first fix
**produced by** the inc-140 end-user experience pass. The dogfood (deadline-citer persona vs statcheck) found that
"this paper is flagged" and "here is the specific result that doesn't recompute" were two good halves that **didn't
link** — the METHODS pane defaults to **Details**, and the "⚠ N flagged" chip→filter left you on Details with the
already-selected paper. Fix (frontend-only, `40_app.jsx` + `06_methods_statcheck.jsx`): the flagged chip now (1) opens
the METHODS **Statistics check** section (`setMethodsOpen("statcheck")`; `methodsOpen` added to `paneCtx`), (2)
**re-targets the top *flagged* paper** via a **`pendingSelectTopRef`** resolved in the `/papers` fetch callback (so it
selects the *filtered* list's top, not the stale pre-filter one — the bug behind the first failed headed run), and (3)
the per-paper `StatcheckPaper` **auto-runs** its check when its section is the open one (`active = ctx.methodsOpen ===
"statcheck"`; gated so the mount-but-hidden section never runs) — so the inconsistent rows (reported vs recomputed *p*
+ page link) show with **no manual "Check statistics" click**. Net: the citer clicks "⚠ N flagged" → the flagged
paper's specific result is right there (backlog sub-findings (a)+(c) shipped; (b)/(d)/(e) remain). **No Principles
trigger** (UX wiring; counts/rows unchanged — still a list-to-review, region page-open); **no new surface** (106/106 API
+ 530/530 FE, 0 uncovered); pytest **519** unchanged; `ruff` clean; build + assembly green. **Verified headed, no
egress** (`.local/visual/drive_inc141_statcheck_path.py` — chip → Statistics check opens → flagged paper auto-selected →
inconsistent row auto-shows `computed p = 0.0449` vs reported `.001`; 0 console/page/genai). Notes: `INCREMENT-141-NOTES.md`.
**NEXT (queued):** remaining statcheck sub-findings (b on-paper entry [design], d deep-link to the test, e flagged-vs-to-review
duality [design]); gap-finder followed-authors / similarity ranking; a cadence auto-refresh. **Watch (rule #1):**
`clustering/my_publications.py` at **594/600**.

Earlier — increment 140 (the end-user experience pass — a 4th gate — + its first dogfood): codifies
the standing orientation the user asked for — **before any user-facing change is "done," make a pass inhabiting the
end user of the thing you touched** (does it actually *serve* them?). New **`.claude/EXPERIENCE-PASS.md`** + **CLAUDE.md
rule #11**: two questions — (1) **reception** (discoverable / legible / is the next step obvious) and (2) **intended
use** (what does the user reach for next; does the built thing support it or dead-end), the latter **bounded by our
commitments** (a desire conflicting with the ethics — accusation, paywall circumvention, an opaque score — is *declined*
per #9 + A-A, not served). The user's key upgrade = the **mechanism**: *persona-grounded experience agents* — dispatch
a subagent **in character** as a concrete persona with a **goal in the moment** (the **deadline citer** vetting a paper's
stats before citing; the corpus builder; the skeptical synthesizer) to drive the feature and report what's left to be
desired — grounding turns "is the UX good?" into "can *this* person, doing *this*, get where they're going?" The 4th
gate beside DESIGN (#8 looks) / PRINCIPLES (#9 honest) / QA (#10 works+covered) → **EXPERIENCE (#11 serves the user)**;
reflective pause → a finding (fix-cheap or backlog). **Dogfooded immediately:** a deadline-citer agent drove the live
statcheck flow and found the per-paper drill-down (METHODS → Statistics check → "This paper" → per-test rows) is
**hidden** — the METHODS pane defaults to Details and the "⚠ N flagged" chip→filter lands on Details, ignoring the
flagged state, so "flagged" and "the specific result that doesn't recompute" never link. Filed **▲ BUILD FIRST** to
`INCREMENT-BACKLOG.md` (5 sub-findings, simplest-first; (a) open Statistics check from the flagged view = the cheap fix).
**Docs-only** — no app code / build / migration / surface change; pytest **519** unchanged. Notes: `INCREMENT-140-NOTES.md`.
**NEXT (queued):** the statcheck flagged→per-test fix [build-first (a)]; gap-finder followed-authors / similarity ranking;
a cadence auto-refresh. **Watch (rule #1):** `clustering/my_publications.py` at **594/600**.

Earlier — increment 139 (accordion tabs-within-a-section — Tags becomes a tab of AXES; METHODS
reordered): codifies the IA rule that **accordion sections are broad tool categories and TABS present like-with-like
submenus** (DESIGN.md §5). **`05_panes.jsx`** registry now supports tabs: `registerPaneTab({id,label,paneId,order},
{id,label,order,render})` adds a tab to a find-or-created host section; `registerPaneSection` is sugar for a one-tab
section (no strip). A section with ≥2 tabs renders a **segmented tab strip** (reuses the `.tags-srcfilter` chip recipe
— the user-approved style) + **mount-but-hides** the inactive tabs (`.pane-tab:not(.active){display:none}`, so an open
axis / running action survives a switch); the active tab persists (`callosum.panetab.<sectionId>`). **THEORY:** **Tags**
moves from its own section to the **second tab of AXES** (`[Axes | Tags]`, `15_axes.jsx` + `10_pdf_layer.jsx` →
`registerPaneTab`) — like-with-like (your labels beside your conceptual lenses); discoverability is preserved (the Tags
tab is always visible when AXES is open, the default). **METHODS reordered by cognitive task:** **Data consistency
(GRIM)** (`order: 20`) now precedes **Statistics check** (`order: 30`) — raw-data check before analysis check; future
stat checks become **tabs** within Statistics check, not new sections. **Frontend-only** — no backend/API/migration/egress;
no Principles trigger (IA, not a new claim/signal). **Rule #10:** route_00 + route_20_tags repointed to the Tags tab;
surface **106/106 API + 530/530 FE, 0 uncovered** (the new tab strip). help corpus's left-pane + Tags lines updated
(`HELP-DOCS-SYNCED` → 139). pytest **519** unchanged; `ruff` clean; build + assembly green. **Verified headed, no egress**
(`.local/visual/drive_inc139_panetabs.py` — THEORY = [AXES, SYNTHESIS] with [Axes|Tags] tabs + mount-but-hide switching;
METHODS GRIM-before-statcheck; 0 console/page/genai). Notes: `INCREMENT-139-NOTES.md`. **NEXT (queued):** gap-finder
followed-authors / similarity ranking; a cadence auto-refresh; the broader backlog. **Watch (rule #1):**
`clustering/my_publications.py` at **594/600** — split before the next backend addition there.

Earlier — increment 138 (auto-select the top library paper on load — Details populated): on app
load the **top library paper is auto-selected**, so the METHODS → DETAILS section starts **populated** (its editable
Details) instead of the empty "Select a paper …" hint — the right pane is useful without a first click. **Frontend-only**
(`40_app.jsx`): an effect sets `selected` to `listState.papers[0].id` when **nothing is selected** and the **(non-trash)**
list is ready with papers; it fires on first load + when a selection clears to null (e.g. the selected paper was trashed),
and **never overrides** a paper the user already picked (guarded `selected == null` → idempotent, no loop). Auto-selects
**Details only** (does not open a PDF tab — `openPdf` is separate). **No Principles trigger** (auto-triggers an existing
view-state), **no new surface** (surface map unchanged 106/106 API + 528/528 FE, 0 uncovered) — `route_00` step 5 reworded
(DETAILS starts populated; the hint shows only for an empty library). pytest **519** unchanged; `ruff` clean; build +
assembly green. **Verified headed, no egress** (`.local/visual/drive_inc138_autoselect.py` — on load the top paper's
title fills Details, no hint, clicking another paper updates it; 0 console/page/genai). Notes: `INCREMENT-138-NOTES.md`.
**NEXT (queued):** the accordion-tabs design rule (tabs-within-a-section for like-with-like — Axes+Tags tabs; order
Data-consistency before Statistics-check; codify in `DESIGN.md`); gap-finder followed-authors / similarity ranking; a
cadence auto-refresh. **Watch (rule #1):** `clustering/my_publications.py` at **594/600** — split before the next backend
addition there.

Earlier — increment 137 (gap-finder v2 — forward gap + axis-scoped + persistent cache): rounds
out the inc-135 backward gap-finder with the user-chosen scope. **Forward gap** (`compute_gaps(direction="forward")`):
works that **cite** ≥ N of your papers ("cites N of your papers") — newer work building on your collection — via new
OpenAlex `fetch_work_id` + `fetch_citing_works` (`?filter=cites:<W…>`, validated `^W\d+$`, cached `citing:<id>`,
capped `MAX_CITING=200`, fail-closed); **backward** (works your papers cite) is the unchanged other branch. **Axis-scoped**
(`axis_id`): `_scoped_paper_rows` restricts the scan to an axis's members (inc-63 subquery). **Persistent cache**
(`gap_candidates`, **migration 0019**; `persistence/gap_repo.py` replace-all-per-scope + read): **`GET /gaps
{direction,axis_id}`** reads the cache and **filters dismissed / now-in-library at read time** (Add/Dismiss take
effect with no recompute), **`POST`/`GET /gaps/refresh`** recomputes + replaces a scope (the inc-135 `/gaps/find*`
removed). Frontend `36_gaps.jsx` gains a **direction toggle** + an **axis dropdown** + a **Refresh** button (opening /
toggling reads the cache instantly; a "Last refreshed …" line). **Honesty/Principles unchanged** — "cited by / cites N
of *your* papers" is a library count, never a global importance/quality rank; coverage stated; candidates-not-verdicts;
Add metadata-only (no PDF → no paywall circumvention); forward adds no new judgment (declined a must-read leaderboard).
**Gotcha:** OpenAlex ids are `W`+**digits** — the backward path drops non-digit ids (`^W\d+$`), so seed/test data must
use real `W<digits>` ids. **Rule-#1 prerequisite:** split `schema.py` (611→**558**, over since inc 130/132) — the
findings/signals/retraction/gap tables moved to `persistence/schema_findings.py` on a shared `persistence/schema_base.py`
`metadata`, re-exported from `schema.py` (no circular import; zero blast-radius; `metadata.create_all` still includes
every table). Audit: **addendum** to `2026-06-26_gapfinder.md` (same OA-metadata posture; additive/guarded migration;
bound-param SQL; no new dependency; no Gemini egress) **PASS**. Rule #10: `route_41_gaps.md` updated → surface
**106/106 API + 528/528 FE, 0 uncovered**. pytest **519** (+5: `fetch_work_id`, `fetch_citing_works`, forward,
axis-scoped, `gap_repo`, + 2 endpoint tests replacing the find-endpoint tests); `ruff` clean; build + assembly green;
migration head **0019**. **Verified headed, no egress** (`.local/visual/drive_inc137_gaps.py` — free port + own-process
check; pre-seeded `external_api_cache` so the real client runs offline: Refresh backward → "cited by 3 of your papers"
+ coverage; toggle forward → Refresh → "cites 3 of your papers"; Dismiss drops the row; 0 console/page/genai). Notes:
`INCREMENT-137-NOTES.md`. **NEXT (queued):** auto-select the top library paper on load (Details populated); the
accordion-tabs design rule (tabs-within-a-section for like-with-like — Axes+Tags tabs; order Data-consistency before
Statistics-check; codify in `DESIGN.md`); gap-finder followed-authors / similarity ranking; a cadence auto-refresh.
**Watch (rule #1):** `clustering/my_publications.py` at **594/600** — split before the next backend addition there.

Earlier — increment 136 (watched folders rescan on window focus — live-ish pickup): a user
dropped a PDF into their library folder expecting it to appear (and be retraction-tagged); nothing happened.
Root cause (no code bug): the watched-folder auto-rescan only ran **on app launch** (`40_app.jsx`'s effect had
`[]` deps → mount-only), so a **mid-session** drop wasn't picked up until a restart / manual "Re-scan all". Fix
(**frontend-only**): the rescan now also fires **on window `focus`** (throttled 20s + an in-flight guard, gated by
the existing `callosum.autoScanWatched` toggle) — drop a PDF, switch back to Callosum, it appears. The rest of the
chain already worked: scan → `pdf-scaffold` → enrich (**`find_doi_in_pdf` reads the DOI from the PDF text**,
`enrichment.py:160` → Crossref → metadata) → the inc-134 `auto_check_retractions` tags it. Two prerequisites the
user owns: the folder must be **registered as watched** (a one-time "Scan folder" via the UI — can't be done
remotely), and a retraction check must have run / runs on-import. pytest **514** unchanged (frontend-only; the
rescan endpoint + chain are already tested); build + assembly + the e2e suite green; help corpus watched-folders
line updated (`HELP-DOCS-SYNCED` → 136). Notes: `INCREMENT-136-NOTES.md`. **NEXT (queued):** gap-finder v2
(forward gap + axis-scoped ranking + a persistent `gap_candidates` cache — user-chosen scope); auto-select the top
library paper on load; the accordion-tabs design rule (tabs-within-a-section for like-with-like, Axes+Tags tabs,
order Data-consistency before Statistics-check, codify in `DESIGN.md`); a true live OS file-watcher later if
focus-rescan isn't enough.

Earlier — increment 135 (literature gap-finder — backward citation gap): a new **discovery**
capability (a long-wanted future-track). Aggregate each library paper's OpenAlex **`referenced_works`** → surface
external works cited by **≥ N (default 3) of your papers** that the library doesn't have ("**cited by N of your
papers**") as **Add / Dismiss candidates** — the inverse of the inc-119 "who cites my work" feature. New OpenAlex
adapter methods `fetch_referenced_works` (cached DOI→work, bare `W…` ids, capped, fail-closed) + `fetch_work_meta`
(a candidate by `W…` id — **validated `^W\d+$` before any fetch**, cached); `clustering/gapfinder.compute_gaps`
(aggregate `ref_id → set(paper_id)`; keep ≥ min; **exclude** no-DOI / already-in-library / dismissed; rank by
count + a coverage dict); an **ephemeral async job** `POST`/`GET /gaps/find` (`app.state.gap_jobs` over
`app.state.openalex_client`); `POST /gaps/add` (reuses the inc-119 `import_citing_work` with a new `imported_source`
param → `"gap-import"` — **metadata-only, deduped, into the general library**; the PDF stays the OA-acquire lane →
no paywall circumvention); `POST /gaps/dismiss` (persisted in `profile.dismissed_gap_works`, **migration 0018**
additive; `dismiss_gap` inserts a minimal profile row if none — the gap-finder needs no My-Pubs profile). A **"Gaps"**
library-header button → `36_gaps.jsx` modal (Find gaps → candidate list + Add/Dismiss + the coverage caveat).
**Honesty/Principles:** "cited by N of *your* papers" is a count over the user's own library, **never a global
importance/quality rank**; coverage is **stated** ("scanned M of N papers; partial"); candidates-not-verdicts; no
PDF on Add. **Principles gate run** (declined a "must-read importance leaderboard"); **audit
`.claude/security-audits/2026-06-26_gapfinder.md` PASS**; **rule #10** `route_41_gaps.md` → surface **105/105 API +
522/522 FE, 0 uncovered**; help corpus gained a "Finding gaps in your library" section (`HELP-DOCS-SYNCED` → 135).
Egress = public **OpenAlex/Crossref metadata** (bounded, cached, fail-closed), **not** the Gemini gate. pytest
**514** (+8 `test_gapfinder.py`); `ruff` clean; build + assembly + the **e2e suite** green; migration head **0018**.
**Verified headed, no egress** (pre-seeded `external_api_cache` so the **real** code path ran offline — a "cited by
3" candidate, Add → in-library; 0 console/page/genai). **Op gotcha:** stray uvicorns from repeated headed-driver
runs can hold a port + serve a *stale* app — use a free port + assert your own process is alive (folded into
`route_41`). **Watch:** `my_publications.py` at **594/600** (the `import_citing_work` signature growth) — split
before the next addition there. Notes: `INCREMENT-135-NOTES.md`. **NEXT:** axis-scoped gaps ("gaps for [axis]"); a
persistent `gap_candidates` cache (v1 recomputes — cached OpenAlex makes the 2nd run fast); external-search
discovery beyond the library.

Earlier — increment 134 (retraction lifecycle — on-import auto-check + RW staleness nudge):
completes the producer's world-state lifecycle. The retraction producer checked only on demand (the batch /
per-paper), so a freshly imported retracted paper wouldn't flag until a manual re-run. Now: (1) **on-import
auto-check** — new `methods/retraction.py::auto_check_retractions(conn, paper_ids, *, checkers)` runs a **guarded
best-effort** detect+apply over a set of papers (each wrapped in `try/except` on top of `detect_retraction`'s
per-source guard, so a source error / missing row **never aborts the import**), hooked into the **scan** job
(`_process_scan_result` gained a `retraction_checkers` param, passed by scan + watched-rescan) and the
**citation-import** job over the *new* paper ids via `app.state.retraction_checkers` — a freshly imported
retracted paper flags immediately (Crossref reads the cache the enrich just populated; the RW mirror is offline;
OpenAlex is one cached lookup → marginal); (2) an **RW staleness nudge** — the Retraction Watch panel computes its
snapshot age from `retrieved_at` and past **30 days** appends "· N days old — refresh recommended" (amber; the
data isn't wrong, just old). **No new endpoint, migration, external-fetch type/host, or dependency** → reuses the
inc-131 audit (an **addendum** was added to `2026-06-26_retraction.md`) + the established Principles posture (no
new claim type); **no new end-user surface** (an internal auto-check + a text nudge in the already-QA-covered RW
panel) → no new QA route, surface map unchanged (**0 uncovered**). help corpus's retraction section gained the
on-import + staleness lines (`HELP-DOCS-SYNCED` → 134). pytest **506** (+2 `test_retraction.py`:
`auto_check_retractions` best-effort [flagged / clean / missing-id swallowed]; the citation-import job auto-checks
→ the imported paper carries the FACT); `ruff` clean; build + assembly + the **e2e suite** green locally; the
staleness endpoint + render confirmed live. `library.py` 284/600. Notes: `INCREMENT-134-NOTES.md`. **This
completes the retraction arc end-to-end (131 SP1 → 132 SP2 → 133 candidate-review → 134 lifecycle).** **NEXT:**
on-import for the Zotero / single-PDF paths; an automatic *cadence* refresh of the RW DB; the broader backlog
(discovery/gapfinder, a live OS file-watcher, the Word/Docs adapters, auth).

Earlier — increment 133 (activate the candidate-review half — statcheck candidates + a unified
"N to review" facet): the inc-130 Confirmed/Accepted/Noted candidate-review machinery was built but **unexercised**
(the only producer, retraction, writes *facts*). Now the **statcheck batch also emits a CANDIDATE finding** per
flagged paper (`source="statcheck"`, `desc` + counts + the flagged result's page; clean re-check → supersede; a
reviewed candidate's state is **preserved** across re-runs via `upsert_findings`' `content_key` idempotency) —
**coexisting** with the inc-97 **signal** (the candidate = the user's reviewable *work-state*; the signal = the
persistent *fact* about the paper — reviewing the candidate drops it from the review queue but **not** from the
"⚠ N flagged" statcheck filter). A unified **"📋 N to review"** library chip (count of papers with an unreviewed
candidate, derived from the `/findings/overview` already fetched into `findingsByPaper`) + filter view
(`GET /papers?finding=needs-review` → `repository.FINDING_FILTERS` allowlist → a bound subquery on
`paper_findings.review_state`, mirroring the inc-97 `SIGNAL_FILTERS`) reuses `librarySignalFilter` with the
sentinel `"needs-review"` (**zero new view-state**); the `/papers` fetch gained `findingsRefresh` as a dep so
reviewing a paper **re-narrows the queue live**. The Review-pane `FindingCard` + per-card badge already render
candidates (inc 130). **Principles** (run inline): a statcheck candidate is *a prompt to look, reviewable* (the
inc-95/97 framing) — signal-not-verdict, no score, non-accusatory; the facet is a work-state queue, not a rank;
retraction **facts** are correctly excluded (`review_state=None`). **No new endpoint, no migration, no external
fetch, no egress** → no audit gate. **Rule #10:** `route_38_findings.md` extended; surface **101/101 API +
510/510 FE, 0 uncovered** (the `finding` param rides the existing `/papers`). help corpus "Reviewing findings"
gained the review-queue lines (`HELP-DOCS-SYNCED` → 133). pytest **504** (+3 `test_findings_review.py`); `ruff`
clean; build + assembly + the **e2e suite (incl. reading mode)** green locally. **Verified headed, no egress**
(`.local/visual/drive_inc133_review.py` — chip → filter → the statcheck candidate card → Confirm → drops from the
queue live; 0 console/page/genai). `methods.py` at **492/600** (split watch). Notes: `INCREMENT-133-NOTES.md`.
**NEXT:** p-curve/GRIM are collection-level / per-value (not per-paper auto-scans → don't naturally emit
candidates, deferred); the retraction **on-import auto-check + a TTL/staleness nudge** remains open; a later
consolidation could fold the statcheck signal chip into the unified facet (coexist is the deliberate v1).

Earlier — increment 132 (Retraction Watch DB, SP2 — the bulk third retraction source):
completes the user's "all three sources" ask. The **Retraction Watch Database** (Crossref-hosted, CC0) joins
Crossref + OpenAlex (SP1) as the **third checker** — downloaded once into a local **`retraction_records`** mirror
(migration **0017**, additive/guarded) and matched against every library DOI **offline**; it's the **richest**
source (nature, date, **reason**, notice), **prepended** to `DEFAULT_CHECKERS` so its detail wins the merge (an
empty mirror → None, the SP1 sources still work). New `persistence/retraction_repo.py` (`replace_retraction_records`
[DELETE-all + bulk INSERT — authoritative, withdrawn records vanish] / `lookup_retraction_record` [most-severe] /
`retraction_db_status`); `integrations/retraction_watch/` (`RetractionWatchClient` — an injectable **size-capped**
https fetcher mirroring `acquisition/fetch.py`, mailto from `CALLOSUM_CROSSREF_MAILTO`, **absent →
`RetractionWatchUnavailable`** fail-closed; `parse_retraction_csv` — **stdlib `csv`, no new dependency**, tolerant
headers, **skips no-DOI + Reinstatement + unknown natures**; `download_retraction_database`). `RETRACTION_WATCH_CHECKER`
in `methods/retraction.py`; endpoints `GET /methods/retraction/database` + async `POST`/`GET
/methods/retraction/database/refresh` (`app.state.retraction_db_jobs` + `retraction_watch_client`, overridable);
a "Refresh database" UI + as-of line + the RW **reason** in the FactMark tooltip. **No new dependency.** Public
**bulk CC0 metadata** (manual-triggered, snapshot date shown) — **not** the Gemini gate; **reinstatements never
flagged** (an un-retraction is the opposite of a finding); `notice_url` derived-only (no SSRF). **Audit
`.claude/security-audits/2026-06-26_retraction-watch.md` PASS**; **rule #10** `route_40_retraction_watch.md` →
surface **101/101 API + 506/506 FE, 0 uncovered**; help corpus gained an RW-database paragraph (`HELP-DOCS-SYNCED`
→ 132). pytest **501** (+8 `test_retraction_watch.py`); `ruff` clean; build + assembly green; migration head 0017.
**Verified headed, no egress** (`.local/visual/drive_inc132_retraction_watch.py` — as-of line, FactMark + notice +
RW-reason tooltip; 0 console/page/genai). **The real CSV download is the user's manual check** (needs their
`CALLOSUM_CROSSREF_MAILTO` + a ~tens-of-MB fetch; verifies the live URL + CSV schema the hermetic tests assume).
`methods.py` at **463/600** — a `routers/retraction.py` split when it next grows. Notes: `INCREMENT-132-NOTES.md`.
**This completes the retraction arc (SP1 inc 131 + SP2 inc 132) — all three sources.** **NEXT:** an on-import
auto-check + TTL/cadence refresh; then statcheck/p-curve/GRIM can emit *candidates* into the findings store + a
unified library-wide "needs review" facet.

Earlier — increment 131 (retraction producer, SP1: Crossref + OpenAlex — the first findings
producer): the first real producer feeding the inc-130 findings contract. For each library paper's DOI, query
**multiple sources** (Crossref + OpenAlex in SP1), **merge**, and persist a **FACT** in `paper_findings` (the
Review-pane FactMark + a notice link + the ◆-fact card mark) plus an honest per-paper **check status** in
`open_science_signals` (`none` when checked-clean, `unchecked` when no DOI — **silence ≠ clean**) that also powers
a library **"Retracted" chip + filter**. The user asked for *all three* sources ("critical to know before
citing") → SP1 = the per-DOI two-source core via the existing audited adapters; **SP2 (inc 132) adds the
Retraction Watch DB** as a third checker (the merge layer already accepts it → additive). New
`app/backend/methods/retraction.py` (pure `RetractionSignal`/`merge_signals`/`detect_retraction`/`apply_retraction`;
checkers are injected `RetractionChecker`s → **hermetic**; no-DOI → `unchecked`, a source raising is skipped never
aborts, a now-clean paper supersedes its stale FACT); `CrossrefClient.lookup_retraction` parses the raw
`message.update-to`, `OpenAlexClient.lookup_retraction` reads `is_retracted` (the type→status map is **local to
each adapter** — no `methods`→`integrations` cycle); `signals_repo` store/count/get retraction status; endpoints
(`routers/methods.py`) `GET /papers/{id}/retraction` (read-only) + async `POST`/`GET /methods/retraction/run` +
`GET /methods/retraction/summary`; `app.state.retraction_jobs` + `retraction_checkers` (overridable in tests);
`SIGNAL_FILTERS["retraction-retracted"]` for the filter; the frontend FactMark/status-line/chip/filter/batch. **No
migration** (reuses `paper_findings` + `open_science_signals`). **Honesty/Principles:** a registry FACT relayed
verbatim (no LLM), evidence-carried (sources + notice), **no accusation** (the chip is a *filter* count, never an
author/reputation signal — A-A veto), and `notice_url` is **derived-only** (`https://doi.org/<doi>` → no SSRF).
Public DOI metadata egress — **not** the Gemini gate. **Principles gate run** (declined the author-reputation +
unchecked-as-clean easy paths); **audit `.claude/security-audits/2026-06-26_retraction.md` PASS**; **rule #10**
`route_39_retraction.md` → surface **98/98 API + 504/504 FE, 0 uncovered**; help corpus gained a "Checking for
retractions" section (`HELP-DOCS-SYNCED` → 131). pytest **493** (+15 `test_retraction.py`); `ruff` clean; build +
assembly green. **Verified headed, no egress** (`.local/visual/drive_inc131_retraction.py` — chip + filter,
FactMark + notice link, checked-none / unchecked status lines; 0 console/page errors, 0 genai hits). Notes:
`INCREMENT-131-NOTES.md`. **NEXT (queued):** SP2 (inc 132) — the **Retraction Watch DB** bulk source (a
`retraction_records` table + a download/index job + the third checker); then an on-import auto-check + TTL expiry;
then statcheck/p-curve/GRIM can optionally emit *candidates* into the same findings store + a unified
"needs review" facet.

Earlier — increment 130 (findings subsystem — the FACT-vs-CANDIDATE backbone, foundation only):
the architectural spine the METHODS "data-detective" features (statcheck, p-curve, GRIM, and the coming retraction
producer) plug into — a persistent, typed, per-paper **findings** store + a review surface. **v1 ships the contract +
UI only — no producer is wired yet** (retraction is the explicit next increment; user-chosen scope "foundation only").
New **`paper_findings`** table (migration **0016**, additive/guarded): `kind` (**fact** | **candidate**), nullable
`tier`, JSON `payload`, deterministic `content_key`, nullable `review_state`. New `persistence/findings_repo.py` — the
**producer contract** `upsert_findings(conn, paper_id, source, findings)` diffs by `content_key` (**supersede stale +
preserve the review_state of unchanged candidates** → idempotent re-runs), plus `get_paper_findings` /
`findings_overview` / `set_review_state` (allowlisted `confirmed`/`accepted`[needs reason]/`noted`; candidates only).
Endpoints (`routers/findings.py`): `GET /papers/{id}/findings`, `GET /findings/overview`, `POST /findings/{id}/review`
(404/422 on bad input). Frontend `08_methods_findings.jsx` self-registers the METHODS **"Review"** section (order 40):
**FACTs render as neutral marks**, **CANDIDATEs as reviewable cards** (region-precision page anchors — coordinate
honesty intact, no fabricated exact rect); the library card gets a `◆ fact` mark + an **"N to review"** work-state
badge from `/findings/overview` (refetched after a review). **Honesty encoded structurally** — `kind` IS the
FACT/CANDIDATE distinction; the badge counts the user's review work, never paper quality, and vanishes at zero;
nothing auto-acts or labels a paper/author (A-A no-accusation veto). **Principles gate run** (aligned with #2/#3/#5/#7/#8
+ the veto); **audit `.claude/security-audits/2026-06-26_findings.md` PASS** (local, bound-param SQL, validated/escaped,
no egress, no new dependency); **rule #10** new `route_38_findings.md` (+ `04_layout.jsx` folded into `route_00`, a
pre-existing inc-128 gap) → surface **94/94 API + 496/496 FE, 0 uncovered**; help corpus gained a "Reviewing findings"
section (`HELP-DOCS-SYNCED` → 130). pytest **478** (+6 `test_findings.py`; route-surface extended); `ruff` clean; build
+ assembly green. **Verified headed, no egress** (`.local/visual/drive_inc130_findings.py` — badge + FactMark render,
Confirmed reviews + drops the badge, persists across reload; 0 console/page errors, 0 genai hits). Notes:
`INCREMENT-130-NOTES.md`. **NEXT (queued):** the first real **producer** = **retraction** (Crossref / Retraction Watch
→ a **FACT** with a TTL) — its own increment, trips the audit gate (new external fetch) + the Principles gate; then
statcheck/p-curve/GRIM can optionally emit candidates into this store + a library-wide "needs review" facet.

Earlier — increment 129 (multi-item GRIMMER): completes the inc-127 GRIMMER — `grimmer_test`
now supports **multi-item scales** (`items > 1`), not just single-item. The multi-item math is the same analytic
check with an **`items²` factor** on the variance term and the total taken over all `N*items` item responses,
**with the same parity refinement** (`Σc_i² ≡ Σc_i = T (mod 2)`); `items=1` is the special case (the single-item
behavior is unchanged). **Derived from first principles + validated against the scrutiny reference** (mean 2.74,
SD 0.96, N 63, items 2 → consistent). The `items != 1 → supported=False` guard is gone (`supported` is now always
true); the dead frontend "unsupported" branch was removed (rule #5) and the help line updated. The simplified
analytic **errs toward leniency** (no per-item-range min-SS bound), so any miss is a *missed* inconsistency, never
a false "impossible" — the safe, non-accusatory direction. Backend math + tests + a 1-line frontend/help tidy;
**no API/surface change** (the GRIMMER verdict render path was headed-verified in inc 127 and is unchanged).
pytest **472** (+1 net: the "unsupported" test became two multi-item tests); `ruff` clean; build + assembly green.
Notes: `INCREMENT-129-NOTES.md`. **NEXT (user's pick):** the **findings subsystem** (the FACT-vs-CANDIDATE
backbone — the big architectural arc these METHODS features plug into); or other backlog.

Earlier — increment 128 (split 40_app.jsx — relieve the 600-line cap): a behavior-preserving
refactor clearing the rule-#1 risk flagged since inc 126/127 (`40_app.jsx` had crept to **590/600**). New early
chunk **`app/frontend/js/04_layout.jsx`** (107) holds, extracted verbatim: the module-scope layout helpers
(`_loadLayout`/`_saveLayout`/`_clampW`/`_beginDrag`, the `LEFT_*`/`RIGHT_*` width consts, the `Divider` component)
+ a new **`useUiPrefs()`** hook = the app's persisted UI state (theme; axis hide-uncertain + cutoff defaults;
auto-scan-watched; side-panel widths/open + their localStorage effects; THEORY/METHODS accordion-open; transient
Reading mode), lifted out of `App` unchanged. **`40_app.jsx` 590 → 514**: `App` now replaces ~50 lines of
pref/layout state with one `const { … } = useUiPrefs();` (only `settingsOpen`/`helpOpen` stay — modal toggles).
**Chunk-order-safe** (04 loads before its consumers; `30_viewer.jsx` already used `_loadLayout`/`_saveLayout` via
the IIFE function-hoist — now they're defined-before-use). No user-facing / API / surface change. pytest **471**
(unchanged); `ruff` clean; QA surface 91/484 0-uncovered. **Verified behavior-preserving headed**
(`.local/visual/drive_inc128_layout.py` — renders all 6 accordion sections; dark-mode toggles; left-panel collapse
works **and persists across reload**; Reading mode + Esc; 0 console/page errors). Notes: `INCREMENT-128-NOTES.md`.
**NEXT (user's pick):** multi-item GRIMMER; or the **findings subsystem** (the FACT-vs-CANDIDATE backbone — the big
architectural arc the methods plug into).

Earlier — increment 127 (GRIM + GRIMMER data-consistency calculator — the second GRIM/p-curve
"data-detective" METHODS feature): **GRIM** (Brown & Heathers, 2017) checks whether a reported **mean** of
integer-scale data is mathematically possible for the sample size; **GRIMMER** (Anaya 2016 / Allard 2018) extends
the check to the **SD**. Brainstorming chose an **assisted per-value calculator** (NOT an auto-scanner — pulling
mean+N+granularity from PDF prose is unreliable and would risk false, accusation-flavored flags): the user enters
a specific reported value to check, exactly how researchers use GRIM. **New `app/backend/methods/grim.py`** (pure
stdlib, no scipy/LLM/egress): `grim_test(mean, n, items=1)` (achievable means `K/(N*items)`; **nearest-possible**
values; a `no_power` flag when `N*items >= 10**decimals`) + `grimmer_test(mean, sd, n, items=1)` — **items=1**:
GRIM-check the mean, then test for an **integer sum-of-squares in the SD interval with the parity refinement
`SS ≡ T (mod 2)`** (the Allard correction over Anaya; **validated against the `scrutiny` reference** —
5.23/2.55/31→consistent, /35→inconsistent: for N=35 the only integer SS is even while the total is odd, so parity
correctly flips it). Rounding is **round-half-up via `Decimal`** (not banker's / float `==`). **`POST /methods/grim`**
(`routers/methods.py`) — sync, stateless, no DB/egress; `{mean, sd?, n, items}` → `{grim, grimmer?}`; bad inputs →
**422**. **Frontend `07_methods_grim.jsx`** — a **self-registering** METHODS section "Data consistency (GRIM)"
(order 30): a mean/SD/N/items form → GRIM (✓/✗ + nearest) + GRIMMER (✓/✗) + the no-power + integer-scale caveats +
a credit block with one-click **add to library**; tokens-only CSS; **no `40_app.jsx` change** (self-registered →
sidesteps the 590/600 cap there). **Assisted/per-value → inherently non-accusatory** (the user picks the value; it
never scans/ranks/labels a paper or author): **Principles gate #9 aligned** (declined an auto-scanner of
guessed-N flags; the A-A no-accusation veto held); **audit `.claude/security-audits/2026-06-25_grim.md` PASS**;
**rule #10** `route_37_methods_grim.md` + surface **91 API / 484 FE, 0 uncovered**; **credit-the-lineage** —
`THIRD-PARTY-NOTICES.md` (GRIM + GRIMMER + the `scrutiny` reference [Lukas Jung] + the Lakens catalog). **GRIMMER
is items=1 in v1** (multi-item deferred; GRIM supports items). pytest **471** (+12 `test_grim.py`: math + endpoint;
route-surface updated); `ruff` clean. **Verified headed, no egress** (`.local/visual/drive_inc127_grim.py` — 3.48/
N20 → impossible + nearest 3.45/3.50; 5.23/2.55/31 → GRIM+GRIMMER consistent; add-to-library; 0 console/page/genai).
Design/plan: `.claude/docs/specs/2026-06-25-grim-calculator-{design,plan}.md`; notes: `INCREMENT-127-NOTES.md`.
**NEXT (user's pick):** multi-item GRIMMER; the findings subsystem (FACT vs CANDIDATE); or the overdue
**`40_app.jsx` 590/600 split** (rule #1).

Earlier — increment 126 (p-curve — collection-level evidential-value check; the first GRIM/p-curve
"data-detective" METHODS feature): the user asked for GRIM/p-curve (surfaced via Daniël Lakens'
[automated-review catalog](https://lakens.github.io/automated_review_daily_build/)); we built **p-curve first**
(lower risk — it **reuses the proven statcheck p-value extractor**; GRIM's hard, low-coverage mean+N+granularity
extraction is the deliberate follow-up). Given a SET of significant focal NHST results across **user-selected**
papers, p-curve (Simonsohn, Nelson & Simmons, 2014) tests whether the p-value distribution is **right-skewed**
(→ evidential value) vs flat. **Collection-level only, never per-paper, never "p-hacked"** (the A-A no-accusation
veto); the interpretation is the user's. **New `app/backend/methods/pcurve.py`** (pure, no-DB/LLM/egress):
`compute_pcurve` (right-skew **Stouffer** `Z=ΣΦ⁻¹(p/.05)/√k` + a **binomial** check on share-of-p<.025 + the 5
observed bins) + `run_pcurve` (over per-paper `StatResult`s). **Async `POST/GET /methods/pcurve/run`**
(`routers/methods.py`, new `api.state.pcurve_jobs`) reuses `run_statcheck`+`get_chunks_for_paper` per **live**
selected paper; **ephemeral — no persistence, no migration**; selection de-duped+capped, empty→422. **Frontend:**
a **p-curve** library bulk-bar action (`10_pdf_layer.jsx`) + minimal `40_app.jsx` wiring → a new
**`29_pcurve.jsx`** modal: the collection-level/not-a-verdict framing, the coverage note, a hand-rolled **SVG
curve** (bars .01–.05 + a dashed 20% null), the right-skew + binomial statistics (descriptive), the
**included-tests** list (each opens its page at region precision), the coverage caveat, and a **credit** block
(Simonsohn et al. 2014 + a one-click **add to library** via the inc-93 `/library/import` with bundled CSL-JSON);
tokens-only CSS (rule #8). **Reuses statcheck's exact p-values** (`StatResult.computed_p`); since those are
rounded 4dp, results so significant p rounds to ≈0 are **conservatively dropped** (biases *against* over-claiming
— the safe direction; stated in the coverage note). **Principles gate #9 aligned** (declined a per-paper
"evidential value / p-hacking" badge/rank); **audit `.claude/security-audits/2026-06-25_pcurve.md` PASS**;
**rule #10** `route_36_methods_pcurve.md` + surface **90 API / 472 FE, 0 uncovered**; **credit-the-lineage** —
`THIRD-PARTY-NOTICES.md` gained a methods-lineage section (p-curve + `scrutiny` [Lukas Jung] + the Lakens catalog;
statcheck's credit backfilled). pytest **459** (+10 `test_pcurve.py`: math + endpoint; route-surface updated);
`ruff` clean. **Verified headed, no egress** (`.local/visual/drive_inc126_pcurve.py` — 12 papers → 76 significant
tests, **Z=−10.98, p<.0001** right-skewed; SVG curve + stats + included-tests + add-to-library; 0 console/page/genai).
**WATCH (rule #1): `40_app.jsx` is now 590/600 — a split is overdue; keep further wiring out of it.** Swept stray
`tests/*.tmp.*` + `app/frontend/js/*.tmp.*` atomic-write orphans (rule #5). Design/plan:
`.claude/plans/would-you-mind-reading-wise-peacock.md`; notes: `INCREMENT-126-NOTES.md`. **NEXT (user-queued):**
**GRIM** — the per-paper data-detective analogue (its own increment; harder extraction of mean+N+response
granularity → conservative v1 with heavy coverage caveats).

Earlier — increment 125 (strengthen the front-matter classifier — **live-validated** with real
Gemini): the user authorized spending tokens to eyeball the real synthesis output, and a **live** no-query
papers-scope run (`.local/visual/drive_inc124_live.py`, egress on) over the same papers that produced the broken
summary #7 showed inc-123's `is_front_matter_chunk` was **still too conservative** — paper **titles**, **author/
affiliation lines**, **journal running-headers**, and **funding lines** were leaking into the verified claims.
Strengthened `is_front_matter_chunk` (`app/backend/summarization/chunk_filtering.py`) to catch: name-attached
author superscripts (`Alves1`/`Uğurlar2`, `[A-Za-z][1-9](?![0-9])`, ≥2) + digit-prefix affiliations
(`1Department`, `(?:^|\s)\d[A-Z][a-z]`, ≥2); funding/acknowledgment lines (`grant`/`funding` + a grant-id
`[A-Z]{1,3}\s?\d{4,}`); and the **strong prose-safe title/header signal** — *no terminal sentence punctuation AND
≥60% of words capitalized* (body prose is mostly lowercase function words, so its caps-fraction is low even when
truncated → safe for content; titles/journal-headers are caught). The real leaked strings are now regression
tests (`tests/test_chunk_filtering.py`); the real body text that correctly stayed is asserted as CONTENT (guards
over-flagging). **Still fallback-only** (the inc-123 two-phase `_select_no_query` is unchanged — front matter is
deprioritized, never dropped), so a more-aggressive classifier is safe. **Re-ran live** → the verified claims are
now **all body text** (no front matter) and the **inc-124 Overview populated** with 3 real synthesis sentences,
each tracing to the verified claims it restates (e.g. *"For survival, continuously evaluating environmental risks
is crucial…"* → claims [2, 6]). The earlier **empty Overview** was confirmed **transient** — the 2nd (overview)
Gemini call hit repeated **503**s (model overloaded); the **fail-closed** path correctly omitted it and it
populated on retry over the cached summary. **Op note:** Gemini **key 1's prepay credits are depleted (429)** —
the live run fell back to `GOOGLE_API_KEY_2` (keys 1-4 live in `.env`). Backend-only — no `/summarize` contract
change, no migration, no egress, no new dependency; **Principles gate non-triggering** (retrieval quality, like
inc-66/123). pytest **449** (the FRONT_MATTER/CONTENT regression lists were extended; no new test functions);
`ruff` clean. Notes: `INCREMENT-125-NOTES.md`. **This live-validates the full synthesis-overview fix (inc 123 +
124 + 125): the original "synthesis gives no real summary, just sections" report is resolved end-to-end.**
**NEXT (user's pick):** the findings subsystem (FACT vs CANDIDATE) + adopting the THEORY/METHODS vocabulary; or
open backlog (discovery/gapfinder, GRIM/p-curve, file-watcher, emoji→SVG buttons, toasts, auth).

Earlier — increment 124 (synthesis evidence-traceable Overview — Part B of the synthesis-overview
fix; **completes** the "synthesis should provide a summary, too" request): after a synthesis is generated +
verified, a **second LLM pass narrativizes ONLY the verified claims** into a short **Overview** shown **above**
them, where **each Overview sentence links back to the verified claim(s) it restates** (per-sentence trace — click
a line → the claim(s) scroll into view + flash). Framed *"Overview — synthesized from the verified claims below"*
(traceable, NOT a free-floating "unverified" blob — the user's refinement): it restates only verified claims, its
trace refs are **inherited from verified claims, never LLM-invented** (`claim_indices` validated ⊆ the verified set
→ mapped to the verified sentences' **ordinals**; out-of-range dropped), and a line left with no valid refs is
dropped. New `app/backend/summarization/overview.py` (`OverviewGenerator` Protocol + `FakeOverviewGenerator` +
`OverviewSentence{text,claim_indices}`) + `integrations/gemini/overview.py` (`GeminiOverviewGenerator`, mirrors
`research_summary.py`; defensive `_parse_overview_response`; `OVERVIEW_PROMPT_VERSION`) + `EgressGatedOverviewGenerator`
(the inc-58 seam — library-derived text → **library egress gate**; egress-off → summary gen already raised, so the
pass is never reached → **no overview**, verified claims stand alone; any generator error caught → no overview,
never fails the synthesis). `summarize_scope(..., overview_generator=None)` + `_maybe_store_overview`; new
`summaries.overview_json` column (**migration 0015**, guarded/additive; head derived by tests, inc 99); `overview`
on the summary response (`OverviewItemResponse{text, claim_ordinals}`); `_overview_generator(api)` factory +
`create_app(overview_generator=…)` + `_summarization_app(..., overview_generator=…)` seams. Frontend
`20_synthesis.jsx`: `OverviewBlock` above the claims + `flashClaims` scrolling/flashing `#summary-claim-<ordinal>`;
tokens-only CSS (rule #8). **Principles gate #9 aligned** (traceable-to-evidence, restates only verified, secondary/
above the evidence, egress-gated, omitted when 0 verified — declined the authoritative-prose-eclipsing-evidence
path); **audit `.claude/security-audits/2026-06-25_synthesis-overview.md` PASS**; **rule #10** `route_55` extended;
**surface check 88 API / 462 FE, 0 uncovered**. pytest **449** (+9 `test_summary_overview.py`: column, Fake/egress/
parse, pipeline storage+map+out-of-range-drop+0-verified→none, e2e response); `ruff` clean; help corpus synthesis
section gained an Overview paragraph (`HELP-DOCS-SYNCED` → 124). Verified **headed, no egress**
(`.local/visual/drive_inc124_overview.py` — Overview above claims, label, trace-flash, 0 console/page/genai). The
**real Gemini prose-quality eyeball is deferred to the user** (needs egress + a key). Design (both parts):
`.claude/docs/specs/2026-06-25-synthesis-overview-design.md`; plan: `…-synthesis-overview-partB-plan.md`; notes:
`INCREMENT-124-NOTES.md`. **This completes the synthesis-overview fix (Part A inc 123 + Part B inc 124).**
**NEXT (user's pick):** the real-Gemini Overview eyeball (egress on); then the findings subsystem (FACT vs
CANDIDATE) + adopting the THEORY/METHODS vocabulary, or open backlog (discovery/gapfinder, GRIM/p-curve,
file-watcher, SVG buttons, toasts, auth).

Earlier — increment 123 (synthesis no-query scope prefers content over front matter — Part A of
the synthesis-overview fix): fixes **root cause #1** of the user's report that "synthesis doesn't provide a real
summary, just relevant sections." The no-query **papers** scope (the inc-62 select-papers→summarize path) was
ordering chunks by `chunks.c.id` (= import order → the *first* chunk of each paper is its **title page /
masthead**) and `_round_robin_by_paper(rows)[:top_k]` took the first chunk of each paper — so the LLM was fed
front matter and the "verified claims" came back as mastheads ("Original Manuscript", "© The Author(s) 2021 …
DOI:", journal volume lines, author lists — validation summary #7). Fix: a new conservative classifier
`app/backend/summarization/chunk_filtering.py::is_front_matter_chunk` (flags DOI/publisher/©-boilerplate; ≥2
author-affiliation superscripts; short + journal-volume run; short + no-terminal-punctuation + <10% function
words — **titles deliberately NOT caught**, errs toward "content") + a two-phase `_select_no_query` in
`pipeline.py` that round-robins **content** chunks across papers first, then front-matter chunks **as fallback**
(never dropped — a paper with only front matter still contributes), then slices `top_k`. **Query/cluster scopes
untouched** (query ranking already passes front matter). **Backend-only — no `/summarize` contract change, no new
endpoint, no migration, no egress, no new dependency** → no rule-#10 route change (surface check 0 uncovered, 88
API / 460 FE) and no audit-gate trigger; **Principles gate non-triggering** (a retrieval-quality change like
inc-66 trashed-paper exclusion; inspectability / provenance / egress posture all unchanged — every verified claim
still carries its quote/page/confidence). pytest **440** (+3: 2 classifier unit + the content-over-front-matter
selection assertion); `ruff` clean. Design (both parts): `.claude/docs/specs/2026-06-25-synthesis-overview-design.md`;
plan: `…-synthesis-frontmatter-fix-plan.md`; notes: `INCREMENT-123-NOTES.md`. **NEXT (user-queued):** **inc 124,
Part B — the evidence-traceable Overview**: a second LLM pass that narrativizes ONLY the verified claims into a
short prose Overview shown above them, where **each Overview sentence links back to the verified claim(s) it
restates** (per-sentence trace; citations inherited from verified claims, never LLM-invented; framed
"synthesized from the verified claims below", not "unverified"). Trips the audit + Principles gates; adds a
`summaries.overview_json` migration + the `EgressGatedOverviewGenerator` seam + `20_synthesis.jsx` rendering.

Earlier — increment 122 (statcheck relocated to a METHODS "Statistics check" section — the
first real METHODS module on the inc-121 pane registry): moved **both** statcheck surfaces — the **library-wide
batch** (was `StatcheckSettings` in ⚙ Settings) and the **per-paper check** (was `StatcheckRow` in the Details
pane) — into a new **METHODS accordion section** "Statistics check" (`app/frontend/js/06_methods_statcheck.jsx`,
self-registers `order: 20`, after DETAILS). The section has two parts under "Whole library" / "This paper"
eyebrows: `StatcheckLibrary` (the batch, verbatim) + `StatcheckPaper` (the per-paper check — since `paneCtx`
carries only `selectedPaper` (the id), it **self-fetches** `GET /papers/{id}` for title + chunk_count, then runs
`GET /papers/{id}/statcheck`). App wiring: `paneCtx` gains `onShowStatcheckFlagged` + `onStatcheckRan`, and the
inc-100 "⚠ N flagged" header-chip refresh moved from **settings-close-keyed** to **mount + `onStatcheckRan`**
(after a batch). statcheck was **removed from both Settings and Details**; the library chip + the
`?signal=statcheck-inconsistent` filter/banner are unchanged. This **relieves the pre-existing rule-#1 violation**
on `25_detail.jsx` (**625 → 579**). **Honesty posture preserved verbatim** → **Principles gate non-triggering**
(a relocation, not a new claim/signal): counts never a composite score (#7); "a prompt to look, not a verdict" +
non-accusatory (#2 + the A-A no-accusation boundary); inline-APA caveat (#6); per-test rows open the page at
`precision:"region"` (no fake exact rect). **Frontend-only — no backend/endpoint/migration/egress change**
(every statcheck endpoint already existed). **Rule #10:** `route_33` repointed `fe:` → `06_methods_statcheck.jsx`
+ steps via the METHODS accordion; `route_30` dropped the per-paper statcheck step + its coverage (now route_33's
alone); `route_32` clarified; **surface check 0 uncovered (88 API / 460 FE)**. Also swept stray
`app/frontend/js/*.jsx.tmp.*` atomic-write orphans (rule #5). pytest **437**; `ruff` clean; help corpus statcheck
section repointed (`HELP-DOCS-SYNCED` → 122). Spec/plan:
`.claude/docs/specs/2026-06-25-statcheck-methods-section-{design,plan}.md`; notes: `INCREMENT-122-NOTES.md`.
**NEXT (user-queued):** investigate **synthesis showing no text summary** (the papers-scope front-matter bug —
diagnosed + spec'd at `.claude/docs/specs/2026-06-25-synthesis-papers-scope-bug.md`); then the findings subsystem
(FACT vs CANDIDATE) + adopting the THEORY/METHODS vocabulary once more METHODS modules exist.

Earlier — increment 121 (THEORY/METHODS accordion side-panes on a module registry — the
"next major upgrade", UI-shell half): replaced the two fixed side-pane wrappers (left `Sidebar` = Axes+Tags;
right `RightPane` = the inc-57 Synthesis/Details drag-split) with **accordions** on an extensible **module
registry** — new chunk `05_panes.jsx` (`PANE_SECTIONS` + `registerPaneSection({id,label,paneId,order,render})` +
`<PaneAccordion paneId ctx openId onOpen/>`). **Left pane = THEORY accordion** (AXES · SYNTHESIS · TAGS, one open
at a time, AXES default); **right pane = METHODS accordion** (DETAILS, with a "select a paper" hint). Sections
**self-register from their own chunks** (15/20/10/—; load order 05<10<15<20<25 ⇒ the registry exists before the
register calls; `order` controls display position; adding a section is one call with **zero `PaneAccordion` edits**,
proven via a throwaway chunk). **Mount-but-hide** (inactive bodies `display:none`, never unmounted) keeps an
in-progress synthesis alive across a switch; the open section persists (`callosum.theoryOpen`/`methodsOpen`);
summarize-from-library opens the SYNTHESIS section. The inc-57 `RightPane`+`detailH`+`.divider-h` are **retired**;
the outer panel resize/collapse + reading mode + center tabs are untouched. **Soft labels** — section headers only,
no "THEORY"/"METHODS" umbrella text yet (the `paneId` is the internal architecture + the eventual rename, adopted
once the METHODS modules earn it). One intentional behavior change: **Tags always shows** (empty-state hint) instead
of vanishing when empty (the user reported never discovering Tags). **DESIGN.md §5** = the THEORY/METHODS placement
rubric (place by cognitive task) + the accordion/registry pattern + the AI-usage principle + a FACT-vs-CANDIDATE
forward-note. **esbuild DCE gotcha (documented):** the IIFE build dead-code-eliminates unreferenced top-level
functions, so a registered-but-unused component is stripped until used — the gate is raw-assembly inclusion +
a successful build (`test_frontend_assembly.py` checks the raw assembly), not a bundle grep; `node --check` doesn't
take `.html`. **Rule #1:** `25_detail.jsx` was already **625 (>600) pre-inc-121** → the DETAILS registration lives
in `05_panes.jsx` to avoid worsening it (back to exactly 625); a split is queued (the statcheck→METHODS move pulls
statcheck out of it). pytest **437** (frontend-only — unchanged); `ruff` clean; help corpus layout passages updated
(`HELP-DOCS-SYNCED` → 121); `route_00` recalibrated + surface map green (88/88). Frontend-only, no backend/migration;
Principles gate non-triggering. Verified headed on `:8097` (switch/persist/synthesis-survives/details-on-select,
0 console errors). Spec/plan: `.claude/docs/specs/2026-06-25-theory-methods-accordion-{design,plan}.md`; notes:
`INCREMENT-121-NOTES.md`. **NEXT (user-queued):** (1) **statcheck Settings → a METHODS accordion section** (the
first real METHODS module — relieves the 25_detail.jsx size debt); (2) **investigate synthesis showing no text
summary** (only retrieved sections — leading hypothesis: egress off → no generation; could be a render bug); then
the findings subsystem (FACT vs CANDIDATE) + adopting the THEORY/METHODS vocabulary once METHODS modules exist.

Earlier — increment 120 (QA mechanism — surface-coverage gate + Codex-exec supervisor +
watched inbox): installed the QA bundle delivered as `qa_routes.zip` (authored out-of-band) per its
`QA-BUILD-GUIDE.md`, and had **Codex author the full route suite** until the gate went green. New **rule #10**
(`.claude/QA-POLICY.md`) — read before changing any **end-user surface** — joins DESIGN.md (#8) + PRINCIPLES.md
(#9). Three parts: **`tools/qa/build_surface_map.py`** (pure-stdlib static extractor — AST of `@router.<m>("path")`
+ JSX element/handler scan — and a `check` that diffs the surfaces declared in `.claude/qa-routes/*.md` against the
real ones; **API hard-gate, FE checklist**), **`tools/qa/supervisor.py`** (dispatches each route to a headless
`codex exec`, waits for its deposit in `.claude/qa-inbox/<run-id>/`, writes a Critical/High-first `run-summary.md`;
Tier-0 gates the rest), and **`tools/qa/_qa_serve.py`** (the fixture contract — a freshly migrated + **seeded
throwaway** SQLite via `tests.api_helpers._seed_library` on a free port, **egress unset by default**, never the
real library). Routes assert the **honesty invariants** (egress gate, coordinate honesty, signal-not-verdict), not
just clicks. Coverage is a **computed property** (re-extracted each run): current tree **88 API / 460 FE**, and
after Codex authored the 13 missing routes (the 2 seeds + 13 = **15 routes**, tiered 00 / 15–40 T1 / 55–58 T2
hermetic) → **88/88 API + 460/460 FE → `check` exits 0**. CLAUDE.md gained rule #10 + kickoff step #10 (triage the
inbox); `.gitignore` covers `qa-inbox/` + `surface-map.json` + the zip; CI has a report-only `check` step. Repo-fit:
added `tools/qa/__init__.py`, ran `ruff --fix`/`format` on the bundle scripts. **Two Codex roles:** the *author*
(this increment — writes the spec files, never opens the app) vs. the *route-runner* the supervisor dispatches
(Phase 3 — an **adversarial end user** driving the seeded app in Playwright, instrumented to also verify the
invariants). pytest **436** (additive — no app/test code touched); ruff clean. **NOT run (the user's to trigger —
spends Codex credits):** **Phase 3**, `python tools/qa/supervisor.py --tier 0` (the real browser-driven QA pass),
then deeper tiers; the first deposit is triaged at the next kickoff. **NEXT:** kick off a Tier-0 QA run to validate
the pipeline end-to-end; otherwise the open backlog (discovery/gapfinder, GRIM/p-curve, file-watcher, SVG buttons,
toasts, auth) is the user's pick.

Earlier — increment 119 (My Publications overhaul, SP3 — citing articles & citation counts):
the **final** sub-project (TDL #14); **completes the overhaul = SP1 (inc 117) + SP2 (inc 118) + SP3 (inc 119) = TDL #1 +
#3–18**. Each own-pub card shows its **OpenAlex cited-by count** (shown verbatim + attributed, never a Callosum
composite or ranking verdict) + a **"Most cited"** sort; clicking the count opens a **citing-articles modal** — the
papers OpenAlex records as citing it (**discovery candidates**, coverage stated "not exhaustive") — with per-row
**Import** + a confirm-gated **Import all**, which add them **metadata-only + deduped** to the **general** library (NOT
My Pubs — they aren't your works; the PDF stays the separate OA-acquire lane → no paywall circumvention). **Backend
(additive, no migration):** `AuthorWork.openalex_work_id` (was fetched but discarded), `paper_citations` on the
dashboard, `OpenAlexAuthorClient.fetch_citing_works` (`filter=cites:<id>`, validated `^W\d+$`, **cached** under
`citing:<id>`, **capped 100**, fail-closed) + `GET /my-publications/citing/{work_id}` (in_library via dedup) +
`import_citing_work` + `POST /my-publications/citing/import`; **`resolve_my_publications` now `fetch_author_works(refresh=True)`**
so the "Refresh from OpenAlex" button repopulates fresh counts + the work ids the chips need (old caches lack them).
Egress = **public OpenAlex/Crossref metadata, bounded/cached/on-demand** — NOT the Gemini library-text gate.
**Principles gate run** (spec §2 — aligned: count=fact, citing=candidates, human-selected import, OA-only PDFs);
**audit `2026-06-24_mypubs-citing.md` PASS**. Frontend: an optional `PaperCard` cited-by chip (library omits it) +
`MyPubsPublications` Most-cited sort + new chunk `34_mypubs_citing.jsx` (the modal). pytest **436** (+5: work-id
capture, `paper_citations`, citing fetch/cache/endpoint/in_library, import-citing dedup/not-in-mypubs, route-surface);
`ruff format`/`check` clean; verified **headed** via Playwright on `:8097` (71 chips, Most-cited reorder, a real
`cites:` fetch → 9 candidates, import → in-library). **Watch:** `clustering/my_publications.py` is **587/600** — split
before the next backend addition lands there (extract the citing/import or dashboard-builder helpers). **NEXT:** the
My-Publications overhaul is done; open backlog — the discovery/gapfinder track, GRIM/p-curve, a live OS file-watcher,
emoji→SVG buttons, toasts, auth — is the user's pick.

Earlier — increment 118 (My Publications overhaul, SP2 — domain organization):
the second sub-project (TDL #9/#15/#16/#17/#18). Organizes the own-corpus by **research domain**. A **Group by domain**
toggle regroups the publications under per-domain headers (the dashboard list) and collapsible subheadings (the pinned
**sidebar** My-Pubs card), with an **"Other"** group for papers in no domain and **starred-first** ordering within each.
Domains can be **renamed** inline (the box pre-suggests the closest existing **axis** name by domain-term overlap), and
custom names **persist across Re-decompose** by best paper-overlap (Jaccard ≥ 0.5 — a `custom` flag in the existing
`research_domains` JSON + `_reapply_custom_labels`, so **no migration**). **#18:** selecting a domain locks the Overview
flip-chart to **Publications (domain-filtered)** and disables the **Citations** pill until cleared. **Backend additive
only:** `Domain.paper_ids` + `DashboardResponse.starred_ids` on the dashboard, a per-paper **`ClusterPaperResponse.domain`**
populated only for the my-pubs `/axes/{id}/clusters` (mirrors the inc-84 `starred` gating — so the sidebar groups with
**no new route and no second fetch**), and one new endpoint **`POST /my-publications/domains/rename`** (a local
profile-JSON write; audit `2026-06-24_mypubs-domain-rename.md` PASS). **No migration, no egress, no Principles trigger**
(organizational, not a new claim/signal). A shared `PaperCard` (from SP1) is reused; `MyPubsPublications`
(`33_mypubs_pubs.jsx`) does the dashboard grouping, `15_axes.jsx` the sidebar grouping. pytest **432** (+4:
`paper_ids`/`starred_ids`/`domain` shape, rename endpoint, `_reapply_custom_labels` overlap); `ruff format`/`check`
clean; verified **headed** via Playwright against the live `:8097` data. Spec/plan:
`.claude/docs/specs/2026-06-24-mypubs-sp2-{domains-design,plan}.md`; notes: `INCREMENT-118-NOTES.md`. **NEXT:** **SP3 —
citing articles & citation counts (#14)** — citation counts on the publication cards → click → a modal of the papers
that *cite* yours → import them; needs a **new OpenAlex "cited-by" fetch** → trips the security-audit gate AND the
Principles gate (a new discovery signal), so it's built last on its own. (The domains section sits below the
publications list transitionally; a later layout pass can move it if wanted.)

Earlier — increment 117 (My Publications overhaul, SP1 — dashboard restructure & publication cards):
the first sub-project of the My-Pubs overhaul (TDL line 1 + #1/#3–8/#10–13; decomposed into SP1/SP2/SP3). The dashboard
tab was restructured into author-priority order — **Overview** (collapsible: 2×2 metrics + one **Publications⇄Citations**
flip-chart, last 10 years `'NN`, replacing the two side-by-side charts) → **Research summary** (moved to r2; the
⭐-only toggle hides when no starred pubs, #8) → **Publications** (the user's in-library own-papers as library-style
cards via `GET /papers?axis_id=<my-pubs>` — search/sort + a checkbox bulk bar [summarize/export/bibliography/delete] +
copy + open; the **Decompose** button relocated into its controls row, #10) → Research domains → **OpenAlex footer card**
(provenance "as of …", the indexed/library/not-imported gap, 2-yr mean citedness + affiliation + an OpenAlex profile
link, a second **Refresh** [#11], and a **Review/Dismissed →** button opening the missing-works **modal**, #12). A shared
**`PaperCard`** was extracted from the 40-prop `PaperList` monolith (behavior-preserving for the library) so the list
reuses the library aesthetic + parity; new chunks `33_mypubs_pubs.jsx` (the list) + `32_mypubs_missing.jsx` (the modal).
**Backend additive only:** `ResolvedAuthor.two_year_mean_citedness` + `.affiliation` parsed from the already-cached
OpenAlex author object → an `openalex_extra` block + `starred_count` on the dashboard response — **no new endpoint,
migration, or egress** (OpenAlex figures stay verbatim + attributed, the inc-81 posture → no audit/Principles gate).
Two bugs caught + fixed: `/papers` 422 on `limit>200` (→ 200 + an honest truncation note); the "Review →" button was
unreachable when every missing work was dismissed (→ now "Dismissed (N) →"). pytest **428** (+`openalex_extra`/
`starred_count` assertions in `test_my_publications.py`); `ruff format`/`check` clean; verified **headed** via Playwright
against the live `:8099` data (`.local/visual/drive_mypubs.py` + `drive_t5{,b}.py`; the modal restore→re-dismiss
round-trip confirmed the `onChanged` refetch and left state clean). Spec/plan:
`.claude/docs/specs/2026-06-24-mypubs-sp1-{restructure-design,plan}.md`; notes: `INCREMENT-117-NOTES.md`.
**NEXT:** **SP2 — domain organization** (#9 group-by-domain toggle, #15 rename domains vs axes, #16 domains →
AXES-card subheadings, #17 starred-first sorting, #18 chart-filter-on-domain-select); then **SP3 — citing articles &
citation counts** (#14, a new OpenAlex cited-by fetch → trips the audit + Principles gates). The domains section sits
below the publications list transitionally; SP2 reworks it.

Increments 109–116 (frontend/UX TDL items: inc-109 brand-asset source move, inc-110 PDF page-view options, inc-111
editable Translators, inc-112 multi-paper focus query, inc-113/114/115 button canonicalization, inc-116 synthesis
✕-close + AXES ambient outlines) are journaled in `RECOVERY-LOG.md` rather than in this footer.

Earlier — increment 108 (LibreOffice (UNO) citation adapter — the first word-processor adapter):
the first piece that places citations **inside a word processor**, riding the inc-107 `POST /citations/render-document`
contract. A drop-in LibreOffice Writer **Python UNO macro** in a new top-level **`adapters/`** tree (client code
that ships into the user's LibreOffice — NOT the FastAPI app, NOT a server-side `integrations/` client). A **thin
field-placer**: place/track a live field, read the full ordered set, write back what the backend rendered — it
**never formats** (citeproc does). Live fields = **ReferenceMarks** whose name carries the cited work's CSL-JSON
(base64), the Zotero `CSL_CITATION` **pattern** (credited in `THIRD-PARTY-NOTICES.md`, not code). Four macros:
Insert (paper id → `/papers/export` csl-json → ReferenceMark), Refresh (full-document-order scan via
`XTextRangeCompare` → `render-document` → write back in-text + bibliography), SetStyle (validated vs
`/citations/styles`, persisted as doc user-properties), Flatten (live→static). **No server change** — no new
endpoint/migration/route/egress (127.0.0.1 only); stdlib `urllib` (LO's bundled Python has no pip). **Verified by a
headless UNO round-trip** (`.local/lo_roundtrip/run_roundtrip.py` drives a real LibreOffice → IEEE `[1]/[2]`, APA
`(Vaswani & Shazeer, 2017)` author-date, flatten preserves text — **SELFTEST OK**) + **5 pytest pure-logic tests**.
**Four UNO traps found+fixed** (carry forward to the next adapters): `loadComponentFromURL` needs `Hidden=True`;
clearing the bib invalidates its bookmark anchor (reuse the cursor); `setString` on a ReferenceMark anchor
**destroys the mark** (recreate around the new text); holding `ReferenceMarks` items across a mutation hangs on a
stale handle (capture names → re-fetch) + removing a mark deletes its text (flatten re-inserts it). pytest **424**
(+5 `test_libreoffice_adapter.py`); `ruff` clean; audit `.claude/security-audits/2026-06-21_libreoffice-adapter.md`
**PASS**; help corpus unchanged (no in-app surface). **NEXT (the track):** **Word (Office.js)** — one cross-platform
add-in over the same `render-document` engine (needs the CORS/origin change, content-controls/ADDIN fields, Win+Mac
parity); then **Google Docs** (named ranges, the fenced cloud opt-in, built last). Deferred for LibreOffice: `.oxt`
packaging + toolbar, a library-search picker, grouped cites/locators, note-style footnotes, Track-Changes handling.

Earlier — increment 107 (position-aware document-render layer — Phase 2 of word-processor
integration): the shared contract every word-processor adapter (LibreOffice → Word → Google Docs) will call.
The inc-106 engine renders each cite **in isolation** (`makeCitationCluster`) — right for a *selection*, **wrong
for a live document** (numeric must renumber `[1][2][3]` by order; author-date must disambiguate `2020a`/`2020b`
across the doc). Inc 107 adds the position-aware layer: the runner gains a **`mode:"document"`** branch using
citeproc's **`rebuildProcessorState`** (the inc-106 per-item path is the unchanged default); `render.py` refactors
the subprocess into **`_run(request)`** + adds **`render_document(citations,*,style,locale)`** (self-contained —
renders from the passed CSL-JSON, **no library lookup / no DB**; caps clusters/items/total; output `_safe_html`-
sanitized); **`POST /citations/render-document`** `{citations:[{citationID?,items:[CSL-JSON]}],style,locale}` is
*the adapter contract* (scan doc for citation fields → POST in document order → get back position-aware in-text per
field + the bibliography to write back; stateless per request; 503/422/502, never 500). **Backend-only — no
frontend change (no rebuild), no migration, no egress, no new dependency.** pytest **419** (+3 `test_citations.py`
document-render: IEEE `[1][2][3]`+renumber-on-reorder, APA `2020a`/`2020b` disambiguation, unknown-style 422;
route-surface +1); `ruff` clean; audit `.claude/security-audits/2026-06-21_citation-render-document.md` **PASS**;
help corpus unchanged (no user-facing surface). **NEXT (the track):** the **LibreOffice (UNO) adapter** — the
live-field loop (insert → render → update → flatten) riding this endpoint; then Word (Office.js, needs the
CORS/origin change); then Google Docs (opt-in). Deferred: note-style footnote management, locators/prefixes, a
shared subprocess timeout, Vancouver + more styles.

Earlier — increment 106 (citation & bibliography engine — Phase 1 of word-processor
integration): the foundation of the word-processor track + the close of the "no formatted citation styles" gap.
**citeproc-js** runs as a **Node sidecar** (invoked exactly like esbuild — `citations/render.py::_run_engine`
mirrors `frontend.py::_transpile_jsx`, request JSON on stdin / result on stdout, fail-closed → 503) over **bundled
CSL styles + locales** (`app/backend/citations/csl/`, committed verbatim, CC-BY-SA) to render `papers.csl_json`
into formatted in-text citations + bibliographies (APA/MLA/Chicago/IEEE/Nature/Harvard). One central render = the
**word-processor adapters will only place fields, never format** (LibreOffice → Word → Google Docs ride this
engine). citeproc HTML is **sanitized server-side** (`_safe_html`) before any in-app render. Endpoints
`GET /citations/styles` + `POST /citations/render`; in-app surface = Details **"Cite as …"** (style dropdown + live
preview + copy) + a bulk **"bibliography…"** `.html` download. `citeproc` pinned (`package.json`); **no egress**
(bundled styles). Credit in `THIRD-PARTY-NOTICES.md` (credit-the-lineage). pytest **416** (+5 `test_citations.py`;
route-surface +2); `ruff` clean; opt-in Playwright smoke (0 console errors); audit
`.claude/security-audits/2026-06-21_citation-engine.md` **PASS**; help corpus gained a formatted-citations note
(`HELP-DOCS-SYNCED` → 106). **NEXT (the track):** the **LibreOffice (UNO) adapter** — the live-field loop (insert →
render → update → flatten) on this engine; then Word (Office.js, needs the CORS/origin change); then Google Docs
(opt-in). Deferred: fetch-on-demand styles, Vancouver + more styles, rich-clipboard copy, CRediT builder,
highlight-to-suggest/evaluate.

Earlier — increment 105 (two chores: default axis cutoff in Settings + a tag source filter):
the "2 chores" half of a fresh patter (carrot = the **literature gap-finder** (backward gap), next, in its own
plan-mode increment). Both **frontend-only over existing data**. (1) A **`callosum.axisCutoffDefault`** localStorage
pref — a "Default axis cutoff" slider in **Settings → Axes** (clamped [0.2,0.6], default 0.35; mirrors the inc-77
hide-uncertain pattern) — threads App→Sidebar→AxesPanel→`AxisItem`, whose re-score cutoff flipper falls back to it
when `axis.scoring_gain == null` (a stored per-axis gain still wins; AxesPanel keys cards on the default so a change
re-inits unscored cards). Sets what the flipper *proposes*; no backend change. (2) The sidebar `TagsPanel` gained an
**All / Yours / Keywords** segmented control filtering by the inc-100 tag `source` (`tagIsImported`), shown only
when both kinds exist — purely client-side over the already-fetched `/tags`. `styles.css` `.settings-cutoff` +
`.tags-srcfilter` (tokens only, rule #8). pytest **411** unchanged; `ruff` clean; opt-in Playwright smoke (2 tests)
passed (0 console errors); `callosum-app.html` rebuilt; help corpus tags section noted the source filter
(`HELP-DOCS-SYNCED` → 105). **NEXT:** the carrot — **literature gap-finder (backward gap)**: surface papers cited
by ≥k of your library's papers but missing from it ("cited by N of your papers on [axis]"), axis-ranked,
add-or-dismiss; uses the OpenAlex adapter (`referenced_works`). Gets **plan-mode + the Principles gate + a security
audit** (new external fetch / discovery signal).

Earlier — increment 104 (panel min-widths + Spotify pull-to-collapse + sidebar-button
reposition): three small layout tweaks (frontend-only). The **left (AXES)** panel now has a **300px** min drag
width and the **right (Synthesis/Details)** panel **415px**; dragging a resizer ~80px past its min auto-collapses
that panel (no chevron needed) — `40_app.jsx` constants `LEFT_MIN/RIGHT_MIN` + `*_COLLAPSE_AT`, each divider's
drag collapses when the unclamped `proposed` width crosses the threshold (else clamps to `[MIN,MAX]`); the
persisted width init clamps up to the min. The panel sticks at its min then snaps shut (works via `_beginDrag`'s
document-level listeners); re-expand = the collapse chevron. The two sidebar-header buttons regrouped:
`.icon-help` → `top:19px;right:33px` (down 7 / left 4, then both nudged left 15px), `.icon-gear` →
`top:19px;right:60px` (same Y, 27px left of help — a right-aligned pair, top-left vacated), both with an always-on
`currentColor` outline (hover unchanged).
pytest **411** unchanged; `ruff` clean; opt-in Playwright smoke
(incl. the reading-mode panel test) passed (0 console errors); `callosum-app.html` rebuilt. Visual QA delegated.
**NEXT:** the user's call — more layout polish, another patter, or deferred backlog (a live OS file-watcher,
GRIM/p-curve, the discovery/gapfinder track, My Pubs Layer 3, tag-provenance grouping/protection).

Earlier — increment 103 (per-card "copy BibTeX" clipboard button): a small library-card
affordance the user requested. inc-98's `.paper { user-select:none }` (which fixed the double-click word-select)
removed card text-copy, so each card now carries a small **clipboard SVG button** just left of its checkbox that
copies the paper's **BibTeX** in one click (`PaperCopyButton` in `10_pdf_layer.jsx`, reusing the inc-70
`POST /papers/export {format:"bibtex"}` → `navigator.clipboard`; `stopPropagation` so it never selects/opens the
card; icon → green ✓ for ~1.5s). `.paper-copy` is absolutely positioned at `top:10px;right:36px` (the checkbox
stays at `right:14px`, untouched); `.paper-title` gained `padding-right:46px` to clear both controls; two inline
Feather SVGs. Shown only in `selecting` mode (the normal library view), matching "alongside the checkbox".
**Frontend-only — no backend/endpoint/migration/egress** (reuses a validated, tested local read-only endpoint).
pytest **411** unchanged; `ruff` clean; the opt-in Playwright smoke passed (0 console errors, confirming the SVG
JSX compiled under the inc-102 esbuild precompile); help corpus's "Exporting citations" section gained a line.
**NEXT:** the user's call — another patter, or deferred backlog (a live OS file-watcher, GRIM/p-curve, the
discovery/gapfinder track, My Pubs Layer 3, tag-provenance grouping/protection).

Earlier — increment 102 (precompile the JSX with esbuild; drop in-browser Babel): a console-
hygiene change the user requested. The served page transpiled `<script type="text/babel">` JSX **in the browser**
via `babel-standalone` (cdnjs) — emitting a "precompile for production" warning + a `babel.min.js.map` 404
source-map error, plus a ~500KB download. Now `frontend.py` **esbuild-precompiles** the concatenated chunks
(`assemble_jsx` → `_transpile_jsx`: `node node_modules/esbuild/bin/esbuild --loader=jsx --jsx=transform
--jsx-factory=React.createElement --jsx-fragment=React.Fragment --format=iife --target=esnext`, JSX via stdin, no
shell) into one plain `<script>`; the Babel CDN line is removed from `index.html`. esbuild is a **build-time** dep
(`package.json` pins 0.28.1; `npm install`; `node_modules/` gitignored); the **server stays Python-only** (serves
the prebuilt `callosum-app.html`; the live-assembly fallback degrades gracefully if esbuild is absent — `app.py`
try/except, no 500). The IIFE preserves the chunks' shared scope (identical runtime). `test_frontend_assembly.py`
updated (precompiled markers; `test_every_js_chunk_is_included` checks the raw `assemble_jsx()` so completeness
needs no toolchain); CI gained `setup-node` + `npm ci`. Verified: `node --check` on the output (153
`React.createElement`, 0 leftover JSX) **and the opt-in Playwright smoke passed with 0 console errors**. pytest
**411** unchanged; `ruff` clean; audit `.claude/security-audits/2026-06-21_precompile-esbuild.md` **PASS**. (The
third console line — `XrayWrapper … content-script.js` — is an external **browser extension**, not callosum;
nothing to fix in the repo.) **NEXT:** the user's call — another patter, or deferred backlog (a live OS
file-watcher, GRIM/p-curve, the discovery/gapfinder track, My Pubs Layer 3, the tag-provenance
grouping/protection).

Earlier — fix (post-inc-101): double-click on a library card no longer word-selects the title — `.paper` got
`user-select: none` (inc-98 `onDoubleClick` always opens; the browser's default word-select on double-click was
the residual highlight). Card text isn't drag-selectable now but stays copyable in the Details pane. Frontend-only;
pytest 411 unchanged.

Earlier — increment 101 (Reading mode — one-click distraction-free reader): the carrot of the
inc 100–101 patter. A **⛶ Read** toggle (right of the center tab bar) hides **both** side panels and their
dividers to maximize the open PDF; **⤢ Exit** or **Esc** returns. `readingMode` state in `40_app.jsx`
(`toggleReading` snapshots `leftOpen`/`rightOpen` → collapses both → restores the snapshot on exit, so an
asymmetric layout returns intact); `cols` zeroes the divider tracks + `.app.reading .divider{display:none}` so
only the center pane shows; Esc is guarded to defer to an open modal. **Transient** (a reload returns to normal —
never strands the user with hidden chrome). Frontend-only (`40_app.jsx`, `30_viewer.jsx` `LibraryFrame`,
`styles.css` `.frame-reading` — tokens only, rule #8); no backend/migration/egress. pytest **411** unchanged;
`ruff` clean; `callosum-app.html` rebuilt. Visual QA delegated (no Playwright MCP this session). **NEXT:** the
user's call — another patter, or deferred backlog (a live OS file-watcher, GRIM/p-curve, the discovery/gapfinder
track, My Pubs Layer 3, the remaining tag-provenance grouping/protection).

Earlier — increment 100 (statcheck "flagged" header chip + tag-source aesthetic
differentiation): a "2 chores" half-patter (carrot = Reading mode, inc 101). (1) A **⚠ N flagged**
chip in the Library header — when the inc-97 batch statcheck run flagged any papers — jumps to the flagged-papers
filter (a more prominent door to a Settings-only feature). `signals_repo.count_statcheck_flagged` + `GET
/methods/statcheck/summary` (cache-only count; the inc-97 batch stays the only persister) → a `statcheckFlagged`
state in `40_app.jsx` → the chip in `10_pdf_layer.jsx`. (2) Tags from different sources (imported
Crossref/OpenAlex/Zotero keywords vs the ones you typed) are differentiated **aesthetically** — a muted style +
a source tooltip, no on-screen label (user request, to declutter Details). The inc-73 `import_source` is exposed
on the tag responses (`PaperTagRef`/`TagRef`/`TagSummary.source`) and read by `tagIsImported`/`tagSourceLabel`
(`00_lib.jsx`) → `tag-chip-imported`/`tags-panel-item-imported` in `25_detail.jsx` + `10_pdf_layer.jsx`. Both are
read-only projections of persisted facts — **no migration, no egress, no LLM**; the `source` field is additive
(default null). Principles gate: chip = a path to a *filter* (no rank/verdict; no-accusation boundary holds); tag
styling = provenance made visible (inspectability). pytest **411** (+1 `test_tag_source_exposed_on_responses`;
statcheck-summary assertion folded into an existing test); `ruff` clean; help corpus tags + statcheck sections
updated (`HELP-DOCS-SYNCED` → 100). **NEXT:** the carrot — **Reading mode** (a one-click distraction-free reader:
collapse both side panels, maximize the open PDF, Esc to return; frontend-only, builds on the inc-42 collapsible
panels); or another patter / deferred backlog (a live OS file-watcher, GRIM/p-curve, the discovery/gapfinder
track, My Pubs Layer 3).

Earlier — increment 99 (tests derive the Alembic head, not a hardcoded revision): a small
dev-infra cleanup killing a recurring failure class — a migration bumps the head, but `test_health.py` +
`test_startup_migration.py` hardcoded the old revision string, so a missed edit only went red on the *full* suite
(it bit inc 91 + inc 98). New `tests/api_helpers.py::alembic_head()` (`ScriptDirectory…get_current_head()`); the
two files now use `HEAD = alembic_head()` instead of `"00NN_…"` literals — a new migration needs **zero** test
edits for the head, and `test_health`'s `db_revision == HEAD` (vs a migrated DB) is the wiring proof. Tests-only;
no app code/migration/behavior change. pytest **410** unchanged; `ruff` clean. **NEXT:** the user's call —
another patter, or deferred backlog (a live OS file-watcher, GRIM/p-curve, the discovery/gapfinder track, My Pubs
Layer 3, reading mode / page-view options).

Earlier — increment 98 (double-click-to-open fix + watched library folders): a user-reported
bug + a requested feature. **(A) Double-click bug:** the inc-82 `getSelection().isCollapsed` guard suppressed the
open when the **title** was double-clicked (browser auto-selects the word) — so `onDoubleClick` now **always
opens** (`10_pdf_layer.jsx`); titles stay copyable in Details. (Independent of the scan — the wiring was intact;
coincidental timing.) **(B) Watched folders (Zotero/Mendeley-style, minus a live OS watcher):** scanning a folder
now **registers** it (`watched_folders` table, migration **0014**, `persistence/watched_repo.py`), and watched
folders are **re-scanned automatically on launch** (default-on Settings toggle) + via "Re-scan all" — new PDFs
appear without re-adding. `GET/DELETE /library/watched` (un-watch keeps papers) + `POST/GET
/library/watched/rescan` (async, reuses the inc-87 scan body via a shared `_process_scan_result`); the "+ Add ▾"
menu item → **"Watched folders…"** with a managed list. Safe to re-scan the library folder (content-dedup by
`file_sha256` → no dupes), answering the user's "no need to re-add" concern. Server-side folder read is now
persisted + auto-read → the deployment-gate note extended. pytest **410** (+2 `test_watched_folders.py`;
migration head → 0014); `ruff` clean; audit `.claude/security-audits/2026-06-21_watched-folders.md` **PASS**; help
corpus's scanning section reworked → watched folders (`HELP-DOCS-SYNCED` → 98). **NEXT:** the user's call —
another patter, or deferred backlog (a live OS file-watcher, changed-file re-ingest, GRIM/p-curve, the
discovery/gapfinder track, My Pubs Layer 3, reading mode / page-view options).

Earlier — increment 97 (statcheck as a library-wide lens): the patter's **carrot** (chores =
inc 96). Turns the inc-95 per-paper statcheck into **library triage**: a batch "Check all papers" (⚙ Settings →
Statistics check) persists a per-paper summary into the pre-built `open_science_signals` table (new
`persistence/signals_repo.py`, OR-REPLACE upsert — no migration), and a library **filter**
(`GET /papers?signal=statcheck-inconsistent`, allowlisted → bound subquery) shows only papers with a reporting
inconsistency, reached via a **"Show flagged papers"** link + a non-accusatory banner. Async
`POST/GET /methods/statcheck/run` (`routers/methods.py`, `statcheck_jobs`); the batch is the **only** persister
(the inc-95 per-paper GET stays live/read-only). **Principles gate run:** the aggregate is a **FILTER, never a
rank/score (#7) or a "bad papers" verdict (#2 + the no-accusation veto)** — the declined easy path was a
reproducibility-score leaderboard. Reuses the inc-95 engine unchanged; **no migration, no egress, no LLM, no new
dependency.** pytest **408** (+3 `test_statcheck.py`); `ruff` clean; audit
`.claude/security-audits/2026-06-21_statcheck-library.md` **PASS**; help corpus's statcheck section gained the
library-wide check (`HELP-DOCS-SYNCED` → 97). **This completes the inc 96–97 patter.** **NEXT:** the user's call
— another patter, or deferred backlog (a permanent header entry for the filter, GRIM/p-curve, a unified findings
facet, the discovery/gapfinder track, My Pubs Layer 3, reading mode / page-view options).

Earlier — increment 96 (sidebar Tags browser + Details "More → + add field"): the two
**chores** of a fresh patter (carrot = statcheck-as-a-library-lens, next, in its own plan-mode increment). Both
**frontend-only**, reusing already-tested endpoints. (1) A **`TagsPanel`** in the left sidebar (below Axes,
`10_pdf_layer.jsx`) lists every tag + paper count → click to filter the library (reuses `GET /tags` + the inc-71
`filterToTag`); a `tagRefresh` nonce + an `onTagsChanged` callback (App→RightPane→DetailContent→TagsRow) keep it
live with per-paper tag edits. (2) The Details **"More"** section always renders now + has an **`AddFieldRow`** to
add an arbitrary CSL field by hand (reuses the inc-49 validated `csl` patch; letter-led `[A-Za-z0-9_-]` keys,
reserved/core 422). **No Python changed**; rebuilt `callosum-app.html`. pytest **405** unchanged; `ruff` clean;
help corpus updated (tags + Details sections; `HELP-DOCS-SYNCED` → 96). **NEXT:** the carrot — **statcheck as a
library-wide lens** (persist results to `open_science_signals` + a batch run + a "reporting inconsistencies"
library filter; plan-mode + Principles gate — keep it a *filter with counts*, never a rank/"bad papers" list).

Earlier — increment 95 (statcheck — an inspectable, deterministic statistics-reporting signal):
the patter's **carrot** (chores = inc 94) and Track A's v1. A **"Check statistics"** button in the Details
**Statistical reporting** section recomputes reported APA NHST p-values (t/F/r/χ²/z) from the paper's extracted
text and flags reported-vs-computed disagreements — **deterministic, local, no-LLM.** `methods/statcheck.py` (new
`methods/` package): anchored regexes → `recompute_p` via `scipy.stats` → classify **consistent / inconsistent /
decision-error** with **rounding + one-tailed tolerance** (so correct reporting isn't false-flagged); per-chunk so
each result carries its page. `GET /papers/{id}/statcheck` (`routers/methods.py`, sync read-only; no chunks →
`checked:0`). UI shows per-test rows (verbatim match + recomputed p + green/amber `.cite-status` pill) + **counts,
never a composite score** + a **non-accusatory** caveat (amber not red; inline-APA-only ⟹ absence ≠ clean), each
row routing to its page. **Principles gate (rule #9) run:** PRINCIPLES Example 3 / extends value A6; honors the
veto-level **no-accusation** boundary (#2/#7 — signal-not-verdict, no opaque score). `scipy` made explicit
(already transitive via scikit-learn; needed for the t/F/χ² CDFs). **No persistence v1** (the `open_science_signals`
table + a library-wide facet defer to the findings subsystem); **no migration, no egress.** pytest **405** (+10
`test_statcheck.py`); `ruff` clean; audit `.claude/security-audits/2026-06-21_statcheck.md` **PASS**; help corpus
gained a "Checking statistics (statcheck)" section (`HELP-DOCS-SYNCED` → 95). **This completes the inc 94–95
patter.** **NEXT:** the user's call — another patter, or deferred backlog (statcheck persistence + library-wide
facet, GRIM/p-curve, the discovery/gapfinder track, My Pubs Layer 3, reading mode / page-view options).

Earlier — increment 94 (library-header "+ Add ▾" menu + persistent/descending Sort): the two
**chores** of a fresh patter (carrot = statcheck, next, in its own plan-mode increment). (1) The library header's
two "bring papers in" actions (Scan folder + Import) folded into one **"+ Add ▾"** dropdown (`AddMenu` in
`10_pdf_layer.jsx`: a `.trash-toggle`-styled trigger + an outside-click-closing popup; token-based CSS) — 6
header actions → 5. (2) The **Sort** choice now **persists** (`localStorage["callosum.librarySort"]`, like the
theme/hide-uncertain prefs) and gained **Title (Z–A)** / **Author (Z–A)** (new `title_desc`/`author_desc` keys in
the `_paper_sort_order` allowlist; NULL author still last, `papers.id` tiebreak). Frontend-only bar the one
allowlist line; rebuilt `callosum-app.html`. pytest **395** unchanged (+2 assertions on the existing sort test);
`ruff` clean. **No migration, no egress.** **NEXT:** the carrot — **statcheck** (Track A: a local, inspectable
per-paper open-science signal that recomputes reported NHST p-values from the extracted text and flags
inconsistencies — never a verdict). Gets **plan-mode + the Principles gate** first (it produces a signal about
the literature).

Earlier — increment 93 (BibTeX / RIS / CSL-JSON import): the patter's **carrot** (chores were
inc 91 filter-by-type + inc 92 un-dismiss). The inverse of inc-70 export: **Import** a `.bib`/`.ris`/`.json`
(library header, next to Scan folder) → parse → dedup → create metadata-only papers → embed. New
`metadata/citation_import.py` **hand-rolls** all three parsers (**no new dependency** — project ethos, cf.
inc-75); each yields a CSL dict (inverting `citation_export`'s maps), `csl_record_to_paper_fields` → `create_paper`
kwargs (`csl_json` stored whole → lossless round-trip; `item_type` = CSL type → the inc-91 Type facet labels it);
`import_citations` dedups via `find_existing_paper_by_identity` in per-record savepoints (a bad entry is
skipped+counted, never fatal); caps bytes + record count. **Entirely local — NO egress** (the file is
authoritative; no Crossref/Gemini); the browser POSTs the file **text in the JSON body** (no multipart/upload
surface, no server-side path → no traversal surface). Async `POST/GET /library/import` (`routers/library.py`,
reusing the inc-87 scan scaffolding) + `28_import.jsx` (clones `ScanModal`, a file picker). `<fmt>-import` is
outside enrichment's update allowlist (won't clobber the imported metadata, like user-edits). pytest **395**
(+9 `test_citation_import.py`); `ruff` clean; audit `.claude/security-audits/2026-06-21_citation-import.md`
**PASS**; help corpus gained an "Importing a citation file" section (`HELP-DOCS-SYNCED` → 93). **No migration, no
egress, no new dependency.** **This completes the "2 chores + 1 carrot" patter (inc 91–93).** Deferred: PDF-attach
on import, optional enrich/My-Pubs hook, a hardened BibTeX parser. **NEXT:** the user's call — another patter, or
deferred backlog (statcheck, the discovery/gapfinder track, page-view options / reading mode, full `.btn-*`
normalization).

Earlier — increment 92 (un-dismiss for My-Publications missing works): chore 2 of the patter.
Completes inc-85's missing-works review queue with the **undo** inc-67 added for duplicate-dismissals — a
mistakenly-dismissed own-paper can be **Restored** to the queue. `profile_repo.undismiss_work` removes a
normalized DOI from `profile.dismissed_work_dois`; `build_dashboard` now also returns **`dismissed_works`**
(the author's cached works whose DOI is dismissed — titles from the cached OpenAlex works) beside `missing_works`,
sharing one dismissed-set computation; `DashboardResponse.dismissed_works` reuses `MissingWork`; new **`POST
/my-publications/works/undismiss`** (local, idempotent, 204) mirrors the dismiss endpoint; the dashboard
(`31_mypubs_dashboard.jsx`) gains a collapsible **"Previously dismissed (N)"** section with a **Restore** link.
Cache-only (no network call), **no migration, no egress** (pure profile-JSON edit). pytest **386** (+1:
`test_undismiss_returns_work_to_missing_queue`); `ruff` clean; backlog reconciled (the inc-85 deferred follow-on
marked done). **NEXT (this patter):** the carrot — **BibTeX/RIS/CSL-JSON import** (plan-mode + security-audit
first; new ingestion path, the complement to inc-70 export).

Earlier — increment 91 (filter the library by type + prerequisite module splits): chore 1
of a "2 chores + 1 carrot" patter. A **Type** dropdown in the library header filters to a single CSL item type
(article-journal / book / preprint / …): `list_papers(item_type=…)` adds a **bound** `WHERE item_type == :v`
(rule #3), and a new **`GET /papers/item-types`** facet endpoint (distinct **live** types + counts via
`list_item_types`, NULL excluded) drives the dropdown so it only offers types that exist — a `_typeLabel` map
prettifies them ("article-journal" → "Journal article (32)"). `.searchbar` gained `flex-wrap`. **Rule #1 forced
a split first:** adding this surfaced `repository.py` (625) + `routers/papers.py` (600) at/over the 600-line cap
(the CLAUDE "~577" note had silently drifted), so native-annotations data-access moved verbatim →
`persistence/annotations_repo.py` (repository.py→538) and PDF file-serving → `routers/paper_files.py`
(papers.py→539), both behavior-preserving (precedents: dedup_repo/tags_repo, duplicates.py). The PDF route kept
its path, so the only route-surface change is `/papers/item-types`. Frontend: `40_app.jsx` `libraryItemType` +
`itemTypes` state; `10_pdf_layer.jsx` Type `<select>`; rebuilt `callosum-app.html`. pytest **385** (+1:
`test_filter_by_item_type_and_item_types_endpoint`); `ruff` clean; backlog reconciled (Unsorted=inc 80,
re-score-wrap=inc 86, filter-by-type=inc 91 marked done; progress-indication partial). **No migration, no egress,
no audit gate.** **NEXT (this patter):** chore 2 — un-dismiss for My-Pubs missing works (mirror inc-67); then the
carrot — **BibTeX/RIS/CSL-JSON import** (plan-mode + security-audit; new ingestion path).

Earlier — increment 90 (sidebar header redesign: horizontal logo + larger wordmark):
a frontend-only brand-header reorg (user request, matched to a mockup + alignment guides). The sidebar brand
became a **horizontal lockup** — the brain logo on the left, a **36px** "Callosum" serif wordmark to its right
(was a 19px wordmark stacked *under* a centered logo) — with the `⚙` settings button in the **top-left** corner
and the `?` help button in the **top-right**. **CSS-only** (`app/frontend/styles.css`: `.brand` column→row +
center + `margin-top`; `.brand h1` 19→36px + nowrap; `.icon-gear` →top-left `left:14`; `.icon-help` →top-right
`right:14`): the JSX already supported it (the buttons are `position:absolute` so DOM order is irrelevant;
`.brand` is a flex container). The inc-47 connection-status logo (green-dot `.connected` swap, theme-matched) is
untouched; no new tokens/hexes (serif + `--ink`, existing `.icon-*` recipes). Rebuilt `callosum-app.html`. pytest
**384** unchanged (no Python touched); visual QA delegated to the user; **font-size 36px is the flagged tunable**.
_(Two same-day tweaks after first look: wordmark 40→36px; buttons split back into the two corners, settings left /
help right.)_
**NEXT:** the user has broader tweaks coming (likely My Pubs); or a fresh chore/carrot cluster (deferred:
BibTeX/RIS import, statcheck, the discovery/gapfinder track, scan watch/auto + changed-file re-ingest, full
button `.btn-*` normalization if the user wants it eyeballed).

Earlier — increment 89 (search across all fields + a search-scope dropdown): two related
search upgrades (user request). (1) **Fixed the all-authors bug** — search only looked at title +
`first_author_family_name`, so a co-author's surname found only first-authored papers (the user's name returned
6 of 40); it now searches the whole `csl_json` record (every author + journal + year + DOI + abstract + …). (2)
A **scope dropdown** beside the search box (All fields / Title / Author / Journal, default All) narrows it.
Backend: `repository._search_clause(field, pattern)` + a `search_field` query param on `GET /papers` (key from a
`SEARCH_FIELDS` allowlist — rule #3; pattern bound); composes with sort/deleted/axis/tag/pagination.
Frontend: a `librarySearchField` state + the scope `<select>` (`40_app.jsx`, `10_pdf_layer.jsx`). **No migration,
no new endpoint, no egress.** pytest **384** (+1: `test_search_covers_all_authors_and_scopes` — a 2nd author is
found under all/author, not title; journal matches venue); `ruff` clean; help corpus's "Browsing and searching"
search paragraph rewritten (`HELP-DOCS-SYNCED` → 89). Trade-off (v1): the `author` scope matches the whole
record + `all` includes the JATS abstract — a precise per-author `json_each` query is a deferred refinement.
**NEXT:** the user has broader tweaks coming (likely My Pubs); or a fresh chore/carrot cluster (deferred:
BibTeX/RIS import, statcheck, the discovery/gapfinder track, scan watch/auto + changed-file re-ingest, full
button `.btn-*` normalization if the user wants it eyeballed).

Earlier — increment 88 (search + sort on one row): a small library-pane tweak (user request) —
the **Sort** control moved inline to the right of the search box (into the `.searchbar` flex row; dropped the
`.lib-sort-row` wrapper), reclaiming a vertical row. Frontend-only (`10_pdf_layer.jsx` + `styles.css`); pytest
**383** unchanged.

Earlier — increment 87 (scan / refresh a library folder): the user's top-priority TDL item —
point Callosum at a folder of PDFs and reconcile **new / unchanged / removed** files into the library (the
Zotero-free way to keep it current). New `pdf_processing/library_scan.py::scan_library_folder` (reuses
`attach_pdf_to_paper` + `file_sha256` + the indexed `attachments.checksum`; **linked** in-place, nothing copied;
checksum-dedup; per-file savepoint isolates corrupt PDFs; removed → `availability="missing"`) + an async job
(`routers/library.py`, `POST/GET /library/scan`) that enriches new papers from Crossref (unresolved → the inc-80
Unsorted view) + embeds them. Frontend: a **Scan folder** button + `ScanModal` (`27_scan.jsx`). **No migration**
(reuses `attachments`); only egress is the Crossref DOI lookup (NOT the Gemini gate); the folder is read
server-side (fine on 127.0.0.1 — flagged in the deployment checklist to gate before any hosted deploy). pytest
**383** (+3); audit `.claude/security-audits/2026-06-21_library-scan.md` **PASS**; help corpus gained a "Scanning
a folder for PDFs" section (`HELP-DOCS-SYNCED` → 87). v1 = manual scan/refresh; **watch/auto** + a persisted
watched-folder + changed-file re-ingest are deferred. **NEXT:** the user has tweaks coming (likely My Pubs); or
a fresh chore/carrot cluster (deferred: BibTeX/RIS import, statcheck, the discovery/gapfinder track).

Earlier — increment 86 (axis re-score line-wrap fix + button-cleanup resolution): two
frontend-only UI-polish chores. (1) The axis **re-score row** no longer wraps badly — `flex-wrap: nowrap` + the
Cutoff slider made the shrinkable flex item (`.axis-cutoff-range flex:1; min-width:36px`), so label · slider ·
Re-score · 👁 stay on one line at any sidebar width. (2) **DESIGN §3 #5 resolved:** the remaining "divergent
buttons" (axis-sort, pdf-zoom, axis-new, source-jump, history-delete, hl-editor, axis-x, frame-tab-close) were
reviewed and found to be **intentional distinct compact/colored variants, not near-duplicates** — folding them
into the full `.btn-*` recipe would value-shift them (contra "no behavior change"), so they're **kept as
documented exceptions**; the only safe unification was tokenizing every `border-radius: 5px` → `var(--radius-sm)`
(zero visual change; advances §3 #6). pytest **380** unchanged (frontend-only); `ruff` clean; help corpus
unchanged. **NEXT (in progress):** the carrot — **scan/refresh a library folder** (plan-mode first; new
ingestion path → audit gate).

Earlier — increment 85 (My Publications — missing-works review + import): the dashboard's
indexed-vs-library gap ("79 indexed · 40 in library") becomes a **review queue** — the OpenAlex-attributed works
**not** in your library, each with **Import** (accept) or **Dismiss** (reject). `build_dashboard.missing_works`
= cached author works whose DOI ∉ live library ∉ `profile.dismissed_work_dois` (sorted by citations; cache-only).
**Import** (`import_missing_work`) is **guardrailed** (the DOI must be one of the author's cached works — no
arbitrary minting) + **metadata-only** (`create_paper` + Crossref enrich `force=True`; the OA-PDF path stays the
separate "Acquire OA copy") + adds a confirmed My-Pubs member directly; idempotent. **Dismiss** persists a
normalized DOI (migration **0013**). `POST /my-publications/works/{import,dismiss}`; only egress is the Crossref
DOI lookup (not the Gemini gate). pytest **380** (+3); audit
`.claude/security-audits/2026-06-21_my-pubs-missing-works.md` **PASS**; help corpus updated (`HELP-DOCS-SYNCED`
→ 85). **This completes the user's three My-Pubs follow-ups** (inc 84 starring + inc 85 missing-works review +
import). **NEXT:** Layer 3 (enriched per-paper cards) / Layer 4 (prospection) remain deferred; or a fresh
chore/carrot cluster.

Earlier — increment 84 (star key publications + scope the AI summary): a My-Publications
curation chore — ⭐ **star** key papers in the My Pubs sidebar card, and a **"⭐ only"** toggle on the dashboard
that scopes the inc-81 AI research-summary generation to the starred set. Storage is an isolated
`profile.starred_paper_ids` JSON list (migration **0012**; like `research_domains`); the star state surfaces on
the **my_publications axis clusters** response (`ClusterPaperResponse.starred`, gated to that axis); `POST
/my-publications/star`; the generate endpoint gained a `starred_only` body → `my_publication_documents(only_paper_ids=…)`
(empty starred + starred_only → 422). LLM-free plumbing (the summary path is the already-gated inc-81 egress
seam). pytest **377** (+2); help corpus updated (`HELP-DOCS-SYNCED` → 84); `ruff` clean. **NEXT:** inc 85 (the
carrot) — the missing-works review/import queue.

Earlier — increment 83 (My Publications Part 2 — domain decomposition, Layer 2): the
dashboard's **Research domains** section — cluster your CONFIRMED own-papers into research domains
(**impact-by-domain**: citation sums) and **click a domain to re-filter** the publications-by-year chart.
**LLM-free** local clustering (reuses the inc-52 axis-suggestion machinery); the only egress is the OpenAlex
works **refresh** that adds per-work `cited_by_count` (metadata, not the Gemini gate). Stored as an **isolated
`profile.research_domains` JSON** artifact (migration **0011**), NOT child `cluster_nodes` — because
`axis_score_state` counts members by `axis_id` across all nodes, so children would double-count the inc-78/79
card badge. New `decompose_domains` + `_dashboard_domains` (my_publications.py), `AuthorWork.cited_by_count` +
`fetch_author_works(refresh=…)`, `POST/GET /my-publications/domains`, `DashboardResponse.domains`; frontend
domains section (impact bars + select-to-refilter) in `31_mypubs_dashboard.jsx`. Impact = honest citation
**sums** (no composite score); domains show member papers + terms (inspectable); 0.25 candidates excluded.
pytest **375** (+5); audit `.claude/security-audits/2026-06-20_my-publications-domains.md` **PASS**; help corpus's
My Publications section extended (`HELP-DOCS-SYNCED` → inc 83). Layers 3–4 deferred. **Also captured to the
backlog (user, deferred):** star key pubs + scope the AI summary to starred; a review queue for OpenAlex works
**missing** from My Pubs (the 79-indexed vs 40-in-library gap → accept/reject); import the missing ones via the
acquisition lane. **NEXT:** those My-Pubs follow-ups, or Layer 3 (enriched per-paper cards), or another
chore/carrot cluster.

Earlier — increment 82 (library-card tidy + double-click/text-select fix): two small
library-card UX chores (frontend-only, `10_pdf_layer.jsx`). (1) Dropped the "N chunks" chip from cards —
chunk count is processing-internal, not bibliographic (cards keep title·authors·year·venue + tier/file/needs-DOI).
(2) A card's double-click now opens the PDF **only when it didn't select text** (`getSelection().isCollapsed`):
double-click a title word → it selects (copyable), no open; double-click empty card space → opens. pytest **370**
unchanged (frontend-only); no migration/endpoint/egress/CSS. **NEXT:** the chosen carrot — My Publications
**Part 2 Layer 2** (domain decomposition: cluster your own corpus into sub-axes + impact-by-domain, re-filter
the dashboard) — plan-mode first.

Earlier — increment 81 (My Publications Part 2 — the impact dashboard, Layer 1): an Overview
**dashboard tab** for the pinned My Publications axis (opened by a **📊** button on the card), turning the
user's own corpus into a first-class impact surface — headline OpenAlex metrics (citations / h-index / i10 /
indexed works), a hand-rolled **publications-by-year SVG chart** (+ citations-by-year), the **indexed-vs-library
gap** (an import nudge), and an **editable AI research summary**. The dashboard is a **cache-only, egress-free
read** (`build_dashboard` via `cached_author`, which never fetches; gated on `profile.openalex_author_id` ⟹ the
cache is warm) — the OpenAlex author object inc-78 already cached carries the stats, so headline metrics need
**no new API call**, are OpenAlex's authoritative figures shown **verbatim + attributed** (never a callosum
composite). The only egress is the research summary — LLM narration over the user's OWN titles/abstracts
(library text), **egress-gated at the inc-58 seam** (`EgressGatedResearchSummaryGenerator`; off → 503), a
non-load-bearing editable draft. New `integrations/gemini/research_summary.py`, `31_mypubs_dashboard.jsx`,
3 endpoints (`GET /my-publications/dashboard`, `POST /summary/generate`, `PUT /summary`), migration **0010**
(`profile.research_summary`). pytest **370** (+8); audit
`.claude/security-audits/2026-06-20_my-publications-dashboard.md` **PASS**; help corpus's My Publications
section extended (`HELP-DOCS-SYNCED` → inc 81). Layers 2–4 (domain decomposition / enriched cards / grounded
prospection) deferred. **NEXT:** open backlog — a separate **discovery** track the user floated (find papers
beyond the library / external search / a gapfinder) stays a parked future-track, plus the standing backlog
(library merge, etc.).

Earlier — increment 80 (the "Unsorted" library view — a needs-review filter): an **Unsorted**
toggle in the Library header (+ a clearable banner) that narrows the list to papers whose metadata still needs
review — raw PDF scaffolds, Crossref-unresolved imports, and papers with no recorded source — so they don't
silently disappear into the library. Backend: a `needs_review` query param on `GET /papers` →
`list_papers(needs_review=…)` filters `imported_source IN ("pdf-scaffold","crossref-unresolved") OR IS NULL`
(a local literal allowlist; bound-param). A **view** like Trash (clears axis/tag filters) but keeps
checkbox-select on, so you can select-all the unsorted papers and bulk re-resolve/export/delete. **No migration,
no new endpoint, no egress**; pytest **362** (+1: the three unsorted states returned, resolved/user-edited
excluded, trashed excluded); `ruff` clean; help corpus updated (the browsing section gained the Unsorted control;
`HELP-DOCS-SYNCED` → inc 80, also folding in the inc-77 hide-uncertain default + the inc-79 count-badge note).
**NEXT (task list):** My Publications Part 2 — the impact **dashboard tab** (the carrot; plan-mode first). A
separate **discovery** direction the user floated (find papers beyond the library / external search / a
gapfinder) stays a parked future-track, not part of My Pubs Part 2.

Earlier — increment 79 (count badge subtracts hidden uncertain papers): a follow-on to
inc-77's hide-uncertain-by-default — when an axis shows only assigned/manual papers (the inc-51 👁 toggle / the
inc-77 Settings default), its count badge now shows the **visible** count (total − uncertain) with a tooltip
noting how many are hidden, so the number matches the list. `axis_score_state(conn, id, *, cutoff=…)` returns a
new **`uncertain_count`** (scored `confidence < cutoff`, mirroring the read-time tiering); `AxisResponse.uncertain_count`
exposes it; `15_axes.jsx` subtracts it per the per-axis view-state (My Pubs card passes `hideUncertainDefault={false}`
→ full count). Additive read-only field on the existing `/axes` response — **no migration, no new endpoint, no
egress**; pytest **361** (assertions added to two existing axis tests, count unchanged); `ruff` clean; frontend
rebuilt. (Also this session, as small unnumbered chores: an indeterminate `ProgressBar` on the long async jobs;
the My Publications card moved below the filter/sort controls; inter-axis-card spacing 2→5px; CI actions bumped
to Node 24 — checkout@v5 / setup-python@v6.) **NEXT (task list):** the UNSORTED/needs-review library filter
(chore), then My Publications Part 2 — the impact **dashboard tab** (carrot, plan-mode first).

Earlier — increment 78 (My Publications — the auto-axis of your own papers, Part 1):
a pinned, **OpenAlex-resolved, LLM-free** axis of the researcher's own papers. Set a **profile** (name /
published-name variants / ORCID) in Settings → **Refresh** resolves the identity via OpenAlex (ORCID-first) →
ORCID/DOI matches are **confirmed members**, name-only matches are **candidates** you ✓ confirm / ✕ reject
(**persisted** in `my_publication_decisions` — a rejection never re-appears). Facts-vs-candidates +
confirm-and-learn; an **import hook** adds new matching papers incrementally (cache-based, zero extra egress);
the pinned 📄 card reuses `AxisItem` branched on the new `axes.kind`. New `integrations/openalex/author.py`,
`persistence/profile_repo.py`, `clustering/my_publications.py`, `routers/my_publications.py`, migration **0009**.
OpenAlex author lookup is **metadata egress, not the Gemini gate**; **no model tokens**; strictly additive (the
import hook is a guarded no-op when unused). pytest **361** (+14); audit
`.claude/security-audits/2026-06-20_my-publications.md` **PASS**; help corpus gained a "My Publications" section
(`HELP-DOCS-SYNCED` → inc 78). **NEXT:** Part 2 — the impact **dashboard tab** (charts / citation graph /
prospection), deferred. (Also this session: the backlog was split into open + `INCREMENT-BACKLOG-DONE.md`;
inc 77 hide-uncertain-by-default shipped.)

Earlier — increment 77 (hide uncertain axis papers by default): a backlog quick-win — the
inc-51 per-axis **👁 hide-uncertain** view can now be the **default** via a new **Settings → Axes** toggle
(persisted to `localStorage["callosum.hideUncertainDefault"]`, mirroring the theme pattern). Threaded App →
Sidebar → AxesPanel → AxisItem (initial `hideUncertain` reads the default; AxesPanel keys each card on it so a
toggle remounts them live). Frontend-only (`35_settings.jsx`, `40_app.jsx`, `10_pdf_layer.jsx`, `15_axes.jsx`,
`styles.css`; rebuilt `callosum-app.html`); pytest **347** unchanged; visual check delegated to the user. Also
this session: the **backlog was split** into `INCREMENT-BACKLOG.md` (open) + `INCREMENT-BACKLOG-DONE.md` (closed
archive). NEXT: the **My Publications** future-track (the chosen reward — plan-mode + Principles gate first), then
more backlog quick-wins / the deferred follow-ons.

Earlier — increment 76 (literature acquisition — the wanted list + OA re-check + coverage, C):
completes the acquisition arc's **track** loop. A persistent **wanted list** (`wanted_items`, migration **0008**)
that auto-includes PDF-less library papers (**Sync from library**) and accepts external adds (**Add by DOI**),
a manual async **Re-check OA** job that runs the same resolver cascade over the list and **auto-acquires** hits
(library wants fill the paper; external wants create a paper then import + enrich), and a **coverage readout**.
The OA-only bright line is **free + structural** — the re-check resolves only through the `ResolverRegistry` (so
no non-OA/arbitrary-URL path; test-pinned); external wants need a doi/pmid (title-only → skipped, never a fuzzy
mint); per-item errors never abort a run; a logged per-run cap bounds bulk fetching. New
`persistence/wanted_repo.py` + `acquisition/wanted.py` (the testable re-check service) + `routers/wanted.py`
(`/wanted` CRUD + sync-library + coverage + async recheck) + `26_wanted.jsx` (a **Wanted** modal in the lib-head).
**No new dependency, no new egress** (OA databases only, NOT the Gemini gate). pytest **347** (+13: repo +
run_recheck library/external/skip/miss/error-isolation/registry-only + endpoints); audit
`.claude/security-audits/2026-06-20_wanted-list.md` **PASS**; help corpus gained an acquisition/wanted section
(`HELP-DOCS-SYNCED` → inc 76). **This completes Acquisition A/B/C.** **Phase 8** (the future-tracks watched-inbox
session-kickoff rule — Session kickoff #9) is now done too, **closing the release-readiness arc, Phases 1–8.**
NEXT: deferred follow-ons in `INCREMENT-BACKLOG.md` (CI billing, collaborator/branch-protection, dev-infra
hardening, and the future tracks themselves); the legally-ambiguous lane stays counsel-gated (parked in the
gitignored inbox).

Earlier — increment 75 (literature acquisition — fan out the resolver cascade, B): the
inc-74 OA lane gains a **7-source cascade** (gold→green→preprint, first authorized copy wins) behind the
unchanged `OaLocation` seam — OpenAlex (primary) → **DOAJ** → **Europe PMC** → **Crossref-OA** → **CORE** →
**arXiv** → **bioRxiv/medRxiv** → **OSF/PsyArXiv**. Each is the OpenAlex-adapter shape (injectable fetcher,
`external_api_cache`, `lookup_oa → OaLocation|None`, fail-closed) + a thin resolver; the `resolve()` loop is
untouched (new sources only `register()` in `build_default_registry`). OA-ness stays each database's assertion
(no honest https PDF → None, never a guess); shared `integrations/api_cache.py`; **CORE** uses
`CALLOSUM_CORE_API_KEY` (Bearer; absent → silent no-op); **arXiv** parses the Atom id by regex not stdlib XML
(XXE surface, rule #4) → **no new dependency, no migration (head 0007), no new endpoint, no frontend change**.
pytest **334** (+31 hermetic per-source + cascade + structural); audit
`.claude/security-audits/2026-06-20_oa-acquisition-b.md` **PASS**; help corpus gained an "Acquiring an
open-access copy" section (`HELP-DOCS-SYNCED` → inc 75, clearing the inc-74 help debt). **NEXT:** Increment C
(wanted-list table + an OA-DB-only re-check job + a coverage readout). The legally-ambiguous lane stays
deferred/counsel-gated (its inbox spec is gitignored).

Earlier — increment 74 (literature acquisition — the legally-clear open-access lane, A):
resolve a PDF-less paper (DOI/PMID/title) → an OpenAlex-asserted **authorized open-access** PDF → download +
validate → import locally as a **`managed`** attachment named per the library convention
(`Authors - Year - Venue.pdf`) + labeled OA color/version/source (bronze flagged unstable). The bright lines
are enforced **structurally** by the `OaLocation` seam (required OA color, no "closed" member; the downloader
takes an `OaLocation`, never a bare URL → an arbitrary/non-OA fetch is inexpressible — same idea as the inc-58
egress gate). New `app/backend/acquisition/` (registry + fetch + resolvers), `integrations/openalex/`, migration
**0007** (OA-label columns on `attachments`), async `POST /papers/{id}/acquire-oa`, and a per-paper **"Acquire
OA copy"** button on PDF-less papers. pytest **303** (+24: structural OA-only, OpenAlex mapping/cache/fail-closed,
download validation, managed import+labeling, filename convention); audit
`.claude/security-audits/2026-06-20_oa-acquisition.md` **PASS**; e2e green; the spec is
`future-tracks/opus4.8_future-tracks_acquisitionclean.md`. **NEXT:** Increment B (resolver cascade —
DOAJ/CORE/arXiv·bioRxiv·PsyArXiv·PMC/Crossref) then C (wanted-list + OA-only re-check + coverage). The
legally-ambiguous lane stays deferred/counsel-gated. (The release-readiness arc Phases 1–7 shipped callosum to
**github.com/cliffworkman/callosum** — public, AGPL-3.0; follow-ons — CI billing, collaborator/branch-protection,
Phase 8 watched-inbox rule, dev-infra hardening roadmap — are tracked in `INCREMENT-BACKLOG.md`.)

Earlier — increment 73 (author/index keywords as first-order tags — Crossref `subject`):
a paper's **Crossref subject categories** import as first-order tags (`import_source="keyword:crossref"`) —
automatically on **🔎 re-resolve** / batch enrich, and across the existing library via
`python tools/backfill_keyword_tags.py` (full: cache-first, re-resolve the rest; **tag-only**, idempotent).
`adapter._crossref_message_to_csl` now keeps `subject` in `csl_json`; `enrichment.apply_crossref_subject_tags`
mirrors it to tags (additive, never clobbers metadata); `tags_repo.add_tag_to_paper(import_source=…)` sets
provenance on create only (a user tag is never relabeled) + `add_tags_to_paper`. DOI-only to public Crossref
(NOT the egress gate, per inc 49); **no migration, no new endpoint, no new dependency**. The inc-72 c-TF-IDF
suggester is the second-order gap-filler; Zotero tags already import (inc 71). Frontend bugfix: `TagsRow`
re-syncs on a detail refetch so 🔎-added chips appear without a paper switch (no other UI change — the inc-49
"More" section already hides the list-valued `subject` via `isScalarValue`). pytest **256** (+5: adapter
dedupe, re-resolve→tags + provenance preserved + filterable, backfill cache/fetch/idempotent/metadata-safe);
live E2E (`.local/keyword_tags_e2e/`, injected fake Crossref) — 🔎 → keyword chips → filter, 0 console errors;
audit `.claude/security-audits/2026-06-20_keyword-tags.md` PASS; help corpus tags section covers keyword tags
+ the backfill (`HELP-DOCS-SYNCED` → inc 73). NEXT (deferred): the **provenance UI** (surface tag `source`;
group "author keywords" vs "your tags" vs system facts; protect imported tags), **OpenAlex `concepts` /
PubMed MeSH** sources, and the **tags ↔ findings/system-facts** cross-cut (RETRACTED etc.) — all in
`INCREMENT-BACKLOG.md` "Tags & keywords"; plus sidebar Tags browser, formatted citation styles, library
**merge** (last).

Earlier — increment 72 (auto-suggest tags via local c-TF-IDF): a **✨ Suggest** button on
the Details Tags row proposes candidate tags mined from the paper's own text vs the library
(`clustering/tag_suggestion.py::suggest_tags_for_paper` — tf·idf, reuses `axis_suggestion._paper_tokens`,
excludes existing tags), which the user clicks to accept (added via the inc-71 path). The per-paper analogue
of inc-52's axis suggestion — **purely local: no embeddings, no clustering, no Gemini, no egress** (user's
explicit choice). `GET /papers/{id}/suggested-tags` (sync, read-only); no migration. pytest **251** (+3:
distinctive ranking, **idf demotes common terms**, exclude-existing, endpoint; route-surface +1); live E2E
(`.local/tag_suggest_e2e/`) — Suggest → accept a candidate, 0 console errors; audit
`.claude/security-audits/2026-06-20_tag-suggest.md` PASS; help corpus tags section now covers ✨ Suggest
(`HELP-DOCS-SYNCED` → inc 72). **FOLLOW-UP (user):** **author/expert keywords as first-order tags** (the
authors already did the concept work; c-TF-IDF is the second-order gap-filler) + a **tag-provenance** model
(user / imported-keyword / suggested / system-fact) + the **tags ↔ findings** cross-cut (a future RETRACTED
tag from the retraction producer) — recorded in `INCREMENT-BACKLOG.md` + "Tags hook" notes in the
future-tracks docs. NEXT: that author-keywords increment (Crossref `subject` / OpenAlex concepts / PubMed
MeSH; Zotero tags already imported), sidebar Tags browser, formatted citation styles, embedding-text JATS
cleanup, library **merge** (last).

Earlier — increment 71 (tags: per-paper labels + filter the library by tag): lightweight
free-form **tags** — view/add/remove on the Details pane, click a tag to **filter the library** to it. The
`tags`/`paper_tags` tables already existed (the Zotero importer populated them via `_upsert_tags`), so this
surfaces previously-**invisible** imported tags with **no migration**. New `persistence/tags_repo.py`
(get/list[+counts]/add[get-or-create + idempotent link]/remove[+orphan prune]) — split out because
`repository.py` was at 591 (mirrors inc-67's `dedup_repo.py`); new `routers/tags.py` (`GET /tags`,
`POST`/`DELETE /papers/{id}/tags*`); `PaperDetailResponse.tags` + a `tag_id` filter on `GET /papers` (IN
subquery, mirrors the inc-63 axis filter). Local, bound-param, non-destructive (manages links; prunes orphan
tags); names rendered as plain text. Frontend: Details `TagsRow` (chips name→filter / ×→remove + add-input
with a `/tags` datalist) + the axis-filter mirrored for tags (`libraryTagFilter`, mutually exclusive) + a
"Filtered to tag …" banner. pytest **248** (+4: dedupe/idempotent/orphan-prune/filter/endpoints; route-surface
+3); live E2E (`.local/tags_e2e/`) — add→filter→clear→remove, 0 console errors; audit
`.claude/security-audits/2026-06-20_tags.md` PASS; help corpus gained a "Tagging papers" section
(`HELP-DOCS-SYNCED` → inc 71). NEXT (chosen): **inc 72 — auto-suggest tags** per paper via **local c-TF-IDF
(no Gemini)**, reusing the inc-52 axis-suggestion machinery; candidate terms curated → added via this
increment's tag path. Other backlog: sidebar Tags browser, formatted citation styles (APA/MLA), embedding-text
JATS cleanup, purge-deletes-on-disk-PDF, library **merge** (last).

Earlier — increment 70 (citation export: BibTeX + RIS + CSL-JSON): the first way to get
citations **out** of the library — a **bulk file download** (select papers → `export…` picker → a
`.bib`/`.ris`/`.json`) and a **per-paper clipboard copy** (Details → **Cite** row). New
`app/backend/metadata/citation_export.py` (pure `to_bibtex`/`to_ris`/`to_csl_json` + `render_citations`
dispatch; reads `csl_json` with scalar fallback, abstract JATS-stripped via `abstract_plain_text`; **escapes
output**; BibTeX key = `citation_key` else deduped `{family}{year}`); `repository.get_papers_for_export`
(bound-param `IN`, **live papers only**); `POST /papers/export {paper_ids, format: Literal}` → `Response` with
the format media type + a **constant** download filename. **Read-only, local (no egress), no migration.**
Frontend: `apiPost` forces `.json()`, so a **raw fetch** does blob→`<a download>` (bulk) / text→clipboard
(per-paper; secure context on 127.0.0.1); the Cite links reuse the inc-68 `.btn-link`. pytest **244** (+8: 7
formatter unit + endpoint; route-surface +`/papers/export`); live E2E (`.local/citation_export_e2e/`) — bulk
`.bib` download + clipboard copy, 0 console errors; audit `.claude/security-audits/2026-06-20_citation-export.md`
PASS; help corpus gained an "Exporting citations" section (`HELP-DOCS-SYNCED` moved to inc 70). NEXT: see
`.claude/docs/INCREMENT-BACKLOG.md` — formatted human citation styles (APA/MLA via a CSL processor, Track-B);
persist library sort; migrate divergent ghost/icon buttons to `.btn-*`; embedding-text JATS cleanup;
purge-deletes-on-disk-PDF; library **merge** (last, destructive).

Earlier — increment 69 (sort the library): added a **Sort** dropdown to the library
pane-head — order by date added (oldest/recent), title (A–Z), publication year (newest/oldest), or first
author (A–Z). Backend: a `sort` query param on `GET /papers` → `repository._paper_sort_order(sort)` maps the
key via an **allowlist** to ORDER BY constant column expressions (rule #3 — never interpolated); unknown →
default `added` (= prior `id ASC`); NULL year/author sort **last**; `papers.id` is the stable tiebreak.
**No new route, no migration, no egress**; composes with q/deleted/axis_id/pagination. Frontend: `librarySort`
state (resets to page 1; omitted from the URL when `added` so the default is unchanged) + `.lib-sort` control.
pytest **236** (+1: every sort order + NULL-last + unknown→default); live E2E (`.local/library_sort_e2e/`) —
list re-orders by title/year/recency, 0 console errors; no audit gate (read-only param); help corpus library
section updated (`HELP-DOCS-SYNCED` moved to inc 69). NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — persist
the chosen sort + a direction toggle (deferred); migrate divergent ghost/icon buttons to `.btn-*` (+ §3 #6
radius scale); deferred token levers; embedding-text JATS cleanup; purge-deletes-on-disk-PDF; library
**merge** (last, destructive).

Earlier — increment 68 (canonical `.btn-*` button classes, DESIGN.md §3 #5): added
`.btn`/`.btn-primary`/`.btn-ghost`/`.btn-link`/`.btn-icon` + a `.danger` modifier as the single source of
truth for buttons, and folded the cleanly-identical ad-hoc button blocks into them by **grouping their
selectors** (primary: `.axis-btn`+`.synth-actions button`; ghost: `.pginate button`; link: `.axis-link`;
icon: `.axis-icon-btn`) — only where every grouped property is byte-identical, so it's **CSS-only with zero
visual change and no JSX touched**. Size-divergent ghost/icon buttons left as-is (value-shifting → deferred
to a per-button className migration). No Python changed → pytest unchanged at **235**; live E2E
(`.local/btn_dry_e2e/`) asserts each canonical class's **computed style** equals the intended recipe + the
real `.synth-actions button` keeps its sizing delta, 0 console errors; DESIGN.md §2 Buttons rewritten + §3 #5
→ PARTIAL. No audit gate (styling only); no help-corpus change. NEXT: see `.claude/docs/INCREMENT-BACKLOG.md`
— migrate the divergent ghost/icon buttons to `.btn-*` (+ reconcile `.axis-link.axis-danger` amber→red) +
the §3 #6 radius scale; deferred token levers; embedding-text JATS cleanup; purge-deletes-on-disk-PDF;
library **merge** (last, destructive).

Earlier — increment 67 (un-dismiss / manage dismissals): completes inc-64's persistent
"not a duplicate" dismiss with an **in-app undo** — the Duplicates modal now has a **Previously dismissed**
section listing the dismissed pairs (with titles) and an **un-dismiss** control that lets the scan flag them
again. `GET /papers/duplicates/dismissed` (registered before `/papers/duplicates/{job_id}` so "dismissed"
isn't captured as a job id) + `POST /papers/duplicates/undismiss {paper_ids}` (non-destructive, idempotent,
local, bound-param). No migration (reuses the inc-64 table). **Forced module split (rule #1):** the two new
data-access fns pushed `repository.py` to 604 (>600), so the dedup-dismiss concern (4 fns) was **moved
verbatim** to new `persistence/dedup_repo.py` (63; repository.py→555); two importers repointed. pytest **235**
(+1: list → undismiss → re-flag, idempotent, 422); route-surface +2; live E2E (`.local/undismiss_e2e/`) —
dismiss → previously-dismissed → un-dismiss → re-flagged, 0 console errors; audit
`.claude/security-audits/2026-06-20_undismiss-duplicates.md` PASS; help corpus duplicates section updated
(`HELP-DOCS-SYNCED` moved to inc 67). NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — deferred token levers
(cache extension + output caps); DESIGN.md `.btn-*` DRY; embedding-text JATS cleanup; purge-deletes-on-disk-PDF;
library **merge** (last, destructive).

Earlier — increment 66 (exclude trashed papers from synthesis retrieval): closes the last
soft-delete leak (the inc-65 deferred item) — a paper in **Trash** (soft-deleted, not yet purged) is no
longer a retrieval candidate, so it can't be cited in a **new** synthesis. The real leak wasn't where inc-65
guessed: the pipeline doesn't use `search_similar` — `summarization/pipeline.py::_source_chunks_for_scope`
builds its own candidate SQL, and the **query** scope was `select(chunks)` with no paper filter (every paper).
Fixed with a **live-paper filter** there (covers query + hardens papers/cluster scopes); also hardened the
general `retrieval._candidate_embedding_ids` primitive (excludes trashed paper/chunk embeddings; used by the
validation harness). Backend-only — no migration/endpoint/egress/frontend; behavior-preserving when nothing
is trashed (harness unaffected). pytest **234** (+2: query-scope `_source_chunks_for_scope` + `search_similar`
both drop a trashed paper, keep the live one); no audit gate; help corpus trash gotcha updated
(`HELP-DOCS-SYNCED` moved to inc 66). NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — deferred token levers
(cache extension + output caps); un-dismiss / "manage dismissals" UI; DESIGN.md `.btn-*` DRY; embedding-text
JATS cleanup; purge-deletes-on-disk-PDF; library **merge** (last, destructive).

Earlier — increment 65 (permanent delete: delete forever / empty Trash): completes
inc-54's soft-delete — a **trashed** paper can now be **permanently purged** (per-paper **Delete forever**
or **Empty Trash**), removing the paper, its dependent rows, AND its embeddings + sqlite-vec vectors. The
unsafe part inc-54 deferred was the orphan crash (`embeddings.target_id` has no FK + the store had no
delete → a leftover vector crashes `retrieval._resolve_hit`); fixed by a new `VectorStore.delete` +
`repository.purge_paper`/`purge_all_trashed` that delete the paper's embeddings + vectors **before** the
paper row (FK CASCADE handles the rest), in one transaction. **Trashed-only** (a live paper → 404, can't be
purged in one step); UI double-confirms; local-only; **no migration** (pure DML; head stays 0006).
`DELETE /papers/{id}/permanent` + `POST /papers/trash/empty`; frontend Delete-forever/Empty-Trash (danger,
`.danger` recipe). pytest **232** (+4: purge removes rows+vectors + no orphan-crash, live-paper refused,
trash-only endpoint, empty-trash-only-trashed); route-surface +2; live E2E
(`.local/permanent_delete_e2e/`) — delete-forever + empty-trash, live paper survives, 0 console errors;
audit `.claude/security-audits/2026-06-20_permanent-delete.md` PASS; help corpus trash section updated
(`HELP-DOCS-SYNCED` moved to inc 65). Deferred: doesn't delete the on-disk PDF; trashed-but-not-purged
papers still leak into new-synthesis retrieval (separate `deleted_at` filter). NEXT: see
`.claude/docs/INCREMENT-BACKLOG.md` — that retrieval `deleted_at` filter; deferred token levers (cache
extension + output caps); un-dismiss / "manage dismissals" UI; DESIGN.md `.btn-*` DRY; embedding-text JATS
cleanup; library **merge** (last, destructive).

Earlier — increment 64 (persistent "not a duplicate" dismiss): marking a duplicate group
**not a duplicate** now **sticks** — the scan persists the group's pairs and respects them on every future
scan (finishes inc-56's deferred "persistent dedup-dismiss"). New `dismissed_duplicate_pairs` table
(migration **0006**, head; canonical `low<high`, FK CASCADE, unique) + `repository`
`get_dismissed_duplicate_pairs`/`dismiss_duplicate_pairs`; `find_duplicate_groups` drops dismissed pairs
**before** the union-find (so the group never re-forms); `POST /papers/duplicates/dismiss {paper_ids}`
(≥2 existing live papers → else 422; bound-param `INSERT OR IGNORE`; local, non-destructive); the frontend
dismiss button keeps the session-hide AND persists. **Forced module split (rule #1):** extending dedup pushed
`routers/papers.py` to **636** (>600), so the duplicates concern (models + `_DedupJobStore` + the 3 endpoints
+ `_run_dedup_job`) was **moved verbatim** to new **`routers/duplicates.py`** (157; papers.py→**497**),
included **before** `papers.router` so `/papers/duplicates*` still wins over `/papers/{paper_id}` — behavior
preserved. pytest **228** (+1; migration-head + route-surface asserts → `0006`); live E2E
(`.local/dedup_dismiss_e2e/`) — dismiss → reopen → "No likely duplicates found.", 0 console errors; audit
`.claude/security-audits/2026-06-20_dedup-dismiss.md` PASS; help corpus duplicates section corrected
(`HELP-DOCS-SYNCED` moved to inc 64). NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — deferred token levers
(cache extension + output caps), un-dismiss / "manage dismissals" UI, DESIGN.md `.btn-*` DRY, embedding-text
JATS cleanup, permanent-delete/empty-trash; library **merge** (last, destructive).

Earlier — increment 63 (filter the library by axis): clicking an axis's **count badge**
(now a button, `15_axes.jsx`) narrows the main Library to that axis's papers, with a clearable "Filtered to
axis …" banner; pairs with inc-62 — **filter → select all → summarize** = a verified synthesis of a whole
topic cluster. Server-side: a new `axis_id` query param on `GET /papers` → `repository.py::list_papers` adds
a **bound-param `IN` subquery** over `cluster_node_papers`→`cluster_nodes` (composes with the existing
`deleted_at`/`q`/pagination; trashed stay excluded; rule #3). Frontend: `40_app.jsx` `libraryAxisFilter`
state + `filterToAxis`/`clearAxisFilter`/`selectAllLibrary` (the filter is a *view*, exclusive with
trash/focus but keeps checkbox-select on) threaded App→Sidebar→AxesPanel; a banner (reuses the inc-50
`.focus-card`) + a `.lib-select-all` link in `10_pdf_layer.jsx`. **No new endpoint/egress/ingestion/migration**;
read-only (security note in the increment notes, no separate audit). pytest **227** (+1); live E2E
(`.local/library_axis_filter_e2e/`) — filter narrows 2→1 + banner + select-all→summarize verified + clear
restores, 0 console errors; help corpus axis-review section updated (`HELP-DOCS-SYNCED` moved to inc 63).
NEXT: deferred token levers (cache extension + output caps), DESIGN.md `.btn-*` DRY, embedding-text JATS
cleanup, permanent-delete/empty-trash, persistent dedup-dismiss; library **merge** (last).

Earlier — increment 62 (summarize selected papers): the library checkbox multi-select
(inc 54) now wires to a **summarize** action — select papers → click **summarize** in the bulk bar → a
**verified, citation-grounded synthesis of just that subset** runs in the always-on Synthesis pane (with an
"N selected papers" scope-note badge), reusing the existing `/summarize` **papers** scope + local
verification + the inc-61 cache (no new endpoint/egress/ingestion/migration). Wiring:
`40_app.jsx` (`pendingSummarize` nonce + `bulkSummarizePapers`) → `RightPane` → `20_synthesis.jsx`
(`start()`'s POST+poll refactored into a shared `launch()`; a nonce-keyed `useEffect` runs the papers scope
with `top_k = min(max(8, n), 24)`). **Backend coverage fix:** `pipeline.py::_round_robin_by_paper`
interleaves chunks across the selected papers before the `top_k` slice (a plain `rows[:top_k]` is
chunk-id-ordered → would ignore higher-id papers); ≤1 paper → identity, query scope untouched. The
**critical-review supplement** is deferred behind the **Auditability standard** (recorded in the backlog).
pytest **226** (+3: round-robin interleave + a capturing-generator multi-paper coverage proof); live E2E
(`.local/summarize_selected_e2e/`) 0 console errors; audit `.claude/security-audits/2026-06-20_summarize-selected.md`
PASS; help corpus's synthesis section updated (`HELP-DOCS-SYNCED` moved to inc 62). NEXT: deferred token
levers (cache extension + output caps), DESIGN.md `.btn-*` DRY, embedding-text JATS cleanup,
permanent-delete/empty-trash, persistent dedup-dismiss; library **merge** (last).

Earlier — increment 61 (reduce LLM token spend: content-addressed summary cache +
usage logging): a **persistent content-addressed SQLite cache** on the token-expensive **summary
generation** step (a cache hit costs zero tokens — the dominant cost lever). `CachedSummaryGenerator`
(`app/backend/llm/cache.py`) keys on `sha256(canonical_json({cache_signature, chunk set, scope_ref}))`
(`cache_signature` = model + `SUMMARY_PROMPT_VERSION`), so any input change misses automatically (no
explicit invalidation; negative results cached free); stored in `llm_cache` (migration **0005**, head). It
is layered **inside** the egress gate (`EgressGated(Cached(real))`) so egress-off behaves byte-for-byte as
before, and uses the pipeline's existing `conn` (threaded into `generate()`; a 2nd SQLite connection
mid-transaction would lock); **local citation-verification re-runs on every result, cached or fresh** — a
hit replays cached *candidates* and re-verifies them, never serving a stale verdict. Plus token-usage
logging (`llm/usage.py`) at all 4 LLM call sites. Eagerness audit: no hover/preview/auto LLM calls (only
`/axes/suggest` fires on its modal open). The other levers (cache extension to help/labeler/suggester,
output caps + JSON mode, top_k right-sizing, Gemini provider prefix caching, Batch API, coalescing) are
**proposed with a measurement/verification plan and DEFERRED for review** — see `INCREMENT-61-NOTES.md` for
the ranked table + implemented-vs-deferred. pytest **223** (+6); audit
`.claude/security-audits/2026-06-20_llm-cache.md` PASS; no frontend change. NEXT: the deferred token levers
(cheapest: cache extension + output caps, gated on the usage measurements), then backlog — library merge,
terms-as-first-class, embedding-text JATS cleanup, permanent-delete/empty-trash, persistent dedup-dismiss.

Earlier — increment 60 (AI help assistant, separate gate): an AI help assistant in the
help modal — ask a question, get an answer + **reference chips** that scroll to and highlight the matching
help section (reusing inc-59's `flashHelpSection`), recapitulating the synthesis "probe → route to source"
workflow over the app's own help. `POST /help/ask` is gated by its **own** `CALLOSUM_HELP_ASSISTANT_ENABLED`
toggle (new `GeminiConfig.help_assistant_enabled`), **independent** of the library `CALLOSUM_ALLOW_DATA_EGRESS`
gate — it sends only the user's question + the **public** help corpus (never library text), so it works
with the library gate off (proven by a test + a library-egress-off live E2E). Provider-neutral
`HelpAssistant` Protocol (`app/backend/help/assistant.py`) + `GeminiHelpAssistant`
(`integrations/gemini/help_assistant.py`, **NO RAG** — whole corpus stuffed); enforced at the inc-58 seam
(`EgressGatedHelpAssistant` + `HelpAssistantDisabledError`). Multi-turn (stateless), defensive parse
(failure → answer, no refs, never 500), router drops hallucinated section ids. Additive — **no existing
path or API shape touched**. Added an `ai-help-assistant` help section (moving the `HELP-DOCS-SYNCED` marker
to inc 60). pytest **217** (+7: answer+refs, gate-independence, hole-closed 503, unknown-id drop, 422, parse
degradation, self-check); live E2E (`.local/help_assistant_e2e/`, library egress OFF) 0 console errors; audit
`.claude/security-audits/2026-06-20_help-assistant.md` PASS. NEXT: backlog — library **merge** (last,
destructive), terms-as-first-class; DESIGN.md `.btn-*` DRY; embedding-text JATS cleanup;
permanent-delete/empty-trash; persistent dedup-dismiss.

Earlier — increment 59 (help corpus + navigable help modal): the in-app help became a
real surface — extensive end-user documentation served as a structured **corpus**
(`app/backend/help/help_content.md`, 22 sections with **stable anchor ids** via `<!-- section: <id> -->`
markers) by `GET /help/corpus` (stateless, no DB, **no egress**), rendered in a **navigable two-column
modal** (`18_help.jsx`: TOC + sections + a reusable `flashHelpSection(id)` scroll-to-flash) — retiring the
old single hard-coded tips block. `corpus.py` parses the markdown into sections + a small **allowlisted**
HTML render (no new dep); `dangerouslySetInnerHTML` is safe here (app-owned static, escaped/allowlisted —
audit PASS). The **first draft was generated by Codex** (token-saving) then reviewed against the real code
and shipped. Groundwork for the inc-60 AI help assistant (`help_corpus_prompt()` is defined; its references
will reuse `flashHelpSection`). New convention: a **`HELP-DOCS-SYNCED` marker** in `.claude/changes.md` +
a Session-kickoff check so future sessions can tell from the changelog whether the corpus needs updating.
pytest **210** (+7); live E2E (`.local/help_e2e/`) — 22 sections, TOC scroll+flash, 0 console errors; audit
`.claude/security-audits/2026-06-19_help-corpus.md` PASS. NEXT (after the user reviews the in-app docs):
**increment 60** — the AI help assistant (`POST /help/ask`, its own `CALLOSUM_HELP_ASSISTANT_ENABLED` gate
via the inc-58 seam pattern, references → `flashHelpSection`). Other backlog unchanged.

Earlier — increment 58 (provider-agnostic egress gate at the DI seam): moved
data-egress enforcement (invariant #3) from per-provider self-checks **by convention** to a
**provider-neutral gate applied at the dependency-injection seam**, closing the hole where a provider
injected via `create_app(...)` was returned **unchecked**. New `app/backend/llm/egress.py` is the
**canonical home** of `DataEgressDisabledError` (re-exported from `integrations/gemini/generator.py`, so
every existing import path resolves to the same class) + three wrappers
(`EgressGated{SummaryGenerator,AxisTermSuggester,AxisClusterLabeler}`) conforming to the existing
protocols; the three router factories (`_summary_generator`, `_axis_term_suggester`,
`_axis_cluster_labeler`) now resolve the inner provider (injected or default Gemini) and return it
**wrapped** with the `GeminiConfig.from_environment().data_egress_enabled` flag. Egress-on → delegate
unchanged (real Gemini path identical); egress-off → same `DataEgressDisabledError` (summaries job
`error`; suggest-terms 503 via the unchanged handler; labeler → `apply_labels` local fallback, never
503). Providers keep their internal checks as **defense-in-depth**. Tests model consent via an autouse
conftest fixture (`CALLOSUM_ALLOW_DATA_EGRESS=1` by default; egress-off tests `delenv`). No migration, no
new route, no API-shape change; backend-only (no frontend rebuild). pytest **203** (+4: hole-closed +
behavior-preserved across generator/suggester/labeler); audit
`.claude/security-audits/2026-06-19_egress-gate-seam.md` PASS. Also swept 25 stray `*.tmp.26380.*`
atomic-write orphans from a crashed earlier process. NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` —
library **merge** (last, destructive — needs design forks), terms-as-first-class; DESIGN.md `.btn-*` DRY;
embedding-text JATS cleanup; permanent-delete/empty-trash; persistent dedup-dismiss. (`axes.py` is at 586
lines — a split watch candidate.)

Earlier — increment 57 (always-on Synthesis + contextual Details split, backlog F): the
right pane stopped being **tabbed** (Synthesis | Detail) and became a **vertical split** — Synthesis always
on top, and when a paper is selected its editable **Details** appear in a lower section with a **draggable
divider** between them (height persisted to `localStorage["callosum.detailH"]`). Reuses the inc-42 resizer
(`_beginDrag` now passes clientX **and** clientY; horizontal side callers use x, the vertical split uses y).
`RightPane` (`20_synthesis.jsx`) rewritten + dead `.pane-tabs` removed; `SynthesisPane`/`DetailContent`
unchanged; Details aren't mounted when nothing is selected (Synthesis fills the pane). Frontend-only; pytest
199 (unchanged); live E2E (`.local/synthesis_split_e2e/`) — no-paper→synth only, paper→both, drag resizes +
persists across reload, 0 console errors; no audit gate.

Earlier — increment 56 (duplicate detection, flag-only, backlog E): a **"Duplicates"**
scan (library head, next to Trash) surfaces likely-duplicate paper groups for review. New
`app/backend/clustering/duplicate_detection.py` `find_duplicate_groups`: **layered** signals — shared
`csl_json` PMID/arXiv (DOI can't collide, UNIQUE) → identical canonical title+author+year → embedding
cosine ≥0.92 (high, so not same-topic; reuses axis_suggestion's in-memory numpy) — merged by **union-find**
into groups with a confidence + reason. Async `POST /papers/duplicates` + `GET /papers/duplicates/{job_id}`
(mirror `/axes/suggest`; registered before `/papers/{paper_id}`); entirely **local** (no egress); **ephemeral**
+ **flag-only** (never auto-deletes/merges). The review modal (`19_duplicates.jsx`) resolves a group by
**deleting** the redundant copy (reuses the inc-54 soft-delete → Trash, reversible), open, or session-only
dismiss. pytest 199 (+9: 7 unit layers/union-find/trashed + 2 endpoint); live E2E
(`.local/duplicates_e2e/`) 0 console errors; audit `.claude/security-audits/2026-06-19_duplicate-detection.md`
PASS. **Deferred:** library **merge** (the real consolidation, last); **persistent "not a duplicate"**
dismiss. NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — synthesis split (F), terms-as-first-class, library
merge (last); DESIGN.md `.btn-*` DRY; embedding-text JATS cleanup; permanent-delete/empty-trash.

Earlier — increment 55 (fix: strip JATS from the editable abstract + suggest terms):
raw Crossref JATS XML (stored in `papers.abstract` per inc-33) was leaking as `<jats:p>` tags in the inc-49
editable abstract **textarea** and as the term **"jats"** in **suggest-optimal-axes** (the c-TF-IDF
tokenizer). One shared fix: new **`abstract_plain_text(raw)`** (`metadata/abstract_display.py`, a tag-free
sibling of `clean_abstract_for_display`) feeds both — a new `PaperDetailResponse.abstract_text` (the
textarea binds to it) and `axis_suggestion._paper_tokens` (strips JATS before counting terms). Display-only
(stored column untouched; editing the textarea writes the user's plain text). **Deferred:** the abstract's
JATS noise in the *embedding text* (`paper_embedding_text`) — cleaning it needs a `PAPER_TEXT_VERSION` bump
+ a full re-embed. pytest 190 (+7); live E2E (`.local/jats_fix_e2e/`) 0 console errors; no audit gate.
NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — dedup (E), synthesis split (F), library merge (last),
terms-as-first-class; DESIGN.md `.btn-*` DRY; embedding-text JATS cleanup.

Earlier — increment 54 (library delete: soft + multi-select + Trash/Restore, backlog D):
the first way to delete a paper. Checkbox multi-select + a bulk-delete bar (mirrors the inc-43 axis pattern)
→ **soft-delete** (`papers.deleted_at`, migration 0004): hidden from the library/axes/clustering but kept,
with a **Trash ⇄ Library** toggle + per-row **Restore**. Soft because a **hard** delete is unsafe today —
`embeddings.target_id` has no FK + the vector store has no delete method, so it orphans the paper's
embeddings/sqlite-vec vectors and an orphaned paper-embedding crashes `retrieval._resolve_hit`; true
permanent-delete / empty-trash (with vector cleanup) is **deferred**. `DELETE /papers/{id}` (soft, 404 if
missing/already-trashed) + `POST /papers/{id}/restore` + `GET /papers?deleted=true`. `repository`:
`soft_delete_paper`/`restore_paper`, `list_papers(only_deleted=…)`, cluster-node + suggest exclude trashed;
`get_paper` unfiltered (Restore/detail resolve by id). Frontend `40_app.jsx` + `10_pdf_layer.jsx` (the three
row modes normal/focus/trash are mutually exclusive). pytest 183 (+4); live E2E
(`.local/library_delete_e2e/`) 0 console errors; audit `.claude/security-audits/2026-06-19_library-delete.md`
PASS. Deferred (noted): permanent-delete/empty-trash + excluding trashed papers from new synthesis retrieval.
NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — dedup (E), synthesis split (F), library merge (last),
terms-as-first-class; DESIGN.md `.btn-*` DRY.

Earlier — increment 53 (polish pass): four deferred quick wins, frontend-only. (1)
**SRI** — `integrity` sha384 + `crossorigin` on the React/ReactDOM/Babel CDN `<script>`s in `index.html`
(hashes from the immutable cdnjs files; the live E2E rendering under them is the proof they're correct;
pdf.js is loaded dynamically so left as-is). (2) **Radius scale** — `--radius-sm/-lg/-pill` tokens added
(DESIGN.md §3 #6); the clean pill (`999px`/`20px`) + modal (`12px`) values migrated; the messy middle
(4/5/6/8/9px) + the `.btn-*` class DRY left as §3 worklist items (too value-shifting to bundle mid-use).
(3) **In-app HELP viewer** — a **?** button in the sidebar header (top-left, mirroring ⚙) opens
`HelpModal` (`18_help.jsx`) with the axes/tiers tips from `.claude/HELP.md`. (4) **Favicon dark-swap** —
two `media="(prefers-color-scheme:…)"` favicon links (light `favicon.png` / dark `favicon_dm.png`) so the
tab icon follows the **OS** scheme with no JS (trade-off: OS, not the in-app toggle); `inline_brand_assets.py`
now maintains both. pytest 179 (unchanged); live E2E (`.local/polish_e2e/`) 0 console errors; no audit gate.
NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — library multi-select + bulk delete (D, destructive → needs a
soft-delete/undo decision + plan), dedup (E), synthesis split (F), library merge (last), terms-as-first-class;
DESIGN.md `.btn-*` DRY + full radius consolidation.

Earlier — increment 52 (suggest optimal axes): a **✨ Suggest** button mines the
library's own embeddings to propose a *diverse* set of candidate axes that **blanket the literature without
duplicating each other or the user's existing axes**, then the user curates (rename + toggle term chips,
selected-by-default) and creates the ones they like. New `app/backend/clustering/axis_suggestion.py`:
in-memory clustering (`AgglomerativeAbstractClusterer`) → **novelty filter** (drop clusters ≥0.6 cosine to an
existing axis) → **MMR-lite diversity** (skip ≥0.5-similar clusters) → **local c-TF-IDF labels**;
`apply_labels` adds optional **egress-gated Gemini polish** (`integrations/gemini/axis_cluster_labeler.py`,
sends only representative titles) that **falls back to local on any failure — so the endpoint never 503s**.
Async `POST /axes/suggest` + `GET /axes/suggest/{job_id}` (mirror the score job); frontend chunk
`17_axes_suggest.jsx`. Suggestions are ephemeral — creation goes through the existing `POST /axes`. **NO
migration, no new dependency** (numpy/sklearn already present). pytest 179 (+5: clusters/novelty/labeler/
egress-off-local/too-few); live E2E (`.local/suggest_axes_e2e/`, fake model, no network) 0 console errors;
audit `.claude/security-audits/2026-06-19_suggest-axes.md` PASS. NEXT: see
`.claude/docs/INCREMENT-BACKLOG.md` — library multi-select + bulk delete (D, destructive → soft-delete/undo
decision + plan), dedup (E), synthesis split (F), library merge (last); favicon dark-swap; DESIGN.md
`.btn-*` DRY; HELP viewer; SRI.

Earlier — increment 51 (B′: eyeball toggle to hide/show UNCERTAIN papers): a small
follow-on to inc-50's axes UX. `AxisItem` gains a per-axis **👁** toggle (in the re-score row, shown only
when the axis has ≥1 uncertain paper) that filters the list to an **assigned/manual-only** view; a subtle
"N uncertain hidden — show" hint restores them. Pure display filter — frontend-only (`15_axes.jsx` 344,
`styles.css`), no backend/endpoint/migration. pytest 174 (unchanged); live E2E (`.local/eye_e2e/`) 0 console
errors; no audit gate. NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — suggest-optimal-axes, library
multi-select/bulk-delete (D, destructive → needs a soft-delete/undo decision + plan), dedup (E), synthesis
split (F), library merge (last).

Earlier — increment 50 (axes manual-assignment cleanup + library focus-mode, backlog B + C):
the axes panel's manual-override UX. **B:** the redundant "ASSIGNED" tag is gone (assigned = no tag, just
the confidence; amber = uncertain; dashed = manual/human), and a **✓** on uncertain rows promotes a paper to
a manual override. **C:** the per-axis **＋** opens a **library focus-mode** — a reminder card above the
search bar + per-row **+add / ✓ in axis / ✓ staged / − staged** buttons — **staged and committed on Save**
(replacing the inc-38 in-card `AddPaperPicker`). Underpinned by two `axis_scoring.py` correctness fixes so
**`confidence IS NULL` (= manual) is authoritative + durable**: `add_manual_assignment` upserts a scored row
to NULL (the confirm), and `restore_manual_assignments` forces NULL even when present (survives re-score;
also fixed a latent revert-on-re-score bug). Frontend: `15_axes.jsx` (332, AddPaperPicker removed),
`10_pdf_layer.jsx`, `40_app.jsx` (focus state + `axisRefresh` nonce), `styles.css`. **NO new
endpoint/route/migration/egress** — ✓-confirm + focus Save reuse `POST`/`DELETE /axes/{id}/papers`. pytest
174 (+2); live E2E (`.local/axes_manual_e2e/`, fake model) 0 console errors; audit
`.claude/security-audits/2026-06-19_axes-manual-assignment.md` PASS. NEXT: see
`.claude/docs/INCREMENT-BACKLOG.md` — B′ eyeball (hide UNCERTAIN), suggest-optimal-axes, library
multi-select/bulk-delete (D), dedup (E), synthesis split (F), library merge (last).

Earlier — increment 49 (editable Details pane + DOI correction / re-resolve, backlog G):
the Detail pane is now a Mendeley-style **always-editable** bibliographic editor (inline fields, "Add …"
placeholders, **auto-save on blur**, Literature Type dropdown, large editable title, collapsible
**Identifiers**, a **More** section that auto-surfaces extra DOI-populated scalar fields, a **Files** list,
honest provenance footer). A wrong/missing **DOI can be corrected and re-fetched from Crossref** (🔎). New:
`app/backend/metadata/paper_edits.py` (`build_paper_update` — safe partial csl_json merge + column
projection, the linchpin: edits a copy, writes only changed columns → never wipes the record); `PATCH
/papers/{id}` (DOI-UNIQUE clash → 409; empty title/no fields → 422) + `POST /papers/{id}/re-resolve`
(force past the user-edited guard; Crossref miss → graceful 200); `enrichment.USER_EDITED_SOURCE` (NOT in
the can-update allowlist → batch enrich won't clobber hand-edits) + a `force` flag; `create_app(crossref_client=…)`
injectable. Frontend chunk `25_detail.jsx` (DetailContent moved out of `20_synthesis.jsx`; `onOpenPaper=openPdf`
threaded for the Files list). **NO migration** — `csl_json` is the canonical record; scalar columns are
projections. pytest 172 (+22: `test_paper_edits.py` unit + PATCH/re-resolve integration + route surface);
live E2E (`.local/detail_edit_e2e/`, fake Crossref) 0 console errors; audit
`.claude/security-audits/2026-06-19_paper-edit-doi.md` PASS. Deferred (noted): per-attachment PDF serving
(Files opens the primary today — lands with duplicate-merge), multi-URL, Translator(s), a "More" add-field
menu. NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — tier-tag ✓-confirm, B′ eyeball, library
multi-select/dedup/merge, suggest-optimal-axes.

Earlier — increment 48 (sidebar density + cutoff acts on displayed precision):
finished the **B″ density** pass — dropped the "local reference workbench" subtitle, added an axis
**filter** (`Filter axes…`, matches title or terms), turned "+ new" into a green **"+"** (`--verified`),
all on one no-wrap controls row (`Filter… · sort ▾ · +`) so more axes are visible. Also a **rounding fix**
(`_confidence_from_cosine_distance` now `round(…,2)`): confidences are stored/compared at the 2 decimals
the UI shows, so a paper displayed as "0.35" can't be tagged UNCERTAIN because its raw score was 0.349
(user-caught). Frontend-only density + a 1-line backend round; pytest 150; live E2E (`.local/density_e2e/`)
0 console errors. **B″ is now complete** (with inc 47's connection-in-logo). NEXT: see
`.claude/docs/INCREMENT-BACKLOG.md` — favicon dark-swap, DESIGN.md `.btn-*` DRY + radius scale, HELP
viewer, terms-as-first-class, tier-tag ✓-confirm, B′ eyeball (hide UNCERTAIN), library focus-mode/
multi-select/dedup/merge, synthesis split + editable Details + DOI re-search, suggest-optimal-axes, SRI.

Earlier — increment 47 (connection status shown by the logo): retired the textual
`● connected · local-verifier-v1` line; the **brand logo now carries the signal** — a green dot in the
brain's cell-body when connected — using the user's `logo_on`/`logo_dm_on` assets. Implemented as a
**4-state CSS `background-image`** (theme × a `.connected` class): four `--logo-*` tokens in `styles.css`
`:root` hold the base64 (**kept in CSS, not the Babel script** — 4 logos there would blow its 500KB deopt
cap). `.brand-logo` is now a `<div>` (removed the inc-46 two-`<img>` toggle); `ConnStatus` + the `.conn`/
`.led` CSS removed; the "local reference workbench" subtitle kept (its removal is a separate B″ item).
Losslessly recompressed `logo_on`/`logo_dm_on` (423KB→57KB); `inline_brand_assets.py` repointed to the 4
CSS tokens. Frontend-only; pytest 149 (unchanged); live E2E (`.local/conn_logo_e2e/`) 0 console errors;
no audit gate. NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — **B″ remaining** (drop the subtitle +
verifier text entirely, axis **filter** field, "+ new" → green "+", single no-wrap row); then favicon
dark-swap, DESIGN.md `.btn-*` DRY + radius scale, HELP viewer, terms-as-first-class, tier-tag ✓-confirm,
library focus-mode/multi-select/dedup/merge, synthesis split + editable Details + DOI re-search,
suggest-optimal-axes, SRI hardening.

Earlier — increment 46 (DESIGN.md token consolidation + dark mode + Settings modal):
finished DESIGN.md's color-token consolidation (scattered hex → tokens; split destructive color reconciled
to a new `--danger`) — the groundwork for a **warm-dark theme** via `:root[data-theme="dark"]` CSS-variable
overrides. `data-theme` is set on `<html>` by a **no-flash bootstrap** `<script>` in `index.html`'s head
(localStorage/`prefers-color-scheme`); toggled in a new **Settings modal** (`35_settings.jsx`) opened by a
**gear icon** in the sidebar. The **rendered PDF page stays light** in both themes (only chrome themes);
`--on-fill` flips so text stays legible on the now-light semantic fills; the brand logo CSS-swaps to
`logo_dm.png` (losslessly recompressed 427KB→57KB so the inline Babel script stays under its 500KB deopt
cap). **Any CSS change must read `.claude/DESIGN.md` (rule #8).** Frontend-only; pytest 149 (unchanged);
live E2E (`.local/dark_mode_e2e/`) 0 console errors; audit `.claude/security-audits/2026-06-19_dark-mode-settings.md`
PASS. NEXT: see `.claude/docs/INCREMENT-BACKLOG.md` — DESIGN.md §3 worklist remaining (`.btn-*` DRY +
radius scale), favicon dark-swap, **B″ sidebar density** (+ connection-in-logo), HELP viewer,
terms-as-first-class, tier-tag ✓-confirm, library focus-mode/multi-select/dedup/merge, synthesis split +
editable Details + DOI re-search, suggest-optimal-axes; hardening: SRI on the CDN scripts.

Earlier — increment 45 (adjustable assignment cutoff + axis-card redesign): the
assigned/uncertain badge is now an **absolute cutoff** (default 0.35), **per-axis, persisted**
(`axes.scoring_gain`; migration 0003, additive + auto-applied on startup) and **user-adjustable** via a
"Cutoff" flipper on the Re-score row — superseding inc-39's relative natural-break, which assigned only
the top 2–6 papers (the largest gap sits near the top of real axes' smooth similarity declines). Axis
cards redesigned: ✎/＋/🗑 icon buttons (＋ auto-expands + opens the add-paper picker; ✎ does NOT expand) +
a circular **red count badge**; Re-score is the lone in-list control. The relative-tiers tip moved to
`.claude/HELP.md` (in-app help viewer deferred). `_axis_text` unchanged; existing axes re-tier at 0.35 on
read with NO re-score needed. pytest 149; live E2E (`.local/axis_gain_e2e/`) 0 console errors; audit
`.claude/security-audits/2026-06-19_axis-gain.md` PASS. `axis_scoring.py` 588, `axes.py` 466,
`15_axes.jsx` 378. NEXT: the running to-do list **`.claude/docs/INCREMENT-BACKLOG.md`** (guiding
principle: *reference manager first*) — queued: in-app HELP viewer, Settings (cutoff default +
light/dark), terms-as-first-class, **B′ eyeball toggle** (hide/show UNCERTAIN), tier-tag ✓-confirm (B),
library focus-mode (C), suggest-optimal-axes, library multi-select/dedup/merge, synthesis split + editable
Details + DOI re-search. Open proposals: undo/soft-delete, filter-library-by-axis.

Earlier — increment 44 (axis edit modal + title/term decoupling + click-to-open; backlog
A + A′): one **Edit Axis modal** (`14_axes_edit.jsx`) for create/edit/term-search — the **title is now a
cosmetic display name** and the *search vocabulary* is a curated terms list stored in the description's
`Related:` block (primary term first). `_axis_text` embeds the **description only** (label fallback; no
migration) so the title no longer pollutes the query; existing axes show stale → re-score once. Suggested
terms arrive **deselected** (selected sort to top — human-in-the-loop). "+ new" = a quick inline name →
prefilled modal. Removed the inline create/edit forms, the inc-41 terms modal, the standalone "suggest
terms" action, and the per-axis `.axis-desc` preview (terms live only in the modal). **A′:** clicking an
axis-listed article opens its PDF (`onOpenPaper` threaded App→Sidebar→AxesPanel). pytest 147 (+2: scoring
keys on description not label; label-only fallback); live E2E (`.local/axis_edit_e2e/`) 0 console errors;
audit `.claude/security-audits/2026-06-19_axis-edit-modal.md` PASS (no new endpoint/egress/ingestion).
`15_axes.jsx` 448→357, new `14_axes_edit.jsx` 102. NEXT: the running to-do list
**`.claude/docs/INCREMENT-BACKLOG.md`** (guiding principle: *reference manager first*) — A + A′ now done;
next is **B** (tier-tag cleanup: remove the ASSIGNED tag, ✓-confirm uncertain papers) + **C** (library
focus-mode manual add), then suggest-optimal-axes (now safe against the finalized axis model); then library
multi-select + bulk delete, AI dedup (after **G** = editable Details + DOI re-search), always-on synthesis +
contextual Details, settings + light/dark; library **merge** deferred to last (free-form). Open proposals:
undo/soft-delete, filter-library-by-axis.
Earlier — fix (2026-06-19, post-inc-44): an axis could show "re-score" forever after a merge —
`axis_score_state` judged freshness from the newest embedding row by id, but `_embed_axis` accrues one
row per scored text version (never pruned), so a merge/edit cycle revisiting a prior version left a stale
higher-id row above the matching one. Now fresh if ANY stored embedding matches the current text
(self-heals on read; no re-score needed). Also restored the 600-line cap (`_axis_text`'s inc-44 comment
had pushed `axis_scoring.py` to 603 → 598). pytest 148.
Earlier — increment 43 (axis management): sortable ordering (name / paper count / newest),
checkbox multi-select with a bulk-action bar (delete N, or merge ≥2), and a **merge** that folds axes into
one surviving axis via a comparison/curation view (`16_axes_merge.jsx`) — each folded axis's label carried
into the survivor's `Related:` terms so a re-score keeps its papers discoverable; manual assignments
unioned, survivor auto-re-scores. New `app/backend/clustering/axis_operations.py` (`merge_axes`); `POST
/axes/merge` + `created_at` on `AxisResponse` (no migration). pytest 145; audit
`.claude/security-audits/2026-06-19_axis-merge.md` PASS.
Earlier — increment 42 (resizable + collapsible side panels): the `.app` grid's side
columns are React state with drag-grip resizers + chevron collapse toggles (a `Divider` between each side
panel and the center); the center PDF/library area expands as a side collapses; layout persists to
localStorage. Frontend-only (`40_app.jsx` + `styles.css`, rebuilt `callosum-app.html`); removed the old
narrow-screen media query. pytest 143 (Python untouched).
Earlier — increment 41 (Gemini axis synonym suggester): optional AI assist to broaden
niche axes. New `integrations/gemini/axis_terms.py` (`GeminiAxisTermSuggester`, mirrors the summary
generator) + `POST /axes/suggest-terms` (sync, stateless, **egress-gated** — off → 503 before any genai
call; other failure → 502). The user curates suggested terms in a new modal (`15_axes.jsx`); chosen terms
fold into the axis description (re-score to apply) — no migration. Untrusted model output is
deduped/capped/echo-stripped; suggester injectable for hermetic tests. pytest 143 (+3); live E2E +
security audit PASS. NEXT (queued, per the user): resizable/collapsible panels → axis-management tree
(sort + multi-select + bulk delete/merge) → suggest-optimal-axes (unsupervised + coverage-with-diversity).
Earlier — increment 40 (axis punctuation normalization): axes differing only in
punctuation/spacing scored differently ("anomalous-is-bad" vs "anomalous is bad") because `normalize_text`
keeps punctuation and MiniLM tokenizes them differently. New `strip_punctuation` util
(`embeddings/models.py`) is applied to the axis text before embedding + text-versioning (`_embed_axis` +
`axis_score_state` in `axis_scoring.py`), so equivalent phrasings produce an identical axis embedding.
Axis-side only (no paper re-embed, no migration, no frontend). pytest 140 (+2). Users re-score punctuated
axes once (they show stale). NEXT: Gemini synonym-suggestion modal (egress-gated, user-curated) to raise
recall on niche axes.
Earlier — increment 39 (axis scoring calibration): inc-38's absolute thresholds
(assigned ≥0.7 / uncertain ≥0.5) assigned NOTHING on real data — `all-MiniLM-L6-v2` axis-vs-paper-metadata
cosine maxes ~0.37 (median 0.02), though the ranking is correct. Replaced with **natural-break relative
tiering**: new `assignment_mode="natural_break"` + `SUPERVISED_AXIS_CONFIG` (noise floor 0.2, minimum_gap
0.03) — assigned = the cluster above the largest gap in the axis's ranking, uncertain = the rest of the
eligible, never-empty fallback. Tiers recomputed on read from stored confidences (`natural_break_assigned_ids`)
→ no migration, read == score. The 0.2 floor is a documented MiniLM constant. pytest 138; real-data check +
live E2E green. Users must re-score axes scored under the old logic. `axis_scoring.py` 595 (<600).
Earlier — increment 38 (Axes increment 1: create/browse/score/correct user-defined
axes): exposed the existing `app/backend/clustering/axis_scoring.py` engine as write endpoints + an
AxesPanel UI (`app/frontend/js/15_axes.jsx`). New on the axes router: `POST /axes`, `PATCH`/`DELETE
/axes/{id}`, async `POST /axes/{id}/score` + `GET /axes/score/{job_id}` (mirrors the summarize job;
fully local, no egress), `POST`/`DELETE /axes/{id}/papers` (manual override). Scoring uses
`assignment_mode="absolute"` → assigned ≥0.7 / uncertain ≥0.5 / below-threshold (not stored). NO
migration: manual-vs-scored = `confidence IS NULL` vs float; staleness via the axis embedding's stored
`source_text_version` + `normalization`. Re-score preserves manual adds. Sidebar Axes panel is now
create/browse/correct (was read-only). pytest 136 (route-surface updated); hermetic fake-model tiers +
live browser E2E (create→score→tiers→manual-add, 0 console errors). Supervised single-lens only;
unsupervised/synthesis-scope/multi-pole deferred. Audit:
`.claude/security-audits/2026-06-17_axes-supervised.md`.
Earlier — increment 37 (modularize the monolith files): behavior-preserving split
of the oversized files to satisfy the 600-line rule and enable directed reviews. `app/backend/api/app.py`
1108→113 (thin factory + `routers/{health,papers,annotations,axes,summaries}.py` + `startup.py` +
`dependencies.py`; only logic change: `/summarize*` read the job store via `request.app.state`).
`pdf_processing/extraction.py` 662→555 (+`quote_matching.py`). `tests/test_api.py` → `conftest.py` +
`api_helpers.py` + per-resource `test_*.py`. `tools/validation_harness.py` 1298→898 (report
dataclasses + markdown renderer → `tools/validation/`; probes stay — exempt). `callosum-app.html`
2023 → modular `app/frontend/` assembled at serve time into one document at `/` (no build step, no new
file-serving surface; JSX concatenated into one `<script>` so shared scope is unchanged); old file
deleted. No file under `app/`/`integrations/` now exceeds 600 (largest `extraction.py` 555). pytest 129
(route-surface invariant green); inc-36 E2E green vs the assembled frontend (reload-drift 0.0px, 0
console errors). Audit: `.claude/security-audits/2026-06-17_frontend-assembly.md`.
Earlier — increment 36 (synthesis → annotation bridge, suite C): a verified,
exact-coordinate synthesis citation can be saved as a durable `source="synthesis"` annotation.
`POST /papers/{id}/annotations` now accepts an optional `source` (allowlist-validated against
`NATIVE_ANNOTATION_SOURCES`, forged → 422; defaults `"user"`) — no new route, no migration. A
"Save as highlight" control on each citation card is enabled only for exact+verified citations and
otherwise disabled-with-tooltip (honesty contract); saved synthesis highlights render with a distinct
dashed `.pdf-synthesis-outline` and appear live in an open viewer via an `annoRefresh` nonce (no
reload). pytest 129; headless E2E: gating proof + reload-drift 0.0px + 0 console errors. See
`.claude/security-audits/2026-06-17_synthesis-source.md` + `INCREMENT-36-NOTES.md`.
Earlier — increment 35 (multi-line highlight compositing): fixed the darker
interior band by flattening each annotation's per-line rects into an isolated per-annotation group
(opaque fills union without doubling) that composites once via multiply (opacity 0.7) — uniform on
every row, text-legible. No geometry change; reload-drift 0.0px; gap-row luminance spread ~2.4 across
the page. Frontend-only; pytest 126.
Earlier — increment 34 (PDF text-layer alignment): fixed progressive text-layer↔
canvas drift by single-sourcing the scale (exact un-floored CSS dims for canvas/text/overlays),
device-resolution canvas backing (DPR-aware), and removing responsive shrink; added a matchMedia
DPR-change re-render. Bottom-of-page drift −7.97px→−0.20px; highlight reload-drift 0.0px at
50/75/115/195% + dpr2. Frontend-only; pytest 126.
Earlier — startup auto-migration is now loud (INFO check / WARNING "auto-migrated
X→Y" / INFO "already at head" / ERROR-but-non-fatal on failure, on stdout via a `_loud()` helper that
survives Alembic's `fileConfig`), and `/health` is honest (`db_migrated` = at-head, plus
`db_revision`/`db_head_revision`). No schema change; env.py untouched. pytest 126.
Earlier — increment 33 (clean JATS abstracts): Crossref abstracts stored raw as
JATS XML now render structured in the Detail pane via a new allowlisted-HTML transform
(`clean_abstract_for_display`) exposed as a derived `abstract_display` field; raw `abstract` and the
stored column are untouched. App's first `dangerouslySetInnerHTML` (allowlisted output only; audited).
No schema change. pytest 122.
Earlier — fix: highlight-create 500'd on stale `.local` DBs missing the
`annotations` columns (never run through migration `0002`). The app now **auto-migrates the
configured DB to head on startup** (lifespan), the frontend **surfaces API errors** (toast +
console.warn) instead of swallowing them, and all existing `.local/**/validation.sqlite` were
migrated. No schema change (head stays `0002`). pytest 113.
Earlier — increment 32 (branding): brain `logo.png` shown before the "Callosum"
wordmark + `favicon.png` wired, both inlined as base64 `data:` URIs from `app/media/` (no new
file-serving surface). Pure frontend; pytest still 113.
Earlier same day — increment 31 (annotation notes + management panel): `note` now
writable via the project's first update endpoint `PATCH /annotations/{id}` (note/color only,
note capped 4000) + `note` on create; a collapsible in-viewer panel lists/edits/deletes/jumps-to
annotations; note indicator on commented highlights. No migration (the `note` column already
existed). See `.claude/security-audits/2026-06-16_annotation-notes.md` + the decision-log row.
Earlier same day — increment 30 (annotation highlights): first user-authored data +
first mutating endpoints. Extended the `annotations` table (now shared across imported/user/
synthesis via a `source` discriminator) and added `POST/GET /papers/{id}/annotations` +
`DELETE /annotations/{id}`; see the decision-log rows + `.claude/security-audits/2026-06-16_annotations.md`.
Earlier same day — initial authoring, adapted from the renovatr / rubberhead / clffwrkmn CLAUDE.md
house style and customized to callosum (local-first Python reference manager): dropped all
web-deploy machinery; added the citation/coordinate honesty invariants, the egress gate, the
increment workflow, and the zip-snapshot backup model.*
