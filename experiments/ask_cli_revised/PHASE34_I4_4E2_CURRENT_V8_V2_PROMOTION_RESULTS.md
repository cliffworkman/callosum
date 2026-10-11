# Phase 34 / I4-4E2 — current v8/v2 promotion gate result

**Current disposition: I4-4E2 COMPLETE — READY FOR BOUNDED I2-3.** The authorized
continuation promotes the reviewed Ask invocation to current v8/v2/plan-v5 while preserving
the exact historical installed producer and recorded identities. No I2-3 work begins here.

The initial STOP is preserved below as historical evidence. The later, explicitly authorized
continuation and its latest disposition are recorded in **Resumed E2: invocation-owned current
selection**, after the original Stop section. Statements about unchanged code or an uncommitted
stop in the historical section describe that first attempt, not the resumed implementation.

## Historical initial E2 attempt (preserved)

**STOP. Not ready for bounded I2-3.** The current-version constant is inside the
byte-pinned installed D1 producer source. Changing only that constant makes the accepted
reproduction issuer fail its source-identity check. The required qualification suite
therefore cannot remain passing under that promotion without resolving this boundary.

This is an installed-producer reproduction blocker, **not** a failure of persisted D1
consumption or E1B's recorded-disposition repair. Those remain valid and were rechecked.

## Checkpoint and final state

Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
Starting and final HEAD: `9c07c6ffb587bdcd6b677f13c7eced6a3b9cbf62`.
The worktree was clean at entry. No production file was changed, even temporarily.
The only tracked changes at stop are:

- `experiments/ask_cli_revised/PHASE34_I4_4E2_CURRENT_V8_V2_PROMOTION_RESULTS.md`
- `experiments/ask_cli_revised/CONTRIBUTION-LINEAGE.md` (append)

The promotion gates did not pass, so section 27's conditional implementation commit/push
was not performed. No hook bypass was used. These documentation changes remain uncommitted.

## Exact blocker and evidence

`sufficiency_engine.py:141` declares:

```python
SUFFICIENCY_SEMANTICS_VERSION = SUFFICIENCY_SEMANTICS_V7
```

The enrolled producer code manifest
`producer-code-input-manifest-v1:sha256:3ea98ca41a74f6fdb6fc4e4391032ecb7c2b6b361eead954d560a02081670625`
pins all of this file, including the declaration. The encoding contract permits universal
newline normalization only. It does not exempt default declarations, comments or other
non-scientific changes.

`producer_replay._verify_installed_producer` compares the installed file bytes with that
manifest. `reproduce_accepted_v8` calls it before reading event inputs or executing the
producer. This is an intentional issuer boundary; the existing source-drift test requires
rejection before production. Multiple required D1/D2 qualification fixtures call this issuer
to establish their actual reproduced inputs.

The local offline probe `.local/i4-4e2/test_promotion_pin.py`:

1. Successfully reproduced the accepted event with the unchanged installed source.
2. Constructed an in-memory copy of the source differing in exactly one declaration:
   `SUFFICIENCY_SEMANTICS_VERSION = SUFFICIENCY_SEMANTICS_V8`.
3. Scoped the runtime current constant to v8 and made `Path.read_bytes` return that copy
   only for the engine path. All other source/material/input bytes remained original.
4. Verified the already-produced persisted bundle and rebuilt D2 with its exact original hash.
5. Called the real reproduction issuer and observed the precise rejection below.
6. Restored both scoped patches and asserted original source bytes and current-v7 identity.

| Source identity | SHA-256 after enrolled newline normalization |
|---|---|
| Actual source / enrolled pin | `69f8d1970aa5bc56647f81035d77d26eb31ae7f18b4a374c4c20a4accc4b6245` |
| One-line promoted source | `79d8c152cdf35e51f54f647fca39107e4a839e6c28ddb197738e30d4b052b3f6` |

Observed issuer error:

```text
producer source drift: experiments/ask_cli_revised/sufficiency_engine.py
```

