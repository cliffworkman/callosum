# Phase 34 / I4-4C — pure Layer C validation/reference substrate results

Date: 2026-10-10. OTR prerequisite implementation; **no consumer activation**.

Canonical branch: experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z.

Accepted I4-4B docs checkpoint, committed and pushed before implementation:
**396e7c396ca035bf1d5993bd78861d3bd7ca379c**. Implementation began at that clean HEAD.
Entry inspection found only the two authorized documentation changes. They are separate from this
implementation commit. Final implementation HEAD is the single commit containing this report;
resolve it with git log -1 --format=%H -- experiments/ask_cli_revised/PHASE34_I4_4C_LAYERC_VALIDATION_REFERENCE_SUBSTRATE_RESULTS.md.
Its full SHA is reported in the completion response; a commit cannot embed its own resulting hash.

**Readiness: READY for separately authorized I4-4D consumer integration**. This does not authorize or start I4-4D.

## Delivered boundary and API

Only five new pure production modules were added under experiments/ask_cli_revised:

| File | Responsibility |
|---|---|
| layerc_projection.py | Sole public validation/projection authority; exact profile/input binding; immutable output |
| _layerc_common.py | Canonical hashes, immutable records, exact display envelopes, pure future semantic claim-ID helper |
| _layerc_validation.py | One-pass retained payload index; stored support/view/gate/proof/join/context validation |
| _layerc_observations.py | Stored bases, alignment, physical spans and summary-reference validation/transport |
| _layerc_values.py | Closed value adapters, category references, value-specific permissions and scoped grouping |

No existing production module was edited. ParentClaims, AnswerPlan, renderer and ordinary e2e
paths do not import/call the substrate. Existing witness selection, classification, policy,
guards, recovery, role/category states and rendering are untouched.
Current/default remains sufficiency-semantics-v7 and answer-plan-step2-v4.
V8 stays supported_noncurrent and nonhistorical; no sufficiency v9 or plan-v5 activation.

~~~python
validate_layerc_inputs(
    smap, sealed, authored_contract, *,
    profile, optional_context_receipts=(),
) -> LayerCProjectionV1
~~~

sealed is the original UTF-8 artifact **bytes**, so its byte digest is actually checked rather
than accepting a hash for unavailable bytes. authored_contract contains requirements (child-keyed
authored requirements without runtime instances/state/reason/summaries) and overlay.
The test adapter supplies preserved inputs; it is not new runtime authoring/routing.

LayerCProjectionV1 is a frozen dataclass with schema_version, projection_id and recursively
immutable mapping/tuple registries. Outputs are detached. No mutable candidate arrays, duplicated
whole witness bundles or rendered prose are exposed. Literal assertions/source passages remain
stored evidence, not newly realized prose.

## Exact profiles and registries

Input profile: **v8-layerc-v2-plan-v5**, validation/projection only in this increment.
It binds exact supported_noncurrent/v8 identity; map hash; sealed artifact bytes; sealed proposition
index; authored requirements/overlay identities; ordered context manifest; v8 containment/direction;
producer identity/output-map receipt and authorization digest. Unknown/mixed/stale profiles reject.

| Input | SHA-256 |
|---|---|
| canonical map | e1c6d1027c96098dce96b7c86ee9259d1c50e379845c1d9bb3adeb62ba00b8cf |
| sealed ledger bytes | a70409e8f5a0937f414c73c4796b293c6c1a9ef3b31c7fc83bbfa61794c6bd5d |
| sealed proposition index | c33b1aab85ff01a38522827a41bc62cab5e378444291b89ca425c683a783d6f3 |

Hashes establish consistency with caller-supplied authorization, not cryptographic authenticity.
Authenticating producer/authoring authorization remains the caller's responsibility.
Stored-path soundness is validated; completeness of the producer's possible-assignment search is
not claimed, because proving it would require forbidden reselection.

Projection schema: **layerc-validated-projection-v1**. Real registry counts:

