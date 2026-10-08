# PHASE 34 / I4-1h — pre-I4-2 baseline reconstruction + integration contract audit

**Status: PLANNING / READ-ONLY EMPIRICAL AUDIT.** No production code changed. No `support_policy` wired. No
`candidate_supports` wired. No `achieved_outcome_span` consumed. No mapping change. No requirement-state
change. No sufficiency-semantics or plan-version bump. No recovery/relation/direction/effectiveness/AnswerPlan
change. I2-3 not started. No model, network, or live E2E run — every empirical result below comes from running
the already-shipped, already-tested, **pure** I4-1 modules (`assertion_authority.py`, `achieved_outcome_span.py`,
`sufficiency_engine.py`'s I4-1g additions) against real, already-committed/stamped artifacts, in a disposable
scratch script (`/tmp/sweep2.py`, outside the repo, never imported anywhere).

- Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
- Starting HEAD: `4f3199aa3ae2b1d712bedc369c422f100ecaac53` — confirmed (`git rev-parse HEAD`, clean working tree).
- I4-1g (same HEAD) is accepted.

I4-1 through I4-1g are treated as implemented, tested, pure, unwired experimental machinery, unchanged by this
audit — nothing in this file edits any of them.

---

## 1. Current accepted architecture

Confirmed by direct re-reading of all seven committed reports (I4-1, I4-1b, I4-1c, I4-1d, I4-1e rev. 2, I4-1f,
I4-1g) in full, not from memory. The locked conceptual principle stands exactly as stated in the directive:
**misattribution is the defect; indirect evidence is legitimate evidence; provenance/directness determines HOW
evidence counts; the requirement determines WHETHER that form of support is sufficient.** No direct > indirect >
synthetic quality hierarchy exists anywhere in the accepted design or in any code shipped so far.

---

## 2–3. Hard gate: recovering and verifying the preserved 54-quote input

### 2.1 Where it actually was

I4-1f's and I4-1g's own reports (`PHASE34_I4_1F_PROVENANCE_AGGREGATION_RESULTS.md` §9, `PHASE34_I4_1G_SUPPORT_SCHEMA_RESULTS.md`
§12) both state that `frozen_54_inputs.json` and any `final_v4*.json` map file were **not present** anywhere
under this worktree's `.local/` directory, "confirmed by direct listing." That listing was **incomplete, not
false**: it enumerated `.local/`'s top-level directory names (`decompose-runs`, `e2e-runs`, `phase32`,
`sufficiency-nomination-diagnostic-*`) and dismissed `e2e-runs` as "unrelated" without descending into it.

A scoped search this increment actually performed (`find .local -iname "*attempt2*"`, guided by the run id
`phase28-live-parent-synthesis-attempt2-20261004T014500Z` named in
`PHASE28_ATTEMPT2_LIVE_PARENT_SYNTHESIS_RESULTS.md` line 23) finds the complete stamped run directory:

```
.local/e2e-runs/phase28-live-parent-synthesis-attempt2-20261004T014500Z/
    phase28_authorization.json, phase28_recorder_calls.json, phase28_result.json, phase28_runner.py, run.zip
    run/00_question.json … run/18_sufficiency_model_assist.json  (33 files, the full staged pipeline trace)
```

**File timestamps settle the chronology.** `run/11_verified_ledger.json` and `run/17_sufficiency_map.json` carry
mtime `2026-10-03 22:03:3x`. I4-1d's own commit (which *used* this exact data — its §10 table reproduces to the
binding) is `321a5d42` at `2026-10-07 15:11:59`; I4-1f is `8fe436fc` at `17:57:03`; I4-1g is `4f3199aa`'s parent
at `18:46:56`, same day. **The data was on disk, in this worktree, four days before I4-1d read it and roughly
two hours before I4-1f reported it absent.** I4-1f's own search simply did not look inside the one top-level
directory it had already listed and named. This is reported as a precondition-recovery finding, not a
criticism of that increment's own bounded scope (which explicitly declined to fabricate substitute data —
the correct call given what its own search found).

### 2.2 What the recovered file is, and is not

`run/11_verified_ledger.json` (SHA-256 `a70409e8f5a0937f414c73c4796b293c6c1a9ef3b31c7fc83bbfa61794c6bd5d`,
968,752 bytes) is a dict with keys `request_contract, subquestions, verified_propositions, evidence_spans,
coverage_authority, coverage_assessed, coverage_outcome, obligation_states, coverage, hierarchy, sealed_hash`.
`verified_propositions` has **exactly 54 entries**, ids `p1`…`p54`, each `{proposition_id, subquestion_id,
obligation_ids, mapping_state, paper_id, retrieval_anchor_chunk_id, evidence_anchor_chunk_id, evidence_span_id,
proposition_text, quote, provenance, verification, responsive_obligation_ids}`. Its own `sealed_hash` field is
`1dce0e1c2dead992c631f9eb9bfaaa4fc29cabb30ec9304687df515cd4abeef8` — a different artifact (and a different
hash) from the one `PHASE34_I4_1B_STRUCTURAL_CONTEXT_RESULTS.md` recorded for `frozen_54_inputs.json`
(`8aa8b0e06b4dd750fc8c7c900a4ca6868ca6196e718d13267550f3e47f5cf8ac`), which is expected: `frozen_54_inputs.json`
was a hand-extracted, quote-only convenience copy a prior session made *from* this richer ledger, in some
serialization whose exact shape was never itself committed or specified anywhere in the seven reports.

Several serialization guesses (compact/indented JSON; list-of-`{id,quote}`; dict `id→quote`; list of bare
quotes; `proposition_text` substituted for `quote`) were hashed and **none matched**
`8aa8b0e06…`. This is the expected, disclosed outcome the directive itself anticipates (§3): the original
convenience file's exact byte layout is unrecoverable without guessing, so byte identity to
`frozen_54_inputs.json` specifically is **not claimed**.

### 2.3 Identity verification against every independently-recorded fact

Checked against every fact the seven prior reports record about the sealed quotes, all from the ledger's real
content, not re-derived from prose summaries:

