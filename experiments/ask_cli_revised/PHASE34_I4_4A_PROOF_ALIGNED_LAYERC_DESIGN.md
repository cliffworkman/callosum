# Phase 34 / I4-4A — proof-aligned Layer C design audit

Date: 2026-10-10. Planning and read-only analysis; no production implementation.

Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
Verified clean starting HEAD: `d4cb7ff1cb7898f95557fb09df6d3f00b47cd9d5`.
HEAD remains unchanged. The only tracked changes from this audit are this report and the lineage append.
Current/default is still sufficiency-semantics-v7. V8 remains supported_noncurrent.

**Decision: NOT READY for a single I4-4 implementation.** The proof-aligned architecture is
specified below, but the real-data audit finds an unresolved boundary between selected legacy
category support, recorded category observations and display coverage. A reference-only transport
projection preserves 17 claims, nine node states and Layer 1; a stricter per-value evidence
projection exposes one existing cross-value citation/coverage substitution. The former is not
evidence that a fully corrected implementation preserves every answer state.

Recommend **I4-4B — Layer C value, category-coverage and validation contract closure
(planning/read-only)** before implementation. Then implement the shared validation/reference
substrate and the atomic ParentClaim/AnswerPlan integration as separately bounded increments.
Promotion is a separate final increment. Do not weaken proof alignment to force real-map parity.

## Evidence, reproducibility and limits

All ten answer_plan production Python files were read: __init__, overlay, relations, classify,
plan, step2, text, render, replay and source_metadata. The ledger, its production callers in
e2e/plan/replay/parent_synthesis_audit, and its realization/render/audit consumers were inspected.
The existing overlay is presentation/decomposition input, not scientific evidence.

Offline verification used the preserved I4-2a replay harness with frozen model nominations and
the accepted ownership-context builder. No nominations were regenerated. Network connections
were denied in the replay controls. No external search, library retrieval, model call, NLI call
or live E2E occurred. No full suite was necessary.

```text
pytest experiments/ask_cli_revised/test_i4_3c_replay.py
       experiments/ask_cli_revised/test_i4_3c_witness.py
       -q --tb=short -p i4_offline
```

The launcher loads the existing .local/i4-2b3 offline plugin. **75 passed**. These include the exact
historical/v8 hash assertions, the known Layer C exception, legacy parity disagreement and stale
operand IDs, both same-P2 signs, inherited alternatives and malformed-reference controls.

| Version | Exact combined replay SHA-256 |
|---|---|
| v4 | `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a` |
| v5 | `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77` |
| v6 | `dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be` |
| v7 | `04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72` |
| v8 | `1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0` |

Read-only scratch receipts are under .local/i4-4a: baseline-controls.log, inventory.log,
current.json, oracle.py/prospective.log/prospective.json, strict_probe.py/strict-probe.log and
synthetic.py/synthetic-results.json and strict-counterfactual.log/json. These are ignored audit scratch, not new production modules,
committed tests or a new replay baseline. The first inventory serialization attempt rejected a
Python set; it was rerun using the accepted replay serializer. A scratch link probe initially used
an unrecognized designator, then used the existing frozen XYZ fixture. No production behavior or
frozen expectation was changed.

The prospective oracle consumes existing support-view/proof references; it does not enumerate
candidate_supports, perform policy/attribution or search for new compatible assignments.
Its first stage deliberately preserves current display decisions. The strict probe independently
checks those decisions against each value's selected support IDs. Synthetic grouping expectations
are manually specified design rules exercised over unchanged v8 outputs, not a passing future
Layer C implementation suite.

## C1. Existing ParentClaim families and consumers

There are exactly four CLAIM_KINDS, not separate null, propagated or gap claim kinds.
All claim IDs currently hash the entire finalized payload (16 hex digits), including provenance,
support IDs, instance keys, values, model dependency and summaries. List order is canonicalized
by the builder; identity nevertheless changes when support or representative content changes.

| Family / producer in parent_synthesis_ledger.py | Existence, value and identity | Evidence and representative dependence | Observation / proof survival |
|---|---|---|---|
| role_value; _atomic_candidate:274, _role_value_claim:368 | Filled own completion role when the instance is not emitted as a 2+-own relational claim. Semantic fold uses kind, role, category, representative PID and exact_text. | Value is binding.exact_text; PID is binding.proposition_id; support is representative PID plus provenance.supporting_proposition_ids. Resolves representative PID against sealed ledger. | Does not consume views, gate receipts or proofs. |
| category_list; _build_atomic_claims:326, _category_list_claim:386 | Within one requirement/role, 2+ distinct (PID,text) members under exists/open_list/for_each_discovered_instance/all_requested_categories. at_least_n is excluded. Across-requirement standalone folds are separate. | Each member uses the atomic representative. List admissible IDs are member support unions. Same printed value from different PIDs can remain two members. | Does not preserve member-specific proof receipts. |
| relational; _accumulate_relational:225 | Complete instance with >=2 own completion roles. Key is sorted own (role,representative PID,exact_text), not required-role I1 identity. | Calls unversioned relationship_witness_support_ids; raises if empty. Values use representative IDs/text. Dedup merges witness IDs and placements. | Ignores stored joint_grounding and witness_proofs. Completion relationship is distinct from I1. |
| direction_or_effectiveness; :414 | One summary record per requirement/field when observed/conflicted complete instances exist. Empty values list; summary provides content. | Direction citation IDs come from observations passing counts_toward_relation_direction; effectiveness unfiltered. Model flags come from own bindings. | Consumes summaries and observation PIDs, drops observation IDs/alignment/proof paths. Carries both conflict flags. |
| UnresolvedGap; build_gap_report:478 | One final recovery target; validates requirement existence. Not a ParentClaim. | Target fields only; no invented citation. | No candidate diagnostics today. |
| ResolvedEmptyOutcome; :545 | Completed terminal scoped search plus is_zero_evidence_terminal. Not a ParentClaim and not a literature-null assertion. | No source support or candidate inference. | Remains a separate search-outcome record. |
| Inherited/propagated operands | No independent claim family. parent_of argument is ignored. Parent-context roles are excluded from own_evidence_roles. | Child may emit its own atomic facts; parent evidence never automatically becomes child-owned. Current ledger cannot represent an inherited-only contribution to a relational tuple. | Child I1 proofs can support such a relation in the future; parent origin proof is not child authority. |

