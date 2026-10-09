# Phase 34 / I4-3A — Candidate-set relationship witness necessity audit

Date: 2026-10-09. Planning and offline audit only.

**Decision: candidate-set relationship witnessing is needed before I4-4.** The unchanged production consumers can make relationship truth depend on the first eligible candidate projected into a legacy RoleBinding. The preserved q_aib v7 replay does not exercise that failure: zero roles have multiple admissible resolved candidates, and all 40 relational instances agree with the candidate-set existential audit oracle. Synthetic cases prove the architectural gap.

An additional bounded finding matters: even candidates with the **same** proposition support set can make direction depend on the representative's assertion text. A production-grounded two-assertion example changes its direction consensus from positive to negative when only candidate order is reversed. A proposition-ID-only repair is insufficient.

Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
Full starting HEAD, verified before the audit and again before materialization:
`8c14689e14f5017da6d638566dddafe4dfbfff65`. The starting worktree was clean.

This report does not implement or stamp v8. It does not change role satisfaction, candidate collection, attribution, support policy, guards, verifiers, ParentClaims, AnswerPlan, PLAN_VERSION, or semantic versions. No external search, live retrieval, model call, or live E2E was used.

## 1. Required decisions

| Decision | Result |
|---|---|
| R1 — Consumers | The production witness path uses role state plus legacy representative text and the representative's plural proposition support. No relationship consumer selects across `candidate_supports`. The complete consumer inventory is in §3. |
| R2 — Representative truth | **Yes**, at the supported binding-consumer boundary. A/P1 then B/P2 fails against sibling P2; B/P2 then A/P1 succeeds. Collector reachability is narrower and explicitly discussed in §5. |
| R3 — Real threatening cases | **0** filled roles with >1 admissible resolved candidate; **0** with differing eligible support sets. c3 alone has >1 retained candidate: two total, one eligible. |
| R4 — Synthetic result | Required A–K plus L permutations: 33 executions. C, D, I, J are order-dependent in current production. Including six extra exclusion/empty families: 42 executions, 12 current-versus-proposed disagreements, all false negatives. Proposed truth is invariant in every permutation. |
| R5 — Eligibility | A candidate may witness only if `admissible is True` AND `attachment_ambiguous is False`, after evaluated-record validation. Existing completion/required-role gates still apply. |
| R6 — Plural same_proposition | Existential assignment of one eligible resolved support per participating own-evidence role, with one proposition ID common to all selected supports. This generalizes the historical identity relation; it does not introduce anchor or entity matching. |
| R7 — Union | Do not overwrite legacy provenance with a union. A correctly filtered per-role union/intersection is mathematically safe for the **Boolean pure common-ID predicate only**, but is not a witness proof or text/observation contract. Global unions, unfiltered unions and pairwise-only joins are unsafe. |
| R8 — Algorithm | Extend the shared witness machinery with eligible support views, compatible assignments and relation-specific proof records. Preserve engine completion and I1 own/inherited witnessing as separate consumers of that mechanism. No global relational database. |
| R9 — Provenance | Retain role-to-candidate stable references, source/support IDs, assertion locators, gate/attribution references, join basis, verifier/rule and semantic version. Carry all relevant successful evidence alternatives for observations; do not select the first witness as semantic authority. |
| R10 — Observations | Evidence IDs, assertion locators and operand surfaces must come from the **same successful assignment**. Merely fixing the Boolean or witness IDs leaves direction inconsistent. Preserve conflict across successful alternatives. |
| R11 — same_local_assertion | **Redundant for current authored achieved-outcome relevance; defer registration.** No current authored distinct contract needs it. This is not a universal claim about future multi-assertion contracts. |
| R12 — Version | **v8 required for the eventual correction**: synthetic relationship/direction outcomes change. Explicit v4–v7 remain exact historical behavior. No version change here. |
| R13 — Ordering | **I4-3 before I4-4.** Candidate-aware answer integration cannot safely treat the current representative as a relation's witness. |
| R14 — Next increment | **I4-3B — V8 compatible-witness selection and observation-alignment integration design**, narrowly specified in §10. |
| R15 — Readiness | **READY for that bounded design increment. NOT an authorization or implementation-ready wire contract for v8.** Close candidate-reference serialization, observation span transport and the legacy answer-consumer handoff there. |

## 2. Evidence and method

Read production modules, historical reports, and existing tests at the exact starting HEAD. The accepted offline harness `test_i4_2a_replay.remap` reran v4, v5, v6 and v7 using the hash-verified sealed ledger, preserved model-role bindings and saved evidence packets from Attempt2. `test_i4_2b3_replay.context()` built the existing ownership-context index. No nomination was regenerated.

The independent **planning oracle** did not monkeypatch relationship behavior. For a binding with candidate records it retained only resolved/admissible records and projected each candidate into a temporary binding with that candidate's own text and support IDs. A filled binding with no candidate key supplied one legacy support view. A missing/ambiguous binding, or a present candidate list with no eligible members, supplied no view. For each compatible Cartesian assignment, the oracle called unchanged `_joint_grounded` or `relation_witness.witness_instance` on scratch dictionaries, then collected successful witness IDs. Every relevant real instance was compared separately. This exercises existing relation meaning over plural eligible evidence; it is not a version-stamped v8 replay or a passing implementation suite for a future selector.

For engine joint grounding, participating roles were exactly `own_evidence_roles(role_completion, bindings)`. For I1 witnesses, participating roles were exactly the sorted `required_roles`, retaining own/inherited source distinctions. These role sets must not be silently equated. An empty or one-own-role joint check bypasses the multi-own-role relation gate; that does not establish an I1 relation.

Synthetic candidate records were built and validated through the unchanged `new_candidate_support`, `new_evaluated_candidate_support`, empirical policy evaluator and `_project_evaluated_supports`. Production `recompute_instance` and `witness_instance` supplied observed outcomes. The proposed existential outcomes are explicitly audit expectations evaluated by the separate oracle.

## 3. R1: production consumer inventory

Paths below are relative to `experiments/ask_cli_revised/`; line references are at the starting HEAD. “Legacy plural” means binding primary ID plus binding provenance support IDs, **not all candidates**.

