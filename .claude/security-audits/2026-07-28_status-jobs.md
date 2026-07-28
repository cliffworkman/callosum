# Security audit — cross-feature async-job status (`/status/jobs*`), inc 406

**Date:** 2026-07-28
**Author:** Claude (session)
**Trigger:** New API endpoints (audit-gate criteria #1) — three new routes on a new router,
`app/backend/api/routers/status.py`.

## What shipped

The "Status" menu popover's backend: an aggregator that reflects over every `JobStore`-typed
attribute on `api.state` (~30 independent job stores already exist, one per feature — Ask,
axis scoring, dedup scan, library scan/import, meta-analysis batches, ...) and reports them as
one unified list, plus a way to dismiss finished entries.

- `GET /status/jobs` — read-only aggregation across every discovered store, with a lazy
  auto-expiry sweep (drops done/error jobs whose `finished_at` is over an hour old).
- `POST /status/jobs/{store}/{job_id}/dismiss` — removes one job from its store.
- `POST /status/jobs/clear-finished` — bulk-removes every done/error job across all stores.

No new file-write path, no new external fetch, no new auth logic, no DB access (pure in-memory
aggregation over structures already held in `api.state`).

## Threat review

| Concern | Assessment |
|---|---|
| **The one real input-validation question: the `store` path segment** | `store` is a user-suppliable string on the dismiss endpoint. It is **never** used to `getattr`/resolve an arbitrary attribute off `api.state` from that string. `discover_stores()` first builds the map of *actual* `JobStore` instances currently on state (by iterating `api.state`'s real keys and filtering `isinstance(value, JobStore)`), and the endpoint does a plain dict `.get(store)` against that pre-built map. A request for `store="engine"` (a real, sensitive attribute — the SQLAlchemy engine) or any other non-`JobStore` attribute, or a name that isn't an attribute at all, can never resolve to anything but a 404 — there is no code path where the string reaches `getattr`. Verified directly: `test_dismiss_rejects_a_state_attribute_that_is_not_a_job_store`. |
| **Information disclosure** | The aggregator returns only `{store, job_id, label, status, detail, progress}` per job. `detail` is the existing `Job.detail` field, already populated by each feature's own `mark_error(job_id, detail)` calls (e.g. `f"{type(exc).__name__}: {exc}"` — the same exception-summary strings already returned by each feature's *own* existing status-polling endpoint today, e.g. `GET /papers/citation-counts/refresh/{job_id}`). This surfaces nothing that wasn't already reachable per-feature; it just aggregates it. `Job.result` (which can hold larger payloads, e.g. a full citation-refresh summary) is deliberately **never** included in the `StatusJob` response model. |
| **Injection (rule #3)** | N/A — no SQL, no filesystem, no subprocess. The whole surface is pure in-memory dict/attribute access. |
| **SSRF / external calls** | N/A — no outbound requests of any kind. |
| **Secret handling** | N/A — no secrets touched; `api.state` also holds non-`JobStore` sensitive objects (`engine`, clients, credentials-adjacent config), and the reflection is filtered to `isinstance(..., JobStore)` before anything is exposed, so those never enter the response. |
| **Resource exhaustion / DoS** | The aggregator is O(number of jobs across all stores), bounded by how many jobs a single local user has actually started — no unbounded loop, no user-controlled iteration count. The 1-hour auto-expiry sweep runs on every read and is O(jobs in that store); trivial at local-app scale. Polling cadence (2s open / 12s background) matches existing per-feature polling patterns elsewhere in the codebase (e.g. `CitationCountsButton` polls at 600ms) — not a new traffic class. |
| **Auth / access-control interaction** | `/status/jobs*` is **not** added to `_EXEMPT_PATHS` or `_RECOVERY_PATHS` in `access_control.py` — it requires the same bearer token as every other endpoint when Remote access is enabled (default off). Under `CALLOSUM_READ_ONLY=1`, the two `POST` routes (dismiss, clear-finished) correctly 403 via the existing method-level read-only boundary; `GET /status/jobs` still works — the same generic behavior every other endpoint gets, no special-casing needed or added. |
| **Supply chain** | No new dependency — FastAPI/pydantic already present; `JobStore` extensions use only stdlib (`time`, `dataclasses`). |

## Negative-path checks (concrete results)

Run: `python -m pytest tests/test_status.py tests/test_job_store.py -q` → **17 passed**.

- `store="engine"` (a real, non-`JobStore` state attribute) on the dismiss endpoint → 404, not a
  crash or silent no-op on real state (`test_dismiss_rejects_a_state_attribute_that_is_not_a_job_store`).
- `store="not_a_real_attribute_at_all"` → 404 (same test).
- Dismissing an already-dismissed job → 404, not a second success (idempotency check,
  `test_dismiss_removes_a_finished_job_and_is_idempotent_404_after`).
- A freshly `create()`d job never `mark_running`'d is not shown (not a leak of pre-start
  internal state) — `test_freshly_created_job_not_yet_running_is_not_shown`.
- `clear-finished` only removes `done`/`error` jobs, never `running`/`pending` —
  `test_clear_finished_removes_only_done_and_error_jobs`.
- The 1-hour auto-expiry sweep is exercised directly at the `JobStore` level with a backdated
  `finished_at`, confirming stale entries are dropped and fresh/running ones are not —
  `test_prune_finished_older_than_drops_stale_done_and_error_jobs`.

## Residual risk

None identified beyond the existing, already-accepted posture of every other job-status
endpoint in the codebase (each of which already exposes its own `detail`/`status` per job to
any caller that can reach the local API). This feature aggregates that existing exposure; it
does not create a new one.

## Verdict

**Security Audit: PASS.** The one real external-input surface (the `store` path segment) is
constrained to a pre-filtered map of actual `JobStore` instances and can never resolve an
arbitrary `api.state` attribute; no new dependency, no new file/DB/network surface; covered by
17 tests including the specific negative path the design was built to prevent.