Real v8 ledger: **nine relational, two role_value, six category_list, zero direction/effect
claims = 17**. The nine relational claims include c1, whose required-role count is one plus an
alternative role; it has completion proofs but no I1 result. Treating all relations as I1-only
would incorrectly remove this real claim.

Production ingress/egress inventory:

- e2e._parent_synthesis_outputs builds claims/gaps/resolved outcomes, realizes, renders and records them.
  Current/default routing stays v7. Future schema dispatch must reach the entire caller chain.
- answer_plan.plan.build_plan and answer_plan.replay.main rebuild claims; replay also compares
  their old IDs with the preserved Phase-28 ledger.
- parent_synthesis.authorized_claim_text/build_prompt and claim_value_reasons consume values;
  _passage_units/source_passage_reasons/_screen_candidates consume whole quotes from admissible IDs.
  _segment mechanically copies citation IDs. No call to this model/NLI path was made in this audit.
- parent_synthesis_render literal templates consume values/summaries; format_citations consumes
  admissible IDs; _locator exposes whole quotes. construction_record is parent-synthesis-v1.
- parent_synthesis_audit rederives claims and hashes, rechecks citations, screens and terminality.
  It has no proof-aware schema dispatch today.
- Tests characterize these consumers; they are not additional runtime authorities.

Future claim receipts alone cannot fix whole-quote realization/NLI scope. Either add explicit
v2 adapters for these consumers during eventual integration or reject v2 at their entry points.
Do not let an old renderer or screen silently interpret a v2 receipt as permission to use a
representative or every word in its containing proposition.

## C2. AnswerPlan consumer inventory

A = semantic decision; B = evidence/citation selection; C = human-facing value/text projection;
D = consistency validation; E = display-only compatibility. Multiple labels are intentional.