| Consumer | Evidence surface actually read | Gates and implications |
|---|---|---|
| `sufficiency_engine.py:744 aggregate_support_role`; `:946 reference_future_role_state` | All evaluated candidates | Layer A only. Resolved admissible → filled; otherwise admissible ambiguous → ambiguous; otherwise missing. The reference helper now delegates to this v7 contract. |
| `sufficiency_mapping.py:449 _project_evaluated_supports` | All candidates for state; first resolved admissible candidate for legacy text/ID/plural support/guard | Preserved discovery order selects representation after state. Excluded/ambiguous records never populate filled legacy fields. |
| `sufficiency_engine.py:979 _support_set` | Legacy plural | No state, candidate, attachment or policy inspection. Primary plus explicitly recorded plural aliases; no physical-anchor inference. |
| `:1000 _verify_same_proposition` | Legacy plural for each supplied role | N-way intersection, not pairwise overlaps. No candidate eligibility filtering of its own. |
| `:1013 _verify_contract_directed_links` | Representative `exact_text` | Requires supplied `context.attachment_pieces`; intersects extracted designators. No production mapping caller supplies this context. It fails closed in this pipeline. |
| `:1045 _joint_grounded` | Supplied role bindings through registered verifiers | Fewer than two roles → true; otherwise OR across authored verifiers. No candidate selection. |
| `:1061 own_evidence_roles`; `:1180 recompute_instance` | Role states and immediate source; then legacy verifier surfaces | Required roles all filled, every alternative group has a filled member. Joint gate includes **all filled** required/alternative own roles, excludes optional and parent-context roles. Does not choose one alternative per group for the joint check. Preserve this behavior. |
| `:1076 relationship_witness_support_ids` | Legacy plural from filled own completion roles | Zero own → empty; one own → its set; multiple own → intersection. Despite its parameters, it does not execute verifiers or use context in its body. Not the same contract as I1 witnessed relation. |
| `relation_witness.py:56 is_relational`, `:63 operand_source`, `:68 support_ids` | Required-role count, source marker, legacy plural | Relational means ≥2 **required** roles. c1's required-plus-alternative relation gates are outside this I1 classifier. |
| `:80 is_admissible`, `:130 witness_instance` | Required role states; own legacy plural; inherited representative text; sealed proposition quote/verification/anchors | Every required role filled, at least one own operand, one shared own proposition verified and containing every inherited referent. Here “admissible” is **sealed-proposition verification**, distinct from candidate support-policy admissibility. No candidate gates or authored-verifier lookup. |
| `:201 attach_relation_witnesses`; diagnostic mapping call | Same shared I1 function | Adds witnessed/IDs/provenance; does not alter `complete`. |
| `sufficiency_diagnostic.py:242 _instance_scoped_units` | Supplied witness IDs mapped back to physical units | Narrows IDs but retains whole unit passage; deduplicates physical units. No candidate assertion-span selection. |
| `:275 _bound_surfaces`, `:286 _relation_witness_ids`, `:293 compute_direction_and_effectiveness` | Required filled representative texts; engine witness-support IDs; separate stored I1 witness IDs | Engine scope determines inspected units. I1 IDs additionally gate relation-direction eligibility. Metadata can be computed on incomplete instances. |
| `sufficiency_mapping.py:1566 find_direction_observations` | Supplied whole-unit sentences, supplied operand texts and relation IDs | One observation per direction-bearing sentence. Eligible iff witness-ID overlap, classifier target=relation and a literal sign. Does not inspect candidates or candidate spans. |
| `direction_target.py:149 classify_sentence` | Sentence and supplied operand surfaces | Generic grammatical direction classification only; no candidate source, policy or witness selection. Relation target is not itself proof of a witnessed relation. |
| `sufficiency_mapping.py:1625 find_effectiveness_observations` | Supplied whole passages, predicate and passage flags | Result predicate + negation/absence flags. No direct candidate gates, I1 relation check or selected-span constraint; depends on caller scoping. |
| `sufficiency_engine.py:1117 counts_toward_relation_direction`, `:1126 summarize_observations` | Observation eligibility and instance completeness | Summaries use complete instances; targeted direction must be relation-eligible. Conflict and between-instance heterogeneity remain distinct. |
| `:1352 eligible_parent_instances`; `sufficiency_mapping.py:1320 map_paired_requirement`, `:1268 _propagated_provenance` | Parent role filled AND parent instance complete; parent representative text/ID | Parent eligibility can change if joint completeness changes. Mapping copies the binding with `{**parent_binding, provenance: ...}`: candidate records, if present, survive, but provenance is restamped parent_context and its plural-support field is not carried there. Inherited supports must not become child-owned evidence merely because candidates survive. |
| `sufficiency_mapping.py:109 _sibling_support_set`, `:125 resolve_target_dependency`, `:169 _collect_achieved_outcome` | Filled sibling representative text and legacy plural allowed IDs | Upstream layer A relevance boundary, not a downstream witness selector. Exactly one dependency slot required; multiple dependencies fail closed. Scope by support-ID intersection before target-local text relevance. Do not widen this collector during I4-3. |
| `sufficiency_recovery_targets.py:213 _relationship_unverified_roles`; pairing/context helpers | Completion/role states, source markers; representative context text | Infers failed joint gate from filled completion roles + incomplete instance. Parent gaps use eligible_parent_instances. Does not independently select witnesses. |
| `parent_synthesis_ledger.py:126 _support_set`, `:218 _relational_identity`, `:225 _accumulate_relational`, `:274 _atomic_candidate` | Legacy plural and representative IDs/text; complete + own roles; engine witness IDs | Layer C dependency. Relational claim support can come from the shared helper while claim values/identity still come from representatives. A Boolean-only repair can therefore leave claims misaligned. No changes here. |
| `:414 _direction_or_effectiveness_claims` | Complete-instance observation sets and direction filter | Inherits selection defects upstream; no candidate selection. |
| `answer_plan/relations.py:34 _stored_metadata_check`, `:62 relation_units`, status/claim helpers | Shared I1 derivation and stored parity; representative operand fields | Recomputes witness through shared function, verifies stored metadata, then also requires filled operands and instance completeness for renderable relation status. No independent candidate selection. |
| `answer_plan/classify.py:254 _operand_surfaces`, `:258 _evaluate_direction`; generic-map/relational evaluation | Legacy relation-unit operand texts, claim support IDs, sealed quote sentences | Shared direction classifier, but still representative operands. Exposed downstream handoff for I4-4; not repaired by this audit. |

A production-source search for `candidate_supports`, `supporting_proposition_ids`, `witness_ids` and their helpers confirmed the boundary: candidate semantic consumption is in engine aggregation and mapping, not a relationship-selector implementation. Other plural-ID uses in stages/supervisor evaluation are ledger/coverage data, not RoleBinding relationship verifiers. Rendering, model-context and identity readers of representative text are downstream dependencies, not evidence that the representative is a complete witness.

## 4. Historical meaning and exact eligibility

Historical `same_proposition` means a single proposition ID common to all participating own-role support sets. The Phase 3 report records the different-primary/same-recorded-support failure; current engine tests freeze its plural-support correction:
`test_primary_selection_order_cannot_change_truth_when_support_sets_are_identical`,
`test_bindings_with_one_shared_supporting_proposition_pass`, and
`test_disjoint_support_sets_fail_even_when_conceptually_from_one_anchor`.
The original singleton behavior remains covered. Extending **which eligible support is selected** generalizes that existing relation; it does not change proposition identity into anchor identity.

[Phase 18 implementation §3](PHASE18_DIRECTION_EFFECTIVENESS_IMPLEMENTATION_RESULTS.md) explicitly rejected a union across own roles for observation scope. Its example A={p1,p2}, B={p1,p3} admits p1 only; ingredient p2 must not annotate the relation. [Phase 32 I1](PHASE32_I1_RELATION_WITNESS_RESULTS.md) separately freezes verified common own evidence, inherited-referent containment, no distributed witnesses, and the all-inherited rejection. Neither historical contract says “the first candidate is authoritative.”

For a future version, consume validated evaluated records with:

```text
eligible(c) = (c.admissible is True) AND (c.attachment_ambiguous is False)
```

Do not recompute or reinterpret support policy at the witness layer. `admissible` already encodes independent guard and policy gates; attachment remains orthogonal. `support_label`, attribution provenance, captions and authority-veto metadata cannot add another implicit evidence ranking or gate. Candidate `admissible=None` is not true; explicit historical versions keep their old path.

| Role condition | Relationship treatment |
|---|---|
| Filled, multiple eligible resolved | Evaluate all eligible alternatives through compatible assignments. |
| Filled, eligible plus excluded/ambiguous | Only eligible resolved alternatives can establish truth. Retained exclusions cannot donate IDs or text. |
| Ambiguous, only otherwise admissible ambiguous attachment | Cannot establish true relation; preserve ambiguous role state and the existing instance-state rules. Diagnostic evaluation may explain the block. |
| Missing, only excluded candidates | Cannot establish true relation. |
| Missing, no candidates | Cannot establish true relation. |
| Filled legacy role without candidate key | One compatible legacy support view, retaining its plural IDs and own/inherited source. Do not retroactively apply achieved-outcome policy to model/category/other strategies. |
| Candidate key present but empty/all ineligible | No legacy fallback, even if stale representative fields are populated. Inconsistent filled state should fail closed/diagnose rather than resurrect support. |

At the full relationship boundary, missing/ambiguous **required** operands block I1 witnessing and normal completeness. An unused unfilled alternative does not block a satisfied alternative group. A diagnostic helper may inspect the subset of filled own roles while an instance is incomplete; its nonempty support set must not be mistaken for completed relation truth.

## 5. Order dependence, reachability and no union-splicing

The requested P1/P2 construction gives exactly:

```text
sibling = legacy filled support {P2}
evidence = [A: resolved, admissible, {P1},
            B: resolved, admissible, {P2}]

v7 role state                    filled in both orders
A then B -> projected P1          complete=False; relation_witnessed=False
B then A -> projected P2          complete=True;  relation_witnessed=True
existential assignment B+sibling true in both orders; witness P2
```

This is an observed failure of unchanged production **binding consumers**, using schema-valid evaluated records. It is not presented as a current q_aib replay regression or as a case already emitted by the current two-role collector. That collector scopes candidates to the unique sibling's legacy allowed proposition IDs before relevance; with sibling support exactly {P2}, P1 would be discarded upstream. More than one dependency slot also fails closed today. Thus the small counterexample alone does **not** prove current collector reachability of arbitrary two-/three-candidate-role relationships.

Those restrictions do not establish the requested invariant for all supported downstream binding sets, nor for witness-selected **text**. They are upstream collection restrictions, not a candidate-aware relationship contract. §8 supplies a production-grounded same-proposition multi-assertion counterexample for the latter. Keep this distinction explicit when turning the audit into regression tests; do not expand collection to manufacture reachability.

The inverse family is equally important. An excluded matching P2 beside eligible nonmatching P1 must remain false; so must attachment-ambiguous matching P2 beside resolved nonmatching P1. Guard-only, policy-only, both, empty, and ambiguous-plus-excluded cases were exercised separately. Current projection avoids those false positives; a future selector must preserve that property.

**Union nuance.** Let E(r) be the eligible candidates for role r and S(c) a candidate's support IDs. For pure same-proposition only:

```text
exists p, one c_r in E(r) for every r, with p in every S(c_r)
iff
intersection_over_roles(union_over_eligible_candidates(S(c))) is nonempty
```

This equivalence means that a correctly filtered **per-role** union can be used as an internal index to find possible shared IDs. It would be incorrect to claim that this exact Boolean formula creates a false same-proposition witness. For the user's A1/P1,A2/P2 and B1/P2,B2/P3 example it correctly finds the actual A2+B1/P2 pair.

It still must not replace binding provenance or erase assignment identity. Recover an actual eligible candidate per role for each common ID; retain locators/gates and apply relation-specific text/verification constraints to that assignment. Unfiltered candidate unions admit exclusions. A union **across roles** admits ingredients. Pairwise-only joins admit A={P1,P2}, B={P2,P3}, C={P1,P3} despite the empty global intersection. Combining a proposition match from one candidate with text/designator/operand checks from another creates an invalid proof. Each successful verifier needs a compatible assignment; the existing OR across verifier IDs remains OR, not an invented conjunction.

## 6. Deterministic synthetic matrix

All candidate alternatives below are resolved and admissible unless marked X (guard+policy excluded), ? (attachment ambiguous), G (guard-only excluded), or Q (policy-only excluded). Single-list cases have a legacy sibling on P2. Multi-list cases make all listed roles required and own-evidence. A candidate has exactly the listed singleton support set; propositions are verified. Current truth below is both production instance completeness and I1 witnessed truth for these fixtures. “Reverse” reverses every candidate list; the audit also ran **every independent per-role permutation**, not just simultaneous reversal.

| Case | Candidate lists | Current forward / all reversed | Current true / permutations | Existential result, all permutations |
|---|---|---|---:|---|
| A | [P2] | true / true | 1/1 | true; P2 |
| B | [P1] | false / false | 0/1 | false; no witness |
| C | [P2,P1] | true / false | 1/2 | true; P2 |
| D | [P1,P2] | false / true | 1/2 | true; P2 |
| E | [P1,P3] | false / false | 0/2 | false; no witness |
| F | [P2 X,P1] | false / false | 0/2 | false; no witness |
| G | [P2,P1 X] | true / true | 2/2 | true; P2 |
| H | [P2 ?] | false / false | 0/1 | false; no witness |
| I | [P1,P2] × [P2,P3] | false / false | 1/4 | true; P2 |
| J | [P1,P2] × [P3,P2] × [P4,P2] | false / true | 1/8 | true; P2 |
| K | [P1,P2] × [P2,P3] × [P1,P3] | false / false | 0/8 | false; no witness |
| M-empty | [] | false / false | 0/1 | false; no witness |
| N-excluded | [P2 X] | false / false | 0/1 | false; no witness |
| O-ambiguous-plus-eligible | [P2 ?,P1] | false / false | 0/2 | false; no witness |
| P-guard-only | [P2 G,P1] | false / false | 0/2 | false; no witness |
| Q-policy-only | [P2 Q,P1] | false / false | 0/2 | false; no witness |
| R-ambiguous-excluded | [P2 ?,G] | false / false | 0/1 | false; no witness |

L is the permutation obligation applied to C–G, I–K and the extra multi-candidate families above. All 33 required executions and all nine additional executions met their manually specified existential expectations. Current production disagreed in 12 executions: C/D once each, I three times, J seven times. There were no current false positives in this matrix.

Additional unchanged I1 checks on scratch inputs: all inherited → false/`no_own_operand`; unverified common proposition → false/`no_admissible_candidate`; inherited referent absent from the own proposition → false/`inherited_referent_absent`; same inherited referent present → true. The oracle preserved each result. Existing continuation-anchor tests were also rerun with the historical witness battery (§11).

The minimal oracle specification is reproducible without a production edit:

```python
# Planning pseudocode; no new production API or version.
views(binding):
    if binding.state != "filled": return []
    if "candidate_supports" not in binding: return [legacy_view(binding)]
    validate_evaluated_records(binding.candidate_supports)
    return [view(c, binding.source) for c in binding.candidate_supports
            if c.admissible is True and c.attachment_ambiguous is False]

# For each unchanged historical consumer's participating-role set:
for assignment in cartesian_product(views(binding[r]) for r in participating_roles):
    projected = scratch_bindings_with_assignment_text_and_ids(assignment)
    evaluate_unchanged_same_proposition_or_I1(projected)
# Truth = any success. IDs = all successful witness IDs.
# Proof/observation records preserve each assignment's own candidate references.
```

For these fixtures use `se.new_candidate_support` with current_document, non_synthetic_or_unspecified, result; use interpretation for policy rejection, authored `["hedged"]` for guard rejection and the existing empirical policy evaluator. Project with `sm._project_evaluated_supports`; compare `se.recompute_instance` and `rw.witness_instance` against the existential loop. The fixtures, expected results and all permutation cardinalities above are fully specified. The audit harness is not added to production or committed as a future implementation test suite.

## 7. Real v7 replay

There are **40 I1 relational instances**, covering c2, c4, c5, c6, c8, c9, c10, c11 and c12. c1 adds one required-plus-alternative joint-grounding instance, so the full audited table has **41 instances**. Every stored I1 object and every direction-bearing instance is covered in Appendix A.

- Eight relational instances are witnessed: c2/p47; c4/p2+p11; c4/p40; five c8/p41 instances.
- Eight are complete but unwitnessed: all four c5 and all four c6 instances. Each fails inherited-referent containment.
- Twenty-four have incomplete required operands.
- Zero current-versus-existential Boolean disagreements; zero witness-ID disagreements. The engine's participating-role joint checks also agree on all 41 audited instances.
- The only filled role with >1 retained support is c3/`c3#suff:attitude-manifestation`/null/`attitude_manifestation_evidence`: first candidate p7 with support [p7,p3,p14,p17,p26], admissible/resolved result; second p9 with support [p9,p20], interpretation excluded independently by hedged and empirical policy. Legacy representative remains p7. Counts: **2 total, 1 eligible, 1 eligible support set**.
- There are **zero** real >1 eligible-resolved cases and zero differing eligible provenance-set cases. c3 is not an I1 relation: its multi-candidate role is nevertheless explicitly audited here.
- The full v7 evidence inventory remains 15 candidates, 10 eligible and five dual-excluded; evidence-role states remain 10 filled, 16 missing, zero ambiguous.

c5 and c6 inherit each of c4's two complete region instances and pair with their own model-nominated behavior/attitude values. Engine completeness trusts the parent role as background; I1 separately asks whether an own proposition contains that inherited referent. None does. Candidate-set selection offers no new own evidence here: these are legacy singleton views. Their eight complete-but-unwitnessed outcomes must not be “fixed” by pooling parent evidence or equating completeness with witnessing.