| Check | Expected (from prior reports) | Found in `11_verified_ledger.json` | Match |
|---|---|---|---|
| Count | 54 | 54 (`len(verified_propositions)`) | ✅ |
| Id range | p1–p54 | `p1`…`p54`, contiguous, no gaps | ✅ |
| p41 quote | "Results: Across the ratings for all faces, Spearman correlations revealed greater proportionality was associated with attrac- tiveness (ρ = 0.292, P < 0.001) and trustworthiness…" | byte-identical | ✅ |
| p1/p4/p8 shared quote | "This research confirmed earlier reports that people with anomalous faces are imbued with negative personality characteristics, detected explicit biases against people with facial anomalies, and described a behavioral manifestation of the 'anomalous-is-bad' stereotype…" (I4-1d §10) | all three identical, byte-identical to the quoted text | ✅ |
| p30 run-in heading | "Specificity and generalization of intervention effects We also observed…" (I4-1b §9) | byte-identical | ✅ |
| p36 subject | "Participants expressed explicit biases…" (I4-1b §10, "the `Participants` subject is not a cue") | byte-identical | ✅ |
| 64 total assertions across the 54 quotes | I4-1b §10, I4-1c §10 | **64**, reproduced independently via `classify_target_assertions` (§5 below) | ✅ |
| Authoritative-assertion count after I4-1c | 22 | **12 propositions carry ≥1 authoritative assertion** out of 22 authoritative assertions — recomputed independently (§5) | ✅ (same 22; I4-1b/c count assertions, this table's count-of-propositions figure is a different, compatible cut) |
| 54-quote achieved-outcome parity | "237 texts total, zero mismatches" incl. these 54 (I4-1d §4) | re-run independently (§6): 24 achieved-outcome matches across 20 propositions, zero mismatches against `attribution.has_result_predicate` | ✅ |

**Decision for §3's own instruction ("report BOTH"): semantic reconstruction is verified — not merely
plausible, but confirmed against nine independent, specific, previously-recorded facts with zero
disagreements. Byte identity to the historical `frozen_54_inputs.json` convenience file is unavailable** (that
file's own serialization was never itself committed/hashed in a reproducible form). The artifact actually
recovered — `11_verified_ledger.json` — is **the primary source the convenience file was itself derived from**,
not a second-hand reconstruction, and is strictly richer (it carries `paper_id`, chunk anchors, and
verification scores the quote-only file could never have carried).

---

## 4. Hard gate: recovering the v4 map

`run/17_sufficiency_map.initial.json` (SHA-256 `46a213044bc6211702fa89710268e1bfb6c4fc348259727a46cb238ef5bbc14e`)
and `run/17_sufficiency_map.json` (SHA-256 `28478500e485137cd6930b8010d274bb1da3afd48e7f4a6208dd183610d9ca0b`) are
each a dict keyed by child id (`c1, c2, c3, c4, c5, c6, c8, c9, c10, c11, c12` — `c7` absent, matching the
`14_final_answer.c*.md` file set, which also skips `c7`), each value `{child_id, requirements: [...]}` in the
exact shape `sufficiency_engine.new_requirement`/`new_role_binding` produce.

**Structural identity check against I4-1d's own published table** (§10 there, "15 bindings, 8 distinct
proposition ids"): every `filled` `achieved_outcome_predicate`-strategy role binding was enumerated
programmatically across the whole `17_sufficiency_map.json`. Result: **15 filled bindings, 8 distinct
proposition ids** — `{p1, p4, p8, p11, p24, p30, p31, p41}` — **and the per-child/per-instance breakdown is
cell-for-cell identical** to I4-1d's table: `c1`→p1 (×1), `c2`→p4 (×3 instances), `c3`→p8 (×1), `c4`→p11 (×2
instances), `c12` instances 0/2/3→p24/p30/p31, `c8`→p41 (×5 instances, all against the
`relationship_to_bias_manifestation` role). This is an exact structural match on every cell the prior report
published, not merely a matching total.

**Decision: `17_sufficiency_map.json` is used as the recovered `final_v4` map; `17_sufficiency_map.initial.json`
as `initial_v4`.** Byte identity to a historically-named `final_v4_lenient.json` scratch copy is unclaimed for
the same reason as §2 — no byte-level hash of that convenience filename was ever recorded anywhere to check
against — but the structural identity above is as strong a confirmation as a byte hash would have given,
since it reproduces eight independent proposition-id bindings across five different children exactly.

**The known c1 gap, located.** `c1`'s instance has `required_roles=[neural_manifestation_evidence]` (filled,
p1) and `alternative_role_groups=[[neural_measure_or_modality, brain_region_or_network]]`, of which
`brain_region_or_network` is filled (p11, via `model_nomination_only`) — yet the instance's own `complete` flag
is `false` and `state` is `partially_filled`/`incomplete_instance`. This is the "known c1 gap" I4-1's own §12
parenthetical names. It is a **pre-existing engine-level discrepancy between `role_completion`'s
alternative-group semantics and the instance completeness flag**, orthogonal to the support-policy work this
audit is scoping — reported here because it is now located precisely, not because this increment is asked to
fix it.

**Limitation disclosed plainly, matching the directive's own §4 instruction:** one previously-documented
binding this audit cannot independently re-derive is the exact **live model-nomination call** that produced
each `model_nomination_only` value (e.g. `p20`'s four `individual_difference_trait_or_construct` instances in
`c8`) — those are recorded as `nomination_receipt_status: "held_fixed_replay"` or `"fresh"` provenance in the
map itself, not re-computable offline without the live model call that made them (which this audit does not,
per the directive, repeat). Every **deterministic** (`achieved_outcome_predicate`) binding, by contrast, is
fully reproducible offline, and was reproduced in §5–6 below.

---

## 5. I4-1f descriptor sweep over all 54 quotes (real run, zero errors)

`aa.classify_target_assertions(quote, target_start=0, target_end=len(quote))` was run against all 54 real
quotes (not the synthetic batteries), for every one of the 54 propositions, with **zero exceptions**. This is
the full sweep I4-1f's own §9 explicitly could not perform ("the other six specifically-discussed ids … and
the full 54-quote sweep" were "genuinely unverified"). It is now performed, with real data, for the first time.