| File / function group | Current use | Classes / v8 consequence |
|---|---|---|
| relations.relation_units:59 | Required-role representative text, PID and support; shared rw.witness_instance; engine completeness; stored metadata parity. | A/B/C/D. Current v8 call finalizes/reselects proofs and still emits stale representative operands. Replace with stored-proof validation + tuple adapter. |
| relations._stored_metadata_check:29 | flag, IDs and failure_reason compared with newly derived result. | D. Validate stored proof references/receipts instead; no representative parity. |
| requirement_relation_status, claim_witnessed, unit_for | Best requirement status; match by instance/requirement; unit_for returns first match. | A/B. Explicit claim-to-unit/path refs, not first matching instance. Include placement owner to avoid accidental cross-child collisions. |
| classify.build_generic_map:40 | Filled achieved-outcome binding.exact_text used to detect generic passage reuse. | A. Selected assertion/slot references replace representative authority; no new support-admissibility rule. |
| evaluate_sentence:64 | Whole-quote caption, lexical attribution, completeness, construct and stimulus tests; sentence edits. | A/B/C. Preserve display-fidelity tests separately from upstream policy. Candidate attribution metadata must not be overwritten by lexical reclassification of another scope. |
| _candidates_containing:99 | Searches every sentence of unioned claim admissible PIDs for value text. | B/C. Per-value/per-proof render source refs; no cross-member evidence substitution. |
| _evaluate_relational:147 | claim_witnessed, representative values contained in one sentence; first passing render. | A/B/C. Validate selected tuple; deterministic display among equivalent paths only, retain all paths. |
| _evaluate_values:173 | First passing source per value; category enumeration; normalized-text dedup. | A/B/C. Per-value evidence association and explicit coverage refs needed. |
| _evaluate_direction:258, _operand_surfaces | Both direction and effectiveness records enter this branch; rescans whole quote and calls direction_target with representative operands. | A/B/C. Separate direction/effect adapters over aligned observations; no classifier rerun or new effectiveness I1 gate. |
| plan.build_plan:62 | Builds claims, relation units, generic map, evaluations, facets; PLAN_VERSION; inputs/hash. | A/B/C/D. Explicit semantics profile selects both claim and plan paths. |
| _facet_for/_roles_of/_build_facets | Claim roles, requirement kind, required roles, quantifier and relation statuses. | A. Stable semantic-slot/tuple refs, retain existing quantifiers. |
| _instance_bindings:173; _covered_roles:226; _covered_categories:238; _coverage_pool | Representative text occurrence and value strings establish rendered coverage; duplicate render can cover another facet. | A, not E despite the “never to create content” comment. Replace with validated slot/category coverage receipts. |
| _dedupe_node:186 | Same normalized sentence collapses claims; substring subsumption by relation; merges values but not full evidence paths. | A/B/C. Display merging cannot drop sources or assert semantic equivalence by text alone. |
| _facet_state/_build_node/_parent_plan | Answered/partial/not_established/searched_empty; statements; allowed statement IDs; parent counts. | A/C. Map state is not display coverage. Existing rules remain, corrected inputs may change a status. |
| _reasons/_disclosure_items | Fixed disclosures from evaluation reasons/state. | C. Keep scientific status distinct from display restrictions; do not invent I2-3 wording here. |
| _set_aside_by_node | Whole-quote records, dedup by normalized text. | B/C. Preserve physical sources and selected locators; separate excluded-support diagnostics. |
| _statement_record/_claim_role_record/_disagreements | Whitelists discard new references; stores representative-derived metadata. | B/C/D/E. V8 schema must explicitly carry receipts through every projection. |
| step2.paper_of/finalize | First statement PID determines paper; first PID provides Layer-2 quote; scans paper spans for limitations. | A/B/C. Source-specific paths, not arbitrary first evidence source. Context limitations are not positive role supports. |
| step2.discover_limitations/_promotion/_promoted_statement | Attribution heuristics, same-paper lexical association, independent sealed-span qualification statements. | A/B/C. Existing qualification channel remains separately typed; cannot supply missing claim evidence or alter proof truth. |
| step2._ground_node/_definition_record | Same-paper definition lookup, first-use acronym edits. | B/C/E. Keep separate definition-span refs and reversible edits; no new role binding. |
| step2._consolidate/_limitation_view | Fixed disclosures and audit details. | C/E. Preserve states while carrying receipt references. |
| text split/contains/normalization and display transforms | Scope and sentence matching; hyphen edits, labels, definitions. | B/C/D/E. Helpers may validate/display selected scope; may not select candidate evidence. |
| text attribution_kind/speculative_or_aim/is_caption/construct_direct/stimulus_rating | Current presentation classifications over whole passages. | A/C. Legacy behavior is not general v8 support policy or ownership authority. |
| render.citation_map/_statement_keys/_markers/_passage_key | prop_ids -> paper/page/span; first appearance determines marker. Span-only limitations have a separate path. | B/E. Proof-aligned citation refs supply IDs. Numbering can remain a display choice. |
| render_layer1/2/3 | Statements/disclosures; whole support passages; identifiers/version/audit. | C/E. Minimal schema adapters only, no style redesign. |
| render.invariant_report:266 | Passage containment, source labels, coverage and question-specific historical acceptance checks. | D. Existing 33 checks are necessary but do not test proof alignment; add generic receipt tests later. |
| replay.main:129 | Reads map identity, authorizes, builds plan twice, renders, compares legacy ledger IDs. | A/D/B. Bind actual claim/plan semantics and actual rebuilt ledger; preserve historical reference separately. |
| replay.verify_replay_authorization:113 | Digest, exact status/version, applied containment/direction. No plan version binding today. | D. Extend v8 authorization profile without relaxing I4-3C0 equality. |
| overlay | Authored decomposition, phrases, scopes, hashes and validation. | C/D. Not candidate or ownership authority. |
| source_metadata | Optional read-only library citation extract and author-date labels. | B/E. Labels resolve cited physical sources; not proof of attribution to an original external paper. No extraction was needed here. |
| __init__ | Package documentation only. | No semantic use. |

## C3–C10. Semantic values, proof grouping and observation claims

### Four distinct objects

1. **Semantic value:** the entity/category/measure or asserted finding occupying a role.
2. **Evidence text:** the selected support record's assertion slice, or its explicitly legacy scope.
3. **Classifier operand surface:** exactly the text referenced by the selected view/observation path.
   It can be an entire assertion. Layer C does not improve it or rerun a classifier with a shorter value.
4. **Citable support:** resolvable sources/locators on that path, with contextual inherited support
   separated from the source that establishes the child relation.

There is no independent value field in RoleBinding. exact_text serves different purposes by strategy.
_project_evaluated_supports chooses the first eligible assertion for compatibility; that text is not
a stable named-entity value. derive_instance_key also hashes representative PID/text. Thus proof refs
are stable at a fixed placement, but a newly rebuilt upstream map can rename forked placements when
representatives change. Layer C must not promise byte-identical reference IDs across such re-keying.
Its semantic claim ID must remain independent of representative-based instance keys.

Proposed closed value adapter:

| Input role shape | Semantic value | Evidence / operand / citation |
|---|---|---|
| Named model, lexicon, category or authored value represented by a legacy view | Exact selected literal value plus role/category identity. Keep authored category membership and available polarity separately. | Selected legacy view, its text ref and support set; never replace the value with its full quote. |
| Achieved-outcome candidate role participating with independently grounded entity/value roles | Typed evidence-slot descriptor from the RoleSpec and requirement relation contract; it is not a named entity or an invented “positive outcome” value. | Exact selected assertion/text ref remains evidence and classifier operand. Different statements are not silently made synonyms. |
| Standalone achieved-outcome finding without an independent semantic value | Literal selected assertion is the conservative asserted value. Distinct assertion texts remain distinct unless existing authored grouping explicitly equates them. | Same selected record provides evidence scope; no arbitrary first assertion. |
| Candidate-backed named-value role, unknown custom shape or inherited candidate value | Selected literal operand text, unless an explicit authored value reference already exists. | Selected view/source remain attached. Do not infer entities by NLP or role-name/domain vocabulary. |
| Unresolvable value mapping | Non-renderable structured diagnostic, not a fabricated label or representative fallback. | Keep exact evidence refs for audit. |

Using an evidence-slot descriptor preserves, for example, a named region/trait value instead of
replacing it with a full result sentence. The descriptor authorizes no extra scientific content.
For an all-evidence-role relation without a stable operand tuple, conservatively keep literal
assertion semantics separate; do not merge unrelated assertions merely because the requirement ID
is the same. The exact closed mapping/unsupported behavior needs preregistration in I4-4B.