| Registry | Count |
|---|---:|
| placements | 46 |
| role_specs | 25 |
| support_records | 56 |
| support_views | 51 |
| eligibility_receipts | 2 |
| candidate_metadata | 15 |
| candidate_metadata_by_support | 15 |
| category_observations | 7 |
| proofs | 20 |
| observation_bases | 45 |
| observations | 6 |
| summaries | 3 |
| semantic_values | 41 |
| value_coverage | 51 |
| value_paths | 41 |
| sources | 71 |
| display_envelopes | 71 |
| link_context_status | 0 |
| link_context_records | 0 |
| grouping | 25 |
| diagnostics | 0 |

Exact projection ID: layerc-validated-projection-v1:sha256:13f2174081d418d3ec7ef1fd72fc118d0c485f6f8f9503c150147a61eb4472fa.

The 41 total value IDs are **32 own claim-member values plus nine distinct inherited values**
across 13 inherited placements. All 51 filled placements retain receipts: 38 own and 13 inherited.
The 25 grouping records are scoped role/quantifier descriptions, not production ParentClaims.
Five exclusions are diagnostic_only metadata, not eligible views. The real corpus has no link-only
proofs; generic fixtures cover them.

## Reference validation and scientific boundary

Each binding's retained candidate payloads is indexed once, for exact resolution only. No ranking,
alternative assignment search, Cartesian products, missing-view repair or proof construction.

Stored supports/views are checked against canonical ID material, placement, source identity,
quote hashes, assertion/predicate/content bounds, exact text, payload hash, eligibility receipts,
outer own/inherited source and operand/locator/provenance refs. Engine-owned
validate_evaluated_candidate_support validates stored schema/gate arithmetic; it does not execute
a support-policy predicate. This is the only allowlisted sufficiency-engine import.
Guard identities and policy snapshot/source/identity are compared with authoring without evaluating
the evidence triple. Stored role-state/gate consistency is checked, never written back.

The preserved ledger reuses extraction-local (paper, chunk, span_id) labels for different text.
Resolution includes the **existing exact quote hash**, not a last-row catalog winner or arbitrary
passage. Every referenced real proposition resolves. This corrects an initial overly broad
uniqueness assumption in the new validator; it changes no sealed input or scientific semantics.

Stored proof checks include:
- Canonical body ID, schema/version, placement, purpose/verifier, participating roles and selected tuple.
- Own joining-PID membership; sealed verification/continuation receipt equality.
- Existing casefolded canonical full-quote containment for the selected inherited referent.
- joint_grounding and witness_proofs membership, frozen prerequisite/status consistency and I1 IDs/truth.
- Stored shared-designator operands/context hash using the existing closed extractor, never link discovery.

Observation checks include basis identity/placement/own assignment; completion/I1 membership; exact
operand refs; alignment ID; physical source/assertion/observation bounds; raw/normalized text hashes;
selected path/proof/source membership; and summary-reference consistency. Stored summaries and
aligned observation IDs survive in the projection. No direction, effect or category classifier is
rerun; no summary conclusion is recomputed or changed.

No alternate scientific assignment is selected. Completion and I1 remain separate.
Inherited support stays inherited; parent-origin proof never becomes child relation authority.

## Excluded candidate metadata

candidate-metadata-v1 binds map_sha256, exact child/requirement/instance/role placement and normalized
candidate_payload_sha256, with reverse support-ref resolution. All 15 retained real payloads resolve.
The payload preserves relation, aggregation, kind, authority_veto, is_caption, attachment ambiguity,
guard exclusions, policy snapshot/source/failures, text/spans and attribution proof/context/ruleset refs.

Five exclusions remain diagnostic_only with no eligible view, semantic value or positive path.
Conflicting same-ID payloads, contradictory gates, unauthored policy/guard identities and stale refs
fail loudly. Identical duplicate paths normalize. Exclusion in an unrelated role is not a global veto.

## Category authority and exact p8/p36 receipts

