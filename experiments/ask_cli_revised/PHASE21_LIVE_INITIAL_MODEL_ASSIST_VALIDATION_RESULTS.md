# Phase 21 (restart) — one bounded, production-shaped LIVE initial model-assisted sufficiency validation

**Restarted** (Cliff Workman, 2026-10-02, pasted-content-id-d898) from a corrected, full-contract
state after the original Phase-21 preflight found a real Phase-19 request-multiplicity gap on real
`c12` and Phase 19b (commit `23a7f164`) repaired it. **Exactly ONE live run occurred. No retry. No
c12 exclusion. No production code changes. No recovery execution. No Phase-22 remapping.**

## Preflight / authorization

- **Pre-run HEAD:** `23a7f164c132e4aa060ee2d499c1e7dc28255297` (Phase 19b) — matched the brief's
  expected HEAD exactly.
- **Tree state:** clean except the one intentionally-preserved untracked diagnostic harness
  (`phase21_live_initial_model_assist_validation.py`) — confirmed throughout the run and again
  afterward (`git diff --stat HEAD -- '*.py'` excluding the harness is empty).
- **Phase 19b commit present at HEAD; Phase 20a (`b928d140`)/20b (`304ad5ad`) present in lineage.**
- **Frozen v9 `combined_hash`:** reconfirmed `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.
- **Phase 21 had not previously started; zero live calls had been made; the one-run/no-retry
  authorization was unused** — all confirmed true before this run.

**Section 0 offline assertion (verified before any network use):** under
`exact_scope_set_policy(set())`, a new `request_context` with no U1 prior receipt is NEVER
authorized for a fresh call (`is_authorized_for_fresh_call` returns `False` for *every* scope under
an empty `exact_scope_set`, independent of `request_context`), and its prior-receipt lookup under the
new composite key correctly misses (`None`), yielding zero fresh call, no sibling-context borrowing,
and status `held_fixed_no_valid_prior` — confirmed both by direct code reading
(`sufficiency_model_scope.py:303-317`) and by re-running the two already-committed Phase-19b tests
covering exactly this case (`RequestContextTests::test_u2_new_post_recovery_context_gets_no_prior_
receipt_and_zero_fresh_call`, `RealV9FullContractReplayTests::test_u2_never_borrows_a_sibling_
request_contexts_receipt`) — both passed. Proceeded directly per instruction.

**Fresh-call cap, mechanically derived (candidate construction only, no live call):** running the
real, unmodified `compute_diagnostic_sufficiency_map` against the real frozen v9 contract and the
real preserved sealed evidence with a counting-only fake client (never asserting a nomination)
produced exactly **14** nonempty, `fresh`-status composite request keys, against **15** declared
semantic scopes (`enumerate_model_nomination_scopes`). This derivation was re-run live, in-process,
immediately before authorization was written, and matched this value exactly — the hard cap used for
the actual run was this freshly-derived 14, not the stale Phase-19 declared-scope count of 15 (which
Phase 19b's composite key makes an incorrect upper bound: it undercounts `c12`'s real two-context
split and overcounts `c9`/`c11`'s two declared-but-unreached scopes). A pre-live, non-consuming
dirty-tree preflight abort (the harness's own `git status` check had not yet been taught to tolerate
its own untracked existence) was fixed in the harness before any network touch — confirmed
non-consuming since it occurred before `OllamaClient` construction.

## Run identity

- **Model:** `qwen3.5:9b` · **think:** `False` · **endpoint:** `http://127.0.0.1:11435` (JUNO,
  isolated).
- **Question:** `aib` (the canonical q_aib question/hierarchy; `question_sha256`
  `6e037bab4baad2c0b4427a1c73c6e1720296292b3be36189cd9cf02436e57030`).
- **Full-contract confirmation:** the real sufficiency contract has exactly 11 children
  (`c1,c2,c3,c4,c5,c6,c8,c9,c10,c11,c12`, no exclusions); the real preserved sealed evidence
  (2026-09-30 T5C live run's own verified ledger, confirmed byte-identical `question_hash` and
  hierarchy `integrity_sha256` to the hierarchy loaded for this run) was used directly, since a
  hierarchical `execute()` cannot be seeded and this keeps the live footprint exclusively to
  sufficiency nomination.