### C4: atomic claims

Use **B (distinct semantic values)** with **A (multiple equivalent evidence paths per value)** and
preserve **C (the existing requirement-scoped list grouping)**. These are different levels:

- One eligible view: one atomic value with that evidence path.
- Multiple supports for the same explicitly identified literal value/slot: one value, all paths.
- Distinct assertions on the same PID: retain separate locators; same PID alone establishes no value equivalence.
- Eligible plus excluded: positive support only from eligible views.
- All excluded, or candidate key present with no eligible view: no positive atomic claim, no fallback.
- Legacy binding with no candidate key: consume its one Layer A/B legacy view, do not apply a new policy.
- Lists preserve member-to-evidence associations and the current list-like quantifier boundary.
  A display-distinct-value count is not a cardinality count. Do not use semantic dedup to recompute sufficiency.

### C5–C6: relational semantic key and merge/split

Proposed key:

```text
parent-claim-v2 / relational
+ authored requirement semantic scope and relation-contract identity
+ ordered (role, category identity, typed semantic value) tuple
+ relation assertion kind
```

Requirement semantic scope is supplied input, not question parsing. Preserve role order/identity;
do not treat a swapped tuple as equal. Exclude support IDs, proof IDs, discovery order, representative
PID/text, instance keys, citations and evidence receipt hashes from this semantic identity.
Include literal text when it IS the semantic value, not when it is merely an evidence assertion.
Do not deduplicate across requirement scopes without an explicit authored equivalence.

For complete instances, consume successful completion_joint proofs for the engine's own-role tuple.
Separately consume successful i1_relation_witness proofs for the required own/inherited tuple.
Merge purposes only when their semantic tuples and relation contracts agree; retain both purposes.
When tuples differ (alternatives or inherited values), represent separate relation claims/units.
A completion proof is not a fabricated I1 proof. c1 is a concrete required example of this distinction.

One proof repeated -> one path. Two valid proofs for the same tuple -> one claim/two paths.
Different values -> separate claims. Opposite direction signs -> one undirected underlying relation
plus structured conflict, not two contradictory consensus claims. Distinct physical sources stay
distinct evidence even when values and display sentences match.

### C7: inherited operands

Use the child proof's selected inherited view and semantic value; retain immediate source=inherited.
Child-owned evidence establishes the relation; parent evidence supplies context. Store origin references
as provenance only. Never copy a parent proof as child authority or include inherited PIDs in the own
witness intersection. An inherited candidate's scientific assertion_relation does not change this rule.

### C8: link-only proofs

A stored successful completion proof with shared_designator establishes the corresponding completion
relation even with empty witness_ids. Record establishment_basis=completion_joint/shared_designator,
I1 status separately, selected operand source refs and context_sha256/designators. Do not manufacture
a proposition witness or relabel I1 as true.

Selected operand records may resolve to citable propositions; label these as operand/context support,
not as one joint proposition. The proof stores a digest of attachment_pieces, not a recoverable
context passage. Without separately supplied hash-matching context, structured representation is
possible but a self-contained context citation/verbatim relationship sentence is not. Set a display
limitation; do not fabricate a source. This is not grounds to discard the valid proof.

### C9: direction

Consume evidence_alignment observation IDs and their exact selected paths. Copy sign, target,
relation_eligible and existing summary; never call direction_target again. A requirement summary
is scoped to that requirement, not automatically to every distinct semantic tuple within it.
Attach observations to their path's tuple. If a requirement spans different tuples, retain the
requirement summary plus tuple-scoped observation references; do not broadcast a consensus to a
tuple with no contributing observation.

Same-P2 positive/negative fixture: relation established, two observations and both path sets,
consensus=null, observed_values=[], within-instance conflict=true, across-instance heterogeneity=false.
Use a direction_or_effectiveness summary record with no positive/negative consensus assertion,
linked to the underlying relation. No new conflict prose policy is needed.

### C10: effectiveness

Use aligned conclusion/scope/local flags and existing summary. No I1 gate. The same complete
instance's supported/not_supported observations yield null consensus and within-instance conflict.
Important existing boundary: summarize_observations only includes COMPLETE instances. The accepted
I4-3C local effectiveness fixture with a missing second role retains both observations but has no
complete-instance summary contribution. A complete one-role companion produces the conflict summary.
Preserve both behaviors; “no I1 gate” does not mean “ignore instance completeness.”

## C11–C18. Receipts, identity, validation and data flow

### C11: excluded evidence

Choose **B: a separate AnswerPlan evidence-diagnostics surface**, backed by the input map.
No extra positive ParentClaims and no change to recovery/gap algorithms. Distinguish:
no grounded candidate; retained but guard-excluded; policy-excluded; attachment uncertain;
eligible evidence with no compatible relation; and display restrictions. Exclusions and uncertainty
remain orthogonal. I2-3 owns wording, not preservation of these facts.

### C12: proposed claim-evidence-v1

