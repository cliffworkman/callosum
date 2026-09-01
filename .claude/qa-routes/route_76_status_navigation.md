<!-- qa-coverage
api: GET /status/jobs, POST /status/jobs/{store}/{job_id}/dismiss, POST /status/jobs/clear-finished
fe: 04c_status.jsx, 04d_update.jsx, 04b_workspaces.jsx, 40_app.jsx, 20_synthesis.jsx
-->

# ROUTE 76 — Status popover: aggregation, dismissal, and click-to-navigate

**Tier:** 1 local-stateful
**Goal:** Exhaust the global operation contract: actionable backend jobs, synchronous provider/local AI calls, and
shared progress indicators appear in Status, expose honest progress/ETA, and click back to their exact UI destination;
routine Library/WIP scans remain inline-only and cannot crowd the list.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). Egress unset (nothing here needs it).

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **No uncompletable control.**
- **No dead clicks.** Every visible application `JobStore`, tracked AI request, and auto-registered `ProgressBar` has
  a bounded destination. The desktop-updater receipt is the deliberate navigation exception because its action
  remains in the updater toast. `library_scan_jobs` and `wip_scan_jobs` are deliberate visibility exceptions: neither
  running work nor finished receipts may appear in Status, while their source UI continues to show state.
- **`job.result` never leaks.** `GET /status/jobs` may add only compute kind, bounded navigation, monotonic elapsed/
  stage state, and numeric completed-stage receipts. Navigation contains server-owned workspace/pane/tab/modal tokens
  plus typed paper/summary ids; stage/receipt fields contain controlled labels, configuration identity, coarse numeric
  workload size, and durations—never results, prompts, passages, URLs, paths, or secrets.
- **No invented measurement.** Every running row shows stage plus elapsed time. Real `current`/`total` progress may
  use determinate fill. Calibrated ranges require at least three comparable local receipts; a narrow countdown requires
  at least eight stable receipts. Sparse local work remains elapsed-only, provider-variable work says timing varies,
  and overruns say they are taking longer than recent runs—never a negative or stuck-zero countdown.
- **Local means local.** Installed embeddings, semantic retrieval, NLI, OCR, and clustering are labeled `Local AI`;
  configured external or loopback model calls are accurately labeled `Provider AI` or a combined boundary.
- **An in-progress job never fabricates an entity.** Clicking a still-running Ask row lands on Ask generally; the
  exact `summary_id` appears only when the result exists.

## Adversarial checklist

- click a row's label repeatedly while its job is still running (before `nav` exists) — no crash, no stale
  navigation
- dismiss a job, then rapid-click where its row was — no navigation to a removed job
- start two Ask jobs; let one finish; click the finished one's row → reopens *that* synthesis, not the other
- leave a synchronous AI surface while its request is held open; Status must retain the operation and its route back
- exercise a local-AI call and a provider-AI call; neither may disappear because it lacks a backend `JobStore`
- mount an ordinary unowned `ProgressBar`; it must self-register exactly once, then leave a finished receipt
- run repeated Library and WIP folder scans; neither may add a Status row or receipt
- resize to `375x812` — popover still opens/closes/navigates correctly, no overflow

## Steps

1. Seed/trigger a **meta-analysis reporting-completeness** run and a **citation-count refresh** (inject fake clients
   if needed) so both appear in Status mid-run and once done. Confirm each row names its compute boundary where one
   applies.
2. Click the meta-analysis row (running, then again once done) → both must land on the **Library** tab
   filtered to `meta-incomplete` (the same destination `showMetaFlagged`'s own existing chip already
   produces) — confirm the URL/filter state, not just that *some* navigation happened.
3. Click the citation-count row (running, then done) → lands on **Library**, sorted **"Most cited"**
   (`citations_desc`).
4. Start a **Synthesize > Ask** query. While it's still running, switch to a different workspace (e.g.
   Library), open Status, click its row → lands on the **Ask tab**, still showing the live in-progress state
   (no fabricated synthesis id). Once it finishes, click the (now `done`) row again → reopens **that exact**
   synthesis (`GET /summaries/{id}` content matches what the job actually produced), not a blank Ask form.
5. Hold **Help assistant** (`POST /help/ask`) open with a deferred fixture response. Switch to Library, open Status,
   confirm **Provider AI**, the indeterminate bar, elapsed time, and provider-variance copy; click the row and
   confirm it returns to Help. Resolve the request and confirm elapsed time freezes in the completed row.
6. Trigger one synchronous **local-AI** path (for example suggested tags or citation evidence). Confirm it produces
   one Status row, identifies `Local AI`, and navigates to the exact pane/tab and selected paper. Trigger an unowned
   inline progress bar and confirm automatic registration without adding feature-specific Status code.
7. Trigger at least three other backend job families (duplicate scan, axis score, OCR, registration comparison).
   Every label must be clickable and land on its exact modal/pane/workspace; none may open an unrelated fallback.
   For **Axis suggest**, close the Suggested axes modal while the job is running, then click its Status row: the
   Theory → Axes tab must open and the modal must resume that exact job (no second `POST /axes/suggest`, no duplicate
   Status row). Repeat after completion and confirm the same saved suggestions reopen.
   Separately trigger Library and WIP folder scans repeatedly: their inline state must work, while Status remains free
   of both running and finished scan rows.
8. Confirm the pre-existing dismiss `×` and "Clear all finished" still work unaffected by the new click
   target (dismissing a row must not also trigger navigation, and vice versa).
9. Adversarial: rapid-click a navigable row several times; resize to `375x812`, confirm Status remains beside the
   Workspace selector, and repeat navigation with no horizontal overflow.
10. In the desktop shell, inject the updater's `update-ready` event. Confirm **Restart now** invokes the install command
   for a restart action, **Open release page** invokes the release action on Linux, **Later** collapses to an
   **Update ready** pill, and the pill restores the notice without duplicating event listeners.

## Pass criteria

- Backend, synchronous-AI, and auto-progress examples each appear exactly once and navigate to the relevant UI.
- Routine Library/WIP scans never appear in Status and retain their source-surface feedback.
- Provider and installed-local AI are both covered and labeled accurately.
- `job.result` is never present in a `GET /status/jobs` response; navigation stays bounded and typed.
- Every running job exposes elapsed time; calibrated estimates are evidence-backed, uncertainty-aware, and gracefully
  acknowledge overruns. A fresh/incompatible history never fabricates an estimate.
- Dismiss / Clear all finished are unaffected by the new click target.
- Status remains available at mobile width; 0 console/page errors and no overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_76_status_navigation.md` + `screenshots/` (see `_TEMPLATE.md`).