category-observation-ref-v1 hashes schema, full placement, exact observation body, source_identity
(paper/chunk/span), and quote_sha256. The enclosing sole category role, authored exact term,
instance identity, stored polarity/ambiguity/classifier/audit/guard and sealed passage are validated.
No category is inferred from text. All seven real observation IDs match I4-4B exactly.

| Value | Selected binding/view | Scientific goal / reported finding | Positive scientific coverage | Authorized display/citation inputs |
|---|---|---|---|---|
| c3 explicit | p8 unchanged | established / positive_finding | scoped positive observations p8,p36,p52 | those three inputs; future presentation-ready path preregistered as p36 |
| c3 implicit | p36 unchanged | unestablished / null_finding | none for positive presence | its own selected p36 null observation |

Explicit selected view:
support-view-v1:sha256:b7b8cfa3588ca88c87e30c5f4031a9d764a70147a99f0bdc423cf4296fdfb04b.

Implicit selected view:
support-view-v1:sha256:a01b445f6091ab1e379587d05b331a8e9d8c3bf945a4a2391109756a2f488913.

Explicit p36 observation:
category-observation-ref-v1:sha256:354a9a5e01c3ebfb147ba25e1c6c7cbf38d450272ea273262f793783c501d110.

Implicit p36 observation:
category-observation-ref-v1:sha256:00d5a665483085e7f8771d1de013a285832773505751207797273270450f7b55.

No p36 view is created for explicit; no binding/support set is rewritten. The two observations
are independently scoped facts on one physical source, not claim-wide borrowing.
Unknown/mentioned/ambiguous observations cannot become positive coverage. Null reporting does
not establish presence, change requirement satisfaction or close recovery.

## Coverage authorization versus presentation

value-coverage-v1 includes typed establishment_refs, scientific_coverage_refs, typed_reporting_refs,
authorized_display_source_refs, citation_source_refs, relation_proof_refs, aligned observation_refs,
role/instance state, scientific_goal_state, reported_finding and typed limitations.

Templates carry presentation.finalization_required=true and required checks. They have **no final
display_state** and introduce no unreviewed pending scientific state. I4-4D executes presentation
checks on these exact authorized inputs; it may restrict paths but cannot add evidence edges.
Authorizing p8/p36/p52 does not claim all are display-ready. The fixture independently freezes
p36 as the final explicit display/citation expectation.

Established science plus unavailable display stays established. Null reported is not positive
presence. Source permissions have exact placement/ownership/locator/gate refs. A flat claim-wide
citation union never establishes a member's coverage.

## Values, grouping and exact IDs

Dispatch is solely strategy plus validated shape:
named_instrument_lexicon, achieved_outcome_predicate, explicit_category_terms,
direction_or_sign_pattern, model_nomination_only.

Kinds are authored_category, literal_value, evidence_slot with independent stored-proof operands,
literal_assertion when no independent named value exists, and value_unresolvable diagnostic.
Unknown strategy rejects. Unresolvable values retain refs without invented labels or representative
fallback. No domain/role-name inference or cross-study entity resolution.

Exact own classes: **19 literal_value, nine evidence_slot, one literal_assertion, three authored_category**.
Zero real unsupported mappings; all inherited placements accounted for.
Canonical JSON uses UTF-8, sorted keys, compact separators, ensure_ascii=false, allow_nan=false.
New IDs retain full SHA-256. Value identity excludes evidence/proof IDs, instance keys,
representative PID and discovery order. Exact literals enter only when they are semantic values.

