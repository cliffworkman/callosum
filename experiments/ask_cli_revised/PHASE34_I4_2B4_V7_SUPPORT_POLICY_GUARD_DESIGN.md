# PHASE 34 / I4-2b4 — v7 support-policy and guard-retention integration design

## Status, scope, and evidence

**Planning/docs only. READY for the bounded I4-2b5 implementation specified below. No v7 implementation
or production behavior change occurred in this audit.**

Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
Verified clean starting HEAD: `11486c031f0a3d9280866ef5bc4039301166f2c4`.
I4-2b3 attribution-only v6 is the accepted implementation. This report changes neither its classifier nor its
grounding contract. The authorized persisted changes are this report and the experiment lineage append.

The audit inspected the current engine, mapper, diagnostic orchestration, unit/guard producer, recovery,
version-routing tables, schema/reference tests, accepted I4-2b0/b1/b2/b3 reports and the committed replay
harness. The real projection used hash-verified saved packets and ledger/map inputs, held recorded
nominations fixed, and ran the existing v6 grounding, i4-2b3.0 attribution and downstream machinery.
Network connections were denied. No library lookup, live retrieval, model call, external search or live E2E
was used.

The core finding is confirmed: **10 -> 15 candidates, 10 eligible and 5 independently excluded by both
guard and policy; no evidence-role or requirement state changes.** Four missing c8 bindings acquire
inspectable candidate evidence and an exclusion reason. c10 and c12 remain candidate-empty.

Recommendation B remains intact: attribution was repaired first; the conservative absent-policy predicate
is retained. The historical uncorrected six-exclusion counterfactual in I4-2b0 is not rewritten.

## V1–V2. Pipeline and historical guard scope

Future v7 answers whether an already grounded, role-instance-relevant, correctly attributed candidate may
satisfy this role's evidence requirement. Activation is **achieved_outcome_predicate only**. Other mapping
strategies keep their existing guard and collection behavior; this increment does not introduce policy
activation for those strategies.

Freeze this order:

1. **A — receive** the role-scoped unit and the same authored RoleSpec/dependency context.
   Validate any present authored policy as schema data once at role entry, including an empty candidate
   scope. Invalid explicit policy is an error even if all units later fail grounding; schema validation is
   not evidence-policy evaluation.
2. **B — observe guards** from the historical unit flags, retaining every triggered authored identity.
   Do not discard the unit.
3. **C — ground and establish relevance** through the existing v6 sequence: coordinate validation,
   predicate localization, assertion join, deduplication, dependency scope, target relevance.
4. **D — refuse failed grounding/relevance.** No candidate for a failed/ambiguous join, target mismatch,
   unavailable/ambiguous dependency, or absent recognized hit. Guard metadata does not rescue any of these.
5. **E — annotate ownership** using the unchanged i4-2b3.0 path, context transport and R1/R2/R3 rules.
6. **F — attach guard_exclusions** to each successful candidate.
7. **G — select** absent empirical default versus the complete authored policy by **key presence**.
8. **H — evaluate policy** for every candidate, including candidates already excluded by a guard.
9. **I — derive admissible** from guard pass AND policy pass; derive the compatibility reason separately.
10. **J — aggregate the role** only after every candidate has its independent gate facts.
11. **K — project a legacy representative** only from resolved admissible candidates, after role aggregation.

Guards/policy must not alter assertion boundaries, candidate discovery order, proposition IDs/order,
attribution, spans, or target-relevance text. They do not select an assertion or widen a quote.

### Observed guard contract

`overview_evidence.build_units` computes `passage_flags(unit["passage"])` on the source passage;
`passage_flags` uses the existing _clean/has_hedge lexical machinery.
`sufficiency_mapping.is_admissible` currently applies:

```text
not any(unit.flags.get(name) for name in RoleSpec.disqualifying_guards)
```

Therefore v7 must retain the same **passage-level**, role-authored, truthiness-based guard facts.
Do not substitute classifier.hedged, candidate exact_text, or an assertion-local detector. A hedge elsewhere
in the same passage may exclude an otherwise unhedged local assertion; that historical limitation is
explicitly preserved. Guard identities absent from flags retain their historical false/missing behavior;
v7 does not introduce a new guard-name validation or detector vocabulary.

Emit triggered names in authored order, deduplicating repeated identical authored names at first occurrence
without rewriting the authored list. If several guards trigger, retain them all. Only the timing of the
achieved-outcome exclusion changes. Do not change global is_admissible or model-role guard filtering.

## V3–V6. Candidate schema, eligibility, and reasons

The smallest adequate additive schema has **two new candidate fields**, required on evaluated v7
achieved-outcome candidates and absent from historical v6 rows:

```text
guard_exclusions: list[str]

support_policy_evaluation:
    schema_version: "support-policy-evaluation-v1"
    policy_source: "absent_default" | "authored"
    policy_identity: string
    policy_snapshot: normalized policy data
    passed: bool
    failed_dimensions: ordered list of closed codes
    reasons: ordered list of closed codes
```

Retain every existing candidate field, including attribution, attachment_ambiguous, admissible and
inadmissibility_reason. No duplicate top-level inadmissibility_reasons field is needed: guard_exclusions
preserves actual guard identities, and policy evaluation preserves all policy failures. A third duplicate
reason list would add a consistency obligation without preserving any new fact.

### Precise meaning of admissible

