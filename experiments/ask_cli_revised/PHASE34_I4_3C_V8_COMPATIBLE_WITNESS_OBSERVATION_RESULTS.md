# Phase 34 / I4-3C — v8 compatible-witness proofs and aligned observations

Date: 2026-10-09. Explicit supported-noncurrent Layer A/B implementation and offline qualification.

Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
Verified clean starting HEAD: `693672bf34582f3ba111bef1381b6c622a0e4bea`.
Final implementation HEAD is the single commit containing this report:
`git log -1 --format=%H -- experiments/ask_cli_revised/PHASE34_I4_3C_V8_COMPATIBLE_WITNESS_OBSERVATION_RESULTS.md`.
Its full hash is recorded in the delivery receipt, avoiding a self-referential commit hash.

**READY for I4-4 planning.** V8 Layer A/B is implemented and qualified as **supported_noncurrent**.
Current/default remains **sufficiency-semantics-v7**. V8 is supported, not current and not historical.
This is not unrestricted end-to-end answer qualification: the documented synthetic ParentClaim and
AnswerPlan limitations remain visible. No Layer C production file changed.

## Identity, activation and real replay

The accepted I4-3C0 identity implementation and replay CLI are byte-unchanged.
Engine configuration adds SUFFICIENCY_SEMANTICS_V8 to SUPPORTED only.
SUFFICIENCY_SEMANTICS_VERSION still equals SUFFICIENCY_SEMANTICS_V7; HISTORICAL remains v1-v6.

A real produced v8 map reads as:

```json
{"status":"supported_noncurrent","version":"sufficiency-semantics-v8"}
```

Only `read_map_identity(map, accept_supported_noncurrent=True)` accepts that map.
Default and historical-only reads reject it. applied_semantics_version returns v8, never v7.
Replay authorization binds that exact status and version; rehashed receipts claiming current/v8 or
historical_versioned/v8 fail the exact consistency check.

Real offline replay invocation:

```text
.venv/Scripts/python.exe -m experiments.ask_cli_revised.answer_plan.replay
  --run-dir <preserved-input-copy-with-real-v8-map>
  --out-dir <separate-output-directory>
  --allow-supported-noncurrent
```

The qualification copies preserved inputs into a temporary run, writes the actual v8 map and invokes
the existing replay CLI. There is no sentinel or semantic test double on this path. Default and
historical-only invocations reject the same map. The new authorization records v8 for both containment
and direction. The separately retained I4-3C0 sentinel tests still exercise disposition lifecycle.

## Shared support authority and reference schemas

One new pure module, compatible_witness.py, adapts candidates, constructs references and receipts,
selects assignments and validates bundles. It reads no question prose and performs no collection,
policy evaluation, attribution, I/O, retrieval or model call. Engine role participation and I1 sealed
verification/containment predicates are supplied by their existing owners.

For a filled binding with candidate_supports present, every record is validated before filtering,
including exclusions. Only admissible=True and attachment_ambiguous=False produces a support view.
An empty or all-ineligible list yields zero views, even when legacy representative fields are filled.
Missing/ambiguous bindings yield zero views. Filled bindings without the candidate key yield exactly
one legacy view; no empirical support policy is applied retroactively.

Immediate source comes exclusively from the outer binding's provenance.candidate_source:
parent_context means inherited, otherwise own. Scientific assertion_relation is never used for this
classification. Child-owned attributed evidence remains own; parent-carried current-document evidence
remains inherited.

The implemented schemas follow I4-3B:

