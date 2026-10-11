# Phase 34 / I4-4D2 — proof-aligned claim-v2 + plan-v5 integration

Date: 2026-10-11. Scope: explicit offline consumer integration, with no promotion.
Readiness: READY for a separate I4-4E promotion decision; no promotion performed.

Starting HEAD: 8b2e1184c9cc9c9f313ebae30775f0cc05ec90aa.
The canonical experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z worktree
was clean when this increment began. Final HEAD is the single atomic integration
commit containing this report, with that starting HEAD as its parent. Its full ID is
resolved by `git log -1 --format=%H -- experiments/ask_cli_revised/PHASE34_I4_4D2_PROOF_ALIGNED_CLAIM_PLAN_INTEGRATION_RESULTS.md`;
the literal commit ID is reported after commit/push, avoiding a self-referential commit hash.

## Explicit profiles and unchanged defaults

| Route | Scientific identity | Layer C |
|---|---|---|
| Default | current / sufficiency-semantics-v7 | legacy claims/synthesis, answer-plan-step2-v4 |
| Profile A: v8-legacy-layerc-plan-v4-characterization | supported_noncurrent / sufficiency-semantics-v8 | unchanged legacy characterization |
| Profile B: v8-layerc-v2-plan-v5 | supported_noncurrent / sufficiency-semantics-v8 | parent-claim-v2, claim-evidence-v1, relation-unit-v2, parent-synthesis-v2, answer-plan-step2-v5 |

The existing supported-noncurrent flag alone stays on the legacy path. Profile B needs
an explicit profile selector and a snapshot containing the already enrolled receipt and
actual bound input bytes. The command uses
`python -m experiments.ask_cli_revised.answer_plan.replay --layerc-profile v8-layerc-v2-plan-v5 --profile-b-input <snapshot.json> --out-dir <new-directory>`.
No semantic-version-to-plan-version inference is allowed. In-repository profile-B outputs
are restricted to the dedicated .local/i4-4d2 tree, and existing output directories are rejected.

Profile A remains available with its explicit v8/supported-noncurrent opt-in. A profile-A
request carrying another semantic version is rejected. No v8 or plan-v5 default promotion,
same_local_assertion, claim-goal/authority-veto change, or I2-3 work occurred.

## Producer verification before projection

The consumer calls the existing pure verify_producer_authorization with the fixed
installation registry and actual immutable snapshots. It never calls reproduce_accepted_v8.
The qualification issuer ran separately, before the consumer, with socket connections denied.
Tests replace the issuer with a failing stub during consumer/replay construction.

The bridge requires the exact VerifiedProducerAuthorization type, then re-verifies it
against the fixed registry and these actual inputs before comparing identities and calling
the unchanged validate_layerc_inputs. The observed ordering is verified, verified,
projection, claims/typed evidence, plan, render, downstream manifest. The bridge's second
verification establishes that a supplied verified record still binds the current invocation;
the lightweight I4-4C compatibility envelope is never treated as a trust root.

The D1 verifier checks the supported_noncurrent/v8 identity, map canonical hash, sealed byte
hash and proposition-index hash, independently reviewed authored inputs, overlay, nominations,
ownership contexts, semantic rulesets and output shape. All 19 actual input files remain bound.
The recorded producer's 26 scientific source fingerprints remain unchanged.

Raw IDs, raw receipt dictionaries masquerading as verified objects, missing authority,
wrong map/disposition/nominations, revoked authority, and downstream manifests substituted
for upstream receipts are rejected before Layer C. D1's exact accepted-event enrollment
and consume lifecycle checks remain authoritative. No trust configuration was added to
the caller. The D0/D1 threat model remains A-D relative to trusted repository/process code;
this does not claim protection against arbitrary in-process object/code replacement (threat E).

Stable authority chain:

- Registry: producer-authorization-registry-v1:sha256:3ca420b42e64046470738773b2affad9509ffbab4f0b0df166963fcc0308d0ef
- Producer profile: qualified-producer-profile-v1:sha256:0c739b235dd983b77f3f9adfca22bebea90255f0f51f57f45cd7e699ef0bd2cd
- Enrolled receipt: producer-output-receipt-v1:sha256:a040ad7757ee792e9c0a7f0414bead5ce22ed5eb5d19e1bdc37931b4f0d4071d
- Verified authorization: verified-producer-authorization-v1:sha256:aa9ccbfa94f100a4c8cc0cbe85f60f27eebb289528e0f280447f0fcd23bb04b2
- Projection: layerc-validated-projection-v1:sha256:13f2174081d418d3ec7ef1fd72fc118d0c485f6f8f9503c150147a61eb4472fa

