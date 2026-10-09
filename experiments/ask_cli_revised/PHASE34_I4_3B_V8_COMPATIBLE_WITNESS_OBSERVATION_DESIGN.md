# Phase 34 / I4-3B — V8 compatible-witness selection and observation-alignment design

Date: 2026-10-09. **Planning/docs only. No v8 implementation or baseline.**

Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
Verified full starting HEAD: `d1768f48d3ac8a3ff6a618e3a94ba49afe381205`.
The starting worktree was clean. This design builds on accepted I4-3A and the accepted v5 grounding, v6 attribution and v7 policy/guard increments.

**Decision: READY for one bounded, atomic Layer A/B v8 implementation of candidate-aware witness proofs plus aligned observations.** Do not ship a Boolean-only intermediate. The recommended next increment is **I4-3C — V8 compatible-witness proofs and aligned observations: bounded integration and offline qualification**. This readiness does **not** mean existing ParentClaims/AnswerPlan become candidate-aligned. Their concrete synthetic limitations are characterized below and remain I4-4 work; unrestricted end-to-end candidate-aware answer qualification is not ready.

The closed design selects **candidate assertion scope**, preserves legacy unit scope, retains every relevant successful assignment, and keeps effectiveness independent of I1 eligibility. The prospective real oracle preserves all existing semantic outputs. Exact v4–v7 replay hashes remain unchanged.

## 1. Required decisions

| Decision | Closed result |
|---|---|
| B1 | `support-view-v1`, with placement, outer source, representation kind, support IDs, text/evidence references and receipts; §3. |
| B2 | `support-ref-v1:sha256:<64 hex>`, placement + immutable spanned grounding identity. Support IDs/text/gates are checked integrity payload, not discovery index; §4. |
| B3 | Explicit `legacy-support-ref-v1`; separately tagged candidate-without-assertion-span reference. No invented spans or legacy fallback; §4. |
| B4 | Identical normalized duplicate collapses; same grounding reference with conflicting payload raises before eligibility filtering. Proof duplicates collapse by full proof identity; §4. |
| B5 | Validate candidate records; filled + admissible is True + attachment_ambiguous is False. Key present with zero eligible records means zero views; §3. |
| B6 | Immediate source comes only from outer binding candidate_source==parent_context. Scientific assertion_relation never determines own/inherited; §3. |
| B7 | Exact existing own_evidence_roles participation, prerequisite/category gates, filled alternatives, optional/parent exclusion and <2-own bypass; §5. |
| B8 | Exact I1 required roles, every required role filled, ≥1 own, verified common own proposition and selected inherited referents; §5. |
| B9 | Per-role support-ID index → global common IDs → actual compatible view tuples; §5. |
| B10 | Separate proof sets per authored verifier, OR for truth, no cross-verifier splicing; §5. |
| B11 | Enumerate compatible own assignments; filter inherited alternatives by full sealed-quote containment for that own proposition, then retain every successful extension; §5. |
| B12 | `relationship-proof-v1`, including purpose, placement, verifier, assignment, join, checks and version; §6. |
| B13 | Keep witness_ids as sorted unique proposition IDs. Add witness_proofs; link-only proofs have no invented proposition ID; §6. |
| B14 | Serialize joint-grounding outcome and proof references, including explicit bypass/blocked status. Do not equate it with I1; §6. |
| B15 | Exact selected assertion slice. No containing-sentence, whole-proposition or whole-unit expansion when own candidate-local evidence is available; §7. |
| B16 | Derive observation sentence offsets *inside* the assertion using the unchanged direction splitter and a reversible whitespace offset map. No classifier or candidate schema change; §7. |
| B17 | `legacy_unit` scope explicitly preserves historical unit construction/scoping when selected own views are legacy-only; §7. |
| B18 | Physical source/scope + assertion and observation spans + observation kind/result identity. Merge provenance paths, not distinct assertions; §8. |
| B19 | Direction uses one complete selected assignment's operand references and evidence; all successful alternatives survive and opposing signs produce conflict; §8. |
| B20 | Effectiveness uses aligned own-evidence scopes and existing predicate/flag rules. No new I1 gate; local flags come from the existing detector on the local slice; §8. |
| B21 | Parent eligibility and copying unchanged; child support references are re-scoped to child placement and remain inherited. Origin proofs stay on origin instances; §9. |
| B22 | Recovery algorithms unchanged; changed complete/state naturally changes targets. Real targets identical; §9. |
| B23 | I4-4 receives proof registry, selected text/locator references and observation paths. Current ParentClaim exception and stale AnswerPlan operand projection remain explicit limitations; §9. |
| B24 | 0 real role/requirement/witness/observation changes; 48 targets, 17 claims, nine nodes and all 33 invariants preserved; §10. |
| B25 | Freeze I4-3A A–K/L and exclusion families; add identity, inherited, scope, deduplication, verifier-OR and downstream-characterization cases; §11. |
| B26 | Explicit v8 routing only; v7 grounding/attribution/policy/guards/classifiers/quantifiers/recovery inherited exactly. Explicit v4–v7 remain byte-exact; §12. |
| B27 | File/function-level import, key-consumption, selector-call and mutation guards; §13. |
| B28 | One bounded integration, staged internally as pure helpers/tests then atomic v8 routing. Do not activate witness truth separately from observation alignment; §14. |
| B29 | READY for that bounded implementation and offline A/B qualification. NOT a claim of readiness for general proof-aligned Layer C/end-to-end answers; §14. |
| B30 | I4-3C — V8 compatible-witness proofs and aligned observations: bounded integration and offline qualification. No I4-4 implementation in that increment; §14. |

## 2. Actual architecture and audit method

Production inspection confirmed the I4-3A inventory. Key seams:

- `sufficiency_engine._support_set/_verify_same_proposition/_joint_grounded` use legacy binding support/text; `own_evidence_roles` and `recompute_instance` determine engine participation and completeness.
- `relation_witness.witness_instance` independently uses **required** roles, own/inherited source and verified sealed propositions. It does not implement authored verifier OR.
- `sufficiency_diagnostic.compute_direction_and_effectiveness` obtains observation scope from `relationship_witness_support_ids`, passes required-role representative surfaces, and separately supplies I1 IDs for direction eligibility.
- `sufficiency_mapping.find_effectiveness_observations` uses result-predicate detection and negated/absence flags, without an I1 gate.
- `overview_evidence.build_units` uses `_dedupe_key(paper_id, passage) = (paper_id, " ".join(words(passage)))`, not a unique physical anchor. Its unit retains a passage, proposition IDs and locators. Preserve this existing legacy behavior explicitly.
- `assertion_authority` can expose sentence information in classification records, but production candidate_supports retain assertion/predicate/content spans, not a uniform sentence locator. No new assertion-authority consumer is needed.
- `derive_instance_key` reads representative ID/text. `_rederive_keys_if_forked` runs before requirement recomputation; model dependency origins are stamped later by the diagnostic. This affects when references are constructed and what provenance belongs in their identity.
- Parent copying uses `{**parent_binding, "provenance": restamped_parent_context}`; carried candidate lists survive as data. Instance-level proof bundles are not part of the copied role binding.
- ParentClaims call the **unversioned legacy** relationship-support helper and still construct values from representatives. AnswerPlan calls the shared I1 function but separately projects representative operand text/IDs.