| Schema/reference | Content and identity |
|---|---|
| support-view-v1 | Final child/requirement/instance/role placement; immediate source; evaluated_candidate or legacy_binding; support IDs; primary ID; operand/locator/candidate/receipt/provenance references. |
| support-ref-v1 | Candidate assertion identity: scheme, representation, final placement, anchor proposition, sealed quote/source identity and assertion span. Full support set, exact text, other spans, attribution and gate payload are validation material. |
| candidate_unlocated under support-ref-v1 | Explicitly tagged; placement, anchor, support IDs/quote identities, exact-text hash and available predicate/content spans. May join by proposition identity but supplies no local observation scope. |
| legacy-support-ref-v1 | Placement, legacy primary/support set, text hash/null, immediate source and stable outer provenance identity. Locator kind legacy_unit; no fabricated assertion spans. |
| support-eligibility-v1 | Independent admissible, attachment_ambiguous, guard_exclusions and complete existing support_policy_evaluation, without reevaluation. |
| witness-bundle-v1 | Shared support/receipt/view registries, both-purpose proofs, observation bases, diagnostics, sealed-input digest and binding semantic-input digest. |

Canonical JSON is sorted-key, compact UTF-8 with ensure_ascii=False and allow_nan=False. Text hashes
use exact UTF-8 bytes. IDs use full lowercase SHA-256 and versioned prefixes. Set-valued IDs/roles are
normalized; candidate discovery arrays and input bindings are never mutated.

References are stable across reorder and unrelated insertion at a fixed placement, distinguish assertion
offsets and placement, and exclude display representative IDs, free-form detail and late model origins.
Identical normalized duplicates collapse. Conflicting payloads under the same grounding reference raise
WitnessIntegrityError before filtering, even if one record is excluded. Proof identity hashes its complete
normalized body excluding proof_id; identical proof duplicates collapse and conflicts raise.

Locators use half-open Unicode code-point offsets into sealed quote strings. Exact-text slices, bounds,
plural quote-coordinate consistency and attribution quote hashes are validated. Unlocated candidates
emit candidate_assertion_locator_unavailable and never fall back to whole-unit evidence. Null and empty
legacy text remain distinct; empty-support legacy views exist but cannot create a common-ID proof.

## Completion, I1 and instance storage

Engine recomputation receives explicit caller-owned witness_context (child, requirement, sealed proposition
index). Mapping routes thread it only on explicit v8; historical paths ignore it. Final instance keys exist
before references are built. Duplicate outer placements fail visibly. Completion happens before parent
eligibility/pairing, using unchanged required/alternative/category prerequisites.

Participation is exactly own_evidence_roles: every filled required or alternative member, excluding optional
and immediate inherited roles. Fewer than two own roles retain the historical bypass. Otherwise the selector
indexes eligible views by proposition ID, intersects across all roles and enumerates actual compatible
products for each global common ID. It neither accepts pairwise-only overlap nor silently truncates proofs.

Authored verifier OR retains every successful verifier's proof set. contract_directed_links requires its
existing supplied attachment_pieces and shared designator basis; absent context yields no proof. Its proof
has no invented proposition ID. Registry remains exactly same_proposition and contract_directed_links.
same_local_assertion remains unregistered.

I1 independently uses required roles, all filled with eligible views, and at least one own operand.
Compatible own assignments must share a sealed verified proposition with the existing continuation-anchor
checks. Every eligible inherited alternative is checked against the full sealed quote using unchanged
casefolded canonical containment. All successful extensions survive. Inherited IDs do not enter the own
intersection; all-inherited I1 remains false even if engine completion bypasses its own joint gate.

Existing I1 failure meanings are preserved; no_eligible_operand_support identifies a stale filled required
binding with no eligible support view. Sealed-proposition admissibility remains distinct from policy
admissibility.

relationship-proof-v1 records placement, purpose (completion_joint or i1_relation_witness), normalized
roles, actual selected view/source/evidence assignment, verifier, join, checks and semantic version.
Top-level relation_witnessed, witness_ids and witness_provenance remain in place. witness_ids remains the
sorted proposition IDs of successful I1 proofs. New witness_proofs holds references into the shared bundle.
joint-grounding-v1 records blocked_prerequisite, bypassed_lt_two_own, proved or unproved, with roles,
verifiers and proof references; bypass is not a fabricated relationship proof.