```text
admissible = (guard_exclusions == []) AND support_policy_evaluation.passed
```

It means passing the evidence-admissibility gates v7 actually implements. It is not synonymous with
satisfying the role: attachment still matters at aggregation. Attachment ambiguity **never flips**
admissible. Every emitted v7 candidate must have a real bool; None remains the exact historical
v6 “unevaluated” state and is invalid input to v7 aggregation.

This is compatible with the current schema's bool-or-None field and its separate attachment_ambiguous
field. It corrects the old reference convention that encoded ambiguity as inadmissible=False.
No replacement eligibility field is necessary, provided the revised meaning and validation are explicit.

### Singular compatibility projection

Keep inadmissibility_reason for compatibility/display, derived from the two gate facts:

| Guard excluded? | Policy failed? | admissible | Candidate inadmissibility_reason |
|---|---|---|---|
| No | No | True | None, including otherwise-eligible attachment ambiguity |
| Yes | No | False | disqualifying_guard_excluded |
| No | Yes | False | support_policy_excluded |
| Yes | Yes | False | guard_and_support_policy_excluded |

There is no first-failure precedence. These scalar strings must not drive state. The existing
assertion_attachment_ambiguous candidate reason remains readable on historical schema records but is
not emitted as a v7 evidence-gate rejection. A v7 ambiguous **RoleBinding** can still use that reason.

For RoleBinding projection use:

- filled -> reason None;
- ambiguous -> assertion_attachment_ambiguous;
- missing with retained candidates -> candidate_supports_excluded;
- no successful candidate -> the existing missing/not_found path.

The engine's documented REASON_CODES should add the two applicable role-level strings; its candidate
reason vocabulary adds the two new guard-related strings. Historical versions emit no new reason.

### Closed policy failure vocabulary

For an authored policy, evaluate **all** dimensions in fixed order relation, aggregation, kind:

| Failed dimension | Closed reason |
|---|---|
| relation | assertion_relation_not_allowed |
| aggregation = require_synthesis | aggregation_requires_synthesis |
| aggregation = exclude_synthesis | aggregation_excludes_synthesis |
| kind | assertion_kind_not_allowed |

The absent default has a coupled relation/aggregation condition, so do not misrepresent it as independent
prohibitions on unresolved ownership or non-synthetic aggregation:

| Failed default predicate term | failed_dimensions entry | Closed reason |
|---|---|---|
| unresolved AND non_synthetic_or_unspecified | relation_aggregation | unresolved_non_synthetic |
| kind is not result | kind | non_result_kind |

Evaluate both default terms independently and retain both failures when both apply, in the order above.
The shorter coupled reason deliberately avoids calling an interpretation a “result.” PASS has empty
failed_dimensions/reasons. Malformed inputs raise a schema ValueError; an error is not a False policy
decision and never falls back to the default. No free-form explanation is semantic state.

### Required consistency validation

A future v7 candidate builder/validator must require both new fields together; validate policy schema,
source, identity/snapshot, closed dimensions/reasons, strict boolean passed and attachment status;
and verify admissible and the compatibility projection against the independent facts. Partial new
shapes, None eligibility, inconsistent passed/failure fields, or a forged combined admissible value
must fail loudly. Do not retrofit new keys, null placeholders or validation-driven coercions onto v6.

`new_candidate_supports` currently accepts exactly the historical key set, optionally plus attribution.
It needs an explicit additive evaluated-key-set branch. Keep the old key sets unchanged. Recommend a
separate `new_evaluated_candidate_support(base_candidate, *, guard_exclusions, support_policy_evaluation)`
data constructor, rather than changing the defaults of the historical candidate builder. Production v7
must supply the already-annotated v6 candidate, with i4-2b3.0 attribution retained.

## V7–V9. Pure policy APIs and replayable identities

Select a **new pure support_policy.py** for evaluation. The mapper is the sole production evaluation
caller. The engine retains schema/state authority. Avoid adding text classification or more policy
branching to the mapper, or growing engine.py into a policy evaluator.

Recommended public evaluation APIs, accepting only the semantic triple:

```text
default_support_policy(
    *, assertion_relation, aggregation, assertion_kind
) -> support_policy_evaluation

evaluate_authored_support_policy(
    policy, *, assertion_relation, aggregation, assertion_kind
) -> support_policy_evaluation
```

A narrow triple-only signature makes it impossible for these functions to inspect support_label,
authority_veto, is_caption, question text, role descriptions, mapping strategy, guards or attachment.
Validate the triple against the existing closed vocabularies before evaluation.

Use a one-way import from support_policy.py to sufficiency_engine for the existing vocabulary and a
public canonical_support_policy schema wrapper around the existing canonical builder. The engine must
not import the evaluator: its candidate/schema validator validates data and gate consistency without
re-evaluating evidence policy. Thus there is no cycle and no copied policy evaluator in two modules.
Normalization needs explicit type/error checks for malformed input, while valid authored dimensions
retain the current sorted/deduplicated builder representation.

### Absent means absent

Only `"support_policy" not in role_spec` selects the default:

```text
kind == result AND NOT (relation == unresolved AND aggregation == non_synthetic_or_unspecified)
```

Never call new_support_policy() to implement that default. Its deliberately permissive defaults admit
unresolved non-synthetic results. A RoleSpec containing support_policy=None, {}, a partial object,
unknown/extra dimensions, invalid vocabulary or empty allowed sets is malformed; fail schema validation.

