# Phase 34 / I4-4B — Layer C value, category-coverage and validation contract closure

Date: 2026-10-10. **Planning/docs only. No implementation.**

Canonical branch: experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z.
Clean starting HEAD: **f38b85d8d412fff88aa911bd4b678a898f8d243e**.
At entry, the accepted I4-4A report and lineage were uncommitted at d4cb7ff1cb7898f95557fb09df6d3f00b47cd9d5.
The user explicitly authorized committing those two files. Commit f38b85d8 establishes the requested clean checkpoint; all commit hooks passed.
This increment adds only this report and its lineage entry. It does not commit or activate I4-4B.

**D4: OPTION B — authorized category-observation coverage.**
The explicit p36 observation is independently keyed to the exact authored category and is already
one of the observations considered by category satisfaction. It may supply explicit's scientific
coverage and display path without becoming its selected RoleBinding support. The explicit binding
remains p8. This decision follows the producer/engine contract, not desired output parity.

**D5: node 3 is preregistered as answered under the reporting-coverage rule below.**
A necessary qualification: implicit is a recorded **null_finding**, not established positive presence.
Node 3 reports both categories faithfully; its category facet must also retain
scientific_goal_state=incomplete and implicit goal_state=unestablished. Answered is a reporting
coverage status, never a claim that the map's positive-presence goal is satisfied or recovery ended.

**D30: READY for bounded I4-4C substrate implementation after this design is accepted.**
I4-4D activation remains separate; v8 stays supported_noncurrent, v7/plan-v4 remain current.
No upstream scientific semantic change is required. This closes the contracts; it is not a
passing implementation qualification or permission to start implementation in this turn.

## Evidence and verification

Read the complete category producer/classifier path, category-goal recomputation, its recovery
contract and tests, all category_observations references, selected-view construction, stored proof
validation and link context handling. Revisited claim construction, per-value rendering, facet/node
aggregation and the accepted I4-4A inventory. Source anchors below are repository-relative and
function names are authoritative if lines shift:

- overview_evidence.build_units: verified quotes become deterministic passage units, with sealed
  locators, proposition IDs and lexical flags. Overview eligibility is not a universal mapping gate.
- sufficiency_mapping.map_cardinality_requirement: single category role; exact v4-v8 dispatch to
  _map_category_requirement_v4; _category_observations:1210; _representative_observation:1243.
- category_polarity.classify_category_observation and _classify_occurrence: deterministic occurrence,
  sentence and clause classifier. Its top-level "unwired" description records its original I2-1
  status; production import and I2-2 wiring supersede that historical sentence.
- sufficiency_engine.is_category_requirement:171, category_goal_satisfied:180,
  recompute_instance:1180 onward: binding completeness AND positive category observation.
- PHASE33_I2_2_CATEGORY_SATISFACTION_RESULTS.md, especially observation structure, goal gate,
  category recovery, and the real implicit null result. This finding is not new classifier behavior.
- compatible_witness.build_support_views: eligible candidate/legacy views; validate_witness_bundle:538
  rebuilds views and is unsuitable as the future validation-only API.
- answer_plan.classify._evaluate_values, _candidates_containing, evaluate_sentence;
  answer_plan.plan._covered_categories, _facet_state:249, _build_node:352 and _disclosure_items.
- parent_synthesis_ledger._atomic_candidate/_build_atomic_claims and relationship accumulation;
  existing ParentClaims can report filled bindings even when the containing goal is incomplete.
- contract_directed.links.extract_designators and attachment_pieces; v8 stored shared_designator
  proof construction. No link discovery was invoked by this audit.

Targeted unchanged tests: test_i4_3c_replay.py and
test_sufficiency_v4_category_satisfaction.py with the existing i4_offline plugin: **32 passed**.
The replay tests block network access; model-role nominations are the preserved frozen inputs.
The independent scratch inventory reran all five remaps and checked these exact hashes:

| Version | Combined replay SHA-256 |
|---|---|
| v4 | `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a` |
| v5 | `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77` |
| v6 | `dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be` |
| v7 | `04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72` |
| v8 | `1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0` |

Preserved sealed inputs passed the replay harness's fingerprint checks. The inventory checks
input equality before/after, accounts for all 51 filled placements, 32 claim-member values and 17
claims, and finds zero unexpected unsupported mappings. All 33 existing real replay invariants
pass. No full suite, new production test suite, external search, live retrieval, model/NLI call
or live E2E was run. Loading the frozen replay/context inputs is offline artifact reading.

Ignored scratch: .local/i4-4b/audit.py, inventory.json, check_contract.py and contract-check.json.
The contract check confirms the exact nine-node table from stored target/proof states and
value-specific display results, explicitly checks p8 establishment/p36 coverage and the implicit
null, and asserts unchanged inputs. This is a design oracle, not a production plan-v5 test.
These artifacts contain the full exact references,
identity material and observed display checks used for the annexes. The report is self-contained:
table aliases resolve to full IDs/material below. Prospective states/matrices are design
expectations, not observations of an implemented plan-v5. An initial shell brace-expansion command
and a runpy module invocation were corrected; a large console dump hit Windows encoding and was
rerun with UTF-8. None changed production inputs or a frozen expectation.

## D1–D3. Category-observation authority and fields

There is exactly one current category-evidence role per mapped cardinality requirement.
The adapter derives scope from the **containing child, requirement, instance and sole role**.
The authored requested_category_terms list and exact instance key establish category identity.
The classifier does not discover a category: the producer supplies each authored term and its
competing terms. Its existing case-insensitive substring detector is an upstream limitation,
not a license for Layer C to match arbitrary text to a category.

Production sequence:

1. Receive verified proposition-backed units and the authored role.
2. For each requested term, inspect every unit that passes that role's disqualifying_guards.
3. Locate the literal term, classify that occurrence and record the observation in that term's instance.
4. Choose the first positive observation for the compatibility binding; otherwise first null,
   mentioned, unknown, in that order. It is never the satisfaction rule.
5. Recompute category goal from **any positive observation**, independently of representative choice.
   Null/mentioned/unknown bindings may be filled while their goal/instance remains incomplete.
6. V8 builds the selected legacy support view from that binding. Unselected category observations
   do not acquire views or witness authority.

| Stored field | Producer/input and exact authority |
|---|---|
| term | Exact authored term, separately recorded per category instance; validate equality to requested term and placement. |
| proposition_id | First proposition ID in that already deduplicated unit; points to sealed source. No claim that it is the only physical occurrence. |
| unit_id | Deterministic unit label in that replay, not a globally stable source ID or semantic value ID. |
| exact_text | Literal matched category surface, not the finding assertion. |
| source_passage | Whole unit passage supplied to the classifier; source-authentic evidence surface, not generated scientific prose. |
| observation_polarity | positive_finding, null_finding, mentioned_only, unknown. contrary_finding is reserved and never emitted by this classifier; reject as unsupported here. |
| rule / ambiguity | Deterministic classifier reason and uncertainty; ambiguity must not be erased by a positive-looking sentence. |
| classifier | observation-polarity/i2-1 identity; retain historical ruleset identity, do not silently rerun. |
| competing_terms | Other exact authored category terms supplied to contrast scoping. |
| classifier_audit | Occurrence count/matched surface; term/contrast clauses/connectives; finding/directional/measurement/null cues; competing terms in contrast; hedge; absence_statement; occurrence_results; result_complement. Optional keys depend on the rule. These explain classification, not extra support grants. |
| guard | Unit lexical flags at collection. Only authored disqualifying guards are gates; negated=true is not globally exclusionary. |

Not directly stored: observation ID, full placement, paper/chunk/span identity, source offsets,
assertion_relation/aggregation/kind, candidate-policy receipt, attachment-ambiguous flag or a selected-view link.
The enclosing map plus sealed ledger supply placement and source identity without semantic inference.
A detached reference can hash those immutable records. Do not invent missing attribution or an
evaluated-candidate policy receipt for this legacy category channel.

These observations **participate in sufficiency**; they are not diagnostic-only.
Before this proposed integration, ParentClaims/AnswerPlan do not consume them directly.
The existing renderer borrows p36 through a claim-wide PID union, so identical printed text is
not proof that existing coverage was authorized correctly.

Authorized positive category coverage requires all of:

- Supported producer/profile; exact enclosing requirement and sole category-role scope; term equals
  the authored category key and instance key. Same spelling in another scope is not a match.
- Stored positive_finding with ambiguity=null, and upstream category presence already established.
- Valid sealed proposition and source passage equality, exact physical locator, and replay-bound map provenance.
- Existing role-specific guard facts consistent with collection; no contradictory same-path
  exclusion/attachment status. Checking stored receipts is validation, not calling policy/classifier.
- The selected binding stays fixed. Only the observation reference is added to the value receipt.
- Display/citation separately pass locator and presentation checks on the authorized passage.

There is no candidate support_policy on this category path today; absence of a candidate evaluation
is not rejection and must not trigger the achieved-outcome default. A candidate excluded in another
role is not a global veto on this observation. Conversely a contradictory exclusion on the *same
authorized path/scope* is an integrity failure, not permission to bypass it.

Null_finding has a narrower permission: report the already bound category's **null observation**
with its polarity intact, through its selected legacy path. It cannot authorize positive-presence
coverage, turn a missing category into established presence, or satisfy recovery. Mentioned_only
and unknown do not authorize a scientific finding display. No future null-finding claim-goal
authoring is added by this reporting distinction.

## D2, D4–D5. Exact p8/p36 trace

Requirement: c3#suff:implicit-explicit-coverage; role: category_evidence;
strategy: explicit_category_terms; terms [implicit, explicit]; guards []; quantifier all_requested_categories.
The requirement remains partially_filled/category_missing. All observations are produced **before**
representative selection. Both bindings have immediate source deterministic_mapping/own.

| Value/instance | Selected primary/support set | Selected v8 view | Binding / instance / goal |
|---|---|---|---|
| implicit | p36 / [p36] | support-view-v1:sha256:a01b445f6091ab1e379587d05b331a8e9d8c3bf945a4a2391109756a2f488913 | filled / partially_filled, complete=false / positive presence unestablished |
| explicit | p8 / [p8] | support-view-v1:sha256:b7b8cfa3588ca88c87e30c5f4031a9d764a70147a99f0bdc423cf4296fdfb04b | filled / filled, complete=true / established |

Support refs respectively:
legacy-support-ref-v1:sha256:ee9d60beed9db5e5d2cbd7be84850787804309f825ab90fdb2a27fdc2ab9f7d6
and legacy-support-ref-v1:sha256:7579862389a712fb866915ff929bb4835442f9d02832fcdc575f356ca0544e27.
No p36 view is inserted into explicit's bundle.

### implicit / p36 / U8

- State/rule: null_finding / local_null_same_clause; ambiguity=None.
- Category term/exact_text: implicit / implicit; competing_terms=['explicit'].
- Locator: paper 67, chunk 35068, span e7, page 10; whole passage [0,135); term [87,95). Python Unicode code-point offsets, end exclusive.
- Term-clause offset: [81, 135]. This is an observation audit locator, not a new achieved-outcome assertion span.
- Stored classifier audit/guard:

```json
{
  "classifier": "observation-polarity/i2-1",
  "classifier_audit": {
    "absence_statement": false,
    "competing_terms_in_contrast": [],
    "contrast_clause": null,
    "contrast_connective": [],
    "directional_cues": [],
    "finding_cues": [],
    "hedge": false,
    "matched_surface": "implicit",
    "measurement_cues": [],
    "null_cues": {
      "complement": [
        "significant"
      ],
      "negation": [
        "not"
      ],
      "self_null": []
    },
    "occurrence_results": [],
    "result_complement": null,
    "term_clause": "their implicit biases were slight and not significant.",
    "term_occurrences": 1
  },
  "guard": {
    "absence_statement": false,
    "causal_cues": [],
    "correlational": false,
    "fragment": false,
    "hedged": false,
    "negated": true,
    "starts_mid_sentence": false,
    "study_description": false
  }
}
```

Exact source passage:

> Participants expressed explicit biases against people with facial anomalies, but their implicit biases were slight and not significant.

### explicit / p8 / U1

- State/rule: positive_finding / local_finding_predicate; ambiguity=None.
- Category term/exact_text: explicit / explicit; competing_terms=['implicit'].
- Locator: paper 67, chunk 35111, span e1, page 13; whole passage [0,292); term [136,144). Python Unicode code-point offsets, end exclusive.
- Term-clause offset: [127, 188]. This is an observation audit locator, not a new achieved-outcome assertion span.
- Stored classifier audit/guard:

```json
{
  "classifier": "observation-polarity/i2-1",
  "classifier_audit": {
    "absence_statement": false,
    "competing_terms_in_contrast": [],
    "contrast_clause": null,
    "contrast_connective": [],
    "directional_cues": [
      "detected"
    ],
    "finding_cues": [
      "detected"
    ],
    "hedge": false,
    "matched_surface": "explicit",
    "measurement_cues": [],
    "null_cues": {
      "complement": [],
      "negation": [],
      "self_null": []
    },
    "occurrence_results": [],
    "result_complement": null,
    "term_clause": "detected explicit biases against people with facial anomalies",
    "term_occurrences": 1
  },
  "guard": {
    "absence_statement": false,
    "causal_cues": [],
    "correlational": false,
    "fragment": false,
    "hedged": false,
    "negated": false,
    "starts_mid_sentence": false,
    "study_description": false
  }
}
```

Exact source passage:

> This research confirmed earlier reports that people with anomalous faces are imbued with negative personality characteristics, detected explicit biases against people with facial anomalies, and described a behavioral manifestation of the “anomalous-is- bad” stereotype affecting prosociality.

### explicit / p7 / U3

- State/rule: unknown / repeated_term_occurrence; ambiguity=repeated_term_occurrence.
- Category term/exact_text: explicit / explicit; competing_terms=['implicit'].
- Locator: paper 67, chunk 35068, span e4, page 10; whole passage [0,252); term [73,81). Python Unicode code-point offsets, end exclusive.
- Term-clause offset: not uniquely supplied; unknown occurrence record. This is an observation audit locator, not a new achieved-outcome assertion span.
- Stored classifier audit/guard:

```json
{
  "classifier": "observation-polarity/i2-1",
  "classifier_audit": {
    "matched_surface": null,
    "occurrence_results": [
      {
        "observation_polarity": "mentioned_only",
        "rule": "no_finding_predicate",
        "sentence": "Nevertheless, we found evidence for the “anomalous-is-bad” stereotype in explicit negative attitudes about people with facial anoma- lies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit Bias Questionnaire).",
        "term_clause": "we found evidence for the “anomalous-is-bad” stereotype in explicit negative attitudes about people with facial anoma- lies both as individuals (i.e."
      },
      {
        "observation_polarity": "mentioned_only",
        "rule": "no_finding_predicate",
        "sentence": "Nevertheless, we found evidence for the “anomalous-is-bad” stereotype in explicit negative attitudes about people with facial anoma- lies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit Bias Questionnaire).",
        "term_clause": "scores on the Explicit Bias Questionnaire)."
      }
    ],
    "result_complement": null,
    "term_occurrences": 2
  },
  "guard": {
    "absence_statement": false,
    "causal_cues": [],
    "correlational": false,
    "fragment": false,
    "hedged": false,
    "negated": false,
    "starts_mid_sentence": false,
    "study_description": false
  }
}
```

Exact source passage:

> Nevertheless, we found evidence for the “anomalous-is-bad” stereotype in explicit negative attitudes about people with facial anoma- lies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit Bias Questionnaire).

### explicit / p36 / U8

- State/rule: positive_finding / local_finding_predicate; ambiguity=None.
- Category term/exact_text: explicit / explicit; competing_terms=['implicit'].
- Locator: paper 67, chunk 35068, span e7, page 10; whole passage [0,135); term [23,31). Python Unicode code-point offsets, end exclusive.
- Term-clause offset: [0, 75]. This is an observation audit locator, not a new achieved-outcome assertion span.
- Stored classifier audit/guard:

```json
{
  "classifier": "observation-polarity/i2-1",
  "classifier_audit": {
    "absence_statement": false,
    "competing_terms_in_contrast": [
      "implicit"
    ],
    "contrast_clause": null,
    "contrast_connective": [],
    "directional_cues": [
      "expressed"
    ],
    "finding_cues": [
      "expressed"
    ],
    "hedge": false,
    "matched_surface": "explicit",
    "measurement_cues": [],
    "null_cues": {
      "complement": [],
      "negation": [],
      "self_null": []
    },
    "occurrence_results": [],
    "result_complement": null,
    "term_clause": "Participants expressed explicit biases against people with facial anomalies",
    "term_occurrences": 1
  },
  "guard": {
    "absence_statement": false,
    "causal_cues": [],
    "correlational": false,
    "fragment": false,
    "hedged": false,
    "negated": true,
    "starts_mid_sentence": false,
    "study_description": false
  }
}
```

Exact source passage:

> Participants expressed explicit biases against people with facial anomalies, but their implicit biases were slight and not significant.

### explicit / p52 / U33

- State/rule: positive_finding / local_finding_predicate; ambiguity=None.
- Category term/exact_text: explicit / explicit; competing_terms=['implicit'].
- Locator: paper 68, chunk 14547, span e6, page 12; whole passage [0,93); term [31,39). Python Unicode code-point offsets, end exclusive.
- Term-clause offset: [0, 93]. This is an observation audit locator, not a new achieved-outcome assertion span.
- Stored classifier audit/guard:

```json
{
  "classifier": "observation-polarity/i2-1",
  "classifier_audit": {
    "absence_statement": false,
    "competing_terms_in_contrast": [],
    "contrast_clause": null,
    "contrast_connective": [],
    "directional_cues": [
      "influence"
    ],
    "finding_cues": [
      "influence"
    ],
    "hedge": false,
    "matched_surface": "explicit",
    "measurement_cues": [],
    "null_cues": {
      "complement": [
        "evidence"
      ],
      "negation": [],
      "self_null": []
    },
    "occurrence_results": [],
    "result_complement": null,
    "term_clause": "providing direct evidence that explicit beliefs can influence the social evaluation of faces.",
    "term_occurrences": 1
  },
  "guard": {
    "absence_statement": false,
    "causal_cues": [],
    "correlational": false,
    "fragment": false,
    "hedged": false,
    "negated": false,
    "starts_mid_sentence": true,
    "study_description": false
  }
}
```

Exact source passage:

> providing direct evidence that explicit beliefs can influence the social evaluation of faces.


All five c3 observations are enumerated above, including rejected alternatives.
p36's explicit record contains term=explicit, exact_text=explicit, positive_finding,
local_finding_predicate, ambiguity=null and its own explicit term_clause.
The same p36 passage has a *different* implicit record, null_finding/local_null_same_clause.
These are two independently scoped facts sharing one physical source, not a text-based cross-value substitution.

No observation stores assertion_relation. Legacy presentation checks currently classify p8 as prior-work,
p36 as this-study-result, p7 as this-study-result and p52 as unknown. Those are **presentation outputs**
from the unchanged checker, not newly justified assertion_authority ownership values.
The report neither repairs nor transports them as candidate ownership.

**Explicit receipt:** establishment.selected_binding = p8; upstream category-goal basis =
the existing positive observation set {p8,p36,p52}; authorized scientific coverage =
those exact scoped positive records; display-ready coverage = p36; citation = p36's sealed locator.
p8's display restriction and p52's restriction remain inspectable. Unknown p7 cannot donate coverage.
It would be inaccurate to say only p8 scientifically establishes presence: the engine's any-positive
goal rule already considers p36 and p52 too. It is accurate to say only p8 is the selected binding.

**Implicit receipt:** establishment.binding = p36; goal positive presence = unestablished;
reported finding = null_finding; scientific/display/citation path = its own p36 null record and selected
legacy view. The null can be reported; no positive claim or new role support is generated.
One printed source sentence may have two value receipts because the structured records authorize both.
The second clause is not an implicit result inferred from explicit's receipt.

Option A is unnecessarily restrictive for explicit given the existing structured authority.
Option C is not required: scope, polarity, provenance and source are recoverable from stored records.
Observation IDs/locators added by the detached adapter are reference infrastructure, not new scientific data.
The implicit distinction is closed by typed reporting versus goal state, not by changing the map.

## Category-observation matrix (D3)

E = establishment of the upstream slot/goal; C+ = positive scientific coverage;
D/Cite = finding display and its own source citation after display checks.
An observation adapter never establishes E; it only reports the frozen upstream decision.

| Case | E change | C+ | D / citation permission |
|---|---|---|---|
| A selected A + positive A | None | Yes, exact scope | Yes on A path |
| B selected A + positive B | None | No for A | No borrowing B |
| C text mentions A, structured category B | None | No for A | No; textual mention is irrelevant |
| D selected A + null/negative/nonfinding A | None | No positive presence | Typed null may report through A's existing selected path; mentioned/unknown or reserved contrary cannot assert a result |
| E ambiguous/untyped A | None | No | Diagnostic only |
| F two positive A, different sources | None | Both | Both retained; display may choose equivalent presentation, citations stay path-specific |
| G duplicate identical observation path | None | One set member | One receipt edge; same ID/different body fails |
| H positive A + excluded candidate mentioning A | None | Positive observation if independently valid | Exclusion stays diagnostic; never borrowed; contradictory same-path gates fail |
| I A established, selected display support restricted + positive A | None | Yes | Observation may supply display/citation (real explicit) |
| J missing A + positive A | None | No new positive claim | In current valid producer this combination is inconsistent; reject stale map or keep unattached diagnostic, never repair |
| K positive A in different requirement | None | No for target | No cross-scope donation |
| L same printed category in distinct authored scopes | None | Separate | Separate receipts/value IDs; no label-only merge |

## D6–D9. Closed semantic values and grouping

Dispatch on the declared strategy and stored binding/view representation, never role-name or domain
vocabulary. Current vocabulary is exactly named_instrument_lexicon, achieved_outcome_predicate,
explicit_category_terms, direction_or_sign_pattern, model_nomination_only.
The immutable projection adapter consumes validated selected views/proofs, not candidate discovery.

