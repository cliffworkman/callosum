# Increment 415 — Status popover: click an entry to navigate to its destination

## Implemented

Callosum's flagship functionality (synthesis, meta-analysis checks, citation-count refresh) is slow. The
Status popover (incs 406-408) already lets a user watch every running/recently-finished job in one place with
real progress where available — but it was purely informational. Cliff's rationale: knowing roughly how long
something will take already makes the wait more bearable; letting a click jump straight from that same list to
a job's outcome (or to where it's happening, if still running) means a user can go do something else and
navigate straight back the moment it matters, instead of hunting for where the result landed.

Three concrete destinations were named: the meta-analysis section of the Methods panel, the Library view where
cited-by counts live, and Synthesize > Ask for a specific past question. Three Explore passes + a Plan pass
found the Status popover had zero navigation capability and `Job`/`JobStore` carried no "what resource is this
about" data at all — every job-creating endpoint has the relevant id in hand at creation time but discards it
into a background-task closure argument, never persisted onto the `Job` the aggregator reads. The three named
examples resolved to three different shapes:

1. **Meta-analysis** = the reporting-completeness auditor (`meta_jobs`, `metaanalysis.py`) — NOT the unrelated
   Work > Meta-Analyze dataset-prep tool, which has no async job at all and structurally can't appear in Status
   regardless (correctly out of scope). This job is library-wide, no per-paper id — reuses the existing
   `showMetaFlagged()` (filters Library to exactly the papers this job found) verbatim.
2. **Library cited-by counts** = `citation_count_jobs` — also library-wide. Reuses the existing `gotoLibrary()`
   plus `libraryBits.onSortChange("citations_desc")`, which `App()` can already reach directly (no new prop
   plumbing needed).
3. **Synthesize > Ask** = `summary_jobs`, identified by `summary_id`. A working "reopen a past synthesis"
   mechanism (`loadSummary`) already existed *inside* `SynthesisPane` but nothing external could call it — this
   needed genuinely new plumbing (below). Confirmed a **running** Ask job's `summary_id` doesn't exist yet, even
   server-side — clicking an in-progress Ask entry can only open the Ask tab in general; the Status popover's own
   live progress bar remains the way to watch it work. This is an honest, accepted limitation, not a compromise.

**Backend — one narrow field, not a reopening of "expose `job.result`":** `Job.nav: dict[str, Any] | None`
(`app/backend/api/job_store.py`) — a loose dict a job's own `mark_done()` call may optionally populate (e.g.
`{"summary_id": 42}`). `StatusJob` gains the same field; `_to_status_job()` gains exactly one new line
(`nav=job.nav`) — `job.result` is still never read, so the original inc-406 audit's "aggregates existing
exposure, creates none" holds by construction. The *only* call-site change needed: `summaries.py`'s
`_run_summarize_job` now passes `nav={"summary_id": result.summary_id}` to `mark_done`. `metaanalysis.py` and
`citation_counts.py` need zero changes — their batches have no id to publish, so `nav` stays `None` by omission,
correctly matching "fixed destination, no entity."

**Frontend:** `04c_status.jsx` gains a `STATUS_NAVIGABLE_STORES` allowlist (`meta_jobs`, `citation_count_jobs`,
`summary_jobs`) — a row's label renders as a real, indigo, `.btn-link`-styled `<button>` only when its store is
in the allowlist; any other job kind keeps the plain, honest, non-clickable `<span>`. `StatusMenu({ onNavigate
})` closes the popover on navigate. `App()` (`40_app.jsx`) owns the dispatch table (`onStatusNavigate`, keyed on
`job.store`), reusing `showMetaFlagged`/`gotoLibrary`/`libraryBits.onSortChange` verbatim. A new
`openSynthesisSummary` composes the existing `openSynthesisWorkspace()` (confirmed it never touches
`pendingSummarize`, so no conflict with a fresh "summarize selected papers" run) plus a new `requestedSummary`
state (`{summaryId, nonce}`), added to `workspaceCtx` next to the existing `workspaceTabRequest`.
`SynthesisPane` (`20_synthesis.jsx`) gains a `requestedSummary` prop and a new effect mirroring
`WorkspacePane`'s existing nonce-only-dependency idiom exactly, calling `loadSummary` — confirmed independent
of the existing `pendingSummarize` effect (separately nonce-gated), so no cross-firing risk.