```json
{
  "schema_version": "claim-evidence-v1",
  "claim_id": "claim-v2:sha256:<semantic-key-hash>",
  "receipt_id": "claim-evidence-v1:sha256:<receipt-body-hash>",
  "input_refs": {"map_sha256": "...", "sealed_sha256": "..."},
  "paths": [{
    "placement_ref": {"owner_id": "...", "requirement_id": "...", "instance_key": "..."},
    "purpose": "atomic_support | completion_joint | i1_relation_witness | observation",
    "proof_refs": ["..."],
    "observation_refs": ["..."],
    "value_support": [{"value_id": "...", "support_view_refs": ["..."]}],
    "operand_text_refs": {"role": {"support_ref": "...", "field": "exact_text", "sha256": "..."}},
    "evidence_locator_refs": ["..."],
    "eligibility_receipt_refs": ["..."],
    "candidate_metadata_refs": ["..."],
    "own_witness_proposition_ids": ["..."],
    "context_support_proposition_ids": ["..."]
  }],
  "citation_proposition_ids": ["..."],
  "diagnostic_refs": ["..."]
}
```

This is a normative field proposal, not existing JSON. owner_id is a generic placement adapter to
v8 child_id, not a rename of any map field. Atomic paths have no fabricated proof_ref; observations
retain all successful paths. IDs use full SHA-256 over canonical UTF-8 sorted JSON, normalized sets,
explicit null/empty distinctions and deterministic path ordering. No full bundle/candidate duplication.

Candidate metadata is not fully recoverable from current support_records alone: those records retain
candidate_payload_sha256, while the full attribution proof and evidence triple remain on candidate
records. Excluded records have no eligible view linking them to a receipt. The future input resolver
must resolve the existing payload hash plus placement to the original immutable candidate object.
This is exact identity resolution by the Layer A/B owner, not eligibility filtering or selection.
Ambiguous hash/payload matches with conflicting content fail. Layer C receives references/read-only
metadata, never candidate arrays. Do not pretend the current candidate_ref already solves this.

A helper may build a detached metadata index from the existing immutable map without emitting new
fields into v8 maps or changing IDs. Its API and tests belong in the prerequisite contract closure.
Do not add fields to accepted v8 support/proof schemas merely for downstream convenience.

### C13: identity and dedup

Use stable semantic claim ID + separately changing evidence receipt. Adding support to the same
claim changes only receipt/ledger artifact hash. Claim identity is run/contract scoped; never infer
cross-study entity equivalence. Keep the historical 16-hex complete-payload claim IDs unchanged
for v4-v7. New category-list identity uses the authored grouping scope and canonical semantic members;
physical member/evidence occurrences remain separately addressable.

Merging display text cannot erase proof paths, attribution differences or source identity.
A source-specific wording choice may require a render partition even when the underlying semantic
claim is shared. Never combine current-document and external evidence into an undifferentiated
“This study found” statement.

### C14: citations

Truth precedes citation projection. For same_proposition relations, own witness IDs come from the
selected proof joins; inherited operand citations are separately labeled. Atomic citations resolve
their selected support views; direction/effect citations resolve their aligned observation paths.
A sorted union is permitted only AFTER equivalent claim paths have independently been established.
It is a citation index, never a verifier or permission to search for another sentence.

Keep value-to-path-to-source relationships even when an outer claim exposes a convenience
citation_proposition_ids list. A source paper reporting prior work is the citable source available
here; do not invent an original external-paper citation from assertion_relation.

### C15–C17: one validation authority, two consumers

Proposed flow:

```text
explicit map identity + sealed inputs + authored role contract
 -> Layer A/B-owned read-only reference resolver and stored-output validator
 -> validated evidence projection (no candidate selection, no map writes)
 -> v8 ParentClaim value/grouping adapter + claim-evidence receipts
 -> v8 relation-unit and observation adapters
 -> explicit plan-v5 assembly, coverage and minimal rendering adapters
 -> authorization binds input identity, applied schemas and actual output hashes
```

Choose **B: validation of stored metadata**, not blind trust and not rw.witness_instance recomputation.
The current compatible_witness.validate_witness_bundle calls build_support_views; finalize_instance
also reselects I1 proofs. Neither is the requested Layer C API. Factor or add a validation-only
API under the witness owner in a later authorized increment; do not change selection output.

Validation must check:

- Map status/version and sealed/map identity; schema, placement, reference resolution and canonical hashes.
- Exact selected record/view/receipt identity against the bound input; admissible=true,
  attachment_ambiguous=false, filled outer state; check stored gates, do not run policy.
- Proof purpose, authored verifier, role participation, source, join membership, sealed verification,
  continuation and inherited containment for the STORED assignment only. Checking a selected assignment
  is validation; enumerating alternatives or constructing a new assignment is selection and forbidden.
- Completion receipt and prerequisite consistency; bypass is not a proof. Required-role I1 flag equals
  existence of valid stored I1 proofs; witness_ids equal the sorted proof-join PIDs.
- Observation hashes/scopes/path references, operand text hashes, proof/path agreement and summary
  membership. Validate existing summary arithmetic if needed; no classifier rerun.
- Claim values/path membership, proof grouping, citations and observation refs all resolve to the same
  tuple. Excluded support refs cannot be positive support. Diagnostics may reference exclusions.
- No unknown IDs, duplicate conflicting bodies, stale metadata or silently rebuilt missing receipts.
  Raise a typed integrity error and withhold the v8 plan; keep diagnostic detail separately.

Canonical hashes alone do not prove authenticity. Bind them to the supplied map/sealed artifact and
authorized producer receipt. A validation-only consumer proves stored-path soundness and consistency;
it cannot prove that no successful assignment was omitted without recomputing the selector. Exhaustive
selection remains covered by Layer A/B qualification and input identity. Do not claim otherwise.

### C18: relation-unit-v2

One unit per placement + distinct semantic tuple, with explicit establishment basis. Fields:

- schema/version, placement, semantic_relation_key, typed semantic operands and value IDs;
- engine_complete, required roles, completion status/proof refs, I1 status/proof refs,
  relation_witnessed and witness_ids with unchanged I1 meaning;