| Shape | Semantic representation / identity | Renderability and evidence association / failure |
|---|---|---|
| 1 authored category | authored_category with exact term + authored role/category scope | Literal category label; goal/polarity separately from selected legacy support and authorized scoped observations |
| 1 named lexicon or model-nominated literal | literal_value with exact stored nominated/lexicon text in scope | It is a literal value, not a guessed normalized entity. Selected support/locators must validate |
| 2 achieved-outcome paired with independent named operands | evidence_slot: authored category_description + sorted role/literal operand tuple | Descriptor never rendered as a finding. Selected proof's assertion is evidence/operand; independent names remain names |
| 3 standalone achieved-outcome finding | literal_assertion with exact selected assertion text | All distinct eligible literal assertions produce distinct values/paths; no first-candidate collapse |
| 4 inherited named value | Same literal adapter in child role scope; outer source remains inherited | Context-only unless the child's stored proof establishes a relation; original source retained |
| 5 candidate-backed named/custom value | Explicit stored authored/nominated value ref if present; otherwise literal_assertion, not invented entity | Each eligible selected view is a path; absent independent name cannot be reconstructed from representative. Unknown strategy is not accepted |
| 6 legacy null text | Non-renderable diagnostic value_unresolvable | Keep support refs and slot state; no label from role text or first PID |
| 7 support IDs but no value text | Same as 6 | Source existence does not create a semantic name |
| 8 candidate assertion, no independent named value | literal_assertion | Literal finding is the value; no entity extraction, no arbitrary first candidate |
| 9 unsupported/unknown strategy/shape | value_unresolvable diagnostic | No positive claim/render; exact refs retained; explicit unsupported adapter error in qualification |
| direction_or_sign_pattern literal binding | literal_value from the selected binding | Its sign is not a direction summary; summary authority comes only from aligned observations |

Candidate-backed custom semantics require an explicitly supported authored shape. A recognized strategy
with only a candidate assertion can expose a literal finding; an unknown strategy must not silently
gain that fallback. Missing/ambiguous/excluded-only bindings are diagnostics, not filled values.
A nonempty value with an unlocated candidate can remain semantically established by the frozen map
but has display=unavailable until an already stored locator resolves; do not search the quote to repair it.

**D7:** zero real unexpected unsupported mappings. All 51 filled placements were visited:
38 claim-bearing own placements and 13 inherited context placements. All three category bindings have
literal values; none of the real filled bindings has null text. The 32 claim-member values reconcile
to 19 literal_value + 9 evidence_slot + 1 literal_assertion + 3 authored_category.
The 13 inherited placements are separately enumerated, not hidden in the 32-value count.

**D8 canonical value identity** (full SHA-256; no truncation):
UTF-8 JSON, sorted object keys, compact separators, ensure_ascii=false, allow_nan=false.
No implicit case-folding/whitespace/synonym normalization of literal values.
Material schema=semantic-value-v1; scope={owner_id,requirement_id,role}; kind; then:
authored_category -> category_identity={term,role}, literal=exact term;
literal_value/literal_assertion -> literal=exact stored value;
evidence_slot -> slot=authored category_description and operand_tuple sorted by role with each exact
independent literal. The real tuple contains one named operand; generic tuples use all independently
established named operands participating in that proof. Optional unrelated bindings are excluded.
Prefix semantic-value-v1:sha256: plus the full digest. No evidence IDs, discovery index, representative
PID or instance key in material. The annex computes this exact scheme for the current single-operand tuples.

Authoring changes that change meaning must change scope or material; identity is not cross-study entity
resolution. A validated literal can retain awkward source hyphenation. Display normalization is an
audited transform, never an identity rewrite. A future independently stored value key would require
an explicit adapter version, not a silent improvement.

**D9 grouping:** preserve the current requirement/role/quantifier grouping eligibility, including
the existing exclusion of at_least_n from this list fold. Same value ID within that scope becomes
one member with all establishment/coverage paths and instance placements. Repeated category identity
merges only inside that grouping scope. Different authored category/role scopes stay separate even
with the same label. Ordered output sorts IDs, not candidate arrival order; canonical set arrays
deduplicate by exact reference, not text. Never recompute cardinality, map state or recovery from
display member count. Real controls: Hadza has one member/two placements/two source paths; Explicit
Bias Questionnaire has one member/four placements and all selected source sets. No identity across
the c3 and c6 explicit categories or across c1/c4/c5/c6 region roles.

## D10–D12. Coverage receipts, scientific state and plan state

Every semantic member, including each relational operand, carries a value-coverage-v1 receipt:

~~~text
value_id
placement_refs[]; role_spec_ref; binding_state_ref
establishment_refs[]           # binding/view and upstream goal-basis refs, distinctly typed
scientific_coverage_refs[]     # selected support, category observation, aligned proof/observation
display_refs[]                 # authorized evidence scope + optional display envelope
citation_refs[]                # source locator on the same path, with own/inherited role
scientific_goal_state
reported_finding               # category positive/null/mentioned/unknown, or not_applicable
display_state
limitations[]                  # closed reason codes + affected ref
~~~

A source's eligibility for positive scientific coverage does not guarantee it passes existing display
checks. No union may supply missing per-value edges. Convenience citation unions are derived only
after receipts exist and may never be consulted to establish member coverage.

**D11 vocabulary:**
scientific_goal_state = established | unestablished | incomplete | not_applicable.
Established means this exact semantic target, not every enclosing scientific relationship.
A named instrument is established as a name, not as evidence of a brain relationship.
Invalid evidence/profile is a validation error; do not use "invalid science" as an ordinary state.
Category reported_finding = positive_finding | null_finding | mentioned_only | unknown | not_applicable.
display_state = supported | restricted | unavailable | invalid:
supported has at least one authorized, faithful display path; restricted has located evidence but
fails a declared presentation condition; unavailable lacks a necessary text/locator/value/context;
invalid indicates inconsistent refs and withholds the profile output, rather than rendering a fallback.

Typed reasons: value_unresolvable, unsupported_value_shape, source_unlocated, source_missing,
display_rule_failed (with exact existing rule ID), context_unavailable, context_ambiguous,
reference_integrity_error, goal_unsatisfied_null, goal_unsatisfied_unknown, attachment_ambiguous,
guard_excluded, support_policy_excluded. The latter three transport existing facts only.

**D12 exact state rule:** keep three separate axes:
(1) upstream role/requirement/goal state, unmodified;
(2) requested scientific target/relation establishedness using the existing proof meaning;
(3) report coverage for the authored answer facet.

Facet answered: all authored reporting obligations have authorized display receipts, with required
relationship proofs when the obligation is relational. An existing selected category null finding
can answer a category *findings-reporting* obligation only as a null, while its positive-presence goal
remains unsatisfied. This is not a new null goal and never closes recovery.
Facet partial: not answered, and either an exact requested scientific target is established but
display-restricted/unavailable, or a scientifically valid subcomponent is actually reportable.
Facet not_established: neither condition above; do not infer a requested relation from filled names.
Facet searched_empty: only existing certified empty-search outcome, never from display failure.
A malformed profile is a rejected build, not a node state.

For open_list, report coverage cannot certify exhaustive completion. Existing paired/for-each and
required-role obligations remain scoped as authored; display dedup does not remove them.
Node aggregation stays all answered -> answered; any answered/partial -> partial;
all searched_empty -> searched_empty; otherwise not_established. Preserve separate facet axes in
the node. In particular, a member name's establishment is not proof of the facet's relation.

This deliberately revises a plan-v4 conflation: established but undisplayable results must not be
labeled scientifically absent. The new real expectation changes four node status labels (below).
No map/role/category/recovery change follows. Disclosures must carry typed display limitations;
they may not say "retrieved evidence does not establish X" when X is already established.
This audit does not design I2-3 polarity prose; retain source wording and structured goal/polarity facts.

## D13–D15, D20, D24. One validation authority and immutable projection

Recommend a new sibling module under experiments.ask_cli_revised owned by the Layer A/B sufficiency
boundary, **layerc_projection.py**, with a single public entry
validate_layerc_inputs(map, sealed, authored_contract, *, profile, optional_context_receipts=()).
Return LayerCProjectionV1 (schema layerc-validated-projection-v1) or typed integrity error.
This name reflects inspected ownership: compatible_witness validates but also rebuilds support views;
its existing validator and finalize_instance are forbidden shortcuts here.

The owner may traverse bindings **once to index and validate exact stored payloads**, including
excluded records. This is not enumerating alternatives to choose supports. Layer C never receives
mutable candidate arrays. It resolves only stored registry IDs/placement+payload digests, and uses
existing selected proof assignments or eligible atomic-view records. No Cartesian products, new
witness selection, policy/attribution/direction/effect classification, remapping or silent repair.

Validation order:

1. Exact profile/identity authorization; sealed/map/authored input hashes. Bind the actual map,
   not only its sufficiency version or an old Phase-28 ledger hash.
2. Index existing support records/views/eligibility receipts/proofs/observation bases; verify their
   canonical IDs, exact placements, quote hashes, spans, source identity, text and outer source.
3. Match immutable candidate payload digest to exact placement; validate stored gate consistency.
   No call to build_support_views, support_policy, assertion_authority or a classifier.
4. Validate each stored assignment: authored verifier/purpose/roles, selected refs, source membership,
   own/inherited containment checks under the existing v8 rule, and existing proof checks. For a
   same-proposition join, the stored joining PID is on every required own selected path. For a link,
   validate the stored designators in the selected operands using the same closed extractor only;
   do not call a candidate selector or link finder.
5. Validate joint_grounding/witness_proofs membership and frozen prerequisite state, observation
   basis and evidence_alignment IDs, exact selected-path/operand refs and summary references.
   No rerun of summaries, direction or effectiveness; existing complete-instance/I1 distinctions remain.
6. Resolve category observations by containing scope, immutable body and sealed source equality.
   Validate stored category summary consistency from existing polarity facts, not by reclassifying text.
   The single-role category contract makes role placement recoverable; ambiguous multi-role shapes fail.
7. Derive pure semantic-value records/coverage permissions under the closed adapters and display
   envelope bounds. These are reference projections of the stored scientific decision.
8. Freeze projection registries, returning only immutable values/refs. Deep input equality required.

Stored-path validation proves soundness/consistency of the assignments supplied; it does not prove
exhaustive candidate search or that the producer omitted no possible proof. That remains Layer A/B
qualification plus authorized map provenance. A self-consistent hash does not establish authenticity.

Minimum projection: exact profile+input identities; semantic placements/role specs; frozen binding/
goal states; support/view refs; candidate metadata refs; category-observation refs; proof and aligned
observation refs; typed values; coverage permissions/receipt templates; display-envelope refs;
link-context statuses; typed diagnostics. No whole duplicated witness bundles, candidate arrays or
rendered prose. ParentClaims and AnswerPlan consume the **same projection identity**.
Scientific/display-source authorization belongs here. Final display eligibility uses explicit
presentation checks during I4-4D and finalizes the same receipt; it cannot add an evidence edge.

