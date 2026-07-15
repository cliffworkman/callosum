# Security Audit — Multi-paper (set) critical review (#12)

**Date:** 2026-07-15
**Feature:** A "critical read" over a CHOSEN SET of papers reviewed *together*, extending the single-paper read
(audit `2026-07-08_critical-review.md`). Tier 1 (deterministic/local): each set paper's stored method-check signals
composed into a **fact-matrix** (no score) + intra-set contested claims (the cross-corpus contradiction detector
scoped to the set). Tier 2 (opt-in, egress-gated): an LLM proposes **cross-paper** critique *candidates* admitted
only through the #13 verbatim bar; the human accepts/rejects. New:
`methods/critical_review_set.py`, `integrations/gemini/critical_review_set.py`, the set endpoints in
`routers/critical_review.py` (`POST/GET /critical-read/set`), migration `0045` +
`related_paper_ids_json` on `critical_review_candidates`, `08y_critical_set.jsx` + two entry points.
**Audit gate triggers:** new API endpoints (#1), a new external LLM call path (#2), a net-new feature spanning
3+ files (#5), a schema/request-schema change. No new dependency; no new file-ingestion/file-write path.

## Threat review

- **Data egress (invariant #3).** Tier 1 makes **no** external call — `methods/critical_review_set.py` imports
  nothing from any gemini/LLM module (reuses the local embed/vector/NLI deps via the `critical_review_deps` seam).
  Tier 2 (`_run_set_tier2`) gates on `GeminiConfig.from_environment()`: if `requires_egress(config)` and not
  `data_egress_enabled` → the job's `llm_status.status == "unavailable"` and **no** generator runs (Tier-1 still
  completes and returns its report); a loopback provider needs no consent (zero egress); a cloud provider also
  requires `resolved_api_key()`. The gate is enforced **before** the generator is invoked, so an injected fake
  generator (test seam) still refuses when egress is off. Verified:
  `test_set_tier2_fake_generator_and_egress_off` (egress-off ⇒ `unavailable`, no candidates).
- **Untrusted LLM output.** The model response is untrusted (the roster may point at an arbitrary endpoint).
  `parse_set_drafts` is defensive — tolerates code-fences + surrounding prose (`_loads_lenient`), ignores malformed
  entries, and yields `[]` on any parse failure (never a crash). Every draft then passes the extended **#13
  verbatim bar** (`verify_set_candidates` → `canonical_text_contains(anchor_quote, some set paper)`); an ungrounded
  draft is **dropped** (honest shortfall). The model can never inject a "quote" that isn't verbatim in a set paper,
  and it never chooses the anchor — the anchor paper is decided **deterministically** by which set paper contains
  the quote. Verified: `test_verify_set_candidates_grounds_anchor_and_relates`,
  `test_verify_set_candidates_drops_ungrounded_and_rejected`, `test_parse_set_drafts_defensive`.
- **`related_paper_ids` is framing, not a link (invariant #1 / #7).** The model's bracketed "related" indices are
  mapped to set paper ids, **validated to the set** (unknown/out-of-set indices dropped, anchor removed), stored in
  the additive `related_paper_ids_json` column, and surfaced in the UI explicitly labeled *"the model's framing,
  not a verified link."* Only the anchor quote is verified. No cross-paper *edge* is ever asserted as fact.
- **No authoritative LLM claim (invariant #1) / signal-not-verdict (#2/#7) / no composite score.** A Tier-2 point
  is a **candidate** (amber, `status="pending"`) the human accepts/rejects. The Tier-1 aggregate is a **fact-matrix**
  — per-paper stored check statuses + an intra-set contested count — with **no** summed score, quality, grade, or
  ranking field (guard test `test_set_aggregate_is_a_fact_matrix_not_a_score` asserts the banned key set is absent;
  `test_verify_set_output_has_no_author_or_score_fields` asserts candidate output too). An empty `method_signals`
  is honest silence ("these checks surfaced nothing"), never "clean." The prompt + all UI copy critique *claims and
  methods, never the authors* (A-A no-accusation veto).
- **Injection / SQL (rule #3).** All persistence is SQLAlchemy Core bound parameters; the candidate table + columns
  (incl. the new `related_paper_ids_json`, a typed `JSON` column) are constants. No request/model text is
  interpolated into SQL or a path. The set-scoping query binds `set_ids` via `.in_()` bound params.
- **Input validation / caps (rule #4).** `POST /critical-read/set` de-dups ids and requires **2 ≤ len ≤ 12**
  (`MAX_SET_PAPERS`) → **422** otherwise; every id is existence-checked → **404** on an unknown id. Tier-2 caps:
  `_MAX_DRAFTS = 8`, `_MAX_CONCERN`/`_MAX_QUOTE = 400`, and the whole-set prompt is bounded to
  `_MAX_SET_PROMPT_CHARS = 20000` **divided across the set** (per-paper budget) so a large set can't inflate the
  prompt. The async job mirrors the existing JobStore pattern (bounded poll).
- **Output encoding.** All matrix/contested/candidate text renders through React (auto-escaped); the modal builds
  no HTML from model or paper text. Cell `title` tooltips are React attributes (escaped).
- **Secrets.** The provider key comes from env/keychain via `GeminiConfig.from_environment()`; never logged, never
  in a response.
- **Supply chain.** No new dependency (reuses the CrossEncoder NLI + the `complete()` provider seam + the inc-266
  single-paper primitives).

## Negative-path checks (results)

- `POST /critical-read/set` with `< 2` ids → **422** "Select 2–12 papers…"; with `> 12` ids → **422**. ✓
  (`test_set_validation`)
- `POST /critical-read/set` with an unknown id → **404** "Paper N not found". ✓ (`test_set_validation`)
- Tier-2 requested (`llm:true`) with egress **off** → job's `llm_status.status == "unavailable"`, `candidates == []`,
  Tier-1 report still complete. ✓ (`test_set_tier2_fake_generator_and_egress_off`)
- Ungrounded model draft (quote not verbatim in any set paper) → **dropped**, not persisted. ✓
- Previously-**rejected** signature (union across the set) → not re-created on re-generate. ✓
- `related` index outside the set / equal to the anchor → dropped from `related_paper_ids`. ✓
- Aggregate / candidate response → no `score`/`quality`/`grade`/`rank`/`rating` field; no author-directed copy. ✓

## Verification

`pytest tests/test_critical_review_set.py` — 11 passed (8 engine/Tier-2 + 3 endpoint); full suite green (see
increment notes). QA route 71 covers the 2 new API surfaces (`build_surface_map.py check` → 0 uncovered API).
`ruff format`/`check` clean; line-budget gate green.

## Result

**Security Audit: PASS.** Tier 1 is local-only and produces a fact-matrix (never a score); Tier 2 is egress-gated
(default off, loopback zero-egress, egress-off ⇒ honest `unavailable`), its untrusted output defensively parsed and
admitted only through the verbatim #13 bar as human-confirmed candidates whose anchor is chosen deterministically.
`related_paper_ids` is surfaced as the model's framing, not a verified link. Bound-param SQL, 2–12 id validation,
capped prompt/inputs, escaped output, no author accusation.