c9 has five instances inherited from the five complete c8 instances; every named_scale_or_instrument role is missing. All five are incomplete and unwitnessed; neither retained exclusions nor the parent proposition can fill the missing own role. c8 remains open-list and partially filled. c10/c12 still acquire no achieved-outcome candidates. Nothing in this audit changes cardinality, exists, open-list or for-each aggregation.

The prospective structural comparison changes **0 role states, 0 of 13 requirement states, 0 of 40 I1 witness results, and 0 direction/effectiveness outcomes** on this corpus. Parent eligibility/pairings and the 48 recovery targets therefore have no selection-induced change. The accepted replay still yields 17 ParentClaims, nine AnswerPlan nodes and 33 passing answer invariants. These are the actual baseline outputs, not a claim that an unimplemented v8 serialization has the same bytes. The oracle supplies no new successful assignment on the real map that would change the downstream inputs.

## 8. Direction and effectiveness: proof alignment is mandatory

Current direction evidence is not simply “read the representative text as a quote.” The diagnostic first intersects **representative-level support sets** to choose physical units, then scans those units' full passages. It independently passes representative operand texts and the I1 witness-ID set. Effectiveness uses the same scoped units but has no extra I1 eligibility check. This distinction explains both failures below.

### 8.1 Requested non-witness A / witness B fixture

Scratch binding: evidence A=(P1,“alpha”) then B=(P2,“gamma”), both eligible/resolved; sibling=(P2,“beta”). Unit P1 says “alpha was negatively associated with beta.” Unit P2 says “gamma was positively associated with beta.” Both sealed propositions are verified. This is a consumer-boundary fixture, not a claim about the present achieved-outcome collector's two-role output.

| Audit projection | Inspected IDs | Operand surfaces | Direction result | Effectiveness |
|---|---|---|---|---|
| Current production | none: representative support intersection empty | alpha, beta | no observations | no observations |
| Change only witnessed Boolean/IDs on instance | still none: engine scope remains empty | alpha, beta | no observations | no observations |
| Also correct evidence IDs, leave operand representative | P2 | alpha, beta | positive, target unknown, `relation_without_two_operands`, ineligible | P2 supported |
| Use B's witness assignment for both IDs and operands | P2 | gamma, beta | positive, target relation, eligible | P2 supported |

These outputs came from unchanged `_instance_scoped_units`, `find_direction_observations`, `find_effectiveness_observations` and the shared direction classifier with separately supplied audit projections. No negative observation from P1 is allowed to annotate the P2 relationship.

### 8.2 A reachable grounding shape: same ID, different assertion text

The unchanged v7 achieved-outcome binder, with sibling target “alpha” supported by P2, produced **two admissible resolved candidates** from:

> We found alpha was positively associated with beta. We found alpha was negatively associated with beta.

Both have support [P2], current_document/result, no guard exclusions, passing empirical policy. The preserved assertion coordinates are [0,50] and [52,102]; exact texts are the corresponding local assertions without the final periods. The binder genuinely grounds and evaluates these records; the audit then reorders that unchanged emitted candidate set and invokes the unchanged projection and observation functions.

| Projection order | Completeness / I1 witness | Eligible direction sentence | Production summary |
|---|---|---|---|
| positive assertion, negative assertion | true / P2 | positive sentence only; negative has only one recognized operand surface | positive consensus, no conflict |
| negative assertion, positive assertion | true / P2 | negative sentence only; positive has only one recognized operand surface | negative consensus, no conflict |

This is an actual classifier/collector-produced candidate shape. Reversal occurs at the candidate-set/projection boundary, not by pretending the classifier discovers spans randomly. The two assertions can equally be reordered in preserved discovery without changing the evidence set. It demonstrates why “same eligible proposition sets” is sufficient for the pure common-ID Boolean invariant, **but not for representative-text consumers**.

A separate in-memory combination of the two assignment-eligible observations fed the **unchanged** summary function: consensus=null, observed_values=[], within-instance conflict=true, across-instance heterogeneity=false. That is the required conflict-preserving direction behavior when both successful alternatives are consumed. Do not pick a canonical “best” candidate and discard the other sign.

**Minimal future seam:** a successful witness selection exposes its selected support references, locators, join IDs and operand surfaces together. Observation construction consumes that same assignment, keeps candidate-backed evidence bounded to its verified assertion/sentence locator, and does not scan an unrelated candidate or borrow an excluded assertion from the same proposition. A legacy support with no local candidate locator keeps an explicitly labeled legacy evidence scope; do not fabricate a span. Deduplicate repeated physical observations without erasing distinct assertions or opposing outcomes. Aggregate all supported observations with the existing conflict rules.

The exact handling of sentence boundaries, legacy whole-unit scope and effect-negation metadata must be specified in I4-3B before implementation. No new polarity inference, authority-veto rule or guard reinterpretation is authorized. Likewise, do not silently tighten I1's inherited-referent **sealed-quote** containment to an assertion-only rule: that would be a separate relationship meaning change, not merely candidate selection.

## 9. Smallest mechanism and witness provenance

Reuse the existing split: engine joint grounding/completion, shared `relation_witness` for own/inherited verified relation evidence, and the diagnostic observation seam. Share an eligible-support-view adapter/selector rather than duplicating candidate filtering in each caller. Preserve these contracts:

1. Resolve the consumer's participating roles exactly as today. Completion uses required plus filled alternatives; I1 uses required roles. Optional roles do not become obligations. Preserve immediate own/inherited source identity.
2. Obtain eligible views. Candidate-backed bindings never fall back to representatives. Legacy bindings supply one view under their existing contract. Validate malformed evaluated records; do not rerun policy or broaden collection.
3. For same_proposition, index eligible own candidates by support ID, find IDs common across all participating own roles, and retain actual candidate assignments for each shared ID. This can avoid searching impossible Cartesian products. No pairwise-only success and no provenance ranking.
4. For engine verifier OR, retain which verifier and which assignment succeeded. A shared-designator proof remains distinct from common-proposition proof. Its existing missing-context failure stays unchanged; do not fabricate a proposition witness from a link-only success.
5. For I1, additionally require at least one own role, a verified common own proposition and all selected inherited referents in that proposition under the selected version's containment rule. Parent supports remain context, not donated child evidence.
6. Derive Boolean truth existentially, but preserve all successful evidence alternatives needed for deterministic witness IDs and observations. Sorting is for stable output only. Do not use discovery-first or a canonical first tuple to decide the sign/effectiveness.
7. Preserve existing role states, quantifiers and independent completion/witness distinctions. A later version's changed joint outcome can naturally affect completeness, parent pairing and recovery; do not add new provenance-based role states.

The smallest provenance contract should expose:

| Field group | Required content |
|---|---|
| Witness context | Child, requirement, instance, participating-role set and consumer purpose (completion joint proof versus I1 own/inherited witness). |
| Semantic identity | Explicit sufficiency version and verifier/rule ID; distinguish same_proposition and operand_source_witness. |
| Assignment | Role → selected stable support reference plus own/inherited source; one actual compatible assignment per proof. Legacy roles are explicitly tagged legacy binding references. |
| Candidate identity | Instance/role-scoped immutable grounding identity, based on span_proposition_id + assertion_span + sealed quote identity; no discovery-order index as identity. Specify a deterministic text/support fingerprint fallback for valid records without spans. |
| Evidence locator | Candidate supporting_proposition_ids, anchor ID, assertion span and exact-text hash/reference; predicate/content spans available by lookup. Preserve the sealed quote hash/coordinate basis. |
| Eligibility receipt | Reference/fingerprint to the evaluated candidate's admissible, attachment status, guard_exclusions and support_policy_evaluation. Preserve attribution relation/aggregation/kind and attribution proof reference for inspection. |
| Join proof | Common proposition ID for same_proposition; distinct explicit basis for other verifiers. I1 adds sealed-verification/continuation and inherited-referent checks. |
| Observation handoff | Selected evidence locator and operand text references **from that assignment**, plus witness reference on each derived observation. |