- semantic status (established / unestablished / incomplete / invalid) and renderability separately;
- each operand's selected support-view refs, exact operand_text_refs, immediate own/inherited source;
- claim-evidence receipt refs, own witness citations and contextual citations;
- direction/effect observation refs and summaries, attribution/eligibility/diagnostic refs.

Do not copy bundles. A link-established relation can be established with I1=false and no witness IDs.
A completion-only c1 tuple has I1=not_applicable. Preserve the 40 current required-role units as a
compatibility projection and add one completion-only unit in the real corpus (41 semantic units total).
Do not overload the old “witnessed” enum to falsely assert I1 for either case.

## C19–C22. Versioning and replay

**C19.** Recommend **parent-claim-v2**, **claim-evidence-v1**, **relation-unit-v2** and a v8-only
**parent-synthesis-v2** construction envelope. Existing bare claims have no schema field;
parent-synthesis-v1 is an envelope identity, not a sufficient claim schema selector.

**C20.** Recommend **answer-plan-step2-v5** for the candidate-aware plan path. Keep plan-v4 as the current v7
path until separate promotion. V4 plan semantics cannot generally consume v8: the accepted P2 control
already disproves that. Real-map success is a compatibility observation, not general qualification.

**C21.** No sufficiency-semantics-v9 is needed for Layer C projection/validation. V8 scientific map semantics
remain unchanged. If a proposed repair starts changing map collection, category selection, proof
outputs, summaries or completeness, stop and request its own semantic design; do not hide it in Layer C.

**C22.** Use a closed compatibility table, not >=, lexical version comparison or “latest”:

| Sufficiency input | Default applied Layer C profile |
|---|---|
| Explicit v4-v7 | Existing claim/envelope and plan-v4 behavior, byte exact |
| Explicit v8 with independent supported_noncurrent opt-in | Claim-v2 / envelope-v2 / plan-v5 after qualification |
| Unknown or incompatible pair | Reject |
| Historical unversioned | Existing explicit policy remains; never silently label it v8 |

Preserve the accepted I4-3C combined v8 + legacy Layer C baseline as an explicitly named
characterization profile for audit replay. Its map is not historical merely because its Layer C
profile is old. Do not overwrite its hash or falsely call it general v8 answer support.
The future qualified v8+plan-v5 combined artifact gets its own baseline keyed by BOTH semantics.

V8 replay authorization must bind exact supported_noncurrent/v8, containment/direction v8,
parent_claim_schema, parent construction schema, answer_plan_version and the actual rebuilt ledger
hash. Preserve the old Phase-28 ledger hash as historical input, not the hash of the new ledger.
Authorization digest binds these fields; the plan records authorization/input identities and
applied schemas; output manifest binds plan hash without a circular dependency.
Reject rehashed authorizations with a mismatched profile, not only stale digests.
Do not relax I4-3C0 status/version checks.

No constant, schema, routing table or authorization code changed in this audit.

## C23. Real v8 prospective diff — two projections, not one claimed pass

The accepted replay contains 46 instances, 51 eligible support views, 56 support records,
11 completion proofs, nine I1 proofs and eight witnessed required-role instances.
Five retained exclusions have no eligible support view. No map mutation is proposed.

### Reference-transport oracle (display decisions held fixed)

| Measure | Accepted v8 + legacy Layer C | Proposed transport projection |
|---|---:|---:|
| Claims / families | 17; 9 relational, 2 role_value, 6 category_list | Same |
| Semantic claim ID changes | — | 17 (new identity scheme) |
| Claim value records | 34 legacy occurrences | 32 distinct semantic values; every occurrence/path retained |
| Claim evidence receipts | 0 | 17 |
| Claim evidence paths | Not represented | 40: 20 relationship proofs + 20 atomic view paths |
| Required-role relation units | 40 | 40 adapted |
| Completion-only relation units | 0 | 1 (c1) |
| Required-unit statuses | 8 witnessed / 8 unwitnessed_complete / 24 incomplete | Same in compatibility projection |
| Node states | 9 | Same with display held fixed |
| Layer 1 | Accepted output | Byte equal in this projection |
| Existing invariant checks | 33 passing | 33 passing |
| Plan/ledger identity and hash | Legacy | Changed; intentionally not frozen as a new baseline |

Two duplicate literal values account for 34 -> 32: Hadza in c10 (two independent sources),
and Explicit Bias Questionnaire in c6 (multiple placements/source paths). This is display-value
normalization, not entity resolution or loss of evidence. Keep their list grouping and all members.

| # / scope | Family | Evidence paths | Citation IDs |
|---|---|---:|---|
| 1 / c1 | relational | 2 | p11, p2 |
| 2 / c2 | relational | 2 | p47 |
| 3 / c4 | relational | 4 | p11, p2 |
| 4 / c4 | relational | 2 | p40 |
| 5–9 / c8, five trait instances | relational | 2 each | p41 each |
| 10 / c3 | role_value | 1 | p14, p17, p26, p3, p7 |
| 11 / c6 | role_value | 1 | p52 |
| 12 / c10 | category_list | 2 | p29, p53 |
| 13 / c2 | category_list | 2 | p35, p46 |
| 14 / c3 | category_list | 2 | p36, p8 |
| 15 / c8 | category_list | 4 | p20, p9 |
| 16 / c5 | category_list | 4 | p46, p47 |
| 17 / c6 | category_list | 4 | p14, p17, p26, p3, p7 |