- **Run id:** `phase21-live-initial-model-assist-validation-20261002T195945Z`.

## Call accounting

| Metric | Value |
|---|---|
| Declared semantic scopes | 15 |
| Reached composite request keys | 14 |
| `fresh_no_candidates` | 0 |
| Nonempty (fresh) request keys | 14 |
| Physical live calls (U1) | 14 |
| Successful calls | 14 |
| Mechanical failures | 0 |
| Successful calls with `accepted=[]` | 9 |
| Successful calls with ≥1 accepted (post-dedup) | 5 |
| Raw model-proposed items (pre-grounding) across all calls | 25 |
| Accepted nominations (post-grounding/dedup) | 11 |
| `memoized_in_pass` reuse count (U1) | 0 (no repeated composite key was resolved twice in U1) |
| U1 wall time | 70.328 s |
| U2 fresh calls | **0** (required) |
| U2 wall time | 0.078 s |

Every physical call's `(scope, request_context)` is unique — no duplicate call for the same composite
key/fingerprint pair occurred. The 3 declared scopes never reached (`c9`'s one role, `c11`'s two
roles) cost zero calls, consistent with the offline derivation; this reflects the real evidence
having no admissible candidate units for those roles this pass, not an infrastructure gap.

**A real, informative distinction confirmed from the raw trace** (`qwen_calls.jsonl`, 14 entries,
one per physical call): the call-log's own `n_accepted` reflects the **raw** model output count
*before* `nominate_with_model`'s grounding (`canonical_text_contains`) and anchor-based dedup —
e.g. call #2 returned 2 raw items (`p2`, `p11`, identical text) that correctly collapsed to 1
grounded nomination (`supporting_proposition_ids: ["p11","p2"]`) because both share the same
physical anchor. This is expected, correct behavior, not a discrepancy — verified below.

## c12 validation (REQUIRED — the exact case Phase 19b fixed)

c12 reached its real two-request-context shape live, for the first time ever:

| Composite key | status | candidates | accepted |
|---|---|---|---|
| `(c12, intervention, U1)` | fresh | 5 (p24,p1,p4,p8,p12) | `[]` |
| `(c12, intervention, U5)` | fresh | 3 (p25,p6,p18) | `[]` |
| `(c12, target_manifestation, U1)` | fresh | 5 (same as above) | `[]` |
| `(c12, target_manifestation, U5)` | fresh | 3 (same as above) | `[]` |

- Both real root request contexts (`U1`, `U5`) remained distinct — confirmed disjoint candidate
  pools (zero proposition-id overlap between U1's and U5's offered rows).
- **No `RequestFingerprintMismatch`** — the run completed end to end.
- Receipts keyed independently (4 distinct composite keys, 4 distinct receipts).
- Candidate pools were never mixed between U1 and U5.
- All four accepted lists are empty, so cross-contamination is structurally moot this run — but the
  isolation that prevents it (the composite key) is exercised and proven regardless.
- No role-fork occurred for c12 this run (zero accepted nominations means nothing to fork), so
  role-fork memoization wasn't separately exercised on c12 specifically — it *was* exercised
  elsewhere (the dedup within calls #2/#8/#9/#10/#14 below) and was separately proven on real c12
  evidence in the Phase-19b release-gate test suite offline.
- Final semantic instances for c12 are correctly derived: both `U1` and `U5` instances remain
  `missing`/`partially_filled` for `intervention`/`target_manifestation`, matching the empty
  acceptance — no spurious fill.

**This is the exact bug Phase 19b fixed. Verdict: Phase-21 infrastructure PASS on c12.**

(Scientific note, not an infrastructure finding: the model declined to nominate from either
candidate pool. U5's own passage — "Having knowledge about individual differences in empathy and
disgust sensitivity *might* improve decision-making and reduce bias..." — is speculative/hedged
("might"), not a description of an administered intervention with a measured effect, so declining
is a defensible, arguably correct outcome rather than a missed finding. U1's passage describes study
findings generally, not an intervention at all.)

## Infrastructure adjudication (per reached composite request)

Checked for every one of the 14 receipts: every accepted `exact_text` is a literal substring of its
proposition's own verified passage (`canonical_text_contains`, confirmed by direct inspection — no
exception); admissibility guards passed (no disqualifying guard present on any contributing unit);
dedup is correct (traced three concrete cases below); multiple nominations fork correctly where they
occurred (c8, c6); no cross-context contamination (c12, above); no descriptive-text authorization
(scope/authorization decisions never reference `category_description`, confirmed by code); and
`request_context` never alters authorization identity (authorization is decided on `scope` alone in
every receipt — `all_eligible_policy()` authorized all 14 regardless of context value).

