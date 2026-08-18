# Increment 481 — analytic-flexibility surfacing (backlog #37)

## Implemented

The analytic-flexibility surfacing feature: an egress-gated LLM proposes candidate analytic-decision points
from a paper's (Library) or manuscript's (WIP) methods-section text, every quote is anchored afterward
deterministically and locally, and candidates persist as reviewable findings on both surfaces. This is the 5th
Checklists-family tool and the first one that is LLM-assisted rather than deterministic/local.

- `app/backend/pdf_processing/quote_matching.py::anchor_quote` — a value-less, deterministic, local quote
  locator: given a PDF path and a quote, classifies the result as `exact` (real bbox rectangles), `region`
  (matched but no resolvable rectangles), or `unanchored` (not found) — never fabricates a location.
- `integrations/gemini/analytic_flexibility_assistant.py` — the egress-gated LLM assistant. Its prompt asks for
  a JSON array of `{category, quote}` objects, `category` restricted to a closed 5-value taxonomy
  (`exclusion-criteria`, `covariate-choice`, `test-selection`, `outcome-choice`, `other-branch-point`).
  `parse_proposals` defensively parses the untrusted model response: tolerates markdown fences and surrounding
  prose, drops any entry with an invalid category or a missing/blank quote (never coerces), caps quote length
  and candidate count, and yields `[]` on any parse failure rather than raising.
- `app/backend/citations/section_scope.py::paper_methods_text` (Library) — methods-section text assembly from
  a paper's chunks, GROBID-preferred with a heuristic fallback (reuses `candidate_section_family`, inc 479).
- `app/backend/wip/analytic_flexibility_text.py::wip_methods_text` (WIP) — the WIP-side equivalent, with a
  disclosed PDF-vs-non-PDF scoping asymmetry (see Key technical detail below).
- `app/backend/analytic_flexibility.py` + `POST /papers/{paper_id}/analytic-flexibility`
  (`app/backend/api/routers/analytic_flexibility.py`) — the Library orchestration module/endpoint. Egress is
  refused before any paper lookup; candidates persist into the existing `paper_findings` table as
  `kind="candidate", tier="speculative"`.
- `POST /wip/manuscripts/{manuscript_id}/checks/analytic-flexibility`
  (`app/backend/api/routers/wip_checks.py::analytic_flexibility_run`) — the WIP orchestration endpoint. Same
  egress-gate ordering; candidates persist into the existing `wip_findings` table via
  `store_analytic_flexibility_run` (`app/backend/persistence/wip_checks_repo.py`).
- `app/backend/api/routers/findings.py` — `GET /papers/{paper_id}/findings` gained an additive, optional
  `?source=` query parameter (e.g. `?source=analytic-flexibility`) so the Library panel can scope its own read
  without affecting any existing caller.
- `app/frontend/js/08n_methods_analytic_flexibility.jsx` (new) — the Library Methods → Checklists panel: a
  "Surface analytic-flexibility candidates" button (disabled until the egress-consent setting is confirmed on),
  candidates rendered as cards via the existing `FindingCard`, copy repeatedly disclaiming any aggregate/score.
- `app/frontend/js/10k_wip_checks.jsx`'s `WipAnalyticFlexibilitySection`/`WipAnalyticFlexibilityResult` — the
  WIP Checks-tab panel, reusing the shared `WipChecklistSection` shell every sibling tool already uses; renders
  the PDF-vs-non-PDF scoping-degrade caveat when `scoped=False`.
- `app/frontend/js/08x_methods_critical.jsx`'s `FindingCard` — fixed to read a candidate's real
  `payload.anchor_state` instead of a hardcoded `precision: "region"` (see Key technical detail).