Do not duplicate entire candidate objects in every witness or make support_label part of semantic identity. Referential lookup must be unambiguous: identical candidate identities with conflicting evidence/gate payloads should not be silently merged. The exact compact serialization, duplicate policy and no-span fallback are I4-3B design outputs. Do not solve combinatorics by silently capping successful candidates or selecting only the first tuple.

The real parent propagation code copies candidate lists when present, so the selector must keep inherited source status separate from those candidates' original ownership. It must never turn a carried parent candidate into own child evidence.

### same_local_assertion decision

`target_relevance.verify_shared_local_assertion` is a thin wrapper over the same local relevance primitive used before achieved-outcome candidate creation. I4-1j's report established that whole-passage input made it vacuous then; I4-2a now supplies actual narrowed assertion text, so the primitive is usable, but usability is not an authored requirement.

All current authored achieved-outcome candidates already pass target-local relevance to their unique dependency before construction. Calling the same primitive again adds no missing candidate-selection behavior. No authored relationship in the replay requests same_local_assertion; the registry still contains only same_proposition and contract_directed_links. Multi-own model-nominated roles might someday need a distinct assertion-co-occurrence contract, but that is not presently authored or specified. **Keep it unregistered and deferred.**

## 10. Next increment, version and answer-layer boundary

**Recommend I4-3B — V8 compatible-witness selection and observation-alignment integration design. READY for that bounded read-only design.**

Its exact deliverables should be a closed support-view/proof schema, deterministic eligible assignment algorithm, consumer-by-consumer version dispatch plan, and preregistered regression expectations using this audit's fixtures. Resolve only:

- Stable candidate references including legacy/no-span adapters, duplicate identities and inherited copies.
- Separate participation rules for engine completion and I1 witnessing; preserve existing verifier OR and absent link context.
- Shared assignment transport to both witness consumers and direction/effectiveness. Include same-ID/different-assertion direction conflict, not merely the P1/P2 Boolean case.
- Observation locator/sentence scope, physical deduplication and passage-flag handling, with no excluded candidate leakage.
- A precise handoff to currently representative-based ParentClaims/AnswerPlan: identify what can remain historical/display-only during B integration and what must wait for I4-4. Never claim candidate-aware witness truth makes old representative claim values correct.
- Exact v4–v7 isolation and expected prospective v8 real-map parity at the semantic level, plus synthetic outcome changes. No need to broaden collection, add relational databases, author new verifiers or change Layer A.

The answer-layer work can be planned against the future proof contract, but **candidate-aware ParentClaims/AnswerPlan integration should not begin before I4-3 supplies it**. Current Layer C could otherwise combine newly selected witness IDs with a different representative's text. This report identifies the dependency and leaves Layer C unchanged.

The eventual boundary is `sufficiency-semantics-v8`, because identical candidate evidence can change completeness, witnessed truth, direction and related recovery behavior under the corrected rule. Zero disagreement on q_aib cannot justify mutating v7. The repository's explicit v5 grounding, v6 attribution and v7 policy boundaries provide the precedent. Preserve historical dispatch rather than modifying a globally shared helper in place for all versions. PLAN_VERSION remains untouched here; any future answer schema decision belongs to its own authorized increment.

I4-3A is complete. No I4-3 implementation, same_local_assertion registration, I4-4, claim-goal/veto work or I2-3 begins in this increment.

## 11. Verification receipt

| Explicit replay | SHA-256 of actual rerun | Result |
|---|---|---|
| v4 | `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a` | exact accepted baseline |
| v5 | `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77` | exact accepted baseline |
| v6 | `dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be` | exact accepted baseline |
| v7 | `04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72` | exact accepted baseline |

Replay serialization is the existing sorted JSON, UTF-8, CRLF, terminal-newline convention in `test_i4_2b3_replay.replay_bytes`. Input ledger/map and packet hashes are verified by the existing harness before consumption.

- Actual four-version offline replay: all four exact hashes above.
- Real comparison: 41 joint-check instances, 40 I1 instances, zero Boolean or witness-ID differences against the separate oracle.
- Synthetic required matrix: 33 executions; expanded matrix: 42; current false negatives disclosed rather than hidden as passing production behavior.
- Four additional I1 source/verification checks preserved.
- Production-grounded same-P2 two-assertion direction example: two permutations, differing current consensus; combined assignment-eligible observations yield conflict with no consensus.
- Targeted unchanged historical battery: `python -m pytest experiments/ask_cli_revised/test_relation_witness.py experiments/ask_cli_revised/test_sufficiency_direction_effectiveness.py experiments/ask_cli_revised/test_sufficiency_engine.py -q` → **130 passed, 2 subtests passed**.
- Accepted v7 downstream invariant report: **33/33 pass**.
- No full suite, live retrieval, model inference, external search or live E2E. All oracle/projection work was in memory.
- Authorized tracked changes: this report and one experiment-lineage append only. No Python, classifier, schema, policy, verifier, semantic-version, ParentClaim or AnswerPlan source changes.

## Appendix A. Every real relational/joint instance and binding

The tables are generated from the actual v7 rerun, not manually reconstructed from older reports. Null instance keys are written `null`. “C/E” means retained candidate count / admissible resolved candidate count. “Absent” means no candidate key, so a filled binding has one **legacy** support view; its candidate count remains zero, not one invented candidate. Eligible sets list each actual candidate separately in preserved ID order. Missing/ambiguous bindings offer no witness view.

“Joint” is the raw current/proposed multi-own-role helper result, including its <2-role bypass; it is not a completeness verdict. “Witness” is the stricter I1 result; c1 is N/A because it has one required role plus alternatives. All rows agree between current and existential results.


### c1 — c1#suff:neural-manifestation

Quantifier: `exists`; requirement state: `filled`; verifiers: `same_proposition`. Required: `neural_manifestation_evidence`. Alternatives: `[["neural_measure_or_modality","brain_region_or_network"]]`.

| Instance | Complete / state | Joint current / proposed | I1 current / proposed, witness IDs | I1 failure |
|---|---|---|---|---|
| `null` | true / filled | true / true | N/A | — |

| Instance | Role / state / source | C/E; key | Legacy representative: ID; exact_text | Representative support | Complete eligible candidate support sets / legacy view |
|---|---|---|---|---|---|
| `null` | `neural_measure_or_modality` / missing / none | 0/0; absent | null; null | ∅ | none |
| `null` | `brain_region_or_network` / filled / model_mapping | 0/0; absent | p11; the specific amygdala response | {p11,p2} | legacy {p11,p2} |
| `null` | `neural_manifestation_evidence` / filled / deterministic_mapping | 1/1; present | p2; the specific amygdala response to facial anomalies correlated with stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, and less prosociality toward people with facial anomalies | {p11,p2} | {p2,p11} |

### c2 — c2#suff:behavioral-manifestation

Quantifier: `exists`; requirement state: `filled`; verifiers: `same_proposition`. Required: `behavior_or_behavioral_measure`, `behavioral_manifestation_evidence`. Alternatives: `[]`.

| Instance | Complete / state | Joint current / proposed | I1 current / proposed, witness IDs | I1 failure |
|---|---|---|---|---|
| `i::4777c74a36ed08b9` | false / partially_filled | true / true | false / false; ∅ | incomplete_operands |
| `i::9fb27754ba7442ef` | false / partially_filled | true / true | false / false; ∅ | incomplete_operands |
| `i::76d9e54baf790d84` | true / filled | true / true | true / true; {p47} | — |