All four existing offline replays were freshly rerun from hash-verified preserved ledger/map/packet inputs. Model nominations were held fixed through the existing offline harness. A separate in-memory oracle implemented support views, per-ID assignments, verifier OR, inherited alternatives, local versus legacy observation scopes and path deduplication. Existing production direction/effectiveness functions and summary functions evaluated the selected texts. No production function or file was replaced.

For the Layer C characterization only, a scoped in-memory stub returned the prospective I1 result to the unchanged AnswerPlan adapter to expose its remaining representative projection. This is explicitly a counterfactual call, not a produced v8 map.

The oracle carries enough temporary data to exercise decisions; its transient Python objects are not the proposed serialization. Counts below are logical proof/view counts, not a frozen v8 wire artifact. Normative schemas and identity material are specified here; schema conformance and complete version-isolation tests are preregistered for implementation.

## 3. One eligible-support adapter and support-view schema

### 3.1 Input/output contract

Proposed sole production adapter:

```text
compatible_witness.build_support_views(
    placement, role_bindings, sealed_proposition_index
) -> support registry
```

All inputs are caller-supplied immutable data. No library reads, models, database, retrieval or policy re-evaluation. Placement is explicit:

```json
{"child_id":"c","requirement_id":"r","instance_key":null,"role":"role_name"}
```

Null is a real JSON null; it is not the string "null", an empty string or an ordinal. Do not infer child_id from requirement naming. Reject duplicate outer instance placements in one bundle namespace; do not hide them behind list indices.

For each binding:

1. If candidate_supports is present, require a list and run `se.validate_evaluated_candidate_support` on every record. Validate identities/locators and detect duplicate conflicts before filtering. A malformed retained exclusion must not disappear silently.
2. Missing/ambiguous binding → zero views, even if it contains an otherwise passing candidate.
3. Filled candidate-backed binding → one view for each distinct candidate satisfying `admissible is True and attachment_ambiguous is False`.
4. Present empty/all-ineligible list → zero views, even with stale filled legacy ID/text. Record `no_eligible_support_views`; do not change role state or use fallback.
5. Filled binding with **absent** candidate key → exactly one legacy view. No empirical-policy application to model/category/other legacy evidence.
6. Immediate source is `inherited` iff the CURRENT binding's provenance.candidate_source is `parent_context`; otherwise `own`, exactly as `rw.operand_source` currently does.

Candidate assertion_relation answers scientific ownership. Immediate operand source answers how the current requirement acquired a role. An attributed_external candidate may be a child-own operand; a current_document candidate carried from a parent is still inherited.

### 3.2 Normative support view

```json
{
  "schema_version": "support-view-v1",
  "support_view_id": "support-view-v1:sha256:<64 hex>",
  "placement": {"child_id":"c","requirement_id":"r","instance_key":null,"role":"a"},
  "immediate_operand_source": "own",
  "representation_kind": "evaluated_candidate",
  "support_ref": "support-ref-v1:sha256:<64 hex>",
  "supporting_proposition_ids": ["P1","P2"],
  "primary_proposition_id": "P1",
  "operand_text_ref": {"support_ref":"support-ref-v1:sha256:<64 hex>","field":"exact_text","sha256":"<64 hex>"},
  "evidence_locator_ref": "support-ref-v1:sha256:<64 hex>",
  "candidate_ref": "support-ref-v1:sha256:<64 hex>",
  "eligibility_receipt_ref": "support-eligibility-v1:sha256:<64 hex>",
  "source_provenance_ref": {"placement":{"child_id":"c","requirement_id":"r","instance_key":null,"role":"a"},"field":"provenance"}
}
```

Closed representation kinds: `evaluated_candidate | legacy_binding`. candidate_ref/eligibility_receipt_ref are null for legacy. primary_proposition_id is the candidate's span_proposition_id, or the legacy binding's historical primary, including null where historically absent. Never pick a new primary to change semantics.

The registry contains the locator/receipt once per support reference. It does not copy whole candidates into every view/proof. Candidate lookup uses the reference's immutable key inside the specified role placement, **not an array index**. It verifies a normalized candidate-payload digest against the still-retained candidate. Identical duplicates resolve to the same value.

Candidate locator fields:

```text
kind: candidate_assertion | candidate_unlocated
span_proposition_id: str | null
supporting_proposition_ids: sorted unique ID set for proof use
quote_identities: [{proposition_id, quote_sha256, source_identity}, ...]
assertion_span: [start,end] | null
predicate_span: [start,end] | null
content_span: [start,end] | null
exact_text_sha256: hash | null
candidate_payload_sha256: hash
```

Offsets are half-open Python/Unicode code-point offsets into the **sealed JSON quote string**, not PDF bytes, UTF-16 units or mutable library text. source_identity carries paper_id, evidence_anchor_chunk_id, evidence_span_id and any ordered continuation-anchor descriptors. Absent source fields remain explicit null in minimal fixtures.

For a spanned candidate, require an in-range nonempty assertion_span, exact equality `quote[start:end] == exact_text`, anchor membership in support IDs, and the current shared-coordinate guarantee for plural IDs. Validate attribution.target.quote_sha256 against the actual sealed anchor when attribution is present. Predicate/content spans remain their own validated sealed-quote coordinates: they need not be artificially clipped to assertion_span (current content spans can include punctuation the assertion omits).

Eligibility receipt fields are exactly the already evaluated independent facts: admissible, attachment_ambiguous, guard_exclusions and the complete support_policy_evaluation. The underlying candidate reference also preserves assertion_relation, aggregation, assertion_kind, attribution proof, authority_veto, caption and support_label metadata. None adds a new witness gate or quality ranking.

## 4. Stable identities, legacy/no-span cases and conflicts

### 4.1 Canonical encoding

All new hashes use full SHA-256, lowercase 64-hex, domain-separated versioned prefixes. Canonical JSON: UTF-8, sorted object keys, separators comma/colon without spaces, ensure_ascii=False, allow_nan=False, no newline; strings preserve their exact Unicode content. Text hashes hash UTF-8 text bytes directly. No Unicode, case, hyphen or whitespace normalization for evidence identity.

Only fields declared sets are sorted/deduplicated: support-ID sets, role-name sets, proof/ref sets, designator sets. Ordered source anchors and authored data keep their order. Normalize candidate.supporting_proposition_ids and attribution.target.supporting_proposition_ids for duplicate comparison; do not rewrite their preserved discovery-order arrays in the map.

The input sealed-ledger snapshot digest belongs on the bundle, not in each candidate ID: unrelated candidate insertion must not rename existing support references. Per-proposition quote/source identities protect against cross-source coordinate reuse.

### 4.2 Candidate reference

Adopt `support-ref-v1`: a content-derived **grounding reference**, not a list address or a quality score.

For a candidate with assertion_span, hash this material:

```text
scheme = support-ref-v1
representation = candidate_assertion
outer placement = child_id, requirement_id, instance_key, role
span_proposition_id
sealed quote identity = quote_sha256 + source_identity
assertion_span
```

**Validation material, not ID material:** the complete support-ID set, exact_text hash, predicate/content spans, attribution payload, support-policy/guard receipt and all other candidate payload. Two records claiming the same grounding reference must agree on that normalized payload. Moving a predicate/text/support set within an unchanged asserted grounding identity is an integrity conflict, not permission to create a second interpretation of the same record.

The reference distinguishes two assertions at different offsets in one proposition, different role placements and different instances. Candidate reorder, verifier order and insertion of an unrelated candidate do not change existing references.

