<!-- qa-coverage
api: GET /status/jobs, POST /status/jobs/{store}/{job_id}/dismiss, POST /status/jobs/clear-finished
fe: 04c_status.jsx, 04d_update.jsx, 04b_workspaces.jsx, 40_app.jsx, 20_synthesis.jsx
-->

# ROUTE 76 — Status popover: aggregation, dismissal, and click-to-navigate

**Tier:** 1 local-stateful
**Goal:** Exhaust the "Status" menu-bar popover — a pre-existing gap (this surface has had **no QA route at
all** since it shipped, inc 406) now closed alongside inc 415's new capability: clicking a row navigates to
that job's destination (or, for a job kind nobody's wired a destination for, the label must render as
honest, non-clickable text — never a dead click).

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). Egress unset (nothing here needs it).

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **No uncompletable control.**
- **No dead clicks.** A Status row's label is clickable **only** for a job kind that actually has a wired
  destination (today: `meta_jobs`, `citation_count_jobs`, `summary_jobs`) — any other job kind's label must
  render as plain text, not a button, and must not respond to a click.
- **`job.result` never leaks.** The only per-job data beyond `{store, job_id, label, status, detail,
  progress}` is the new, narrow `nav` field — confirm via the network tab that `GET /status/jobs` responses
  never include a full citation-refresh/meta-analysis/synthesis payload, only small ids inside `nav` (or
  `null`).
- **An in-progress job never fabricates a destination.** Clicking a still-running Ask row must land on the
  Ask tab in general (no specific synthesis to reopen yet — its own `summary_id` genuinely doesn't exist
  until the job finishes); this is honest, not a bug.

## Adversarial checklist

- click a row's label repeatedly while its job is still running (before `nav` exists) — no crash, no stale
  navigation
- dismiss a job, then rapid-click where its row was — no navigation to a removed job
- start two Ask jobs; let one finish; click the finished one's row → reopens *that* synthesis, not the other
- resize to `375x812` — popover still opens/closes/navigates correctly, no overflow

## Steps

1. Seed/trigger a **meta-analysis reporting-completeness** run and a **citation-count refresh** (inject fake
   clients per this project's existing test-injection patterns if a real network call would otherwise be
   needed) so both appear in the Status popover mid-run and again once done.
2. Click the meta-analysis row (running, then again once done) → both must land on the **Library** tab
   filtered to `meta-incomplete` (the same destination `showMetaFlagged`'s own existing chip already
   produces) — confirm the URL/filter state, not just that *some* navigation happened.
3. Click the citation-count row (running, then done) → lands on **Library**, sorted **"Most cited"**
   (`citations_desc`).
4. Start a **Synthesize > Ask** query. While it's still running, switch to a different workspace (e.g.
   Library), open Status, click its row → lands on the **Ask tab**, still showing the live in-progress state
   (no fabricated synthesis id). Once it finishes, click the (now `done`) row again → reopens **that exact**
   synthesis (`GET /summaries/{id}` content matches what the job actually produced), not a blank Ask form.
5. Trigger any OTHER job kind (e.g. a duplicate scan, an axis-score run) and confirm its row's label is
   plain, non-clickable text — no button styling, no click response.
6. Confirm the pre-existing dismiss `×` and "Clear all finished" still work unaffected by the new click
   target (dismissing a row must not also trigger navigation, and vice versa).
7. Adversarial: rapid-click a navigable row several times in a row; resize to `375x812` and repeat steps 2-4.
8. In the desktop shell, inject the updater's `update-ready` event. Confirm **Restart now** invokes the install command
   for a restart action, **Open release page** invokes the release action on Linux, **Later** collapses to an
   **Update ready** pill, and the pill restores the notice without duplicating event listeners.

## Pass criteria

- All three named destinations (meta-analysis → Library filtered; citation-count → Library sorted; Ask →
  Ask tab / the exact reopened synthesis) work both mid-run and once done, per the honest-limitation caveat
  for the in-progress Ask case.
- An unwired job kind's label is never clickable.
- `job.result` is never present in a `GET /status/jobs` response; only the narrow `nav` field (or `null`).
- Dismiss / Clear all finished are unaffected by the new click target.
- 0 console/page errors; mobile viewport has no overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_76_status_navigation.md` + `screenshots/` (see `_TEMPLATE.md`).