| Instance | Role / state / source | C/E; key | Legacy representative: ID; exact_text | Representative support | Complete eligible candidate support sets / legacy view |
|---|---|---|---|---|---|
| `i::4777c74a36ed08b9` | `behavior_or_behavioral_measure` / filled / model_mapping | 0/0; absent | p35; decisions that were incongruent with behavioral bias (share with bad partner and keep with good partner versus the alternative choices) | {p35} | legacy {p35} |
| `i::4777c74a36ed08b9` | `behavioral_manifestation_evidence` / missing / none | 0/0; absent | null; null | ∅ | none |
| `i::9fb27754ba7442ef` | `behavior_or_behavioral_measure` / filled / model_mapping | 0/0; absent | p46; share decisions between partners (good versus bad) | {p46} | legacy {p46} |
| `i::9fb27754ba7442ef` | `behavioral_manifestation_evidence` / missing / none | 0/0; absent | null; null | ∅ | none |
| `i::76d9e54baf790d84` | `behavior_or_behavioral_measure` / filled / model_mapping | 0/0; absent | p47; faster to share when playing with the good partner compared to the bad | {p47} | legacy {p47} |
| `i::76d9e54baf790d84` | `behavioral_manifestation_evidence` / filled / deterministic_mapping | 1/1; present | p47; we observed that participants were faster to share when playing with the good partner compared to the bad (t11 ¼ –3.73, P o 0.005) and neutral partners (t11 ¼ –1.89, P ¼ 0.08) | {p47} | {p47} |

### c4 — c4#suff:specific-region

Quantifier: `exists`; requirement state: `filled`; verifiers: `same_proposition`. Required: `named_brain_region_or_network`, `region_bears_on_bias_evidence`. Alternatives: `[]`.

| Instance | Complete / state | Joint current / proposed | I1 current / proposed, witness IDs | I1 failure |
|---|---|---|---|---|
| `i::ac9b72f14d53f532` | true / filled | true / true | true / true; {p11,p2} | — |
| `i::a3ab9566580a7fe4` | true / filled | true / true | true / true; {p40} | — |

| Instance | Role / state / source | C/E; key | Legacy representative: ID; exact_text | Representative support | Complete eligible candidate support sets / legacy view |
|---|---|---|---|---|---|
| `i::ac9b72f14d53f532` | `named_brain_region_or_network` / filled / model_mapping | 0/0; absent | p11; the specific amygdala response | {p11,p2} | legacy {p11,p2} |
| `i::ac9b72f14d53f532` | `region_bears_on_bias_evidence` / filled / deterministic_mapping | 1/1; present | p11; the specific amygdala response to facial anomalies correlated with stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, and less prosociality toward people with facial anomalies | {p11,p2} | {p11,p2} |
| `i::a3ab9566580a7fe4` | `named_brain_region_or_network` / filled / model_mapping | 0/0; absent | p40; increased amygdala reactiv- ity | {p40} | legacy {p40} |
| `i::a3ab9566580a7fe4` | `region_bears_on_bias_evidence` / filled / deterministic_mapping | 1/1; present | p40; Laypersons with high levels of implicit bias toward those with facial anomalies demonstrated increased amygdala reactiv- ity.6 | {p40} | {p40} |

### c5 — c5#suff:brain-behavior

Quantifier: `exists`; requirement state: `filled`; verifiers: `same_proposition`. Required: `named_brain_region_or_network`, `behavior_or_behavioral_measure`. Alternatives: `[]`.

| Instance | Complete / state | Joint current / proposed | I1 current / proposed, witness IDs | I1 failure |
|---|---|---|---|---|
| `i::a3ab9566580a7fe4::13b13ddc969b96ae` | true / filled | true / true | false / false; ∅ | inherited_referent_absent |
| `i::a3ab9566580a7fe4::855c307939056b14` | true / filled | true / true | false / false; ∅ | inherited_referent_absent |
| `i::ac9b72f14d53f532::4a3f8a1c59aaa360` | true / filled | true / true | false / false; ∅ | inherited_referent_absent |
| `i::ac9b72f14d53f532::e4796948ec530e13` | true / filled | true / true | false / false; ∅ | inherited_referent_absent |

| Instance | Role / state / source | C/E; key | Legacy representative: ID; exact_text | Representative support | Complete eligible candidate support sets / legacy view |
|---|---|---|---|---|---|
| `i::a3ab9566580a7fe4::13b13ddc969b96ae` | `named_brain_region_or_network` / filled / parent_context | 0/0; absent | p40; increased amygdala reactiv- ity | {p40} | legacy {p40} |
| `i::a3ab9566580a7fe4::13b13ddc969b96ae` | `behavior_or_behavioral_measure` / filled / model_mapping | 0/0; absent | p46; participants made more share decisions overall when playing with the good partner than with the bad | {p46} | legacy {p46} |
| `i::a3ab9566580a7fe4::855c307939056b14` | `named_brain_region_or_network` / filled / parent_context | 0/0; absent | p40; increased amygdala reactiv- ity | {p40} | legacy {p40} |
| `i::a3ab9566580a7fe4::855c307939056b14` | `behavior_or_behavioral_measure` / filled / model_mapping | 0/0; absent | p47; participants were faster to share when playing with the good partner compared to the bad | {p47} | legacy {p47} |
| `i::ac9b72f14d53f532::4a3f8a1c59aaa360` | `named_brain_region_or_network` / filled / parent_context | 0/0; absent | p11; the specific amygdala response | {p11} | legacy {p11} |
| `i::ac9b72f14d53f532::4a3f8a1c59aaa360` | `behavior_or_behavioral_measure` / filled / model_mapping | 0/0; absent | p46; participants made more share decisions overall when playing with the good partner than with the bad | {p46} | legacy {p46} |
| `i::ac9b72f14d53f532::e4796948ec530e13` | `named_brain_region_or_network` / filled / parent_context | 0/0; absent | p11; the specific amygdala response | {p11} | legacy {p11} |
| `i::ac9b72f14d53f532::e4796948ec530e13` | `behavior_or_behavioral_measure` / filled / model_mapping | 0/0; absent | p47; participants were faster to share when playing with the good partner compared to the bad | {p47} | legacy {p47} |

### c6 — c6#suff:brain-attitude

Quantifier: `exists`; requirement state: `filled`; verifiers: `same_proposition`. Required: `named_brain_region_or_network`, `attitude_type_or_measure`. Alternatives: `[]`.

| Instance | Complete / state | Joint current / proposed | I1 current / proposed, witness IDs | I1 failure |
|---|---|---|---|---|
| `i::a3ab9566580a7fe4::f0daa6613a3449e9` | true / filled | true / true | false / false; ∅ | inherited_referent_absent |
| `i::a3ab9566580a7fe4::9492e632eeb1c2f9` | true / filled | true / true | false / false; ∅ | inherited_referent_absent |
| `i::ac9b72f14d53f532::2f2b08aa35e6e926` | true / filled | true / true | false / false; ∅ | inherited_referent_absent |
| `i::ac9b72f14d53f532::9fe92674ba934ce3` | true / filled | true / true | false / false; ∅ | inherited_referent_absent |

| Instance | Role / state / source | C/E; key | Legacy representative: ID; exact_text | Representative support | Complete eligible candidate support sets / legacy view |
|---|---|---|---|---|---|
| `i::a3ab9566580a7fe4::f0daa6613a3449e9` | `named_brain_region_or_network` / filled / parent_context | 0/0; absent | p40; increased amygdala reactiv- ity | {p40} | legacy {p40} |
| `i::a3ab9566580a7fe4::f0daa6613a3449e9` | `attitude_type_or_measure` / filled / model_mapping | 0/0; absent | p14; Explicit Bias Questionnaire | {p14,p17,p3,p7} | legacy {p14,p17,p3,p7} |
| `i::a3ab9566580a7fe4::9492e632eeb1c2f9` | `named_brain_region_or_network` / filled / parent_context | 0/0; absent | p40; increased amygdala reactiv- ity | {p40} | legacy {p40} |
| `i::a3ab9566580a7fe4::9492e632eeb1c2f9` | `attitude_type_or_measure` / filled / model_mapping | 0/0; absent | p26; Explicit Bias Questionnaire | {p26} | legacy {p26} |
| `i::ac9b72f14d53f532::2f2b08aa35e6e926` | `named_brain_region_or_network` / filled / parent_context | 0/0; absent | p11; the specific amygdala response | {p11} | legacy {p11} |
| `i::ac9b72f14d53f532::2f2b08aa35e6e926` | `attitude_type_or_measure` / filled / model_mapping | 0/0; absent | p14; Explicit Bias Questionnaire | {p14,p17,p3,p7} | legacy {p14,p17,p3,p7} |
| `i::ac9b72f14d53f532::9fe92674ba934ce3` | `named_brain_region_or_network` / filled / parent_context | 0/0; absent | p11; the specific amygdala response | {p11} | legacy {p11} |
| `i::ac9b72f14d53f532::9fe92674ba934ce3` | `attitude_type_or_measure` / filled / model_mapping | 0/0; absent | p26; Explicit Bias Questionnaire | {p26} | legacy {p26} |