| Alias | Kind | Exact semantic value ID |
|---|---|---|
| V01 | literal_value | semantic-value-v1:sha256:71e539b97612a8e6b7c55805d777aa625355908b317a8657322a26f331a2dd08 |
| V02 | evidence_slot | semantic-value-v1:sha256:dfb887dc4970e0245a4f3f7b0c85ae39d7c3a6e7a8607c0da71b5a86f7052d00 |
| V03 | literal_value | semantic-value-v1:sha256:3fcebcec37ff6f5b014a578c90da202ed158c969a2ab9b8fd6363c18ddebe25c |
| V04 | evidence_slot | semantic-value-v1:sha256:751e23ed92b57b22709dd30b7adb5b6e928f5cb5f87aca818d592ed254d878da |
| V05 | evidence_slot | semantic-value-v1:sha256:02e3471955ebe76fd628662fd3be9bb03341d58f7678b0bd24222fe1783e4689 |
| V06 | literal_value | semantic-value-v1:sha256:c71d74c74520515a44822188e345418c1546cb83e49d8f910e2a448c3be81067 |
| V07 | literal_value | semantic-value-v1:sha256:e29229098dae6fa5dc269d953ad2b2c3a070e02fa88dd39647956dde5972de93 |
| V08 | evidence_slot | semantic-value-v1:sha256:0010d9051d1776feefd833e762303a1b5e1fc5b031202b6af75add7496d1a82f |
| V09 | evidence_slot | semantic-value-v1:sha256:9871c85eb64726c5b1394e3051e8e6f7e5e6013311fc846e8ec4f11d885d7587 |
| V10 | literal_value | semantic-value-v1:sha256:637bdfd2f6c67012d4617655bd7c09e1a13d615b207f3185916e625f4eabe595 |
| V11 | evidence_slot | semantic-value-v1:sha256:1d84fca93f15e3cbf8dfce00c41e153e7e957ded16c6477f9babc664b119a162 |
| V12 | literal_value | semantic-value-v1:sha256:8c3e973976d23a8472f3f094b9b1ed52cd7f012e33e84a0eedd306add0422f20 |
| V13 | evidence_slot | semantic-value-v1:sha256:15046f1f6a3546697d0c77fde5d61e70e19eded91538b4aaac6bb14d65e8f902 |
| V14 | literal_value | semantic-value-v1:sha256:c2247677d32bf4a9e3ab39db7d2e1cf63ba398f24258302bdf19afa2a448c46c |
| V15 | literal_value | semantic-value-v1:sha256:52de78a144af120d61898d196d1ffbca88c38e71a7f3de2c7cb735679f2adcdc |
| V16 | evidence_slot | semantic-value-v1:sha256:0a612abee98c488f11ecaef9b20538d3a2050125d5dc06f8acc78a1bef0f0608 |
| V17 | evidence_slot | semantic-value-v1:sha256:972f2149ad56f9a9d9e28f17eed71fcb2181e5ef6d0e92d5bec12c80eb9228d3 |
| V18 | literal_value | semantic-value-v1:sha256:a4e6cf453349208936e627f051220b0cf0736d4cb37c658f8e65814f943ca8d5 |
| V19 | literal_assertion | semantic-value-v1:sha256:20ab47f0575592ac3519357d1ce20dd537f68e8caa32384b0f1bf8dabe4e171f |
| V20 | authored_category | semantic-value-v1:sha256:0b2d5d6507dbbc6f6d0212b7cc0411c9be3d2663cc7798295605d85659716980 |
| V21 | literal_value | semantic-value-v1:sha256:ec620d2e915553dd9fc9bb83a0dc3330247d83aa357b1ff02ccaedd9e59eba7b |
| V22 | literal_value | semantic-value-v1:sha256:236ced83cf41481eb76b7733518a532c21bc2d2f4b808530c35c01e5c8d6dbc9 |
| V23 | literal_value | semantic-value-v1:sha256:f6dcd8bfe866cd5c62411674f25e50d2ad99279174bd34a1f3b5b183e8d2edba |
| V24 | authored_category | semantic-value-v1:sha256:8eb2403f24906e5a891c736b9c91bd3b29610c9a46866a1685e7105c656a6ea0 |
| V25 | authored_category | semantic-value-v1:sha256:bc62af4f96a9b58b0d2cd5c38de50473a465baf5e23665a718971518907978c5 |
| V26 | literal_value | semantic-value-v1:sha256:460dfdd5d724ad401ae421c98262ddea836c1e1b51a50946652c9f0331455992 |
| V27 | literal_value | semantic-value-v1:sha256:67404b8a0b0b338af1eb1440bb7fd438174e8050771d99bfef940924f67c7d29 |
| V28 | literal_value | semantic-value-v1:sha256:be4fdda9a1c7a097f7098d7333cb28702273ade4921d78726b0289e720ec89d4 |
| V29 | literal_value | semantic-value-v1:sha256:13da9580be9944534392f504551b6bad7cad0d7c54e9eacbbc97d46957d1187e |
| V30 | literal_value | semantic-value-v1:sha256:c7fe32e9c37b15c9bc91fe0261f24cf922eac5561a5dcff7463bcb916b5ecf4b |
| V31 | literal_value | semantic-value-v1:sha256:565e311eb69e7038959dbae8cbf58c07f808b1c2e310671c8f87732b2d46c0ce |
| V32 | literal_value | semantic-value-v1:sha256:4d66f019291fc331bfcbd04fd731c2117a9840421ea7db303023dbe9a657e72e |

