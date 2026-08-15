# Increment 479 — GROBID section-scoping closes backlog #30 (Task 12: QA route, security audit, housekeeping)

## Implemented

The final task of a 12-task implementation plan
(`.superpowers/sdd/2026-08-13_grobid-section-scoping-implementation-plan/`) that closes backlog #30's last open
piece — Stage-4 section-scoping for Suggest-Citation. Tasks 1-11 (already committed in this worktree's history,
`3dccbbf`/`4f38aa2`/`bc6a169` etc.) built:

- **Baseline section-aware retrieval (Tasks 1-3, no GROBID dependency):** `app/backend/citations/
  section_scope.py` — `expected_section_family` classifies the draft's current heading into callosum's existing
  canonical section-family taxonomy (`pdf_processing/sections.py`); `candidate_section_family` looks up a
  candidate chunk's own family; `partition_by_phase` reorders (never filters) candidates so same-family matches
  lead, disclosing a `search_phase` flag rather than silently re-ranking. Wired into `suggest_citations` +
  `POST /citations/suggest`, and the LibreOffice adapter now passes the draft's current heading through.
- **GROBID HTTP client + TEI-XML parser (Tasks 4-6):** `integrations/grobid/client.py` posts a PDF to a
  user-configured GROBID server's `processFulltextDocument` endpoint (multipart `teiCoordinates=div,head,p` —
  a real bug, first tried as a query param, fixed before ship) and returns the raw TEI-XML.
  `integrations/grobid/tei_parse.py` parses it with a hardened DOCTYPE/NUL/UTF-8 guard closing a genuine
  XXE/entity-expansion gap (see Key technical detail). `integrations/grobid/section_classify.py` reuses the
  same taxonomy as the baseline (Task 1) rather than inventing a second one.
- **Schema + orchestration (Tasks 7-8):** `paper_sections` + `chunks.grobid_section_id` (migration
  `alembic/versions/0074_paper_sections.py`, needed `op.batch_alter_table` for SQLite's `ForeignKey`-add
  constraint). `app/backend/grobid_pipeline.py::parse_paper_structure` maps GROBID's section bounding boxes onto
  callosum's existing PyMuPDF chunk bboxes by real coordinate overlap (never fuzzy text matching); the
  pre-existing heuristic `chunks.section` column is never written by this pipeline.
- **Settings, jobs, endpoints (Task 9):** `app/backend/app_settings.py::set_grobid_url`/`stored_grobid_url` (a
  plain non-secret preference, mirrors `local_base_url`); `app/backend/api/routers/grobid.py` — 7 endpoints
  (`GET /grobid/status`, `POST /grobid/settings`, `POST /grobid/test-connection`,
  `POST /grobid/papers/{id}/parse` + its poll, `POST /grobid/library/parse` + its poll), all routed through the
  new `grobid_parse_jobs` `JobStore`.
- **Provenance preference (Task 10):** `candidate_section_family` extended to prefer a mapped GROBID section
  over the heuristic when present — strict either/or, never blended — with **zero changes** needed at any
  Suggest-Citation call site, confirming Task 1's interface design held under extension.
- **UI (Task 11):** `GrobidSettings` (`app/frontend/js/35e_maintenance.jsx`) — URL field, test-connection ping,
  bulk "Parse structure for library" action with a `managedBy="backend-job"` `ProgressBar`.
  `GrobidParseRow` (`app/frontend/js/25a_detail_actions.jsx`) — the per-paper "Parse document structure…"
  action, shown whenever a paper has a local PDF regardless of chunk state (so it can appear alongside either
  the OCR row or the Reprocess-PDF-text button).

**This task (12) added:**

- `.claude/qa-routes/route_91_grobid_document_structure.md` — the QA route covering all 7 `/grobid/*`
  endpoints plus the Settings UI and per-paper parse action, asserting the loopback/non-loopback egress split,
  the unconfigured-fails-closed 409, the never-fabricate-a-mapping honesty discipline, and the Status-popover
  findability + correct compute-kind label ("Local processing + self-hosted GROBID"). `python tools/qa/
  build_surface_map.py check` now reports **0 uncovered API surfaces** (423/423, was 416/423 before this route)
  and 0 uncovered frontend surfaces.