The historical new_role_spec builder accepts None as an omission shorthand and omits the key. Preserve
that compatibility behavior; it is not an authored policy object. Once a **stored RoleSpec contains the
key**, a null value is an error. Document this boundary so maintainers do not use .get()/truthiness to
choose default behavior.

### Explicit means complete replacement

The authored object has exactly allowed_assertion_relations, aggregation_requirement and
allowed_assertion_kinds. Relation membership AND aggregation condition AND kind membership are the
entire policy rule. An explicit policy does not layer over the empirical default and does not override
guards or attachment.

Aggregation semantics are exact:

- any -> no aggregation restriction;
- require_synthesis -> aggregation == literature_synthesis;
- exclude_synthesis -> aggregation == non_synthetic_or_unspecified.

No special question parsing. “What did THIS study find?” is authored as current_document + result, with
any aggregation unless synthesis is separately excluded. A definitional role authors description/
interpretation kinds and its chosen relations. This mechanism can later serve Hierarchical and Simple
Ask; v7 does not claim the achieved-outcome collector can extract every definition or activate Simple Ask.

### Identities and snapshots

Absent policy_source is absent_default; policy_identity is **empirical-default-v1**. Retain this
normalized declarative snapshot (it describes a fixed function, not an arbitrary expression interpreter):

```json
{
  "kind": "empirical_default",
  "required_assertion_kind": "result",
  "excluded_relation_aggregation": {
    "assertion_relation": "unresolved",
    "aggregation": "non_synthetic_or_unspecified"
  }
}
```

Authored policy_source is authored. Snapshot exactly the three normalized dimensions, without RoleSpec
prose. Identity is:

```text
authored-support-policy-v1:sha256:<lowercase SHA-256 hex>
```

Hash UTF-8 JSON of that normalized snapshot using sorted object keys, separators (",", ":"), and
ensure_ascii=False. Allowed sets are sorted/deduplicated before hashing. Ordering or duplicates in authored
input do not change identity. A changed semantic dimension does. The v1 prefix fixes this canonicalization
and evaluator contract; later semantic changes require an appropriate new identity and sufficiency boundary.
Default identities never pretend to be the hash of new_support_policy().

## V10–V11. Engine aggregation and safe representative projection

Recommend a pure engine function `aggregate_support_role(candidate_supports)`, used only by the
explicit v7 achieved-outcome path and rejecting unevaluated/inconsistent records.

```text
FILLED:     any(not attachment_ambiguous AND admissible is True)
AMBIGUOUS:  no FILLED candidate AND any(attachment_ambiguous AND admissible is True)
MISSING:    otherwise
```

All candidates are evaluated before this function runs. It must not read singular reason strings,
support labels, a representative, or evidence provenance rankings. The mapper calls this engine
authority and then constructs the RoleBinding. Existing instance/requirement completion logic consumes
the resulting binding state as it already does.

The full single-candidate truth table is:

| Attachment | Guard | Policy | admissible | Role |
|---|---|---|---|---|
| resolved | pass | pass | True | filled |
| resolved | fail | pass | False | missing |
| resolved | pass | fail | False | missing |
| resolved | fail | fail | False | missing |
| ambiguous | pass | pass | True | ambiguous |
| ambiguous | fail | pass | False | missing |
| ambiguous | pass | fail | False | missing |
| ambiguous | fail | fail | False | missing |

The current v6 join only emits successfully resolved assertions. V7 does not start retaining failed or
attachment-ambiguous joins. The ambiguous rows above freeze the schema/set-aggregation contract using
synthetic evaluated records; they are not a new candidate-construction route.

Freeze these set cases, including their reversed order:

| Frozen case | Role state |
|---|---|
| resolved_direct_and_attributed | filled |
| excluded_direct_eligible_attributed | filled |
| eligible_resolved_and_ambiguous | filled |
| all_policy_excluded | missing |
| all_guard_excluded | missing |
| guard_failure_and_policy_failure | missing |
| eligible_ambiguous_only | ambiguous |
| guard_excluded_ambiguous | missing |
| policy_excluded_ambiguous | missing |
| multiple_eligible_syntheses | filled |
| dual_excluded_ambiguous | missing |
| empty | missing |
| excluded_resolved_eligible_ambiguous | ambiguous |
| resolved_eligible_excluded_ambiguous | filled |

After aggregation, select the **first resolved admissible candidate in preserved discovery order** for a
filled binding's legacy proposition_id/exact_text/provenance/guard. No direct-versus-attributed or synthesis
ranking. Never delete or reorder other candidates. If there is no resolved eligible candidate, leave those
legacy support fields unset/default; retain candidate_supports on the missing/ambiguous binding.
Return one binding carrying the set, not one binding per support; achieved-outcome candidates do not fork
instances. If the set is empty, preserve the existing [] -> missing/not_found projection.

**Existing downstream limitation:** the legacy surface is not display-only throughout the repository.
_support_set, _joint_grounded and witness/direction consumers still read binding-level support/text under
their established contracts. V7 must not let the representative decide **candidate admissibility or role
state**, but must preserve those existing downstream contracts. Do not silently union all candidate
proposition IDs into the binding or make excluded candidates into witnesses; that would independently
change relationship semantics. Set-wise joint-witness selection remains separate from this increment.
The real projection proves downstream parity; it does not prove arbitrary future multiple-support
relationship checks are independent of their historical compatibility projection.

