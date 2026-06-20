# Security audit — Axes increment 1: create/browse/correct user-defined axes (supervised)

Date: 2026-06-17
Scope: six new write endpoints + one new GET on the axes router exposing the existing
`axis_scoring.py` engine, plus an async score-job (mirroring the summarize job) and an AxesPanel UI.
Triggered the audit gate: new endpoints + a net-new feature spanning ≥3 files.

## New surface
- `POST /axes`, `PATCH /axes/{axis_id}`, `DELETE /axes/{axis_id}`
- `POST /axes/{axis_id}/score` (202 + job) / `GET /axes/score/{job_id}` (poll)
- `POST /axes/{axis_id}/papers` (manual add) / `DELETE /axes/{axis_id}/papers/{paper_id}` (manual remove)
- Additive read fields: `scored`/`stale`/`assignment_count` on `AxisResponse`; `status`/`manual` on
  `ClusterPaperResponse`.

## Threat review
- **Authn/authz.** Unchanged — local, single-user, loopback-bound, CORS GET-only to localhost. These
  are the project's first axis-mutation routes but add no new auth surface. Pre-public gating
  (auth + rate-limiting on mutations) still tracked in CLAUDE.md.
- **Input validation.** `AxisCreateRequest.label` is `Field(min_length=1, max_length=200)` and the
  handler also rejects whitespace-only (422); `description` is capped at 4000 (422). `PATCH` validates
  the same and rejects an empty patch (422). `axis_id` / `paper_id` existence is checked → **404**
  (`get_axis` is None / `get_paper` raises `NoResultFound`); an unknown `job_id` → 404; a missing
  assignment on remove → 404. Verified by `test_axis_create_validation` +
  `test_axis_manual_add_and_remove_are_distinguishable`.
- **No data egress.** Axis scoring is **fully local** — it embeds the axis text + the library and
  compares vectors with the local model/vector-store. There is NO LLM call, no Gemini, no network;
  the egress gate does not apply (and nothing routes around it). Strictly more conservative than the
  summarize job.
- **Injection.** SQLAlchemy Core bound parameters throughout (the new `axis_scoring.py` helpers use
  `insert`/`delete`/`select` with bound values; table/column names are schema constants). No string SQL.
- **Output encoding.** Responses are Pydantic models with typed fields; the frontend renders labels /
  titles / confidences as React text children (auto-escaped) — no `innerHTML` of any axis/paper text.
  `status` is a server-derived enum-like string; `manual` a bool; confidence a float|null.
- **Delete blast radius.** `DELETE /axes/{id}` removes only that axis; its `cluster_nodes` +
  `cluster_node_papers` cascade via existing `ondelete=CASCADE` FKs (PRAGMA foreign_keys=ON). Papers
  and other axes are untouched — proven by `test_axis_delete_cascades_only_its_own_tree` (asserts no
  orphan nodes for the deleted axis and the sibling axis + papers intact).
- **Honesty contract.** Assignments are surfaced as tiers (assigned/uncertain/manual) + confidence,
  never as categorical truth; manual overrides (confidence NULL) are visually + structurally distinct
  from scored (float). Manual adds survive a re-score; this is data integrity, not a trust boundary.
- **Resource caps.** Scoring embeds the whole library → potentially slow, so it runs as an async
  background job (the request returns 202 immediately). The in-process job store grows over process
  lifetime (same characteristic as the summarize job store) — acceptable for a local single-user app;
  a bounded/expiring store is a pre-public hardening item alongside rate-limiting. The score job
  fails **gracefully** (caught → `status:"error"` + detail, no 500) when the embedding model is
  unavailable — proven by `test_axis_score_job_fails_gracefully_when_model_unavailable`.
- **Route-surface invariant.** `test_api_exposes_only_read_only_get_routes` updated to admit exactly
  the six new mutations + the new GET poll path; nothing else.

## Negative-path checks (all covered by tests)
empty/whitespace/over-long label → 422; unknown axis/paper → 404; unknown job → 404; double-remove →
404; delete cascade is narrow; model-unavailable → graceful error; live browser flow has 0 console
errors.

## Verdict
**Security Audit: PASS** for the current local, single-user context. No data egress (local scoring),
inputs validated + length-capped, narrow CASCADE delete, graceful async failure. Auth + rate-limiting
+ a bounded job store remain pre-public hardening items tracked in CLAUDE.md.