Node states in the transport oracle: 1 not_established; 2 not_established; 3 answered;
4 not_established; 4A not_established; 4B partial; 5/6/7 not_established.
Three existing scientific statement instances remain in nodes 3 and 4B.
Recovery targets, map states, witness proofs and source metadata are untouched.

### Strict per-value display-support probe

The first projection is deliberately NOT a future-plan success claim. Checking each current atomic/
list value's render sources against its own selected view finds exactly one renderability mismatch:

- Claim category_list::351d34bff55b518f, c3 implicit/explicit coverage.
- implicit has selected legacy support p36.
- explicit has selected legacy support p8.
- Old _evaluate_values scans the claim-wide union [p36,p8] and uses p36 for BOTH values.
- Restricting explicit to p8 fails the existing attribution_prior_work presentation check.
- The implicit p36 sentence remains displayable; its incidental “explicit” words do not make it
  the selected explicit binding's evidence.

A strict selected-view coverage projection therefore changes the category facet and node 3 from
answered to partial, credits implicit only and leaves explicit uncovered. A second in-memory experiment replaced only _candidates_containing's atomic/list citation input
with the value-specific selected support set, then ran the existing full replay machinery.
It confirmed exactly that node-3 change: the map and all 17 claims remained identical, all
scientific statement texts stayed identical, and all 33 existing invariants still passed.
The emitted status/disclosures changed, so Layer 1 parity cannot honestly be claimed.
This temporary process-local adapter was not written to production code.

The unchanged disclosure machinery would now say “The retrieved evidence does not establish explicit
attitude findings,” despite the preserved positive category observations. That is a further reason
not to ship the strict projection mechanically: display-source rejection, selected binding authority
and scientific category state need an explicit contract. This is rendered coverage, not a change
to sufficiency or evidence ownership.

The preserved explicit category instance ALSO contains an existing positive_finding p36
category_observation. It is already upstream-classified evidence, not a scientific guess, but it is
not represented by that role's selected legacy support view. Three choices must not be conflated:

1. Strict selected-view authority: accept the node-3 coverage change.
2. Explicitly authorize a category-observation reference adapter for atomic category coverage:
   consume the existing p36 observation without creating a candidate/view or rerunning polarity.
3. Retain the old union/text substitution silently: **reject**; it has no value-specific receipt.

Recommend auditing option 2 against the full category-observation contract in I4-4B; if that authority
is not approved, choose option 1 and record its real delta. This audit does not implement either.

There is a second presentation boundary: c3's candidate assertion excludes the “Nevertheless,”
prefix and terminal punctuation present in the currently printed source sentence. Evidence scope
must remain the assertion. A future display adapter may preserve a separately located, audited
non-assertive sentence wrapper; it cannot use enclosing-sentence text to introduce another result,
sign, owner or unsupported clause. Freeze this wrapper rule before promising byte-identical prose.
Legacy whole-unit scope remains exactly the v8 rule for legacy-only evidence.

Consequently “17 claims / nine nodes / 33 checks” is necessary but insufficient qualification.
The current 33 invariants accept the cross-value substitution and do not prove receipt alignment.

## C24. Frozen synthetic A–R design matrix

Observed current behavior and future expectations are deliberately separated. The 75 unchanged
tests reproduce the known failures; the scratch reference projection exercises proposed grouping,
not production ParentClaims/AnswerPlan repair.

| Case | Future required result / audit evidence |
|---|---|
| A: A/P1 + B/P2, sibling P2 | Current ParentClaim raises empty joint support; legacy parity disagrees; current v8 AnswerPlan has P1/P2 operands despite witness P2. Future claim/unit uses selected P2 path, no P1 relationship citation, no exception. Scratch proof projection contains only P2. |
| B: reverse candidates | Same semantic claims and path sets at fixed placement; no representative rewrite. Scratch both orders equal. Upstream re-keyed placements may change reference IDs, not semantic claim identity. |
| C: equivalent independent proofs | One tuple, all paths. Scratch two common PIDs produce two completion plus two I1 refs; purposes remain distinct. |
| D: different tuples | Separate claims. Two selected inherited referents beta/gamma yield two tuples; not a union tuple. |
| E: matching excluded/nonmatching eligible | No false relation; scratch projection empty. |
| F: attachment-ambiguous matching | No established relation; uncertainty remains diagnostic. |
| G: candidate key/zero eligible | No legacy fallback; scratch projection empty. |
| H: inherited operand | Selected inherited value plus child I1 proof; not child-own. No origin-proof substitution. |
| I: link-only | Valid completion relationship, empty I1 witness IDs; retain context/designator refs. No fake PID. Source context citation limitation remains visible. |
| J: same-P2 opposite signs | Established underlying tuple, both observation paths; null consensus and within-instance conflict. No single-sign render or consensus claim. |
| K: same-sign distinct assertions | One directional conclusion only if existing summary supports it; two physical observation refs, no offset collapse. Scratch summary positive, no conflict. |
| L: supported/not_supported | Complete-instance companion has conflict/null consensus. Incomplete original keeps two diagnostics with no summary contribution; no I1 gate added. |
| M: malformed proof ref/hash | Typed integrity failure; no plan. Scratch altered proof reference rejected; production validator still to be built. |
| N: claim points to excluded support | Reject positive claim receipt even if ID resolves; diagnostics allowed. Scratch stored gate corruption rejected. |
| O: duplicate proof path | Set normalization; one path/claim/citation occurrence, conflicts under same ID fail. |
| P: distinct physical sources/same text | Both source paths retained; no text-only evidence dedup. Scratch independent P1/P2 paths stay distinct. |
| Q: legacy v7 | Exact accepted replay; no new fields, selectors, claim IDs or version. Reverified. |
| R: real v8 | Reference transport retains 17 claims and old answer. Strict category coverage reveals the documented boundary; NOT yet an unconditional same-answer pass. |