support_view_id hashes its scheme, support_ref, representation_kind, immediate_operand_source, **stable outer source identity** and eligibility_receipt_ref (null for legacy). Stable outer source identity is the closed projection of candidate_source, model, upstream_model_dependent and source_lineage, with explicit nulls for absent keys. It excludes supporting_proposition_ids, free-form detail and additive model_dependency_origins. In particular, the representative's support IDs must never enter another candidate's view ID.

Full outer provenance remains inspectable through source_provenance_ref. Model-dependency-origin stamping must not invalidate IDs. A separate finalized bundle input digest covers the consumed binding/evidence fields; it does not turn incidental display or late provenance annotations into relation semantics.

**Placement boundary:** IDs are order-independent at a fixed outer placement. The existing `derive_instance_key` hashes representative ID/text; an audit confirmed that rerunning that upstream key derivation after representative reversal can change the runtime instance key. That is a different placement, so its placement-scoped references intentionally differ. V8 does not redesign instance keys or collection. Construct final references after current fork-key derivation; do not promise invariance under changes to the supplied placement itself.

### 4.3 No assertion span and legacy references

A candidate without assertion_span remains an evaluated candidate, never a legacy binding. Use the same support-ref-v1 prefix with representation= candidate_unlocated and ID material: placement, anchor ID/null, sorted support IDs and their sealed quote identities, exact_text hash/null, and available predicate/content spans. This distinguishes partial locators without pretending they identify a complete assertion. It can participate in identity-based relationship proof if eligible, but cannot supply a candidate-local observation scope. Record `candidate_assertion_locator_unavailable`; never expand to a whole proposition or fuzzy-find text to compensate.

Legacy `legacy-support-ref-v1:sha256:...` ID material:

```text
placement
representation = legacy_binding
historical primary proposition ID, or null
historical support set = primary UNION provenance.supporting_proposition_ids
exact_text SHA-256, or null
immediate_operand_source
stable outer source identity defined above
```

Legacy locator kind is `legacy_unit`; assertion/predicate/content spans are null. Its referenced unit is determined through the existing sealed-unit path when observations are built, not fabricated during adaptation.

Missing legacy support IDs produce one empty-support view as required by the historical filled-binding adapter; same_proposition/I1 common-ID checks then fail. A legacy inherited view with no own support IDs can still supply its referent text: I1 never required parent IDs to join child evidence. Missing/empty inherited text fails containment. Missing own text does not newly prohibit the historical structural common-ID proof, but cannot serve as a direction operand surface. Invalid non-string/non-null text is a schema error. Null and empty string have distinct identity material.

### 4.4 Duplicate and tamper rules

- Same support_ref + same normalized payload → one registry entry/view, retaining occurrence count only as optional diagnostic metadata.
- Same support_ref + conflicting candidate payload → raise a typed integrity error **before** eligibility filtering, even if one record is excluded.
- Changed source quote/hash, out-of-range span, wrong exact slice, missing candidate anchor, inconsistent attribution quote hash or nonidentical plural coordinate basis → fail loudly; no repair by lookup order.
- Same proof ID + same complete normalized proof → one proof. Same ID with conflicting payload → integrity error.
- Repeated authored verifier names do not duplicate proofs or change OR truth.
- Never normalize two different assertion spans into one candidate or use array position to break a collision.
- Bundle validation verifies every referenced view/receipt/locator, selected eligibility, role placement, source classification and join membership. A stale bundle cannot be reused after the relevant candidate/state/source inputs change.

## 5. Selection authority and preserved participation

### 5.1 Engine joint completion

Keep the existing required/all and alternative/any prerequisite checks, category-goal gate and state aggregation unchanged. Obtain joint participants from the exact existing `own_evidence_roles(role_completion, bindings)`:

- All filled required and alternative-group members participate; do not choose a convenient one per group.
- Optional roles and immediate parent_context roles are excluded.
- Fewer than two own roles bypass the joint gate, even though no successful relationship proof is emitted.
- All-inherited filled operands can still pass this engine gate; I1 separately rejects all-inherited witnessing.

If prerequisite/category gates fail, serialize a blocked joint receipt and no completion proof. Diagnostic observation bases may still describe the already-filled own evidence, as current metadata construction does. A bypass is not evidence that an I1 relation is witnessed.

### 5.2 same_proposition

Given participating own roles R and their eligible views:

1. Build an index role → proposition ID → views containing that ID.
2. Intersect the proposition-ID keys across **all** R.
3. For each common p in sorted order, enumerate only the product of indexed views for that p.
4. Emit a proof for each actual role→view assignment and p.
5. Canonicalize/deduplicate proofs by complete identity.

For p with A2 and B1/B3, emit A2+B1/p and A2+B3/p. The same assignment supported by two recorded common proposition IDs produces two join proofs; witness_ids deduplicates their IDs and observation deduplication prevents fake corroboration. Do not enumerate products for IDs absent from any participating role. Do not silently cap or rank successful assignments; any explicit resource limit must fail visibly, never truncate evidence and suppress conflict.

A filtered per-role union/intersection is a valid Boolean index for this pure predicate, but the index is not the proof. No support union is written into binding provenance. No physical-anchor, paper, chunk, similarity or entity join replaces proposition identity.

### 5.3 Verifier OR

Each authored verifier produces its own compatible proof set. Joint truth for ≥2 own roles is true iff that union is nonempty. Sort for serialization, not semantic preference. Do not stop after the first successful verifier and lose its alternatives or the second verifier's distinct basis.

For contract_directed_links, preserve the current requirement for nonempty caller-supplied attachment_pieces and the existing shared-designator test on **selected** texts. Missing context yields zero proofs. When supplied in a synthetic fixture, record the shared normalized designators, selected text refs and context digest; do not reinterpret that lightweight historical check as a stronger document-link verifier. Distinct proposition IDs can yield a link proof but no common-proposition witness ID. No production caller currently supplies this context; v8 does not create it.

### 5.4 I1 own/inherited assignment

I1 remains a separate purpose, not an alias for engine verifier OR:

1. Require every required role filled and an eligible view for each. A filled role with no eligible views yields `no_eligible_operand_support`, a new v8-specific failure reason. Malformed data raises instead.
2. Split required roles by outer immediate source. Require ≥1 own role.
3. Find compatible common-proposition assignments among own required views.
4. For each common p require the current sealed verification and continuation-anchor rules (`rw.is_admissible`).
5. For every inherited required role, independently retain eligible views whose **selected referent text** is contained in p's full sealed quote using the explicit v8-selected, unchanged v2–v7 casefolded canonical containment rule.
6. Form every combination of those retained inherited views with that own assignment; emit one I1 proof for each.
7. Relation truth is existence of an I1 proof. witness_ids is the sorted unique set of its verified common own IDs.

Inherited IDs never enter the own intersection. An inherited view's original assertion_relation does not change source classification. Do not tighten full-quote containment to candidate-assertion containment. Do not join an inherited referent from one proof with another proof's own evidence.

Existing I1 failure reasons remain meaningful: incomplete_operands, no_own_operand, no_single_proposition, no_admissible_candidate, inherited_referent_absent. The latter two continue to mean sealed-proposition verification and containment, not candidate policy. Keep per-view exclusions in registry diagnostics rather than overload those reasons.

## 6. Proof schema, APIs and storage

### 6.1 One successful proof