Evidence is preserved locally in `.local/i4-4e2/promotion-pin-evidence.json`,
`pin-gate.log` and `pin-gate.xml`. This is a counterfactual source-read test, not a real
promotion, not a new baseline, and not a claim that post-promotion execution qualified.

The scoped current-v8 test in E1B changed a Python attribute after import. It did not alter
the pinned file bytes. That explains why its identity-coexistence result was correct while
it did not expose this additional installed-source boundary.

No pin was normalized around the changed declaration; no expected hash, registry, receipt,
profile, source verifier or qualification fixture was weakened. No code was moved merely
to conceal the change from the pinned source check. Resolving how historical reproduction
uses its exact installed producer while current runtime defaults advance is the single
remaining promotion prerequisite; this stop does not start another architecture increment.

## Defaults, routing and scope audit

| Item | Before | After this stopped increment |
|---|---|---|
| `sufficiency_engine.SUFFICIENCY_SEMANTICS_VERSION` | v7 | v7, unchanged; requested v8 promotion not applied |
| `answer_plan.plan.PLAN_VERSION` | answer-plan-step2-v4 | unchanged legacy serializer identity |
| `answer_plan.plan_v5.PLAN_VERSION` | answer-plan-step2-v5 | unchanged v2 serializer identity |
| Reviewed fresh entry | `reviewed_ask.run_reviewed_request` | unchanged E1B route |
| Reviewed fresh authority | trusted_fresh_invocation | unchanged, distinct from persisted D1 |
| Reviewed fresh science | explicit v8, runtime supported_noncurrent | unchanged |
| Reviewed fresh selected answer | shared Layer C v2 / plan-v5 | unchanged |

The existing v4 plan constant is used by the legacy serializer and explicit replay; changing
it globally would relabel old objects without converting their schemas. The fresh v2 pipeline
already imports `plan_v5`. No textual v4 replacement or partial plan-default promotion was made.

The current fresh entry requires bound, jointly reviewed request, scientific definitions,
native reporting-contract-v1 and scientific parent context. There is no missing-reporting
fallback or raw-text scientific authoring. Its existing implementation contains no fixture
loader, Phase-30 overlay, D1 receipt or q_aib input dependency. This increment introduces none.
Replay qualification retains its separate authenticated, fixture-specific path.

No scientific mapping, candidates, attribution, guards/policy, category logic, proofs,
witnesses, direction/effectiveness or recovery changed. Existing v8 characterization is
reproducible; real before/after-promotion scientific equality is **not claimed**, because
the promotion stopped before production edits.

## Qualification performed

**49 passed in 35.53s**, using the existing offline runner and network guard:

```text
.venv/Scripts/python.exe .local/i4-4c/run_offline.py
  .local/i4-4e2/test_promotion_pin.py
  experiments/ask_cli_revised/test_producer_store_issuer.py
  experiments/ask_cli_revised/test_producer_authorization.py
  experiments/ask_cli_revised/test_fresh_recorded_identity.py
  experiments/ask_cli_revised/test_producer_static_replay.py
  -q --tb=short --junitxml=.local/i4-4e2/pin-gate.xml
```

The passing probe means it successfully demonstrated the expected rejection; it does not
mean promotion passed. These controls recheck D1 enrollment and actual reproduction,
pure consumption, source-drift rejection, fixed issuer scope, exact historical replay,
recorded/current coexistence, forged relabeling rejection and D2 equality. The E1B scoped
identity test also reran a public atomic fresh current-v8 control, then restored v7.

The full promotion suite, optional psutil suite, public relational promotion control,
generic A-J and new promotion guards were not run/implemented after the hard prerequisite
failure. No successful real current-v8 default, plan-v5 default or post-promotion generality
result is claimed. No live model, retrieval, NLI, external search or live E2E occurred.

## Historical results rechecked

The selected exact-characterization tests reproduced v4-v8 under the unchanged checkout.
The probe and recorded-identity tests reproduced D2 even with the hypothetical current-v8
identity and promoted source read. Expected historical hashes were never updated.

