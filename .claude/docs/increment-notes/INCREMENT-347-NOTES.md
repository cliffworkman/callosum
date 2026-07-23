# Increment 347 — Workbench batch candidate drafting (backlog #36)

## Context
The assisted-extraction funnel already drafts one paper-linked row at a time: a provider proposes values for
empty structured cells, local code anchors each quote/value, and every proposal remains isolated from trusted
cells/conversion/exports until a human accepts it. Backlog #36's next UX step was batch **Draft all un-filled
rows**, explicitly retaining the same per-candidate review gate and never adding bulk auto-accept.

## Implemented
- **Draft all un-filled rows** appears in an open Meta-Analyze project's header beside Convert all.
- Eligibility is deliberately conservative: a row must link to a library paper, have at least one genuinely
  empty number/choice cell, and have no existing live candidates. Rows already awaiting review are skipped rather
  than silently re-drafted/replaced; unlinked/free-text-only/fully-filled rows are not sent.
- The frontend invokes the unchanged `/workbench/rows/{id}/propose` endpoint **sequentially**, bounding provider
  load and preserving the existing endpoint's egress gate, empty-field short circuit, local anchoring, and
  candidate-only persistence.
- A determinate progress bar shows rows completed / total. Row-level errors do not abort later rows; the final
  result reports candidate and row coverage, names up to four failed rows (+ overflow count), and separately
  reports long-PDF truncation.
- There is no batch accept mechanism or accept call in the handler. Every candidate remains an amber evidence
  card with individual accept/edit/reject and never enters a trusted cell, Convert, or an export beforehand.
- While any draft request is active, project navigation and other draft controls are disabled to prevent
  overlapping requests. Async state updates also tolerate the project view no longer being mounted.

## Experience-pass fix
The headed mobile pass exposed a pre-existing Workbench defect: at 375px, the table itself had a real 145px
height but `.wb-gridwrap` (a child of the flex-column pane) shrank to **0px**, clipping every row. The existing QA
contract already said the grid should remain visible and scroll horizontally. Added `flex: 0 0 auto` to the
wrapper; re-verification measured wrapper/table height 145px, internal width 477px, no whole-page overflow.

## Verification
- `uv run pytest tests/test_frontend_assembly.py -q` — **47 passed** after rebuilding `callosum-app.html`.
  The new static regression pins eligibility's existing-candidate exclusion, sequential await, determinate
  progress, absence of an accept call, and the mobile wrapper rule.
- `python tools/qa/build_surface_map.py check` — **260/260 API covered**; frontend checklist
  **1186/1207 covered**, with the same 21 pre-existing uncovered controls in `10e_tagspanel.jsx` and
  `35a_mypubs.jsx`; the changed Workbench files remain covered by route 65.
- Headed disposable-fixture pass, AI off: desktop and 375×812, control visible and honestly disabled, two linked
  per-row draft controls disabled, no page overflow, zero console errors, no provider/genai request.
- Headed intercepted-provider behavior pass: draft row 1 individually, then batch rows 2–3 with row 2 forced to
  fail. Observed call order `[row1, row2, row3]`, row 1 skipped by batch, maximum concurrency **1**, row 3 still
  completed, **2 candidate cards**, **0 trusted non-empty cells**, **0 accept calls**, and the failed paper named.
- `uv run pytest -n 4 -q` — **1415 passed, 1 skipped** in 599.73s.
- `uv run ruff check .` / `uv run ruff format --check .` — clean (**478 files formatted**).
- `python tools/check_line_budget.py` — clean (**351 application-source files** within cap).

## Gates
- **Principles / A-A:** aligned and unchanged. This expands the candidate funnel's reach, not its authority:
  proposals remain evidence-carried, locally anchored, non-verdict candidates; no score, auto-accept, or hidden
  aggregation was added.
- **Security:** no new endpoint/input/host/dependency/persistence or egress path. The batch composes the existing
  audited per-row endpoint, which retains its provider/egress gate.
- **QA:** route 65 now asserts batch-propose-only, sequentiality, skip-existing, partial-failure continuation,
  progress, candidate isolation, and AI-off disabled behavior.
- **Design:** no new visual recipe. Header action uses `.btn-link`; progress reuses `ProgressBar`; failure uses the
  existing amber Workbench note. The one CSS change repairs the existing internal-scroll recipe with no new token.
- **Experience pass (meta-analysis extractor assembling several studies):** the user can start all untouched rows
  from the project header, see that work is progressing, and receives usable partial output instead of losing the
  whole run to one bad paper. Existing candidates are never overwritten and the next step remains visibly
  per-candidate review. The mobile clipping found during this pass was fixed in the same increment.

## Next
Backlog #36's remaining near-term slice is retrieval-narrowed extraction text: retrieve top relevant chunks from
the requested field labels rather than sending the first 50k characters. Treat that as its own backend/retrieval
increment with hermetic ranking tests and explicit truncation/cost reporting.
