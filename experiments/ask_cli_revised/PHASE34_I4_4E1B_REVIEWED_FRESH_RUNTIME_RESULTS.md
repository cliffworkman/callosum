# Phase 34 / I4-4E1B — reviewed fresh runtime results

Implementation and offline qualification of the reviewed-authored experimental entry.
**READY FOR I4-4E2 PROMOTION.** Final full-suite and hook disposition is recorded below.
This decision does not perform promotion or begin E2.

## Checkpoint and scope

Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.

The accepted E1A design and lineage append were the only outstanding changes at
`13680c71954c7f75964e096ceb48339eb1faf618`. They were committed and pushed, with normal
documentation hooks passing, as:

**E1A checkpoint / E1B starting HEAD: `f1ef2f326732a34cdc6ca4875de9926e05237d7e`.**

Clean status was confirmed before implementation. Final implementation HEAD is the one
atomic commit containing this report, identified by the final delivery and
`git log -1 --format=%H -- experiments/ask_cli_revised/PHASE34_I4_4E1B_REVIEWED_FRESH_RUNTIME_RESULTS.md`.
No self-referential commit hash is embedded in its own file contents.

Defaults remain sufficiency-semantics-v7 and legacy plan-v4. No scientific producer,
classifier, guard/policy, witness selector, direction/effectiveness algorithm, frozen
receipt/profile, baseline, application endpoint or frontend was changed. No sufficiency-v9.

## Public reviewed-authored entry

`reviewed_ask.run_reviewed_request(inputs, *, rt, profile, trace, guard, bound,
entail=None, sufficiency_recovery=False)` is a public experimental Python runner using
the same ordinary runtime, role bindings, trace and residency objects as `e2e.execute`.
It is callable independently of the legacy fixture question table. No new CLI parser,
product endpoint or automatic raw-text authoring system is claimed.

Input preparation has two explicit routes:

- The actual authoring/review caller supplies request, frozen scientific definitions,
  reporting body, scientific parent map and its real joint review to
  `reviewed_ask_inputs.bind_reviewed_inputs`.
- `load_reviewed_inputs` reads those five explicitly named paths once and calls the same
  binder. No default path, question table, replay overlay, nomination artifact or receipt
  can fill in a missing input. Later caller-file changes do not alter the bound snapshots.

The joint review body is closed: `schema=reviewed-ask-inputs-v1`, `status=reviewed`,
nonblank `reviewed_by` and `reviewed_at`, and `inputs` naming the exact request, scientific,
reporting and parent-context content refs. This accepts an existing review from the trusted
authoring caller, as the existing frozen/review lifecycle does. A matching digest alone is
not review authority. The code does not mint approvals; offline fixtures explicitly identify
their test author and do not claim production review. Persisted scientific output is not an
input to this runner or binder.

ReviewedAskInputs is recursively immutable, construction-controlled and not pickleable.
Runtime receives detached copies matching those snapshots. Substitution is rejected before
stages start; mutations during execution are rejected before Layer C. The complete request
body, including its decomposition, is bound rather than just its literal question string.

## Reporting contract and validation

The implemented closed schema is exactly:

```json
{
  "schema": "reporting-contract-v1",
  "request_ref": "request-contract:sha256:<digest>",
  "nodes": [
    {
      "node_id": "1",
      "literal_text": "What was found about alpha?",
      "parent_id": null,
      "owning_child_ids": ["s1-o1"]
    }
  ],
  "scientific_only_child_ids": [],
  "requested_construct_terms": ["alpha"]
}
```

All fields are required; unknown fields fail. Canonical JSON/content refs use the existing
Layer C helpers. Node sequence is authored display order; node ID serves the current label
slot. No separate root, visibility, ordering, evidence or state fields were introduced.

Validation requires a nonempty scientific inventory with matching child keys/IDs and
globally unique nonblank requirement IDs. Owned and explicitly scientific-only children
form an exact partition. Unknown, duplicate, conflicting or omitted ownership fails; every
visible node owns at least one scientific child with requirements. One node can own several
children. One scientific child cannot be split across nodes.

Node IDs and literals must be nonblank. Parents must be preceding ancestors in a contiguous
depth-first authored sequence, giving an acyclic forest without silently reordering it.
Parent links do not roll up states or create scientific inheritance. Scientific-only
children remain in scientific computation and diagnostics; they acquire no independent
visible answer node. Scientific parent links remain separately reviewed.

Construct terms must be explicitly supplied as a unique list of nonblank strings. `[]`
intentionally configures no request-wide term restriction; absence is rejected. The current
display restriction remains unchanged. Category inventories remain in scientific authoring.