| Artifact | Exact combined SHA-256 |
|---|---|
| v4 | `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a` |
| v5 | `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77` |
| v6 | `dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be` |
| v7 | `04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72` |
| v8 profile A | `1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0` |
| D2 profile B | `e697596b8fb3dd3ce426cdc1b82909ca93f4bbc3346e46b74bf2f96f980eafde` |

Unchanged qualified profile:
`qualified-producer-profile-v1:sha256:0c739b235dd983b77f3f9adfca22bebea90255f0f51f57f45cd7e699ef0bd2cd`.
Unchanged receipt:
`producer-output-receipt-v1:sha256:a040ad7757ee792e9c0a7f0414bead5ce22ed5eb5d19e1bdc37931b4f0d4071d`.
Unchanged verified authorization:
`verified-producer-authorization-v1:sha256:aa9ccbfa94f100a4c8cc0cbe85f60f27eebb289528e0f280447f0fcd23bb04b2`.
No current replacement receipt was issued; the registry is untouched.

## Full-suite baseline: prior evidence only

E1B at the starting HEAD reported 5,457 passed, five known failures, 12 skipped,
9 xfailed and 276 passing subtests; optional psutil tests passed 7. These are **E1B results**,
not E2 reruns. Its independently confirmed known failures were:

- `ask_070/tests/test_corpus_and_referents.py::test_dev_eval_separation`: absent frozen dev-input artifact.
- `ask_070/tests/test_schema_validation.py::test_real_frozen_nonsemantic_artifact_schemas`: absent frozen corpus-presence artifact.
- `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`: offline Ollama tags probe denied.
- `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`: existing hierarchy code-pin drift.
- `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`: same hierarchy readiness failure.

The new promotion source-pin failure is separate from these five. It was not reclassified
as a known baseline failure, xfailed or hidden by changing fixtures.

## Stop

**STOP: the promoted current constant changes the enrolled installed-producer source
identity and prevents required D1 reproduction qualification.** Persisted consumption is
still valid; E1B's current-versus-recorded identity fix remains correct. There is no claim
of scientific drift or corrupted old receipt. No promotion commit/push, I2-3, product
endpoint/frontend integration, raw-text authoring, v9 or new architecture follows here.

## Resumed E2: invocation-owned current selection

Cliff Workman explicitly authorized resolving the demonstrated coupling as a bounded
continuation. His preferred direction was to locate current selection at the reviewed Ask
invocation/routing boundary, subject to actual call-graph inspection. Codex traced the callers,
implemented the small boundary change below and retained the original STOP evidence above.

Continuation starting HEAD is `9c07c6ffb587bdcd6b677f13c7eced6a3b9cbf62`, with exactly the
initial stop report and lineage append pending. No pre-existing work was discarded. The final
implementation HEAD is the atomic commit containing this report and continuation; its full
hash is reported after commit/push, avoiding a self-referential document hash.

### Call-graph audit and reason the separation is legitimate

The pinned engine already requires an explicit semantic version at lower scientific entry
points. Its versioned v8 implementations do not need its current-v7 declaration to become v8.
The existing reviewed route already uses those implementations through `e2e.execute`. What
remained coupled was selection/classification at the fresh invocation boundary.