## One immutable scientific/reference projection

ParentClaims and AnswerPlan receive the immutable projection, not candidate_supports or
mutable map bindings. They do not select candidates, classify authority/polarity, run
support policy, reconstruct witnesses, or rerun direction/effectiveness. Independently
verified authored reporting obligations travel alongside the projection; they are not
reconstructed from output states. Final presentation data stays downstream, preserving
the exact accepted projection identity.

Whole-map canonical equality before/after construction covers all 13 requirement states,
46 instances, 94 bindings, candidates, attribution, guard/policy receipts, category
observations, 20 stored proofs, witness IDs and aligned observations/summaries.
The exact scientific-map hash remains
e1c6d1027c96098dce96b7c86ee9259d1c50e379845c1d9bb3adeb62ba00b8cf.
All 48 recovery targets remain equal, with canonical hash
f8f0278d489d4c0fa7e5794ef2238f20a2c19301f26438d7ea2bcd45934d6cd5.
The 32 nomination slots, 21 held bindings, 33 replay requests, 49 stored fingerprints,
and recovery query text are unchanged. The consumer writes no scientific input.

## Claims, member receipts and exact values

Claim IDs contain only frozen semantic material. Evidence IDs, proof IDs, receipt IDs,
instance keys, source/discovery order and display paths do not enter semantic identity.
All C01-C17 identity dictionaries exactly equal I4-4C preregistration.

The 38 claim-evidence-v1 records preserve distinct establishment, scientific_coverage,
display_envelope, citation, relation_proof and observation edges. Paths merge only for the
same semantic claim tuple; each member keeps its own evidence associations. Completion
and I1 purposes remain separate even when attached to the same claim. Convenience citation
lists are downstream transport, never truth or coverage authority.

All 32 own semantic-value-v1 IDs below match the frozen substrate. The 13 inherited
placements retain full value material, coverage placement and inherited establishment
identity in finalized value coverage, including context values with no child proof.
Restricted/unavailable display never deletes a scientific value.

| Claim | Family | Member value numbers | Exact semantic claim ID |
|---|---|---|---|
| C01 | relational | V01, V02 | parent-claim-v2:sha256:f2a6fbb93d46d7666a535b24b748ff829460557b70cb6801063733a86d24fc41 |
| C02 | relational | V03, V04 | parent-claim-v2:sha256:9153f4149522f82597ca9efb9f27c0dac3f49595be951e05a5e02d6ac8991a0a |
| C03 | relational | V05, V06 | parent-claim-v2:sha256:553bfea852b8f012c1b6a3514bf75a61f8d1729af9eccabf5e99f478543faf12 |
| C04 | relational | V07, V08 | parent-claim-v2:sha256:1395b307418fab34026e35a852df86111b9a8fa834f353aacdf800eaec9c6a6a |
| C05 | relational | V09, V10 | parent-claim-v2:sha256:c02f02d65042387427895a977ab8fae9f36498cf07d474d608c7ddbee320bf71 |
| C06 | relational | V11, V12 | parent-claim-v2:sha256:f5b58cd041959f22650c7ebfbb05fa8192b5b40048c2b12d6757af5bb4ae30da |
| C07 | relational | V13, V14 | parent-claim-v2:sha256:418af34a9bca2e476bce33f27b449e23e3ec602842a7083c15d488a6d1fe210b |
| C08 | relational | V15, V16 | parent-claim-v2:sha256:c2cba0c8b1f4356302faeb08aeb8b75b80351c408b0d0627d389b766c51ba94f |
| C09 | relational | V17, V18 | parent-claim-v2:sha256:c43f945b2be16c9d8271176bcc05fefd7a317dd623d24e7b51bb348928631432 |
| C10 | role_value | V19 | parent-claim-v2:sha256:d4289c0ca9483a2033c0382682f58d003b551f827784f35a57036914a542d033 |
| C11 | role_value | V20 | parent-claim-v2:sha256:2e9ac8f59b127263bce923cf4a6b18bdfce32ed4eff5aaac58708df69a110e30 |
| C12 | category_list | V21 | parent-claim-v2:sha256:74445011aa05fdf6695761c486409c05ad1321b4969d0a1c24387a61481cffa7 |
| C13 | category_list | V22, V23 | parent-claim-v2:sha256:cee6dcdbfaf6fef17036224d06b06b0ed929655ead8614764270a13a7467157b |
| C14 | category_list | V24, V25 | parent-claim-v2:sha256:4598c52add356a5ff91f5b5d42d1fc7f1962cb626efd04da919e397581a62bf4 |
| C15 | category_list | V26, V27, V28, V29 | parent-claim-v2:sha256:3756f80867862269d192bfb5d5367403155263dfd8e3cf5e6006c08f6e19e88c |
| C16 | category_list | V30, V31 | parent-claim-v2:sha256:c0ac85668328015df03a1d3d4d3e3b366f6506329c7ef4fb5ed6f4f78dc6ed0a |
| C17 | category_list | V32 | parent-claim-v2:sha256:172e733fd288f49ae73b895e9face8070f0cf9e60eb0d8f9dd7c9aa0d69c3ce3 |

