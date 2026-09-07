# Security audit — Ask query-planner + evidence-hygiene seam (inc 581)

- **Date:** 2026-09-07
- **Trigger:** audit gate #5 (net-new feature spanning 3+ files / ~300+ added LOC).
- **Scope:** `app/backend/summarization/query_planner.py`, `app/backend/summarization/faceted_pipeline.py`,
  the `_run_summarize_job` routing + `_gated_complete` in `routers/summaries.py`,
  `chunk_structure_repo.current_structure_roles`, the `_verify_candidates`/`_persist_verified_summary`
  extraction in `pipeline.py`, and the response/coverage additions. Frontend: `19c_facet_coverage.jsx`.

## Threat review

- **Data egress (invariant #3):** the ONLY new outbound path is the planner's structured `complete()`
  call, which sends **only the user's question** (no library text, no chunks). It routes through
  `_gated_complete`, which refuses (raising `DataEgressDisabledError`) when the active provider
  `requires_egress` and consent is off — checked BEFORE any network call; `plan_query` catches every
  exception and falls back to the narrow path, so with egress off the question never leaves. Per-facet
  generation reuses the existing `EgressGatedSummaryGenerator`/`CachedSummaryGenerator` seam unchanged
  (same gate as today's Ask). **No new un-gated egress.** Verified: `_gated_complete` mirrors the
  existing `/settings/test-key` pre-check and `generator.py`'s own gate.
- **New endpoints / request schema:** none. Routing is entirely server-side inside the existing
  `POST /summarize` background job; `SummarizeRequest` is unchanged. No new external fetch/integration.
- **Injection / SQL (rule #3):** all new reads use SQLAlchemy Core bound parameters
  (`current_structure_roles` binds `chunk_id.in_(chunk_ids)`; the article pool uses the existing
  `_source_chunk_from_row` query shape). No string interpolation. `chunk_ids` is bounded by the
  retrieval budget (a few dozen), well under any SQLite variable limit.
- **Untrusted input at the boundary (rule #4):** the provider's planner JSON is untrusted and treated
  as such — `_extract_json_object` tolerantly reads, then EVERY field is validated (types, non-empty,
  length-capped label ≤80 / query ≤200, facet count clamped to 6, dedup, ≥3-or-narrow). Any malformed/
  oversized/short/garbage response → narrow fallback. No field is coerced; unknown shapes are dropped.
- **Prompt provenance / no injection into generation:** H1a role metadata drives only deterministic
  ranking/coverage; it is NOT injected into the generation prompt (the prompt keeps the existing
  `chunk_id`/`paper_id`/`page`/`text` shape). Generation text is the exact stored chunk text — no
  normalization/assembly — so verbatim-quote verification is unaffected.
- **Verifier authority (invariant #1):** unchanged. One batched `verify_many` over every claim, same
  `VerificationConfig` thresholds. The planner/hygiene seam cannot promote a claim; it only selects what
  to retrieve. Hygiene is deprioritize-not-delete, so it can neither manufacture nor delete evidence.
- **Resource caps:** per-facet top_k (6), per-paper cap (3), global cap (36), facet count (6),
  ≤3 verified/≤2 flagged rendered per facet, ≤1 planner + ≤6 generation provider calls worst case.
  Bounded by construction.
- **Coordinate honesty (invariant #2):** citations keep the existing attachment+page+quote+
  `coordinate_precision` chain; no new coordinate claim.
- **Secrets / file paths / supply chain:** no secrets touched (planner uses the resolved config's key
  via the existing seam; never logged). No filesystem path built from input. No new third-party
  dependency. Coverage rides the existing `scope_ref_json` blob — no schema migration.

## Negative-path checks (run)

- **Malformed/garbage/truncated planner JSON, `<3` facets, dup queries, provider exception:** all →
  narrow fallback (unit tests `test_query_planner.py`: `test_malformed_json_falls_back`,
  `test_fewer_than_min_facets_falls_back_to_narrow`, `test_duplicate_queries_deduped_then_narrow`,
  `test_provider_exception_falls_back`, `test_missing_or_empty_fields_dropped`).
- **Absent/stale `chunk_structure`:** `current_structure_roles` returns `{}`; hygiene is a no-op
  preserving relevance order (`test_absent_roles_is_a_noop_preserving_relevance_order`). Verified against
  a real un-backfilled copy (0 rows → clean run).
- **Egress off:** `_gated_complete` refuses before any network call → narrow fallback (question never
  leaves).
- **Budget caps:** per-paper/global/facet caps enforced in unit tests.

## Result

**Security Audit: PASS.** No new endpoint, no new un-gated egress (planner sends only the question,
through the existing consent gate; generation reuses the existing gated seam), untrusted provider output
is strictly validated with a safe narrow fallback, bound parameters throughout, resource caps bounded,
and the verifier + coordinate-honesty + egress invariants are preserved. The only outbound content is
the user's own question (planner) and the same library text the existing Ask already sends under the
same gate (generation).