Bundles validate semantic input identity, registry references, selected eligibility/source, join membership,
placement, proof hashes, joint receipts, I1 references and direction paths. Stale inputs, tampered receipts
and rehashed incompatible paths fail visibly. Late model-origin stamping does not rename references.
Origin proof bundles remain on origin instances; copied parent candidates are re-adapted under child
placement and remain inherited. No provenance union or representative rewrite occurs.

## Observation transport

observation-basis-v1 preserves the broader historical diagnostic eligibility: zero filled own completion
roles yield no bases; one own role supplies each eligible support/ID basis; multiple own roles require a
global common-ID assignment. Bases do not independently assert completion or I1 truth.

Direction paths extend each own basis with selected required-role operand surfaces. Compatible I1 extensions
take precedence over rejected inherited alternatives *for path selection*: only successful extensions
produce eligible relation paths. Where no I1 extension exists, available selected surfaces still yield
ineligible diagnostics, preserving real c5/c6 behavior. No attachment/guard/policy semantic precedence is
introduced.

When an own evaluated candidate participates, observation scope is exactly its selected assertion slice.
No containing-sentence, proposition or unit expansion is allowed. Unlocated own candidates supply no local
scope; inherited candidates supply referents only. Mixed candidate/legacy bases do not scan additional
legacy units to broaden evidence. With no own candidate view, legacy whole-unit scope/flags remain intact.

Direction uses the existing splitter inside the selected assertion. Reversible whitespace normalization,
exact monotonic sentence matching and raw-offset roundtrip checks retain observation coordinates; no fuzzy
search or tokenizer replacement is used. Existing direction classification is unchanged and receives
operand text from the same assignment. relation_eligible requires compatible I1 proof, relation target and
a non-null sign.

Effectiveness has no new I1 gate. Each own basis supplies its selected assertion or legacy unit; the existing
result-predicate detector and negated/absence flags determine the outcome. For local evidence, the existing
passage_flags function runs on the exact local slice. Candidate guards/policy are not reevaluated.
Authority-veto remains metadata and no new claim-goal semantics are introduced.

observation-alignment-v1 adds physical source/scope, quote and raw-text hashes, assertion/observation spans,
normalization identity, supporting IDs, selected view/operand references and all proof paths.
Observation identity includes placement, physical scope, kind, semantic result and version, never discovery
order or proof count. Duplicate paths to one physical/result observation merge; different offsets, opposite
signs, distinct same-sign assertions and unproven distinct physical sources remain separate.

The opposite-sign same-P2 fixture emits both eligible observations in every order:
consensus_value=null, observed_values=[], has_within_instance_conflict=True,
has_across_instance_heterogeneity=False. The local effectiveness pair emits supported and not_supported
without whole-passage negation contamination, independently of I1. Repeated inherited or proposition-alias
proof paths merge without inflating physical observations.

## Preregistered synthetic results

The 17 matrix families run all 42 independent candidate-order permutations. A/C/D/G/I/J
produce the expected compatible I1 witness; B/E/F/H/K and M-R do not. K's pairwise overlaps
never become a global common-ID proof. D is the important non-representative repair:
a display-first P1 no longer masks a compatible P2 candidate. Excluded or attachment-ambiguous
P2 records never rescue a P1-only eligible assignment, and an empty candidate list cannot
fall back to its stale representative.

The additional frozen cases cover verifier OR (one or both successful), absent link context,
duplicate verifiers/candidates, conflicting candidate payloads, ID reorder/insertion stability,
unlocated candidates, empty/null legacy support, continuation anchors, selected local evidence,
mixed candidate/legacy evidence, inherited alternatives, all-inherited rejection and copied
parent placement. Tampered proof, locator, receipt and observation path cases fail visibly.
Repeated successful paths preserve one physical observation; distinct assertion offsets and
unproven distinct sources stay separate. The local opposite-sign and effectiveness outcomes
are recorded above. These are implemented assertions against preregistered expectations,
not a post-hoc manual projection.

## Real replay and downstream boundary