| Value | Claim | Scientific goal / finding | Final display; citation PIDs | Exact semantic value ID |
|---|---|---|---|---|
| V01 | C01 | established / not_applicable | restricted; none | semantic-value-v1:sha256:71e539b97612a8e6b7c55805d777aa625355908b317a8657322a26f331a2dd08 |
| V02 | C01 | established / not_applicable | restricted; none | semantic-value-v1:sha256:dfb887dc4970e0245a4f3f7b0c85ae39d7c3a6e7a8607c0da71b5a86f7052d00 |
| V03 | C02 | established / not_applicable | restricted; none | semantic-value-v1:sha256:3fcebcec37ff6f5b014a578c90da202ed158c969a2ab9b8fd6363c18ddebe25c |
| V04 | C02 | established / not_applicable | restricted; none | semantic-value-v1:sha256:751e23ed92b57b22709dd30b7adb5b6e928f5cb5f87aca818d592ed254d878da |
| V05 | C03 | established / not_applicable | restricted; none | semantic-value-v1:sha256:02e3471955ebe76fd628662fd3be9bb03341d58f7678b0bd24222fe1783e4689 |
| V06 | C03 | established / not_applicable | restricted; none | semantic-value-v1:sha256:c71d74c74520515a44822188e345418c1546cb83e49d8f910e2a448c3be81067 |
| V07 | C04 | established / not_applicable | restricted; none | semantic-value-v1:sha256:e29229098dae6fa5dc269d953ad2b2c3a070e02fa88dd39647956dde5972de93 |
| V08 | C04 | established / not_applicable | restricted; none | semantic-value-v1:sha256:0010d9051d1776feefd833e762303a1b5e1fc5b031202b6af75add7496d1a82f |
| V09 | C05 | established / not_applicable | restricted; none | semantic-value-v1:sha256:9871c85eb64726c5b1394e3051e8e6f7e5e6013311fc846e8ec4f11d885d7587 |
| V10 | C05 | established / not_applicable | restricted; none | semantic-value-v1:sha256:637bdfd2f6c67012d4617655bd7c09e1a13d615b207f3185916e625f4eabe595 |
| V11 | C06 | established / not_applicable | restricted; none | semantic-value-v1:sha256:1d84fca93f15e3cbf8dfce00c41e153e7e957ded16c6477f9babc664b119a162 |
| V12 | C06 | established / not_applicable | restricted; none | semantic-value-v1:sha256:8c3e973976d23a8472f3f094b9b1ed52cd7f012e33e84a0eedd306add0422f20 |
| V13 | C07 | established / not_applicable | restricted; none | semantic-value-v1:sha256:15046f1f6a3546697d0c77fde5d61e70e19eded91538b4aaac6bb14d65e8f902 |
| V14 | C07 | established / not_applicable | restricted; none | semantic-value-v1:sha256:c2247677d32bf4a9e3ab39db7d2e1cf63ba398f24258302bdf19afa2a448c46c |
| V15 | C08 | established / not_applicable | restricted; none | semantic-value-v1:sha256:52de78a144af120d61898d196d1ffbca88c38e71a7f3de2c7cb735679f2adcdc |
| V16 | C08 | established / not_applicable | restricted; none | semantic-value-v1:sha256:0a612abee98c488f11ecaef9b20538d3a2050125d5dc06f8acc78a1bef0f0608 |
| V17 | C09 | established / not_applicable | restricted; none | semantic-value-v1:sha256:972f2149ad56f9a9d9e28f17eed71fcb2181e5ef6d0e92d5bec12c80eb9228d3 |
| V18 | C09 | established / not_applicable | restricted; none | semantic-value-v1:sha256:a4e6cf453349208936e627f051220b0cf0736d4cb37c658f8e65814f943ca8d5 |
| V19 | C10 | established / not_applicable | supported; p14,p17,p26,p3,p7 | semantic-value-v1:sha256:20ab47f0575592ac3519357d1ce20dd537f68e8caa32384b0f1bf8dabe4e171f |
| V20 | C11 | established / positive_finding | restricted; none | semantic-value-v1:sha256:0b2d5d6507dbbc6f6d0212b7cc0411c9be3d2663cc7798295605d85659716980 |
| V21 | C12 | established / not_applicable | restricted; none | semantic-value-v1:sha256:ec620d2e915553dd9fc9bb83a0dc3330247d83aa357b1ff02ccaedd9e59eba7b |
| V22 | C13 | established / not_applicable | restricted; none | semantic-value-v1:sha256:236ced83cf41481eb76b7733518a532c21bc2d2f4b808530c35c01e5c8d6dbc9 |
| V23 | C13 | established / not_applicable | restricted; none | semantic-value-v1:sha256:f6dcd8bfe866cd5c62411674f25e50d2ad99279174bd34a1f3b5b183e8d2edba |
| V24 | C14 | unestablished / null_finding | supported; p36 | semantic-value-v1:sha256:8eb2403f24906e5a891c736b9c91bd3b29610c9a46866a1685e7105c656a6ea0 |
| V25 | C14 | established / positive_finding | supported; p36 | semantic-value-v1:sha256:bc62af4f96a9b58b0d2cd5c38de50473a465baf5e23665a718971518907978c5 |
| V26 | C15 | established / not_applicable | restricted; none | semantic-value-v1:sha256:460dfdd5d724ad401ae421c98262ddea836c1e1b51a50946652c9f0331455992 |
| V27 | C15 | established / not_applicable | restricted; none | semantic-value-v1:sha256:67404b8a0b0b338af1eb1440bb7fd438174e8050771d99bfef940924f67c7d29 |
| V28 | C15 | established / not_applicable | restricted; none | semantic-value-v1:sha256:be4fdda9a1c7a097f7098d7333cb28702273ade4921d78726b0289e720ec89d4 |
| V29 | C15 | established / not_applicable | restricted; none | semantic-value-v1:sha256:13da9580be9944534392f504551b6bad7cad0d7c54e9eacbbc97d46957d1187e |
| V30 | C16 | established / not_applicable | restricted; none | semantic-value-v1:sha256:c7fe32e9c37b15c9bc91fe0261f24cf922eac5561a5dcff7463bcb916b5ecf4b |
| V31 | C16 | established / not_applicable | restricted; none | semantic-value-v1:sha256:565e311eb69e7038959dbae8cbf58c07f808b1c2e310671c8f87732b2d46c0ce |
| V32 | C17 | established / not_applicable | supported; p14,p17,p26,p3,p7 | semantic-value-v1:sha256:4d66f019291fc331bfcbd04fd731c2117a9840421ea7db303023dbe9a657e72e |