## V12–V14. Real candidate and downstream projection

### Original ten, preserved

Each original support remains in its original order with exactly the same text, proposition identities,
spans, attribution object, kind, aggregation, veto/caption and attachment. All are non_synthetic_or_unspecified
result-kind supports; all have empty guard_exclusions, policy PASS, admissible=True and no candidate rejection
reason. Only their previously unevaluated gate fields and additive gate metadata change.

| Child | Requirement | Role | Instance | Supporting IDs / anchor | Assertion span | Relation |
|---|---|---|---|---|---|---|
| c1 | `c1#suff:neural-manifestation` | `neural_manifestation_evidence` | `null` | p2, p11 / p2 | [37,264) | current_document |
| c2 | `c2#suff:behavioral-manifestation` | `behavioral_manifestation_evidence` | `i::76d9e54baf790d84` | p47 / p47 | [76,251) | current_document |
| c3 | `c3#suff:attitude-manifestation` | `attitude_manifestation_evidence` | `null` | p7, p3, p14, p17, p26 / p7 | [14,251) | current_document |
| c4 | `c4#suff:specific-region` | `region_bears_on_bias_evidence` | `i::ac9b72f14d53f532` | p11, p2 / p11 | [37,264) | current_document |
| c4 | `c4#suff:specific-region` | `region_bears_on_bias_evidence` | `i::a3ab9566580a7fe4` | p40 / p40 | [147,273) | attributed_external |
| c8 | `c8#suff:trait-construct` | `relationship_to_bias_manifestation` | `U23::24d132203292cebb` | p41 / p41 | [43,200) | current_document |
| c8 | `c8#suff:trait-construct` | `relationship_to_bias_manifestation` | `U23::8d7156b76bf6a6f7` | p41 / p41 | [43,200) | current_document |
| c8 | `c8#suff:trait-construct` | `relationship_to_bias_manifestation` | `U23::50b0d4004f2f502f` | p41 / p41 | [208,372) | current_document |
| c8 | `c8#suff:trait-construct` | `relationship_to_bias_manifestation` | `U23::f6027eb43b85593c` | p41 / p41 | [208,372) | current_document |
| c8 | `c8#suff:trait-construct` | `relationship_to_bias_manifestation` | `U23::910466e6604581fa` | p41 / p41 | [208,372) | current_document |

### Five newly retained supports

All five use this **exact same local assertion text**, reproduced once and referenced by every row below:

> We suggest that dehumanization is underpinned by a suite of negative attitudes (IAT and EBQ), social cognitive biases (just-world beliefs), emotional dispositions (affective empathy), and undesirable behaviors (less generosity in the DG)—all factors associated with the functioning of the left amygdala

Every row's assertion span is [0,302), predicate span [250,260), content span [250,303).
The sealed quote SHA-256 is
`752351aca817663468ef574847360502d02443b20572e1a6d5148a0ce028906a`.
Offsets retain the original quote coordinate system; the support text is not widened.

| Child / requirement | Role | Exact instance key | Target role value | Supporting IDs / anchor | Assertion span |
|---|---|---|---|---|---|
| c3 / `c3#suff:attitude-manifestation` | `attitude_manifestation_evidence` | `null` | target-free role | p9, p20 / p9 | [0,302) |
| c8 / `c8#suff:trait-construct` | `relationship_to_bias_manifestation` | `U6::b2958c5ad5164563` | negative attitudes (IAT and EBQ) | p20, p9 / p20 | [0,302) |
| c8 / `c8#suff:trait-construct` | `relationship_to_bias_manifestation` | `U6::ce8933c59b53a00f` | social cognitive biases (just-world beliefs) | p20, p9 / p20 | [0,302) |
| c8 / `c8#suff:trait-construct` | `relationship_to_bias_manifestation` | `U6::da37435ef9b489b6` | emotional dispositions (affective empathy) | p20, p9 / p20 | [0,302) |
| c8 / `c8#suff:trait-construct` | `relationship_to_bias_manifestation` | `U6::d41542e10edf3ea7` | undesirable behaviors (less generosity in the DG) | p20, p9 / p20 | [0,302) |

Each of these five was actually processed by the current v6 annotation code with **i4-2b3.0**, not assigned
an old audit label. The shared observed classification is:

| Field | Observed value |
|---|---|
| assertion_relation | current_document |
| aggregation | non_synthetic_or_unspecified |
| assertion_kind | interpretation |
| support_label | interpretive, display only |
| source_resolution | parsed |
| ordered classifier rules | predicate.suggest; subject.owner; kind.interpretation_verb |
| ownership proofs | [] |
| context_status / context_failure | not_needed / None |
| authority_veto / is_caption / attachment_ambiguous | None / False / False |
| guard_exclusions | ["hedged"] |
| policy source / identity | absent_default / empirical-default-v1 |
| policy passed / failed_dimensions / reasons | False / ["kind"] / ["non_result_kind"] |
| final admissible / compatibility reason | False / guard_and_support_policy_excluded |

Explicit legacy and corrected classifications agree for all five. No R1/R2/R3 correction changes their
ownership. The candidate source is explicitly “We,” but the assertion remains an interpretation.
The c3 support follows its original eligible p7 support in discovery order; c3 stays filled and keeps
its original representative. The four c8 instances keep their already-filled trait bindings and remain
incomplete/missing for the relationship role.