- `app/frontend/js/04c_status.jsx` — both synchronous endpoints registered as tracked AI requests (invariant #5).
- `.claude/qa-routes/route_92_analytic_flexibility.md` — QA coverage for both API surfaces and all four new
  frontend chunks; `build_surface_map.py check` passes 0/0 uncovered.
- `.claude/security-audits/2026-08-17_analytic-flexibility-surfacing.md` — full threat review, PASS.

## Key technical detail

**The PDF-vs-non-PDF WIP methods-scoping asymmetry, and why it's a disclosed degrade rather than a fixed gap.**
Non-PDF WIP files (Markdown/DOCX/ODT/HTML/JATS-XML) carry a real per-block heading string in
`ContentBlock.section` (lifted from the source format's own heading markup), which `wip_methods_text` classifies
into the same canonical section-family taxonomy `citations/section_scope.py` already uses for the Library side —
real per-block scoping. PDF WIP files' raw blocks always carry `section=None`: PyMuPDF text blocks have no
per-block heading text to classify at all, unlike the Library-paper ingest pipeline, which runs a stateful
`SectionTracker` over PDF text as it chunks (a WIP manuscript's PDF is never run through that pipeline — it's a
draft, not an ingested library paper). Rather than inventing a fragile per-PDF-block heuristic to paper over
that real gap, `wip_methods_text` honestly degrades to "every block, capped at 20000 chars" and reports
`scoped=False`, which `WipAnalyticFlexibilityResult` renders as an explicit caveat ("This file type has no
per-block section scoping, so the whole manuscript text was searched rather than just its methods section") —
disclosed to the UI, not silently presented as equivalent to real section-scoping.

**The `unanchored`→`NULL` CHECK-constraint mapping.** `wip_findings.coordinate_precision` has a DB CHECK
constraint permitting only `NULL | 'exact' | 'region'` (`schema_wip_provenance.py`) — a legacy constraint this
feature didn't design and didn't touch. `anchor_quote` can produce a third real state, `unanchored` (quote not
found, or no PDF exists to search at all), which has no matching literal. `store_analytic_flexibility_run` maps
`anchor_state != "unanchored"` straight through and `"unanchored"` → `None` for the narrow column — but the
full, un-narrowed candidate dict (including the real `anchor_state` string) is written unmodified into the
sibling `details_json` column, so the fuller value stays inspectable one field over rather than being silently
lost. The Library side never hits this narrowing at all: `paper_findings` has no `coordinate_precision` column
— `anchor_state`/`page`/`bbox_json` all live inside its free-form `payload` JSON blob.

**Task 8's `FindingCard` fix, and why it was in-scope for this plan rather than a drive-by refactor.** Every
prior Checklists-family tool (statcheck, transparency, LMM, Bayes, meta-analysis) only ever produces `region`-
or `null`-precision evidence — none of them anchors a quote against a real PDF the way this feature's
`anchor_quote` does, so `FindingCard`'s pre-existing hardcoded `precision: "region"` in its "show in paper"
action was harmless for all of them. This feature is the first Checklists-family tool whose candidates can
carry a real `exact` anchor (a genuine bbox rectangle from `anchor_quote`), so the hardcoded value would have
silently understated its own best-case output — every "show in paper" click would have scrolled to the page
and shown an approximate-location note instead of drawing the precise highlight rectangle that was actually
available. Fixed by reading the candidate's real `payload.anchor_state` and passing through the matching
`bbox_json` only when it is `"exact"` — required by this feature's own correctness (coordinate-honesty
invariant #2 demands showing an exact match as exact, not understating it as region), not a bundled refactor.

## Manual verification script

No live browser session was run for this task (Task 12 is a docs/audit close-out task, not a UI-implementing
one) — this is the script a human should run to confirm the built feature end-to-end:

1. Start the app (`uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8888`) against a DB with at least
   one Library paper that has a PDF attachment with a real methods section, and confirm AI features / data-
   egress consent is enabled in Settings.
2. Open that paper, go to Methods → Checklists → Analytic flexibility, and click "Surface analytic-flexibility
   candidates." Confirm candidates render as individual cards (never a count, index, or aggregate score
   anywhere on the panel).
3. On a candidate whose payload shows `anchor_state: "exact"` (inspect via the network tab or the finding's own
   payload if a debug view is available), click "show in paper." Confirm the PDF viewer opens to the correct
   page and draws a real, precise bbox highlight rectangle — not just a page-level scroll.
4. On a candidate with `anchor_state: "region"` or `"unanchored"`, click "show in paper" (if a page number is
   present) and confirm it scrolls to the page with an approximate-location note, drawing no exact rectangle —
   the coordinate-honesty contract holding for both directions.
5. Switch to a WIP manuscript (Synthesize/Work → WIP) whose registered primary file is a PDF. Open its Checks
   tab, run "Analytic-flexibility surfacing," and confirm the result shows no PDF-scoping caveat if a real
   methods section was found via per-block scoping is impossible for PDFs — instead confirm the honest
   "whole manuscript text was searched" caveat always appears for a PDF-primary manuscript.
6. Switch to (or register) a WIP manuscript whose primary file is Markdown/DOCX/ODT with a real "Methods"
   heading. Run the same check and confirm the scoping caveat does NOT appear (real section-based scoping was
   used) when a methods heading is present, and that unmapped candidates persist with `coordinate_precision:
   null` while their fuller `anchor_state` remains visible in the finding's raw payload.
7. In Settings, turn data-egress consent OFF. Repeat step 2 (Library) and confirm the button is disabled /
   the endpoint refuses with 403 before any candidates appear. Directly `POST` to
   `/wip/manuscripts/{id}/checks/analytic-flexibility` (e.g. via the browser devtools console or curl) with
   egress off and confirm 403, not a network hang or a 500.
8. Confirm the Status popover shows a tracked AI-request entry while either "Surface" action is running, with a
   click-back to the correct workspace/pane.

## Pytest

Targeted suite (`pytest tests/test_quote_matching.py tests/test_analytic_flexibility_assistant.py
tests/test_section_scope.py tests/test_analytic_flexibility.py tests/test_wip_analytic_flexibility_text.py
tests/test_wip_analytic_flexibility_checks.py tests/test_wip_checks.py tests/test_frontend_assembly.py -v`):
**122 passed**, 0 failed, 0 skipped — no regressions in `test_wip_checks.py`'s 16 pre-existing tests.
Additionally ran `tests/test_findings.py` (touched by the additive `?source=` query parameter, not part of the
brief's Step-2 command): **8 passed**.

Full suite (`pytest -n 2 -q`; `-n 4`/`-n auto` both hit this machine's known intermittent xdist worker-crash
flakiness — see `.claude/CLAUDE.md`/session memory — retried at `-n 2` for a clean run): **2315 passed**, 1
failed, 4 skipped. The one failure, `tests/test_website_how_it_works.py::test_primary_local_destinations_exist
[demo/-target2]`, is a pre-existing, unrelated gap: it asserts the gitignored `dist-demo/` build artifact
exists on disk, which only `tools/demo/build_demo.py` (a separate, CI-only build step this plan never touches)
produces — this worktree never ran that build, and nothing in this plan's diff comes near the demo static-site
pipeline.

**Two real, unrelated-looking-but-genuine regressions were found and fixed during this final full-suite run**
(not present in any of Tasks 1-11's own targeted-test verification, since neither is exercised by this
feature's own test files):
1. `tests/test_short_write_sweep.py::test_no_unaccounted_raw_commit_in_routers` — a repo-wide guard (inc 281)
   that fails on any new raw `conn.commit()` in a router not explicitly allowlisted. Task 4's
   `analytic_flexibility.py` deliberately uses `Depends(get_connection)` + a manual commit instead of
   `run_write` (reviewed and confirmed correct in Task 4: `run_write` retries its whole closure on a SQLite
   lock, which would risk re-firing the LLM call) — exactly the "egress" reason category the allowlist already
   documents for `critical_review.py`/`workbench.py`. Fixed by adding
   `"analytic_flexibility.py": 1,  # propose_analytic_flexibility — the LLM candidate-proposal call (egress)`
   to `ALLOWED_RAW_COMMITS`.
2. `tests/test_demo_snapshot.py::test_demo_wip_state_regenerates_from_real_sandbox_deterministically` — a
   byte-identical snapshot test comparing a freshly-regenerated `demo/wip-state-v1.json` against the committed
   copy. Task 6 added `analytic-flexibility` (`kind: "provider-ai"`) to `wip_checks.py`'s tool registry, which
   the demo generator serializes into every synthetic manuscript's `checks.tools` list — the committed snapshot
   predates that addition. Fixed by regenerating via `python tools/demo/generate_demo_wip_state.py` (the
   project's own established regeneration path); the resulting diff is a clean, minimal 10-line addition (one
   new tool-registry entry, ×2 synthetic manuscripts).