**D14 excluded metadata:** detached index key =
{map_sha256, placement(child,requirement,instance,role), candidate_payload_sha256}.
Normalize only the exact existing candidate serialization (support IDs set-normalized as in
compatible_witness.normalize_candidate), then hash; additionally map support_ref/grounding identity
to that key. Index all payloads without selecting. Expose exact relation, aggregation, kind,
authority_veto, is_caption, attachment uncertainty, guards, support-policy receipt/source/failed
dimensions, spans, assertion text and attribution proof/context/ruleset refs.
Five real exclusions have support_records but no eligible support_view. They remain metadata-only;
no positive claim may point to the diagnostic index in place of an eligible view.
Same key/different bytes or conflicting payloads for one physical support identity fails loudly.
Identical duplicate bodies normalize to one ref with all placements retained.

**D15 link-only closure:** the v8 lightweight verifier tests a shared designator in selected own
operand texts and requires nonempty supplied attachment context. It records context_sha256 of the
ordered attachment_pieces list; it does not store a finding quote proving a separate joint predicate.
Do not confuse this with contract_directed.find_links or original-source retrieval.

- Present, unique, hash-matching ordered context bytes: validate existing fields/offsets; expose a
  context-only display reference. It becomes a source citation only if an already supplied sealed
  locator/source receipt independently validates. Matching a hash alone is not citation authority.
- Missing bytes: stored map proof remains usable for the narrow typed shared-designator relation
  with selected operands and their own citations; joint-context quote unavailable. No fabricated PID.
  This is option A for a structured relation, with display limitation for any stronger joint prose.
- Hash mismatch: integrity error; reject projection, never ignore supplied conflicting context.
- Multiple identical matching bodies: deduplicate. Multiple incompatible claimed bodies/locators:
  ambiguous context diagnostic, no context display/citation; if they contradict a referenced identity,
  integrity error. Do not choose the first.

Even with matching bytes, a link-only proof authorizes only its stored relation kind and purpose;
it does not create I1=true, common witness PID, an effect or a causal assertion.
Inherited operands preserve outer inherited identity. Parent-origin proof never substitutes for child proof.

## D16–D17. Evidence span versus display envelope

Choose **B: terminal punctuation/whitespace only** as the initial deterministic envelope.
Exact evidence assertion bounds remain unchanged. No leading discourse-marker expansion is needed
to make a selected assertion readable. A known marker can stay visible when already inside an
authorized legacy whole-unit scope; that is not expansion of a candidate assertion.

display-envelope-v1 contains source ref/hash, evidence_span, display_span, added prefix/suffix
intervals, wrapper rule IDs, and literal wrapper bytes. Whitespace means adjacent source whitespace.
A terminal period may be added only when immediately adjacent in the same sealed source and not
part of an alphanumeric decimal/abbreviation continuation; otherwise use exact assertion. No search
past intervening semantic text. Existing terminal punctuation is not re-added. No wrapper interval
may be a support/observation/value locator or satisfy another claim.

For c3's selected finding, the source begins "Nevertheless, " but the assertion begins "we found".
The display may add its authentic final period; it does **not** add "Nevertheless, ".
A c6 legacy named-value view still authorizes its whole source scope, so its display can contain
that marker without broadening c3 evidence. Display dedup may share a surface only if every member's
receipt authorizes that exact surface; it cannot widen the narrower receipt.

| Probe | Expansion verdict |
|---|---|
| terminal period | Allowed under immediate-adjacency rule |
| leading whitespace | Allowed; recorded source offsets |
| Nevertheless, | Not allowed by initial envelope; would require a separately accepted parser/wrapper contract |
| However, | Same; no free-form discourse inference |
| run-in Results label | Forbidden semantic/ownership expansion; use existing ownership metadata, not added label |
| leading prior-work phrase | Forbidden; changes owner |
| coordinated second result clause | Forbidden; separate assertion/receipt required |
| trailing citation marker | No wrapper grant; requires existing structured citation token/locator proof, otherwise exclude |
| parenthetical statistic | Forbidden addition; may stay only if already inside evidence span |
| semicolon plus second assertion | Forbidden |
| colon plus second assertion | Forbidden |
| quotation punctuation | Requires existing structured delimiter proof; initial envelope does not add it |
| caption prefix | Forbidden addition; caption metadata is retained, not a new global policy rejection |
| external-owner prefix | Forbidden; changes attribution |

Coordinated-clause control: an assertion ending before "while B decreased" may gain an immediately
adjacent terminal period only if one actually exists there. It cannot skip "while", synthesize
punctuation, or include the second clause. This can leave a source-authentic fragment that is
display-restricted; no evidence widening is permitted to fix it. Plan-v5 need not be byte-identical
to old source-sentence rendering.

## D18–D19. Refined claim evidence and identity

claim-evidence-v1 remains the planned, never-shipped receipt schema; refine it now to typed edges:
establishment, scientific_coverage, display_envelope, citation, relation_proof and observation.
Each edge includes value/tuple refs, exact placement, own/inherited source, source locators,
eligibility/metadata refs and limitations. Category observation edges state positive/null authority
explicitly. Completion and I1 proof purposes remain distinct; no first-proof representative.
Direction/effect receipts point to aligned observation IDs and stored summary/conflict state.
No rerun classifier; no new effectiveness I1 gate.

Semantic claim ID: parent-claim-v2:sha256: + canonical full SHA-256 of:
schema, family, authored scope(owner IDs, requirement IDs, role/category grouping) and:
- role_value: one value_id;
- category_list: sorted unique member value_ids + authored grouping/quantifier identity;
- relational: role-keyed semantic tuple + authored relation contract identity and establishment
  relation kind. A tuple of all own completion operands is joint_own_completion; a required-role
  tuple including inherited operands, or a proper required subset of completion operands, is
  required_role_relation. Determine this from authored participation and outer source, never which
  proof happened to be listed first. If the all-own required and completion tuples are identical,
  use joint_own_completion once and retain both proof purposes as supporting edges.
  Do not merge distinct tuple/claim meanings.
- direction_or_effectiveness: authored relation/target scope, role-keyed tuple IDs, summary kind,
  stored consensus/outcome and conflict flags. A changed sign is a changed semantic claim.
  Underlying relation claim stays separate when consensus is null/conflicted.

No evidence/proof/PID/receipt/instance/discovery-order fields enter semantic claim ID.
Literal text enters only through a literal semantic value. Display edits never enter it.
Authored contract identity in semantic material is the relevant stable scope/subcontract, not
an unrelated whole-map run hash. The full contract hash still binds the profile.

Receipt IDs: claim-evidence-v1:sha256: + canonical entire receipt body excluding receipt_id;
value-coverage-v1 analogously. Arrays representing sets sorted by typed ref ID; semantic ordered
tuples retain authored role identity. Evidence path/source/placement changes alter receipt IDs;
they cannot alter claim meaning solely because a representative moved.
The annex uses C01–C17 as stable human aliases for the prospective semantic claims and gives their
member IDs; old IDs are trace locators only, not new schema identity material.

Closed JSON identity envelope for implementation: {schema, family, scope, content}, with
schema=parent-claim-v2; scope={owner_ids, requirement_ids}, both sorted unique strings.
Content is exactly one of:

- role_value: {role, value_id}.
- category_list: {role, member_value_ids, grouping}, where grouping={instance_quantifier,
  quantifier_n, requested_category_terms}; terms are exact authored strings sorted as a set,
  quantifier_n retains null when inapplicable. The list identifies observed values, not a blanket
  claim of positive presence; typed polarity/goal receipts prohibit that interpretation.
- relational: {relation_kind, operands, relation_contract}, where operands maps role to value_id;
  relation_contract={required_roles, alternative_role_groups, relationship_verifiers}. Role and
  verifier sets sort; alternative groups sort internally and then lexicographically. Optional
  roles do not enter completion scope. Distinct authored scopes cannot collide.
- direction_or_effectiveness: {summary_kind, operands, target_contract, consensus, conflict},
  with target_contract the exact authored direction or effectiveness object, consensus the stored
  summary value (including null), and conflict the stored conflict flags. Observation/PID/proof
  lists are excluded; no textual regeneration or classifier interpretation enters this object.

Reference IDs are likewise closed: category-observation-ref-v1 hashes {schema, placement,
observation, source_identity, quote_sha256}; placement includes child_id, requirement_id,
instance_key and role. observation is the exact stored record, including audit/guard fields;
source_identity is {paper_id,evidence_anchor_chunk_id,evidence_span_id}. These current category
sources are single-anchor; any plural-anchor source must additionally resolve its sealed anchors
through the source registry, without dropping them. The full map/sealed profile hashes bind that
registry. Unknown/missing schema fields fail instead of silently widening this identity.

Exact category-observation reference registry (the seven stored observations on the three
claim-bearing category values; no observation is omitted):

| Member | Source / state | category-observation-ref-v1 SHA-256 |
|---|---|---|
| V20 | p17 / unknown | 343929ad76396bc8bae765f0236d871deeb92dc88325494f151df0155c8bbd87 |
| V20 | p52 / positive_finding | 86131c9eeacef6834c7b8048ad033cf64e367f53225115d19841530af0a96163 |
| V24 | p36 / null_finding | 00d5a665483085e7f8771d1de013a285832773505751207797273270450f7b55 |
| V25 | p8 / positive_finding | 4a873cc16345b5304f83fe3b3f000de448d820c8d02ed79498887d7bace6f2fb |
| V25 | p7 / unknown | 92ee023dc64d0adec826b61f941318648789f919284cf45ef30bafed908323fa |
| V25 | p36 / positive_finding | 354a9a5e01c3ebfb147ba25e1c6c7cbf38d450272ea273262f793783c501d110 |
| V25 | p52 / positive_finding | a71be5ce3306f1d352d78f448ce0077a4f81f1e6435c9b39c14aa902b9456667 |

## D21–D22. Exhaustive real value and claim/member inventory

The following is not a sample. V01–V32 are the **32 distinct claim-member values** from all 17 claims.
"Established" on a name means the named value, not its enclosing requested relation. The implicit
row explicitly marks its positive-presence goal unestablished while its null report is supported.
All mapping rows have unsupported=false. Evidence-slot descriptors are never rendered as prose.
Display results below are observed existing presentation checks applied only after an authorized
value-specific association; future profile expectations preserve these restrictions. They are
not new upstream support-policy evaluations.

