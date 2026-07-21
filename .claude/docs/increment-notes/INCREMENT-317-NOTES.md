# Increment 317 — QA re-triage batch (routes 24/27/30/32, 2026-07-03 run)

## Context
Backlog §1 carried "QA runs 20260702/03 — remaining re-triage": a set of Medium/Low findings from
`.claude/qa-inbox/_processed/20260703_073208/` (routes 24, 27, 30, 32) held un-actioned because several were
suspected to be downstream of the SQLite write-lock issue that was later fully closed (incs 272–281) — the
backlog explicitly warned not to file them as fresh findings without re-confirming first. This increment did
that re-confirmation, live, against a fresh `tools/qa/_qa_serve.py` fixture on the current codebase, for every
Critical/High/Medium finding across all 4 routes — not just the ones presumed stale.

## Disposition (every finding, re-verified live)

**Confirmed FIXED** (all traced to the SQLite write-lock arc, incs 272–281):
- Route 30 Critical (`PATCH /papers/{id}`, tag POST, `/citations/render` all 500ing) and its 3 downstream High
  findings (Year not persisting, tag-add failing, Cite/MLA-switch broken) — reproduced the exact steps live:
  Year edit → `PATCH /papers/3` returned 200 and persisted (confirmed via reload + the library card); tag add →
  `POST /papers/3/tags` returned 201 and the chip rendered immediately; MLA style switch → live preview + enabled
  Copy button, both correct. Route 30's tag-suggestion-accept Medium (downstream of the same tag-POST 500) is
  fixed too — confirmed a suggested-tag chip accepts cleanly.

**Confirmed NOT bugs** (rubric artifacts or by-design, not app defects):
- Routes 24/27/30's three "console-error budget" Medium findings: reproduced live and confirmed each flagged
  console entry is Chromium's own `Failed to load resource: the server responded with a status of 422/404/409`
  network-layer message — **not** an app `console.error()` call (grepped `00_lib.jsx`: the fetch wrapper only
  ever calls `console.warn`). This message is unavoidable for *any* fetch to a non-2xx endpoint, so every route
  whose adversarial checklist deliberately triggers a 422/404/409 will always produce it. Not a code fix; see
  the QA-POLICY note below.
- Route 27's "Import file doesn't accept a raw PDF" High: by design, and already documented — the help corpus's
  "Importing a citation file" section states plainly "Import brings in **metadata only** — no PDF is attached
  (add PDFs via Scan folder, Zotero, or Acquire OA copy)." A QA-agent expectation mismatch, not a defect.
- Route 27's "outside-fixture-path scan accepted" Medium: already a documented, accepted tradeoff for a
  local-only single-user app (CLAUDE.md's security baseline: `POST /library/scan` reading any user-supplied
  folder is "fine on 127.0.0.1 (the server is the user's machine)... gate before any hosted deployment") — not a
  new gap, already tracked for the pre-hosted-deployment pass.
- Route 32's "no seeded exact-precision citation reachable" Low: a QA-harness fixture limitation, not an app
  bug. `_seed_library` (`tests/api_helpers.py`) pins a truthful bbox on a *chunk* (inc 120) but never pre-bakes a
  `citation_mappings`/`evidence_quotes` row — reaching an "exact" citation requires an actual verified-synthesis
  run, whose retrieval/NLI outcome isn't deterministically seedable without faking the whole pipeline. Region and
  null precision are already covered; only exact is a fixture gap.

**Confirmed still open, real, root-caused, and fixed in this increment:**
1. **Route 24 — `DuplicatesModal` un-dismiss didn't refresh the candidate list.** `19_duplicates.jsx`'s scan
   effect ran once on mount; the un-dismiss button's `onClick` only called `refreshDismissed()` (updating the
   "previously dismissed" sub-list) and never re-triggered the scan or cleared the session-only `dismissed`
   hide-set. Reproduced live: dismiss a pair, un-dismiss it, and it never reappeared in "possible duplicates"
   within the same modal session — only closing and reopening the modal (a fresh mount) recovered it. **Not**
   the "stayed absent even after a fresh scan" framing the original report implied — a fresh scan (via
   close+reopen) always worked; the gap was narrower: no way to *rescan in place*. **Fix:** extracted the
   scan-launch+poll logic into a stable `runScan` callback, called both on mount and after a successful
   undismiss.
2. **Route 27 — `ScanModal` lost mid-scan visibility across a modal close/reopen.** The scan job's id lived only
   in component state (`useState`), so closing the "Watched folders" modal while a scan was running and
   reopening it reset to `{status: "idle"}` even though the job kept running server-side (no data loss, just no
   UI feedback). **Fix:** persist the in-flight `{url, jobId}` to `localStorage` (`callosum.scanJob`, mirroring
   the already-established `callosum.scanFolder` pattern) on start, clear it on done/error, and resume polling
   from it on mount if present. Verified live: started a real scan job via the API, set the persisted-job
   localStorage key by hand to simulate "modal reopened mid-scan," then opened the modal fresh — it immediately
   resumed polling and completed correctly (the watched-folder row showed a real "last scanned" date), 0 console
   errors.

## Manual verification (Playwright, this session, against fresh `tools/qa/_qa_serve.py` fixtures)
Both fixes were verified against a **rebuilt** fixture (the assembled-JS is cached in-process at server startup,
so the QA server had to be restarted after each source edit to pick up the change — a live reminder of the same
caching behavior documented for the main dev uvicorn process). Route 24: seeded a title+author+year duplicate
pair directly via `create_paper`, confirmed the scan found it, dismissed it, un-dismissed it, and confirmed it
reappeared in the "possible duplicates" list **without closing the modal** — 0 console errors. Route 27: started
a real scan job via `POST /library/scan`, hand-set the persisted-job localStorage key, reopened "Watched
folders" fresh, and confirmed it resumed + completed on its own.

## Pytest
Full suite **1303 passed, 1 skipped** (up from 1302). `tests/test_frontend_assembly.py` gained
`test_qa_retriage_20260702_batch_undismiss_and_scan_recovery_fixes` — a regression guard asserting `runScan`
exists and is wired to the undismiss handler, and that `27_scan.jsx`'s job-persistence key/resume logic exists.
`ruff check .` / `ruff format --check .` clean; `python tools/check_line_budget.py` clean (348 files — both
touched files stayed well under the cap).

## Gates
- **QA-POLICY note (not yet actioned as a doc edit, flagged for a future pass):** the "console-error budget = 0"
  standing assertion produces a false positive on *any* route whose adversarial checklist deliberately triggers
  a 4xx/5xx, since Chromium's own network-layer logging is indistinguishable from an app-level error in a plain
  console listener. A future QA-POLICY refinement could scope the budget to exclude `Failed to load resource...`
  messages that correlate with an intentionally-triggered negative-path step, so this doesn't keep manufacturing
  the same non-bug across every future adversarial route run.
- **Principles/DESIGN:** neither fix touches a claim/signal, egress, or CSS — pure state-management correctness
  in two existing modals. No gate triggered beyond the standard test/line-budget checks above.

## Next
The QA-POLICY console-error-budget refinement noted above is the one loose end from this pass — not urgent
(it only produces noisy-but-harmless false-positive findings, never masks a real one), left for whenever the
QA-POLICY doc next gets a substantive pass.