Same value in one grouping scope merges membership, not evidence paths. Hadza has one member/two
paths; Explicit Bias Questionnaire one member/four placements. Different authored category/role
scopes stay separate. at_least_n remains excluded from the list fold; no map cardinality recomputation.

Pure parent-claim-v2 helper implements the closed {schema,family,scope,content} identity for all
four future families. It does not build production ParentClaims. C01–C17 canonical materials and
computed helper IDs are frozen in the fixture; hashes are generated from material, not invented.
Evidence/receipt/path/display changes are excluded from semantic claim identity.

## Envelopes and links

display-envelope-v1 keeps evidence_span separate from display_span, with source/hash,
added intervals/bytes, wrapper rule IDs and semantic_support_added=false.
Only adjacent whitespace or an immediately adjacent authentic period without an alphanumeric
continuation may be added. No search ahead for a later period.

"Nevertheless, we found …" yields the selected "we found …" assertion and eligible terminal period,
not the discourse prefix. Results/owner/caption prefixes, coordinated/semicolon/colon second clauses,
external statistics/citation markers and quotation wrappers are not added. Legacy whole-unit scope
remains explicitly legacy. Wrapper bytes cannot support another value.

Shared-designator context:
- Missing bytes: narrow stored proof/selected operands retained; context_unavailable; no joint quote.
- Unique hash match: context-only reference; citation additionally needs valid supplied sealed locator.
- Identical contexts deduplicate.
- Hash mismatch/contradictory referenced locator fails; no first-context selection.
- No invented PID, I1 witness, common proposition, effect or causal statement.

## Fixtures and future state contract

layerc_i4_4c_preregistered.json contains all 32 exact value IDs/materials, selected placements/views,
category bodies/refs, all C01–C17 members and canonical identity materials, inherited placements,
per-member authorized inputs versus future display expectations, A–R matrix and nine-node fixture.

| Node | Future report_state (not activated) |
|---|---|
| 1 | partial |
| 2 | partial |
| 3 | answered |
| 4 | partial |
| 4A | not_established |
| 4B | partial |
| 5 | partial |
| 6 | not_established |
| 7 | not_established |

Node 3 separately records answered reporting coverage, both covered categories, category scientific
goal incomplete, implicit unestablished/null_finding, explicit established/positive_finding and
persistent recovery. Typed reasons/facet axes are frozen. The substrate computes no future plan state.

## Qualification

New substrate battery: **92 passed**. It exercises the real IDs and every claim/member selected
path, category authority cases, A–R permissions, 14 envelope probes, null/unlocated values,
duplicates/physical-source distinctions, scoped labels, unknown strategies, payload/ref conflicts,
rehashed proof corruption, inherited containment, profile/context/gate mismatches, path order and
deep immutable inputs/outputs.

Static guards use narrow import/call allowlists; deny activation, selectors/classifiers/recovery/
I/O and input mutation; and check no candidate array escapes. Runtime spies deny I/O, selectors,
policy evaluation and category classification. Stored schema validation is explicitly allowed.
The first combined targeted run passed **312 tests**, including category satisfaction,
I4-3C witness/static/identity and all five frozen replay checks.
Final schema/reference refinements also passed the 92-test substrate rerun.