| Consumer / boundary | Audited behavior and disposition |
|---|---|
| `sufficiency_engine.py` | The current-v7 declaration is also referenced when defining the supported set. Keep the entire enrolled file unchanged; explicit v8 remains supported. |
| `sufficiency_identity.py` | Pinned legacy map reader, explicit historical/noncurrent opt-ins, and historical-unversioned applied semantics retain their original v7-relative behavior. The single explicit `stamp_map` path is unchanged. |
| `e2e.execute` legacy branch | Continues to capture the engine's legacy default. Existing non-reviewed experiment routes retain behavior. |
| `e2e.execute` reviewed branch | Takes `fresh_execution.semantics_version` from the active reviewed invocation before stages run. Every existing U1/U2, observation, recovery and search-semantics call uses that local value. |
| `_parent_synthesis_outputs` in `e2e.py` | Uses the legacy declaration; fresh execution never enters this legacy parent-output helper. |
| Phase 13, Phase 15, Phase 21, Phase 23 drivers; `sufficiency_model_nomination_diagnostic`, `sufficiency_recovery_targets_inventory`, `parent_synthesis_test_support` | All other non-test consumers of the pinned current declaration are historical/legacy experiment or support drivers. They are not the rebuilt reviewed public entry and remain unchanged. |
| `reviewed_ask.run_reviewed_request` | Validates invocation-owned joint review and enters existing `e2e.execute`. No version/profile/noncurrent option is needed. Exposes the current science and plan identities of this route. |
| `fresh_invocation._Execution` | Captures current selection, then requires every produced map child to carry that exact version before issuing the existing trusted fresh capability. Classifies this actual execution as current. |
| `producer_replay` | Verifies all 26 installed source pins and explicitly passes v8 to the existing mapper, aligned observations and recovery. No current selection or enrolled source changes. |
| `recorded_sufficiency_identity` / D1 verifier | Continue authenticating the enrolled recorded disposition, independent of the new fresh default. No relabeling or new receipt. |
| `layerc_pipeline` / `plan_v5` | Existing shared v2 pipeline already selects the v5 serializer. The reviewed current plan identity aliases that actual serializer constant. Legacy `plan.py` stays v4. |

This is not code movement to evade a fingerprint. No pinned function, declaration or
scientific algorithm moved. The existing active invocation now owns the choice it passes to
the existing version-explicit science. It also owns classification of that execution, while
the old artifact reader and authenticated recorded-event checker keep their respective jobs.
There is no mutable global version patch, source-normalization exception, new registry,
parallel scientific pipeline or new version.

### Minimal implementation and exact change set

All changed files are under `experiments/ask_cli_revised/`:

| File | Change |
|---|---|
| `fresh_invocation.py` | Defines current science=v8 and current plan as the actual v5 serializer identity. Captures science at invocation start; validates a nonempty, uniformly stamped produced map and issues current/v8 provenance. Removes the legacy supported-noncurrent reader from the active fresh path. |
| `e2e.py` | One selection line reads the active invocation's captured version instead of a separately hardcoded v8 constant. Existing scientific calls already thread this local version. |
| `reviewed_ask.py` | Exposes the reviewed route's current science/plan constants and documents their scope. Public runner signature and authoring requirements stay unchanged. |
| `fresh_layerc.py` | Checks the output plan against the route's current plan identity, which aliases `plan_v5.PLAN_VERSION`. |
| `answer_plan/plan_v5.py` | Docstring only: identifies current reviewed Ask and explicit persisted qualification as its callers. Serializer and plan semantics are unchanged. |
| `test_reviewed_ask_promotion.py` | Actual public U1/U2 version threading and scientific parity; all 26 pins; installed issuer/current-fresh coexistence; forged identity and malformed/wrong-version map rejection. |
| `test_reviewed_fresh.py` | Replaces the old noncurrent expectation and hypothetical-current-only test with real current execution, retaining atomic/relational and initial/recovery controls. |
| `test_fresh_static.py` | Guards captured invocation selection, no global version patching and no historical reader/noncurrent opt-in in fresh issuance. Existing fixture-independence guards remain. |
| `test_i4_3c0_supported_noncurrent.py` | Removes the no-longer-used fresh opt-in call from the closed inventory; legacy explicit opt-ins remain. |
| `test_sufficiency_semantics_threading.py` | Exact AST expectation follows the invocation-owned selection; other driver constraints are unchanged. |
| This report and `CONTRIBUTION-LINEAGE.md` | Preserve initial STOP and append authorized resolution, evidence and disposition. |