`single_question` is an explicit authoring operation, not approval. It copies the original
question and requires one actual obligation ID matching the reviewed scientific child.
Flat IDs such as `s1-o1` pass unchanged through request responsiveness, sealing, U1/U2 and
Layer C; `s1` or a fabricated `root` is not substituted. Multiple requirements under that
child need no hierarchy. Explicit multi-node bodies are accepted under the same structural
rules, without deriving visible nodes from the execution hierarchy.

## Scientific execution and selected answer

The new route calls `e2e.execute` with its bound reviewed inputs. Only that explicit branch
selects v8 and enables the existing scientific stages for a flat request. Legacy eligibility
and defaults remain unchanged. The same ownership-context construction, U1 mapper, optional
recovery targeting, U2 mapper, observations, direction/effectiveness and final recovery/search
machinery run. There is no second scientific pipeline and no model-assisted nomination pass
added by this increment.

After scientific production, execution constructs fresh provenance and calls `fresh_layerc`.
The legacy model-facing Overview/parent realization is not selected on this route; the
deterministic v2 consumers provide its answer. `14_final_answer.md`, returned
`selected_answer`, and `layerc_v2.render.layer1` are checked equal. `14_render_manifest.json`
names the fresh profile/output manifest. `15_v2_output.json` contains the full inspectable
consumer result; it is additional inspection material, not the sole activation of v2.

## Fresh versus persisted authority

Fresh provenance is `trusted-fresh-invocation-v1`, with a domain-neutral profile
`fresh-v8-layerc-v2-plan-v5`. It binds:

- Request, scientific, reporting, parent-context and joint-review refs.
- Actual runtime classification and explicit v8 semantic version.
- Exact sealed bytes, sealed proposition index and final map digests.
- Ownership context and recovery/search-state digests.
- Authored scientific definitions and the reporting consumer-view digest.

The private execution capability begins in `e2e.execute` before its scientific stages and
finishes once at the actual post-U2 boundary. Static checks restrict issuance to that call
site. TrustedFreshInvocation has a private in-process origin, immutable body, no public
constructor and no deserialization route. A JSON object, persisted map or reconstructed
digest cannot enter the fresh consumer as this type. Arbitrary code replacing the process
or using Python reflection to subvert private fields is outside the existing process trust
model; this is invocation provenance, not cryptographic authentication.

The fresh profile goes through **the same `validate_layerc_inputs` and `_validate` scientific
checks** as qualification. Only the upstream profile binding differs. Exact types and bound
input digests are checked before projection; candidate/proof/reference/category/value logic
is unchanged. `layerc_pipeline.build_components` contains the former shared D2 orchestration
and is called by both paths; no scientific or answer semantics were duplicated.

The fresh plan carries typed `upstream_authority.kind=trusted_fresh_invocation`, its ref and
the native reporting-contract ref. Its output manifest binds the projection, all claims,
receipts, relation units, finalized values, synthesis, plan and render, with directed hashes
and no circular authority. Digest validation is output consistency, not a credential for
detached replay. Persisted profile B still obtains VerifiedProducerAuthorization through
D1's exact enrolled event/profile checks. No enrollment, receipt issuance, wildcard or trust
root was added.

## Reporting views and exact historical compatibility

Fresh `reporting_contract.consumer_view` maps node ID to label, parent ID to parent, and
passes literal, ownership and construct terms. It does not carry historical role/category/
obligation phrases, review names, run IDs, replay status or postdating metadata.

`reporting_qualification.reporting_view` is separately replay-only. It authenticates the
original D1 bundle, obtains the original request and scientific definitions, and copies the
confirmed overlay's nodes/order/construct terms. Only explicitly folded active scientific
children may be scientific-only; unresolved omissions fail. Its inspection provenance names
the original overlay and verified producer authorization and explicitly says the original
live run did not possess the new reporting contract.

This view remains outside the frozen output. It neither replaces original overlay bytes nor
inserts a new ref in D2/profile-A serialized outputs. Field/order equivalence is tested.
The D2 producer-only plan fields and output manifest remain exact; the fresh branch adds
its typed authority without rewriting historical schemas/identities.

## Recorded disposition repair

`recorded_sufficiency_identity.check_recorded_binding` validates the disposition/version
against the already authenticated event's authorized identity, requires a supported known
version, and checks every map child carries that version. D1 calls it only after its exact
receipt/profile enrollment and input checks. Unknown/forged disposition, changed event,
version or map still fails. Runtime `sufficiency_identity.read_map_identity` and its existing
current-relative authorization checker are untouched, preserving their routing purpose and
the pinned producer source manifest.

An executable scoped/restored test sets current semantics to v8 and simultaneously verifies:

1. A real public fresh v8 run is classified `current/v8`.
2. The old D1 authorization is identical and remains recorded `supported_noncurrent/v8`.
3. D2 combined output is exactly unchanged.
4. Explicit v8 scientific replay through legacy Layer C/plan-v4 has the exact profile-A hash.
5. The runtime checker still rejects falsely treating the old recorded pair as today's
   runtime pair. A forged replacement current receipt still fails D1 enrollment.