**Dedup correctness, traced against the raw trace:**
- **Call #2** (`c1`, `brain_region_or_network`): raw 2 items (`p2`,`p11`, identical text, shared
  anchor) → 1 accepted, `supporting_proposition_ids: ["p11","p2"]`. Correct collapse.
- **Call #8** (`c2`, `behavior_or_behavioral_measure`): raw 8 items → 3 accepted. Five items sharing
  one anchor (`p1,p4,p8,p12,p24`, identical text) collapsed to 1; two items sharing another anchor
  (`p5,p15`, identical text "visual attention toward...") collapsed to 1; one item (`p5`, a
  *different* exact_text, "influence visual attention when looking at...") stayed separate because
  normalized text differs even though the anchor is the same as the second group — matching
  `nominate_with_model`'s documented policy exactly (same anchor does not force a merge across
  different exact_text values).
- **Call #10** (`c8`, `individual_difference_trait_or_construct`, context `U6`): raw 8 items
  (`p20`/`p9` × 4 distinct texts) → 4 accepted, each citing both `p20` and `p9` (shared anchor),
  one per distinct construct name. Correct multi-instance extraction from one sentence enumerating
  four separate constructs.
- **Call #14** (`c6`, `attitude_type_or_measure`): raw 5 items, all identical text ("Explicit Bias
  Questionnaire") → 2 accepted, NOT 1 — because `p26` has a genuinely different physical anchor than
  `p14/p17/p3/p7`. Correctly *not* merged across anchors despite identical text, per the
  no-fuzzy-cross-anchor-merge rule.

No dedup or grounding defect found anywhere in the 14 calls. **Infrastructure verdict: PASS.**

## Scientific adjudication (separate from infrastructure correctness)

11 accepted nominations, judged only from the requested role/category, the offered proposition, and
the verified passage — no hidden benchmark answers used.

| # | Child/role | Nominated text | Verdict | Reason |
|---|---|---|---|---|
| 1 | c1 `brain_region_or_network` | "the specific amygdala response" | **Ambiguous** | Correctly names the amygdala but the span wraps in "response" wording that blurs into the (separately, and here empty) neural-measure role. |
| 2 | c2 `behavior_or_behavioral_measure` | "described a behavioral manifestation of the 'anomalous-is-bad' stereotype affecting prosociality" | **Incorrect** | A meta-description that the paper *described* a behavior, not a name for the behavior/measure itself — the "vague existence statement filling a specific entity role" historical failure mode, confirmed live. |
| 3 | c2 `behavior_or_behavioral_measure` | "visual attention toward people with facial anomalies" | **Correct** | A genuine, specific behavioral/eye-tracking measure. |
| 4 | c2 `behavior_or_behavioral_measure` | "influence visual attention when looking at faces with anomalous anatomy" | **Ambiguous** | Same underlying measure as #3, restated from the same sentence/anchor (`p5`) — a "same-anchor fake multiplicity" case: not false, but an inflated duplicate of #3 rather than a distinct second measure. |
| 5 | c4 `named_brain_region_or_network` | "the specific amygdala response" | **Ambiguous** | Same reasoning as #1. |
| 6 | c6 `attitude_type_or_measure` | "Explicit Bias Questionnaire" (citing p14/p17/p3/p7) | **Correct** | A specific, real named instrument. |
| 7 | c6 `attitude_type_or_measure` | "Explicit Bias Questionnaire" (citing p26) | **Correct** | Same instrument, a genuinely separate mention elsewhere in the paper — correctly not merged with #6. |
| 8 | c8 `individual_difference_trait_or_construct` | "negative attitudes (IAT and EBQ)" | **Correct** | A real, named individual-difference construct. |
| 9 | c8 `individual_difference_trait_or_construct` | "social cognitive biases (just-world beliefs)" | **Correct** | Same. |
| 10 | c8 `individual_difference_trait_or_construct` | "emotional dispositions (affective empathy)" | **Correct** | Same. |
| 11 | c8 `individual_difference_trait_or_construct` | "undesirable behaviors (less generosity in the DG)" | **Incorrect** | A behavioral *outcome* (Dictator Game generosity), not itself an individual-difference trait/construct — a semantic-category stretch; the model over-generalized the enumerated list's shared sentence frame to an item that doesn't fit the requested role. |

