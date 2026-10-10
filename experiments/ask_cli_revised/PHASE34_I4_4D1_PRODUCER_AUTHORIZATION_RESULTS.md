# Phase 34 / I4-4D1 — pinned producer authorization results

Date: 2026-10-10. Bounded prerequisite implementation for accepted I4-4D0 Option A.
**READY to resume I4-4D separately: producer authorization prerequisite implemented and qualified.**

## Checkpoint and change boundary

Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
The only starting changes were the accepted D0 design report and lineage append.
They were committed and pushed, with normal documentation hooks passing, as
**8d2003b7f79665e2858751cea9442228e8b5c853**. D1 started from that clean HEAD.

The final implementation HEAD is the single commit containing this report; resolve it with
`git log -1 --format=%H -- experiments/ask_cli_revised/PHASE34_I4_4D1_PRODUCER_AUTHORIZATION_RESULTS.md`.
Its full hash is reported in the delivery message. A document cannot embed its own commit hash.

Exactly 19 changed files, all under `experiments/ask_cli_revised/`:

- `_producer_schema.py`: closed material validation, canonical identity and immutable types.
- `_producer_inputs.py`: pure actual-snapshot and independent authored/nomination checks.
- `producer_authorization.py`: pure verification and lifecycle/enrollment resolution.
- `producer_authorization_store.py`: fixed repository loader.
- `producer_replay.py`: one bounded reproduction and receipt issuance boundary.
- `producer_authorization.registry.json`: exact D0 registry.
- `producer_authorization_material/preserved-nomination-input-manifest-v1--4aac7557e6421be49255ffdeefd26508dd7b92856f88afdd291c4e6dc0a8710c.json`
- `producer_authorization_material/producer-code-input-manifest-v1--3ea98ca41a74f6fdb6fc4e4391032ecb7c2b6b361eead954d560a02081670625.json`
- `producer_authorization_material/producer-event-input-manifest-v1--5ce389c0bd2baec24044131ddd464b309308a592c33a34032d8acf3f57d3ea3e.json`
- `producer_authorization_material/producer-output-receipt-v1--a040ad7757ee792e9c0a7f0414bead5ce22ed5eb5d19e1bdc37931b4f0d4071d.json`
- `producer_authorization_material/qualified-producer-profile-v1--0c739b235dd983b77f3f9adfca22bebea90255f0f51f57f45cd7e699ef0bd2cd.json`
- `producer_authorization_material/reviewed-authored-inputs-v1--2187272f3314817ca687fd1add912c4b178b68063c864d16024cc8db14cd8a83.json`
- `test_producer_authorization.py`
- `test_producer_tamper.py`
- `test_producer_store_issuer.py`
- `test_producer_static_replay.py`
- `test_i4_2b3_attribution.py`: add only the new fixed issuer to the ownership-context
  consumer allowlist; existing attribution and unauthorized-consumer guards remain unchanged.
- This results report.
- `CONTRIBUTION-LINEAGE.md` append.

The 26 scientific producer source files, existing production consumers, historical artifacts, replay
baselines and version/default routing are unchanged. The two internal helpers separate shared
closed data handling from pure snapshot checks; they add no scientific decisions.

## Trust statement and fixed root

The trusted installation explicitly authorizes one producer implementation/configuration and
one exact deterministic reproduced output event. The trust root is repository-pinned enrollment,
not a content hash by itself. A known producer or valid profile does not authorize a new output.

Threats A-D from D0 are covered relative to trusted repository/verifier/process code: malformed
caller data, unqualified producers, wrong replay code/inputs/profile, and runtime-artifact
substitution. Threat E—replacement of the repository, registry, verifier or arbitrary process
code—is outside this model. There is no signature, signing key, release-key reuse, Minisign,
network verification, remote identity, nonrepudiation or wall-clock execution proof.