| Value | Claim | Class | Role | Exact semantic literal or slot descriptor | Scientific state / finding | Display | Renderable source | Unsupported |
|---|---|---|---|---|---|---|---|---|
| V01 | C01 | literal_value | brain_region_or_network | the specific amygdala response | established | restricted | no primary display | False |
| V02 | C01 | evidence_slot | neural_manifestation_evidence | an observed neural finding bearing on the bias | established | restricted | no primary display | False |
| V03 | C02 | literal_value | behavior_or_behavioral_measure | faster to share when playing with the good partner compared to the bad | established | restricted | no primary display | False |
| V04 | C02 | evidence_slot | behavioral_manifestation_evidence | an observed behavioral finding bearing on the bias | established | restricted | no primary display | False |
| V05 | C03 | evidence_slot | region_bears_on_bias_evidence | evidence that the named region bears on the bias | established | restricted | no primary display | False |
| V06 | C03 | literal_value | named_brain_region_or_network | the specific amygdala response | established | restricted | no primary display | False |
| V07 | C04 | literal_value | named_brain_region_or_network | increased amygdala reactiv- ity | established | restricted | no primary display | False |
| V08 | C04 | evidence_slot | region_bears_on_bias_evidence | evidence that the named region bears on the bias | established | restricted | no primary display | False |
| V09 | C05 | evidence_slot | relationship_to_bias_manifestation | evidence relating the trait/construct to the bias's manifestation | established | restricted | no primary display | False |
| V10 | C05 | literal_value | individual_difference_trait_or_construct | attractiveness | established | restricted | no primary display | False |
| V11 | C06 | evidence_slot | relationship_to_bias_manifestation | evidence relating the trait/construct to the bias's manifestation | established | restricted | no primary display | False |
| V12 | C06 | literal_value | individual_difference_trait_or_construct | trustworthiness | established | restricted | no primary display | False |
| V13 | C07 | evidence_slot | relationship_to_bias_manifestation | evidence relating the trait/construct to the bias's manifestation | established | restricted | no primary display | False |
| V14 | C07 | literal_value | individual_difference_trait_or_construct | anger | established | restricted | no primary display | False |
| V15 | C08 | literal_value | individual_difference_trait_or_construct | dominance | established | restricted | no primary display | False |
| V16 | C08 | evidence_slot | relationship_to_bias_manifestation | evidence relating the trait/construct to the bias's manifestation | established | restricted | no primary display | False |
| V17 | C09 | evidence_slot | relationship_to_bias_manifestation | evidence relating the trait/construct to the bias's manifestation | established | restricted | no primary display | False |
| V18 | C09 | literal_value | individual_difference_trait_or_construct | threateningness | established | restricted | no primary display | False |
| V19 | C10 | literal_assertion | attitude_manifestation_evidence | we found evidence for the “anomalous-is-bad” stereotype in explicit negative attitudes about people with facial anoma- lies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit Bias Questionnaire) | established | supported | p14,p17,p26,p3,p7 | False |
| V20 | C11 | authored_category | category_evidence | explicit | established / positive_finding | restricted | no primary display | False |
| V21 | C12 | literal_value | named_culture_or_population | Hadza | established | restricted | no primary display | False |
| V22 | C13 | literal_value | behavior_or_behavioral_measure | decisions that were incongruent with behavioral bias (share with bad partner and keep with good partner versus the alternative choices) | established | restricted | no primary display | False |
| V23 | C13 | literal_value | behavior_or_behavioral_measure | share decisions between partners (good versus bad) | established | restricted | no primary display | False |
| V24 | C14 | authored_category | category_evidence | implicit | unestablished / null_finding | supported | p36 | False |
| V25 | C14 | authored_category | category_evidence | explicit | established / positive_finding | supported | p36 | False |
| V26 | C15 | literal_value | individual_difference_trait_or_construct | negative attitudes (IAT and EBQ) | established | restricted | no primary display | False |
| V27 | C15 | literal_value | individual_difference_trait_or_construct | social cognitive biases (just-world beliefs) | established | restricted | no primary display | False |
| V28 | C15 | literal_value | individual_difference_trait_or_construct | emotional dispositions (affective empathy) | established | restricted | no primary display | False |
| V29 | C15 | literal_value | individual_difference_trait_or_construct | undesirable behaviors (less generosity in the DG) | established | restricted | no primary display | False |
| V30 | C16 | literal_value | behavior_or_behavioral_measure | participants made more share decisions overall when playing with the good partner than with the bad | established | restricted | no primary display | False |
| V31 | C16 | literal_value | behavior_or_behavioral_measure | participants were faster to share when playing with the good partner compared to the bad | established | restricted | no primary display | False |
| V32 | C17 | literal_value | attitude_type_or_measure | Explicit Bias Questionnaire | established | supported | p14,p17,p26,p3,p7 | False |

Full identity registry (prefix semantic-value-v1:sha256: applies to each 64-hex digest):
- V01 = `71e539b97612a8e6b7c55805d777aa625355908b317a8657322a26f331a2dd08`.
- V02 = `dfb887dc4970e0245a4f3f7b0c85ae39d7c3a6e7a8607c0da71b5a86f7052d00`.
- V03 = `3fcebcec37ff6f5b014a578c90da202ed158c969a2ab9b8fd6363c18ddebe25c`.
- V04 = `751e23ed92b57b22709dd30b7adb5b6e928f5cb5f87aca818d592ed254d878da`.
- V05 = `02e3471955ebe76fd628662fd3be9bb03341d58f7678b0bd24222fe1783e4689`.
- V06 = `c71d74c74520515a44822188e345418c1546cb83e49d8f910e2a448c3be81067`.
- V07 = `e29229098dae6fa5dc269d953ad2b2c3a070e02fa88dd39647956dde5972de93`.
- V08 = `0010d9051d1776feefd833e762303a1b5e1fc5b031202b6af75add7496d1a82f`.
- V09 = `9871c85eb64726c5b1394e3051e8e6f7e5e6013311fc846e8ec4f11d885d7587`.
- V10 = `637bdfd2f6c67012d4617655bd7c09e1a13d615b207f3185916e625f4eabe595`.
- V11 = `1d84fca93f15e3cbf8dfce00c41e153e7e957ded16c6477f9babc664b119a162`.
- V12 = `8c3e973976d23a8472f3f094b9b1ed52cd7f012e33e84a0eedd306add0422f20`.
- V13 = `15046f1f6a3546697d0c77fde5d61e70e19eded91538b4aaac6bb14d65e8f902`.
- V14 = `c2247677d32bf4a9e3ab39db7d2e1cf63ba398f24258302bdf19afa2a448c46c`.
- V15 = `52de78a144af120d61898d196d1ffbca88c38e71a7f3de2c7cb735679f2adcdc`.
- V16 = `0a612abee98c488f11ecaef9b20538d3a2050125d5dc06f8acc78a1bef0f0608`.
- V17 = `972f2149ad56f9a9d9e28f17eed71fcb2181e5ef6d0e92d5bec12c80eb9228d3`.
- V18 = `a4e6cf453349208936e627f051220b0cf0736d4cb37c658f8e65814f943ca8d5`.
- V19 = `20ab47f0575592ac3519357d1ce20dd537f68e8caa32384b0f1bf8dabe4e171f`.
- V20 = `0b2d5d6507dbbc6f6d0212b7cc0411c9be3d2663cc7798295605d85659716980`.
- V21 = `ec620d2e915553dd9fc9bb83a0dc3330247d83aa357b1ff02ccaedd9e59eba7b`.
- V22 = `236ced83cf41481eb76b7733518a532c21bc2d2f4b808530c35c01e5c8d6dbc9`.
- V23 = `f6dcd8bfe866cd5c62411674f25e50d2ad99279174bd34a1f3b5b183e8d2edba`.
- V24 = `8eb2403f24906e5a891c736b9c91bd3b29610c9a46866a1685e7105c656a6ea0`.
- V25 = `bc62af4f96a9b58b0d2cd5c38de50473a465baf5e23665a718971518907978c5`.
- V26 = `460dfdd5d724ad401ae421c98262ddea836c1e1b51a50946652c9f0331455992`.
- V27 = `67404b8a0b0b338af1eb1440bb7fd438174e8050771d99bfef940924f67c7d29`.
- V28 = `be4fdda9a1c7a097f7098d7333cb28702273ade4921d78726b0289e720ec89d4`.
- V29 = `13da9580be9944534392f504551b6bad7cad0d7c54e9eacbbc97d46957d1187e`.
- V30 = `c7fe32e9c37b15c9bc91fe0261f24cf922eac5561a5dcff7463bcb916b5ecf4b`.
- V31 = `565e311eb69e7038959dbae8cbf58c07f808b1c2e310671c8f87732b2d46c0ce`.
- V32 = `4d66f019291fc331bfcbd04fd731c2117a9840421ea7db303023dbe9a657e72e`.

The next table makes all per-member edges explicit. E = selected establishment support/view(s);
S = authorized scientific evidence (for the exact name/finding/goal only); D = allowed primary display
source; C = citation for D, or evidence-only locator when D is restricted. "None" never means no science.
Every E path is resolved by placement and role in the placement annex; the support sets shown are
those paths' sets, not a claim-wide union used for coverage.