| Measure | Count |
|---|---|
| Propositions | 54 |
| Total assertions | **64** (exact match to I4-1b/c's own figure) |
| `assertion_relation = current_document` | 24 |
| `assertion_relation = unresolved` | 38 |
| `assertion_relation = attributed_external` | 2 (both from **p40** — "Recent work… implicated certain neuroanatomic structures…" and a second eye-tracking citation in the same quote) |
| `aggregation = literature_synthesis` | **0** |
| `aggregation = non_synthetic_or_unspecified` | **64 (all of them)** |
| `assertion_kind = result` | 47 |
| `assertion_kind = interpretation` | 12 |
| `assertion_kind = method_or_description` | 3 |
| `assertion_kind = aim_or_hypothesis` | 1 |
| `assertion_kind = unknown` | 1 |
| `authority_veto` set (either value) | **0 of 64** — exact match to I4-1c §10's finding |
| `finding_authority = authoritative` (propositions with ≥1) | 12 — `p1, p3, p4, p7, p8, p12, p14, p17, p24, p26, p41, p47` |
| `support_label` distribution | `direct_empirical`:22, `unresolved`:24, `interpretive`:12, `descriptive`:3, `attributed_indirect`:1, `None`:2 (the one `aim_or_hypothesis` + the one `unknown`) |

Every count above is internally self-consistent (kind totals sum to 64; label totals sum to 64; relation×kind
cross-tabulation reconciles exactly) — cross-checked programmatically, not merely eyeballed.

**The single most consequential real finding from this sweep: `aggregation = literature_synthesis` never fires,
anywhere, in the real 54-quote preserved corpus.** I4-1e/I4-1f's entire motivating case — "Across multiple
studies, regions A, B, C are implicated in X" — and the §8 corrected-default's one intended behavior change
(admitting an `unresolved` + `literature_synthesis` candidate) have **zero real instances to validate against**
in this corpus. Every piece of evidence for that design decision so far is synthetic-battery-only. This does
not make the design wrong — the corpus is one Qwen-decomposed run over one small library slice, not a
representative sample of review/meta-analysis language — but it means **I4-2's own real-corpus byte-diff
(§18 below) cannot demonstrate the design's one intended positive effect**, only its (correctly) unchanged
behavior on ordinary direct/attributed/unresolved evidence. This should be named explicitly when I4-2 reports
its own diff, so "zero change observed" is not mistaken for "the correction had no effect" when it is really
"the correction's trigger condition never occurred in this particular sealed sample."

---

## 6. Achieved-outcome attachment inventory, rebuilt and extended

`aos.find_achieved_outcome_matches(quote)` was run against all 54 real quotes. Result: **24 achieved-outcome
predicate matches across 20 of the 54 propositions**, zero exceptions, zero mismatches against
`attribution.has_result_predicate` (reproducing I4-1d §6's own 0-mismatch claim independently). For the 8
proposition ids the real v4 map actually binds via `achieved_outcome_predicate` (p1, p4, p8, p11, p24, p30,
p31, p41), the match counts are:

| Proposition | Matches | Ambiguous? | Rule(s) |
|---|---|---|---|
| p1, p4, p8, p24, p11, p30, p31 | 1 each | No | `single_or_last_in_clause` |
| p41 | 3 | **Yes** (2 of the 3 mutually ambiguous) | `ambiguous_boundary`, `ambiguous_boundary`, `single_or_last_in_clause` |

This reproduces I4-1d's own §10 table exactly, including p41's specific pattern, via an independent
re-implementation of the enumeration rather than a re-read of the prior report.

**A finding beyond what I4-1d's own report states: p41's "ambiguity" is a property of `achieved_outcome_span`'s
own narrower, independently-reimplemented predicate-matching layer — not of `assertion_authority`'s
already-resolved assertion/content boundaries.** Cross-running the SAME p41 quote through
`assertion_authority.classify_target_assertions` (§5's own sweep) shows p41 resolves to **exactly 2
assertions**, cleanly non-overlapping, each independently classified:

```
assertion 1  span=[43,200]   current_document / result / authoritative
  content: "greater proportionality was associated with attrac- tiveness (ρ=0.292,…) and trustworthiness (ρ=0.193,…)"
assertion 2  span=[208,372]  unresolved / result / candidate
  content: "with impressions of anger (ρ=0.132,…), dominance (ρ=0.259,…), and threateningness (ρ=0.234,…)"
```

Neither is flagged ambiguous with the other by `assertion_authority` — assertion 1's own embedded-content
parsing already resolves "revealed [elliptical-that] greater proportionality was associated with…" as *one*
assertion headed by `revealed`, exactly the same elliptical-`that` case I4-1d's own §10 names as the root cause
of `achieved_outcome_span`'s separate ambiguity. `achieved_outcome_span` cannot see this resolution because, by
its own explicit design (I4-1d §2, "Boundary logic: duplicated, not imported"), it re-implements clause/sentence
splitting independently rather than importing `assertion_authority`'s own boundary logic, specifically to avoid
tripping that module's unwired-import guard even for a read-only consumer.

**This directly and concretely answers the open question in I4-1d §9/§15 ("key each role binding to the
assertion span those records return") with a real worked example: if I4-2 keys achieved-outcome attachment to
`assertion_authority`'s assertion/content spans — the seam I4-1d's own report recommends — p41 is *not*
attachment-ambiguous at all.** It is two clean, non-overlapping, independently-classified assertions: one
admissible under the §8 default (`current_document`/`result`), one not (`unresolved`/`result`, excluded by the
compound default's own `not(relation==unresolved and aggregation==non_synthetic)` term). The role would be
`filled` from assertion 1, with assertion 2 fully retained and inspectable as a `support_policy_excluded`
candidate — never `ambiguous`. The "p41 is genuinely ambiguous" characterization in I4-1d §10 is correct **only
for `achieved_outcome_span`'s own finer, duplicated-boundary layer**; it does not survive contact with the
seam I4-1d's own recommendation actually points to. This is carried into the §11 and P7 decisions below.

---

## 7. Proposition identity defect — answered against real data

**A.** No — not in general, and the real data proves it two different ways. (i) The duplicate-id case:
`p1`/`p4`/`p8`/`p24` are four *different* proposition rows bound to the exact same 292-character passage; a
code-level match against that passage text alone cannot distinguish which id "really" produced it — the match
is on the passage, and four ledger rows happen to share one passage. (ii) The multi-assertion case: p41's own
single passage contains two genuinely distinct assertions with different authority. In neither case does
"the matched text" uniquely identify "the one proposition row."

**B.** Sometimes, but not from the achieved-outcome detector's own signal alone. `assertion_authority`'s span
output (§6) *can* disambiguate *which assertion* produced a match (p41's two assertions are now separable);
it cannot disambiguate *which of several same-passage proposition rows* (p1 vs p4 vs p8 vs p24) is "the" owner
of that one assertion, because all four rows literally share the identical passage — there is no finer claim/
finding identity recorded anywhere in the ledger to tell them apart (confirmed directly: all four ledger rows'
`quote` fields are byte-identical; their `proposition_id`, `subquestion_id`, and `obligation_ids` differ, but
nothing in the row content itself does).

**C. Recommendation: `supporting_proposition_ids: [...]`, not a singular `proposition_id`, for a
candidate-support record whose content matches more than one proposition row.** The real map's own
`model_mapping`-sourced bindings already do exactly this (`"supporting_proposition_ids": ["p20", "p9"]` on
`c8`'s trait-construct bindings, confirmed directly in `17_sufficiency_map.json`) — the deterministic
(`achieved_outcome_predicate`) path is the one place that still collapses to `unit["proposition_ids"][0]`
singular, inconsistently with its own sibling strategy. **I4-1g's own `new_candidate_support` schema already
has a singular `proposition_id` field (§5 there), not a plural one — this is the one place the schema should be
revisited before production wiring**, consistent with the directive's own instruction not to let `[0]` carry
forward merely because the field is presently singular.

**D.** Not required for correctness — only for the existing single-id-shaped `RoleBinding.proposition_id`
compatibility projection (I4-1e §6, step 5: "a representative/primary binding… selected… for display only").
`candidate_supports` itself should carry the plural, honest form (`supporting_proposition_ids`); a legacy
single-id consumer can still be served a first/representative id from that list, exactly as the plural
model-mapping provenance already does today for its own `supporting_proposition_ids`. **A real, concrete
illustration of a new finding from this audit's own §6 that was not visible to I4-1d:** even for the
*single-proposition* p41 case, the correct supporting id is unambiguous (p41 alone) — the duplicate-id problem
and the multi-assertion problem are **independent defects that happen to coexist in this corpus**, not two
faces of the same bug; a fix for one does not fix the other.

---

## 8. `exact_text` semantics

**Recommendation: both, as two separate fields — never one field doing both jobs.** I4-1g's
`new_candidate_support` schema already has the right shape for this (§5 there): `exact_text` (the matched
local content) *plus* `proposition_id`/optional `predicate_span`/`content_span` (source locator). The real
data shows why collapsing these would be lossy: for p41's assertion 1, the *local* content
("greater proportionality was associated with attrac- tiveness… and trustworthiness…") is what actually earned
the binding, but the *passage* ("Results: Across the ratings for all faces, Spearman correlations revealed…")
is what a human needs to see to relocate/audit it — specifically to see that it was the `Results:` label (not
"We" ownership) that made it `current_document`. **Concrete rule: `exact_text` = the local matched
assertion/content span (I4-1d's `content_span`, once wired); source relocation rides on the already-existing
`proposition_id`/chunk-anchor provenance chain**, never on reconstructing a wider span from the narrow one.
This supersedes today's production behavior (the *whole passage* as `exact_text`, confirmed at
`sufficiency_mapping.py:358`/`_match_achieved_outcome`), which is the thing I4-1d's span work exists to replace.

---

## 9. "Relevant candidate" must be defined — answered against real code and real data

Reading `_bind_role_candidates` directly (`sufficiency_mapping.py:316-377`) settles several of these questions
concretely rather than speculatively:

- **Unit eligibility today:** a unit is eligible for a role if `is_admissible(role_spec, unit.get("flags", {}))`
  — i.e., none of the role's `disqualifying_guards` flags are set on that unit (today, uniformly `["hedged"]`
  for every real `achieved_outcome_predicate` role in this contract — confirmed by enumerating all seven such
  roles in the real map: `c1, c2, c3, c4, c8, c10, c12`, every one `disqualifying_guards=["hedged"]`). There is
  **no topical-relevance check inside this function at all** — relevance was already decided upstream, by
  whatever assembled `units` (retrieval/mapping scope), before this function ever sees them.
- **Local-assertion relevance:** currently **undefined** at the assertion level — the function tests only
  `_deterministic_text_for_role(role_spec, unit["passage"])`, i.e. "does this whole passage contain a result
  predicate," never "does *this specific assertion* bear on *this role's target*." This is exactly I4-1d's §9
  gap, confirmed again here by direct code reading.
- **Does the role carry a target term today? No, never, for the real contract.** Every one of the 7 real
  `achieved_outcome_predicate` roles in `17_sufficiency_map.json` has `requested_category_terms: []` (§10
  below). There is zero target-term signal anywhere in this contract for this strategy today.
- **What currently prevents an unrelated result assertion in the same passage from becoming candidate support?
  Nothing, structurally — and the real data demonstrates this is not hypothetical.** `c8`'s five
  `relationship_to_bias_manifestation` instances (one per trait: attractiveness/trustworthiness/anger/
  dominance/threateningness, each independently model-nominated for the *sibling* role
  `individual_difference_trait_or_construct` on the same instance) **all five receive the identical
  whole-passage `exact_text` and the identical `proposition_id=p41` for `relationship_to_bias_manifestation`**
  — confirmed directly in `17_sufficiency_map.json`. The deterministic binder is called once per role and has
  no per-instance parameter at all (confirmed by reading its signature: `role_spec, units, model_client=None,
  child_id=None, requirement_id=None, nomination_context=None, request_context=None, semantics_version` — no
  instance key, no sibling-role-value argument), so it necessarily returns the same first-match answer for
  every instance regardless of which specific trait that instance is actually about. The "anger" instance's
  `relationship_to_bias_manifestation` binding is, today, evidence from assertion 2 of p41 (the clause about
  anger/dominance/threateningness) *mislabeled as if it were the same evidence as* the "attractiveness"
  instance's binding (which really is about assertion 1). **This is a real, present, uninvestigated
  misattribution risk in the live corpus, not a synthetic what-if** — though it is a side effect of the
  deterministic strategy's complete absence of per-instance context, not of any provenance/admissibility
  question this audit's own scope covers.

**Distinguishing the five gates, concretely, against real code:** (1) retrieval relevance — upstream of this
module entirely, not inspected here; (2) proposition/role nomination — the `model_nomination_only` path's own
`nominate_with_model`, genuinely per-instance for *that* role, but with no mechanism to pass its own result
sideways to a sibling deterministic role on the same instance; (3) deterministic achieved-outcome matching —
today, whole-passage, no instance awareness (confirmed above); (4) target-term disambiguation — not
implemented for this strategy in any real role today (§10); (5) support admissibility — not implemented at all
(§12/§13). These are five genuinely separate mechanisms, and the real corpus shows mechanism (3)'s own
complete lack of per-instance awareness is the most consequential open question for I4-2 to resolve — more
consequential than the provenance/admissibility work I4-1e–g already designed, because it is a **misattribution**
risk (the exact defect the directive's own locked principle names as the thing that must never happen), not an
indirectness-vs-sufficiency question.

---

## 10. `requested_category_terms` prospective audit — real contract, exhaustive

Every `achieved_outcome_predicate` role in the real v4 map (not a stub) was enumerated:

| child | requirement | role | `requested_category_terms` |
|---|---|---|---|
| c1 | neural-manifestation | neural_manifestation_evidence | `[]` |
| c2 | behavioral-manifestation | behavioral_manifestation_evidence | `[]` |
| c3 | attitude-manifestation | attitude_manifestation_evidence | `[]` |
| c4 | specific-region | region_bears_on_bias_evidence | `[]` |
| c8 | trait-construct | relationship_to_bias_manifestation | `[]` |
| c10 | culture-existence | bias_evidence_in_population | `[]` |
| c12 | intervention-effectiveness | observed_effect_or_outcome | `[]` |

**Non-empty: 0 of 7. Empty: 7 of 7.** No useful target wording exists elsewhere on these `RoleSpec`s either —
each one's only wording field, `source_wording_span`, is the *raw research question text* ("how does the
anomalous is bad bias manifest in brain"), not a per-trait term list; it answers "what was the researcher
asking about this child," never "which specific candidate value this instance wants." **It cannot be
populated deterministically from existing authored wording without q_aib-specific vocabulary**, because the
per-instance values this role actually needs (the five trait words for c8) are not static, authored facts at
all — they are themselves the *output* of the sibling role's own per-instance model nomination (§9). Populating
`requested_category_terms` here would require either (a) authoring five separate static roles instead of one
multi-instance role (a contract-shape change, out of scope), or (b) a genuinely new, dynamic,
instance-local disambiguation mechanism that reads a sibling role's already-bound value for *this instance*
and uses it as the disambiguating term — which is architecturally different from, and not expressible by,
I4-1e/I4-1g's static authored-list design. **This is named here as a real design gap for I4-2 to decide on
purpose, not something to silently patch around by stuffing authored guesses into the field.**

**Real multi-assertion bindings left unresolved by the empty field today:** exactly the c8/p41 case walked
through in §6/§9 — all five instances resolve the same way, and nothing currently distinguishes them.

---

## 11. Attachment-ambiguity rule — applied to real recovered candidates

Applying I4-1g's own reference contract (`reference_future_role_state`) conceptually to the real 15 bindings,
using the `assertion_authority`-keyed assertion spans from §5–6 (not `achieved_outcome_span`'s own narrower
layer, per §6's finding) as the attachment unit:

| Class | Real roles | Which |
|---|---|---|
| **Filled** (≥1 admissible candidate) | 11 of 15 bindings | p1, p4 (×3), p8, p24, p41 (×5) — all `current_document`/`result` |
| **Would move to `missing`, not `ambiguous`, under §8's default** (only candidate is `support_policy_excluded`, none attachment-ambiguous) | 4 of 15 | p11 (×2, `unresolved`/`result`), p30 (`unresolved`/`result`), p31 (`unresolved`/`interpretation`) |
| **Ambiguous** (no admissible candidate + an attachment-ambiguous relevant candidate) | **0 of 15**, under assertion-level keying | — |

**Zero bindings land in `ambiguous` once attachment is keyed to `assertion_authority`'s own spans.** This is
the opposite of what a naive reading of I4-1d §10 ("p41 is genuinely ambiguous") would predict, and it is the
single most important correction this audit makes to the prior sessions' own framing: **the directive's
"pay particular attention to p41" instruction is answered, concretely, as "p41 is clean once keyed correctly;
the apparent ambiguity was an artifact of a different, narrower, intentionally-duplicated boundary
implementation — not evidence that the attachment-ambiguity *rule itself* needs special-casing for p41."**

If I4-2 instead keys attachment to `achieved_outcome_span`'s own predicate-match boundaries (the narrower,
currently-available unit), p41 *would* fall into `ambiguous` by the same reference rule (2 of 3 raw matches are
mutually `ambiguous_with`, and the third is itself only "unambiguous" because it is in a separately-clause-split
region) — so the production choice of *which span layer attachment keys to* is not cosmetic; it changes p41's
own outcome class. **Recommendation: key to `assertion_authority` spans, not `achieved_outcome_span` matches,
precisely because the former already resolves exactly this ambiguity via real embedded-content grammar that
the latter was deliberately built not to duplicate.** `achieved_outcome_span`'s own matches remain useful as
the tighter `content_span`/`predicate_span` *within* an already-resolved assertion (§8's `exact_text`
recommendation), not as the top-level attachment-ambiguity unit.

---

## 12. Support-policy default: exact executable semantics, checked against real data

The compound predicate from I4-1e §8 — `kind == result and not (relation == unresolved and aggregation ==
non_synthetic_or_unspecified)` — was applied to the real 64-assertion sweep (§5):

| Outcome under the default | Count | Share |
|---|---|---|
| Admissible | 23 | (24 `current_document`/result − 0 excluded by kind, + the 2 `attributed_external`/result, − 0 excluded; `current_document` 22 result + `attributed_external` 1 result) |
| Excluded — `unresolved` + non-synthetic | 24 | every `unresolved`/`result` assertion |
| Excluded — wrong `assertion_kind` (not `result`) | 17 | 12 interpretation + 3 method_or_description + 1 aim_or_hypothesis + 1 unknown |

(23 + 24 + 17 = 64. ✓)

**`RoleSpec` has no `support_policy` ≠ `RoleSpec` has `new_support_policy()`'s own defaults, and this
distinction is now empirically load-bearing, not merely an API nuance.** `new_support_policy()`'s own keyword
defaults are `allowed_assertion_relations=(current_document, attributed_external, unresolved)` — i.e. **all
three relations, unconditionally** — `aggregation_requirement="any"`, `allowed_assertion_kinds=("result",)`.
Applied literally to the real data, that *explicit*-but-default-valued policy would admit **every** `result`-
kind assertion regardless of relation/aggregation — **38 unresolved-result assertions that the §8 *compound*
default would correctly exclude.** Confirmed directly: I4-1g's own §4 states the compound default "is not
implemented at all, by design" — no code anywhere computes it. **This means a role that omits `support_policy`
today has, as of I4-1g, *no* admissibility behavior defined at all** (I4-2 hasn't wired anything), and if I4-2
were to naively treat "no policy → construct `new_support_policy()`'s own keyword defaults" as the implementation
of "the default," it would silently implement the **wrong, more permissive policy** — the one I4-1e's own §0.3
correction ledger explicitly rejected as self-contradictory. **This is a real, concrete maintenance trap,
exactly the kind the directive's §12 worried about, confirmed with real numbers: 24 real assertions distinguish
the two defaults.** I4-2 must implement `default_support_policy(relation, aggregation, kind)` as its own
explicit function — never derive it from `new_support_policy()`'s constructor defaults.

---

## 13. Explicit `support_policy` semantics — defined, and one expressibility gap named

- **`allowed_assertion_relations`:** set membership — a candidate is relation-admissible iff its
  `assertion_relation` is in this frozenset. Unconditional; does not vary by `aggregation` or `kind`.
- **`allowed_assertion_kinds`:** set membership — unconditional, does not vary by relation/aggregation.
- **`aggregation_requirement`:** `"any"` — no constraint; `"require_synthesis"` — admissible iff
  `aggregation == literature_synthesis`; `"exclude_synthesis"` — admissible iff `aggregation ==
  non_synthetic_or_unspecified`. Unconditional; does not vary by relation/kind.
- **Overall:** a candidate is admissible iff **all three** independent membership tests pass (logical AND of
  three orthogonal, unconditional gates).

**Expressibility gap, confirmed by the §12 analysis: the compound default (`unresolved` admitted only when
`aggregation==literature_synthesis`, every other relation admitted regardless of aggregation) is a
*conditional* rule over the `(relation, aggregation)` pair and is provably NOT expressible as three
independent, unconditional set-membership gates.** No choice of `allowed_assertion_relations` +
`aggregation_requirement` can encode "admit `unresolved` only when synthesis, but admit `current_document`/
`attributed_external` regardless of synthesis" — the schema's `aggregation_requirement` field has no way to
apply only to a subset of relations. **This is not a defect in I4-1g's schema for the *explicit*,
author-overridable case** (an author who genuinely wants one uniform rule across all allowed relations is
well served by it, and the four worked cases in I4-1e §7 are all uniform in exactly this way) — **it is
specifically the *default* predicate that cannot be represented as an instance of this schema.** I4-1e's own
§8 already flagged this ("not expressible as three independently-defaulted set memberships… an I4-1g/I4-2
implementation choice, not locked here") and I4-1g did not resolve it. **Decision: the default stays a
separate, hard-coded function, never a `support_policy` dict instance; an authored override is layered on top
of (and can supersede any subset of) that function's behavior, exactly as I4-1e's own closing sentence in §8
anticipated — this is an acceptable, final design, not a gap requiring a fourth schema field, because no real
role in this contract needs a conditional rule for its own *authored* policy (every real
`achieved_outcome_predicate` role today omits `support_policy` entirely and would rely on the default alone).**

---

## 14. `authority_veto` integration — design confirmed, zero real exercise

I4-1e §9's design (veto blocks admissibility only for the specific positive-outcome-shaped role targeting the
embedded negated claim; the same vetoed assertion remains fully legitimate for an adjacent "was this tested"/
"what null findings exist" role) is already complete and sound on paper, and needs no revision here. **Real-data
status: zero of the 64 real assertions carry a non-null `authority_veto` (§5)**, so this mechanism is, like
`aggregation=literature_synthesis`, entirely unexercised by the real preserved corpus — any I4-2 byte-diff will
show zero veto-driven change here too, for the same "trigger never occurred in this sample" reason as §5.

**On reusing `category_polarity.py` conceptually:** read directly (`category_polarity.classify_category_
observation(text, term, ...)`), it answers "is this *specific named term*'s occurrence negated/present/unknown"
— it is parameterized by an explicit candidate term string, because category roles always have one (the
candidate value itself is the term being searched for). `achieved_outcome_predicate` roles have no such
named term — the "outcome" is the predicate's own result-claim, not a separately-nameable candidate string.
**Conceptually the two modules solve the same general shape of problem (does this clause negate/exclude its
own anchor) but are not code-reusable, because achieved-outcome roles have nothing to hand `category_polarity`
as its required `term` argument.** `authority_veto`'s own existing, independent, predicate-structure-based
negation/absence-of-evidence detection (I4-1c) is the correct, already-built mechanism for this role family;
`category_polarity` should stay scoped to `explicit_category_terms`/cardinality roles. No coupling is
recommended or needed.

**No separate target-polarity field is required beyond what exists.** `achieved_outcome_predicate`'s own
semantic_goal is inherently positive-outcome-shaped by construction in this contract (every real role asks
"was X observed," never "was X tested" as a separate requirement) — so the I4-1e §9 design's narrower question
("does the role ask about the positive outcome, or about whether testing/null-finding occurred at all")
currently has only one real answer in this contract. A future contract that *does* author a "was this tested"-
shaped role would need its own `RoleSpec` wording to say so; nothing here infers that from `mapping_strategy`
alone, by design, and that remains correct.

---

## 15. Caption semantics — zero real cases, answered by design intent

**Zero of the 54 real sealed quotes are caption-sourced** (none begin with `Figure`/`Table`/`Fig.`, and the
ledger's own schema has no `is_caption` field at all — `is_caption` is a parameter the *caller* must supply
from chunk-structure knowledge the classifier itself never infers from text). This is a genuine negative
finding, not an omission: **there are no real preserved caption cases in this corpus to examine.**

**Answer to the design question anyway, since I4-1 already specifies the mechanism precisely:**
`is_caption` is **not** a global admissibility veto by itself — it is provenance/display metadata that forces
`finding_authority` to `candidate` (never `authoritative`) for that one (assertion, target) pair, exactly
mirroring `authority_veto`'s own scoped behavior (I4-1 §5, unchanged through every subsequent increment). It
should retain exactly that role under the new `candidate_supports` design: a caption-sourced candidate is
fully retained, fully inspectable, carries `is_caption=True` on its own record, and is excluded from
admissibility only insofar as the role's `support_policy`/default predicate's relation/kind gates happen to
exclude it for an unrelated reason (a caption can be `current_document`/`result`, perfectly admissible). **No
conjunction with another rule is needed beyond what already exists; this requires no new design work, only
the observation that the real corpus never exercises it.** A forward-looking note, not actionable here: the
H1a `chunk_structure.chunk_type` substrate (CLAUDE.md, inc 577) is a plausible future *source* for a real
`is_caption` signal (it is explicitly non-load-bearing today), but wiring it is out of this audit's scope.

---

## 16. Existing `disqualifying_guards` vs. support-policy: gate order and independence

Specified precisely, against real code and the real contract:

| Gate | Removes candidate entirely? | Retains as `candidate_supports[...]` with `admissible=False`? | Changes role state? | Metadata-only? |
|---|---|---|---|---|
| 1. Mapping/retrieval relevance (upstream of `_bind_role_candidates`, never this layer's job) | Yes — a unit never offered to this function at all is simply absent from `units` | n/a | n/a | n/a |
| 2. `disqualifying_guards` (today: `is_admissible`, a hard `continue` in the unit loop) | **Yes, today** — a guard-failing unit is skipped before any detector even runs, never recorded anywhere | **No, today** — and this is a real tension with the new design's own stated principle | n/a (today) | n/a (today) |
| 3. Local assertion attachment (I4-1d spans) | No | Retained — multiple assertions in one passage all become separate candidates | No by itself | — |
| 4. Attachment ambiguity (I4-1g's `assertion_attachment_ambiguous`) | No | **Yes — `admissible=False`** | Only via aggregation (role → `ambiguous` iff no admissible candidate exists and this reason is present) | — |
| 5. Assertion descriptors (I4-1f: relation/aggregation/kind/label) | No | Carried on the record | No by themselves | Yes — pure metadata |
| 6. `support_policy` (I4-1g schema / §12-13's default) | No | **Yes — `admissible=False`, `inadmissibility_reason="support_policy_excluded"`** | Only via aggregation (role → `missing` if every candidate is excluded this way) | — |
| 7. Target-specific `authority_veto`/`is_caption` (I4-1e §9, not yet coded) | No | Carried on the record; affects only that specific (assertion, target) pair's admissibility, never globally | Only for the specific positive-outcome role it targets | — |

**A real, concrete inconsistency this audit surfaces: gate 2 (`disqualifying_guards`) today behaves like the
*old*, discard-everything architecture (a hard `continue`, nothing retained), while gates 4/6/7 are designed,
per I4-1e §4's own explicit instruction ("inadmissible evidence must remain inspectable… never gate
existence"), to retain-and-flag instead.** Every real `achieved_outcome_predicate` role in this contract
declares `disqualifying_guards=["hedged"]` (§9), so a hedged unit is *silently and totally invisible* today —
not even recorded as an excluded candidate — which is exactly the opposite of the new design's own
stated principle for every other gate. **This is a real, pre-existing architectural inconsistency I4-2 should
resolve on purpose: either gate 2 is brought into the same retain-as-inadmissible discipline as gates 4/6/7
(consistent, but a behavior change to a mechanism that predates this whole design track), or it is explicitly
and permanently exempted as "pre-filtering, not admissibility" with a stated reason — but the current silent
asymmetry should not simply carry forward unexamined into I4-2.**

---

## 17. Read-only I4-2 simulator — what was actually run

Built as two disposable scratch scripts outside the repository (`/tmp/sweep.py`, `/tmp/sweep2.py`, under this
session's own OS temp directory — **not** committed, **not** imported anywhere, per the directive's own
preference). Inputs: the recovered `11_verified_ledger.json` (54 real quotes) and the recovered
`17_sufficiency_map.json`/`.initial.json` (the real v4 map). Machinery used, unmodified: `assertion_authority
.classify_target_assertions`, `.assertion_relation`, `.support_label`; `achieved_outcome_span
.find_achieved_outcome_matches`. No `RoleSpec`/`candidate_supports` production object was constructed (I4-1g's
own builders were inspected and reasoned about directly in §7–13 above rather than invoked, since doing so
would have required authoring exactly the `support_policy`/per-candidate inputs this audit's own findings
show are not yet well-defined for the real contract — authoring them here would have pre-empted the very
decisions this audit exists to surface).

**Per-role prospective projection** (CURRENT v4 vs. PROSPECTIVE, under §8's compound default + assertion-level
attachment keying per §6/§11):

| Role (child) | CURRENT v4 | PROSPECTIVE candidate_supports | PROSPECTIVE state |
|---|---|---|---|
| c1 neural_manifestation_evidence | filled, p1, whole passage | 1 candidate, admissible (current_document/result) | **filled**, unchanged |
| c2 behavioral_manifestation_evidence (×3) | filled, p4, whole passage | 1 candidate, admissible | **filled**, unchanged |
| c3 attitude_manifestation_evidence | filled, p8, whole passage | 1 candidate, admissible | **filled**, unchanged |
| c4 region_bears_on_bias_evidence (×2) | filled, p11, whole passage | 1 candidate, `unresolved`/result → **inadmissible** (`support_policy_excluded`) | **missing** (changed) |
| c8 relationship_to_bias_manifestation (×5) | filled, p41, whole passage (identical across all 5 instances) | 2 candidates per instance (assertion 1 admissible/current_document; assertion 2 inadmissible/unresolved), **identical across all 5 instances** (§9's own finding — nothing here fixes the per-instance mismatch) | **filled**, unchanged state, but now exposes the real span distinction §9 flags |
| c12 observed_effect_or_outcome, inst. 0 | filled, p24, whole passage | 1 candidate, admissible | **filled**, unchanged |
| c12 observed_effect_or_outcome, inst. 2 | filled, p30, whole passage | 1 candidate, `unresolved`/result → **inadmissible** | **missing** (changed) |
| c12 observed_effect_or_outcome, inst. 3 | filled, p31, whole passage | 1 candidate, `unresolved`/interpretation → **inadmissible** (also fails the kind gate) | **missing** (changed) |

---

## 18. Quantified prospective v4 → v5 diff

- **Roles unchanged:** 11 of 15 bindings (c1, c2×3, c3, c8×5, c12-inst0) — same state, same representative
  evidence (once the compatibility projection picks the admissible candidate — identical to today's single
  binding in every one of these cases, since each already had exactly one candidate).
- **Filled → missing:** **4 of 15** — c4×2 (p11), c12-inst2 (p30), c12-inst3 (p31). All four are `unresolved`-
  relation candidates excluded by the default's own compound rule; none involve `literature_synthesis` (§5's
  finding — this corpus has none), so none are rescued by the one case the correction was built to fix.
- **Filled → ambiguous:** **0.** (Contrast with a naive `achieved_outcome_span`-keyed attachment, which would
  put p41's binding into `ambiguous` instead of leaving it `filled` — see §11.)
- **Missing → filled:** none observed — this audit did not re-run full candidate *collection* (scanning every
  searched unit per child, not just the one unit the current first-match architecture happened to record), so
  a currently-invisible second admissible candidate for c4/c12's now-excluded roles **cannot be ruled out**;
  it is simply not recorded anywhere in the current v4 map to check, because the current architecture stops
  scanning after the first match regardless of its own future admissibility. **This is the one real unknown
  the full all-support-collection step of I4-2 (not simulated here) would resolve** — it could turn some of
  the four "filled → missing" cases above into "filled → filled, but from a different, now-admissible
  candidate" instead, if the broader unit pool for those children/roles happens to contain an unexamined
  `current_document`/result assertion this audit has no way to discover without re-running retrieval.
- **Proposition-id identity changes:** none of the 15 real bindings are affected by §7's duplicate-id finding
  (p1/p4/p8/p24 each own a *different* role/child, so the duplicate-passage problem never actually collides
  within one single role in this particular corpus — it is a latent risk for a future contract with two
  children sharing a target, not a live defect in this run's own 15 bindings).
- **`exact_text` changes due to local attachment:** all 11 "unchanged-state" bindings would still have a
  materially *narrower* `exact_text` under §8's recommendation (the local assertion/content span, not the
  whole passage) — a real, visible rendering change even where `state` itself does not move.
- **Newly-retained indirect evidence:** the 4 inadmissible candidates above (p11×2, p30, p31) go from
  *invisible* (not recorded anywhere, since today's architecture discards a non-matching unit silently) to
  *fully retained and inspectable* as `support_policy_excluded` — this is a strict improvement in
  inspectability even where the role itself becomes `missing`.
- **Newly-retained synthetic evidence:** none (§5 — zero real synthesis cues in this corpus).
- **Newly policy-excluded unresolved evidence:** the same 4 cases above.
- **Candidates blocked by `authority_veto`:** none (§5/§14 — zero real vetoes in this corpus).
- **Candidates affected by caption handling:** none (§15 — zero real captions in this corpus).

**Downstream consequences, described conceptually, never executed:** c4's `region_bears_on_bias_evidence`
role moving `filled → missing` would make its *instance* re-evaluate against `role_completion` (it is currently
`partially_filled`/`incomplete_instance` for the unrelated c1-style alternative-group reason at c1, but c4's
own instance structure would need the same re-check); a newly-`missing` instance becomes newly eligible for
whatever recovery-target machinery (`sufficiency_recovery_targets.py`) currently treats a `filled` instance as
settled — this is exactly the kind of downstream ripple the directive instructs **not** to actually trigger
here, and it was not triggered; it is named as the expected shape of the consequence, not measured.

---

## 19. q_aib is evaluation, not ontology — confirmed by code, not merely assertion

Every module exercised in this audit (`assertion_authority.py`, `achieved_outcome_span.py`, and I4-1g's
`sufficiency_engine.py` additions) was already independently cross-domain-tested by its own authors across
architecture/clinical/language-learning twin batteries (I4-1 §7, I4-1d §11, I4-1f §7/§8) — this audit adds no
new cross-domain battery of its own, since none of the real q_aib-specific vocabulary (`"anomalous faces"`,
`"anomalous-is-bad"`, trait names) appears anywhere in any of the three production modules' source (confirmed
directly: `grep`-level inspection of all three files for the literal corpus vocabulary returns nothing — the
only q_aib-specific material anywhere is in the frozen *test fixture* JSON files and the `_authored` provenance
notes inside the real map itself, never in executable logic). The eight generic categories the directive names
(primary empirical result; attributed prior result; review synthesis; meta-analysis's own pooled result;
definitional/descriptive support; null/absence-of-evidence result; source-specific "this study" question;
multi-assertion ambiguous passage) are each already covered by an existing minimal pair or twin case in the
I4-1/I4-1c/I4-1d/I4-1f batteries, independent of q_aib — confirmed by direct cross-reference, not re-derived
here.

---

## 20. Simple Ask consequence

Confirmed directly, not merely asserted: none of `assertion_authority.py`, `achieved_outcome_span.py`, or
I4-1g's `sufficiency_engine.py` additions import anything from `decompose/`, `hierarchy_contract.py`,
`e2e.py`, or any `answer_plan/` file (the import lists at the top of each file were read directly in this
audit — §-by-§ above). The proposed support-policy/candidate-supports machinery operates on raw text and a
`RoleSpec`; nothing in it is reachable only through hierarchical decomposition.

**On "What is the placebo effect?" specifically:** this is I4-1e §7's own worked case 3 (a definitional ask).
Under the §8 *default*, it would **not** be well-served — the default's `allowed_assertion_kinds` is `{result}`
only, so a purely descriptive/definitional sentence (`method_or_description`/`interpretation` kind) is excluded
by *kind*, regardless of relation or aggregation. This is correct, deliberate, and already named in I4-1e §7
("plus `interpretation`, opt-in") — but it means the *default* alone would make descriptive/review evidence
globally inadmissible for a role that forgot to opt in, which is exactly the failure mode §9/§20 of the
directive is alert to. **The honest answer: nothing in this design makes descriptive/review evidence globally
inadmissible for a *well-authored* role (one that explicitly sets `allowed_assertion_kinds` to include
`method_or_description`/`interpretation`, as I4-1e's own case-3 table already specifies) — but the bare,
unauthored default would silently exclude it, by kind, for any role that assumed the default covers
"general evidence" without naming its own kind set.** This is a real authoring-discipline obligation for
Simple Ask's own contract-authoring step, not a code gap — named here so it is not rediscovered the hard way.

---

## 21. Versioning decision

**Recommendation: split into two semantics boundaries, mirroring the H1a/H1b non-load-bearing-substrate
precedent already established elsewhere in this codebase (CLAUDE.md, inc 577/578: additive, non-consumed
structure ships first and is proven non-load-bearing by a static test; only a later increment that actually
reads it bears a version/behavior consequence).**

- **No version bump:** local assertion-span attachment (I4-1d, already shipped, unwired) and the
  `candidate_supports` collection step **by themselves**, *if* I4-2a (§22) ships them as purely additive,
  inspectable metadata on top of the existing single-binding output, with the existing `state`/`proposition_id`/
  `exact_text` computation left **byte-identical** to today (first-admissible-whole-passage-wins) for every
  real contract. This is directly analogous to H1a/H1b's own "nothing on the retrieval path reads it" posture
  and should carry the identical proof obligation (a static test asserting no consuming module reads the new
  structure to decide anything — the same shape of guard I4-1g's own §6/§10 guards already are).
- **`sufficiency-semantics-v5`:** the point at which `support_policy` admissibility actually gates a binding's
  `state` (filled/missing/ambiguous) and/or `exact_text` narrows from whole-passage to local span **for real
  contracts, observably**. §18's own diff (4 of 15 real bindings flip `filled→missing`) is the concrete,
  measured justification for why this is a real behavior boundary, not a cosmetic one. This matches I4-1e §8's
  own "schema compatibility ≠ semantic-output parity" distinction exactly, and should be the only thing that
  triggers the bump.
- **Local assertion-span attachment used only for `exact_text` narrowing without any admissibility gating** is
  a defensible middle ground (§8's recommendation) but should still be treated as v5-worthy if it changes
  `exact_text`'s rendered content for any real binding — which §18 shows it would, for all 11 "unchanged-state"
  bindings. **If I4-2a narrows `exact_text` at all, it needs the v5 bump even without touching `state`; only
  a version that changes *neither* `state` nor rendered `exact_text` content can skip the bump.**

---

## 22. Should I4-2 be one increment?

**Recommendation: split, explicitly, into I4-2a and I4-2b — not for convenience, but because §18's own real
diff shows the two pieces have measurably different blast radii, and §21 shows they cross the version
boundary at different points:**

- **I4-2a — local span attachment + candidate-support collection, no admissibility/state-policy change.**
  Wires I4-1d's spans and I4-1g's `candidate_supports` schema into `_bind_role_candidates`, but keeps today's
  first-admissible-unit-wins `state` computation untouched; every candidate found (including ones that would
  later be `support_policy_excluded`) is recorded and inspectable, but `state` is still computed exactly as
  today. §21's bump decision: **only if `exact_text` narrows** (recommended it does, per §8) — then this is
  already `sufficiency-semantics-v5` by the rule above, even though no `state` output changes. This increment
  should ship with its own real-corpus byte-diff proving `state`/`proposition_id` are unchanged for all 15
  real bindings (a tractable, bounded check, unlike §18's own necessarily-incomplete one above) and that only
  `exact_text` narrows plus `candidate_supports` appears as new, additive detail.
- **I4-2b — `support_policy` admissibility gating + attachment-ambiguity role-state aggregation.** This is the
  increment that actually changes `state` for real bindings (§18's 4-of-15 diff), requires the
  `default_support_policy` function from §12/§13, requires resolving §16's `disqualifying_guards`
  inconsistency on purpose (even if the resolution is "leave it as pre-filtering, documented"), and requires
  re-running the full all-support-collection step (not simulated here) to settle the one real open question
  in §18 (whether any of the four now-excluded roles have a currently-invisible admissible alternative). This
  is the increment the directive's own §12/§13 is really probing, and it is the one that should carry the
  `sufficiency-semantics-v5` identity if I4-2a did not already claim it for `exact_text` narrowing alone.
- **Do not fold §9's per-instance misattribution finding (c8/p41's five identical bindings) into either.** It
  is a real, present defect, but it is a **different kind of defect** from everything else in this track — a
  missing disambiguation mechanism, not an admissibility/provenance question — and conflating its fix with
  I4-2a/b risks exactly the kind of scope creep the directive's own §22 instruction warns against ("prefer the
  smallest empirically auditable semantic step"). It should be its own, later, explicitly-scoped increment,
  informed by but not blocking I4-2a/b.

---

## 23. Required decisions

**P1. Preserved 54-quote baseline recovered/reconstructed?** Recovered, from the primary source
`run/11_verified_ledger.json` (`.local/e2e-runs/phase28-live-parent-synthesis-attempt2-20261004T014500Z/run/`,
SHA-256 `a70409e8f5a0937f414c73c4796b293c6c1a9ef3b31c7fc83bbfa61794c6bd5d`, `sealed_hash`
`1dce0e1c2dead992c631f9eb9bfaaa4fc29cabb30ec9304687df515cd4abeef8`), predating I4-1d/f/g's own sessions by
mtime. **Semantic reconstruction verified** against nine independent prior-report facts, zero disagreements.
**Byte identity to the historical `frozen_54_inputs.json` convenience copy is unavailable** (its exact
serialization was never itself recorded) and is not needed, since the recovered artifact is the richer primary
source that file was derived from, not a second-hand stand-in.

**P2. v4 map baseline recovered/reconstructed?** Recovered: `run/17_sufficiency_map.initial.json` (SHA-256
`46a213044bc6211702fa89710268e1bfb6c4fc348259727a46cb238ef5bbc14e`) as `initial_v4`; `run/17_sufficiency_map
.json` (SHA-256 `28478500e485137cd6930b8010d274bb1da3afd48e7f4a6208dd183610d9ca0b`) as `final_v4`. Structural
identity to I4-1d's own published 15-binding/8-proposition table is exact, cell-for-cell. The one known
limitation: live model-nomination call provenance (not deterministic bindings) cannot be independently
re-derived offline, and is not claimed to be.

**P3. Candidate-support proposition identity rule.** `supporting_proposition_ids: [...]` (plural), never a
singular `[0]`-indexed `proposition_id`, whenever more than one ledger row shares a matched passage — the
deterministic `achieved_outcome_predicate` path should adopt the same plural-provenance shape the
`model_nomination_only` path already uses. A singular display id may still be projected from the plural list,
never the reverse.

**P4. Candidate-support `exact_text`/source-context rule.** Two separate fields: `exact_text` = the local
matched content span (I4-1d's `content_span`, once wired) — never the whole passage; source relocation rides
on the existing `proposition_id`/chunk-anchor provenance, never on widening `exact_text` itself.

**P5. Definition of "relevant candidate."** Five distinct gates, named precisely in §9, none of which
currently supplies per-instance disambiguation for the deterministic `achieved_outcome_predicate` strategy —
confirmed live in the real contract (c8's five instances, §9/§11).

**P6. `requested_category_terms` state and future use.** 0 of 7 real `achieved_outcome_predicate` roles
populate it; it cannot be populated from existing static authored wording for the one real multi-instance case
that would need it (c8), because that case's own disambiguating value is itself dynamic, per-instance,
sibling-role-sourced — a genuinely different mechanism from I4-1e/g's static authored-list design, named as an
open gap, not patched here.

**P7. Attachment-ambiguity production rule.** Key attachment to `assertion_authority`'s own assertion/content
spans, not `achieved_outcome_span`'s independently-duplicated predicate-match boundaries. Under that keying,
**0 of the real 15 bindings land in `ambiguous`** — p41 specifically resolves clean, contrary to a naive
reading of I4-1d's own report (§6/§11). 4 of 15 land in `missing` (policy-excluded, not ambiguous).

**P8. Absent-policy default exact semantics.** The compound predicate from I4-1e §8, implemented as its own
hard-coded function — never derived from `new_support_policy()`'s own keyword defaults, which are
*more permissive* and would (confirmed with real numbers, §12) wrongly admit 24 real `unresolved`/result
assertions the compound default correctly excludes.

**P9. Explicit `support_policy` exact semantics.** Three independent, unconditional set-membership/enum gates,
ANDed (§13). Confirmed: this schema cannot express the *default's* own conditional rule — that is acceptable,
because no real authored role needs a conditional rule of its own; only the default does, and the default is
not an instance of this schema.

**P10. `authority_veto` integration rule.** I4-1e §9's design stands unchanged. `category_polarity.py` is
conceptually analogous but not code-reusable (no named term to hand it for an achieved-outcome role). Zero
real exercise in this corpus (0 of 64 assertions carry a veto).

**P11. Caption integration rule.** Provenance/display metadata forcing `finding_authority=candidate`, never a
global veto — unchanged design, zero real cases to examine in this corpus.

**P12. Existing guard vs. support-policy gate order.** Specified in full in §16. One real, named inconsistency:
`disqualifying_guards` today hard-discards (no retained record) while every I4-1e/g-designed gate retains and
flags — I4-2 must resolve this asymmetry on purpose, not inherit it silently.

**P13. Prospective v4 → v5 diff.** 11 of 15 real bindings unchanged in `state`; 4 of 15 flip `filled→missing`
(none rescued by the literature-synthesis correction, which this corpus never triggers); 0 become `ambiguous`
under correct (assertion-level) attachment keying; the one real open question (a currently-invisible admissible
alternative for the 4 excluded roles) requires live all-support re-collection to settle, which this audit does
not perform.

**P14. Expected recovery consequences.** Named conceptually in §18 (instance/`role_completion` re-evaluation,
recovery-target eligibility change for newly-`missing` instances) — not executed, per the directive.

**P15. Semantics-version boundary.** `sufficiency-semantics-v5` triggers the first time `exact_text` narrows
to a local span for any real binding, OR the first time `support_policy` admissibility changes any real
`state` — whichever ships first (§21). Schema additions alone (I4-1f/I4-1g, already shipped) do not trigger it,
confirmed unchanged throughout this audit.

**P16. One I4-2 vs. split I4-2a/I4-2b.** **Split**, per §22: I4-2a (span attachment + candidate-support
collection, `exact_text` narrowing, no admissibility change) then I4-2b (`support_policy` gating +
attachment-ambiguity aggregation + the real all-support-collection re-run). The c8/p41 per-instance
misattribution finding (§9) is explicitly **excluded from both** and should be its own later increment.

**P17. READY / NOT READY for the next implementation increment.** **READY for I4-2a, exactly as scoped in
§22**, with the real-corpus baseline now recovered and independently re-verified (§2–§6) and the `exact_text`/
proposition-identity decisions made (P3/P4). **NOT READY for I4-2b** until `default_support_policy` is written
as the explicit function P8 requires, the §16 guard-asymmetry decision is made on purpose, and a live
all-support-collection run (not simulated here) settles the one real open question in §13/§18.

---

## 24. Deliverable

This file: `experiments/ask_cli_revised/PHASE34_I4_1H_PRE_I4_2_INTEGRATION_AUDIT.md`. Planning/read-only audit
only. A `CONTRIBUTION-LINEAGE.md` append follows, per existing audit convention.

**Files touched by this increment:** this report, and `CONTRIBUTION-LINEAGE.md` (appended). Nothing else —
confirmed by `git status --porcelain` after writing both. No `.py` file under `experiments/ask_cli_revised/`
was modified. No test file was added or changed. No frozen battery, pin, or version constant was touched. The
two scratch sweep scripts that produced §5/§6/§9/§11–§13/§17's empirical numbers live outside the repository
(`/tmp/sweep.py`, `/tmp/sweep2.py`, this session's own OS temp directory) and were never imported anywhere,
per the directive's own "prefer scratch" instruction.

---

## 25. STOP

STOP after this audit, as instructed.

**Not implemented in this increment:** I4-2 (neither I4-2a nor I4-2b). No version bump. No wiring of
`support_policy`, `candidate_supports`, `assertion_authority`, or `achieved_outcome_span` into any production
mapping, recovery, relation, direction, effectiveness, or AnswerPlan path. I2-3 not begun. No model, network
search, or live end-to-end run was performed anywhere in this audit — every number above comes from running
already-shipped, already-tested, pure Python functions against already-existing, newly-located local files.