The old `test_future_current_v8_does_not_retroactively_authorize_noncurrent_receipt`
expectation was explicitly superseded by this authorized identity separation. Its replacement
checks preserved recorded authority **and** rejection of relabeling, not deletion of the gate.

Two existing static guards also required explicit E1B updates: the closed noncurrent
call-site inventory now includes the fresh issuer with an exact v8 check, and semantic
threading checks permit the captured version only inside `e2e.execute`. That version
starts as the current default and can change to v8 only inside the reviewed-input branch.
Other drivers still must pass the current constant. The focused routing run passed all
**147 tests in 15.84s**. These updates preserve bounded routing checks rather than globally
allowing arbitrary noncurrent execution.

## Public offline results and generality

Both decisive fixtures use independently authored flat scientific requirements and native
reporting, with actual ID `s1-o1`. Offline records enter only the established worker/recovery
stage boundaries; the scripted responsiveness client is a local test double. No final map,
proof, fresh credential or historical overlay is injected. U1/U2 and the shared consumers run.

| Control | Produced result | Selected output |
|---|---|---|
| Atomic alpha result | One v2 claim, no relation unit, node answered. | `We found alpha increased. [1]` |
| Instrument/direction relation | Existing deterministic instrument and direction strategies produce a joint proof; one relational v2 claim, one witnessed relation unit, node answered. | Same source sentence with proof-aligned member citation refs. |

Both initial-evidence and recovery-evidence variants pass. Recovery variants record
`W1,R1,C1,U1,P1,W2,R2,C2,U2`. Their preserved selected results are inspected in
`.local/i4-4e1b/atomic-summary.json` and `relational-summary.json`, with matching output and
scientific-map artifacts. The two citations on the relational sentence reflect the existing
typed member-source refs; citation presentation was not redesigned.

| Recovery control | Scientific map SHA-256 | Fresh output combined SHA-256 |
|---|---|---|
| Atomic | `b3930349c64ca8308157c4685b557fd12f4a888b46c4bb196c0319071e783be4` | `cc6f3738e079d8fe6a3e33f3683b13bde53563a4ff6dbbe923f2a6537a37b66f` |
| Relational | `d3276cd074eb12e0bfb8d5d9894e628ef81452cfe364983d4894fe588822b365` | `52ba021c0d6526eacddfefe72fb530d58ca8fc89fc53d412ec25dd2d859f8053` |

Atomic fresh provenance ref is
`trusted-fresh-invocation-v1:sha256:ddc3496bde1e9cc08cf85ea2aed79550f452f2f9c5a75eb460cbb525e2737036`;
relational ref is
`trusted-fresh-invocation-v1:sha256:1f25c38f3dfc5925281e813d40d47a9f1153ef06bba2ea70b1d799a86384935b`.
Both use native reporting ref
`reporting-contract-v1:sha256:dd1db814cf94fba799afaaeb8301554d72107562a504013ff269b57d71832c13`.
These are invocation/input identities, not registry credentials.

All accepted generic A–J controls are rerun: atomic value; same-proposition relation;
incompatible supports; positive category; null category; multiple members/no citation
borrowing; inherited context; nonrepresentative P2; opposite directions; legacy/default
compatibility. The detached semantic matrices remain unchanged; atomic/relational public
controls additionally prove the new entry. No claim that every synthetic case performed
upstream retrieval is made.

Static inspection of all new fresh modules rejects fixture IDs, historical paths/profiles,
producer/replay imports and fixture loaders. The actual fresh control also prohibits the
fixed sufficiency loader. Qualification imports remain confined to qualification modules;
the legacy runner retains its existing fixture route but the new public branch never uses
it as authoring. Fresh runtime semantic dependence on q_aib material is zero.

The map, authored inputs, recovery and search state are canonically compared immediately
before/after consumption, both in runtime and decisive tests. This covers requirements,
instances, bindings, candidates, attribution, policy/guards, observations, proofs/witnesses,
direction/effectiveness and recovery. Sealed input bytes are immutable. Substitution of
scientific inputs or review, runtime authoring mutation, fresh deserialization and fake
fresh authority are negative controls, not permitted recovery paths.

## Preserved identities

All hashes below were rerun in targeted qualification, without baseline updates.

| Artifact | Exact combined SHA-256 |
|---|---|
| v4 | `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a` |
| v5 | `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77` |
| v6 | `dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be` |
| v7 | `04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72` |
| v8 profile A | `1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0` |
| D2 profile B | `e697596b8fb3dd3ce426cdc1b82909ca93f4bbc3346e46b74bf2f96f980eafde` |

