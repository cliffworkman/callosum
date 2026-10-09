# PHASE 34 / I4-2b5 — v7 support-policy evaluation and achieved-outcome guard retention

## Scope and commit identity

Implemented the bounded [I4-2b4 design](PHASE34_I4_2B4_V7_SUPPORT_POLICY_GUARD_DESIGN.md).
Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
Starting HEAD: `e3e7e729defb9ebe2d0ab66e38fa4459f613d683`.
Final HEAD is the single I4-2b5 implementation commit containing this report; resolve it with
`git log -1 --format=%H -- experiments/ask_cli_revised/PHASE34_I4_2B5_V7_SUPPORT_POLICY_GUARD_RESULTS.md`.
The actual final commit ID is reported after committing; a commit cannot embed its own hash.

**sufficiency-semantics-v7 is current.** V6 is historical/readable and retains its exact replay.
Classifier ruleset remains **i4-2b3.0**; PLAN_VERSION remains **answer-plan-step2-v4**.
No attribution/parser, authoring guard list, detector, same_local_assertion registration, claim-goal/veto gate,
ParentClaims/AnswerPlan rendering implementation, I4-3, I4-4 or I2-3 work is included.
All execution was local/offline; saved nominations were held fixed. No live retrieval, model calls or live E2E.

## Implemented boundary

V7 is v6 grounding and attribution followed by achieved-outcome guard retention, default/authored policy
evaluation, independent evaluated metadata, set-based role aggregation and eligible-only legacy projection.
Only achieved_outcome_predicate changes. Other strategies preserve their guard behavior.

The mapper validates a present authored support_policy at role entry, even for empty scopes. It observes
historical unit guard flags without discarding, runs the shared local coordinate/predicate/assertion/dedupe/
dependency/target pipeline, and emits no candidate for failed grounding/relevance. Successful candidates
receive unchanged v6 annotation, guard facts, policy evaluation, final admissible, engine aggregation, then
legacy projection. Policy is evaluated even when a guard already excludes the candidate.

One private `_collect_achieved_outcome` core accepts only `historical_prefilter` or `retain_for_v7`.
Historical v5/v6 wrappers preserve prefiltering and projection; v7 uses retention. Shared
`_annotate_achieved_bindings` contains the unchanged annotation body. There is no second grounding
algorithm, flag clearing, authored-list mutation, or global bypass. The coordinate check still raises on
newly retained, hit-bearing plural units with nonidentical sealed quotes.

## Dedupe and guard derivation decision

The current candidate key is **(anchor proposition ID, assertion span)**, not assertion text alone.
On validated sealed-ledger inputs, each proposition belongs to one producer unit. The child view can
reorder IDs but neither duplicates that unit inside the child nor recalculates its flags. All raw hits
deduplicating to a candidate therefore inherit the same passage-level guard surface.

The collector retains ordered raw derivation records (unit index, plural IDs, predicate/content spans,
flags) through relevance. Before flattening exclusions it checks every relevant derivation's authored
guard set. A conflicting group raises `STOP: mixed guard derivations require reviewed candidate schema`.
It never ORs, silently chooses a guarded/clear path, or serializes an invented path schema.
This is a defensive refusal for inputs violating the demonstrated producer invariant, not an implementation
of a general multi-path guard algebra.

The preserved corpus has **15 candidates, three with multiple raw-predicate derivations, zero with
multiple source-unit derivations, and zero conflicting guard groups**. The replay's separate diagnostic
invocation doubles the inspection counts to 30/six; the report counts semantic candidate records once.

The four requested synthetic pairs are exercised through actual unit production, grounding and v7 binding:

| Pair | Result under current identity |
|---|---|
| Both clear | Same passage pools into one candidate, guard-clear |
| Both guarded by the same guard | Same passage pools into one candidate, excluded with that identity |
| One clear, one guarded | Different passages/anchors remain two candidates; clear support fills the role |
| Different guard sets | Different passages/anchors remain separate; each exclusion remains inspectable |

These latter two rows deliberately do not claim two anchored candidates are one candidate. A test also
checks multiple recognized predicates inside one assertion share their unit's flags. No valid input
demonstrated a mixed-guard collapse requiring a schema extension. If that invariant changes, the
user's STOP/schema-review boundary remains necessary.

Guard detection remains **passage-level**. A hedge outside the exact local assertion still excludes it;
tests cover that limitation. Triggered names follow authored order, with repeated names deduplicated at
first occurrence. Missing flags preserve historical false behavior.

## Policy, schema and aggregation

The new pure `support_policy.py` accepts only the semantic triple and, for the authored API, the policy.
It imports engine schema/vocabulary only. The mapper is the sole production evaluator caller; the engine
does not import the evaluator. Neither API accepts text, role/question prose, provenance, support_label,
attachment, guards, authority_veto or is_caption.