Final full offline experiments run on frozen code: **5,173 passed, five known failures,
12 skipped, nine xfailed, 276 subtests passed in 259.64 seconds**.
Zero unexplained new failures. The five failures below are unchanged baseline/environment issues,
not waived new regressions.

An earlier full run collected the old static allowlist before the last schema-validator refinement,
while its AST guard read the newer file. That mixed snapshot reported one extra static-test failure.
The frozen-code final run supersedes it. It was not bypassed or marked xfail.

Five baseline/environment failures were independently reconfirmed, with the relevant production/
test files unchanged from the docs checkpoint:
1. ask_070 test_dev_eval_separation: missing frozen/dev_inputs_v0.json.
2. ask_070 test_real_frozen_nonsemantic_artifact_schemas: missing frozen/corpus_presence_v0.json.
3. test_e2e_run dirty-tree smoke fixture: existing Ollama /api/tags probe refused by offline guard.
4. test_hierarchy_contract generated-pin verification: existing hierarchy_contract.py pin drift.
5. test_hierarchy_e2e preflight-only readiness: same pin rejection, return 3 rather than 0.

The optional psutil-dependent module test_run_gate_integration_live.py passed **7 tests** in the
dependency-complete Anaconda environment with the same offline guard. Its endpoint scenarios are
mocked/scripted; no live endpoint/model was contacted.

Exact combined replay hashes, unchanged:

| Profile | Exact SHA-256 |
|---|---|
| v4 | 4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a |
| v5 | 109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77 |
| v6 | dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be |
| v7 | 04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72 |
| v8 | 1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0 |

V8 remains the v8-map/legacy-Layer-C/plan-v4 characterization. No map gained projection fields;
no plan-v5 baseline replaced it. All 33 existing real downstream invariants pass.

Ignored receipts: .local/i4-4c/targeted.log/xml, substrate-final.log, full.log/xml (superseded),
full-final.log/xml, known-baseline.log, optional.log, projection-receipt.json, hooks.log.
run_offline.py loads the existing .local/i4-2b3/i4_offline plugin, denies sockets and sets model
libraries offline. Full invocation:

~~~text
.venv/Scripts/python.exe .local/i4-4c/run_offline.py experiments -q --tb=short
  --ignore=experiments/ask_cli_revised/contract_directed/tools/test_run_gate_integration_live.py
  --junitxml=.local/i4-4c/full-final.xml
~~~

Final staged-file hooks pass whitespace/EOF/conflict/large-file checks, Ruff formatting/lint,
Bandit and Tach. The sole failure is the unchanged pre-existing 615-line
app/frontend/js/20_synthesis.jsx file. Its git blob remains
03f9d3dfee3763533a78d5da601a99cb81bb37f1; frontend is untouched.
The user explicitly authorized --no-verify for this one implementation commit under exactly
that condition. No test, replay, authority or activation gate is bypassed.

## Exact change set and stop

Exactly 12 files under experiments/ask_cli_revised:
the five production modules above; test_layerc_projection.py, test_layerc_integrity.py,
test_layerc_matrix.py, test_layerc_static.py; layerc_i4_4c_preregistered.json;
this report; CONTRIBUTION-LINEAGE.md. No existing production module changed.
The accepted I4-4B docs are a separate preceding commit; implementation is one following commit.

**READY for I4-4D**, separately authorized: atomically integrate claim-v2/construction-v2/plan-v5
consumers of this projection, finalize existing presentation checks against its closed authorized
inputs, qualify the frozen 17-claim/nine-node contract and establish a separate explicit profile
baseline. The current substrate does not execute those consumers or final presentation decisions.
No scientific-map change is needed for this handoff; caller authentication of producer authorization
remains an integration responsibility.

STOP after I4-4C. No I4-4D, claim-v2/construction-v2/plan-v5 consumer activation, v8 promotion,
rendering/category/role/recovery/observation/selection change, same_local_assertion,
claim-goal/authority-veto behavior, I2-3, live retrieval, model/NLI or live E2E.