```json
{
  "schema_version": "relationship-proof-v1",
  "proof_id": "witness-proof-v1:sha256:<64 hex>",
  "purpose": "completion_joint",
  "placement": {"child_id":"c","requirement_id":"r","instance_key":null},
  "verifier_id": "same_proposition",
  "participating_roles": ["a","b"],
  "assignment": {
    "a": {"support_view_id":"...","immediate_operand_source":"own","evidence_ref":"..."},
    "b": {"support_view_id":"...","immediate_operand_source":"own","evidence_ref":"..."}
  },
  "join": {"kind":"same_proposition","proposition_id":"P2"},
  "checks": {},
  "semantic_version": "sufficiency-semantics-v8"
}
```

Purpose is closed to `completion_joint | i1_relation_witness`. I1 verifier_id is `operand_source_witness`; its join is still same_proposition and its checks record the sealed verification/continuation receipt plus each selected inherited referent's text reference, containment-rule ID and successful full-quote check.

A links join is `{"kind":"shared_designator","designators":[...],"context_sha256":"..."}`; it has no proposition_id. Hash the complete proof body excluding proof_id. Include schema, purpose, placement, version, verifier, normalized roles, full assignment, join and checks. Exact duplicated proof bodies collapse; do not merge purposes.

### 6.2 API split

Proposed functions in one pure `compatible_witness.py`:

| API | Responsibility |
|---|---|
| `build_support_views(...)` | Sole adaptation, identity, validation and candidate eligibility authority. |
| `select_completion_proofs(registry, own_roles, verifier_ids, verifier_context)` | Indexed same-proposition assignment and verifier OR. Caller supplies historical participation. |
| `select_i1_proofs(registry, required_roles, proposition_index, verified_predicate, referent_predicate)` | Same indexed assignment primitive, own/inherited extensions and I1 proof records. Existing I1 predicates are supplied, not reimplemented. |
| `build_observation_bases(registry, completion_own_roles, required_roles, joint_selection, i1_selection)` | Align all observation assignments once, including diagnostic/single-own bases described in §8. No text scanning or policy evaluation. |
| `proof_truth(proofs)`, `proof_proposition_ids(proofs)` | Pure projections. Joint <2-role bypass is handled by its explicit receipt, not by pretending an empty proof set proves a relation. |
| `validate_witness_bundle(...)` | Input identity, references, assignment/gate/source/join integrity; no new candidate choice. |

Engine and relation_witness own their different participation/prerequisite contracts. They delegate **selection** to the same module. Diagnostic, direction and AnswerPlan must not implement another candidate adapter or independently select a first admissible record.

### 6.3 Additive v8 instance storage

Current storage is three **top-level** fields:
relation_witnessed, witness_ids, witness_provenance. Do not wrap or rename them into a new relation_witness object.

Add, on v8 instances only:

```text
witness_bundle:
    schema_version = witness-bundle-v1
    semantic_version = sufficiency-semantics-v8
    placement = child / requirement / instance
    sealed_input_sha256
    binding_semantic_input_sha256
    support_records = canonical ref-keyed locator/payload-digest records
    eligibility_receipts = ref-keyed records
    support_views = view-id-keyed records
    proofs = proof-id-keyed records, both purposes
    observation_bases = canonical basis-ref-keyed records
    diagnostics = ordered typed receipts

joint_grounding:
    schema_version = joint-grounding-v1
    status = blocked_prerequisite | bypassed_lt_two_own | proved | unproved
    participating_roles
    verifier_ids
    proof_refs

witness_proofs: sorted I1 proof references into witness_bundle.proofs
```

blocked_prerequisite includes a typed reason for completion-role or category-goal failure. Engine receipts are serialized because candidate selection can make an instance complete and change parent/recovery behavior. A transient Boolean alone cannot explain that change. Store shared views once; joint and I1 proofs stay distinct records referencing that registry.

Keep witness_provenance's existing diagnostic keys for compatibility. In v8, own_support/candidate_ids may describe **eligible search-space ID sets** as diagnostics, not a selected assignment; proofs are authoritative for assignment. candidate_checks retain sealed verification and explicit per-selected-referent checks/proof references. failure_reason remains the stable compatibility field. No consumer may reconstruct a witness by unioning these diagnostic sets.

The bundle's binding_semantic_input_sha256 covers the fields actually consumed: role states, current source classification/identity, legacy text/IDs where applicable, normalized candidate records and role participation/relationship declarations. It excludes projection-only representative text/IDs on candidate-backed bindings and additive model_dependency_origins. Full outer provenance remains reachable. Build after final fork keys; the existing model-origin stamp can add its metadata without renaming support views. Validate after stamping and before I1/observations. Do not hash newly added proof/observation fields recursively into their own input identity.

A v8 witness call with no valid v8 bundle/context fails loudly; it must not silently run the legacy representative path. The existing AnswerPlan call signature can consume a valid instance bundle through the shared I1 wrapper later without deriving child identity from requirement text. This does not fix its separately projected operand values.

Explicit v4–v7 produce none of these fields.

## 7. Selected observation text and locator transport

### 7.1 Scope decision

| Option | Decision | Reason |
|---|---|---|
| A — exact selected assertion text | **Adopt** | Already sealed, locally grounded and candidate-specific. Retains its actual subject/predicate wording without borrowing another assertion. |
| B — containing sentence | Reject as default expansion | A sentence can contain two coordinated assertions, including an excluded assertion with an opposing sign. Sentence containment alone is not permission to inspect both. |
| C — whole sealed proposition | Reject for candidate-backed own evidence | Can contain many assertions and reintroduce the representative/alignment defect. |
| D — whole physical unit | Preserve only for legacy-only own evidence | Historical unit deduplication can combine IDs/locators; it is not a candidate assertion locator. |

Observed domain-neutral scope probe:

```text
alpha was positively associated with beta, while gamma was negatively associated with delta.
```

The first assertion is eligible; the second is excluded. Existing direction_target on the first assertion classifies relation/positive. Giving it the containing sentence, whole proposition or whole unit produces unknown/conflicting_signs. The scope choice therefore matters even without a classifier change. The candidate-selected slice yields only the supported positive observation; the excluded clause contributes neither text nor flags.

No grammatical completion is invented. If a localized clause lacks enough explicit operand text for the existing classifier, retain its unknown result. Do not prepend a subject, borrow a previous clause or expand to a sentence to force a direction. Full assertion text generally retains more context than the matched predicate/content alone; this is why assertion_span, not predicate_span, is the boundary.

The same-P2 positive and negative *separate* assertions each receive their own assignment and local scope. Both yield eligible direction observations and existing summary semantics yield no consensus, within-instance conflict=true, across-instance heterogeneity=false.

### 7.2 Sentence offsets inside the selected assertion

No new containing-sentence locator is required and no candidate-creation field changes. The selected scope is the existing assertion_span. Direction still calls the unchanged direction_target.split_sentences on that slice; effectiveness evaluates the selected assertion as its passage.

For each direction sentence, derive a locator using this exact deterministic transport:

1. Read the assertion substring by sealed offsets; verify its exact_text hash.
2. Reproduce the splitter's existing whitespace collapse and trim, while building a normalized-character → original half-open character-range map. Each collapsed whitespace character maps to its full original whitespace run.
3. Call the existing splitter on that same assertion string. Locate each emitted sentence by exact, monotonic matching in the normalized string, beginning after the prior sentence. Require intervening text to be only the splitter's separator whitespace.
4. Map the first/last normalized characters back to the raw assertion offsets and add assertion_span.start.
5. Verify that normalizing the raw slice exactly reproduces the emitted observation text. On mismatch, raise an observation-locator integrity error; no fuzzy search or alternative tokenizer.
6. Store raw observation_span, raw-text hash, existing normalized exact_text and normalization ID `direction-whitespace-v1`.