Absent policy is selected by **key absence**, with identity **empirical-default-v1** and the fixed
I4-2b4 snapshot:

```text
assertion_kind == result
AND NOT (assertion_relation == unresolved
         AND aggregation == non_synthetic_or_unspecified)
```

It never calls new_support_policy(). Explicit complete policy replaces this predicate with relation
membership AND aggregation condition AND kind membership. Stored null/empty/partial/extra-key/wrong-type/
invalid-vocabulary/empty-set policies raise ValueError. Builder None-as-omission remains unchanged.

Authored identity is `authored-support-policy-v1:sha256:<digest>` of the normalized three dimensions,
sorted/deduplicated sets, sorted JSON keys, compact separators, ensure_ascii=False and UTF-8.
All six accepted identity digests and all 30 triples across default plus six policies are frozen in
`support_policy_i4_2b5_preregistered.json`, materialized before production edits.

V7 adds exactly `guard_exclusions` and `support_policy_evaluation`. The latter retains schema_version,
policy_source, policy_identity, policy_snapshot, passed, failed_dimensions and reasons.
`new_evaluated_candidate_support` is separate from the historical builder. Historical v6 rows omit the
new fields entirely and retain admissible=None. Evaluated records require strict bool eligibility,
complete metadata, matching normalized identities, ordered closed failures and consistent projections.

Authored failure order is relation, aggregation, kind, with reasons assertion_relation_not_allowed,
aggregation_requires_synthesis / aggregation_excludes_synthesis, and assertion_kind_not_allowed.
The default retains both relation_aggregation/unresolved_non_synthetic and kind/non_result_kind when
applicable. No failure suppresses another.

`admissible = guard-clear AND policy-passed`. Attachment is independent.
The singular compatibility projection is None, disqualifying_guard_excluded, support_policy_excluded,
or guard_and_support_policy_excluded. It never chooses state; consistency validation rejects forged
or mismatched projections. Gate validation checks the supplied data contract, while the sole evaluator
computes policy meaning; the engine does not implement a second policy evaluator.

Engine `aggregate_support_role` evaluates the set contract:

- FILLED: a resolved candidate is admissible=True.
- AMBIGUOUS: none filled, but an attachment-ambiguous candidate is admissible=True.
- MISSING: otherwise.

All evaluated records are validated before deriving state. The reference-only helper delegates to that
authority; production calls the engine aggregate directly. Old historical schema examples remain readable,
but False-plus-ambiguous is no longer a valid way to manufacture v7 ambiguity.
All 14 multiple-candidate cases pass in both orders; all eight attachment/guard/policy combinations pass.

A filled binding projects the first resolved eligible candidate in preserved discovery order. Missing or
ambiguous bindings keep legacy support fields unset/default and retain their full candidate set. No direct/
indirect/synthesis ranking, ID union or instance fork is added. Witness consumers still use their established
binding-level projection; generalized set-wise witness selection is outside this increment.

## Real 10 -> 15 result

The original ten supports retain exact discovery order, local text, spans, IDs/order, veto/caption,
attachment, kind, aggregation and complete i4-2b3.0 attribution/proofs. All pass the empirical policy with
empty guard exclusions and admissible=True. The five additional supports match the independent accepted
I4-2b4 expectation fixture byte-for-byte as data, including complete attribution. That fixture uses explicit
UTF-8 when read; no expected text was changed to accommodate implementation.

| Child / requirement | Role | Exact instance key | Target role value | Supporting IDs / anchor | Assertion span |
|---|---|---|---|---|---|
| c3 / `c3#suff:attitude-manifestation` | `attitude_manifestation_evidence` | `null` | target-free role | p9, p20 / p9 | [0,302) |
| c8 / `c8#suff:trait-construct` | `relationship_to_bias_manifestation` | `U6::b2958c5ad5164563` | negative attitudes (IAT and EBQ) | p20, p9 / p20 | [0,302) |
| c8 / `c8#suff:trait-construct` | `relationship_to_bias_manifestation` | `U6::ce8933c59b53a00f` | social cognitive biases (just-world beliefs) | p20, p9 / p20 | [0,302) |
| c8 / `c8#suff:trait-construct` | `relationship_to_bias_manifestation` | `U6::da37435ef9b489b6` | emotional dispositions (affective empathy) | p20, p9 / p20 | [0,302) |
| c8 / `c8#suff:trait-construct` | `relationship_to_bias_manifestation` | `U6::d41542e10edf3ea7` | undesirable behaviors (less generosity in the DG) | p20, p9 / p20 | [0,302) |

All five exact_text values are:

> We suggest that dehumanization is underpinned by a suite of negative attitudes (IAT and EBQ), social cognitive biases (just-world beliefs), emotional dispositions (affective empathy), and undesirable behaviors (less generosity in the DG)—all factors associated with the functioning of the left amygdala

For every row: assertion span [0,302), predicate span [250,260), content span [250,303);
relation current_document; aggregation non_synthetic_or_unspecified; kind interpretation; label interpretive;
veto None; caption False; attachment_ambiguous False. Actual i4-2b3.0 annotation records predicate.suggest,
subject.owner, kind.interpretation_verb, empty ownership proofs and not_needed context. No R1/R2/R3 change.

Every new candidate has guard_exclusions=["hedged"], absent_default / empirical-default-v1,
policy passed=False, failed_dimensions=["kind"], reasons=["non_result_kind"], admissible=False and
inadmissibility_reason=guard_and_support_policy_excluded. Full records, including source quote hash and
anchor, are in `support_policy_i4_2b5_expected_new_candidates.json` and asserted against the actual replay.

c3 remains filled with its original p7 representative. Four c8 relationship bindings remain missing and
change reason from not_found to candidate_supports_excluded, with legacy support fields unset.
c8 remains open_list and partially filled. c10/p29+p53 still fail assertion joining; its other units have
no recognized hit. c10 and c12 each retain **zero** candidates. No failed grounding becomes inspectable
candidate evidence.

## Downstream and diagnostics

| Measure | V6 | V7 |
|---|---:|---:|
| Candidate supports | 10 | 15 |
| Eligible candidates | unevaluated | 10 |
| Guard and policy excluded candidates | prefiltered | 5 |
| Evidence roles filled / missing / ambiguous | 10 / 16 / 0 | 10 / 16 / 0 |
| Evidence-role state changes | — | 0 / 26 |
| Requirement-state changes | — | 0 / 13 |
| Recovery targets | 48 | 48, exact equality |
| ParentClaims | 17 | 17, semantic equality |
| AnswerPlan nodes | 9 | 9, same statuses/content |
| Downstream invariants | 33 passing | 33 passing |

Witnesses, relations, direction/effectiveness, inherited c5/c6 context, c9 pairing opportunities and Layer 1
semantic content are unchanged. Whole artifacts are not byte-equal: v7 identity, candidate lists/gate metadata,
four c8 reasons, diagnostics and hashes incorporating versioned inputs change. Full recursive comparison
normalizes only semantic identity/plan hash, removes the candidate lists and diagnostics, and reverses the
four specified reason changes; nothing else differs.

Actual v7 totals across 26 role attempts: guard_triggered_units=21, guard_prefiltered_units=0,
guard_excluded_candidates=5, policy_excluded_candidates=5, admissible_candidates=10.
Grounding counters remain observable. Twelve roles have no grounded candidate; sixteen roles are missing.
Historical v6 diagnostic bytes remain exact.

All **31 reached nomination attempts across 29 unique scopes** have identical nomination rows, category
descriptions, prompt strings and request fingerprints. No model is called. Recovery query/scope records
are equal for all 48 targets. Retrieval/search/ranking code is unchanged. Target relevance still receives
the same shared local assertion text; neither policy metadata nor guard explanations enter prompts.

## Historical preservation and v7 baseline

Explicit named routing extends all audited engine/mapping/category/recovery, direction/witness and
diagnostic/E2E context sites. Unknown versions fail closed. V7 inherits i4-2b3.0 explicitly; v6 is still
the prefilter ten-candidate route. There is no numeric comparison or catch-all future-version behavior.

| Version | Combined replay SHA-256 |
|---|---|
| v4 | `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a` |
| v5 | `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77` |
| v6 | `dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be` |
| v7 | `04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72` |

The new baseline is frozen only after semantic gates and regression triage pass. The committed
`support_policy_i4_2b5_replay_baseline.json` and replay test freeze all four combined hashes.
Saved replay data and logs are under .local/i4-2b5; production never reads these artifacts.

## Validation and known failures

- **554 new v7 tests pass**: the 553-test new suite plus the subsequently frozen four-version baseline test.
  The final replay/derivation rerun passes all 13 tests after UTF-8 loading and baseline materialization.
- Full offline experiments: **4,885 passed, five known failures, 12 skipped, nine existing xfails,
  276 subtests passed**. The five failures are independently reproduced on checkpoint modules.
- Existing dependency-complete optional module: **seven passed**.
- Paired omitted/explicit legacy classifier batteries: **443 passed, nine existing xfails**.
- Full collection covers I4-1 through I4-2b3, the 119-node legacy freeze, ownership context,
  engine/mapping/diagnostics, recovery, witnesses/relations, direction/effectiveness, parent synthesis,
  AnswerPlan/replay and hierarchy integration.