| Measure | V7 | Explicit v8 |
|---|---:|---:|
| Evidence-role binding/candidate payload changes | — | 0 |
| Requirement states | 13 | 13; 0 changes |
| Instance completion states | 46 | 46; 0 changes |
| I1 Boolean / witness-ID changes | — | 0 / 40; 0 ID changes |
| Witnessed instances | 8 | 8 |
| Eligible support views | Not emitted | 51 |
| Completion/joint proofs | Not emitted | 11 |
| I1 proofs | Not emitted | 9 |
| Total successful relationship proofs | Not emitted | 20 |
| Nonempty direction observations | 6, all relation-ineligible | 6, same outcomes, all relation-ineligible |
| Effectiveness observations | 0 | 0 |
| Recovery targets | 48 | 48, identical |
| ParentClaims | 17 | 17, identical |
| AnswerPlan nodes | 9 | 9, same semantic content |
| Layer 1 | Accepted output | Identical |
| AnswerPlan invariants | 33 passing | 33 passing |

The semantic projection removes only new proof/alignment metadata, old-vs-new witness explanation payloads,
semantic-version spelling and version-dependent plan hashes. It compares the complete remaining map and
downstream artifacts, not just selected counters. Bindings/candidates, attribution, guard/policy evaluations,
collector diagnostics and held model nominations match exactly. Recovery records and query text match.

Synthetic corrected completion changes existing parent eligibility and relationship-unverified recovery
naturally. Neither algorithm changed. The non-representative P2 fixture remains an explicit Layer C
characterization: v8 proves/completes it, unchanged ParentClaim construction raises its joint-witness
empty-support exception, old witness metadata disagrees, and proof-aware shared I1 still leaves
AnswerPlan operand IDs P1/P2 despite witness_ids=[P2]. No Layer C workaround suppresses these limits.

## Version routing and isolation

Closed membership sites were inventoried and explicitly extended:
engine supported/category tables and v8 completion branch; mapping category/v7 evidence/direction dispatch;
diagnostic ownership-context and witness-context/observation transport; relation-witness containment/v8
finalization; direction_target's unchanged no-fallback table; recovery category/version tables; and e2e's
existing ownership/recovery membership tables. E2E still selects current v7; no live run occurred.

No numeric/lexicographic/latest fallthrough. Historical v4-v7 replay spies forbid support adaptation,
candidate-aware selection and local aligned observation entry. Historical artifacts emit none of the new
fields. Static guards freeze Layer C and identity files, policy/attribution/grounding files, direction
classifier functions, effectiveness classifier and legacy relationship/parent/summary helpers against
starting-commit digests. The selector imports only approved standard-library facilities, the evaluated
candidate validator and existing designator extraction. Runtime socket/file guards and immutable-input
tests accompany import/call-site guards.

witness_i4_3c_preregistered.json was materialized before production implementation from accepted I4-3A/B:
A-K, all independent L permutations, exclusion/empty families and the additional identity/observation/
inheritance/Layer C expectations. No expected semantic outputs were changed to fit implementation.
witness_i4_3c_isolation.json freezes starting code identities. Existing test updates only admit actual
supported-noncurrent v8 and extend the offline harness's unchanged v7 collector diagnostics to that version.
The I4-3C0 sentinel lifecycle suite remains.

## Qualification and replay baseline

Final focused run: **195 passed** (79 v8 witness/static/real-replay cases plus 116 I4-3C0
identity cases), including the newly frozen v8 replay hash assertion. The new witness battery
contains 68 cases; four static guards and seven real-replay/identity cases complete the 79.

Final full offline experiments: **5,081 passed, exactly five independently reproduced baseline
failures, 12 skipped, nine existing xfails and 276 subtests passed** (256.81 seconds).
The earlier complete run had 5,071 passes before ten additional integrity cases were added;
the final run includes those cases and the final production code. After that final run,
only the replay baseline, its hash assertion and documentation were added; the 195-case
receipt rerun passed on that final state.