The source-pin manifest, its 26 files, D1 issuer/verifier/materials, registry, historical
baselines, legacy plan serializer, application endpoint and frontend are untouched.

### Current versus historical identities after the continuation

| Route | Science/disposition | Answer layer / authority |
|---|---|---|
| Public reviewed authored Ask, ordinary call | **current / sufficiency-semantics-v8** | Native reporting-contract-v1, trusted_fresh_invocation, shared Layer C v2, parent-synthesis-v2, **answer-plan-step2-v5**, selected v2 render |
| Pinned legacy driver / historical reader | Original v7-relative selection/classification | Original explicit legacy controls and plan-v4 |
| Explicit profile A v8 characterization | Original supported_noncurrent/v8 replay identity | Exact legacy Layer C / plan-v4 |
| Persisted D2 profile B | Original recorded supported_noncurrent/v8 | VerifiedProducerAuthorization, original overlay serialization, v2/plan-v5, exact D2 hash |

`reviewed_ask.CURRENT_SEMANTICS_VERSION` is `sufficiency-semantics-v8` and
`reviewed_ask.CURRENT_PLAN_VERSION` is `answer-plan-step2-v5`. These are the rebuilt
reviewed Ask defaults. The pinned `se.SUFFICIENCY_SEMANTICS_VERSION` stays v7 because it
belongs to the retained historical implementation; it is not consulted for fresh selection.
No caller supplies a special noncurrent flag or qualification profile to obtain current Ask.

The private fresh execution capability, actual post-production handoff and exact map/version
validation establish the current execution context. A dictionary carrying a matching version
still cannot create fresh provenance or substitute for the capability. Missing, empty, mixed,
unknown, non-string, non-mapping or v7 map identities fail. Persisted inputs remain on their
existing authenticated path. The strict legacy reader still rejects v8 without its own opt-in;
it is not repurposed to rewrite historical dispositions.

### Scientific and public-route evidence

The actual public atomic and relational fixtures run without a version/profile opt-in and
without monkeypatching any version constant. Offline test doubles provide evidence only at
the existing worker/recovery boundaries. Real U1/U2, aligned observations, recovery and shared
Layer C run. Both initial-evidence and recovery-evidence variants select v2 rendering.
The recovery variants record `W1,R1,C1,U1,P1,W2,R2,C2,U2`.

Both final map hashes equal the preserved E1B scientific outputs:

- Atomic: `b3930349c64ca8308157c4685b557fd12f4a888b46c4bb196c0319071e783be4`.
- Relational: `d3276cd074eb12e0bfb8d5d9894e628ef81452cfe364983d4894fe588822b365`.

The local inspection controls additionally compare complete map dictionaries and every
invocation provenance field other than disposition against the E1B artifacts. This includes
authored definitions, sealed identities, ownership context, recovery and search state.
The selected rendered text is also exactly equal. Only fresh execution disposition changes
from supported_noncurrent to current; its content-addressed provenance and downstream
identity-bearing envelopes consequently receive new refs. These are not replacements for
historical E1B or D2 artifacts. E1B files remain preserved in `.local/i4-4e1b`.

Atomic selected text remains `We found alpha increased. [1]`. The relational sentence retains
its proof-aligned member citations `[1][2]`; no representative or cross-member evidence is
borrowed. The unchanged A-J controls cover atomic, same-proposition, incompatible supports,
positive/null categories, independent members, inheritance, nonrepresentative P2, opposite
direction and explicit legacy compatibility. They exercise the existing shared consumer
semantics; they are not claimed to be ten new live retrieval runs.

The new coexistence test reads all 26 installed source fingerprints, reproduces D1 with the
unchanged issuer, runs current public Ask, re-verifies the old authorization and rejects a
forged current receipt. Existing D1 tamper tests, exact v4-v8 replay and D2 tests retain their
expected identities. The six historical hashes and three D1 IDs listed above remain frozen.

### Continuation qualification and shipping disposition