The audit exercised eight locator inputs: plain text, tabs/newlines and leading/trailing spaces, two sentences, repeated identical sentences, run-in label/coordination, semicolon, closing quotation punctuation, and abbreviation/parenthetical text. All reconstructed the unchanged splitter output with exact monotonic raw coordinates. The quotation example deliberately preserves the current splitter's single-sentence outcome; transport must not “improve” tokenization.

Do not call assertion_authority again or import its private sentence parser. Do not persist a guessed sentence span on candidate records. The additive v8 observation locator is sufficient and leaves v4–v7 candidate shapes untouched.

### 7.3 Local and legacy scope construction

For an observation basis with selected **own evaluated candidates**, inspect each distinct selected own candidate's assertion slice. Do not also scan a selected legacy own role's whole unit: that would escape the candidate-local restriction. A candidate with no assertion_span contributes no local scope; emit the missing-locator diagnostic, not a whole-unit fallback. Other selected own candidates with valid locators may still supply their own scopes.

For a basis with no selected own candidate views, retain the historical _instance_scoped_units construction and whole-unit behavior. Tag `scope_kind=legacy_unit`; carry its existing unit identity/passage/locators and proposition aliases. Legacy observations keep historical ordering and citation representative selection where no candidate changes the selected basis. A candidate-backed **inherited** view supplies a selected referent, not child-owned observation evidence; it cannot authorize scanning its parent passage.

The new local flag input is computed by the existing overview_evidence.passage_flags on the exact local assertion slice. This changes only the scope supplied to the detector. It does not reevaluate guard_exclusions or support policy and does not mutate the candidate. Historical legacy_unit paths retain their historical whole-unit flags.

## 8. Observation bases, proof alignment, deduplication and effectiveness

### 8.1 Preserve the distinct historical observation eligibility

Observation scope today is broader than successful I1 witnessing: metadata can exist on incomplete instances, and a single own role supplies evidence without a joint relation proof. Preserve this explicitly with a separate receipt, **not a fake successful relationship proof**:

```text
observation-basis-v1:
    basis_id
    placement
    basis_kind: single_own_support | common_own_support
    participating_own_roles
    selected_views: role -> support_view_id
    common_proposition_id
    completion_proof_refs
    i1_proof_refs
    semantic_version
```

Zero filled own completion roles → no bases. One own role → each eligible view/support ID provides a single-own basis. Multiple own roles → the indexed common-proposition assignment primitive provides bases, retaining the historical intersection rule. It can supply diagnostic metadata even when some other required role is missing or a category prerequisite fails. This is not an alternative completion gate.

A contract_directed_links-only success contributes no proposition observation basis. If a selected assignment independently has a common own proposition, the existing intersection basis can still be recorded; the links proof does not fabricate it.

Direction required-role operand surfaces are selected once in this shared selection stage. For a base, extend with each eligible view of other filled required roles. Missing required roles contribute no operand surface, as historically. Select I1 proof extensions compatible with that exact own assignment and common ID:

- If compatible successful I1 extensions exist, classify direction for each such complete assignment; do not mix its ID with another inherited alternative's text.
- If none exist, retain diagnostic direction paths using the available selected required-role surfaces, with no I1 proof refs and relation_eligible=False. This preserves real c5/c6 diagnostic observations.
- Do not emit unsuccessful inherited alternatives as extra direction paths for an own base that has a valid I1 extension. Those rejected alternatives remain in containment diagnostics, not competing relationship observations.
- Effectiveness uses the own basis regardless of I1 success. Inherited alternatives are unnecessary for its classifier; if retained as path context, they must not create a new eligibility gate or duplicate the physical outcome.

Each base/proof/operand selection is constructed by compatible_witness. The observation builder only consumes those selections; it never enumerates candidate_supports or chooses a first candidate.

### 8.2 Observation envelope and identity

Preserve existing direction/effect assessment fields. Add v8-only `evidence_alignment`:

```text
schema_version: observation-alignment-v1
observation_id: observation-v1:sha256:...
scope_kind: candidate_assertion | legacy_unit
physical_scope:
    source_identity / legacy unit identity
    sealed_quote_sha256 / legacy passage identity
    assertion_span or null
    observation_span or null
    raw_text_sha256
    normalization_id or null
evidence_proposition_ids: sorted IDs actually supporting this observation
paths:
    basis_ref
    witness_proof_refs
    selected_support_view_refs
    evidence_locator_ref
    operand_text_refs: required role -> text reference
semantic_version: sufficiency-semantics-v8
```

For candidate-backed physical identity use the sealed source's paper/chunk/span/continuation identity plus quote hash and assertion_span. Where minimal source metadata is absent, use the explicit anchor proposition ID as a fallback identity component; never claim two unlocated sources are physically identical. Two proposition aliases of the same source/quote/span may deduplicate observations **after** each proposition-identity proof succeeds. This is observation deduplication, not an anchor-equality relationship verifier.

For legacy-only identity preserve the existing unit grouping/scoping convention, including the supplied passage identity and recorded locators; do not retroactively split/merge legacy observations using new physical rules.

Observation identity additionally includes outer instance placement, observation kind, raw observation locator/hash, selected scope kind, direction/effect semantic result and classifier/version identity. It excludes proof IDs and candidate order. Merge identical physical/result observations and union their sorted unique path references. Retain exact sign, target, target_role, target_reason, relation_eligible, required_sign, causal metadata, or effectiveness conclusion/outcome fields in the result component; if the same physical text produces different role-target classifications under different assignments, retain separate result records with their distinct paths.

Never deduplicate by proposition ID alone, sign alone, text alone or proof count. Two same-sign assertions at different offsets remain two observations; opposing assertions remain distinct. Duplicate proofs reaching the same assertion/result create one observation with multiple provenance paths. Citation proposition_id is the sorted minimum of that observation's supporting witness IDs, using the existing legacy selection rule in legacy-only paths; it is display compatibility, not a new evidence choice.

### 8.3 Direction

Keep direction_target's vocabulary, literal-sign rules, clause handling and no-single-operand-fallback behavior unchanged. Run the existing classifier on the selected scope's sentence with the selected assignment's operand texts.

relation_eligible is true only when the observation has a compatible I1 proof on its selected proposition basis, target==relation and sign is not null. Successful I1 proof alone does not establish a direction. Preserve unknown/operand diagnostic results and the existing complete-instance summary filter.

The two selected same-P2 assertions from I4-3A produce positive and negative relation-eligible observations in both candidate orders. Existing summarize_observations returns:
consensus_value=null, observed_values=[], has_within_instance_conflict=True, has_across_instance_heterogeneity=False.
Do not canonical-sort candidates and then inspect only the first.

### 8.4 Effectiveness

No new I1 relation gate. For every own observation basis:

- Candidate-backed: inspect only each selected local assertion; use the unchanged result-predicate detector and the unchanged passage_flags negated/absence predicates applied to that local slice.
- Legacy-only: use the historical whole scoped unit and its existing flags.
- Retain supported and not_supported outcomes from different compatible assertions; use existing summary conflict behavior.
- No authority_veto gate, new claim-goal logic, numeric-sign inference or policy reevaluation.