The full run covers I4-1 through I4-3A, engine/mapping/diagnostic, policy/attribution/context,
recovery, relationship/witness, direction/effectiveness, parent synthesis, AnswerPlan and hierarchy.
It uses the existing offline socket-denial plugin:

```text
.venv/Scripts/python.exe -m pytest experiments -q --tb=short -p i4_offline
  --ignore=experiments/ask_cli_revised/contract_directed/tools/test_run_gate_integration_live.py
  --junitxml=.local/i4-3c/full-final.xml
```

The actual launcher adds .local/i4-2b3 to sys.path before pytest.main so the preserved
i4_offline plugin can load. The ignored optional psutil-dependent module is separately exercised
with the dependency-complete Anaconda Python environment and the same offline guard: **7 passed**.
Its live cases are scripted/mocked; no external endpoint was contacted.

| Version | Combined replay SHA-256 |
|---|---|
| v4 | `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a` |
| v5 | `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77` |
| v6 | `dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be` |
| v7 | `04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72` |
| v8 | `1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0` |

The v8 combined baseline is frozen only after semantic, identity, static and regression gates.
Its classification is supported_noncurrent, Layer A/B qualified, Layer C not generally candidate-aligned.
Historical v4-v7 exact bytes and baseline files are untouched. The combined serialization uses the
existing sorted JSON UTF-8 CRLF convention, not a new artifact encoding.

Known independently reconfirmed baseline/environment failures:

- ask_070 test_dev_eval_separation: missing frozen/dev_inputs_v0.json.
- ask_070 test_real_frozen_nonsemantic_artifact_schemas: missing frozen/corpus_presence_v0.json.
- test_e2e_run dirty-tree smoke fixture: existing Ollama /api/tags probe rejected by offline socket guard.
- test_hierarchy_contract generated-pin verification: existing hierarchy_contract.py code-input pin drift.
- test_hierarchy_e2e preflight-only readiness: same pin rejection returns 3 instead of 0.

Checkpoint modules came from starting HEAD, loaded separately with original hierarchy resources.
No known failure was hidden or marked xfail. Receipts are in .local/i4-3c/, including historical.log,
new-final.log, replay.log, final-receipt.log, static-final.log, full-final.log/xml, known-head.log and optional.log.

All changed-file pre-commit checks pass except the unchanged pre-existing line-budget failure:
app/frontend/js/20_synthesis.jsx has 615 lines. Its Git blob is unchanged at
03f9d3dfee3763533a78d5da601a99cb81bb37f1. Ruff lint/format, whitespace/EOF/conflict/large-file checks,
Bandit and Tach pass. The user's resumed-I4-3C-only authorization permits --no-verify for this
sole failure; no semantic gate is bypassed.

The canonical branch has no open pull request. The repository's CI workflow triggers for main
pushes or pull requests, not this experiment-branch push. Local qualification is recorded here;
no unrun hosted CI result is claimed.

## Exact files changed and stop

All 19 changed files are under `experiments/ask_cli_revised/`:

- CONTRIBUTION-LINEAGE.md
- PHASE34_I4_3C_V8_COMPATIBLE_WITNESS_OBSERVATION_RESULTS.md
- compatible_witness.py
- direction_target.py
- e2e.py
- relation_witness.py
- sufficiency_diagnostic.py
- sufficiency_engine.py
- sufficiency_mapping.py
- sufficiency_recovery_targets.py
- test_i4_2a_replay.py
- test_i4_3c0_supported_noncurrent.py
- test_i4_3c_replay.py
- test_i4_3c_static.py
- test_i4_3c_witness.py
- test_sufficiency_semantics_version.py
- witness_i4_3c_isolation.json
- witness_i4_3c_preregistered.json
- witness_i4_3c_replay_baseline.json

**STOP after I4-3C.** READY for I4-4 planning only. V8 remains noncurrent. No I4-4 implementation,
ParentClaim/AnswerPlan change, same_local_assertion registration, claim-goal/veto implementation or I2-3.
No live retrieval, model call or live E2E.