| Claim key / legacy trace ID | Family | Member | E | S | D | C | Limitation |
|---|---|---|---|---|---|---|---|
| C01 / relational::203c254207f97488 | relational | V01 | p11,p2 | p11,p2 | none (restricted) | p11,p2 (evidence audit only) | referentially_closed |
| C01 / relational::203c254207f97488 | relational | V02 | p11,p2 | p11,p2 | none (restricted) | p11,p2 (evidence audit only) | referentially_closed |
| C02 / relational::51f7d49ce0af93a4 | relational | V03 | p47 | p47 | none (restricted) | p47 (evidence audit only) | requested_construct_direct |
| C02 / relational::51f7d49ce0af93a4 | relational | V04 | p47 | p47 | none (restricted) | p47 (evidence audit only) | requested_construct_direct |
| C03 / relational::493c9ae66cd9558c | relational | V05 | p11,p2 | p11,p2 | none (restricted) | p11,p2 (evidence audit only) | referentially_closed |
| C03 / relational::493c9ae66cd9558c | relational | V06 | p11,p2 | p11,p2 | none (restricted) | p11,p2 (evidence audit only) | referentially_closed |
| C04 / relational::f2151b28ac6f7906 | relational | V07 | p40 | p40 | none (restricted) | p40 (evidence audit only) | attribution_prior_work |
| C04 / relational::f2151b28ac6f7906 | relational | V08 | p40 | p40 | none (restricted) | p40 (evidence audit only) | attribution_prior_work |
| C05 / relational::b98797f466e662e8 | relational | V09 | p41 | p41 | none (restricted) | p41 (evidence audit only) | not_stimulus_rating |
| C05 / relational::b98797f466e662e8 | relational | V10 | p41 | p41 | none (restricted) | p41 (evidence audit only) | not_stimulus_rating |
| C06 / relational::ffd4e0ac38b79c90 | relational | V11 | p41 | p41 | none (restricted) | p41 (evidence audit only) | not_stimulus_rating |
| C06 / relational::ffd4e0ac38b79c90 | relational | V12 | p41 | p41 | none (restricted) | p41 (evidence audit only) | not_stimulus_rating |
| C07 / relational::cf491ce7743dc485 | relational | V13 | p41 | p41 | none (restricted) | p41 (evidence audit only) | not_stimulus_rating |
| C07 / relational::cf491ce7743dc485 | relational | V14 | p41 | p41 | none (restricted) | p41 (evidence audit only) | not_stimulus_rating |
| C08 / relational::b87b1fc33715f29b | relational | V15 | p41 | p41 | none (restricted) | p41 (evidence audit only) | not_stimulus_rating |
| C08 / relational::b87b1fc33715f29b | relational | V16 | p41 | p41 | none (restricted) | p41 (evidence audit only) | not_stimulus_rating |
| C09 / relational::5a0a02f415cffd79 | relational | V17 | p41 | p41 | none (restricted) | p41 (evidence audit only) | not_stimulus_rating |
| C09 / relational::5a0a02f415cffd79 | relational | V18 | p41 | p41 | none (restricted) | p41 (evidence audit only) | not_stimulus_rating |
| C10 / role_value::c24ac1ab2f5259b2 | role_value | V19 | p14,p17,p26,p3,p7 | p14,p17,p26,p3,p7 | p14,p17,p26,p3,p7 | p14,p17,p26,p3,p7 | none on selected display path |
| C11 / role_value::cb9192d62bbccd00 | role_value | V20 | p52 | p52/positive_finding | none (restricted) | p52 (evidence audit only) | attribution_unknown |
| C12 / category_list::775fda7778860372 | category_list | V21 | p29,p53 | p29,p53 | none (restricted) | p29,p53 (evidence audit only) | passage_complete |
| C13 / category_list::ed3e1d5fd3979f2e | category_list | V22 | p35 | p35 | none (restricted) | p35 (evidence audit only) | requested_construct_direct |
| C13 / category_list::ed3e1d5fd3979f2e | category_list | V23 | p46 | p46 | none (restricted) | p46 (evidence audit only) | requested_construct_direct |
| C14 / category_list::351d34bff55b518f | category_list | V24 | p36 | p36/null_finding | p36 | p36 | implicit positive-presence goal unsatisfied |
| C14 / category_list::351d34bff55b518f | category_list | V25 | p8 | p8/positive_finding; p36/positive_finding; p52/positive_finding | p36 | p36 | none on selected display path |
| C15 / category_list::f1f51b4ba55bad3c | category_list | V26 | p20,p9 | p20,p9 | none (restricted) | p20,p9 (evidence audit only) | attribution_aim_or_hypothesis |
| C15 / category_list::f1f51b4ba55bad3c | category_list | V27 | p20,p9 | p20,p9 | none (restricted) | p20,p9 (evidence audit only) | attribution_aim_or_hypothesis |
| C15 / category_list::f1f51b4ba55bad3c | category_list | V28 | p20,p9 | p20,p9 | none (restricted) | p20,p9 (evidence audit only) | attribution_aim_or_hypothesis |
| C15 / category_list::f1f51b4ba55bad3c | category_list | V29 | p20,p9 | p20,p9 | none (restricted) | p20,p9 (evidence audit only) | attribution_aim_or_hypothesis |
| C16 / category_list::7ca8d31e2ecc7709 | category_list | V30 | p46 | p46 | none (restricted) | p46 (evidence audit only) | requested_construct_direct |
| C16 / category_list::7ca8d31e2ecc7709 | category_list | V31 | p47 | p47 | none (restricted) | p47 (evidence audit only) | requested_construct_direct |
| C17 / category_list::8ed22a387cb23c02 | category_list | V32 | p14,p17,p26,p3,p7 | p14,p17,p26,p3,p7 | p14,p17,p26,p3,p7 | p14,p17,p26,p3,p7 | none on selected display path |

C01 completion-only c1 remains a scientific completion tuple with I1=not_applicable; do not suppress
it merely because it lacks a required-role I1 proof. Its real display still fails referential closure.
C03 has four proof paths; other relational claims two each, including distinct completion/I1 purposes.
There are 20 original atomic-view paths; category-observation paths are added as separate typed edges,
never manufactured support views. c3 explicit's three positive observations have only p36 display-ready.

Physical/placement control for all 51 filled bindings:
| Value | Child / requirement / instance | Role | Selected source IDs | Exact selected view ref | Outer source | Evidence assertion span |
|---|---|---|---|---|---|---|
| V01 | c1 / c1#suff:neural-manifestation / null | brain_region_or_network | p11,p2 | support-view-v1:sha256:014205f6fdd3b492402a9364a008def912f8578fa1ab682f40472abe2f618043 | own | legacy whole unit |
| V02 | c1 / c1#suff:neural-manifestation / null | neural_manifestation_evidence | p11,p2 | support-view-v1:sha256:832b22daa18d0c6cfc934ebb874cdf0f2f77adca027842315c43a5392ce6f0d2 | own | [37, 264] |
| V03 | c2 / c2#suff:behavioral-manifestation / i::76d9e54baf790d84 | behavior_or_behavioral_measure | p47 | support-view-v1:sha256:a3155ee5b21b07eed12b449d46f4aaa9f218912a6b329406c80b65720c4b6125 | own | legacy whole unit |
| V04 | c2 / c2#suff:behavioral-manifestation / i::76d9e54baf790d84 | behavioral_manifestation_evidence | p47 | support-view-v1:sha256:f2efae4f60e6ab2b5d3ffe735efd6606d3dbec9c41e691eecc582dbcda675fcd | own | [76, 251] |
| V05 | c4 / c4#suff:specific-region / i::ac9b72f14d53f532 | region_bears_on_bias_evidence | p11,p2 | support-view-v1:sha256:094220b3515ca2ff2ebcaeae7c8776fd2bee93c8706b7635b7dfd53344d886ad | own | [37, 264] |
| V06 | c4 / c4#suff:specific-region / i::ac9b72f14d53f532 | named_brain_region_or_network | p11,p2 | support-view-v1:sha256:338e0c7eca7b9ba07497637356fb6ea0a47fd72024d1da8380cd5c3054b3a94b | own | legacy whole unit |
| V07 | c4 / c4#suff:specific-region / i::a3ab9566580a7fe4 | named_brain_region_or_network | p40 | support-view-v1:sha256:ecfb03ab4648443f3d81514f6414f633f171d02968cb0098a579ad85d33f81e5 | own | legacy whole unit |
| V08 | c4 / c4#suff:specific-region / i::a3ab9566580a7fe4 | region_bears_on_bias_evidence | p40 | support-view-v1:sha256:fa4ef6d5ecd4a8a3335c877e49e5e0c80b6d64dfa08aed9c0c444be6cb93d562 | own | [147, 273] |
| V09 | c8 / c8#suff:trait-construct / U23::24d132203292cebb | relationship_to_bias_manifestation | p41 | support-view-v1:sha256:7f3cbc09943aa838239964c2d07410a4f22a2dba3b736c89c77fa26c05b6d649 | own | [43, 200] |
| V10 | c8 / c8#suff:trait-construct / U23::24d132203292cebb | individual_difference_trait_or_construct | p41 | support-view-v1:sha256:af446c4b3cba8517a3d7f9016a03f56a30208fcc5659710ba9226ff2e8a0b6ef | own | legacy whole unit |
| V11 | c8 / c8#suff:trait-construct / U23::8d7156b76bf6a6f7 | relationship_to_bias_manifestation | p41 | support-view-v1:sha256:a3bd781cf3610b955a38e89134060d25eed38d9b7a0dc9c2f3a46cf98547832d | own | [43, 200] |
| V12 | c8 / c8#suff:trait-construct / U23::8d7156b76bf6a6f7 | individual_difference_trait_or_construct | p41 | support-view-v1:sha256:c3c78b9489293909d7bda74b0b049a9596049a487481c4b56d672b977b149a64 | own | legacy whole unit |
| V13 | c8 / c8#suff:trait-construct / U23::50b0d4004f2f502f | relationship_to_bias_manifestation | p41 | support-view-v1:sha256:8edd2fd356f099900375a40992cce1169a6146f798e4e86a768ded94a45474e9 | own | [208, 372] |
| V14 | c8 / c8#suff:trait-construct / U23::50b0d4004f2f502f | individual_difference_trait_or_construct | p41 | support-view-v1:sha256:ea828fcc3b14e2fc0e955519aa6d22c3a9175dec4a9b070e6bd7505fddf457fb | own | legacy whole unit |
| V15 | c8 / c8#suff:trait-construct / U23::f6027eb43b85593c | individual_difference_trait_or_construct | p41 | support-view-v1:sha256:189b7ebaf794bee0d3644b92aff49f755b3c36c7bc7bc75031829b4bbb902050 | own | legacy whole unit |
| V16 | c8 / c8#suff:trait-construct / U23::f6027eb43b85593c | relationship_to_bias_manifestation | p41 | support-view-v1:sha256:85ba7279d8d14127a6b46a2a453d458ce5922e3cc8a63c0c9238cc31e4286fd1 | own | [208, 372] |
| V17 | c8 / c8#suff:trait-construct / U23::910466e6604581fa | relationship_to_bias_manifestation | p41 | support-view-v1:sha256:20f4cad76aaa8955cfeb733e886c2a41e7e4d88205fd980819c2dae0ddf8f44f | own | [208, 372] |
| V18 | c8 / c8#suff:trait-construct / U23::910466e6604581fa | individual_difference_trait_or_construct | p41 | support-view-v1:sha256:67f97cb604f5c10dfe370b6774386f1410fb952955ef39aef5bf22c6ffbead73 | own | legacy whole unit |
| V19 | c3 / c3#suff:attitude-manifestation / null | attitude_manifestation_evidence | p14,p17,p26,p3,p7 | support-view-v1:sha256:d441ff1b3cff490bbf21a79e80cf1914810c66cbce1cb25035d25db87a7730f3 | own | [14, 251] |
| V20 | c6 / c6#suff:implicit-explicit-coverage / explicit | category_evidence | p52 | support-view-v1:sha256:92a831943179b9bc11a4781038becb69d7c60ed5a440ad3ee9eefef89cd8cc5c | own | legacy whole unit |
| V21 | c10 / c10#suff:culture-existence / i::e506b4436247cda9 | named_culture_or_population | p29 | support-view-v1:sha256:7a5239485837928a403acda9e565004b18b857d5ad2edaab8d8244974164bdb6 | own | legacy whole unit |
| V21 | c10 / c10#suff:culture-existence / i::22b9d69edba8b78a | named_culture_or_population | p53 | support-view-v1:sha256:bfac72827a7b503b8e488f38894bd308c42c9f47c74a911afbfd2a963e269c34 | own | legacy whole unit |
| V22 | c2 / c2#suff:behavioral-manifestation / i::4777c74a36ed08b9 | behavior_or_behavioral_measure | p35 | support-view-v1:sha256:75bdab4e7946dce84262bc1d8759554853f5d8957348062426d93ae2e4b96f36 | own | legacy whole unit |
| V23 | c2 / c2#suff:behavioral-manifestation / i::9fb27754ba7442ef | behavior_or_behavioral_measure | p46 | support-view-v1:sha256:657ed5efe978fe56111ddc37e019120663e25fc05762f545d8aa708498e59cee | own | legacy whole unit |
| V24 | c3 / c3#suff:implicit-explicit-coverage / implicit | category_evidence | p36 | support-view-v1:sha256:a01b445f6091ab1e379587d05b331a8e9d8c3bf945a4a2391109756a2f488913 | own | legacy whole unit |
| V25 | c3 / c3#suff:implicit-explicit-coverage / explicit | category_evidence | p8 | support-view-v1:sha256:b7b8cfa3588ca88c87e30c5f4031a9d764a70147a99f0bdc423cf4296fdfb04b | own | legacy whole unit |
| V26 | c8 / c8#suff:trait-construct / U6::b2958c5ad5164563 | individual_difference_trait_or_construct | p20,p9 | support-view-v1:sha256:1905baba683c4cc3c72a5464760aac8b3e3f35f577893af5664b38a9b2ae48f7 | own | legacy whole unit |
| V27 | c8 / c8#suff:trait-construct / U6::ce8933c59b53a00f | individual_difference_trait_or_construct | p20,p9 | support-view-v1:sha256:9c43d8b81d98c8fa4ca2b42c36229945354310b21011255d6c28f8f8ddc315be | own | legacy whole unit |
| V28 | c8 / c8#suff:trait-construct / U6::da37435ef9b489b6 | individual_difference_trait_or_construct | p20,p9 | support-view-v1:sha256:298178cfe3d71a0bb9326bad2ed5c88f499e3e4248a1c30f7035858983aa515e | own | legacy whole unit |
| V29 | c8 / c8#suff:trait-construct / U6::d41542e10edf3ea7 | individual_difference_trait_or_construct | p20,p9 | support-view-v1:sha256:135238c68ebc7ab85f03aabcc18039766775327b68889f5d0ace1a651b6eb8aa | own | legacy whole unit |
| V30 | c5 / c5#suff:brain-behavior / i::a3ab9566580a7fe4::13b13ddc969b96ae | behavior_or_behavioral_measure | p46 | support-view-v1:sha256:976945fc59d4fe210126e731e1116a8f248d585a0bcf4b2ffc3b16532eb8494d | own | legacy whole unit |
| V30 | c5 / c5#suff:brain-behavior / i::ac9b72f14d53f532::4a3f8a1c59aaa360 | behavior_or_behavioral_measure | p46 | support-view-v1:sha256:2e8e6111eb93edbcbb6ffa897ce8d30c34320ffbcfd25a4db6e8bf1fe6c3a9cb | own | legacy whole unit |
| V31 | c5 / c5#suff:brain-behavior / i::a3ab9566580a7fe4::855c307939056b14 | behavior_or_behavioral_measure | p47 | support-view-v1:sha256:69d323f98eb6fbc411056943459e1f1fef7580f8b622705290a4edbbb93d636d | own | legacy whole unit |
| V31 | c5 / c5#suff:brain-behavior / i::ac9b72f14d53f532::e4796948ec530e13 | behavior_or_behavioral_measure | p47 | support-view-v1:sha256:ebcf9c3b1603541b8c4f39df73c15bd7841b446108e612af4467bd3cddaab357 | own | legacy whole unit |
| V32 | c6 / c6#suff:brain-attitude / i::a3ab9566580a7fe4::f0daa6613a3449e9 | attitude_type_or_measure | p14,p17,p3,p7 | support-view-v1:sha256:c418a3ecf3e6b2092ecac3cb5942a44918bc78d1ac3501744912542163c1b99c | own | legacy whole unit |
| V32 | c6 / c6#suff:brain-attitude / i::a3ab9566580a7fe4::9492e632eeb1c2f9 | attitude_type_or_measure | p26 | support-view-v1:sha256:9a7bfe0eda78b9373896b39abe973c9fd8cc013978ff7eceb64a33a093539724 | own | legacy whole unit |
| V32 | c6 / c6#suff:brain-attitude / i::ac9b72f14d53f532::2f2b08aa35e6e926 | attitude_type_or_measure | p14,p17,p3,p7 | support-view-v1:sha256:829f8bec7d3719a40dee27861487358bfd219fb62634523764ae92993f14c40e | own | legacy whole unit |
| V32 | c6 / c6#suff:brain-attitude / i::ac9b72f14d53f532::9fe92674ba934ce3 | attitude_type_or_measure | p26 | support-view-v1:sha256:984172b15290aab3f5c6b521da2e9ab60a4b78c9de5be31d3bf1659e95f6dae2 | own | legacy whole unit |