Initial routing qualification: **165 passed in 53.77s**. Optional mocked psutil qualification:
**7 passed in 9.79s**. Independent reproduction of the exact five known failures:
**5 failed in 13.07s**, with the same causes listed in the historical section. None is
reclassified, hidden or repaired by this increment.

Broad targeted qualification: **442 passed in 114.11s**, including the two local full-map/
provenance comparisons. The final full offline run reports **5,468 passed, exactly 5 known
failures, 12 skipped, 9 xfailed and 276 passing subtests in 374.66s**. Its failure inventory
matches the independent five-failure rerun: **zero unexplained new failures**. These are
actual E2 runs, not the E1B counts. Continuation logs/XML are under `.local/i4-4e2`; earlier
stop-probe results remain distinct. No live model/retrieval/NLI/E2E or external search was
used. All substantive gates passed for the authorized atomic promotion commit/push.

Targeted command uses `.venv/Scripts/python.exe .local/i4-4c/run_offline.py` with these paths
under `experiments/ask_cli_revised/`:

```text
test_reviewed_ask_promotion.py test_reviewed_fresh.py test_reporting_contract.py
test_fresh_generality.py test_fresh_recorded_identity.py test_fresh_static.py
test_sufficiency_semantics_threading.py test_i4_3c0_supported_noncurrent.py
test_i4_3c_replay.py test_producer_authorization.py test_producer_store_issuer.py
test_producer_tamper.py test_producer_static_replay.py test_profile_b.py
test_profile_b_matrix.py test_profile_b_static.py test_layerc_static.py
```

It also includes `.local/i4-4e2/test_current_inspection.py` and ends with
`-q --tb=short --junitxml=.local/i4-4e2/targeted.xml`. Full offline command:

```text
.venv/Scripts/python.exe .local/i4-4c/run_offline.py experiments -q --tb=short --ignore=experiments/ask_cli_revised/contract_directed/tools/test_run_gate_integration_live.py --junitxml=.local/i4-4e2/full.xml
```

The excluded mocked optional module runs separately with
`C:/Users/cliff/anaconda3/python.exe .local/i4-4c/run_offline.py` and the exact module path,
`-q --tb=short --junitxml=.local/i4-4e2/optional.xml`. The independent known-failure command
uses the five exact node IDs listed above, with the same offline runner and
`-q --tb=short --junitxml=.local/i4-4e2/known-five.xml`.

Current-control output artifacts are `.local/i4-4e2/atomic-current-output.json` and
`relational-current-output.json`, with corresponding summary files. Their combined hashes
are respectively `bdf870f3c56df1913cdebc9108aecc1730942a236e8017583884a6ab65cbe0e9`
and `ccfd340d3657361c3cbf32338421fdbcd6fbb44c750c6d4e30432ee0182fb5b4`.
These are new current invocation envelopes over unchanged science, not historical hash updates.

All final implementation hooks passed except the pre-existing 615-line cap in
`app/frontend/js/20_synthesis.jsx`: whitespace/EOF/conflict/large-file checks, Ruff formatting
and lint, Bandit and Tach passed. Frontend worktree and starting-HEAD blobs both equal
`03f9d3dfee3763533a78d5da601a99cb81bb37f1`. There are no staged application/frontend changes.
The user's E2-only `--no-verify` authorization applies only after all substantive gates pass;
no source pin, authority, semantic, historical-hash or qualification failure is bypassed.

Current promotion remains experimental rebuilt Ask only. It requires jointly reviewed
scientific and reporting inputs; it does not claim unattended raw-question authoring or
completed application integration. I2-3, live scientific qualification, application/frontend
integration and release qualification are later work. Stop after this bounded E2 continuation.

**I4-4E2 complete. READY FOR BOUNDED I2-3.** New reviewed Ask uses v8/v2/plan-v5 as its
current scientific-answer route, and historical D1/D2 reproduction and authorization remain
valid under their exact recorded identities. The initial STOP was resolved within the
existing invocation boundary; no additional architecture or scientific semantics were added.