The complete literal/role/scope/operand identity material remains in
[layerc_i4_4c_preregistered.json](layerc_i4_4c_preregistered.json). Tests compare dictionaries
and exact ID sets, not counts alone. Finalized coverage includes the complete semantic value
and original typed coverage record for inspection.

## Exact p8 / p36 boundary and presentation

c3 explicit still selects p8 for its RoleBinding/support view. Its independent positive
category observations are p8, p36 and p52; presentation accepts the value-specific p36
observation. No p36 support view is manufactured and no p8 binding is rewritten.

c3 implicit independently selects p36 as a null observation. Its reported_finding remains
null_finding and scientific_goal_state remains unestablished. Its own scoped p36 display
receipt answers the findings-reporting obligation without positive-presence inference.
Recovery stays open. The physical sentence's explicit and implicit uses have distinct
typed receipts; textual overlap creates no new evidence association.

Presentation runs only accepted existing checks on projection-authorized, value-specific
source/envelope inputs. Every display path must also have the corresponding citation edge.
Text containment validates that authorized association; it cannot discover one. Generic
summary grouping uses the presentation authority's exact canonicalization. Existing
source-context restrictions may remove permission from a narrowed assertion but never
expand its display envelope.

Candidate-local envelopes add only authentic adjacent whitespace/terminal period.
The 14 wrapper probes cover discourse words, Results labels, prior-owner phrases,
coordination, citations, statistics, semicolon/colon continuations, quotes and captions.
No enclosing sentence contributes a new assertion. Legacy whole-source paths remain
legacy paths; the wrapper restriction does not silently narrow or redefine them.

