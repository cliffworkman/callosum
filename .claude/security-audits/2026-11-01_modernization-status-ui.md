# Security audit (self-review): Library modernization Status and Settings (inc 620)

**Date:** 2026-11-01 · **Branch:** `integrate/inc607-608-ask` · **Blocker:** B9
**Reviewer:** the implementing session (self-review). **This is not an independent review.** No independent automated
or human review has been run on this increment.

## Scope

- `app/backend/modernization/presentation.py` (new, pure)
- `app/backend/api/routers/modernization.py`: extended `GET /modernization`; Pause/Resume now return the extended body;
  `modernization_status_job`
- `app/backend/api/routers/status.py`: one derived row, a covered-store filter, a failure guard; `StatusJob.notes` /
  `persistent`
- `app/backend/modernization/coordinator.py`: non-blocking `status()`
- `app/backend/api/dependencies.py::preview_verifier`, `summarization/verifier_resolution.py::explanation`,
  `routers/embedding_profiles.py` (shared no-load preview, behaviour unchanged)
- Frontend: `04f_modernization_logic.jsx`, `35j_modernization.jsx` (new); `04c_status.jsx`, `04e_whatsnew.jsx`,
  `30c_frame.jsx`, `35_settings.jsx`, `35i_retrieval_profiles.jsx`, `40_app.jsx`; `whatsnew.json`

Audit-gate triggers: changed request/response contract on existing endpoints (no new endpoint); net-new feature over
~300 LOC. No new external fetch, file-ingestion/write path, dependency or auth logic.

## Threat review

| Area | Finding |
|---|---|
| Authorization of state-changing actions | No new state-changing action. The UI calls the existing `POST /modernization/pause` / `resume` (inc 617), which stay behind the same `AccessControlMiddleware` as every route (bearer token when Remote access is on; 403 under `CALLOSUM_READ_ONLY`). Both are idempotent writes of one durable intent value. Neither writes a retrieval or verifier preference (tested). |
| Path / private content exposure | Every new string is a fixed sentence plus integers. Disk info is byte counts only. `index_run.message` reuses `embedding_index._message`, already exposed by `/embedding-profiles`; its `failure_detail` values are fixed sentences written by the supervisor. Paper titles, DB filename, home path, "Traceback" and cache names are asserted absent from both responses. The Status failure guard drops the row instead of surfacing an exception. |
| Injection / output encoding | No SQL text: one SQLAlchemy Core `count()` on `papers`. React renders all strings as text; no `dangerouslySetInnerHTML`. The notice action is a typed `actionKind`, never prose. Navigation is a fixed descriptor `{workspace:"settings", section:"modernization"}` from the backend or a constant, dispatched through the existing bounded `onStatusNavigate`; `_focusSettingsSection` only looks up an element id. |
| Stale status / misleading success | The Status row is recomputed from stored rows on each read (no cached progress), so it cannot report success the stored state contradicts. During a classification pass the counts can lag by at most one pass; the pass itself is reported as running. Terminal states (`invalid` model, `failed` / `cancelled` run, paused) never say they resume (tested). An index waiting for a model that cannot arrive is reported as blocked, not waiting. The retrieval resolution cache is keyed on every input it depends on and expires after 60 s. |
| Duplicate / conflicting Pause/Resume | The button disables while a request is in flight. The endpoints are idempotent (a second Pause is tested). Two windows writing opposite intents resolve last-write-wins on the single durable row, the same as inc 617, and every window then reads the same stored intent. |
| Unbounded polling | One timer per mounted Settings section, cleared before every reschedule and on unmount; it stops in paused / complete / disabled / action-required. Minimum period 2 s. The Status popover keeps its existing 2 s / 12 s cadence and gains no loop. The notice makes at most one `/modernization` read per mount, and only for an entry with fresh-install wording. |
| Server-side cost per poll | `status()` never waits more than 0.2 s for the coordinator lock. The coverage count behind effective retrieval is cached. The verifier preview reads one settings row and a memory probe; it loads no model (tested by making model construction raise). |
| One stage failing independently | Classification, indexing and model have separate notes. `attention` lists terminal problems without hiding a working stage (tested). A failing `modernization_status_job` cannot break `/status/jobs` (tested). |
| Egress | None added. Status reads trigger no download; provisioning is unchanged. |
| Release gates | No gate changed. `DEBERTA_RELEASE_GATES["packaged_runtime_acceptance"]` stays False; the panel reports "automatic DeBERTa verification is not enabled" (tested). |

## Negative-path checks run (all pass; `tests/test_modernization_status.py`)

- Coordinator status raises an exception containing a path → `/status/jobs` 200, other jobs listed, no path in the body.
- Coordinator lock held by another thread → `/modernization` and `/status/jobs` return within 5 s.
- Model construction patched to raise → both reads succeed.
- Waiting-disk run with byte counts → no paper title, DB filename, home path, "Traceback" or "huggingface" in either response.
- Duplicate Pause → intent stays paused; retrieval and NLI preferences unchanged across Pause, restart and Resume.
- Polling, Pause and Resume → papers, chunks, annotations and MiniLM vectors byte-identical.

## Local static checks

- `bandit -ll` on the touched Python files: no findings.
- `ruff check` / `ruff format --check` (scoped): clean. `tach check`: OK. Line budget: OK. QA surface map: OK.
  `check_whatsnew_coverage.py`: OK.

## Residual risk

- Not exercised in a real browser (the Playwright MCP failed to connect in this session) or in a packaged first run.
- The 0.6.0 notice cannot appear until the version bump, which is out of scope here.

**Security Audit: PASS (self-review; independent review not performed)**