- `.claude/security-audits/2026-08-15_grobid-integration.md` — covers the egress-gate ordering (re-verified
  the 403-before-404 precedence directly), the DOCTYPE/XXE guard's completeness (re-ran both known bypass
  shapes against the current code, confirmed both closed, traced every call path into `ET.fromstring` to
  confirm the guard is unconditional), the `/grobid/test-connection` no-egress-gate design choice (reviewed and
  judged a correct, narrower-than-`/settings/test-key` reading of invariant #3, not an oversight), and one real,
  disclosed, accepted-risk finding: no explicit response-size cap on the GROBID TEI-XML response (matches this
  codebase's existing posture for every comparable external-response path; the threat model is
  self-inflicted — the user's own configured server — not a remote attacker). **Security Audit: PASS** (one
  disclosed, accepted low-severity risk).
- A genuine, live, end-to-end smoke test (see Manual verification script) closing Task 8's disclosed deferred
  gap — real coordinate-overlap mapping had never been proven against a real GROBID response + real PyMuPDF
  chunks on the same live PDF before this task, only faked-client unit tests.
- `.claude/CLAUDE.md` — bumped to Increment 479, updated pytest count, added a narrative paragraph for the
  whole GROBID/section-scoping feature.
- `.claude/docs/INCREMENT-BACKLOG.md` — removed backlog #30's open entry entirely (it's fully closed now); also
  fixed a now-dangling cross-reference in #37's entry (which named #30's section-scoping as its own blocking
  dependency — updated to say that infra has now shipped and #37's analytic-flexibility candidate is unblocked,
  not attempted here).
- `.claude/docs/INCREMENT-BACKLOG-DONE.md` — appended one compressed closure line for #30's Stage-4
  section-scoping, and removed the now-stale "remains open" pointer from the prior partial #30 DONE entry.

## Key technical detail

**The coordinate-overlap math.** `_bboxes_overlap` (`grobid_pipeline.py`) compares two independently-produced
bbox representations that use *different* coordinate shapes for the same page: GROBID's own `@coords` attribute
is `page,x,y,width,height` (parsed by `tei_parse.py::_parse_coords`, semicolon-separated for multi-region
spans), while callosum's existing `chunks.bbox_json` (written by PyMuPDF at ingest time,
`pdf_processing/extraction.py::_rect_to_dict`) is corner-coordinate `{"page","x0","y0","x1","y1"}`. Both were
independently confirmed (during this plan's Task 4/8 work, and re-confirmed live against a real GROBID
response in this task) to already share the same coordinate system — `pdf-points-top-left`, no y-flip or scale
transform needed — so the overlap test is a plain axis-aligned-rectangle intersection after converting GROBID's
`x,y,w,h` to its own `x1,y1` corner. A chunk maps to the **first** span it overlaps (spans shouldn't overlap
each other in well-formed TEI output); a chunk with no overlapping span keeps `grobid_section_id` `NULL` —
never a guessed nearest-section fallback.

**The provenance-preference rule (Task 10) is strict either/or, verified against real data in this task, not
just Task 10's faked-client tests.** `candidate_section_family` does one `outerjoin` between `chunks` and
`paper_sections` on `grobid_section_id` and branches: a non-null `section_kind` from that join wins outright
(`source="grobid"`); otherwise the pre-existing heuristic `chunks.section` column is used
(`source="heuristic"`); otherwise `(None, "none")`. The two data sources never blend for one chunk. Verified
directly against the live smoke-test database (see below): chunks GROBID mapped correctly report `"grobid"`
provenance with the right family; chunks GROBID left unmapped but the heuristic had already tagged correctly
report `"heuristic"`; the handful of front-matter/title-page chunks neither system recognized correctly report
`(None, "none")` — never a fabricated match.

**The DOCTYPE/NUL/UTF-8 XXE guard runs on every path into `ET.fromstring`, confirmed by tracing every caller.**
`parse_tei()` is the sole production entry point that reaches `ET.fromstring`, and it unconditionally calls
`_decode_and_reject_doctype` first — there is no second, unguarded call site anywhere in the codebase. The
guard strictly UTF-8-decodes the raw bytes (rejecting any BOM'd UTF-16/UTF-32 payload outright, since none of
their lead bytes are valid UTF-8), then rejects any embedded NUL (closing a deeper, no-BOM UTF-16/UTF-32
bypass a Task 5 code review caught — interleaved NUL bytes survive UTF-8 "decoding" as literal NUL codepoints
and were empirically confirmed to still let `ET.fromstring` parse + expand entities), then rejects any
`<!DOCTYPE` substring — closing the entire XXE/entity-expansion class (GROBID's real output never has a
DOCTYPE) rather than patching individual bypass shapes. Re-verified in this task's security audit by rerunning
both known bypass payloads against the current code.

## Manual verification script

**Live, real, end-to-end GROBID smoke test** (closes Task 8's disclosed deferred verification gap — real
coordinate-overlap correctness against a real GROBID response + real PyMuPDF chunks on the same live PDF had
never been tested before, only faked-client unit tests):

1. Confirmed a real GROBID 0.8.1 Docker container was already running: `curl http://localhost:8070/api/isalive`
   → `true`, HTTP 200.
2. Downloaded the exact same open-access source article the Task 5 committed fixture
   (`tests/fixtures/grobid/sample_fulltext.tei.xml`) was generated from — PLOS ONE, DOI
   `10.1371/journal.pone.0299939`, CC BY 4.0 — directly from `journals.plos.org` (a real 17-page, ~1MB PDF, not
   reused/committed anywhere in the repo).