### Load-bearing negative controls

c10 has the same three physical unit groups:

| Supporting IDs | Historical hedged flag | Raw recognized hits after retaining the unit | Assertion joins |
|---|---|---:|---|
| p21,p22 | True | 0 | none |
| p29,p53 | True | 2 | both no_governing_assertion |
| p54 | True | 0 | none |

Consequently c10 emits **zero** candidate supports. c12 also emits zero candidates after actual existing
grounding/relevance. Neither receives an invented “guard-excluded candidate.” Their unit/grounding
diagnostics can explain why no candidate exists; candidate_supports cannot.

### Exact observed changes

| Measure | Accepted v6 | In-memory gate projection |
|---|---:|---:|
| Supports | 10 | 15 |
| Role bindings with at least one support | 10 | 14 |
| Guard-excluded candidates | unevaluated/absent | 5 |
| Policy PASS / FAIL | unevaluated | 10 / 5 |
| Dual guard+policy exclusions | unevaluated | 5 |
| Evidence-role states | 10 filled, 16 missing | 10 filled, 16 missing; 0 ambiguous |
| Changed evidence-role states | — | 0 of 26 |
| Changed requirement states | — | 0 of 13 |
| Recovery records | 48 | 48, exactly equal |
| ParentClaims | 17 | 17, exactly equal |
| AnswerPlan nodes | 9 | 9, same statuses and contents |
| Rendered Layer 1 | accepted output | exactly equal |
| Downstream invariant results | 33 passing | exactly equal, all 33 passing |
| Real literature_synthesis supports | 0 | 0 |

The full non-diagnostic result compares equal after removing candidate_supports from both maps, except
these four role-binding reason changes:

```text
c8 / c8#suff:trait-construct / relationship_to_bias_manifestation
U6::b2958c5ad5164563: not_found -> candidate_supports_excluded
U6::ce8933c59b53a00f: not_found -> candidate_supports_excluded
U6::da37435ef9b489b6: not_found -> candidate_supports_excluded
U6::d41542e10edf3ea7: not_found -> candidate_supports_excluded
```

Instance keys, dependency bindings, requirements, c5/c6 inherited context, c9 pairing opportunities,
witness results, relation outcomes and direction/effectiveness data are unchanged. c8 remains **open_list**,
partially filled; it is not converted into exists/cardinality semantics.

The original ten attribution objects are byte-for-byte data-equal. New candidate fields account for the
eligibility/provenance changes; the five new records are the only additional supports. The four missing
bindings keep legacy proposition_id/exact_text unset and default provenance/guard surfaces.

The audit did **not** invent a supported v7 selector or stamp a production replay as v7. Its process-local
projection runs the real downstream machinery under the accepted v6 identity, with temporary achieved-outcome
collection/gate/projection overrides only. Thus the unchanged AnswerPlan and its hash are actually compared
under the same identity. A future genuine v7 artifact additionally changes semantic-version fields and
hashes that include version/candidate metadata, including the plan hash for its versioned inputs.
Do not freeze this audit projection as a v7 baseline.

### Diagnostics and their meaning

These are observed existing-collector counters across 26 role-binding attempts, not unique source-unit counts:

| Counter, summed across 26 role attempts | Accepted v6 | Audit with guard prefilter bypassed |
|---|---:|---:|
| eligible_units | 75 | 75 |
| guard_excluded_units | 21 | 0 |
| raw_result_predicate_hits | 42 | 54 |
| successful_assertion_joins | 36 | 42 |
| join_failures | 6 | 12 |
| raw_hits_deduplicated | 8 | 8 |
| locally_grounded_assertions | 28 | 34 |
| target_scoped_assertions | 14 | 18 |
| target_matches | 9 | 13 |
| target_unmatched | 5 | 5 |
| candidate_supports_emitted | 10 | 15 |
| missing_no_grounded_relevant_support | 16 | 12 |

The audit's zero guard_excluded_units is a consequence of temporarily bypassing the early filter; it does
**not** mean no guards triggered. Future v7 diagnostics should explicitly report guard_triggered_units=21,
guard_prefiltered_units=0, guard_excluded_candidates=5, policy_excluded_candidates=5 and
admissible_candidates=10, alongside the observed localization/relevance counts. Keep v6 diagnostic keys
and values exact. In v7, 12 roles have no grounded relevant candidate, whereas 16 roles remain missing:
four missing roles now have excluded evidence. Never equate candidate absence with role missingness.

Unchanged node statuses/rendering are **not evidence that AnswerPlan understands these candidates**.
It currently does not explain the new gate records. I4-4 owns that future rendering work.

## V15–V16. Preregistered synthetic and explicit-policy matrices

These tables are frozen design expectations, checked by an independent in-memory truth-table oracle.
They are not a passing implementation test suite for a nonexistent v7 evaluator. Future I4-2b5 must
materialize them as executable tests without editing expectations to fit implementation.

Mandatory absent-default controls:

| ID | Relation | Aggregation | Kind | Expected |
|---|---|---|---|---|
| D01 | unresolved | literature_synthesis | result | PASS |
| D02 | attributed_external | literature_synthesis | result | PASS |
| D03 | current_document | literature_synthesis | result | PASS |
| D04 | unresolved | non_synthetic_or_unspecified | result | FAIL: unresolved_non_synthetic |
| D05 | current_document | non_synthetic_or_unspecified | interpretation | FAIL: non_result_kind |
| D06 | unresolved | non_synthetic_or_unspecified | interpretation | FAIL: both default terms, neither hidden |

