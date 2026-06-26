# Retraction producer SP1 — implementation plan (increment 131)

**Goal:** Multi-source (Crossref + OpenAlex) per-DOI retraction detection → FACT findings + an honest per-paper
check-status signal + a library "Retracted" filter/chip. Design: `2026-06-26-retraction-producer-sp1-design.md`.

**Global constraints:** SQLAlchemy Core bound params only (rule #3); files < 600 lines (rule #1); no Gemini gate
(public metadata egress); reuse `findings_repo.upsert_findings` + `signals_repo` + `SIGNAL_FILTERS` + the
statcheck batch pattern + the inc-130 FactMark + the inc-100 chip; injected checkers → hermetic tests; egress-off
default. TDD; commit per task; ruff before push; CI green.

---

## Task 1 — backend core: signals, checkers, merge/detect/apply (no network)

**Files:** create `app/backend/methods/retraction.py`; extend `app/backend/persistence/signals_repo.py`,
`integrations/crossref/adapter.py`, `integrations/openalex/adapter.py`; create `tests/test_retraction.py`.

**Interfaces produced:**
- `RetractionSignal` dataclass: `source: str`, `status: str` (`"retracted"|"correction"|"concern"`),
  `nature: str|None`, `date: str|None`, `reason: str|None`, `notice_doi: str|None`, `notice_url: str|None`.
- `merge_signals(signals: list[RetractionSignal]) -> MergedRetraction | None`.
- `RetractionOutcome` (`status_kind: "retracted"|"none"|"unchecked"`, `merged`, `sources_checked: list[str]`).
- `detect_retraction(conn, paper, *, checkers: list[Callable]) -> RetractionOutcome` (paper = a mapping with
  `id`/`doi`/`csl_json`).
- `apply_retraction(conn, paper_id, outcome) -> None`.
- `signals_repo.store_retraction_status(conn, paper_id, *, status, sources, checked_at)`,
  `count_retraction_flagged(conn) -> int`, `get_retraction_status(conn, paper_id) -> RowMapping | None`.
- checkers: `crossref_retraction_checker(conn, paper)` (wraps `CrossrefClient.lookup_retraction`),
  `openalex_retraction_checker(conn, paper)` (wraps `OpenAlexClient.lookup_retraction`).

**Status escalation order:** `concern (0) < correction (1) < retracted (2)`. `STATUS_RANK` dict.

- [ ] **Step 1 — failing tests for `merge_signals` + `detect_retraction` + `apply_retraction`** (`tests/test_retraction.py`).
  Use injected fake checkers (plain callables returning a `RetractionSignal` or None or raising). Assert:
  - merge: openalex-only (`status=retracted`, no notice) + crossref (`status=retracted`, notice_doi/date) →
    merged keeps the notice detail + `sources=["crossref","openalex"]` (sorted); a `correction` + a `retracted`
    → merged `status="retracted"`; `[]` → None.
  - detect: paper with no `doi` → `RetractionOutcome(status_kind="unchecked")` and **no** checker was called
    (use a checker that records calls); both checkers return None (ran) → `none`; one returns a signal →
    `retracted` with merged set; a checker raises → skipped, the other still merges; DOI present but **every**
    checker returns None *because none resolved* — model "didn't resolve" distinctly (a checker returns a
    sentinel? No — keep it simple: a checker returns None for "checked, nothing found"; for "couldn't resolve"
    it also returns None. To distinguish unchecked-due-to-no-resolution from clean, detect treats *DOI present +
    ≥1 checker ran without error* as `none`; only *no DOI* is `unchecked` in SP1). → Simplify the design's
    "no checker resolved → unchecked" to: **no DOI → unchecked; else none/retracted** (resolution failures fold
    into `none` but the `sources_checked` list records which sources actually answered; document this).
  - apply: retracted outcome → `get_paper_findings` has the FACT (source `"retraction"`, kind `"fact"`,
    payload.status `"retracted"`, payload.sources set) **and** `get_retraction_status` = `retracted`; a `none`
    outcome → **no** finding + signal `none`; re-apply retracted twice → one finding (idempotent); apply
    retracted then apply none → finding **gone** (superseded by `upsert_findings(...,[])`) + signal `none`;
    unchecked → no finding + signal `unchecked`.
  Run: `pytest tests/test_retraction.py -q` → FAIL (module missing).

- [ ] **Step 2 — `signals_repo` additions.** Add `store_retraction_status` (OR-REPLACE upsert on the unique
  `(paper_id, signal_type="retraction", source="retraction")`, mirroring `store_statcheck`; `status` column =
  the outcome; `evidence_snippet` = JSON-ish `"sources=…; checked_at=…"`), `count_retraction_flagged` (count
  `signal_type="retraction" AND status="retracted"`), `get_retraction_status`. Run the apply tests (still fail —
  retraction.py missing).

- [ ] **Step 3 — `methods/retraction.py`.** Implement `RetractionSignal`, `MergedRetraction`, `STATUS_RANK`,
  `merge_signals` (escalate status; richest non-null detail wins; `sources=sorted(set)`), `RetractionOutcome`,
  `detect_retraction` (no-DOI→unchecked; else run checkers best-effort [try/except per checker], merge → outcome;
  `sources_checked` = sources whose checker returned non-None-or-ran-cleanly), `apply_retraction`
  (findings FACT via `upsert_findings` when retracted else `upsert_findings(...,[])`; always `store_retraction_status`).
  Run `pytest tests/test_retraction.py -q` → the merge/detect/apply tests PASS.

- [ ] **Step 4 — failing tests for the two checkers** (injected fake fetchers). Crossref: a fake raw response
  whose `message["update-to"] = [{"type":"retraction","DOI":"10.x/notice","updated":{"date-parts":[[2021,3,15]]}}]`
  → signal `status="retracted"`, `notice_doi`, `date="2021-03-15"`; no update-to → None; a `"correction"` type →
  `status="correction"`. OpenAlex: a fake work body `{"ids":{"doi":…}, "is_retracted": true}` → signal
  `status="retracted"`; `is_retracted` false/absent → None. Run → FAIL.

- [ ] **Step 5 — checker impls.** `CrossrefClient.lookup_retraction(conn, doi)` — reuse the cache/fetch of
  `resolve_doi`, read the **raw** `response_json` `message` (verify the field name against a real cached response
  during the build — `update-to` vs `relation`; support both keys defensively), map type→status
  (`retraction`/`withdrawal`→retracted, `correction`/`erratum`→correction, `expression_of_concern`→concern),
  build `notice_url=https://doi.org/<notice_doi>`. `OpenAlexClient.lookup_retraction(conn, ref)` — fetch the work
  (reuse `_fetch_work`), read `is_retracted`. Add thin checker wrappers in `methods/retraction.py` that build the
  `PaperRef`/doi from the paper mapping and call these. Keep each adapter < 600 (check `wc -l`; if near, put the
  parse helper in a sibling module). Run `pytest tests/test_retraction.py -q` → all PASS.

- [ ] **Step 6 — ruff + commit.** `ruff check --fix . && ruff format app tests integrations`;
  `git commit -m "feat(retraction): multi-source detect/merge/apply core + checkers (inc 131 t1)"`.

## Task 2 — endpoints, batch job, library filter

**Files:** extend `app/backend/api/routers/methods.py`, `app/backend/api/app.py`,
`app/backend/persistence/repository.py`; extend `tests/test_retraction.py` + `tests/test_health.py`.

**Interfaces produced:** `GET /papers/{paper_id}/retraction` (sync, runs detect+apply, returns the outcome),
`POST /methods/retraction/run` + `GET /methods/retraction/run/{job_id}` (async batch), `GET
/methods/retraction/summary` (`{retracted: N}`), `GET /papers?signal=retraction-retracted` (filter).

- [ ] **Step 1 — failing endpoint tests.** Seed two papers (one whose injected checkers flag retracted, one
  clean) — inject the checkers via `create_app(...)` or `api.state` (mirror how statcheck/generators are
  injected; add a `retraction_checkers` slot on `api.state`, defaulting to the real Crossref+OpenAlex wrappers).
  Assert: per-paper GET returns `status_kind` + persists; batch run → job completes, the retracted paper has the
  FACT + signal, summary `retracted==1`; `GET /papers?signal=retraction-retracted` returns only the retracted
  paper. Route-surface additions in `test_health.py` (`/papers/{paper_id}/retraction`,
  `/methods/retraction/run/{job_id}`, `/methods/retraction/summary` reads; `/methods/retraction/run` POST). FAIL.

- [ ] **Step 2 — `SIGNAL_FILTERS` + app state.** Add `"retraction-retracted": ("retraction", "retracted")` to
  `repository.SIGNAL_FILTERS`. In `app.py`: `api.state.retraction_jobs = JobStore[...]()` +
  `api.state.retraction_checkers = [crossref_retraction_checker, openalex_retraction_checker]` (overridable in
  tests). Run → filter test passes.

- [ ] **Step 3 — router handlers in `methods.py`.** Pydantic models (`RetractionOutcomeResponse`,
  `RetractionRunResponse`, `RetractionSummary`); the 3 endpoints + `_retraction_run_job` (over
  `list_live_paper_ids`, per-paper `detect_retraction(conn, paper, checkers=api.state.retraction_checkers)` +
  `apply_retraction`). Reuse the statcheck batch shape verbatim. Run `pytest tests/test_retraction.py
  tests/test_health.py -q` → PASS. **Check `wc -l methods.py`** — if > 560, extract `routers/retraction.py`
  (register in app.py) and move the retraction handlers there; re-run.

- [ ] **Step 4 — ruff + commit.** `git commit -m "feat(retraction): per-paper + batch endpoints + Retracted filter (inc 131 t2)"`.

## Task 3 — frontend: retraction-aware FactMark, status line, header chip + filter

**Files:** extend `app/frontend/js/08_methods_findings.jsx`, `10_pdf_layer.jsx`, `40_app.jsx`, `styles.css`;
rebuild `callosum-app.html`.

- [ ] **Step 1 — retraction-aware FactMark + Review status line** (`08_methods_findings.jsx`). When
  `finding.source === "retraction"`: render `.fact-mark.retraction` showing the status label (Retracted /
  Correction / Concern) + a **notice link** (`payload.notice_url`, `target="_blank" rel="noopener"`) + the
  `payload.sources` as a `title` tooltip. In `FindingsSection`, also fetch `GET /papers/{pid}/retraction` and
  render a subtle status line ("Retraction: checked — none found" / "unchecked — no DOI") so silence is honest
  even when there's no FACT.
- [ ] **Step 2 — library chip + filter** (`40_app.jsx` + `10_pdf_layer.jsx`). Mirror the inc-100 statcheck chip:
  a `retractionFlagged` state fetched from `GET /methods/retraction/summary` (refetched on mount + after a batch
  run); a **"⚠ N retracted"** header chip → sets the `signal=retraction-retracted` library view (mirror
  `showStatcheckFlagged` → `libraryNeedsReview`-style view-state) + a non-accusatory banner. Add the batch-run
  trigger to the METHODS Review section or a Settings entry (a "Check all papers for retractions" button calling
  `POST /methods/retraction/run`, mirroring the statcheck batch UI in `06_methods_statcheck.jsx`).
- [ ] **Step 3 — CSS** (`styles.css`, tokens only — read DESIGN.md): `.fact-mark.retraction` (uses `--flag`/
  `--danger` per the status; retraction = `--danger` red, correction/concern = `--flag` amber), `.retraction-status`
  (muted line), reuse the inc-100 chip class for the header chip + the existing filter-banner recipe.
- [ ] **Step 4 — build + assembly.** `python tools/build_frontend.py` + `pytest tests/test_frontend_assembly.py -q`.
- [ ] **Step 5 — commit.** `git commit -m "feat(retraction): FactMark + status line + Retracted chip/filter (inc 131 t3)"`.

## Task 4 — gates, QA, docs, verify, push

- [ ] **Step 1 — security audit** `.claude/security-audits/2026-06-26_retraction.md`: input validation (DOI
  normalize, response-shape guards on the raw Crossref/OpenAlex bodies), SSRF (fixed hosts via the existing
  adapters; notice_url derived only as `https://doi.org/<doi>`, never a fetched arbitrary URL), no library-text
  egress, fail-closed (a source error → skip, never 500), resource caps (batch bounded by library size), supply
  chain (no new dependency). End **PASS**.
- [ ] **Step 2 — Principles gate** writeup (into the increment notes): aligned per the design's invariants;
  declined the author-reputation + unchecked-as-clean easy paths.
- [ ] **Step 3 — QA route** `.claude/qa-routes/route_39_retraction.md` (assert: FACT-not-candidate, silence≠clean
  [checked-clean vs unchecked], no-accusation, evidence-carried [sources + notice link], chip-is-a-filter-not-a-
  verdict, 0 genai). `python tools/qa/build_surface_map.py extract && check` → 0 uncovered (add the new API + FE
  surfaces; fold any stray FE into the route).
- [ ] **Step 4 — headed verify (no egress, injected fake checkers)** `.local/visual/drive_inc131_retraction.py`:
  seed a copy DB, set `api.state.retraction_checkers` to fakes flagging paper A retracted / B clean / C no-DOI
  (or pre-seed the findings+signals directly + drive the read surfaces). Confirm: A shows ◆ fact + the retraction
  FactMark with a notice link; chip "1 retracted"; filter narrows to A; B shows "checked · none found"; C shows
  "unchecked — no DOI". 0 console/page errors, 0 genai.
- [ ] **Step 5 — docs.** `INCREMENT-131-NOTES.md`; `changes.md` (move HELP-DOCS-SYNCED → 131 if the help corpus
  is touched); help corpus "Retraction checks" section; `RECOVERY-LOG.md`; CLAUDE footer + top status line +
  layout enums (`routers`/`methods`/`integrations` if files added); `DESIGN.md` (the retraction FactMark recipe);
  backlog #31/#19 reconciliation (SP1 done; SP2 = RW DB next).
- [ ] **Step 6 — full gate + push.** `ruff check . && ruff format --check .`; full `pytest -q` (green);
  `git commit` the docs/gates; `git push origin main`; watch CI green.

## Critical files
- **New:** `app/backend/methods/retraction.py`, `tests/test_retraction.py`,
  `.claude/security-audits/2026-06-26_retraction.md`, `.claude/qa-routes/route_39_retraction.md`,
  `.local/visual/drive_inc131_retraction.py`, `INCREMENT-131-NOTES.md` (+ maybe `routers/retraction.py` if methods.py crosses the cap).
- **Modify:** `integrations/crossref/adapter.py`, `integrations/openalex/adapter.py`,
  `app/backend/persistence/signals_repo.py`, `repository.py`, `app/backend/api/routers/methods.py`, `app.py`,
  `app/frontend/js/{08_methods_findings,10_pdf_layer,40_app}.jsx`, `styles.css`, `tests/test_health.py`,
  docs (CLAUDE/changes/RECOVERY/backlog/DESIGN/help).
- **Reuse:** `findings_repo.upsert_findings`, `signals_repo`/`store_statcheck` pattern, `SIGNAL_FILTERS`, the
  statcheck batch job + JobStore, the inc-100 chip, the inc-130 FactMark, `CrossrefClient.resolve_doi` +
  `external_api_cache`, `OpenAlexClient._fetch_work`/`_work_from_body`.

## Build-time verifications to NOT skip
- **Verify the real Crossref retraction field shape** against an actual cached `response_json` before trusting
  `update-to` (the future-track flagged the CSL projection "may not survive"). Support both `update-to` and
  `relation` defensively.
- **Confirm OpenAlex `is_retracted`** is present on the work body the adapter fetches.