Audit fixture: “We found alpha increased. We found no evidence that alpha increased.” With both supplied as eligible local candidates, selected scopes produce supported and not_supported, in either order. Whole-passage negation cannot contaminate the first assertion. This is scope correction, not a new polarity classifier. The current authority-veto metadata remains unused.

## 9. Parent propagation, recovery and Layer C handoff

### 9.1 Parent copying and recovery

Joint completeness must be computed before the existing parent eligibility/pairing pass. Preserve the current quantifier aggregation, eligible_parent_instances requirement of filled supplying role AND complete instance, immediate parent_context restamping, and all existing pairing algorithms.

Proof bundles live on originating instances, not role bindings. A copied binding's candidate list remains unchanged data. The receiving child constructs new placement-scoped support views after its own final instance keys exist; immediate source is inherited. Those child references resolve against the child's copied records, so they do not dangle after copying. Parent proofs remain on the parent instance. Existing source_lineage/model_dependency_origins remain the upstream trace; do not invent copied parent proof authority in the child.

Recovery continues to consume complete/state, role source, model provenance and legacy context text. It does not currently consume I1 truth as a replacement completeness gate. No recovery algorithm change is required. Only add explicit v8 routing where existing closed version tables require it.

Synthetic observed consequence: the non-representative P2 proof changes a previously incomplete two-own-role instance to complete. The unchanged _relationship_unverified_roles result changes from ["a","b"] to null; eligible_parent_instances changes from zero to one. Any resulting child pairing/obligation change is natural semantic fallout, not a rewritten recovery algorithm. Real q_aib recovery output remains identical.

### 9.2 Exact I4-4 handoff and expected limitations

I4-4 receives the instance's witness bundle, joint receipt, I1 witness_proofs/IDs, selected support/text/locator references and proof-linked observations. These are sufficient to choose wording/citations from the same actual assignment later. They do not retroactively make existing claim values correct.

Observed consumer-boundary fixture: evidence representative A/P1, eligible non-representative B/P2, sibling P2, prospective complete=True.

1. Unchanged ParentClaim construction raises:
   “complete with 2 own-evidence roles but its joint-witness support set is empty”.
   Its unversioned relationship_witness_support_ids still sees P1/P2 representatives. This is an expected downstream limitation, not a reason to alter the representative or union provenance.
2. Supplying prospective I1 metadata to an unchanged legacy I1 derivation causes AnswerPlan metadata_check="disagrees".
3. In a separately scoped counterfactual call where the shared I1 function returns the proof-aware result, the unchanged AnswerPlan adapter accepts the metadata and reports status="witnessed", witness_ids=[P2], but still emits operand IDs [P1,P2]. Passing metadata parity therefore does **not** establish wording/evidence alignment.

Do not patch ParentClaims/AnswerPlan in v8 integration. In particular, keep the legacy unversioned helper used by ParentClaims separate from the new version-routed proof selector; changing it globally would hide the error while leaving representative values misaligned. Do not suppress the exception, fabricate a witness, relabel a v8 artifact as v7, or force a candidate representative to make Layer C appear compatible.

The bounded implementation can qualify Layer A/B and retain explicit failing Layer C characterization for synthetic changed cases. It must not claim general v8 end-to-end answer readiness or run a live answer demonstration. The real parity corpus can still pass existing downstream construction because no relevant semantic inputs change. I4-4 must resolve the known synthetic handoff before general candidate-aware answer use is declared safe.

## 10. Independent real prospective result

The new in-memory oracle revisited **all 46 instances across 13 requirements**, not only the 40 I1 relations. It constructed 51 eligible support views: ten evaluated-candidate views and 41 filled legacy views. It found 11 engine joint proofs and nine I1 proofs (20 total); multiple common proposition aliases account for proof counts exceeding witnessed-instance counts. There are still eight witnessed I1 instances.

| Measure | Accepted v7 | Proposed semantics projected without new wire fields |
|---|---:|---:|
| Evidence-role states | 10 filled, 16 missing | identical |
| All role-state changes | — | 0 |
| Requirement-state changes | — | 0 / 13 |
| I1 Boolean changes | — | 0 / 40 |
| I1 witness-ID changes | — | 0 |
| Joint/completeness changes | — | 0 / 46 instances |
| Nonempty direction observations | 6, all relation-ineligible | identical |
| Effectiveness observations | 0 | identical |
| Recovery targets | 48 | 48, exact comparison passed |
| ParentClaims | 17 | 17, exact comparison passed |
| AnswerPlan nodes | 9 | 9, full plan comparison passed |
| Rendered Layer 1 | accepted | exact comparison passed |
| Answer invariants | 33 passing | same 33 passing |

All six real direction observations use legacy own evidence in c5/c6; the new local candidate scopes add no real observation. c3's second retained candidate and four c8 retained interpretations remain excluded; no view is created for them. c10/c12 remain candidate-empty. c9 retains five missing scale pairings. c8 remains open-list/partially-filled.

The oracle recomputed selected observation outputs and requirement summaries, then passed the semantic projection through unchanged recovery, ParentClaim, AnswerPlan and rendering machinery. It asserted equality with the fresh accepted v7 replay at each stage. It did not merely assume downstream parity from witness counts.

This is a **prospective semantic projection**, using explicit v7 dispatch for inherited classifiers/downstream machinery because no v8 code exists. It is not a v8 replay. An implemented v8 artifact will differ through semantic identity, support/proof registries, joint receipts and observation provenance. No v8 hash is proposed or frozen here.

## 11. Synthetic preregistration and observed planning checks

The following expectations are normative for I4-3C. “Observed” means the separate in-memory oracle exercised unchanged validators/classifiers over audit projections. It is not a passing production v8 implementation suite.

### 11.1 I4-3A A–K and L permutations

All views are eligible/resolved unless X=guard+policy excluded or ?=attachment ambiguous. A single list is paired with legacy sibling P2. Multiple lists are required own roles.

| Case | Candidate lists | Expected truth | Permutations checked | Successful I1 proofs per permutation |
|---|---|---|---:|---:|
| A | [P2] | true | 1 | 1 |
| B | [P1] | false | 1 | 0 |
| C | [P2,P1] | true | 2 | 1 |
| D | [P1,P2] | true | 2 | 1 |
| E | [P1,P3] | false | 2 | 0 |
| F | [P2 X,P1] | false | 2 | 0 |
| G | [P2,P1 X] | true | 2 | 1 |
| H | [P2 ?] | false | 1 | 0 |
| I | [P1,P2] × [P2,P3] | true, exact P2 pair | 4 | 1 |
| J | [P1,P2] × [P3,P2] × [P4,P2] | true, exact P2 tuple | 8 | 1 |
| K | [P1,P2] × [P2,P3] × [P1,P3] | false, no global ID | 8 | 0 |

L is every independent per-role list permutation above, including all reversed. **33 executions**, with identical truth, support-view-ID sets and proof-ID sets across each family's permutations. The six extra I4-3A families—empty, only excluded, ambiguous matching plus eligible nonmatching, guard-only matching exclusion, policy-only matching exclusion, ambiguous+excluded—add nine executions: **42 total**, all expected false.

These remain consumer-boundary fixtures. The current unique-sibling collector filters P1 before candidate construction when the sibling allows only P2; I4-3C must not broaden collection to manufacture these cases. The same-P2 multi-assertion fixture below is actually produced by the current binder.

### 11.2 Additional closed expectations