### c8 — c8#suff:trait-construct

Quantifier: `open_list`; requirement state: `partially_filled`; verifiers: `same_proposition`. Required: `individual_difference_trait_or_construct`, `relationship_to_bias_manifestation`. Alternatives: `[]`.

| Instance | Complete / state | Joint current / proposed | I1 current / proposed, witness IDs | I1 failure |
|---|---|---|---|---|
| `U6::b2958c5ad5164563` | false / partially_filled | true / true | false / false; ∅ | incomplete_operands |
| `U6::ce8933c59b53a00f` | false / partially_filled | true / true | false / false; ∅ | incomplete_operands |
| `U6::da37435ef9b489b6` | false / partially_filled | true / true | false / false; ∅ | incomplete_operands |
| `U6::d41542e10edf3ea7` | false / partially_filled | true / true | false / false; ∅ | incomplete_operands |
| `U7` | false / missing | true / true | false / false; ∅ | incomplete_operands |
| `U23::24d132203292cebb` | true / filled | true / true | true / true; {p41} | — |
| `U23::8d7156b76bf6a6f7` | true / filled | true / true | true / true; {p41} | — |
| `U23::50b0d4004f2f502f` | true / filled | true / true | true / true; {p41} | — |
| `U23::f6027eb43b85593c` | true / filled | true / true | true / true; {p41} | — |
| `U23::910466e6604581fa` | true / filled | true / true | true / true; {p41} | — |
| `U24` | false / missing | true / true | false / false; ∅ | incomplete_operands |

| Instance | Role / state / source | C/E; key | Legacy representative: ID; exact_text | Representative support | Complete eligible candidate support sets / legacy view |
|---|---|---|---|---|---|
| `U6::b2958c5ad5164563` | `individual_difference_trait_or_construct` / filled / model_mapping | 0/0; absent | p20; negative attitudes (IAT and EBQ) | {p20,p9} | legacy {p20,p9} |
| `U6::b2958c5ad5164563` | `relationship_to_bias_manifestation` / missing / none | 1/0; present | null; null | ∅ | none |
| `U6::ce8933c59b53a00f` | `individual_difference_trait_or_construct` / filled / model_mapping | 0/0; absent | p20; social cognitive biases (just-world beliefs) | {p20,p9} | legacy {p20,p9} |
| `U6::ce8933c59b53a00f` | `relationship_to_bias_manifestation` / missing / none | 1/0; present | null; null | ∅ | none |
| `U6::da37435ef9b489b6` | `individual_difference_trait_or_construct` / filled / model_mapping | 0/0; absent | p20; emotional dispositions (affective empathy) | {p20,p9} | legacy {p20,p9} |
| `U6::da37435ef9b489b6` | `relationship_to_bias_manifestation` / missing / none | 1/0; present | null; null | ∅ | none |
| `U6::d41542e10edf3ea7` | `individual_difference_trait_or_construct` / filled / model_mapping | 0/0; absent | p20; undesirable behaviors (less generosity in the DG) | {p20,p9} | legacy {p20,p9} |
| `U6::d41542e10edf3ea7` | `relationship_to_bias_manifestation` / missing / none | 1/0; present | null; null | ∅ | none |
| `U7` | `individual_difference_trait_or_construct` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U7` | `relationship_to_bias_manifestation` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U23::24d132203292cebb` | `individual_difference_trait_or_construct` / filled / model_mapping | 0/0; absent | p41; attractiveness | {p41} | legacy {p41} |
| `U23::24d132203292cebb` | `relationship_to_bias_manifestation` / filled / deterministic_mapping | 1/1; present | p41; Spearman correlations revealed greater proportionality was associated with attrac- tiveness (ρ = 0.292, P < 0.001) and trustworthiness (ρ = 0.193, P < 0.001) | {p41} | {p41} |
| `U23::8d7156b76bf6a6f7` | `individual_difference_trait_or_construct` / filled / model_mapping | 0/0; absent | p41; trustworthiness | {p41} | legacy {p41} |
| `U23::8d7156b76bf6a6f7` | `relationship_to_bias_manifestation` / filled / deterministic_mapping | 1/1; present | p41; Spearman correlations revealed greater proportionality was associated with attrac- tiveness (ρ = 0.292, P < 0.001) and trustworthiness (ρ = 0.193, P < 0.001) | {p41} | {p41} |
| `U23::50b0d4004f2f502f` | `individual_difference_trait_or_construct` / filled / model_mapping | 0/0; absent | p41; anger | {p41} | legacy {p41} |
| `U23::50b0d4004f2f502f` | `relationship_to_bias_manifestation` / filled / deterministic_mapping | 1/1; present | p41; lesser proportionality was associated with impressions of anger (ρ = 0.132, P = 0.001), dominance (ρ = 0.259, P < 0.001), and threateningness (ρ = 0.234, P < 0.001) | {p41} | {p41} |
| `U23::f6027eb43b85593c` | `individual_difference_trait_or_construct` / filled / model_mapping | 0/0; absent | p41; dominance | {p41} | legacy {p41} |
| `U23::f6027eb43b85593c` | `relationship_to_bias_manifestation` / filled / deterministic_mapping | 1/1; present | p41; lesser proportionality was associated with impressions of anger (ρ = 0.132, P = 0.001), dominance (ρ = 0.259, P < 0.001), and threateningness (ρ = 0.234, P < 0.001) | {p41} | {p41} |
| `U23::910466e6604581fa` | `individual_difference_trait_or_construct` / filled / model_mapping | 0/0; absent | p41; threateningness | {p41} | legacy {p41} |
| `U23::910466e6604581fa` | `relationship_to_bias_manifestation` / filled / deterministic_mapping | 1/1; present | p41; lesser proportionality was associated with impressions of anger (ρ = 0.132, P = 0.001), dominance (ρ = 0.259, P < 0.001), and threateningness (ρ = 0.234, P < 0.001) | {p41} | {p41} |
| `U24` | `individual_difference_trait_or_construct` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U24` | `relationship_to_bias_manifestation` / missing / none | 0/0; absent | null; null | ∅ | none |

### c9 — c9#suff:trait-scale-pairing

Quantifier: `for_each_discovered_instance`; requirement state: `partially_filled`; verifiers: `same_proposition`. Required: `individual_difference_trait_or_construct`, `named_scale_or_instrument`. Alternatives: `[]`.

| Instance | Complete / state | Joint current / proposed | I1 current / proposed, witness IDs | I1 failure |
|---|---|---|---|---|
| `U23::24d132203292cebb` | false / partially_filled | true / true | false / false; ∅ | incomplete_operands |
| `U23::50b0d4004f2f502f` | false / partially_filled | true / true | false / false; ∅ | incomplete_operands |
| `U23::8d7156b76bf6a6f7` | false / partially_filled | true / true | false / false; ∅ | incomplete_operands |
| `U23::910466e6604581fa` | false / partially_filled | true / true | false / false; ∅ | incomplete_operands |
| `U23::f6027eb43b85593c` | false / partially_filled | true / true | false / false; ∅ | incomplete_operands |

| Instance | Role / state / source | C/E; key | Legacy representative: ID; exact_text | Representative support | Complete eligible candidate support sets / legacy view |
|---|---|---|---|---|---|
| `U23::24d132203292cebb` | `individual_difference_trait_or_construct` / filled / parent_context | 0/0; absent | p41; attractiveness | {p41} | legacy {p41} |
| `U23::24d132203292cebb` | `named_scale_or_instrument` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U23::50b0d4004f2f502f` | `individual_difference_trait_or_construct` / filled / parent_context | 0/0; absent | p41; anger | {p41} | legacy {p41} |
| `U23::50b0d4004f2f502f` | `named_scale_or_instrument` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U23::8d7156b76bf6a6f7` | `individual_difference_trait_or_construct` / filled / parent_context | 0/0; absent | p41; trustworthiness | {p41} | legacy {p41} |
| `U23::8d7156b76bf6a6f7` | `named_scale_or_instrument` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U23::910466e6604581fa` | `individual_difference_trait_or_construct` / filled / parent_context | 0/0; absent | p41; threateningness | {p41} | legacy {p41} |
| `U23::910466e6604581fa` | `named_scale_or_instrument` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U23::f6027eb43b85593c` | `individual_difference_trait_or_construct` / filled / parent_context | 0/0; absent | p41; dominance | {p41} | legacy {p41} |
| `U23::f6027eb43b85593c` | `named_scale_or_instrument` / missing / none | 0/0; absent | null; null | ∅ | none |

### c10 — c10#suff:culture-existence

Quantifier: `exists`; requirement state: `partially_filled`; verifiers: `same_proposition`. Required: `named_culture_or_population`, `bias_evidence_in_population`. Alternatives: `[]`.

| Instance | Complete / state | Joint current / proposed | I1 current / proposed, witness IDs | I1 failure |
|---|---|---|---|---|
| `i::e506b4436247cda9` | false / partially_filled | true / true | false / false; ∅ | incomplete_operands |
| `i::22b9d69edba8b78a` | false / partially_filled | true / true | false / false; ∅ | incomplete_operands |

| Instance | Role / state / source | C/E; key | Legacy representative: ID; exact_text | Representative support | Complete eligible candidate support sets / legacy view |
|---|---|---|---|---|---|
| `i::e506b4436247cda9` | `named_culture_or_population` / filled / model_mapping | 0/0; absent | p29; Hadza | {p29} | legacy {p29} |
| `i::e506b4436247cda9` | `bias_evidence_in_population` / missing / none | 0/0; absent | null; null | ∅ | none |
| `i::22b9d69edba8b78a` | `named_culture_or_population` / filled / model_mapping | 0/0; absent | p53; Hadza | {p53} | legacy {p53} |
| `i::22b9d69edba8b78a` | `bias_evidence_in_population` / missing / none | 0/0; absent | null; null | ∅ | none |

### c11 — c11#suff:culture-operationalization-pairing

Quantifier: `for_each_discovered_instance`; requirement state: `missing`; verifiers: `same_proposition`. Required: `culture_or_population`, `operationalization_or_measure`. Alternatives: `[]`.

| Instance | Complete / state | Joint current / proposed | I1 current / proposed, witness IDs | I1 failure |
|---|---|---|---|---|
| `U9` | false / missing | true / true | false / false; ∅ | incomplete_operands |
| `U10` | false / missing | true / true | false / false; ∅ | incomplete_operands |
| `U13` | false / missing | true / true | false / false; ∅ | incomplete_operands |

| Instance | Role / state / source | C/E; key | Legacy representative: ID; exact_text | Representative support | Complete eligible candidate support sets / legacy view |
|---|---|---|---|---|---|
| `U9` | `culture_or_population` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U9` | `operationalization_or_measure` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U10` | `culture_or_population` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U10` | `operationalization_or_measure` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U13` | `culture_or_population` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U13` | `operationalization_or_measure` / missing / none | 0/0; absent | null; null | ∅ | none |