**Extensibility:** a future 4th job kind needs exactly (a) optionally pass `nav={...}` at its own `mark_done()`
call, and (b) one new `if (job.store === "...")` branch + `STATUS_NAVIGABLE_STORES` entry — nothing about
`Job`/`JobStore`/`StatusJob`/the reflection-based `discover_stores()` changes per job kind, mirroring how
`JOB_LABELS` already extends today.

## Key technical detail

`nav` is deliberately a loose `dict[str, Any]`, not a typed sum-type — `Job`/`JobStore` are `Generic[R]` shared
infrastructure across ~30 unrelated stores, so coupling this generic module to every feature's nav shape would
repeat the exact mistake `discover_stores()`'s reflection was built to avoid (hand-enumerating job stores
instead of walking `api.state`). The convention this establishes (documented in the security-audit addendum):
`nav` may only ever carry small ids already independently reachable via that job's own per-feature status
endpoint — never secrets, paths, or free text.

## Housekeeping

- **Security audit:** a dated addendum to `.claude/security-audits/2026-07-28_status-jobs.md` (PASS,
  unchanged verdict) — names the one genuine new residual risk (`nav` is caller-controlled, unlike the
  mechanically-never-serialized `result`) and records the convention it must follow.
- **QA route:** `.claude/qa-routes/route_76_status_navigation.md` (new) — closes a real pre-existing gap found
  along the way: the Status popover has had **zero QA coverage at all** since it shipped in inc 406. Confirmed
  via `python tools/qa/build_surface_map.py check`: this feature's own new surfaces are now covered; the 4
  remaining uncovered API surfaces (`/manuscripts/{id}/funding-runs`, `/manuscripts/{id}/journal-runs`,
  GET/POST `/papers/{id}/grim-checks`) and 27 uncovered frontend surfaces are **pre-existing debt unrelated to
  this feature** (the auto-updater toast, the tags panel, My Publications settings) — flagged here, not fixed,
  since fixing them would be unrelated scope creep for this increment.
- **EXPERIENCE-PASS:** applies (pure "reception" — shortens the path to an existing result, adds no claim,
  changes no provenance); PRINCIPLES #9 does not centrally gate it. None of the existing six personas was a
  clean fit (closest: Migrator's "long opaque operation with no sign it's alive," the Deadline Citer's "a bare
  count with no path to the claim") — added a new **Multi-tasker** persona to `EXPERIENCE-PASS.md`'s
  (explicitly extensible) library rather than forcing a poor fit. Ran the pass as a code-and-help-corpus-
  grounded walkthrough, not a live persona drive — Playwright/browser automation isn't available this session,
  and CLAUDE.md's own stance is to say so explicitly rather than silently skip the gate.

## Manual verification (owed, not yet run — no browser automation this session)

1. Run the meta-analysis batch check and the citation-count refresh; click each Status row mid-run and again
   once done — both must land on Library with, respectively, the `meta-incomplete` filter and `citations_desc`
   sort.
2. Start a Synthesize > Ask query, switch away, click its running Status row → lands on the Ask tab (still
   running, no fabricated destination); once done, click the row again → reopens that exact synthesis.
3. Confirm the dismiss `×` still works independently of the new click target, and an unwired job kind's label
   renders as plain, non-clickable text.

## Pytest / build gates

- `pytest tests/test_job_store.py tests/test_status.py tests/test_summaries.py -q` → **37 passed** (4 new: 2 in
  `test_job_store.py`, 2 in `test_status.py`; `test_summaries.py`'s real-pipeline test extended in place, not a
  new test — the one true end-to-end proof the freshly-created `summary_id` and the published `nav` never
  drift apart).
- `python tools/build_frontend.py` + `pytest tests/test_frontend_assembly.py -q` → **53 passed** (2 pre-existing
  exact-string assertions on `MenuBar`'s signature/render call updated for the new `onStatusNavigate` prop).
- `wc -l` on all five touched frontend files + `job_store.py`/`status.py`/`summaries.py`: all comfortably under
  the 600-line cap (`20_synthesis.jsx` closest at 584).
- Full suite: `pytest -n auto -q` → **1699 passed, 1 skipped** (up from 1695 post-inc-414; +4 new here).