Display is supported, restricted or unavailable for valid outputs. Invalid refs/profile
raise before output rather than becoming an ordinary node state. Scientific goal, finding,
map state and display remain separate. Excluded/ambiguous candidates stay diagnostics;
they cannot create positive values, citations or coverage.

## Stored proofs, relationship units and observations

Exactly 41 relation units are emitted: 40 required-role units plus the completion-only c1
unit. A unit keys placement plus distinct semantic tuple. It preserves completion status
and refs, I1 status/refs, historical witness_ids meaning, selected support/text refs,
own/inherited operand identity, claim/receipt refs, citations, aligned observations and
diagnostics. It does not copy the entire witness bundle.

The P2 control chooses the stored P2-compatible assignment even when the legacy evidence
representative is P1. Its relational claim and unit carry P2, no P1 relationship citation
or stale P1 operand; reversing candidate order gives identical semantic results. The
RoleBinding representative remains unchanged. Existing profile-A defect tests still
characterize the ParentClaim mismatch and stale representative operands.

Multiple physical paths to one tuple retain one semantic claim; distinct tuples receive
different claims. Duplicate inputs do not duplicate semantic paths. Input-bound projection
identity may change when transport metadata changes, while claims/receipts/units/render
remain identical in the duplicate-path control.

Inherited operands remain inherited and never enter own witness intersections. A child's
own selected proof supplies its relationship authority. Joint rendering requires a common
authorized sentence at the proof's source; inherited containment is checked only after that
association. A parent citation cannot become a child relationship citation.

Shared-designator completion retains operands, proof and context status with no invented PID,
I1 truth or joint quotation. Missing joint context restricts rendering without erasing its
narrow stored relation. Completion-only science, including c1, does not acquire I1.

Direction/effectiveness consume stored aligned observations/summaries. Opposite-sign
compatible assertions retain both paths, null consensus, within-instance conflict and
no across-instance heterogeneity. Same-sign assertions retain distinct paths. Effectiveness
supported/not_supported conflict uses the existing completeness filter and adds no I1 gate.
No new sign, negation or whole-passage effectiveness logic exists downstream.

## Parent synthesis, plan and rendering boundaries

parent-synthesis-v2 deterministically realizes authorized member paths. Typed prompt
transport, authorized text, value/source reasons, segmentation, citation transport,
rendering and exact rebuild/audit use v2 receipts. No model/NLI executor is exposed.
Tampered member/value/source/text/polarity items fail typed source validation. Replay
rebuilds the ledger and its synthesis from the verified projection; an altered synthesized
record fails exact rebuild comparison.

Legacy text, prompt, value/source screens, realization, renderer, construction record and
audit explicitly reject v2 rather than flattening it. Default legacy behavior remains
unchanged. Plan-v5 records the profile, verified authority, projection ID/body hash, all
schema identities, applied sufficiency identity, producer profile, claim/receipt/unit/synthesis
hashes, plan hash and downstream output-manifest reference.

Reporting obligations remain per placement: exists can use a qualifying instance,
for_each_discovered_instance must cover every placement, at_least_n must cover its authored
count, and open_list cannot certify exhaustive completion. Required roles cannot be pooled
across instances. Relational reporting requires an applicable rendered I1 path. Category
positive/null reporting retains its separate scientific goal. No searched_empty state is
inferred: the enrolled profile's bound inputs contain no certified empty-search authority,
and the consumer does not accept an unbound search-status override.