### c12 — c12#suff:intervention-effectiveness

Quantifier: `exists`; requirement state: `missing`; verifiers: `same_proposition`. Required: `intervention`, `target_manifestation`, `observed_effect_or_outcome`. Alternatives: `[]`.

| Instance | Complete / state | Joint current / proposed | I1 current / proposed, witness IDs | I1 failure |
|---|---|---|---|---|
| `U1` | false / missing | true / true | false / false; ∅ | incomplete_operands |
| `U5` | false / missing | true / true | false / false; ∅ | incomplete_operands |
| `U14` | false / missing | true / true | false / false; ∅ | incomplete_operands |
| `U15` | false / missing | true / true | false / false; ∅ | incomplete_operands |
| `U16` | false / missing | true / true | false / false; ∅ | incomplete_operands |
| `U17` | false / missing | true / true | false / false; ∅ | incomplete_operands |

| Instance | Role / state / source | C/E; key | Legacy representative: ID; exact_text | Representative support | Complete eligible candidate support sets / legacy view |
|---|---|---|---|---|---|
| `U1` | `intervention` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U1` | `target_manifestation` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U1` | `observed_effect_or_outcome` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U5` | `intervention` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U5` | `target_manifestation` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U5` | `observed_effect_or_outcome` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U14` | `intervention` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U14` | `target_manifestation` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U14` | `observed_effect_or_outcome` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U15` | `intervention` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U15` | `target_manifestation` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U15` | `observed_effect_or_outcome` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U16` | `intervention` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U16` | `target_manifestation` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U16` | `observed_effect_or_outcome` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U17` | `intervention` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U17` | `target_manifestation` / missing / none | 0/0; absent | null; null | ∅ | none |
| `U17` | `observed_effect_or_outcome` / missing / none | 0/0; absent | null; null | ∅ | none |

## Appendix B. Every real nonempty direction observation

All 41 audited instances have an empty effectiveness observation list. Exactly six instances have nonempty direction observations, one each; all six are ineligible for relation direction. All other audited direction lists are empty. These lists remain identical under the real candidate-assignment comparison because every relevant eligible support view is the legacy one.

| Child / instance | Proposition | Sign | Target / reason | Relation eligible | Exact observation text |
|---|---|---|---|---|---|
| c5 / `i::a3ab9566580a7fe4::13b13ddc969b96ae` | p46 | null | unknown / single_operand_unbound_sign | false | In addition, when comparing share decisions between partners (good versus bad), participants made more share decisions overall when playing with the good partner than with the bad (t11 ¼ 3.26, P o 0.01) or neutral (t11 ¼ 2.0, P ¼ 0.07) partners. |
| c5 / `i::ac9b72f14d53f532::4a3f8a1c59aaa360` | p46 | null | unknown / single_operand_unbound_sign | false | In addition, when comparing share decisions between partners (good versus bad), participants made more share decisions overall when playing with the good partner than with the bad (t11 ¼ 3.26, P o 0.01) or neutral (t11 ¼ 2.0, P ¼ 0.07) partners. |
| c6 / `i::a3ab9566580a7fe4::f0daa6613a3449e9` | p14 | negative | unknown / single_operand_unbound_sign | false | Nevertheless, we found evidence for the “anomalous-is-bad” stereotype in explicit negative attitudes about people with facial anoma- lies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit Bias Questionnaire). |
| c6 / `i::a3ab9566580a7fe4::9492e632eeb1c2f9` | p26 | negative | unknown / single_operand_unbound_sign | false | Nevertheless, we found evidence for the “anomalous-is-bad” stereotype in explicit negative attitudes about people with facial anoma- lies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit Bias Questionnaire). |
| c6 / `i::ac9b72f14d53f532::2f2b08aa35e6e926` | p14 | negative | unknown / single_operand_unbound_sign | false | Nevertheless, we found evidence for the “anomalous-is-bad” stereotype in explicit negative attitudes about people with facial anoma- lies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit Bias Questionnaire). |
| c6 / `i::ac9b72f14d53f532::9fe92674ba934ce3` | p26 | negative | unknown / single_operand_unbound_sign | false | Nevertheless, we found evidence for the “anomalous-is-bad” stereotype in explicit negative attitudes about people with facial anoma- lies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit Bias Questionnaire). |

The c5/c6 complete-but-unwitnessed distinction, zero eligible direction observations, empty effectiveness lists and missing c9 scales are preserved. No extra witness is inferred from similar vocabulary or inherited source proximity.