These 13 remaining filled placements are inherited context and do not generate new child-own claims:
| Alias | Child / requirement / instance / role | Literal | Source IDs | Value ID | Selected view | State |
|---|---|---|---|---|---|---|
| I01 | c5 / c5#suff:brain-behavior / i::a3ab9566580a7fe4::13b13ddc969b96ae / named_brain_region_or_network | increased amygdala reactiv- ity | p40 | semantic-value-v1:sha256:0a7dc994e85291cf0e90432977ee073e5f9013866659ae2cee450560c7ee5cb3 | support-view-v1:sha256:df8772d7e46b5b99b96e26779aad3b158a50a40cbfc5ee78d948d7ba79603563 | context only; relationship not established |
| I02 | c5 / c5#suff:brain-behavior / i::a3ab9566580a7fe4::855c307939056b14 / named_brain_region_or_network | increased amygdala reactiv- ity | p40 | semantic-value-v1:sha256:0a7dc994e85291cf0e90432977ee073e5f9013866659ae2cee450560c7ee5cb3 | support-view-v1:sha256:a2f701de5f4b7f6aff2eb390129b786e8e11fc094839cb422b29400aefb27d08 | context only; relationship not established |
| I03 | c5 / c5#suff:brain-behavior / i::ac9b72f14d53f532::4a3f8a1c59aaa360 / named_brain_region_or_network | the specific amygdala response | p11 | semantic-value-v1:sha256:44c9225d5215c082f13c1a1db050e106147bd44de1d5f8d2899f7077de6641c5 | support-view-v1:sha256:bea9a7218e5df5a385918efb3ed8f3f63f018b6223b5c9dc1767f0a57b2be8be | context only; relationship not established |
| I04 | c5 / c5#suff:brain-behavior / i::ac9b72f14d53f532::e4796948ec530e13 / named_brain_region_or_network | the specific amygdala response | p11 | semantic-value-v1:sha256:44c9225d5215c082f13c1a1db050e106147bd44de1d5f8d2899f7077de6641c5 | support-view-v1:sha256:1e293e9dc9ba5929cb4ef4eb909dce5451fbdb3313f079c9c9180f378bcc1103 | context only; relationship not established |
| I05 | c6 / c6#suff:brain-attitude / i::a3ab9566580a7fe4::f0daa6613a3449e9 / named_brain_region_or_network | increased amygdala reactiv- ity | p40 | semantic-value-v1:sha256:52413dc40ec36e20e42178250a94fc2b9093082f117e34e071e294fe6c412881 | support-view-v1:sha256:2cb90d01ad4315d5a57c7d7d912d8ef734ac6e9575cf54345be3801673c6598e | context only; relationship not established |
| I06 | c6 / c6#suff:brain-attitude / i::a3ab9566580a7fe4::9492e632eeb1c2f9 / named_brain_region_or_network | increased amygdala reactiv- ity | p40 | semantic-value-v1:sha256:52413dc40ec36e20e42178250a94fc2b9093082f117e34e071e294fe6c412881 | support-view-v1:sha256:27401571fe13ec02603e9a478628294785195b16dc79bb6e04c6a0fb0d96ace2 | context only; relationship not established |
| I07 | c6 / c6#suff:brain-attitude / i::ac9b72f14d53f532::2f2b08aa35e6e926 / named_brain_region_or_network | the specific amygdala response | p11 | semantic-value-v1:sha256:545fe80f07f215c6e83be36b385f5aed65fef8aff5de50c1e1eb259d5a8c0418 | support-view-v1:sha256:4f76233f5136c42768f71947bfd9f4b68fe7da1e91648d79195104af12aece28 | context only; relationship not established |
| I08 | c6 / c6#suff:brain-attitude / i::ac9b72f14d53f532::9fe92674ba934ce3 / named_brain_region_or_network | the specific amygdala response | p11 | semantic-value-v1:sha256:545fe80f07f215c6e83be36b385f5aed65fef8aff5de50c1e1eb259d5a8c0418 | support-view-v1:sha256:8114164756fef1f8a7a65ea9768d1305aa49745f75840972126c23b17171658a | context only; relationship not established |
| I09 | c9 / c9#suff:trait-scale-pairing / U23::24d132203292cebb / individual_difference_trait_or_construct | attractiveness | p41 | semantic-value-v1:sha256:968f35cf846701778a656d8aa296e2c8d773292f33dff695982947379aa7182b | support-view-v1:sha256:83f415412aad1a4d2c083ae7958cf9d5ba5bf8af2790f6baa4e19ecca731149f | context only; relationship not established |
| I10 | c9 / c9#suff:trait-scale-pairing / U23::50b0d4004f2f502f / individual_difference_trait_or_construct | anger | p41 | semantic-value-v1:sha256:e54608a6fd58d79fc55e79902811212915cb12aa784dbb8ca1b1688c6632ec4b | support-view-v1:sha256:9654df45d8f194962278166bd2dfba9ad98dacec951e6eef0867c32072fdeff3 | context only; relationship not established |
| I11 | c9 / c9#suff:trait-scale-pairing / U23::8d7156b76bf6a6f7 / individual_difference_trait_or_construct | trustworthiness | p41 | semantic-value-v1:sha256:3c491f52c5823091d276584f18d0ada60d3fcfa697677a772f8fcbebd84ec96c | support-view-v1:sha256:dd721f6e0ff194b83a3d7d7065d722b96687e74da22d0f8173f92b5db922ec32 | context only; relationship not established |
| I12 | c9 / c9#suff:trait-scale-pairing / U23::910466e6604581fa / individual_difference_trait_or_construct | threateningness | p41 | semantic-value-v1:sha256:5e96ceebc803f2dd058ca8648e3cd353c6739a21df033f1cd22ffd7d395c063a | support-view-v1:sha256:08df66e653961b1d9e9a8cca98a9a7d3c37535ac016ef111463932d15f796c5f | context only; relationship not established |
| I13 | c9 / c9#suff:trait-scale-pairing / U23::f6027eb43b85593c / individual_difference_trait_or_construct | dominance | p41 | semantic-value-v1:sha256:8670f0698d828d77952c194814c7bd7810b19b43606a4ccbe00e8d71d4ecc5f5 | support-view-v1:sha256:cadfaf0a0165e219e03dd27d8fcd59b4d094ee17ae1ac30bf39ad6988e1efde7 | context only; relationship not established |

Hadza's two source paths and Explicit Bias Questionnaire's four placements are retained above.
Missing roles outside these 51 placements remain missing diagnostics; c10 gains no bias evidence,
c12 gains none, and inherited c9 traits gain no scale or relationship proof.

## D23. Exact preregistered nine-node plan-v5 states

The map, all 13 requirement states, 48 recovery targets, candidates, guards, proof assignments,
direction/effect observations and scientific claims are unchanged. Plan status is explicitly
revised where v4 confused unavailable presentation with absence of established science.