| Node | Final reporting state |
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

Node 3 is answered as a report, covers explicit and implicit, and retains overall category
scientific_goal_state=incomplete. Explicit is established/positive_finding; implicit is
unestablished/null_finding. This does not change map sufficiency or recovery.

Established but undisplayable science yields a typed presentation limitation with minimal
generic wording. It never yields a false assertion that the science was not established.
No broader direct/indirect/unestablished prose system was designed. Text deduplication
occurs after member-specific receipt creation; physical sentence sharing retains all typed
member associations. Every rendered member is checked against its own receipt.

## Noncircular output authorization and new baseline

The upstream registry/enrollment authorizes the producer output first. Projection, claims,
units, synthesis, plan and deterministic rendering are then constructed. Only afterward
does profile-b-output-manifest-v1 bind the downstream artifacts to that verified upstream
reference. This manifest is output integrity material, not a new upstream trust root,
signature or enrollment. A downstream manifest supplied as producer authority is rejected.

The directed graph is upstream -> projection -> claims/receipts/units/synthesis -> plan core
-> render -> output manifest. The plan's manifest back-reference is transport metadata
outside the plan-core hash, preventing a fixed-point hash cycle. The combined output hash
includes that transport reference. There are no timestamps, random values or git HEAD fields.

The final separate baseline was generated after semantic/count/value/node/proof controls,
the final generic presentation/placement checks, and two equal deterministic constructions.
The earlier local draft is not a historical or accepted profile baseline. The historical
v4-v8 identities and I4-4C expected values were never updated to fit the implementation.

| New profile-B identity | Exact value |
|---|---|
| claim_ledger_sha256 | ca50181ba521921463affa49f8aac2292e9970b8f434d512221c82cb55ac579c |
| claim_evidence_sha256 | 3111b6d7c3c7cb78915cc37079a169383a5f528c8d1e897618251eeb7ecc6a2a |
| relation_units_sha256 | 8243b5184886100d78a806328c1104d3ba36d0e2548e92c745bb31ad01876554 |
| value_coverage_sha256 | 4b577dadf8cd7c88c10b00b10c6160db277ec123c4ddcc8880f501982e33f4d7 |
| parent_synthesis_sha256 | 895e3bb956c01cb10d5cde828a631f255cf817332ccd1badff1b202e87855f7f |
| plan_sha256 | c6b4554810059c3cff74e88579fa9ab87f05506ededba4ca8c8383195bdcfbec |
| render_sha256 | 0ba1565a74b9706cb3368c670d4c7ecff3daf5f41891f834fd15ecbcf1c2c96f |
| projection_sha256 | e065d9ef55c3a15f0d7c823158271185353d49a6fe8403466e01ffca1216ef09 |
| Downstream authorization ref | profile-b-output-manifest-v1:sha256:0e1e1a8e6ee27dbd18498d06a19d14aeaae7a162ca21c00058032342fb1a9ce6 |
| Combined profile-B SHA-256 | e697596b8fb3dd3ce426cdc1b82909ca93f4bbc3346e46b74bf2f96f980eafde |

The committed [profile-B baseline](layerc_i4_4d2_profile_b_baseline.json) additionally stores
the complete closed output manifest, counts and node table. Qualification snapshot/replay
artifacts remain in .local/i4-4d2/input_snapshot.json and
.local/i4-4d2/qualified-replay-final; no historical run files were rewritten.

## Historical replay and executable boundaries

All original combined characterization hashes remain exact:

| Replay | SHA-256 |
|---|---|
| v4 | 4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a |
| v5 | 109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77 |
| v6 | dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be |
| v7 | 04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72 |
| v8 | 1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0 |

The v8 row is profile A, not the new profile-B baseline. Legacy tests run with producer
verification/issuance patched to fail if accidentally activated. Current constants remain
v7 and plan-v4.

Closed import/call guards enforce no candidate_supports reads, selectors, support-policy/
attribution/category/direction/effect reruns, witness reconstruction, issuer calls, model,
retrieval or NLI in the new consumers. Runtime controls deny scientific selector calls.
Map, authored data, proof payloads and upstream receipts are not mutation targets.