Original qualified profile remains
`qualified-producer-profile-v1:sha256:0c739b235dd983b77f3f9adfca22bebea90255f0f51f57f45cd7e699ef0bd2cd`;
receipt remains
`producer-output-receipt-v1:sha256:a040ad7757ee792e9c0a7f0414bead5ce22ed5eb5d19e1bdc37931b4f0d4071d`;
verified authorization remains
`verified-producer-authorization-v1:sha256:aa9ccbfa94f100a4c8cc0cbe85f60f27eebb289528e0f280447f0fcd23bb04b2`.

## Qualification and hooks

Targeted final run: **276 passed in 91.56s**. Final public/inspection rerun after output
consistency hardening: **14 passed in 6.11s**. Established optional psutil tests:
**7 passed in 7.71s**, using the dependency-complete Python environment and the offline guard.

Final full offline suite: **5,457 passed, 5 known failures, 12 skipped, 9 xfailed,
276 subtests passed in 294.77s**. Its failure inventory is exactly the independently
reconfirmed five below: **zero unexplained new failures**. The initial full run exposed
two additional obsolete routing expectations, explicitly revised as described above;
the final full run confirms those bounded checks and the rest of the suite together.

Final implementation hooks passed whitespace/EOF/conflict/large-file checks, Ruff format
and lint, Bandit, and Tach. The **only** failure is the unchanged pre-existing
`app/frontend/js/20_synthesis.jsx` at 615 lines. Its worktree and starting-HEAD blob both
equal `03f9d3dfee3763533a78d5da601a99cb81bb37f1`; no frontend change is staged. The user's
section 37 authorizes `--no-verify` for this E1B atomic commit only once all semantic,
identity and generality gates pass. No semantic/test/authentication failure is bypassed.

The five known failures independently reconfirmed in 10.89s are:

| Test | Existing cause |
|---|---|
| `ask_070/tests/test_corpus_and_referents.py::test_dev_eval_separation` | Missing frozen dev-input artifact. |
| `ask_070/tests/test_schema_validation.py::test_real_frozen_nonsemantic_artifact_schemas` | Missing frozen corpus-presence artifact. |
| `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored` | Offline guard denies Ollama tags probe. |
| `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts` | Pre-existing hierarchy_contract.py code-pin drift. |
| `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects` | Same hierarchy pin/readiness failure. |

No known failure is hidden, xfailed or repaired. Qualification uses
`.venv/Scripts/python.exe .local/i4-4c/run_offline.py`; the full command is `experiments -q
--tb=short --ignore=experiments/ask_cli_revised/contract_directed/tools/test_run_gate_integration_live.py
--junitxml=.local/i4-4e1b/full-final.xml`. That optional mocked module runs separately with
`C:/Users/cliff/anaconda3/python.exe` and the same guard. Logs/XML are under `.local/i4-4e1b`.
No external search, live retrieval/model/NLI or live E2E occurred.

## Exact implementation change set

All paths below are under `experiments/ask_cli_revised/`:

- New runtime: `reporting_contract.py`, `reviewed_ask_inputs.py`, `reviewed_ask.py`,
  `fresh_invocation.py`, `fresh_layerc.py`, `layerc_pipeline.py`.
- New qualification/identity: `reporting_qualification.py`, `recorded_sufficiency_identity.py`.
- Narrow existing runtime integration: `e2e.py`, `layerc_projection.py`,
  `answer_plan/plan_v5.py`, `profile_b.py`, `producer_authorization.py`.
- New tests: `test_reporting_contract.py`, `test_reviewed_fresh.py`,
  `test_fresh_recorded_identity.py`, `test_fresh_generality.py`, `test_fresh_static.py`.
- Updated exact boundary allowlists and authorized historical test expectation:
  `test_layerc_static.py`, `test_profile_b_static.py`, `test_producer_static_replay.py`,
  `test_producer_tamper.py`, `test_i4_3c0_supported_noncurrent.py`,
  `test_sufficiency_semantics_threading.py`.
- This results report and `CONTRIBUTION-LINEAGE.md` append.

## Scope limit and stop

This is a reviewed-authored fresh experimental path, not unattended scientific authoring
from arbitrary raw text. Scientific requirements and reporting decisions must already be
reviewed and invocation-owned. The product `/summarize` endpoint is unchanged. No automatic
promotion, E2, I2-3, new model pass or producer ecosystem follows from this increment.

**Shipping decision: READY FOR I4-4E2 PROMOTION.** Native reviewed reporting, actual public
flat/relational execution, selected v2 output, authority separation, recorded/current identity
coexistence, exact replay hashes and scientific immutability passed. The bounded E1B change
is authorized for one atomic commit/push with the documented line-cap exception. Stop after
E1B; promotion remains a separately authorized increment.