| Case | Expected result and audit observation |
|---|---|
| Same P2, opposite eligible assertions | Two proofs and two eligible directions; conflict/no consensus in both candidate orders. Current v7 binder emitted both records. |
| Same P2, two distinct same-sign assertions | Two direction observations, positive consensus; never dedupe by sign/proposition alone. Both orders checked. |
| Same physical own assertion, two contained inherited alternatives | Two I1 proofs, one physical direction/effect result with two provenance paths. Both inherited orders checked. |
| Inherited beta/delta alternatives; only beta in own quote | One I1 proof, beta selected regardless order. Direction comes from successful extension; effectiveness stays independently scoped. |
| Candidate-backed inherited role | Remains inherited in every view; two all-inherited roles still fail I1 despite engine <2-own bypass. |
| Candidate own + legacy own | Compatible P2 proof succeeds; legacy policy is not reevaluated. |
| Positive first clause + excluded negative coordinated clause | Only positive local observation. Sentence/proposition/unit expansion produces conflicting_signs and is rejected. Both candidate orders checked. |
| Local achieved/null assertions | supported + not_supported effectiveness from separate local flags, independent of I1 gating and candidate order. |
| Present all-ineligible list with stale filled legacy fields | Zero views/proofs; no fallback. |
| contract_directed_links without context | Zero link proofs; do not fabricate attachment pieces. |
| OR, only second verifier succeeds | Explicit supplied XYZ context with disjoint IDs permits links after same_proposition fails; reversed verifier case permits same_proposition after contextless links fails. |
| OR, both succeed | Two completion proofs with distinct join bases; I1 has its own one verified proposition proof. |
| Duplicate verifier name | One deduplicated proof, same truth. |
| Identical candidate duplicate | One support/view; no duplicate observation. |
| Same grounding identity, conflicting eligible/guard payload | Raise before filtering; never silently keep whichever occurs first. |
| Unrelated candidate insertion | Existing fixed-placement support/view references remain unchanged. |
| Different placement | Different support reference. |
| Candidate with no assertion span | May prove shared ID; no candidate-local observation; explicit unavailable-locator diagnostic. |
| Legacy no support IDs | One empty-support legacy view; no common-ID proof. |
| Legacy own null text, valid IDs | Historical structural proof can still succeed; no invented operand wording. |
| Non-representative proof, unchanged Layer C | ParentClaim raises; old I1 metadata parity disagrees; shared proof-aware I1 still leaves representative AnswerPlan operands. Preserve as characterized limitation. |

The oracle ran **23 additional scenario executions**, seven explicit identity/edge-condition assertions, eight offset-transport inputs, the four-way scope probe and the downstream/recovery characterizations. Multi-candidate added scenarios were checked in both orders; singleton cases have one ordering. All stated oracle expectations passed.

Implementation must additionally pin the normative wire schemas, quote/attribution hash mismatch, out-of-range spans, alias coordinate mismatch, support-ID order normalization, duplicate proof conflicts, stale bundle inputs, incomplete/alternative/optional/category participation, missing legacy inherited text, valid/invalid continuation anchors, link-only observation emptiness, same physical aliases versus distinct-source equal text, and full historical version isolation. These are **preregistered acceptance cases**, not falsely reported as tests of code that does not yet exist.

## 12. Exact version routing and module ownership

### 12.1 Smallest module decomposition

Add **one** future pure module, `compatible_witness.py`, because two distinct existing consumers need the same adaptation/identity/assignment authority. Keep historical engine APIs intact; use explicit v8 wrappers rather than changing unversioned helper meaning globally.

Dependency direction:

```text
sufficiency_engine v8 wrapper --local import--> compatible_witness
relation_witness v8 wrapper -----------------> compatible_witness
compatible_witness -------------------------> sufficiency_engine validator only
compatible_witness -------------------------> contract_directed.links extractor only
sufficiency_diagnostic ----------------------> proof/basis output
sufficiency_mapping observation adapter -----> selected scopes + unchanged classifiers
```

The engine's import must be local inside its v8 path after module initialization to avoid a module-import cycle with the engine-owned evaluated-candidate validator. The helper must not call back into engine recomputation, mapping or the legacy witness helper. I1 supplies existing pure verification/containment predicates; the helper does not import relation_witness. A narrowly typed frozen predicate/rule descriptor is required; do not accept arbitrary dynamically imported plugins.

Keep observation locator/path handling in bounded functions beside the existing observation construction in sufficiency_mapping, with diagnostic orchestration selecting the v8 entry point. It consumes already-selected bases/proofs and support-record locators, never candidate lists. This avoids moving support_policy, assertion_authority or historical classifiers. If file-size tooling later requires extraction, stop and identify the concrete boundary; no directory-wide import permission is implied.

### 12.2 Supplying context before parent eligibility

Engine recomputation currently lacks child/sealed context. Add an explicit optional keyword `witness_context` only to the future versioned recomputation/mapping path. It contains caller-owned child_id, requirement_id and immutable sealed proposition index; per-instance placement adds the final instance_key. Do not overload the existing verifier `context.attachment_pieces`, infer child IDs from strings or use global state.

Thread through compute_diagnostic_sufficiency_map → map_any_requirement → map_requirement / map_cardinality_requirement / map_paired_requirement → recompute_requirement → recompute_instance, including the category-v4 helper's final recomputation route. v8 requires this context; explicit v1–v7 must ignore/not inspect it. No classifier input, candidate collection, model prompt, nominated scope or source-unit identity changes.

Final fork keys already exist at the mapper's recompute call. Construct support views/joint proofs there so complete is correct before child pairing. Finish I1 proofs and observation bases with sealed verification in the diagnostic's existing post-mapping witness pass. Registry IDs exclude late model-origin annotations as specified in §4. Validate the completed bundle before stamping/export.

### 12.3 Closed behavior routing

Recommend explicit `SUFFICIENCY_SEMANTICS_V8 = "sufficiency-semantics-v8"` in the implementation only. V8 inherits the v7 mapping/policy path explicitly; do not use lexicographic version comparison, numeric >=7, or “anything newer” fallthrough.