`load_trusted_producer_registry()` has no parameters. It resolves the fixed root and material
store relative to its own module, independent of caller cwd/environment. Reference filenames
derive only from validated full schema/hash IDs, with resolved-path containment. Missing material,
unknown schemas, traversal, duplicate JSON keys, unknown/missing fields, malformed full IDs and
nonfinite values (including exponent overflow) fail. There is no alternate/latest/remote registry.

A raw dictionary is not a `TrustedProducerRegistry`. The fixed loader constructs a frozen
object with a private loader-origin token and recursively immutable material/body snapshots.
The pure verifier requires this exact type/provenance and revalidates its content identity.
The explicit synthetic-registry helper lives in tests; no public issuer or profile-B interface
accepts root replacement. Python privacy is not asserted against arbitrary in-process code.
Consumers must load the installation's current root; retaining/replacing internal objects through
arbitrary code is not an ordinary caller capability.

Closed lifecycle behavior is active=(issue, consume), retired=(no issue, consume), and
revoked=(no issue, no consume; archival inspection only). Contradictory flags and unknown states
fail. An additive trusted-root update preserves old receipt consumption only while profile
consumption and exact semantic identity remain compatible. No runtime enrollment exists.

## Exact material qualification

All seven preregistered canonical bodies and IDs match D0 exactly. Canonical serialization is
UTF-8, sorted keys, compact separators, ensure_ascii=False, allow_nan=False; bodies contain no
self-ID field. Full content references are schema:sha256:lowercase-full-hash.

| Material / closed schema | Exact content ID |
|---|---|
| Authored inputs | reviewed-authored-inputs-v1:sha256:2187272f3314817ca687fd1add912c4b178b68063c864d16024cc8db14cd8a83 |
| Code manifest | producer-code-input-manifest-v1:sha256:3ea98ca41a74f6fdb6fc4e4391032ecb7c2b6b361eead954d560a02081670625 |
| Event inputs | producer-event-input-manifest-v1:sha256:5ce389c0bd2baec24044131ddd464b309308a592c33a34032d8acf3f57d3ea3e |
| Nomination inputs | preserved-nomination-input-manifest-v1:sha256:4aac7557e6421be49255ffdeefd26508dd7b92856f88afdd291c4e6dc0a8710c |
| Profile | qualified-producer-profile-v1:sha256:0c739b235dd983b77f3f9adfca22bebea90255f0f51f57f45cd7e699ef0bd2cd |
| Receipt | producer-output-receipt-v1:sha256:a040ad7757ee792e9c0a7f0414bead5ce22ed5eb5d19e1bdc37931b4f0d4071d |
| Registry | producer-authorization-registry-v1:sha256:3ca420b42e64046470738773b2affad9509ffbab4f0b0df166963fcc0308d0ef |

Registry inventory is exactly one active profile (issue=true, consume=true) and one accepted
receipt with the exact profile/input-manifest refs and purpose `profile-b-offline-prerequisite`.
There are no v4-v7 entries or wildcard events.

Profile identity remains `callosum.qaib.preserved-v8-reproduction`,
`diagnostic-map-plus-aligned-observations/v8`, `supported_noncurrent/sufficiency-semantics-v8`,
issuer contract `reproduce-pinned-v8-then-issue-v1`, and
`registry-enrolled-reproduction-only`. Fresh model/retrieval/NLI permission remains false.

## Issuance and independently bound inputs

Public API: `producer_replay.reproduce_accepted_v8(*, output_dir=None)`.
It accepts no completed map, nomination provider, registry, scientific input path or alternate
trust root. The optional directory is nonsemantic and must be new; repository-local output is
restricted to `.local/i4-4d1/`, and historical/material directories are protected.

The issuer resolves the enrolled target and active lifecycle, verifies CPython **3.12.7**, and
reads/verifies all **26 installed source files** before reproduction. Source fingerprints use
UTF-8 with CRLF/CR normalized to LF and no other normalization. Source drift or runtime mismatch
fails before production. New trust orchestration files are outside this scientific manifest,
as preregistered; no profile/code-manifest ID was changed to include them.