The old I4-4C/D1 no-consumer tests now allow only the named explicit caller/consumer modules.
The I4-3C isolation test still compares the original frozen replay-file hash after removing
exactly the three reviewed dispatch additions; it does not bless a replacement hash or
skip the legacy body. Other file/function pins are unchanged. Runtime routing tests
independently exercise legacy/default and explicit profile-B paths.

## Qualification evidence

All 116 new consumer checks pass. The final targeted run including historical/static boundary controls has 136 passes; the four I4-3C isolation controls also pass.
Final full offline suite: **5,386 passed, five known failures, 12 skipped, nine xfailed, 276 passing subtests in 296.18s**. Zero unexplained regressions.
All applicable hooks pass except the unchanged 615-line app/frontend/js/20_synthesis.jsx cap. Frontend HEAD/worktree blob is identically 03f9d3dfee3763533a78d5da601a99cb81bb37f1. Ruff, Bandit, Tach and hygiene checks pass. The user's explicit --no-verify exception applies only to this atomic D2 commit and this sole remaining hook failure.

Seven optional psutil-dependent offline checks pass in the dependency-complete environment.
Exactly five known failures independently reproduce:

| Existing check | Unchanged cause |
|---|---|
| ask_070 test_dev_eval_separation | missing frozen/dev_inputs_v0.json |
| ask_070 test_real_frozen_nonsemantic_artifact_schemas | missing frozen/corpus_presence_v0.json |
| RunTopologyGuardTests dirty-tree unscored smoke | offline guard denies the Ollama /api/tags probe |
| RealPinsTests preserved artifacts | existing hierarchy_contract.py pin drift |
| MainOrderingTests preflight-only readiness | same hierarchy readiness failure, return code 3 |

No retrieval, model, ranking, NLI or live E2E occurred. Network connections were denied;
optional integration-named tests used their established mocked offline path. No known
failure was hidden, xfailed or repaired. Initial implementation/harness failures were
resolved before final qualification: incomplete synthetic authoring fixture, generic
presentation key normalization, per-instance reporting scope, and the old blanket replay
file-isolation guard. A stale in-flight draft-baseline comparison is superseded by the
final complete suite against the final frozen profile-B artifacts.

Local evidence: targeted-final.log/xml, isolation.log, qualification-final.log,
full-final.log/xml, known.log/xml, optional.log and hooks-final.log under .local/i4-4d2.
The full command is
`.venv/Scripts/python.exe .local/i4-4c/run_offline.py experiments -q --tb=short --ignore=experiments/ask_cli_revised/contract_directed/tools/test_run_gate_integration_live.py --junitxml=.local/i4-4d2/full-final.xml`.

## Exact change set

New implementation:

- layerc_consumer.py
- claim_v2.py
- layerc_presentation.py
- relation_unit_v2.py
- parent_synthesis_v2.py
- profile_b.py
- profile_b_replay.py
- answer_plan/plan_v5.py
- answer_plan/render_v5.py

New qualification:

- test_profile_b.py
- test_profile_b_matrix.py
- test_profile_b_static.py
- layerc_i4_4d2_profile_b_baseline.json

Narrow existing-file changes:

- answer_plan/replay.py — explicit profile dispatch only.
- parent_synthesis.py — reject v2 at legacy realization/text/prompt/value/source boundaries.
- parent_synthesis_render.py — reject v2 flat rendering/construction.
- parent_synthesis_audit.py — reject v2 at the legacy ledger audit.
- test_layerc_static.py — exact consumer import allowlist.
- test_producer_static_replay.py — exact verifier bridge/transport allowlist.
- test_i4_3c_static.py — preserve frozen legacy replay text behind explicit added dispatch.

Documentation:

- PHASE34_I4_4D2_PROOF_ALIGNED_CLAIM_PLAN_INTEGRATION_RESULTS.md
- CONTRIBUTION-LINEAGE.md — this increment appended.

All paths above are relative to experiments/ask_cli_revised. No scientific source,
producer authorization implementation/material/registry, I4-4C substrate or preregistration,
historical replay baseline, frontend, or default version constant changed.

## Decision and stop

**READY for a separate I4-4E promotion decision.** The bounded explicit D2 consumer is implemented and qualified; promotion is neither implied nor performed.
A new explicit consumer baseline is not promotion authorization. Stop after this atomic
I4-4D2 commit/push. I4-4E remains a separate decision; I2-3, same_local_assertion,
claim-goal/authority-veto semantics and live execution remain untouched.