| Module / boundary | Future allowed change |
|---|---|
| sufficiency_engine | V8 constant/support/current tables as explicitly authorized; v8 joint wrapper/receipt and context threading. Old helper bodies and all v1–v7 branches retain behavior. Role aggregation, quantifiers, category and stop-search algorithms unchanged. |
| sufficiency_mapping | Route v8 achieved outcomes to the exact existing v7 collector/annotation/evaluator path; thread witness_context; add aligned observation entry points. No collection/relevance/guard/policy changes. |
| relation_witness | Explicit v8 wrapper delegates to shared views/proofs; add v8 casefolded containment table entry. Legacy witness algorithm remains exact. |
| sufficiency_diagnostic | Pass immutable witness context, finalize bundles; v8 observations consume bases/proofs. Historical paths neither construct nor serialize new fields. |
| direction_target | Add only explicit v8 dispatch to the unchanged no-fallback rule. No grammar, stem, sign or target changes. |
| sufficiency_recovery_targets | Add explicit v8 membership to existing inherited category/version routes only. No recovery algorithm or representative search-context change. |
| sufficiency_identity | Existing current/historical logic reads engine constants; no relaxed identity checks or forged historical stamping. |
| e2e | Only explicit v8 membership/context transport where its existing saved ownership/recovery routes enumerate versions; no live run, prompts or orchestration redesign. |
| support_policy, assertion_authority, ownership_context, achieved_outcome_span, target_relevance | Unchanged. |
| parent_synthesis_ledger and answer_plan/** | Unchanged implementation. Layer C limitations remain characterized, not repaired by extending legacy helpers covertly. |
| PLAN_VERSION / frozen authored contract | Unchanged. |

Before activation, implementation must inventory every closed v7 membership site again and account for it by name. The audit found such branches in mapping, diagnostic, engine, direction_target, relation_witness, recovery and e2e. Adding v8 to one classifier table does not authorize changing its rule.

v8 CURRENT activation and unrestricted answer-product readiness are different decisions. This bounded design permits implementation/qualification of the explicit v8 A/B path; it does not permit bypassing the documented Layer C failures to make a global production-default switch appear safe. If the next implementation instruction requires current-default activation before I4-4, it must explicitly acknowledge that boundary and the resulting legacy-consumer limitations. The implementation must not silently change existing new-run behavior as an incidental consequence of adding the constant.

## 13. Exact static/purity guard plan

Use AST/call-site guards with named files/functions, not directory exemptions.

| Guard | Exact allowance / rejection |
|---|---|
| Candidate-list reads added for witness work | Only compatible_witness.build_support_views and its private identity/validation helpers may consume candidate_supports. Existing engine aggregation and mapping collection/projection/annotation reads remain unchanged. No new candidate-list reads in diagnostic, direction, ParentClaims or AnswerPlan. |
| Selector imports | Direct standard-library allowlist: __future__, collections/collections.abc, copy, hashlib, itertools, json, typing. Project imports: sufficiency_engine evaluated-record validator; contract_directed.links existing designator extraction only. Reject model/qwen, retrieval, library, SQLite/SQLAlchemy, HTTP, filesystem/process/time/random APIs and dynamic import. |
| Helper callers | sufficiency_engine's named v8 recompute wrapper, relation_witness's named v8 witness wrapper, sufficiency_diagnostic's named v8 bundle/base orchestration only. Observation construction reads selection output; it does not call a candidate selector. Test files explicitly named for I4-3C may call helpers. |
| No policy re-evaluation | compatible_witness cannot import support_policy or assertion_authority and cannot call mapping binders/evaluators. Engine validator may validate an existing evaluation record; it must not run policy against the triple. |
| No duplicate adaptation | Static test rejects candidate.admissible/attachment filtering added in direction/diagnostic/answer modules. Their authority is selected view/proof references. |
| No representative-first observation path | v8 observation functions cannot call _bound_surfaces or _project_evaluated_supports, nor use next(candidate...) to choose evidence. Historical diagnostic branch may still call _bound_surfaces. |
| No provenance union writeback | Snapshot input bindings/candidates before selection; assert deep equality after every call. AST guard rejects writes to binding.provenance.supporting_proposition_ids in new helper/wrappers. Registry-local sorted sets are allowed. |
| No new verifier | Assert RELATIONSHIP_VERIFIERS and _VERIFIER_FUNCS keys remain exactly same_proposition and contract_directed_links; target_relevance primitive remains unregistered. |
| No Layer C workaround | Diff/static guards prohibit production changes under answer_plan/** and parent_synthesis_ledger.py. Their calls to the legacy helper must not acquire implicit v8 semantics. |
| Historical shape/dispatch | For explicit v4–v7, spy forbids new adapter/selector/observation functions; replay hashes exact; no witness_bundle/joint_grounding/witness_proofs/evidence_alignment fields. |
| I/O purity | Monkeypatch file/network/model/database entry points to raise during pure-helper tests; AST import checks protect direct and transitive reachable calls. Existing pure links dependencies are inspected, not granted access to the whole contract_directed directory. |
| Immutable classifier boundary | Hash/AST comparison freezes actual direction classification and effectiveness predicate/flag logic. Only explicit version membership and local scope transport may differ. |
| Reference integrity | Reordering and unrelated insertion preserve fixed-placement refs; conflicting duplicate payload fails before filtering; repeated proofs only merge provenance paths. |

The existing assertion-authority/grounding static allowlists need no new consumer: this design does not import those modules from the selector. Any test-only oracle imports must remain confined to the explicitly named test modules.

## 14. Bounded implementation readiness and stop

**B28: one bounded atomic v8 A/B implementation is safe; splitting activation into Boolean first and observations later is unsafe.** Internal development can stage pure support identities/selection tests, then proof serialization/observation alignment, then explicit version routing and offline replay. None of those intermediate stages should become a separately active semantic version.

**B29: READY** for that implementation with the frozen acceptance gates. No unresolved choice remains about support eligibility, source classification, participation, common-ID assignment, verifier OR, candidate observation scope, negation source, proof storage or legacy adaptation. Exact code layout can follow the named seams without another architectural planning increment.

Readiness is bounded: general Layer C consumption of newly changed synthetic relationships remains **NOT READY**. Preserve its existing failure/representative limitations; do not patch it during I4-3C. An implementation receipt must distinguish A/B correctness from end-to-end answer qualification and explicitly resolve current-default activation under the next instruction's authority.

**B30 — recommended next increment:**
**PHASE 34 / I4-3C — V8 compatible-witness proofs and aligned observations: bounded integration and offline qualification.**

Required gates for that increment:

1. Normative support/proof/observation schema validation and all preregistered cases in §11, including malformed input and every permutation.
2. Exact historical v4–v7 hashes and byte shape, plus no historical calls into the new selector.
3. Real prospective v8: unchanged role/requirement/witness/direction/effect/recovery semantics; separately report additive proof metadata and version changes.
4. 48 real recovery targets, 17 real ParentClaims, nine plan nodes and 33 invariants remain intact; synthetic Layer C limits are recorded without workaround.
5. Same-P2 opposite assertions produce both observations and conflict in every order; same-sign distinct assertions remain distinct; duplicate proof paths merge.
6. No guard/policy/attribution/classifier/collection/quantifier redesign, no new verifier, no PLAN_VERSION or Layer C source edits, no claim-goal/authority-veto semantics, no live retrieval/model/E2E.
7. Only then freeze an actual v8 replay artifact and implementation receipt under separately authorized version routing. No v8 baseline exists in this design increment.

**STOP after I4-3B.** This report and the lineage append are the entire authorized change set. No v8 code, I4-4 or I2-3 begins here.

## 15. Verification receipt

| Replay | Fresh rerun SHA-256 | Result |
|---|---|---|
| v4 | `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a` | exact frozen baseline |
| v5 | `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77` | exact frozen baseline |
| v6 | `dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be` | exact frozen baseline |
| v7 | `04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72` | exact frozen baseline |

Input verification uses the existing test_i4_2a_replay.inputs ledger/map SHA checks and test_i4_2b3_replay.context packet hash check. Replay bytes use the existing sorted JSON UTF-8 CRLF convention. Four-version replay ran twice while finalizing the observation-path rule; both sets matched.

The independent oracle inspected all 46 instances, with 51 eligible views and 20 successful relationship proofs. It reconstructed observation scopes and reran downstream recovery/claims/plan/render checks on the semantic projection; no deltas. There is no version-stamped v8 artifact and no claim of byte equality after future proof metadata.

Planning checks: 42 original/exclusion permutation executions, 23 added scenario executions, seven identity/edge assertions, eight sentence-offset probes, scope expansion comparison and explicit parent/recovery/AnswerPlan limitations. These checks characterize the design and unchanged functions, not implemented v8 behavior.

No external search, live retrieval, model call, live E2E, production edit or full-suite run occurred. Only this Markdown design and one append to CONTRIBUTION-LINEAGE.md are materialized.