It snapshots and byte-verifies **19 event-input files** once. Independent frozen authoring is
loaded through unchanged `sufficiency_freeze.load_verified`, using private temporary files made
from already verified frozen/review snapshots. It never rereads the mutable original paths.
Pure verification separately checks the reviewed data hashes and requirements. Authority does
not come from the output map's requirements.

- Reviewed frozen v9 combined hash:
  `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.
- Canonical authored requirements:
  `8b219f093c31e7e64215381ac4ef4113d96a1e33320be891fbbae567e541d0dc`.
- Reviewed hierarchy source bytes, pins/review record and derived parent map match D0. Existing
  live hierarchy code-pin drift remains a known failing control; no pins were regenerated,
  hierarchy check weakened, or old live check reported passing.
- Exact Phase-30 overlay bytes/canonical content match. Its authority stays
  `REPLAY_ONLY_OFFLINE_OVERLAY / phase30-confirmed-offline-decomposition-only`, not issuer authority.
- Held nominations preserve **32 scope/context slots**, **21 bindings**, **33 replay requests**.
  Every request matches its stored scope/context, category description, offered candidate rows
  and fingerprint; all **49 stored trace fingerprints** independently recompute. Candidate-row
  comparison uses the existing order-insensitive fingerprint contract and the separately frozen
  complete request-manifest digest.
- Ownership context is built solely from pinned resident sealed/packet snapshots. Manifest:
  `3e3a72f4cd9be783e7932024f004b72d8177cae7788398d42ac3413567218d02`.
  Full index: `45f0326c33294ab424fc1be390962abd528a092a24f6e7f78a1ca6f570234e3d`.
- Scientific rules remain owner.local_antecedent.v1, attribution i4-2b3.0, grounding v5,
  guard/support-policy v7, observation-polarity/i2-1, and witness/containment/direction/
  effectiveness v8; support-view-v1, relationship-proof-v1 and observation-basis-v1 remain exact.

The issuer calls the existing pinned diagnostic map and aligned-observation producer with
explicit v8. Existing function code is reused in per-invocation globals namespaces for the
mapper/diagnostic modules. The closed held-nomination adapter validates each request before
returning its preserved binding; no shared scientific module globals are patched. Function code,
defaults and signatures remain unchanged. No exec/eval, fresh model, retrieval or NLI is used.
A file-read denial test verifies scientific execution consumes resident snapshots without
mutable-path rereads. Trusted installed module/process code remains within D0's threat boundary.

After execution it checks immutable scientific inputs, the final 33-request manifest, exact map,
scientific inventories and diagnostic recovery. It forms a receipt from the enrolled event
template with actual reproduced hashes, requires the exact pre-enrolled receipt ID, and runs
pure verification before returning detached map/receipt and immutable bound inputs/authorization.
It does not create or authorize a new event key.

## Scientific equality and receipt truthfulness

Accepted map canonical SHA-256:
`e1c6d1027c96098dce96b7c86ee9259d1c50e379845c1d9bb3adeb62ba00b8cf`.

Recovery canonical SHA-256:
`f8f0278d489d4c0fa7e5794ef2238f20a2c19301f26438d7ea2bcd45934d6cd5`.

The exact map match covers requirement/instance states, bindings, all candidate supports,
attribution, guards, policy evaluations, categories, relationship proofs/witness IDs and aligned
direction/effectiveness observations/summaries. Runtime checks also require 13 requirements,
46 instances, 20 proofs (11 completion-joint), six direction observations, no effectiveness
observations, and 48 identical recovery targets. Nomination bindings/fingerprints match separately.

The dedicated new output is `.local/i4-4d1/accepted-reproduction/`, containing
`sufficiency_map.json`, `producer_output_receipt.json` and `verified_authorization.json`.
The runtime receipt matches the enrolled material byte-for-byte under canonical serialization.
`.local/i4-4d1/qualification.json` records the resolved identities and counts.

Receipt `event_kind=post_hoc_deterministic_reproduction` and
`historical_receipt_existed=false` are preserved. No original Phase-28, I4-3C, I4-4C or historical
map was changed. This proves the approved deterministic output was reproduced from bound inputs;
it does not assert that the original run emitted a receipt or prove a unique wall-clock invocation.

## Pure consumer prerequisite

API:

```python
verify_producer_authorization(
    smap, sealed_bytes, authored_contract, producer_receipt,
    *, input_bundle, trusted_registry,
) -> VerifiedProducerAuthorization
```

Verification checks trusted provenance/schema; profile membership/body/lifecycle; receipt
body/full ID and independent accepted-receipt membership; exact enrollment refs/purpose;
referenced material; actual sealed/authored/overlay/nomination/context snapshots; exact
noncurrent/v8 identity via unchanged `check_authorization_binding`; map, ruleset, shape, code
manifest and recovery bindings. A self-consistent but unenrolled receipt fails before its claims
can authorize substituted data. Inputs are not rewritten.

The function performs no file/network/database/time/random/model/NLI/retrieval I/O and executes
no producer. At consumption it verifies the recorded immutable producer manifest, not current
installed historical source. A future promotion of v8 to current makes the old noncurrent receipt
incompatible; it does not retroactively change this profile.

The recursively immutable verified object contains only resolved/bound registry, profile,
receipt, input-manifest, map, sealed bytes/index, authored, nomination and code-manifest identities,
rulesets and exact sufficiency identity. Derived result:

`verified-producer-authorization-v1:sha256:aa9ccbfa94f100a4c8cc0cbe85f60f27eebb289528e0f280447f0fcd23bb04b2`.

This is evidence that verification succeeded, not an independent new trust root. No Layer C,
ParentClaims, AnswerPlan, renderer or legacy replay route invokes the new verifier/issuer.

## Tamper and lifecycle qualification

All A-R cases pass their required acceptance/rejection outcomes in executable tests:

| Case | Exercised behavior | Result |
|---|---|---|
| A | Exact enrolled profile/receipt/actual inputs | Accept |
| B | Unknown producer, rehashed receipt | Reject |
| C | Known producer, altered profile | Reject |
| D | Substituted map, recomputed receipt; also substituted map with original receipt | Reject |
| E | Substituted sealed bytes/index | Reject |
| F | Substituted independent authored contract | Reject |
| G | Substituted overlay | Reject |
| H | Substituted nomination/model source bytes, bindings or slot | Reject |
| I | Wrong disposition at same v8 | Reject |
| J | Wrong version | Reject |
| K | Current/v8 receipt against noncurrent; future current-v8 installation | Reject |
| L | Exact supported-noncurrent/v8 | Accept |
| M | Ordinary v7 without producer authority | Exact legacy behavior |
| N | Missing receipt at prerequisite seam | Reject; no profile-B consumer activation |
| O | Self-hash-valid unknown profile | Reject |
| P | Downstream-style authorization wrapping invalid producer authority | Reject |
| Q | Stale profile claiming different implementation/source manifest | Reject |
| R | Additive trusted-root update retaining active/retired consumption | Accept; revoked/incompatible reject |

Additional controls reject a copied output with false new event key, entirely new self-consistent
unenrolled receipt, caller registry dictionaries/wildcards, duplicate keys, unknown/missing fields,
nonfinite numbers, full-ID mismatch, traversal, missing material, forged request fingerprints,
fresh nomination attempts, source/runtime drift and edited characterization-baseline bytes.
Retired/revoked issuance fails before source reads. Mutated original paths leave captured input
snapshots unchanged; authoring reads private snapshots only. Output paths cannot overwrite old
artifacts. Raw claimed hashes cannot replace actual bytes.

Narrow static import/call allowlists enforce the pure family boundary, fixed loader ownership,
single closed issuance API, no arbitrary maps/providers, independent receipt membership and no
registry writing/auto-enrollment. Existing consumer modules cannot import/call the new boundary.
Ordinary v4-v8 replays run with new authorization/issuance functions patched to fail if entered.
These checks constrain trusted repository code; they do not claim to sandbox threat E.

## Legacy characterization

All five exact combined hashes pass without producer fields or a new default gate:

| Version | Unchanged combined SHA-256 |
|---|---|
| v4 | 4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a |
| v5 | 109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77 |
| v6 | dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be |
| v7 | 04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72 |
| v8 | 1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0 |

Current sufficiency remains v7, plan remains answer-plan-step2-v4, and v8 remains
supported_noncurrent. --allow-supported-noncurrent does not activate profile B.

## Offline qualification record

- Targeted four-module qualification: **97 passed in 31.75s**.
- Final targeted run including the existing consumer-allowlist control: **98 passed in 40.15s**.
- Dedicated production reproduction: exact seven materials, map, recovery and receipt; passed.
- Optional psutil-dependent offline module in dependency-complete Anaconda environment:
  **7 passed in 10.64s**. Its tests use mocks despite the module's historical live suffix.
- Five known baseline/environment failures independently rerun: **the same five failed in 14.84s**.
- Final full offline experiments suite: **5,270 passed, five known failures, 12 skipped,
  nine xfailed, 276 subtests passed in 286.81s**. Zero unexplained new failures.
- Ruff check and format check: passed for all nine new Python files.

The first full run reported 5,269 passed and six failures: the five known failures below plus
the existing ownership-context consumer allowlist, which had not yet enrolled the new fixed
issuer. The correction adds only `producer_replay.py` to that exact test allowlist; its
unauthorized-consumer negative controls remain. The final full run supersedes the initial
run. This new failure was corrected, not treated as baseline or suppressed.

The five independently reconfirmed failures are:

| Existing test | Unchanged reason |
|---|---|
| ask_070/test_corpus_and_referents.py::test_dev_eval_separation | Missing frozen/dev_inputs_v0.json |
| ask_070/test_schema_validation.py::test_real_frozen_nonsemantic_artifact_schemas | Missing frozen/corpus_presence_v0.json |
| test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored | Offline guard blocks Ollama /api/tags |
| test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts | Known hierarchy_contract.py source-pin drift |
| test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects | Same pin drift; readiness returns 3 rather than 0 |

Commands use the established `.local/i4-4c/run_offline.py` launcher/socket-denial plugin with
offline Hugging Face/Transformers settings. Full scope is `experiments`, excluding only the
separately qualified optional module. Logs/JUnit are in `.local/i4-4d1/`: targeted, full,
baseline and optional. No live model, retrieval, NLI or E2E ran.

## Readiness and stop

Final staged hooks pass whitespace/EOF/conflict/large-file checks, Ruff formatting/lint,
Bandit security scanning and Tach boundaries. The sole remaining hook failure is the unchanged
615-line app/frontend/js/20_synthesis.jsx (blob 03f9d3dfee3763533a78d5da601a99cb81bb37f1).
The initial hook invocation used the wrong Python from PATH; rerunning with the project .venv
resolved Bandit/Tach availability. The report's trailing blank line was fixed. No such failure
was bypassed. The user-authorized --no-verify exception applies only to the unchanged line cap
for this one D1 implementation commit, after all authorization/scientific/regression gates pass.
Git's per-command core.longpaths=true handles the full material-ID filenames on Windows without
changing the registry naming contract or persistent Git configuration.

**VerifiedProducerAuthorization is implemented. The original I4-4D section 4 authentication
prerequisite is satisfied for the one enrolled preserved v8 event. READY to resume I4-4D in a
separately authorized increment.** Consumers must still integrate this verified prerequisite
before Layer C validation; D1 does not claim that integration is already active. New events
still require separate valid issuance and deliberate independent enrollment.

STOP after I4-4D1. No broad I4-4D consumer work, claim-v2, parent-synthesis-v2, plan-v5,
v8 promotion, I4-4E or I2-3 has begun.