Preserve the neutral synthesis examples “Across studies, X has been associated with Y,” “A review found X,”
and “We found a meta-analytic effect” with their accepted supplied triples. These are policy-input tests;
v7 does not reclassify text inside a policy function. The real corpus has no synthesis candidate.

The six complete authored policies are:

| Authored policy | Relations | Aggregation requirement | Kinds |
|---|---|---|---|
| A_current_document | current_document | any | result |
| B_attributed_allowed | attributed_external, current_document | any | result |
| C_synthesis_required | attributed_external, current_document, unresolved | require_synthesis | result |
| D_synthesis_excluded | attributed_external, current_document, unresolved | exclude_synthesis | result |
| E_definitional | attributed_external, current_document, unresolved | any | interpretation, method_or_description |
| F_unresolved_result | unresolved | any | result |

Their cross-product matrix is:

| Evidence case | Absent default | A: current | B: attributed allowed | C: synthesis required | D: synthesis excluded | E: definition | F: unresolved allowed |
|---|---|---|---|---|---|---|---|
| primary_direct_result | PASS | PASS | PASS | FAIL: aggregation | PASS | FAIL: kind | FAIL: relation |
| attributed_prior_result | PASS | FAIL: relation | PASS | FAIL: aggregation | PASS | FAIL: kind | FAIL: relation |
| unresolved_bare_result | FAIL | FAIL: relation | FAIL: relation | FAIL: aggregation | PASS | FAIL: kind | PASS |
| unresolved_synthesis | PASS | FAIL: relation | FAIL: relation | PASS | FAIL: aggregation | FAIL: kind | PASS |
| attributed_synthesis | PASS | FAIL: relation | PASS | PASS | FAIL: aggregation | FAIL: kind | FAIL: relation |
| current_synthesis | PASS | PASS | PASS | PASS | FAIL: aggregation | FAIL: kind | FAIL: relation |
| description | FAIL | FAIL: kind | FAIL: kind | FAIL: aggregation+kind | FAIL: kind | PASS | FAIL: relation+kind |
| interpretation | FAIL | FAIL: kind | FAIL: kind | FAIL: aggregation+kind | FAIL: kind | PASS | FAIL: relation+kind |
| result_with_veto | PASS | PASS | PASS | FAIL: aggregation | PASS | FAIL: kind | FAIL: relation |
| caption_result | PASS | PASS | PASS | FAIL: aggregation | PASS | FAIL: kind | FAIL: relation |

For this matrix alone, assume no triggered guard and resolved attachment: PASS implies filled and FAIL
implies missing for a sole candidate. Applying attachment ambiguity or guard exclusions uses V10's
orthogonal truth table, not different policy semantics.

A and C demonstrate that current-document ownership and synthesis are independent authored restrictions.
D and F deliberately accept unresolved bare results that the absent default rejects. E accepts description
and interpretation without weakening the empirical default. Authored policy is complete replacement;
it is not an override of selected dimensions.

Freeze all 30 triples (three relations x two aggregations x five kinds) for absent and each authored
policy, including unknown and aim_or_hypothesis kinds. The absent rule passes five triples. Also freeze
multi-dimension failures: current-only + require_synthesis + result applied to unresolved/non-synthetic/
interpretation fails relation, aggregation and kind together, in that order.

Authored canonical policy identity examples:

- A_current_document: `authored-support-policy-v1:sha256:977744c615123c960f30d635250d6fdfbcf01131a689f3519023f66222e64afc`
- B_attributed_allowed: `authored-support-policy-v1:sha256:f15c087db180eeb5a77b96c5cb8894084ab2b5597419c0d86f51282b605a1e6a`
- C_synthesis_required: `authored-support-policy-v1:sha256:334763497256432de3b153168113d78885ce6f635369934a19fe6a572ce86f95`
- D_synthesis_excluded: `authored-support-policy-v1:sha256:89c6fb0b58eaf19ceddee3fb200674acfd7eb5d769b92d79fbf3457dde1876c0`
- E_definitional: `authored-support-policy-v1:sha256:ada46b62425fffbcd72b6a137295276c6b430695a0e383ad38e2b77108beb10d`
- F_unresolved_result: `authored-support-policy-v1:sha256:41a1759826f14e72e00999ab36c2d274acfc7edd218a4e537ec595b278b46cc1`

### Explicit negative gates and schema cases

Authority veto and caption metadata are not policy gates. Both allowed veto values and None, and both
caption flags, must leave a triple's policy result unchanged. A current-document result with
absence_of_evidence metadata passes a result-compatible policy; so does a caption result with the same
triple. This does not disable a separately triggered authored passage guard. No positive/null claim goal
is inferred from strategy, role name, description or question.

Likewise mutate support_label arbitrarily: it must never change policy or role aggregation.

Future tests must cover present-null/empty/partial/extra-key policies, wrong container/value types, empty
relation/kind sets, unknown enum values and malformed aggregation. They must raise schema errors even
when guards fail or candidate scope is empty. Include:

- omitted RoleSpec key selects empirical-default-v1;
- an explicit new_support_policy() object admits unresolved bare result;
- the default function never calls the builder;
- equal normalized policies produce equal IDs; changed dimensions change IDs;
- both new candidate fields must occur together and remain absent on explicit v6;
- True plus attachment ambiguity is valid with candidate reason None;
- a false/ambiguous candidate never makes an ambiguous role;
- multiple authored guards preserve identities/order;
- a hedge in a separate clause still excludes a grounded result under the historical passage guard;
- a guard-triggered unit with failed grounding produces no candidate;
- first excluded candidate followed by eligible attributed candidate projects the eligible one;
- all-excluded/ambiguous bindings retain candidates but no satisfied legacy evidence surface;
- malformed gate records/None eligibility are refused before aggregation.

The in-memory oracle checked 30 default triples, 180 authored triples, eight single-candidate gate/attachment
rows, 14 candidate-set cases in both orders (28 order checks), and 3,780 policy comparisons across
veto/caption/display-label permutations. These counts describe audit checks, not production pytest results.

## V17. Reference/schema migration and shared implementation seam

The current reference_future_role_state is incompatible with corrected B9: it treats any admissible
candidate as filled without checking attachment, then uses a scalar attachment rejection reason to
create ambiguity. Its old test fixtures use admissible=False + attachment_ambiguous=True as the sole
ambiguous record. That convention must be superseded.

In I4-2b5, update the **reference-only** helper to delegate to the new engine aggregation contract and
rewrite its reference assertions around evaluated records and the eight-way table above. Keep the old
schema examples as historical examples where appropriate; they are not valid v7 gate records merely
because they have the same boolean field names. Production calls the new aggregate_support_role
function, never a helper named reference_future_role_state. Keep requested-terms reference disambiguation
unwired; do not introduce a new candidate-selection stage.

Guard retention must not create a second localization/relevance implementation. Recommend:

1. Extract the current achieved-outcome collector into one private shared core, with a closed internal
   guard mode selected only by explicit semantic dispatch: historical prefilter versus v7 retain.
   Return internal candidate+unit/guard association until projection; no extra historical serialized fields.
2. Preserve the v5 wrapper's exact candidate/projection behavior. V6 remains that prefilter collector
   plus its unchanged attribution annotation.
3. Extract v6 annotation into a shared private annotator without changing i4-2b3.0 or its outputs.
4. The v7 wrapper runs retained collection -> same annotator -> guard/policy metadata -> engine aggregation
   -> eligible-only legacy projection. No instance fork per support.
5. Preserve all old error/coordinate handling for unguarded units. Newly retained malformed-coordinate
   units still fail the existing loud coordinate check; v7 must not hide that check merely to retain evidence.

Do not implement this by clearing unit.flags, editing disqualifying_guards, setting a global bypass,
calling the old “any candidate means filled” projection as the semantic decision, or copying the whole
grounding algorithm into a v7-specific fork. The temporary guard bypass used in this isolated audit
is an experimental oracle mechanism, not the recommended production architecture.

## V18. Explicit version-routing and historical preservation

Recommend sufficiency-semantics-v7 as current when the later implementation ships, with v6 explicitly
historical/readable. Classifier remains i4-2b3.0. No floating comparison, “not old version,” or default-to-latest
classifier behavior.

Every currently explicit v6 routing site was audited:

| Current site at starting HEAD | Required future v7 action |
|---|---|
| engine.py:133–141, semantic identity sets | Add named V7; move V6 to historical; retain strict supported-version validation |
| engine.py:1065, category goal gate | Add explicit V7 membership; same category behavior |
| engine.py:1168–1172, category recomputation selection | Add explicit V7 membership; same category behavior |
| mapping.py:670, non-cardinality category refusal | Add V7; preserve refusal |
| mapping.py:678, achieved-outcome V6 dispatch | Keep V6 prefilter wrapper exact; add separate V7 retained/evaluated wrapper |
| mapping.py:1012, category mapper | Add V7; do not activate achieved-outcome policy for category roles |
| mapping.py:1454–1459, target-aware direction dispatch | Add V7; unchanged direction algorithm |
| diagnostic.py:133, ownership context transport | Explicit (V6,V7) selection; older versions still consume no context |
| e2e.py:528 and :704, initial/final context sidecars | Explicit (V6,V7); unchanged ownership-context-v1 identity |
| e2e.py:839–840, final recovery obligation inventory | Add V7; unchanged raw-final-target rule |
| recovery_targets.py:248–252 and :557 | Add V7 to category/terminal-search rules; no query/stop-search redesign |
| direction_target.py:54, semantics table | Add named V7 entry with the same target-aware rule |
| relation_witness.py:112, containment table | Add named V7 entry with the same containment function |

All paths in this table are relative to experiments/ask_cli_revised/. Names omit the common
sufficiency_ prefix on engine/mapping/diagnostic/recovery_targets for readability. Effectiveness and identity/readability code delegate through the existing explicit
version machinery; they have no separate v6-only selector to invent. Unknown future versions still fail.

Update current-version pin tests to V7 and add explicit V6 historical tests without rewriting old classifier
expectations. Preserve the 119-node legacy parser freeze and all old classifier batteries. PLAN_VERSION
remains answer-plan-step2-v4. same_local_assertion remains unregistered; neither policy nor guard
metadata requires it. Relationship-contract changes remain deferred.

The three historical combined replays were rerun during this audit and match exactly:

| Replay | Required and observed SHA-256 |
|---|---|
| v4 | `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a` |
| v5 | `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77` |
| v6 | `dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be` |

I4-2b5 must preserve all three byte hashes, including candidates, diagnostics, witnesses, recovery,
direction/effectiveness, claims, plan/rendering and invariants. Explicit v6 must keep ten candidates,
old shapes and None policy fields on the accepted replay inputs; an authored policy remains unevaluated
on that historical route. V6 keeps its existing explicit ownership-context behavior. V7 alone exposes
15 here. Freeze a real v7 replay only after that implementation's gates pass; no v7 hash is frozen now.

## V19. Purity boundaries, model isolation, and test gates

The narrow production evaluation import is support_policy.py -> engine schema/vocabulary, with
sufficiency_mapping.py as the sole policy-evaluation caller. Engine is the role-state authority; diagnostic
and E2E remain transport/orchestration. No policy imports in the classifier, ownership context, retrieval,
qwen/model scope, authoring text parsers, recovery query generation, ParentClaims or AnswerPlan.

Retain the classifier's sole mapper consumer and the exact ownership-context allowlist. Add exact-file
allowlists and negative unauthorized-consumer fixtures for the new evaluator. Static tests must reject
I/O/network/database/model/classifier imports or calls in policy evaluation, prohibited candidate-field
reads, role/question parsing, domain IDs/vocabulary and whole-directory exemptions. The pure module may
use only canonical schema/vocabulary plus stdlib hashing/JSON; engine must not acquire an evaluator import.

### Audited equality surfaces

The audit compared all 15 declared model-nomination role surfaces and instrumented the actual reached
fork scopes: **31 nomination attempts across 29 unique child/requirement/role/request-context keys**.
Candidate rows, category descriptions, generated prompt strings and fingerprints are exactly equal.
No model was called; existing replay nominations stayed fixed. The shared full trace SHA-256, canonical
compact UTF-8 JSON, is:

`2ef9641e74a92877e4734f70883092689e082151c38c58e7f69ae0a34e4368c2`.

All 48 recovery records are exactly equal, including their query/scope content. Retrieval/search/ranking
code and nominal upstream guard filtering are untouched. Original candidate grounding and target-relevance
texts compare exactly; extra successfully grounded guarded assertions necessarily enter relevance processing
in v7, but their text must be the same local text the shared grounding routine produces. Do not mistake
the intended extra candidate work for permission to rewrite target-relevance text.

For other corpora, a legitimate policy-induced role-state change can change which recovery targets exist.
The invariant is unchanged recovery algorithms and query text for the same target, with no new policy/
guard metadata injected into prompts or queries. The real preserved map is the stronger exact-inventory
equality control. A universal promise that no input can gain a recovery target would contradict policy gating.

### Future implementation gates

Require the frozen matrices/schema errors, guard-scope controls, aggregate and representative cases,
all 15 real candidates, c10/c12 negative controls, historical hashes, parser freeze, source/attribution equality,
nomination isolation, 33 invariants and exact real downstream comparison. Run the existing I4-1 through
I4-2b3 families and the full offline sufficiency/recovery/relation/direction/effectiveness/parent/AnswerPlan/
hierarchy suites. Independently reconfirm any known environment failures then; this planning audit does
not grant a future blanket failure or hook bypass.

No full production test-suite rerun was needed for the two Markdown-only deliverables. The read-only
replays, scoped actual-classifier checks, matrix oracles and document validation are this audit's evidence.

## I4-4 handoff

Preserve role/instance/requirement placement, exact local assertion, plural proposition provenance in
discovery order, span anchor and assertion/predicate/content spans; attribution triple, ruleset and proofs;
attachment_ambiguous; actual guard_exclusions; policy source/identity/normalized snapshot, pass/fail,
all failed dimensions/reasons; final admissible; and sufficiency semantics identity.

Role placement supplies the outer IDs; they need not be redundantly copied into every candidate.
Attribution proof references remain separate from scientific assertion text. This is enough to distinguish
current-source findings, reported prior evidence, synthesis, and relevant evidence excluded by this role's
rule. I4-4 must explicitly consume these facts later. No ParentClaims/AnswerPlan adapter or explanatory
rendering is implemented or proposed as part of the bounded v7 change.

## V20–V21. Readiness and exact next increment

**READY for a separately authorized bounded implementation**, with the contracts in this report frozen.
The real attribution defects are already repaired, all five additional supports were classified using
the actual accepted ruleset, and no empirical state/recovery/rendering surprise appeared.

Exact next increment:

**PHASE 34 / I4-2b5 — V7 support-policy evaluation + achieved-outcome guard-retention integration.**

Its only semantic changes are achieved-outcome retain-and-flag collection, default/authored policy
evaluation, additive independent gate records, and engine-owned set-based role aggregation followed by
safe representative projection. It must keep attribution/parser semantics, other strategy guards,
relationships/witness rules, direction/effectiveness, recovery algorithms and PLAN_VERSION unchanged.
The historical projection limitation documented in V11 is not an authorization to expand witness semantics.

This report is a design decision, not implementation authorization. No v7 constants, evaluator module,
production/test code, guard detector, authored guard list, reference helper, claim-goal semantics,
authority-veto gate, verifier registration, ParentClaims or AnswerPlan file was changed.

**STOP after I4-2b4. Do not begin I4-2b5, v7 implementation, I4-3 implementation, or I2-3.**
