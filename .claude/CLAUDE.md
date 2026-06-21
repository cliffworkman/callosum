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

It is currently at **Increment 77** (see Increment workflow) with **347 pytest tests
passing** (+1 opt-in browser smoke). It is a working MVP backed by a thorough planning suite in `.claude/docs/`.

**Stack:**
- **Backend:** Python 3.11+, FastAPI + Uvicorn (`app/backend/api/app.py`).
- **Persistence:** SQLite via SQLAlchemy Core 2.0; Alembic migrations (`alembic/`).
- **Vectors:** `sqlite-vec` (in-process, no separate daemon) + sentence-transformers
  (default embed model `all-MiniLM-L6-v2`; `bge-base-en-v1.5` also supported).
- **Clustering:** scikit-learn agglomerative clustering + local axis scoring.
- **PDF:** PyMuPDF (`fitz`) for text + bbox extraction.
- **LLM (selective):** `google-genai` → Gemini `gemini-2.5-flash-lite`, **summary generation
  only**, OFF by default (see Core design invariants). Verification NLI runs locally
  (`cross-encoder/nli-MiniLM2-L6-H768`).
- **Frontend:** modular source under `app/frontend/` (`index.html` shell + `styles.css` +
  ordered `js/*.jsx` React chunks, pdf.js via CDN), assembled by `app/backend/api/frontend.py`.
  `tools/build_frontend.py` rebuilds the single-file `callosum-app.html` (byte-identical to the
  old hand-maintained file) from that source; FastAPI serves it at `/` by default, falling back
  to live assembly if it's absent. No bundler, no extra file-serving surface (the JSX is
  concatenated into one `<script>`, so its shared global scope is identical to the old file).
  **Re-run `python tools/build_frontend.py` after editing anything under `app/frontend/`.**
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
│   ├── DESIGN.md                  (the design dictionary — rule #8)
│   ├── docs/                      (planning suite: product-scope, data-contracts, architecture, risk-register,
│   │   ├── increment-notes/       glossary, INCREMENT-BACKLOG, README; increment-notes/ = the per-increment diary;
│   │   ├── future-tracks/         future-tracks/ = longer-horizon docs; future-tracks-import/ = the watched inbox
│   │   └── future-tracks-import/  (session-kickoff watch rule, Phase 8; gitignored — local-only dropzone).
│   │                              NB roadmap.md + backlog-future-tracks.md were archived → deprecated/)
│   ├── research/                  (deep-research planning + feedback docs)
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
│   │   │                          frontend.py [serve-time assembler], routers/{health,papers,duplicates,
│   │   │                          acquisition,wanted,annotations,tags,axes,summaries,help}.py [models + helpers + handlers])
│   │   ├── persistence/           (schema.py [SQLAlchemy Core], database.py, repository.py,
│   │   │                          dedup_repo.py [dismissed-duplicate-pairs data access, inc 67],
│   │   │                          tags_repo.py [tag data access, inc 71], acquisition_repo.py [OA attachment labels, inc 74],
│   │   │                          wanted_repo.py [wanted-list data access, inc 76])
│   │   ├── pdf_processing/        (extraction.py [PyMuPDF text + canonicalize], quote_matching.py
│   │   │                          [locate_quote → bbox rects], ingest.py, location.py, cli.py)
│   │   ├── embeddings/            (models.py, pipeline.py, vector_store.py [sqlite-vec], retrieval.py)
│   │   ├── clustering/            (abstract_clustering.py, axis_scoring.py [scoring engine],
│   │                          axis_assignments.py [manual-override + state API], axis_suggestion.py,
│   │                          axis_operations.py, duplicate_detection.py, tag_suggestion.py [inc 72])
│   │   ├── summarization/         (pipeline.py, generators.py, verification.py)
│   │   ├── llm/                   (egress.py [provider-neutral DataEgressDisabledError + seam-gate wrappers, inc 58];
│   │   │                          cache.py [content-addressed summary-generation cache, inc 61]; usage.py [token logging])
│   │   ├── help/                  (help_content.md [served corpus, inc 59], corpus.py [loader + allowlisted
│   │   │                          md→html], assistant.py [HelpAssistant Protocol + dataclasses, inc 60])
│   │   ├── importers/             (zotero.py)
│   │   ├── metadata/              (doi.py, enrichment.py, abstract_display.py,
│   │   │                          paper_edits.py, citation_export.py [BibTeX/RIS/CSL-JSON, inc 70])
│   │   └── acquisition/           (registry.py [OaLocation OA-only seam + cascade], fetch.py [download/validate/
│   │                              name/import], wanted.py [wanted-list re-check service, inc 76], resolvers/{openalex,
│   │                              doaj,europepmc,crossref,core,arxiv,biorxiv,osf}_resolver.py; the OA acquisition
│   │                              clean lane, inc 74 + cascade inc 75 + wanted list inc 76)
│   ├── frontend/                  ← the UI SOURCE: index.html shell + styles.css + js/*.jsx chunks
│   │                              (assembled by app/backend/api/frontend.py; build → callosum-app.html)
│   └── desktop-shell/             (placeholder — Tauri, post-V1)
├── integrations/                  (external adapters: zotero, crossref, gemini, openalex, doaj, europepmc, core,
│                                  arxiv, biorxiv, osf [impl]; api_cache.py [shared cache helper]; semantic-scholar,
│                                  grobid, mendeley [planned])
├── research/                      (planning + research docs; Track-D acquisition rate-limit records)
├── ops/                           (deployment notes — planning state; gets real content pre-deploy)
├── tools/                         (validation_harness.py + validation/ [reports.py, report_renderer.py],
│                                  enrich_metadata.py, inline_brand_assets.py, build_frontend.py)
├── tests/                         (pytest suite — per-resource files + conftest.py + api_helpers.py; 303 passing;
│                                  tests/e2e/ = opt-in Playwright browser smoke, CALLOSUM_RUN_E2E=1)
├── alembic/                       (env.py + versions/0001_persistence_core … 0008_wanted_items)
├── alembic.ini, pyproject.toml, requirements.txt, requirements-dev.txt
├── callosum-app.html              ← GENERATED from app/frontend/ by tools/build_frontend.py; served at /
├── library/                       (77 scholarly PDFs; "Author et al. - YEAR - Journal.pdf"; gitignored)
└── .local/                        (generated validation DBs + debug images; gitignored)
```

`.gitignore` excludes `.local/`, `.pytest_cache/`, `__pycache__/`, `*.py[cod]`, `*.sqlite`,
`*.db`, `*.pdf`. **NB: callosum is not currently a git repo** (no `.git/`) — the `.gitignore`
documents intended exclusions for when it becomes one. Recovery today is via zip snapshots +
Dropbox version history (see Backup & snapshot protocol).

---

## The rules

### 1. 600-line hard limit on application source

Any file under `app/` or `integrations/` must stay **under 600 lines**. Files approaching it
are split proactively; a file that crosses it MUST be modularized before the next feature
lands in it. Split by concern — routers, repositories, pipeline stages, adapters — and keep
shared/core code loading first.

**Exempt-but-watched:** `tests/` and `tools/` (the validation harness is allowed to be large),
and non-code (Markdown, SQL, config).

**Standing split tasks:** none currently over the limit — the release-readiness Phase-5 pass split
`axis_scoring.py` (617→463) by moving the manual-assignment/state API to `axis_assignments.py` (167), and
consolidated the four duplicated async-job stores into a generic `app/backend/api/job_store.py`
(`Job`/`JobStore[R]`). Largest app-source files now: `repository.py` (~577),
`app/backend/api/routers/papers.py` (~576), `extraction.py` (~551), `routers/axes.py` (~527),
`schema.py` (~494) — all comfortably under 600. (The editable Detail pane lives in its own chunk
`app/frontend/js/25_detail.jsx`; the edit-mapping logic is `app/backend/metadata/paper_edits.py`.)

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

---

## Increment workflow

callosum is built in **numbered increments** (currently at 77). Each increment of real work
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

callosum is **not a git repo**, so backups are deliberate:

1. **Zip snapshots** of the working tree land in `.claude/backups/` (`callosum_HHMMpm.zip`,
   `callosum_inc29.zip` style). Take one before a risky refactor or at the end of a substantial
   increment.
2. **Dropbox version history** is the always-on safety net for individual files.
3. **Plan-file backups:** plan files at `~/.claude/plans/*.md` are per-conversation and get
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
| `.claude/DESIGN.md` | **Design dictionary — read before ANY CSS/inline-style change (rule #8): tokens, element recipes, fixed color/type semantics, consolidation worklist** |
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
| `.claude/research/opus4.8_deepresearch_callosum_plan.md` | Architecture + tech survey baseline |
| `.claude/research/opus4.8_deepresearch_callosum_feedback.md` | Review of the planning skeleton |
| `.claude/deprecated/backlog-future-tracks.md` | **Archived (Phase 6, 2026-06-20)** — earlier capture of the external tracks, superseded by `.claude/docs/future-tracks/` (the canonical source). |

---

## Architectural decision log

| Decision | Rationale |
|---|---|
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
| Modular `app/frontend/` source + a rebuilt single-file `callosum-app.html` artifact (inc 37) | Splitting the 2023-line monolith for directed review while preserving the single file (file-based UI testing expects it). Source of truth: `app/frontend/` (`index.html` shell + `styles.css` + ordered `js/*.jsx`). `app/backend/api/frontend.py` concatenates them into one document (JSX into a single `<script>`, so the shared global scope is identical to the old file); `tools/build_frontend.py` writes that to `callosum-app.html` (byte-identical to the pre-split file). `/` serves the built `callosum-app.html` when present (default), else assembles live (never broken); `CALLOSUM_FRONTEND_PATH` overrides. Trade-off vs the old "no build step" rule: editing the UI now means re-running `build_frontend.py` (the live-assembly fallback keeps the server correct meanwhile) — no bundler, still no extra file-serving surface. |
| Supervised axes expose `axis_scoring.py` with NO migration (inc 38) | Manual-vs-scored assignment = `cluster_node_papers.confidence IS NULL` (manual override) vs a float (scored) — the column was already nullable and the scorer always writes a float, so no schema change. Staleness reuses the axis embedding's stored `source_text_version` + `normalization` (recompute the current axis text-version, compare) — no stored flag needed. Scoring runs async (mirrors the summarize job; fully local, no egress); tiering is calibrated per the inc-39 row (absolute 0.7/0.5 thresholds were unreachable for MiniLM and replaced by relative natural-break). Re-score preserves manual adds (snapshot NULL rows → restore after `score_axis` rewrites the scored set), honoring "the human overrides the embedding". |
| Axis tiering is RELATIVE (natural-break), not absolute (inc 39) | `all-MiniLM-L6-v2` cosine between a short axis phrase and paper metadata is compressed near 0 (observed max ~0.37, median 0.02), so absolute 0.5/0.7 cutoffs assigned nothing. New `assignment_mode="natural_break"` + `SUPERVISED_AXIS_CONFIG` (floor 0.2, minimum_gap 0.03): **assigned** = the cluster above the largest gap in this axis's ranking (≥ floor); **uncertain** = the rest of the eligible; never-empty fallback shows the closest few. The 0.2 floor is a documented MiniLM constant. Tiers are **recomputed on read** from the stored confidences (`natural_break_assigned_ids`, same config) so read == score with NO persisted tier column / migration. Raw similarity still shown honestly. Axis text is **punctuation-normalized** before embedding (inc 40, `strip_punctuation` in `embeddings/models.py`) so phrasings differing only in punctuation/spacing (e.g. "anomalous-is-bad" ≡ "anomalous is bad") embed identically; axis-side only (papers unchanged). |
| Gemini axis synonym suggester is egress-gated + human-curated (inc 41) | `POST /axes/suggest-terms` (sync, stateless) proposes related terms via Gemini; the user curates them in a modal and the chosen terms fold into the axis **description** (reuses the existing axis-text→embed + staleness paths — no new persistence/migration). Mirrors `GeminiSummaryGenerator`: opt-in via `CALLOSUM_ALLOW_DATA_EGRESS` (off → 503 before any genai call), only the user's own axis text leaves the machine, model output is deduped/capped/echo-stripped, failures → 502 (never 500). The suggester is injectable (`api.state.axis_term_suggester`) so tests are hermetic. |
| Zip-snapshot + Dropbox backups instead of git | Matches the user's single-machine workflow today; `.gitignore` is staged for when git is adopted. |
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
10. **When in doubt, ask.** This project is pre-release with one user — a 30-second confirmation
   is cheaper than a wrong turn.

---

*Last updated: 2026-06-20 — increment 77 (hide uncertain axis papers by default): a backlog quick-win — the
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