| Node | Legacy plan-v4 | Future plan-v5 | Exact reason |
|---|---|---|---|
| 1 | not_established | partial | c1 requested neural finding established; completion proof valid; selected source referentially restricted |
| 2 | not_established | partial | One behavioral relation/finding established; requested-construct display restriction |
| 3 | answered | answered | Attitude finding display supported; implicit null and explicit positive each have their own p36 category receipt |
| 4 | not_established | partial | Named-region relations established; referential/prior-source display restrictions |
| 4A | not_established | not_established | Completed role assignments do not establish required I1 brain-behavior relation; no reportable partial component passes display |
| 4B | partial | partial | Instrument/name component reportable; brain-attitude relation unestablished; c6 explicit category display restricted, implicit absent |
| 5 | not_established | partial | Five c8 trait relations established but stimulus-rating display restriction; c9 scale pairing still incomplete |
| 6 | not_established | not_established | Names alone do not establish culture-with-bias-evidence target; no displayable partial component; c11 absent |
| 7 | not_established | not_established | No intervention/effect relation established; c12 missing |

These four status changes are intentional **plan-only** consequences of D12, not a new sufficiency
semantics. Do not promise unchanged nine-node statuses or byte-identical Layer 1. No new scientific
finding sentence is licensed by them. "Partial" here explicitly signals established evidence that
cannot yet be stated under the display rules, or an actually reportable part; it does not assert the
answer's missing relation. c5/c6 completion vs I1 distinctions are preserved.

Node 3 category facet: report_state=answered; display covered categories=[explicit,implicit];
scientific_goal_state=incomplete; implicit goal=unestablished/reported_finding=null_finding;
explicit goal=established/reported_finding=positive_finding. Both cite their separately authorized
p36 paths. The category recovery obligation persists. This is truthful reporting, not positive
presence inferred from a null or a claim that all requirements are filled.
The p8-only counterfactual is retained in I4-4A: without authorized observation coverage node 3
would be partial with a display restriction, never a false scientific-absence disclosure.

## D24. Closed profile fixture and characterization

Exact future profile name: **v8-layerc-v2-plan-v5**.
For the inspected fixture, canonical map SHA-256 is
e1c6d1027c96098dce96b7c86ee9259d1c50e379845c1d9bb3adeb62ba00b8cf;
canonical sealed proposition-index SHA-256 is
c33b1aab85ff01a38522827a41bc62cab5e378444291b89ca425c683a783d6f3;
sealed ledger file SHA-256 is
a70409e8f5a0937f414c73c4796b293c6c1a9ef3b31c7fc83bbfa61794c6bd5d.
These are separate identities from the combined characterization replay hash.
Input fields bind:
sufficiency identity {status:supported_noncurrent,version:sufficiency-semantics-v8};
map canonical SHA-256; sealed artifact byte SHA-256 and canonical proposition-index SHA-256;
authored contract/overlay canonical identities; optional context receipt manifest hash;
containment/direction semantics exactly v8; producer authorization identity/digest.
Do not substitute a baseline's historical ledger hash for a rebuilt ledger identity.

Exact output schema profile:
layerc-validated-projection-v1; semantic-value-v1; value-coverage-v1;
category-observation-ref-v1; display-envelope-v1; parent-claim-v2;
claim-evidence-v1; relation-unit-v2; parent-synthesis-v2; answer-plan-step2-v5.
Projection/claims/receipts/plan/output manifest record their actual body digests.
Input profile authorization is not circular: input digest binds versions+inputs; output manifest
binds resulting projection/ledger/plan hashes. Replay checks both and rejects incompatible profiles,
even if an attacker/replayer recomputes a digest over the wrong version tuple.

Characterization name: **v8-legacy-layerc-plan-v4-characterization**.
It preserves the accepted combined v8 hash printed above, including known legacy Layer C defects.
It is not historical map semantics and not unrestricted v8 answer qualification.
New profile receives a separate independent baseline only after I4-4D qualification.
Historical v4-v7 keep the exact legacy claim/construction/plan-v4 paths and bytes.
No >=, "latest", v8 auto-promotion or inferred plan version; reject unknown pairings.

## D25. Additional plan-v5 qualification invariants

1. Every rendered semantic value resolves to its own authorized coverage receipt.
2. Every citation belongs to that value/path; source identity and own/inherited labeling are exact.
3. No member borrows another's citation except through an independently scoped structured reference.
4. Every relational claim references an applicable stored proof for exactly its tuple/purpose.
5. Direction/effect conclusions reference aligned observation paths; conflicts retain all paths.
6. Excluded/attachment-ambiguous candidate metadata cannot be positive support or an eligible view.
7. Inherited evidence is never relabeled own; child relation requires child proof.
8. Display envelope contains the evidence span and contributes zero extra semantic support.
9. No claim-wide union, substring match, rendered prose or first-source choice establishes coverage.
10. Shuffling paths/registries preserves semantic values/claims/states; receipts canonicalize sets.
11. Unsupported mapping cannot render silently; null/unlocated/malformed refs get typed failures.
12. Null category reporting cannot establish positive presence or suppress category recovery.
13. Same label in distinct authored scopes remains separately keyed.
14. Legacy v4-v7 bytes and explicit noncurrent identity/authorization remain exact.
15. Missing context cannot invent a joint quote, PID or citation; mismatched supplied context fails.
16. Goal state and display state cannot overwrite one another; all display-only status changes
    carry exact limitation refs and cannot generate "no scientific evidence" assertions.
17. Duplicate physical paths do not inflate evidence; distinct physical sources with identical
    text remain distinct; display dedup leaves all member receipts intact.
18. Input deep equality and forbidden-call/AST checks prove no selector, policy, attribution,
    direction/effect classifier, retrieval/model or production-map mutation occurs.
19. Exactly 51 filled placements/32 values/17 claim scopes accounted for in the real fixture;
    exact node table, implicit null and explicit p8/p36 split are checked individually.
20. Existing 33 invariants remain necessary; passing them alone is not qualification.

## D26. Synthetic value-coverage matrix

Each expectation is scoped to an otherwise valid authored single-target facet unless two targets
are named. E means upstream target establishment, not a new inference by this oracle.
The table is a preregistered design fixture, not results from a new implementation.

| Case | Scientific establishment | Coverage / renderability / citation | Facet consequence |
|---|---|---|---|
| A selected A, its source contains A and passes display | Established A | A's selected path supported; cite that path | answered |
| B selected A fails display rule | Established A | restricted; evidence-only citation, no primary sentence | partial + display limitation |
| C B + authorized positive observation A | Established A | Observation A supplies display/citation; selected support remains | answered |
| D C but observation B | Established A | A stays restricted; no B citation donation | partial |
| E source mentions A but structured B | Established A | Same as D; substring not authority | partial |
| F positive category observation A, role A missing | No new establishment | Inconsistent current producer record rejected or unattached diagnostic; no positive display | no manufactured answered state |
| G A/B, only A covered | Both established | A supported, B restricted/unavailable; citations separate | partial |
| H A/B, shared source, distinct authorized observations | Both established (or typed null as stored) | Separate receipts may share physical citation | answered for reporting; goals preserved |
| I shared text contains both, only A observation | B not established by text | A only; no B coverage | partial if B required |
| J A, two independent sources | Established A | One value, both paths; own citations retained | answered if at least one passes |
| K same label, distinct category scopes | Separate upstream facts | Separate IDs/receipts; one cannot cover the other | Evaluate each scoped obligation |
| L all evidence excluded | No positive target | Diagnostics only; no scientific finding citation | not_established, unless other independent evidence exists |
| M attachment-ambiguous only | Not established; ambiguity retained | No positive render; diagnostics only | not_established with uncertainty |
| N legacy selected support | Frozen legacy establishment | Legacy scoped association, no retroactive candidate default | answered if display passes, otherwise partial for an established target |
| O established candidate unlocated | Frozen establishment retained | unavailable; no invented span/citation | partial |
| P wrapper adds authentic adjacent period | Unchanged | supported if other checks pass; evidence span unchanged | unchanged |
| Q wrapper adds second assertion | Unchanged | Reject envelope; exact assertion may still display, else restricted | never gain coverage from added assertion |
| R valid link-only relation, context text missing | Narrow stored relation established | Operand/proof rendering allowed, joint context quote unavailable; own operand citations only | answered only for narrow relation; partial if stronger prose/quote required |

Domain-neutral unchanged category tests exercise positive/null/mention/unknown, order independence,
sibling scope, absent observations and recovery behavior. The 12 observation cases and 14 envelope
cases above close permissions independently of scientific vocabulary. Proposed receipt/value/profile
mutation tests must be implemented in I4-4C; these matrices are not claimed as a passing new-rule suite.

## D27–D31. Scientific boundary, implementation split and stop

**D27:** no upstream scientific semantic change required. Authorized category-observation references
project an existing satisfaction input. Null reporting is constrained to a recorded null and does not
change established_presence. The 32-value normalization and typed display states do not change
sufficiency, cardinality, recovery or evidence ownership. Do not alter observations to improve display.

**D28:** sufficiency-semantics-v8 remains sufficient map semantics. A reference-only detached
projection needs new Layer C schema/profile identity, not sufficiency v9. If implementation needs to
collect a new observation, change polarity, choose a different candidate/proof, infer ownership or
change category completion, stop: that exceeds this design and needs a separately authorized increment.

**D29 exact split:**

- I4-4C: pure validation/reference/value-coverage substrate, without production consumer activation.
  One Layer A/B-owned entry point, exact frozen schemas, metadata/category/link indices, pure value
  adapters, typed source permissions, minimal display-envelope locator validation and immutable receipts.
  Unit/property/mutation tests and offline fixture projection; no ParentClaims/AnswerPlan imports of
  the new adapter, no routing/default/version-constant change, no new rendered prose.
- I4-4D: atomic parent-claim-v2 + parent-synthesis-v2 + plan-v5 integration for explicitly authorized
  noncurrent v8. Update proof/value/citation/observation/coverage transport, node/facet axes,
  display restriction disclosures and minimal render adapters together. Full offline qualification,
  real per-member/nine-node fixtures and separate profile baseline. Legacy callers either have a
  correct v2 adapter or reject it; they may not reinterpret flat support unions.
- I4-4E: tiny separate explicit promotion decision only after all gates pass. Nothing here authorizes
  that promotion. Do not combine C+D for convenience.

**D30 READY for I4-4C**, with this report's exact schemas, authority split, real expectations and fail
behavior as its acceptance contract. NOT an unconditional READY for I4-4D or promotion:
the substrate must first pass the new validation and coverage fixtures. No unresolved A/B/C branch
remains; option B and node 3 answered are fixed with the explicit implicit-null qualification.

**D31 I4-4C scope boundaries:** new pure module(s) and targeted offline tests/fixtures only; read existing
map and sealed artifacts; produce detached immutable projection; verify real counts/IDs/coverage;
no classification/selection/recovery calls; no evidence repairs; no application path activation;
no ParentClaim/AnswerPlan/rendering edits; no PLAN_VERSION/default bump. It may validate literal wrappers
and source permission records but must not add scientific values or user-facing text.
Historical replay hashes and current/noncurrent identity must remain exact.

STOP after I4-4B. No I4-4C implementation, production behavior change, v8 promotion, PLAN_VERSION bump,
category/role-state/recovery change, candidate collection/attribution/policy/guard change,
same_local_assertion registration, claim-goal/authority-veto work, I2-3, or live E2E occurred.