- New matrices cover 30 triples across seven policies (210 rows), six frozen authored identities,
  D01–D06, all-dimensional failures, eight orthogonal combinations, 14 sets in both orders and
  3,780 veto/caption/label non-gate comparisons. Static tests enforce exact consumer paths and
  reject unauthorized imports and forbidden policy inputs/effects.
- Ruff formatting/check, Bandit, Tach and all applicable content hooks pass.
  The only failing hook is the unchanged **615-line app/frontend/js/20_synthesis.jsx** against
  the 600-line limit. Its worktree and starting-commit Git blob hashes are both
  `03f9d3dfee3763533a78d5da601a99cb81bb37f1`.
  The user's explicit I4-2b5-only --no-verify authorization applies to this commit; no semantic,
  replay, attribution, policy, isolation or unexplained-regression gate is bypassed.

Logs: `full-final.log/xml`, `new-tests.log`, `frozen-final.log`, `historical-paired.log`,
`known-head.log`, `known-current.log`, `optional.log`, `hooks.log` and
`baseline-module-hashes.json` under .local/i4-2b5. Counts overlap between suites; they are not
summed into a misleading total.

The five independently reconfirmed checkpoint/environment failures are:

| Test | Same failure at starting checkpoint and current code |
|---|---|
| ask_070/test_corpus_and_referents::test_dev_eval_separation | Missing frozen/dev_inputs_v0.json |
| ask_070/test_schema_validation::test_real_frozen_nonsemantic_artifact_schemas | Missing frozen/corpus_presence_v0.json |
| test_e2e_run::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored | Existing Ollama /api/tags probe denied by offline fixture before mocked runtime |
| test_hierarchy_contract::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts | Existing hierarchy_contract.py code-input pin drift |
| test_hierarchy_e2e::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects | Same pin rejection returns 3 rather than 0 |

They are neither repaired nor marked xfail. Checkpoint modules were copied from e3e7e729 and hash-recorded;
the unchanged hierarchy module uses its original resource root so baseline pin tests actually execute.
The optional psutil-dependent scripted offline module runs in the existing Anaconda environment, separately
from declared-environment collection. No dependency installation or live run was used.

Test-development corrections were confined to six deliberate current-version pins, a UTF-8 fixture reader,
and neutral fixture punctuation/embedded-predicate expectations. Historical semantic hashes, policy
expectations, classifier expectations and scientific text were not rewritten to obtain a pass.

## Exact changed files

- `CONTRIBUTION-LINEAGE.md`
- `PHASE34_I4_2B5_V7_SUPPORT_POLICY_GUARD_RESULTS.md`
- `direction_target.py`
- `e2e.py`
- `relation_witness.py`
- `sufficiency_diagnostic.py`
- `sufficiency_engine.py`
- `sufficiency_mapping.py`
- `sufficiency_recovery_targets.py`
- `support_policy.py`
- `support_policy_i4_2b5_expected_new_candidates.json`
- `support_policy_i4_2b5_preregistered.json`
- `support_policy_i4_2b5_replay_baseline.json`
- `test_achieved_outcome_span.py`
- `test_assertion_authority.py`
- `test_assertion_authority_i4_1b.py`
- `test_assertion_authority_i4_1c.py`
- `test_assertion_authority_i4_1f.py`
- `test_i4_1j_local_grounding.py`
- `test_i4_2a_local_grounding.py`
- `test_i4_2a_replay.py`
- `test_i4_2b5_boundaries.py`
- `test_i4_2b5_derivations.py`
- `test_i4_2b5_policy.py`
- `test_i4_2b5_replay.py`
- `test_sufficiency_semantics_version.py`
- `test_sufficiency_support_schema.py`
- `test_sufficiency_v4_category_satisfaction.py`

Paths are relative to experiments/ask_cli_revised. No app/frontend file is edited.

## Limitations, readiness and stop

**READY for the next separately authorized planning increment.** This is not authorization to start it.
The retained evidence remains passage-guarded; aggregation ambiguity is covered by synthetic evaluated
records and does not authorize retaining failed assertion joins. The real corpus still has zero synthesis
or caption candidates; mandatory synthetic policy and metadata non-gate tests preserve those contracts.

Authority_veto and captions remain metadata only. No claim polarity is inferred. Hierarchical and later
Simple Ask can share this policy machinery with different authored policies; extraction/rendering expansion
is not implemented here. I4-4 metadata survives in the map, but existing ParentClaims/AnswerPlan do not
explain candidate exclusions yet. The earlier six-exclusion counterfactual remains preserved in I4-2b0;
Recommendation B remains satisfied by attribution-first v6, with the conservative default unchanged.

**STOP after I4-2b5. No I4-3, same_local_assertion, claim-goal/veto gating, I4-4 or I2-3.**
