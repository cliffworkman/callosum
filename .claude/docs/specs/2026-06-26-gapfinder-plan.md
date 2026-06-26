# Gap-finder — implementation plan (increment 135)

**Goal:** A library-wide backward citation gap-finder — works cited by ≥N of your papers that you don't have →
Add/Dismiss candidates. Design: `2026-06-26-gapfinder-design.md`.

**Global constraints:** bound-param SQL; files < 600; reuse the OpenAlex adapter + `find_existing_paper_by_identity`
+ `import_citing_work` flow + the p-curve async-job/JobStore + `26_wanted.jsx` modal; injected OpenAlex client →
hermetic; migration head derived by tests (inc 99); public OpenAlex metadata (not Gemini gate); fail-closed. TDD;
commit per task; ruff + the **e2e suite** before push; CI green.

---

## Task 1 — OpenAlex adapter extensions + the gap computation (no network)

**Files:** `integrations/openalex/adapter.py`; `app/backend/clustering/gapfinder.py` (new); `tests/test_gapfinder.py` (new).

**Interfaces produced:** `OpenAlexClient.fetch_referenced_works(conn, ref) -> list[str]`,
`OpenAlexClient.fetch_work_meta(conn, work_id) -> dict | None`; `gapfinder.GapCandidate`,
`gapfinder.compute_gaps(conn, *, openalex_client, dismissed, min_citations=3, max_candidates=50) -> tuple[list[GapCandidate], dict]`
(the dict = `{checked, total, note}` coverage info).

- [ ] **Step 1 — failing tests** (`tests/test_gapfinder.py`): `fetch_referenced_works` with a fake fetcher whose
  work body has `referenced_works: ["https://openalex.org/W1","https://openalex.org/W2"]` → `["W1","W2"]`; no
  field → `[]`. `fetch_work_meta` with a fake `/works/W1` body → `{openalex_work_id:"W1", doi, title, authors,
  year}`; a bad id (`"x"`) → None (no fetch). `compute_gaps`: 3 papers (P1,P2 cite W1; P1 cites W2), min=2 →
  one candidate W1 with `cited_by_in_library==2`; a candidate already in library (its DOI seeded) → excluded; a
  dismissed W1 → excluded; the coverage dict reports `checked`/`total`. Use a fake `OpenAlexClient` (a small
  stub with the two methods) + seed papers with DOIs via `create_paper`. Run → FAIL.

- [ ] **Step 2 — adapter methods.** `fetch_referenced_works`: `work = self._fetch_work(conn, ref); ids = [u.rsplit("/",1)[-1] for u in (work or {}).get("referenced_works", []) if isinstance(u, str)][:MAX_REFERENCED]`.
  `fetch_work_meta`: validate `re.fullmatch(r"W\d+", work_id)`; cached fetch of `/W<id>` (cache key `work:<id>`);
  parse to the meta dict (reuse the `_work_from_body` body + a small author/doi/title/year extractor). Both
  fail-closed. Keep `adapter.py` < 600 (currently ~217 → fine).

- [ ] **Step 3 — `gapfinder.py`.** `GapCandidate` (frozen dataclass) + `compute_gaps` (the aggregation: a
  `dict[str, set[int]]` of ref-id → citing paper ids over live papers with a DOI; filter ≥ min; for the top
  `3*max_candidates` by count, `fetch_work_meta` → skip no-DOI / in-library / dismissed; return up to
  max_candidates sorted by count desc + the coverage dict). Run `pytest tests/test_gapfinder.py -q` → PASS.

- [ ] **Step 4 — ruff + commit.** `git commit -m "feat(gaps): OpenAlex referenced-works + work-meta + compute_gaps (inc 135 t1)"`.

## Task 2 — dismissals migration + endpoints + add/dismiss

**Files:** `app/backend/persistence/schema.py` + `alembic/versions/0018_profile_dismissed_gaps.py` (new),
`persistence/profile_repo.py`, `app/backend/api/routers/gaps.py` (new), `app.py`; `tests/test_gapfinder.py`
(+endpoints) + `tests/test_health.py`.

- [ ] **Step 1 — failing tests.** `profile_repo.dismiss_gap` then `dismissed_gaps` returns the set; the gap job
  `POST /gaps/find` (inject `app.state.openalex_client` = a fake) → a candidate; `POST /gaps/add` → in-library +
  idempotent; `POST /gaps/dismiss` → excluded on the next `find`. Route-surface in `test_health.py`
  (`/gaps/find/{job_id}` read; `/gaps/find`, `/gaps/add`, `/gaps/dismiss` POST). FAIL.

- [ ] **Step 2 — schema + migration.** Add `dismissed_gap_works` (JSON, nullable) to the `profile` Table; create
  `0018_profile_dismissed_gaps.py` (guarded `add_column`, `down_revision="0017_retraction_records"`; SQLite — use
  `op.add_column` guarded by an inspector column check, mirroring the additive-column migrations 0010-0013).

- [ ] **Step 3 — profile_repo.** `dismiss_gap(conn, key)` (normalize → append to the JSON list, sorted, dedup) +
  `dismissed_gaps(conn) -> set[str]` (read the list). Mirror `dismiss_work`/`dismissed` (inc 85/92).