**Scientific tally: 6 correct, 3 ambiguous, 2 incorrect** (of 11). Kept strictly separate from the
clean infrastructure PASS above — several of the imprecise/incorrect nominations are perfectly
*grounded* (literal, admissible, correctly deduped) while being semantically imprecise or
miscategorized. A scientifically wrong nomination with faithful engine grounding is not an
infrastructure failure, per the brief's own framing.

## Historical failure modes (section 14) — observed vs. not observed

- **Vague existence statement filling a specific entity role:** observed (item #2 above).
- **Generic category wording becoming a named referent:** partially related to items #1/#5 (a
  real entity name wrapped in generic "response" wording), not a clean instance of the named
  failure mode on its own.
- **Source wording mistaken for requested entity:** observed (item #2, same case).
- **Bad model-dependent parent propagation:** **not observed** — propagation to c5/c6 (below)
  correctly carried a value that was itself legitimately grounded at its own source (c4); the
  propagation mechanism itself introduced no error.
- **Same-anchor fake multiplicity:** observed (item #4).
- **Order-sensitive first-result behavior:** not exercised/not determinable from a single run.
- **Cross-role contamination (candidate-pool mixing):** **not observed** — every role's candidate
  pool was confirmed scoped to its own child's own units; no pool ever contained another role's
  propositions.
- **Cross-role semantic stretch (a value that fits better elsewhere nominated anyway):** observed
  (item #11 — a behavioral outcome nominated into a trait/construct role; this is milder than true
  candidate-pool contamination).
- **Cross-request_context contamination:** **not observed** — confirmed clean on c12 (the exact case
  this phase targets).

## Stop-search (section 15)

Checked `compute_stop_search_certified` on every requirement in the final map:

| Child/requirement | state | has model/parent-dependent binding | certified |
|---|---|---|---|
| c1 neural-manifestation | filled | yes | **False** |
| c2 behavioral-manifestation | filled | yes | **False** |
| c4 specific-region | filled | yes | **False** |
| c6 brain-attitude | filled | yes | **False** |
| c5 brain-behavior | partially_filled | yes | True (not applicable — not `filled`) |
| c3/c6 implicit-explicit-coverage, c8, c9, c10, c11, c12 | missing/partially_filled | no/yes | True (not applicable — not `filled`) |

Every `filled` requirement with a model-dependent binding correctly returns `certified=False` —
model assistance never silently acquired a stop-search certificate. **Verdict: PASS.**

## Parent context (section 16)

Naturally exercised, for the first time live: c1's and c4's model-nominated
`brain_region_or_network`/`named_brain_region_or_network` ("the specific amygdala response")
propagated into c5's and c6's `named_brain_region_or_network` role via `candidate_source ==
"parent_context"`, with full upstream visibility preserved:

```json
"provenance": {
  "candidate_source": "parent_context",
  "detail": "from parent 'c4#suff:specific-region': model_mapping",
  "model_dependency_origins": [{"child_id": "c4", "requirement_id": "c4#suff:specific-region",
                                  "role": "named_brain_region_or_network", "instance_key": null}],
  "source_lineage": ["model_mapping", "parent_context"],
  "upstream_model_dependent": true
}
```

- Only complete parent instances propagated (c4's own instance was `state=filled, complete=True`).
- Both c1 and c4 independently reached the same value; the resolved `dependency_origins` names c4
  specifically (deterministic single-parent resolution, not an ambiguous blend).
- `candidate_source == "parent_context"` confirmed; upstream model dependence stayed fully visible.
- **One clarification on "no child call occurs merely due to inheritance":** c5's own
  `named_brain_region_or_network` role *did* make its own fresh model call from its own evidence
  first (this is one of the 14 counted calls; it returned empty), and *only then* fell back to
  parent-context inheritance — this is the documented Phase-16 design (own-evidence attempt first,
  parent-context as a deterministic, zero-cost fallback), not a second or wasted call. No additional
  call beyond the one already counted was made because of inheritance.

**Verdict: PASS**, with the above design clarification recorded for anyone auditing call counts later.

## Direction / effectiveness (section 17)

Exercised narrowly: c6 recorded `direction_observations` (`sign: "negative"`, non-causal, reported)
on both its filled instances, from the explicit-negative-attitudes passage. c12's `U1` instance
recorded one `effectiveness_observations` entry (`conclusion: "supported"`, `outcome_reported:
True`) from `p24`'s passage — though this is a thin/questionable effectiveness read given `U1`'s own
candidate pool is about reported findings, not an administered intervention (same caveat as the c12
adjudication above). No other requirement recorded direction/effectiveness observations this pass —
reported as **not exercised** for everything else, not manufactured.

## RecoveryTarget inventory (section 18) — computed, NOT executed

19 targets computed (`compute_recovery_targets`, inspection only; the sufficiency recovery gate
stayed OFF throughout, and nothing was executed). A compact summary:

| search_child_id | requirement_id | target_roles | reason | goal_mode | scope |
|---|---|---|---|---|---|
| c10 | culture-existence | bias_evidence_in_population | missing | single_role | none |
| c10 | culture-existence | named_culture_or_population | missing | single_role | none |
| c11 | culture-operationalization-pairing | operationalization_or_measure | missing | single_role | none |
| c11 | culture-operationalization-pairing | culture_or_population | missing | single_role | none |
| c12 | intervention-effectiveness | target_manifestation | partial | single_role | instance U1 |
| c12 | intervention-effectiveness | intervention | missing | single_role | instance U5 |
| c12 | intervention-effectiveness | target_manifestation | missing | single_role | instance U5 |
| c12 | intervention-effectiveness | intervention | partial | single_role | instance U1 |
| c12 | intervention-effectiveness | observed_effect_or_outcome | missing | single_role | instance U5 |
| c1 | neural-manifestation | brain_region_or_network | **provisional_corroboration** | single_role | none |
| c2 | behavioral-manifestation | behavior_or_behavioral_measure | **provisional_corroboration** | single_role | instance i::d57cf... |
| c3 | implicit-explicit-coverage | category_evidence | missing | single_role | instance "implicit" |
| c4 | specific-region | named_brain_region_or_network | **provisional_corroboration** | single_role | none |
| c5 | brain-behavior | behavior_or_behavioral_measure | partial | single_role | none |
| c6 | implicit-explicit-coverage | category_evidence | missing | single_role | instance "implicit" |
| c6 | brain-attitude | attitude_type_or_measure | **provisional_corroboration** | single_role | instance i::9fe92... |
| c6 | brain-attitude | attitude_type_or_measure | **provisional_corroboration** | single_role | instance i::2f2b0... |
| c8 | trait-construct | individual_difference_trait_or_construct | missing | single_role | none |
| c8 | trait-construct | relationship_to_bias_manifestation | missing | single_role | none |

5 targets carry `reason="provisional_corroboration"` with a non-empty `dependency_origins` pointing
at the exact upstream model-nomination scope responsible — c1, c2, c4, and c6's two instances. This
is real, correctly-structured **Phase-22 empirical input**: the first live evidence of which
model-dependent fills the recovery layer would, if enabled, treat as needing one bounded
corroboration pass rather than either blind trust or unlimited re-search. `RecoveryTarget.scope`
uses the post-fork `instance_key` (`i::...` or the raw `U1`/`U5` context for c12, which here happens
to equal its own un-forked instance key) — confirmed structurally distinct from `request_context`,
exactly the separation Phase 19b's own design decision anticipated and deferred to Phase 22.
`model_dependency_origins`'s shape in every one of these targets is exactly `{child_id,
requirement_id, role, instance_key}` — **no `request_context` field present**, confirming Phase
19b's deferral decision held through to real live data.

## Latency / residency (section 19)

- U1 total wall time: **70.328 s** for 14 physical calls (mean ≈ 5.0 s/call; one outlier call #1 at
  45.281 s — likely cold-model-load/first-token latency on the isolated JUNO endpoint, with every
  subsequent call well under 2 s except two heavier-output calls, #8 at 7.047 s and #10 at 5.187 s,
  both multi-nomination extractions).
- Physical nomination call count: 14, exactly matching the mechanically-derived cap.
- U2 wall time: **0.078 s** for 0 additional calls — confirms held-fixed replay carries no
  model-residency cost, as designed (U2 is deliberately not wrapped in the `stage()` residency guard).
- No GPU/residency swap telemetry beyond the existing per-call `elapsed_seconds` was available from
  this harness; no further measurement attempted (measurement only, no optimization, per
  instruction).

## Pass criteria (section 20)

| Criterion | Result |
|---|---|
| Intended model | ✅ qwen3.5:9b |
| think=False | ✅ |
| Full 11-child contract | ✅ |
| c12 included | ✅ |
| Composite request accounting correct | ✅ |
| Physical calls ≤ mechanically precomputed cap | ✅ (14 = 14) |
| No duplicate same-key calls | ✅ |
| No RequestFingerprintMismatch on legitimate distinct contexts | ✅ (none raised at all) |
| Receipts valid/inspectable | ✅ |
| No cross-context borrowing | ✅ |
| U2 fresh calls == 0 | ✅ |
| Provenance correct | ✅ |
| Candidate validation intact | ✅ |
| Stop-search safeguards intact | ✅ |
| Production-shaped path completes | ✅ |

**INFRASTRUCTURE: PASS.**

**Scientific quality (kept separate, not collapsed into the above):** 6 correct / 3 ambiguous / 2
incorrect of 11 accepted nominations. Two concrete, previously-only-theoretical failure modes from
section 14 were observed live for the first time (vague-existence-statement-as-entity,
same-anchor-fake-multiplicity), plus one additional mild cross-role semantic stretch not explicitly
named in the brief's list.

## Newly discovered issues

1. A real, non-consuming harness bug (pre-live, fixed before any network call): the dirty-tree
   preflight check didn't tolerate the harness's own untracked existence, which the brief's own
   "Authoritative State" section explicitly names as expected. Fixed narrowly in the harness itself
   (not production code) by excluding exactly that one known file from the dirty check.
2. The call-log's raw `n_accepted` (pre-grounding model output count) can legitimately differ from
   a receipt's final `accepted` count (post-grounding/dedup) — documented above as expected
   behavior, not a defect, but worth naming so a future reader of a Phase-21-style trace doesn't
   mistake the difference for a bug.
3. Two concrete scientific failure modes predicted in the brief's own section 14 were confirmed
   present on real live output (see above) — not an infrastructure finding, but worth carrying into
   any future decision about raising nomination quality (e.g., prompt refinement, dedup extension to
   near-duplicate paraphrases, or a stricter admissibility guard for behavioral-outcome language
   leaking into trait/construct roles).

## Next recommendation

**Phase 22 is READY**, with real empirical input now in hand: 5 concrete `provisional_corroboration`
RecoveryTargets with correctly-populated `dependency_origins`, naming exactly which model-dependent
fills would need one bounded corroboration pass if recovery were enabled. The architectural question
Phase 19b deliberately deferred — whether/how to link `request_context` into
`model_dependency_origins` for Phase-22 targeting — can now be designed from this real shape rather
than speculatively: note that none of the 5 `provisional_corroboration` targets observed this run
happen to fall on a `request_context`-partitioned scope (c12's own targets are `reason="missing"`/
`"partial"`, not `provisional_corroboration`), so this run's real data does not yet force that design
question to resolve one way or the other — a useful, honest data point for Phase 22's own scoping,
not a blocker.
