# Increment 309 — backlog §1 close-out: mobile CSS batch, real PDF-404 fix, route_00 rewrite, httpx2 migration

## Context
The 2026-07-19 backlog audit/reorg (see `changes.md`) grouped the genuinely-open, no-decision-needed items into a
new §1 "Near-term" section. This increment clears all of it in one Playwright-equipped session: browser-verify
and fix the 4 mobile-CSS QA findings, actually fix (not just document) the metadata-only-paper PDF 404, rewrite
the stale `route_00` steps, and migrate the `httpx→httpx2` TestClient deprecation.

## Implemented

**4 mobile-CSS spacing fixes (`styles.css`), each browser-verified at 375px with Playwright:**
- Discover Feed's `Unread (391)` label was wrapping mid-word — 3 filter buttons were `flex:1` (equal thirds).
  `.app.mobile .feed-controls .tags-srcfilter-btn { flex: 0 1 auto }` lets them size to content and wrap as a
  group (mirrors the existing `.synth-section-filter` override).
- The workspace "what moved" hint was 4 lines / 82px on a phone. `WorkspacesWhatsNewHint` (`30c_frame.jsx`) now
  takes a `mobile` prop and renders a shorter copy on phone width (82px → 48px) — the full desktop sentence is
  unchanged (kept for `test_frontend_assembly`'s existing substring assertions).
- Settings' collapsed provider rows: `.provider-toggle` (`flex:1; min-width:0`) could shrink its own box, but its
  `nowrap` caret+name+badge children couldn't — they overflowed past the shrunk box straight into the Use/Delete
  actions (a box-vs-content mismatch, not a container overflow). `.app.mobile .provider-toggle { flex-wrap: wrap }`
  lets the badge drop to its own line inside the toggle instead.
- Work → Cite → Suggest's `.cite-pane` has no padding at all (unlike Synthesize's `.synth`), so the right-aligned
  "from your library · local, no egress" line ran flush to the screen edge (right edge at 374/375px).
  `.app.mobile .cite-pane { padding: 0 14px }` gives it the same inset as everywhere else.

**The metadata-only-paper PDF 404 — a real fix, not a documented exception.** Reproduced first (double-clicking a
no-attachment paper fired `GET /papers/{id}/pdf`, a genuine 404, logged as a **console error**, then a graceful
"PDF not available locally" fallback). The library card already carries `attachment_count`; there was no reason
to make the doomed request. `40_app.jsx`'s `openPdf` now computes `hasPdf` from `paper.attachment_count` (`null`
when unknown, e.g. a citation-jump caller that only has `{id, title}` — never clobbers an already-known value from
a prior open of the same tab); `30c_frame.jsx` passes `knownNoPdf={t.hasPdf === false}` to `PdfViewer`; `30_viewer.jsx`
skips the fetch entirely and sets `status: "unavailable"` directly when `knownNoPdf`. Verified: the no-PDF path is
now zero console errors / zero network requests; a real-PDF paper (verified against library paper 1) is
unaffected (200 OK, renders normally).

**`route_00_smoke_readonly.md` rewrite.** Steps 4–5 described the pre-inc-280 THEORY/METHODS accordion with a
left-pane SYNTHESIS section; the actual current structure (confirmed live via Playwright, not assumed) is: left
pane = **Axes** section (tabs: Axes/Tags/Queue) + **Review** section; right pane = **Details** + Data consistency
(GRIM) + Statistics check + Bayesian statistics + Mixed-model reporting + Transparency signals (+ more below the
fold). Rewrote both steps to match. Also fixed step 3 + the pass criteria's stale "the 404 is expected" language,
now inverted by the PDF-404 fix above: a 404 on this path is a regression, not an artifact.

**httpx→httpx2 TestClient migration.** Starlette 1.x's `testclient.py` does `try: import httpx2 as httpx / except
ModuleNotFoundError: import httpx` + warn — so the "migration" is installing `httpx2`, **zero source changes**.
Along the way found the local dev environment's installed `fastapi`/`starlette` (0.115.8/0.45.3) didn't match
what `requirements.txt` has pinned since inc 305 (0.139.2/1.3.1) — the bump was never actually installed here.
Ran `pip install -r requirements-dev.txt` to sync, which is what surfaced the real `StarletteDeprecationWarning`
(the stale environment couldn't reproduce it). Added `httpx2>=2,<3` to `requirements-dev.txt` and
`pyproject.toml`'s `test` extra. Audited (`2026-07-19_httpx2-testclient-migration.md`, PASS) per the new-dependency
gate — dev/test-only, same author/org as the existing `httpx`/`starlette`, zero runtime/shipped-code surface.

## Key technical detail
The PdfViewer fetch effect's dependency array stays `[paperId]` (not `[paperId, knownNoPdf]`) deliberately —
`knownNoPdf` is read via closure at the moment a *new* tab mounts for a given paperId (when `openPdf` has already
computed it), which is the only time it matters; adding it to the deps would re-run the effect if the flag ever
flipped for an already-open tab, which isn't a case this fix needs to handle.

## Manual verification (Playwright, this session)
1. Resize to 375×700. Discover → Feed: filter buttons show full labels, wrap as a group. Library workspace: the
   whatsnew hint is 2 lines, not 4. Settings: provider badges wrap onto their own line, no Use-button collision.
   Work → Cite: the provenance line sits ~15px from the right edge, not flush.
2. Library → search a metadata-only paper (e.g. "Cortical Beta-Amyloid...") → double-click → 0 console errors,
   0 network requests to `/pdf`, same "PDF not available locally" UI as before.
3. Library → open a real-PDF paper → unaffected (200 OK, renders, highlights work).
4. `pip show httpx2` absent → `pytest tests/test_health.py` shows the deprecation warning; installed → gone.

## Pytest
`tests/test_frontend_assembly.py` **35 passed** (34 + 1 new regression guard, `test_qa_20260719_mobile_batch_and_pdf_404_fix`).
Full suite: **1283 passed, 1 skipped** (`pytest -n auto -q`, ~9m20s) — unchanged count, no backend behavior change.
`ruff check .` + `ruff format --check .` clean; `python tools/check_line_budget.py` clean (345 files).
