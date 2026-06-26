# Findings review facet — implementation plan (increment 133)

**Goal:** statcheck batch emits candidate findings + a unified "N to review" library chip/filter. Design:
`2026-06-26-findings-review-facet-design.md`.

**Global constraints:** bound-param SQL (rule #3); files < 600; reuse `upsert_findings` + the statcheck batch +
`librarySignalFilter` + the inc-100 chip; no new endpoint / migration / external fetch; local, no egress. TDD;
commit per task; ruff before push; CI green.

---

## Task 1 — backend: statcheck emits candidates + the `finding=needs-review` filter

**Files:** `app/backend/api/routers/methods.py`, `app/backend/persistence/repository.py`;
`tests/test_findings.py` (or a focused `tests/test_findings_review.py`) + `tests/test_statcheck.py`.

**Interfaces produced:** statcheck batch writes a `source="statcheck"` candidate; `list_papers(finding=…)` +
`FINDING_FILTERS = {"needs-review": ...}`; `GET /papers?finding=needs-review`.

- [ ] **Step 1 — failing tests.**
  - In `tests/test_statcheck.py` (the batch test): after `POST /methods/statcheck/run` over a seeded library
    with ≥1 flagged paper, assert the flagged paper has a `source="statcheck"` **candidate** in
    `get_paper_findings` (`kind=="candidate"`, `review_state=="unreviewed"`, payload `desc` contains
    "inconsistenc", `inconsistent`/`decision_errors` present, `page` set), and a clean paper has **no** statcheck
    finding. (Use the existing statcheck fixtures / seeded chunks that flag.)
  - A re-run after the user reviews the candidate (`set_review_state(..., "noted")`) with the same result →
    the candidate is **preserved** (still noted, not re-surfaced).
  - In `tests/test_findings_review.py` (new): `list_papers(conn, finding="needs-review")` returns only papers
    with an unreviewed candidate (seed via `upsert_findings`); a reviewed/`None` candidate is excluded; an
    unknown `finding` value → no filter; `GET /papers?finding=needs-review` via TestClient.
  Run → FAIL.

- [ ] **Step 2 — the filter.** In `repository.py`: import `paper_findings`; add `finding: str | None = None` to
  `list_papers`; `FINDING_FILTERS = {"needs-review": "unreviewed"}`; when `finding in FINDING_FILTERS`, add
  `papers.c.id.in_(select(paper_findings.c.paper_id).where(paper_findings.c.review_state == FINDING_FILTERS[finding]))`
  (bound; mirrors the SIGNAL_FILTERS block). Wire the `finding` query param on `GET /papers` (`routers/papers.py`
  — add the `finding` param alongside `signal`, pass through to `list_papers`).

- [ ] **Step 3 — statcheck emits the candidate.** In `_run_statcheck_all_job`: after `store_statcheck`, build the
  candidate when `report.inconsistent + report.decision_errors > 0`:
  ```python
  flagged = report.inconsistent + report.decision_errors
  page = next((r.page for r in report.results if r.consistency != "consistent" and r.page is not None), None)
  if flagged > 0:
      upsert_findings(conn, paper_id, "statcheck", [{"kind": "candidate", "tier": "primary", "payload": {
          "desc": f"{flagged} statistical reporting inconsistenc{'y' if flagged == 1 else 'ies'} (statcheck) — review",
          "inconsistent": report.inconsistent, "decision_errors": report.decision_errors,
          "checked": report.checked, "page": page}}])
  else:
      upsert_findings(conn, paper_id, "statcheck", [])
  ```
  Import `upsert_findings`. Run `pytest tests/test_statcheck.py tests/test_findings_review.py -q` → PASS.

- [ ] **Step 4 — ruff + commit.** `git commit -m "feat(findings): statcheck emits candidate findings + needs-review filter (inc 133 t1)"`.

## Task 2 — frontend: the unified "N to review" chip + filter

**Files:** `app/frontend/js/40_app.jsx`, `10_pdf_layer.jsx`; rebuild `callosum-app.html`.

- [ ] **Step 1 — 40_app.jsx.**
  - `const findingsToReview = useMemo(() => Object.values(findingsByPaper).filter(o => o.unreviewed_count > 0).length, [findingsByPaper]);`
  - `showFindingsToReview` = `setLibrarySignalFilter("needs-review")` + clear trash/axis/tag/needs-review/focus +
    `setSelectedLibraryIds(new Set())` + `setSettingsOpen(false)` + `setActiveTab("library")` + `setPage(0)`
    (clone `showStatcheckFlagged`).
  - `/papers` fetch: `if (librarySignalFilter === "needs-review") qs.set("finding", "needs-review"); else if (librarySignalFilter) qs.set("signal", librarySignalFilter);`
    and add `findingsRefresh` to that effect's dep array (re-narrow after a review).
  - `libraryProps`: add `findingsToReview, onShowFindingsToReview: showFindingsToReview`.
- [ ] **Step 2 — 10_pdf_layer.jsx.** Destructure `findingsToReview, onShowFindingsToReview`. Add a header chip
  (after the retraction chip): `{!trashView && findingsToReview > 0 && librarySignalFilter !== "needs-review" &&
    <button className="trash-toggle findings-chip" onClick={onShowFindingsToReview} title="Findings you haven't
    reviewed yet — open each paper's Review section">📋 {findingsToReview} to review</button>}`. Add a banner
  block for `librarySignalFilter === "needs-review"` ("Findings you haven't reviewed yet — open each paper's
  Review section to Confirm / Note." + clear).
- [ ] **Step 3 — CSS** (`styles.css`, tokens only): `.trash-toggle.findings-chip { color: var(--accent); font-weight: 600; }`
  (indigo = the review/provenance accent; not red/amber which are reserved).
- [ ] **Step 4 — build + assembly + commit.** `python tools/build_frontend.py` + `pytest tests/test_frontend_assembly.py -q`;
  `git commit -m "feat(findings): unified 'N to review' chip + filter (inc 133 t2)"`.

## Task 3 — gates, QA, headed verify, docs, push

- [ ] **Step 1 — Principles writeup** (into the notes): aligned (candidate = prompt-to-look, coexists with the
  fact signal; the facet is a work-state queue, not a rank; non-accusatory). No audit gate (no endpoint/fetch/
  migration).
- [ ] **Step 2 — QA.** Update `route_38_findings.md` (the review surface) + `route_33_methods_statcheck.md`
  (statcheck now also emits a candidate) to assert: statcheck candidate is reviewable + coexists with the
  signal; the "N to review" chip is a work-state filter not a rank; reviewing drops it from the queue.
  `build_surface_map.py extract && check` → 0 uncovered (the `finding` param + the chip are covered by the
  existing `/papers` + `10_pdf_layer.jsx` coverage; confirm).
- [ ] **Step 3 — headed verify (offline)** `.local/visual/drive_inc133_review.py`: seed a flagged statcheck
  candidate (via `upsert_findings`, or run the batch over the seeded renderable paper) → the "N to review" chip
  shows → click → filter narrows → open the paper → Review pane shows the statcheck **candidate** card → Confirm
  it → it drops from the chip + the filter view. 0 console/page/genai.
- [ ] **Step 4 — docs.** `INCREMENT-133-NOTES.md`; `changes.md` (HELP-DOCS-SYNCED → 133 if help touched);
  help corpus "Reviewing findings" gains a line about statcheck candidates + the "to review" queue; `RECOVERY-LOG.md`;
  CLAUDE footer + status (tests); backlog (the review-half item). DESIGN note for the chip color.
- [ ] **Step 5 — full gate + push.** `ruff check . && ruff format --check .`; full `pytest -q`; commit docs;
  `git push origin main`; CI green (incl. e2e).

## Critical files
- **Modify:** `app/backend/api/routers/methods.py` (statcheck batch), `repository.py` (the filter),
  `routers/papers.py` (the `finding` param), `app/frontend/js/{40_app,10_pdf_layer}.jsx`, `styles.css`,
  `tests/test_statcheck.py` + a new `tests/test_findings_review.py`, docs.
- **Reuse:** `findings_repo.upsert_findings` / `get_paper_findings` / `findings_overview`; the inc-130 FindingCard
  + per-card badge; the inc-97 SIGNAL_FILTERS block + the inc-100 chip pattern + `librarySignalFilter`.

## Watch
- The inc-95 e2e gotcha: a `useEffect` whose body returns a Promise becomes a bad cleanup (inc-132 reading-mode
  crash). Any new effect here must return undefined or a cleanup function — and run the **e2e suite locally**
  (`CALLOSUM_RUN_E2E=1 pytest tests/e2e -q`) before pushing.
