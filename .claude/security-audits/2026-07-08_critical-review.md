# Security Audit — Critical-review supplement (#12)

**Date:** 2026-07-08
**Feature:** A single-paper "Critical read" METHODS section. Tier 1 (deterministic/local): compose the paper's
stored method-check signals + a cross-corpus contradiction detector. Tier 2 (opt-in, egress-gated): an LLM
proposes critique *candidates* admitted only through the #13 verbatim bar; the human accepts/rejects. New:
`schema_critical_review` + migration `0037`, `critical_review_repo`, `methods/critical_review.py`,
`integrations/gemini/critical_review.py`, `routers/critical_review.py`, `08x_methods_critical.jsx`.
**Audit gate triggers:** new API endpoints (#1), a new external LLM call path (#2), a net-new feature spanning
3+ files (#5). No new dependency; no new file-ingestion/file-write path.

## Threat review

- **Data egress (invariant #3).** Tier 1 makes **no** external call (the module imports nothing from any
  gemini/LLM module — enforced by structure + a test). Tier 2's generate endpoint gates on
  `GeminiConfig.from_environment()`: if `requires_egress(config)` and not `data_egress_enabled` → **422** honest
  refusal (no draft requested); a loopback provider needs no consent (zero egress); a cloud provider also
  requires `resolved_api_key()`. The gate is enforced **before** the generator runs, so an injected fake still
  refuses when egress is off (the inc-259 closed hole). Verified: `test_generate_candidates_endpoint_verifies_and_egress_gates`.
- **Untrusted LLM output.** The model response is untrusted (a user may point the roster at an arbitrary
  endpoint). `parse_drafts` is defensive — tolerates code-fences + surrounding prose, ignores malformed entries,
  and yields `[]` on any parse failure (never a crash). Every draft then passes the **#13 verbatim bar**
  (`canonical_text_contains(anchor_quote, paper_text)`); an ungrounded draft is **dropped** (honest shortfall) —
  the model can never inject a "quote" that isn't verbatim in the paper. Verified: `test_verify_candidates_*`.
- **No authoritative LLM claim (invariant #1) / signal-not-verdict (#2/#7).** A Tier-2 point is a **candidate**
  (amber, `status="pending"`) the human accepts/rejects; nothing enters as fact. No composite/quality/score field
  exists on any response (guard test `test_no_composite_score_field_and_no_author_directed_copy`). The Tier-2
  prompt + all UI copy critique *claims and methods, never the authors* (A-A no-accusation veto; guard test scans
  a banned-phrase list).
- **Injection / SQL (rule #3).** All persistence is SQLAlchemy Core bound parameters; the candidate table +
  columns are constants. No request/model text is interpolated into SQL or a path.
- **Input caps / resource.** `_MAX_DRAFTS = 8`, `_MAX_CONCERN`/`_MAX_QUOTE = 400`, prompt text truncated to
  `_MAX_PROMPT_CHARS = 20000`; Tier-1 claim sentences bounded (`max_claims = 12`), retrieval `top_k = 5`. No
  unbounded loop. The async Tier-1 job mirrors the existing acquire-oa JobStore pattern.
- **Output encoding.** All candidate/backbone text renders through React (auto-escaped); the panel builds no HTML
  from model or paper text.
- **Secrets.** The provider key comes from env/keychain via `GeminiConfig.from_environment()`; never logged, never
  in a response.
- **Supply chain.** No new dependency (reuses the CrossEncoder NLI + the `complete()` provider seam).

## Negative-path checks (results)

- `POST …/candidates/generate` with egress **off** → **422** "AI critique requires data-egress consent". ✓
- Ungrounded model draft (quote not verbatim in the paper) → **dropped**, not persisted. ✓
- Previously-**rejected** signature → not re-created on re-generate. ✓
- Unknown paper/job/candidate id → **404**, not a crash (T4 tests). ✓
- API response / UI copy → no composite score field; no author-directed language (guard test). ✓

## Verification

`pytest tests/test_critical_review.py` — 16 passed; full suite green (see increment notes); QA route 67 covers all
6 new API surfaces (`build_surface_map.py check` → 0 uncovered API). `ruff format`/`check` clean; pre-commit gate green.

## Result

**Security Audit: PASS.** Tier 1 is local-only; Tier 2 is egress-gated (default off, loopback zero-egress,
egress-off ⇒ honest 422), its untrusted output defensively parsed and admitted only through the verbatim #13 bar
as human-confirmed candidates. No composite score, no author accusation, bound-param SQL, capped inputs, escaped output.