Add qualification pairs beyond A–R before implementation: complete vs incomplete effect summaries;
required vs alternative completion participation; completion-only c1; same tuple/different owners;
unlocated selected candidate; orphaned receipt/observation; rehashed wrong tuple; unsupported value
mapping; source-specific render partition; external ownership on an own operand; repeated source
text with different offsets; and the real p8/p36 category case.

## C25–C27. Boundaries, handoff and Simple Ask

Future static/purity guards must be executable:

- Freeze v4-v7 legacy function bodies and exact replay baselines; spy that historical paths never
  enter new adapters or emit null placeholders for v8 fields.
- Layer C production AST must not read candidate_supports, call support_policy/assertion_authority,
  build_support_views, common_assignments, select_completion_proofs, select_i1_proofs,
  finalize_instance or rw.witness_instance on v8.
- New resolver/validator calls have an explicit allowlist; selected-proof validation may resolve
  IDs and check the already selected assignment. It may not form Cartesian products or choose alternatives.
- No v8 classify path calls direction_target; no whole-quote evidence search outside an authorized
  legacy/render-context scope. No first-proof/first-candidate semantic rule.
- No map, binding, proof, observation or input receipt mutation; deep-copy equality before/after.
  Shuffled input registries and candidate order produce identical semantic claim IDs.
- Each citation/value/operand/observation must resolve through its receipt; inject excluded, inherited-as-own,
  foreign-placement, missing, rehashed and stale refs. Require fail-closed behavior.
- Same printed text/different physical sources keeps separate paths; repeated paths do not inflate.
- Freeze policy, attribution, guards, candidate collection, recovery, summaries, PLAN_VERSION and current
  version until their exact future authorized increment. No model/network/database/time/random in pure adapters.
- Replay authorization/profile mismatch tests; default/current v7 still rejects noncurrent v8.
- Compare qualified real output semantically AND by per-value coverage/citation paths, not just counters.

**C26. I2-3 metadata handoff:** per-path assertion_relation, aggregation, assertion_kind, authority_veto,
is_caption, attribution proof/ruleset/context refs, guard_exclusions, policy evaluation/source/
failed dimensions, attachment uncertainty, source ownership, exact locator, compatible relation status,
observations/conflict and no-candidate/excluded/unestablished distinctions. These facts must survive
statement/claim-role/layer2/layer3 projections without being flattened to a quality ranking.
No new authority-veto gate or direct/indirect prose is designed here.

**C27.** Simple Ask can consume the same placement/role/value/evidence/receipt machinery. owner_id is opaque,
and grouping uses authored requirement identity, not q_aib vocabulary, child names or hierarchy prose.
Parent context is optional. Simple Ask currently lacks a demonstrated equivalent role/proof/overlay
production path; upstream contract construction and a display adapter would be required. That is an
integration gap, not justification for a second evidence semantics. No Simple Ask implementation here.

## C28–C32. Readiness, promotion and next increment

**C28 promotion gates:** qualified proof-aligned ParentClaims and AnswerPlan; A/P1+B/P2 end-to-end
success; both signs/conflict preserved; no excluded support leakage; inherited/link-only/alternative
contracts honored; source-specific wording truthful; historical v4-v7 exact; separately frozen
v8+plan-v5 profile; resolved real category/display boundary; correct replay identity and actual ledger
binding; full offline suite with zero unexplained regressions. Existing known failures must be
independently reproduced. Model/live E2E is not required by this audit.

**C29:** separate tiny promotion increment after qualification. V8 and plan-v5 may both remain
explicit/nondefault while v7/plan-v4 stay current. Do not bundle promotion with broad Layer C edits.

**C30:** split the work. A validation/reference prerequisite can ship without activation. The later
claim/plan integration must be atomic across semantic value, evidence, citations, observations and
coverage; do not ship only the ParentClaim exception fix or only proof-aware Booleans.
Minimal render/realization adapters or explicit unsupported-version guards belong in that integration,
not an unannounced I2-3 style rewrite.

**C31:** NOT READY for production Layer C implementation under an unconditional “real answer unchanged”
contract. READY for the bounded design closure below. This is a finding of the completed audit, not
permission to change upstream semantics or silently narrow the user's invariant.

**C32 next increment:** **PHASE 34 / I4-4B — LAYER C VALUE, CATEGORY-COVERAGE AND VALIDATION CONTRACT
CLOSURE (PLANNING / READ-ONLY)**. Resolve (1) the p8-selected/p36-observed category authority and
freeze its exact answer-state expectation; (2) closed semantic-value grouping and unlocated/unknown
fallback behavior; (3) validation-only/reference-resolution API, including excluded metadata and
link context; (4) assertion-evidence vs display-envelope boundary and exact version-profile fixtures.
Return implementation-ready preregistered outputs. No implementation is authorized by this report.

After acceptance, proposed implementation scopes are I4-4C (pure validation/reference substrate,
no activation) and I4-4D (atomic claim-v2/plan-v5 integration + offline qualification), followed by a
separately authorized promotion. Names are recommendations, not started work.

**STOP after I4-4A.** No production code, ParentClaims, AnswerPlan, rendering, witnesses, recovery,
attribution, policy, guards, PLAN_VERSION or sufficiency version changed. No same_local_assertion,
claim-goal/veto semantics, I2-3 or live E2E. This audit is documentation only.
