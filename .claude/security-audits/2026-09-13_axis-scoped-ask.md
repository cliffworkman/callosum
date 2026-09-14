# Security Audit — Axis-scoped Ask (GitHub #82, inc 602)

**Date:** 2026-09-13
**Scope:** New read-only endpoint `GET /axes/{axis_id}/ask-scope`; new request `scope_type="axis"` on
`POST /summarize` (resolved server-side to an ordinary `papers` scope); shared resolver
`app/backend/clustering/axis_membership.py`; frontend `15c_axis_ask.jsx` + `20d_scoped_ask.jsx`.
**Trigger:** audit gate #1 (new endpoint + request-schema change), #5 (net-new feature spanning 3+ files).

## What the feature does

An axis is resolved to a concrete canonical paper-id set that becomes an ordinary production `papers` scope.
The axis changes WHICH papers are eligible, never HOW Ask reasons — there is no axis-specific prompt, retrieval,
generator, verifier, or evidence schema. `GET /axes/{id}/ask-scope` is a pre-run disclosure of the resolved
count per eligibility tier; `POST /summarize {scope_type:"axis",...}` re-resolves at execution and snapshots the
exact executed set.

## Threat review

- **Input validation.** `axis_id` is a path/body int (FastAPI-coerced). `membership_tier` is a strict
  `Literal["assigned","all"]` — an out-of-set value is a 422 at the boundary. `query` is bounded by the existing
  `SummarizeRequest` contract (unchanged). `_validate_summary_request` requires both `axis_id` and a non-empty
  `query` for the axis scope (400 otherwise). A non-existent axis → 404; an axis that resolves to zero papers →
  **422, never widened to the whole library** (`_resolve_axis_scope`).
- **SQL injection.** All access is SQLAlchemy Core with bound parameters / correlated subqueries
  (rule #3). `axis_member_paper_ids_select` and `_member_rows` are JOINs on `cluster_nodes.axis_id` — no user
  string ever reaches SQL text. Table/column names are constants.
- **Parameter-count / resource bound (inc-573 class).** `resolve_axis_corpus` binds **no** Python id list — it
  uses the correlated `cluster_nodes`-join, so a large axis never materializes a `.in_()` variable set.
  `papers_with_usable_fulltext` (disclosure counts only, called by the GET endpoint) binds the tier's resolved
  paper-id list into `.in_()`; this list is **bounded by library size** and, at any realistic scale, is far below
  the packaged app's `SQLITE_MAX_VARIABLE_NUMBER` (32,766) — an axis would need >32,766 members (a single lens
  holding tens of thousands of papers) to approach it. The execution path binds the resolved list only at the
  pre-existing `pipeline.py` papers-scope `.in_(paper_ids)` (unchanged; the same bound). **Decision:** not
  batched now — this matches production Ask's own papers-scope binding and stays within the bound at realistic
  scale. **Follow-up if libraries ever reach that scale:** adopt `persistence/sql_batch.py` at *both*
  `papers_with_usable_fulltext` and `pipeline.py`'s papers-scope filter together (so disclosure and retrieval
  cannot drift). Recorded as a considered resource-cap decision.
- **SSRF / external calls.** None added. The GET endpoint is local, deterministic, model-free, zero-egress. The
  axis Ask resolves to an ordinary `papers` scope and passes through the **same** production Ask egress gate
  (`CALLOSUM_ALLOW_DATA_EGRESS`) — no new egress channel, no new provider call.
- **Egress while disabled.** With egress off, an axis Ask fails closed exactly like any other `/summarize`
  (canonical `SynthesisFailure`); the `ask-scope` GET issues no model/provider request in any state.
- **Secret handling.** None touched.
- **File-path safety.** No file paths involved.
- **Provenance integrity.** `scope_origin={kind,id,label,policy}` is built **server-side** in
  `_resolve_axis_scope` (never client-trusted) and persisted via the additive `SummaryScope.scope_origin`
  (`to_ref()` only). A membership change after a run cannot rewrite a historical run's corpus — the resolved
  `paper_ids` are snapshotted into `scope_ref_json` at execution (pinned by
  `test_axis_ask_persists_the_resolved_corpus_and_survives_membership_change`).
- **Supply chain.** No new dependency.

## Negative-path checks (executed)

- `POST /summarize {scope_type:"axis", query:"q"}` (no `axis_id`) → **400** (`test_axis_scope_requires_axis_id_and_query`).
- `POST /summarize {scope_type:"axis", axis_id, query:""}` → **400** (same test).
- Empty axis → `POST /summarize {scope_type:"axis"...}` → **422**, not widened
  (`test_empty_axis_scope_fails_honestly_and_is_never_widened`).
- Axis whose members lack full text → `ask-scope` reports `eligible_count:0`; the UI disables **Ask**
  (`test_ask_scope_endpoint_reports_both_tiers_and_eligibility`, `papers_with_usable_fulltext` matches the exact
  retrieval eligibility clause).
- An unrelated Library paper is never in scope (`test_resolve_axis_corpus_tiers`: `_outside not in allmembers`).

## Result

Local-only, no new egress channel, bound-parameter SQL, honest fail-closed empty/unresolvable states, server-side
provenance, resource bound within the packaged limit at realistic scale (documented follow-up if libraries grow
past it).

**Security Audit: PASS**
