# Phase 34 / I4-4D — producer-authorization prerequisite stop

Date: 2026-10-10. **NOT READY; consumer integration not started.**

Canonical branch: experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z.

Starting and final implementation HEAD:
b75c6f2fd48975a702713e34436ce4b7d81dabe0.
The full requested HEAD and clean worktree were verified before inspection.
No implementation commit or push was made. Only this report and the lineage append are tracked changes.

## Required stop

I4-4D §4 explicitly requires:

> If existing producer authorization cannot authenticate the required inputs without a new explicit receipt field: STOP and report.

That condition applies. Existing code validates digest consistency and exact sufficiency identity,
but the accepted v8 production/replay path does not provide the authenticated producer/output receipt
required by this request. Creating that missing authority would be an additional prerequisite
contract, not merely resolving an existing receipt.

The I4-4C acceptance remains intact: it intentionally delegates producer authentication to its caller.
The block is at the new caller boundary required for I4-4D.

## Evidence inspected

| Existing component | What it establishes | What it does not establish |
|---|---|---|
| sufficiency_identity.py:126, check_authorization_binding | Exact status/version equality against the map, including supported_noncurrent | Producer authority or source/input provenance; its docstring explicitly describes consistency |
| answer_plan/replay.py:113, verify_replay_authorization | Body digest, exact semantics identity, containment/direction equality | Authentication of producer, bound map contents, sealed bytes, authored inputs or overlay |
| answer_plan/replay.py:189, authorization_body | Locally constructs a replay decomposition record from supplied artifacts and overlay; records several hashes | An independently accepted producer/output authorization receipt |
| layerc_projection.py:74, _profile | Exact profile fields, bound input hashes, producer-map digest and receipt/profile digest arithmetic | Whether the producer identity is authorized; any nonempty producer string satisfies that identity check |
| test_layerc_projection.py:30, profile | Builds consistent test input/profile material | A production authorization issuer; offline-qualified-v8-producer is a fixture string |
| test_i4_2a_replay.py:59, remap | Accepted deterministic mapper replay with preserved nominations and offline source context | A producer authorization receipt; its result is scientific/characterization data |
| witness_i4_3c_replay_baseline.json | Accepted combined v8 characterization hash and inventory | A producer receipt binding every input needed by profile B |

Repository searches for producer_authorization, producer_receipt, authorized_producer,
output_authorization and offline-qualified-v8-producer found no additional implementation of
an authenticated v8 producer receipt. The last string appears in the substrate test helper.
The existing Phase-30 overlay is decomposition authorization, not authorization of the v8 producer.

The committed characterization baseline and I4-4C report are useful independent qualification
evidence. They must not silently be reinterpreted as a runtime producer-authority contract.
The combined replay digest is not the profile-B input receipt, and the substrate fixture derives
its authored requirements from the supplied map. Recomputing those hashes alone does not establish
independent authoring or producer authority.

## Read-only executable probes

Ignored audit script: .local/i4-4d/test_authorization_boundary.py.
Log: .local/i4-4d/authorization-boundary.log.
Executed with the existing socket-denying offline launcher:

~~~text
.venv/Scripts/python.exe .local/i4-4c/run_offline.py
  .local/i4-4d/test_authorization_boundary.py -q --tb=short
~~~

**Four probes passed in 5.29 seconds.** These confirm the prerequisite gap; they are not passing
qualification tests for an I4-4D implementation.

| Probe against unchanged production code | Observed result |
|---|---|
| Rebuild the accepted real v8 map offline; replace the profile producer identity with unregistered-audit-producer; recompute its receipt and profile digests | validate_layerc_inputs accepts it and retains that producer identity |
| Change the producer identity without updating its receipt digest | Substrate rejects the stale producer receipt |
| Give the legacy verifier a self-consistent authorization with valid v8 identity but zero map/contract/claim hashes and an unauthenticated sealed hash | verify_replay_authorization accepts it; it does not authenticate those fields |
| Change the authorization status to current, recompute the digest, retain the v8 map | Exact identity check rejects it |

The first probe calls the complete substrate over the real preserved inputs and checks deep input
equality before/after. The synthetic authorization in the third probe isolates the verifier's
existing scope; it is not asserted to be a complete record emitted by replay.main.

No production function was changed or monkeypatched for authorization acceptance. The reused
accepted replay helper holds model nominations fixed as it already does. No model, retrieval,
NLI, live E2E or external search was invoked. Socket connections were denied throughout.

## Why integration cannot safely proceed under this request

A caller checking only the existing record's self-hash could accept a self-authored producer label
and self-authored input bindings. A fixed producer-name comparison alone would still permit the
same label to be asserted without provenance. Neither satisfies §4.

The requested profile-B output authorization extension (§31) is downstream and noncircular:
it binds outputs after construction. It cannot authenticate the upstream producer merely by
hashing those outputs. No projection/claim/plan output hash is used as a substitute for missing
input authority.

The smallest next prerequisite is an explicitly specified producer authorization receipt and
verification boundary, issued by the accepted upstream path and anchored independently of
caller-supplied hashes. Its contract must bind the producer/output identity, exact v8 noncurrent
identity, map and sealed inputs, authored contract/overlay, and applicable semantics. An
offline-only pinned accepted-input manifest may be a design option, but selecting it as the
trust anchor requires an explicit contract; it is not implemented or silently inferred here.

Keep I4-3C0's exact status/version equality unchanged. A future repair must reject unknown issuers,
rehashed unauthorized input substitutions and incompatible profiles while preserving accepted
legacy replay behavior. This report proposes no new schema field spelling or unreviewed issuer.

## Qualification and activation status

| Requested gate | Status |
|---|---|
| Starting branch, full HEAD, clean tree | Verified |
| Existing producer authentication prerequisite | BLOCKED |
| Four diagnostic boundary probes | Passed, gap reproduced |
| parent-claim-v2 / claim-evidence-v1 / relation-unit-v2 integration | Not started |
| parent-synthesis-v2 / answer-plan-step2-v5 activation | Not started |
| Exact 17 claims, 32 values, 41 units and nine-node integration result | Not qualified for profile B |
| p8/p36, implicit null, P2 witness and conflict consumer controls | Not run; no consumers implemented |
| New profile-B baseline/output authorization | Not generated |
| Full I4-4D suite, five known failure reconfirmations, optional module and hooks | Not run after prerequisite stop |
| Historical v4-v8 replay baselines | Not modified; not newly rerun in this audit |
| READY for I4-4E promotion decision | **NOT READY** |

Previous I4-4C qualification results remain recorded in its accepted report and are not presented
as new I4-4D results. No prospective counts, hashes or consumer tests are reported as achieved.

SUFFICIENCY_SEMANTICS_VERSION remains sufficiency-semantics-v7; PLAN_VERSION remains
answer-plan-step2-v4. V8 remains supported_noncurrent. No new profile routing or consumer entry
point was added. No scientific map, proof, receipt, candidate, role/category state, recovery,
observation, model nomination or query text was written back.

## Exact files changed and stop

Tracked documentation only:

- PHASE34_I4_4D_PROOF_ALIGNED_CLAIM_PLAN_INTEGRATION_RESULTS.md
- CONTRIBUTION-LINEAGE.md

Both remain uncommitted. Section 45 permits an integration commit only when every gate passes;
that condition is unmet. No hook bypass, implementation commit or push was attempted.

**STOP at I4-4D §4.** No promotion, I4-4E, I2-3, same_local_assertion or claim-goal/authority-veto
work. Resume consumer integration only after the missing producer-authorization prerequisite
has an accepted contract and implementation.