- [ ] **Step 4 — router + app state.** `routers/gaps.py`: Pydantic models (`GapCandidateResponse`, `GapsResponse`
  with `candidates`+`checked`+`total`+`note`, `GapRunResponse`, `GapAddRequest`, `GapDismissRequest`); the async
  `POST/GET /gaps/find` (`_run_gap_job` calls `compute_gaps(conn, openalex_client=app.state.openalex_client or
  OpenAlexClient(), dismissed=dismissed_gaps(conn))`); `POST /gaps/add` (reuse `import_citing_work` — it already
  does dedup + metadata-only + enrich; pass `imported_source` via a new arg or a thin wrapper `import_gap_work`)
  ; `POST /gaps/dismiss`. `app.py`: `api.state.gap_jobs = JobStore()` + include `gaps.router`. Run
  `pytest tests/test_gapfinder.py tests/test_health.py -q` → PASS. **Check `import_citing_work`** — if it hardcodes
  `imported_source="citing-import"`, add an `imported_source` param (default keeps inc-119 behavior) so gaps use
  `"gap-import"`.

- [ ] **Step 5 — ruff + commit.** `git commit -m "feat(gaps): dismissals migration + find/add/dismiss endpoints (inc 135 t2)"`.

## Task 3 — frontend: Gaps button + modal

**Files:** `app/frontend/js/NN_gaps.jsx` (new — pick the next free chunk number after the mypubs chunks),
`10_pdf_layer.jsx` (the button) + `40_app.jsx` (the open state), `styles.css`; rebuild.

- [ ] **Step 1 — the modal** (`NN_gaps.jsx`, mirror `26_wanted.jsx`): a **Find gaps** button → POST `/gaps/find`
  + poll → the candidate list (each: **"cited by N of your papers"** + title · authors · year + **Add** /
  **Dismiss**); Add → POST `/gaps/add` (row → "in library"); Dismiss → POST `/gaps/dismiss` (row hidden); the
  **coverage caveat** + the "checked M of N papers" line + an honest empty state ("no gaps found — every work
  cited by ≥N of your papers is already in your library").
- [ ] **Step 2 — wire it** (`10_pdf_layer.jsx` a "Gaps" `.trash-toggle` button in the lib-head; `40_app.jsx`
  a `gapsOpen` state + render the modal). CSS (tokens; reuse the modal + list recipes).
- [ ] **Step 3 — build + assembly + e2e + commit.** `python tools/build_frontend.py`; `pytest
  tests/test_frontend_assembly.py -q`; `CALLOSUM_RUN_E2E=1 pytest tests/e2e -q`;
  `git commit -m "feat(gaps): Gaps button + discovery modal (inc 135 t3)"`.

## Task 4 — gates, QA, headed verify, docs, push

- [ ] **Step 1 — audit** `.claude/security-audits/2026-06-26_gapfinder.md`: the new OpenAlex fetches
  (`referenced_works` + by-id — fixed host, validated `W\d+`, cached, capped, fail-closed), input validation on
  add/dismiss (normalized DOI/id), dedup (no arbitrary minting), no Gemini egress, no PDF acquisition (OA-only
  lane untouched → no paywall circumvention), bound-param SQL, the additive migration. **PASS**.
- [ ] **Step 2 — Principles writeup** (notes): aligned (candidates-not-verdicts, evidence-carried "cited by N of
  *your* papers", coverage stated, no quality rank — declined the importance-leaderboard).
- [ ] **Step 3 — QA route** `.claude/qa-routes/route_41_gaps.md` (assert: candidates not verdicts; the count is
  "cited by N of *your* papers" not a quality rank; coverage caveat + "M of N" honesty; Add = metadata-only into
  the general library, PDF stays OA-lane; Dismiss persists; no genai). `build_surface_map.py extract && check` →
  0 uncovered.
- [ ] **Step 4 — headed verify (offline)** `.local/visual/drive_inc135_gaps.py`: inject `app.state.openalex_client`
  = a fake returning referenced_works + meta so `compute_gaps` yields ≥1 candidate → the Gaps modal lists "cited
  by N" → Add (→ in library) / Dismiss (→ hidden) + the coverage line. 0 console/page/genai.
- [ ] **Step 5 — docs.** `INCREMENT-135-NOTES.md`; `changes.md` (HELP-DOCS-SYNCED → 135); help corpus a "Finding
  gaps in your library" section; `RECOVERY-LOG.md`; CLAUDE footer + status + layout enums (`routers/gaps.py`,
  `clustering/gapfinder.py`, migration head 0018); backlog (the discovery/gapfinder track — v1 shipped). DESIGN
  note if CSS recipes added.
- [ ] **Step 6 — full gate + push.** `ruff check . && ruff format --check .`; full `pytest -q`; the **e2e suite**;
  commit docs; `git push origin main`; CI green.

## Critical files
- **New:** `app/backend/clustering/gapfinder.py`, `app/backend/api/routers/gaps.py`,
  `alembic/versions/0018_profile_dismissed_gaps.py`, `app/frontend/js/NN_gaps.jsx`, `tests/test_gapfinder.py`,
  `.claude/security-audits/2026-06-26_gapfinder.md`, `.claude/qa-routes/route_41_gaps.md`,
  `.local/visual/drive_inc135_gaps.py`, `INCREMENT-135-NOTES.md`.
- **Modify:** `integrations/openalex/adapter.py`, `persistence/profile_repo.py` + `schema.py`, `app.py`,
  `app/frontend/js/{10_pdf_layer,40_app}.jsx`, `styles.css`, `tests/test_health.py`, docs. Possibly a small
  `imported_source` param on `import_citing_work`.

## Watch
- The inc-132 e2e gotcha: any new `useEffect` must return undefined / a cleanup, never a Promise. Run the e2e
  suite locally before pushing.