3. Created an isolated scratch DB (`grobid-smoke/smoke.sqlite`), ran `alembic upgrade head` against it
   (confirmed clean through `0074_paper_sections`), and started the real backend
   (`uvicorn app.backend.api.app:app`) on a free local port pointed at that DB — a genuinely separate instance
   from any real library.
4. `POST /library/scan` against a scratch folder containing only that PDF → the paper was added and fully
   chunked (**229 real chunks** from real PyMuPDF extraction, correct title/authors/venue parsed from the PDF
   itself, `chunk_count: 229`).
5. `POST /grobid/settings {"url": "http://localhost:8070"}` → `configured:true`. `POST /grobid/test-connection`
   → `{"ok": true, "detail": "GROBID is reachable."}` (a real ping against the real container, not mocked).
6. `POST /grobid/papers/1/parse` → job started, polled to completion:
   **`{"sections_found": 28, "chunks_mapped": 48}`** — a real, non-trivial, non-zero mapping result.
7. Queried the scratch DB directly. `paper_sections` held 28 real rows with verbatim GROBID-extracted titles
   matching the actual article structure (`Introduction`, `Material and methods` → `Participants`/
   `Measurements`/`Statistical analysis` (correctly classified `section_kind="methods"`),
   `Results` → `Sample characteristics`/`Local functional connectivity`/`Global functional connectivity`,
   `Discussion`, `Conclusion` — with unrecognized subsection titles like `"Musical activity and late-life
   cognition"` correctly getting `section_kind=NULL`, an honest "unrecognized," not a wrong guess).
   Spot-checked several of the 48 mapped chunks: a chunk whose text begins "We assessed 130 cognitively
   unimpaired participants…" mapped to the real `Methods` section; a chunk beginning "Older participants with
   lifetime musical activity showed significantly higher…" mapped to `Results`; a chunk beginning "We show that
   playing a musical instrument during life relates to…" mapped to `Conclusion` — every spot-check was
   semantically correct, not just structurally non-null.
8. Confirmed the pre-existing heuristic `chunks.section` column was independently populated (212 of 229 chunks,
   e.g. 38 `methods`/29 `discussion`/23 `results`/92 `references`) by the ordinary ingest pipeline and
   **completely untouched** by the GROBID parse — direct DB query, not inferred.
9. Called `candidate_section_family` directly against the live scratch DB for both mapped and unmapped chunk
   ids: mapped chunks (23/24/26) correctly returned `("methods", "grobid")`/`("results", "grobid")`/
   `("discussion", "grobid")`; unmapped-by-GROBID-but-heuristic-tagged chunks (22/45/46) correctly fell back to
   `("methods", "heuristic")`; front-matter chunks (1/2, title/author-list boilerplate neither system
   recognizes) correctly returned `(None, "none")` — the exact strict-either/or, never-fabricated contract Task
   10 designed, now proven against real independent data.
10. Cleanly stopped the test server; no writes ever touched the real library or `validation.sqlite`.

**Result: no bug found in Tasks 5-10's logic.** This closes Task 8's own disclosed deferred item with a
genuine, positive, real-data confirmation rather than leaving it open indefinitely.

## Pytest

Targeted (this plan's own files): `pytest tests/test_grobid_client.py tests/test_grobid_tei_parse.py
tests/test_grobid_section_classify.py tests/test_grobid_pipeline.py tests/test_grobid_endpoints.py
tests/test_section_scope.py tests/test_citations_suggest.py tests/test_libreoffice_adapter.py
tests/test_migrations.py tests/test_frontend_assembly.py -q` — **320 passed** in 123s.

Full suite: `pytest -n 4 -q` — **2222 passed, 1 skipped in 1638.45s (0:27:18)**, exit code 0 (up from the
inc-478 baseline of 2202 passed recorded in CLAUDE.md — the increase reflects this whole 12-task plan's own new
tests across `test_grobid_client.py`/`test_grobid_tei_parse.py`/`test_grobid_section_classify.py`/
`test_grobid_pipeline.py`/`test_grobid_endpoints.py`/`test_section_scope.py` plus extensions to
`test_citations_suggest.py`/`test_libreoffice_adapter.py`/`test_migrations.py`). The one skip is a pre-existing,
environment-conditional skip in `tests/test_wip_api.py:250` ("symlink creation not permitted in this test
environment") — unrelated to this plan; inc 478 recorded 2 skips at the same conditional-skip site, so the
count is environment-state variance, not a regression this task introduced or investigated further. See this
task's own report (`.superpowers/sdd/2026-08-13_grobid-section-scoping-implementation-plan/task-12-report.md`)
for the raw command output.

- `ruff format` / `ruff check` — scoped to every file this whole 12-task plan touched (not repo-wide, per the
  standing instruction against a repo-wide reformat clobbering a concurrent session's work) — clean.
- `python tools/check_line_budget.py` — clean on every file this plan touches.
- `python tools/qa/build_surface_map.py check` — **0 uncovered API surfaces (423/423), 0 uncovered frontend
  surfaces (1737/1737)** after adding `route_91_grobid_document_structure.md` (was 416/423 API before).
