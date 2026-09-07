# Increment 581 — Ask query-planner + conservative H1a evidence-hygiene (broad synthesis)

## Implemented

A broad, multifaceted **Synthesize → Ask** question ("synthesize the systems involved in X, covering
A, B, C…") previously embedded as ONE vector, retrieved a single `top_k=8`, over-generated, and the
verifier correctly flagged nearly everything ("0 of N verified"). This increment adds a bounded facet
planner + a conservative evidence-hygiene seam in front of the existing generate→verify spine, for the
query scope only. Narrow questions and the verifier are untouched.

**New**
- `app/backend/summarization/query_planner.py` — `classify_breadth` deterministic pre-gate (narrow →
  existing path, zero provider calls) + `plan_query` (one provider-agnostic structured `complete()` →
  `QueryPlan{scope, facets[3..6]{label, query}}`), strict validation (cap 6, dedup, ≥3 or narrow), and
  a narrow fallback on any parse/validation/provider failure. The planner decides *what to retrieve*;
  it never makes a claim true.
- `app/backend/summarization/faceted_pipeline.py` — `summarize_faceted`: `_load_article_pool` (live
  article chunks, repeated boilerplate excluded — the existing safe hard filter) → `_faceted_retrieval`
  (ONE batched encode of all facet queries, per-facet vector search over the shared candidate set) →
  `_apply_hygiene_and_budget` / pure `_select_with_hygiene` (H1a **deprioritization** + dedup +
  per-paper(3)/per-facet/global(36) caps) → per-facet generation via the UNCHANGED generator →
  `_verify_candidates` (ONE batched `verify_many` over every claim) → `_assemble` (verified-first,
  ≤3 verified/≤2 flagged per facet, four-state coverage) → persist with facets+coverage in the existing
  `scope_ref_json` blob (no migration). `FacetEvidence` carries the exact stored chunk text (never
  normalized/assembled) so verbatim-quote verification is unaffected.
- `app/frontend/js/19c_facet_coverage.jsx` — `FacetCoverageStrip` (reuses `cite-status`/`synth-coverage`
  classes; green=supported, amber=unresolved). Header counts facets with verified evidence.
- `tests/test_query_planner.py`, `tests/test_faceted_synthesis.py` — 27 pure-logic tests.
- `.claude/research/ask_acceptance_newpath.py` — OLD-vs-NEW acceptance harness.

**Modified**
- `pipeline.py` — extracted shared `_verify_candidates` + `_persist_verified_summary` (+ `_insert_summary`
  `extra_scope_ref`); the narrow path is behavior-preserving.
- `chunk_structure_repo.py` — `current_structure_roles(conn, chunk_ids)` (currentness-gated bulk role
  lookup; `{}` when absent/stale → the hygiene seam no-ops).
- `routers/summaries.py` — query-scope routing (broad→faceted; narrow/sections/failure→existing) +
  egress-gated `_gated_complete` for the planner.
- `routers/summaries_response.py` — optional `coverage` field.

## Key technical detail

- **Deprioritize, never delete (H1a "observed, not obeyed").** The evidence-hygiene study found no
  reason code clears the ≥95% precision gate, so hard exclusion risks deleting real evidence. The seam
  only *down-ranks* the definite `bibliographic`/`structural` tail beneath full-priority
  `scientific`+`unknown`; a demoted chunk still surfaces if a facet has nothing better. `unknown`
  (measured 55.6% — the dominant, evidence-bearing class) is a peer of `scientific`, never below it.
  Empty `chunk_structure` → no-op, so an un-backfilled library loses nothing.
- **Coverage honesty:** `no_evidence_retrieved`/`retrieved_unverified` mean nothing verified in the
  RETRIEVED passages — never that the library lacks the topic.
- **Verifier untouched:** one batched `verify_many`, same thresholds; the planner cannot promote a claim.
- **Egress:** the planner's `complete()` is egress-gated; egress-off → narrow fallback → the question
  never leaves.

## Manual verification script (:8888 demo)

1. `run-callosum.ps1` has no `--reload` → **restart** the server to load new backend code (frontend
   rebuilt via `tools/build_frontend.py`). Provider = **Gemini** (Local AI is `app_data_missing` on dev).
2. Backfill the demo DB for the hygiene tier:
   `python tools/backfill_chunk_structure.py --db-url "sqlite:///C:/Users/cliff/callosum-data/library.sqlite"`.
3. In Synthesize → Ask, run the frozen broad query; confirm it routes broad (facets), the coverage strip
   renders, verified claims lead, and the answer is materially better than the old "1 of 6 verified".
4. A narrow question (e.g. "hippocampal volume in late-life depression?") stays on the unchanged path.

## Acceptance (old-vs-new, same corpus, real models + Gemini)

`.claude/docs/research/2026-09-07_ask-acceptance-old-vs-new.md`: **verified claims 1 → 10**, contributing
papers 5 → 9, all 6 named facets covered with verified evidence, cited scientific-role evidence 0 → 4;
narrow routing unchanged. Judged on verified synthesis / coverage / breadth / hygiene / provenance / gaps
— not raw claim count.

## Pytest

27 new pure-logic tests green; `test_summaries` (17), `test_summarization`/`test_summarize_selected`/
`test_frontend_assembly` (109) green; the trust-spine refactor is behavior-preserving.

## Deferred (design §20, if MUST-SHIP stays solid)

1–3 claim/facet *prompt* target (post-hoc cap ≤3/≤2 per facet is in place instead); flagged-claim
collapse UI; per-citation `evidence_role` surfacing; H1b component-level provenance (no safe
chunk→component bridge yet).
