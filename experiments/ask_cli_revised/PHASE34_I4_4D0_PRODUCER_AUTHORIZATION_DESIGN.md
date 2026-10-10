# Phase 34 / I4-4D0 — producer authorization trust-anchor design

Date: 2026-10-10. **Planning only. READY for bounded I4-4D1 implementation; I4-4D remains stopped.**

Canonical branch: experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z.

Entry inspection confirmed only the accepted I4-4D STOP report and lineage append were dirty.
Those documents were committed and pushed, with normal documentation hooks passing, as
**de03fe12bf8b0f55b8d89d59de7b6ab472a80f03**. This audit began from that clean HEAD.
Production still corresponds to **b75c6f2fd48975a702713e34436ce4b7d81dabe0**.
The audit adds this report and a lineage append only; it implements no authorization or consumers.

## Decision and scope

Choose **Option A: a repository-pinned registry**, initially containing exactly one offline
qualified producer profile and one separately enrolled accepted reproduction receipt.
**Digital signatures: NO, not needed now.**

A profile allowlist alone is insufficient: anybody can copy a known producer ID and rehash a
different output. Consequently the registry must independently pin the accepted output-receipt
identity as well as the producer-profile identity. This is an intentionally bounded offline
authority for the preserved v8 reproduction. It is not a general mechanism for authenticating
arbitrary new outputs. Expanding to new inputs/outputs requires explicit enrollment; silently
accepting any output with a known producer name is forbidden.

The profile remains implementation/configuration authority and contains no run-specific map hash.
The output receipt binds the event's exact inputs/output. The registry grants authority to these
two distinct objects. No object authorizes itself by naming its own digest.

## A1–A4. Threat model, meaning and architecture

| Threat | Scope | Protection / limit |
|---|---|---|
| A. Malformed or self-authored caller input | In scope | Closed schemas; independent registry membership; exact bound bytes, canonical content and references |
| B. Unqualified producer/configuration | In scope | Explicit profile allowlist; pinned semantic implementation/resource identity; controlled issuer; accepted receipt enrollment |
| C. Wrong replay code/input/profile | In scope | Exact fingerprint/input manifest, exact status/version, immutable profile/receipt refs; no latest, wildcard, >= or lexical matching |
| D. Runtime-artifact substitution with trusted repository, verifier and process code | In scope | Rehashed map/receipt/input substitutions cannot match the registry's independently pinned accepted receipt and input manifest |
| E. Modified repository, registry, verifier or arbitrary code injection into the trusted process | Out of scope | An in-repository root cannot defend itself against its own replacement |

Trusted assumptions include the installation/repository checkout, registry loader, verifier,
Python execution environment and cryptographic hash implementation. A caller supplies data,
not executable Python, replacement registries, monkeypatches or arbitrary issuer callbacks.
Untrusted filesystem paths must not redirect trusted registry/module loading.

**A2: meaning.** Authorized means: the trusted Callosum repository profile has explicitly
qualified this scientific producer/configuration and enrolled this exact deterministic
reproduction receipt, and the actual supplied artifacts match those bindings.
It is content/provenance authorization relative to that trusted installation, not remote
organizational nonrepudiation, proof of a wall-clock invocation, or proof that a copied receipt
was independently executed again. Copying the exact approved map and receipt is acceptable;
claiming a changed map is not. A deterministic receipt identifies a logical reproduction event,
not a unique execution nonce.

**A3: choice.** Option A, with separate producer profiles and accepted-receipt enrollment.
This extra accepted-receipt check is essential to matrix case D. A profile-only allowlist plus
self-hashed outputs would reproduce the accepted I4-4D gap.

**A4: alternatives.**

| Option | Assessment |
|---|---|
| A. Repo-pinned profiles + accepted reproduction receipts | Recommended. Offline, deterministic, independently owned configuration; smallest scope for the one accepted preserved run |
| B. Externally signed producer receipts | Not selected. Needed if outputs must be accepted from an external issuer without repository enrollment; does not by itself protect a verifier that an attacker can replace |
| C. Existing independent project root | Patterns exist, but none authorizes these maps. Reusing their review/fingerprint discipline is appropriate; inheriting their authority is not |

For B, a real design would need separately generated signing keys, secured custody outside caller
artifacts, a pinned verification key/key ID, domain-separated receipt signatures, rotation overlap,
revocation policy, deterministic-body handling and an explicit local-development issuer policy.
The desktop release key is not permission to sign scientific producer receipts. Introducing
all of this solely for the word authentication adds no benefit to this bounded trusted-repository
case. If E becomes required, the verifier/distribution root must itself be externally protected;
putting a public key in replaceable source code is insufficient.

Rejected shortcuts: fixed producer string, self-hash, receipt existence, caller-provided git SHA,
arbitrary allow flag, or reinterpreting the characterization digest as producer authority.

## Repository trust-pattern audit

| Inspected location | Existing mechanism | Suitability |
|---|---|---|
| hierarchy_contract.py:61, 778, 821, 855 | Explicit code-input hashes; input/wording pins; independent review naming exact pins; drift refusal | Good review/qualification pattern. Old pin scope and known loader-code drift do not authorize the new producer |
| sufficiency_freeze.py:load_verified | Frozen per-child contract hashes, combined hash and review naming that exact contract | Suitable independent authored-input authority; not producer authority |
| hierarchy_contract.py:check_authorization and sufficiency_model_nomination_authorization*.json | Request/experiment authorization and nomination scopes | Scope-specific experiment/model permissions, not proof of v8 emission |
| answer_plan/overlay.py and Phase-30 overlay | Confirmed offline decomposition metadata/hash | Independent overlay input only |
| answer_plan/replay.py:verify_replay_authorization; sufficiency_identity.py:check_authorization_binding | Body consistency and exact status/version equality | Necessary checks; no independent producer trust root |
| witness_i4_3c_replay_baseline.json; attribution/support-policy baselines | Accepted deterministic qualification hashes and inventories | Evidence referenced by the profile; not the registry |
| app/desktop-shell/packaging/package_python_runtime.py | Declared source/resource fingerprints, newline-independent text hashes, input-derived runtime IDs | Useful fingerprinting precedent; runtime-package scope is different |
| app/desktop-shell/src-tauri/src/python_runtime.rs:verify_manifest_signature; .github/workflows/desktop-python-runtime.yml | Minisign verification against compiled public key; workflow signs runtime manifests using release secrets | Actual signed-artifact infrastructure exists, but authorizes desktop runtime distribution, not scientific maps |

Only public source/configuration was inspected; no signing secret was accessed or generated.
The registry proposed here is new configuration and remains unimplemented. Existing pins,
reviews, release keys and replay baselines are not modified or silently repurposed.

## A5–A8. Registry, profiles, fingerprint and output-receipt schemas

### A5. Registry ownership

Proposed fixed root:
**experiments/ask_cli_revised/producer_authorization.registry.json**.

Its companion immutable material directory is proposed as
**experiments/ask_cli_revised/producer_authorization_material/**, addressed by full digest
and schema. No caller path/URL, environment variable, working-directory override or CLI
--trust-this-producer option selects the root. A repository-owned loader resolves these paths
relative to its own installed module. Material references resolve only in that fixed store;
reject path traversal, duplicate JSON keys, unknown fields, nonfinite numbers and unknown schemas.

The exact prospective registry body appears in the annex. It has one active profile and one
accepted receipt. Lifecycle lives in registry entries, not in immutable profile content.
D0's prospective active flags describe the proposed initial D1 installation; they grant no
authority until explicitly implemented/enrolled. Ordinary runtime never writes this registry.

Do not add historical v4-v7 profiles or a generic new-run producer now. No signed remote receipts,
wildcards, fallback profiles or automatic enrollment. A registry update is a deliberate reviewed
configuration change, separately owned from caller artifacts.

Initial D1 enrollment is published only after the deterministic reproduction and its qualification
have passed. Tests may load prospective material through the explicit test seam, but a planned
receipt ID is not an assertion that issuance already happened. The final reviewed registry commit
is the independent enrollment act; neither the issuer nor a calculation utility performs it.

### A6. Qualified producer profile

Schema: **qualified-producer-profile-v1**. Full body and ID are preregistered below.
It binds producer/implementation identity, exact noncurrent/v8 identity, 26-file implementation
manifest, reviewed authoring identity, preserved-nomination class, frozen-binding adapter contract,
issuer contract, output shape, exact rulesets and qualification evidence. It permits no fresh
model/retrieval/NLI calls. CPython 3.12.7 is the initially audited runtime; changing that runtime
requires explicit qualification, not inference from a compatible-looking version string.

The profile contains no actual map-output hash. The accepted event receipt and its registry
enrollment carry that run-specific identity. The authored-input identity is intentionally narrow
to the current preserved q_aib contract; no general per-query authority is being claimed.

### A7. Exact code/resource fingerprint scope

The annex lists the complete 26 source paths and hashes. Start from the semantic mapper/
observation path exercised in the accepted real replay; add the authoring loader, identity,
nomination-fingerprint, recovery and hierarchy qualification dependencies. Pin whole source
files, not function names or a mutable package version. Source text is UTF-8 with CRLF/CR
normalized to LF, and no other normalization, matching an existing packaging precedent.
Hashes do not depend on checkout newline policy.

Source comments/formatting changes inside these files conservatively require a new manifest
and deliberate requalification. Markdown-only documentation changes do not. Neither HEAD nor
a caller's git revision is authority. Recorded repository revisions are audit context only.

The fingerprint covers the explicitly qualified semantic callable path, not every importable
package in the application. This is not a runtime SBOM. Import-only PDF/model packages are
not authorization to execute extraction, model or network behavior. D1 static/runtime guards
must reject widening the executed semantic path or nomination provider. A new semantic helper
must enter a new manifest/profile; mutable dependency discovery is not a verifier feature.
Resources are separately bound through the authored/event manifests, including reviewed
contracts, hierarchy inputs, sealed bytes, packets, nominations and overlay.

The new D1 loader/verifier/issuer wrappers will be part of the trusted repository code boundary;
they are not claimed to have hashes before they exist. They may orchestrate the pinned producer
and enforce this closed contract, but may not add scientific decisions. Any semantic adapter
change beyond the preregistered held-binding contract requires revised profile material and
requalification. D1 must prove exact equivalence with the existing replay oracle. The registry,
its generated IDs and future reports are excluded from the semantic source manifest to avoid
self-reference. Changes to trust enforcement itself still require review and the tamper tests.

### A8. Producer output receipt

Schema: **producer-output-receipt-v1**. Full body and ID are preregistered below.
It binds the authorized profile, logical post-hoc reproduction event, actual map canonical hash,
sealed byte/index hashes, independent authored requirements, overlay, nominations, context,
rulesets, output shape, recovery result and qualification reference.

A body digest is integrity, not authority. Verification additionally requires the exact receipt
ID to be independently enrolled in the trusted registry with the same profile and input manifest.
Recomputing a receipt for a different output cannot make it enrolled.

The output is presently a bare child-keyed sufficiency map, with v8 identities inside its contracts.
The proposed output_shape string describes that existing shape; it does not add a map schema field.

All new content refs use:
schema + ":sha256:" + SHA256(UTF-8 canonical JSON of the full body).
Canonical JSON: sorted keys, compact separators, ensure_ascii=False, allow_nan=False.
Bodies contain schema but no self ID/hash. IDs are stored in envelopes/registry keys.
No timestamps, local absolute paths, random nonce, git HEAD or receipt ID enter a receipt's own
body. Array ordering is semantic except where the construction rule explicitly sorts sets.

## A9–A11. Issuer, verification and post-hoc migration

### A9. Single issuer boundary

Proposed new repository-owned orchestration:
**producer_replay.py::reproduce_accepted_v8(...)**.
Its only issuance point follows successful reproduction, before returning the map/receipt pair.
The internal receipt constructor is not an arbitrary map-to-receipt public API.

Exact owned sequence:

1. Load the fixed trusted registry/profile and its accepted input-manifest target.
2. Snapshot and verify the pinned producer code/runtime and actual input bytes.
3. Load reviewed authoring with sufficiency_freeze.load_verified using the pinned fixed files.
4. Obtain parent relationships from the exact independently reviewed hierarchy pins and check
   their source/review bindings. Verify the pinned overlay separately.
5. Extract the held nomination bindings from the pinned preserved final map and request traces;
   check the full nomination manifest. No fresh model call or inferred substitute binding.
6. Build ownership context from the pinned sealed ledger and resident evidence packets.
7. Execute the existing sufficiency_diagnostic.compute_diagnostic_sufficiency_map with explicit v8,
   using the closed preserved-binding provider, then compute_direction_and_effectiveness.
   Witness/proof selection remains the existing scientific producer's work.
8. Require exact map hash equality with the independently enrolled reproduction target; compute
   the existing recovery target inventory for the bound qualification check, without retrieval.
9. Form the deterministic receipt, require its exact enrolled ID, and return detached map/receipt.

The preserved binding provider uses exactly the existing replay's
(child, requirement, role, request_context) key and retained own filled bindings; empty choices
remain empty and unknown keys fail. It is not a user-supplied callable or arbitrary override.
The current oracle is test_i4_2a_replay.remap, with context from test_i4_2b3_replay.context.
D1 may expose the equivalent narrow repository-owned replay seam; it must not move semantic
decisions into the issuer or re-author the map.

The issuer takes pinned input handles, not a caller-provided completed map to bless.
Layer C and the existing answer_plan replay consumer may not mint this upstream receipt.
A public hash utility can of course calculate the same deterministic bytes; such calculation
is not issuance or independent enrollment. Exact approved copies remain the same logical event.

### A10. One pure verification boundary

Proposed API:

~~~python
verify_producer_authorization(
    smap, sealed_bytes, authored_contract, producer_receipt,
    *,
    input_bundle,
    trusted_registry: TrustedProducerRegistry,
) -> VerifiedProducerAuthorization
~~~

input_bundle carries the actual immutable nomination/context/overlay/source-manifest payloads
and required byte snapshots. Merely supplying their claimed hashes is insufficient.
The pure function performs no I/O or producer execution. The trusted shell/loader supplies the
registry and byte snapshots. Ordinary caller input cannot construct a trusted registry argument;
an explicit injection seam exists only in tests. Python object privacy is not claimed as a
security boundary against arbitrary in-process code execution, which belongs to threat E.

Verification, in order:

1. Require supported schema and fixed trusted registry provenance; reject raw caller dictionaries
   masquerading as trusted configuration.
2. Resolve the receipt's exact profile ref from the registry and fixed material store. Verify its
   full closed body/hash, producer ID, lifecycle/purpose and exact permitted identity.
3. Validate the receipt's closed schema/hash and require exact membership in accepted_receipts.
   Check that registry entry's profile/input refs equal the receipt. A known producer is insufficient.
4. Resolve/validate all manifest bodies and compare the actual byte/canonical input hashes:
   sealed artifact/index, map, reviewed contracts, overlay, preserved nominations and requests,
   ownership packets/index, provenance files and any bound recovery result.
5. Check exact sufficiency identity with unchanged check_authorization_binding, as well as the
   profile's permitted status/version. Check all ruleset, containment/direction and output-shape fields.
6. Require receipt/profile source-manifest equality. At issuance, verify installed producer code
   against that manifest; receipt consumption validates the enrolled historical manifest and receipt,
   without needing to execute or have the old producer loaded.
7. Return a frozen, recursively immutable verified object binding registry/profile/receipt/input/
   map identities. Its stable ref can be a canonical verified-producer-authorization-v1 digest
   over those refs; it is not a new independently trusted root.

Read each runtime artifact into one bounded snapshot, verify it and consume that same snapshot.
No verify-then-reread of mutable paths; no unverified dynamic imports or registry fallback.

The eventual I4-4D entry point accepts this verified object and passes its exact already-bound
inputs through the sole Layer C validation authority. A raw producer string is not authority.
D1 need not change layerc_projection or activate any consumer; the future caller adapter will
bridge its existing internally consistent profile envelope to this independently verified object.

### A11. Existing v8 migration

Accept the proposed post-hoc strategy. A new deterministic reproduction event runs from preserved
bytes and independent reviewed authoring, matches the accepted map, and only then emits its newly
enrolled receipt. It explicitly records historical_receipt_existed=false. An optional execution
log records actual execution time outside the deterministic body; it cannot authorize an output.

The accepted characterization hash remains qualification evidence:

**1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0**.

It is neither the map hash nor a registry. D1's migration qualification must rerun that exact
legacy characterization separately. No v8 map or old artifact gains receipt fields.
The new upstream receipt can be stored beside the reproduced artifact in a separate output
directory; the original Phase-28 directory remains immutable.

This audit already reproduced the accepted map twice: once through the existing characterization
harness and once with reviewed frozen authoring as the actual mapper input. That establishes
feasibility, not issuance. The prospective IDs below are not valid runtime authorization today.

## A12–A15. Independent authoring, overlay and model/context inputs

**A12. Authored contract.** Use the committed sufficiency_contract.aib_hier_v9.frozen.json plus its
review, through load_verified. The review names combined hash
9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586.
Do not derive authoring authority from a caller's mapped requirements.

The canonical authored requirements digest is
8b219f093c31e7e64215381ac4ef4113d96a1e33320be891fbbae567e541d0dc.
The audit independently strips only runtime fields from the reviewed frozen_view and confirms
exact equality with the accepted v8 requirements: zero differences. Runtime fields excluded are
instances, state, reason, direction_summary and effectiveness_summary.

Hierarchy pin/review source hashes and model-facing digest also match. The known current
hierarchy_contract.py code-pin drift is still real; this design does not declare the old live
pin check passing or regenerate it. The new explicitly scoped offline producer profile pins the
accepted current code separately and consumes the unchanged reviewed hierarchy data/parent map.
No live authorization or default hierarchy loader behavior is weakened.

**A13. Overlay.** Bind exact bytes and canonical identity of the committed Phase-30 confirmed
offline decomposition overlay. Its status is REPLAY_ONLY_OFFLINE_OVERLAY and its scope
postdates the original run. It grants decomposition authority only. It is not the producer's
issuer/authorization root. Substituting another overlay fails the enrolled event binding.

**A14. Nomination/input identity.** Bind both initial/final preserved sufficiency maps,
18_sufficiency_model_assist.json, qwen_calls.jsonl, original request contract and run manifest.
The final map is a pinned source of held nominations, not independent authoring authority.
The initial map and original traces are provenance evidence; they are not rerun.

Exact held-binding extraction matches the accepted oracle: iterate preserved child requirements,
instances and model_nomination_only roles; key by child/requirement/role/request_context;
retain filled non-parent_context bindings with identical duplicates removed; keep empty slots.
Serialize sorted scope/context records using canonical JSON ordering, preserving binding order
within each slot. The resulting manifest has **32 scope/context slots and 21 bindings**.

During the existing v8 replay, record the exact model nomination request scopes, contexts,
category_descriptions, candidate rows and existing request_fingerprint values. Sort full request
records by canonical bytes, retaining repeated calls. There are **33 requests**.
All 33 match a preserved trace by scope/context/fingerprint. Independently recomputing the
49 stored trace fingerprints against the reviewed contract's category_description and stored
candidates_offered matches all 49. No original model call, prompt or answer is re-created.

The existing request_fingerprint deliberately uses its own JSON encoding (sorted keys,
ensure_ascii=False with default separators); do not replace that algorithm with the new compact
manifest encoding. The outer new manifest records those existing fingerprints verbatim.

**A15. Context/rulesets.** Bound packet bytes produce ownership-context-v1; existing context
manifest digest and full canonical index digest are both recorded. No library lookup is needed.
Rules bind owner.local_antecedent.v1, i4-2b3.0 attribution, v5 local grounding, v7 policy/guards,
observation-polarity/i2-1 categories, and v8 proofs/alignment/containment/direction/effectiveness.
Where no finer standalone version exists, the exact source fingerprint supplies implementation
identity; this design does not invent a new scientific version. The full exact rules object is
included in both prospective profile and receipt.

Recovery is a bound diagnostic result (48 targets in accepted qualification), not permission
to run recovery retrieval. A library/database fingerprint is not added as hidden authority:
this replay consumes resident sealed and packet bytes, not a live library.

## A16–A20. Identity, downstream authority, lifecycle, tamper controls and signatures

**A16. Identity is orthogonal.** supported_noncurrent/v8 equality must still pass the existing
identity reader/checker. Producer authorization cannot relabel a map or grant an identity opt-in.
No current/historical synonym, fallback or >= comparison.

**A17. No circular authority.** The dependency order is:
trusted registry -> qualified profile and enrolled receipt -> verified input authority ->
Layer C projection -> claims/plan/render -> separate downstream output authorization.
The downstream manifest references verified upstream authority; it cannot repair it.
The upstream body contains no new projection/claim/plan/render hash. The legacy combined
characterization digest is a qualification reference only.

**A18. Lifecycle.** Immutable profile and receipt bodies never change in place.
Registry entries carry issue/consume permissions and a closed lifecycle:

| Lifecycle | Issuance | Profile-B consumption | Archival inspection |
|---|---|---|---|
| active | Yes, only enrolled reproduction | Yes | Yes |
| retired | No | Yes for already enrolled receipts, while identity still compatible | Yes |
| revoked | No | No | Inspectable as revoked; no verified authorization token |

Adding a profile requires explicit reviewed source/resource qualification and tamper/replay gates,
then registry enrollment. The issuer cannot enroll itself. New input/output events need their own
accepted receipt entry even when the producer profile is unchanged. No auto-append at runtime.
Unknown lifecycle or contradictory permission flags fail closed.

A semantic source, runtime, ruleset, contract/provenance-class or adapter-contract change requires
new qualification/profile material. A new event's run-specific input hashes require a new receipt
and explicit enrollment. Documentation-only edits do not alter the profile.

A later registry adding another profile does not invalidate unchanged, non-revoked enrolled
receipts. Consumption validates recorded producer fingerprints rather than demanding old producer
files be installed. A revoked profile never becomes acceptable by presenting an older caller-chosen
registry snapshot; ordinary consumers always use the installation's fixed current registry.

Promoting v8 semantics from supported_noncurrent to current changes exact identity disposition:
the old noncurrent receipt must not be relabeled. A new explicitly qualified identity profile/
receipt and registry decision are required; the scientific implementation may reuse its existing
qualification evidence, with fresh identity/compatibility tests. The unchanged I4-3C0 check
rejects stale disposition. Old receipts remain inspectable as historical records but cannot
yield current consumption authorization under a mismatched lifecycle identity.

Promoting Layer C/plan-v5 alone does **not** change upstream producer authority when scientific
version/disposition/implementation/inputs remain the same. No downstream schema enters the
producer fingerprint. A new downstream output manifest may reference the same upstream receipt.

**A19. Frozen tamper/substitution matrix.** These are design expectations for D1 tests,
not results from an implemented verifier.

| Case | Proposed verification result | Exact reason |
|---|---|---|
| A exact active profile, enrolled receipt, exact inputs | PASS | Registry membership plus all exact bindings |
| B unknown producer_id, recomputed receipt digest | FAIL | Unknown producer/profile or receipt not enrolled |
| C known producer_id, altered profile body | FAIL | New profile digest absent from registry; ID/body mismatch also fails |
| D authorized profile, substituted map and rehashed receipt | FAIL | Changed receipt ID not enrolled; keeping old receipt fails map binding. A distinct output passes only after separate valid issuance and explicit independent enrollment |
| E substituted sealed bytes | FAIL | Enrolled byte/index/input mismatch |
| F substituted authored contract | FAIL | Reviewed authored identity and event pin mismatch |
| G substituted bound overlay | FAIL | Exact overlay/input mismatch |
| H substituted nominations/model inputs | FAIL | Raw provenance, held bindings or request-manifest mismatch |
| I wrong status, same v8 version | FAIL | Exact profile and map identity check |
| J wrong version | FAIL | Exact profile and map identity check |
| K current/v8 receipt against noncurrent map | FAIL | Exact identity; rehashing cannot fix |
| L accepted noncurrent/v8 receipt against exact accepted map and all bound inputs | PASS | Same conditions as A |
| M ordinary v7 without producer receipt | LEGACY UNCHANGED | New verifier not entered by default; explicit new trust profile remains incompatible |
| N profile B without producer receipt | FAIL | Required upstream authorization absent |
| O valid self-hash, unknown profile | FAIL | No independent registry authority |
| P valid downstream output auth, invalid upstream receipt | FAIL | Downstream cannot authorize upstream |
| Q stale profile with new requalified implementation claimed | FAIL | Receipt/profile/code-manifest disagreement or unenrolled new profile/event; an exact retained old event is governed by R |
| R exact old enrolled receipt after additive registry update | PASS if consume-permitted and exact identity still compatible | Retirement can preserve consumption; revocation or changed semantics disposition fails active consumption, archival inspection remains possible |

Additional required negatives: known producer ID with self-consistent entirely new event;
caller registry replacement; unknown/wildcard profile; duplicate keys/fields; mismatched full ID;
TOCTOU byte replacement; source-manifest drift at issuance; forged nomination slot/request;
fresh model attempt; Layer C trying to issue; output copied with a false new event key;
retired issue attempt; revoked receipt; edited baseline falsely claimed as accepted.

**A20. Signatures now: NO.** The independent authority is fixed trusted repository configuration,
including exact receipt enrollment. It is adequate for A–D as scoped above. Without accepted-receipt
enrollment, Option A would be inadequate for D. E, remote organizational provenance and arbitrary
new unpinned output acceptance are not claimed.

## A21–A22. Exact prospective real material

Every JSON body below is **prospective design material**, computed read-only. No runtime registry,
profile or producer-output artifact is installed. No new receipt has been issued.

| Material | Exact content ID |
|---|---|
| authored_inputs | reviewed-authored-inputs-v1:sha256:2187272f3314817ca687fd1add912c4b178b68063c864d16024cc8db14cd8a83 |
| code_manifest | producer-code-input-manifest-v1:sha256:3ea98ca41a74f6fdb6fc4e4391032ecb7c2b6b361eead954d560a02081670625 |
| event_inputs | producer-event-input-manifest-v1:sha256:5ce389c0bd2baec24044131ddd464b309308a592c33a34032d8acf3f57d3ea3e |
| nomination_inputs | preserved-nomination-input-manifest-v1:sha256:4aac7557e6421be49255ffdeefd26508dd7b92856f88afdd291c4e6dc0a8710c |
| profile | qualified-producer-profile-v1:sha256:0c739b235dd983b77f3f9adfca22bebea90255f0f51f57f45cd7e699ef0bd2cd |
| receipt | producer-output-receipt-v1:sha256:a040ad7757ee792e9c0a7f0414bead5ce22ed5eb5d19e1bdc37931b4f0d4071d |
| registry | producer-authorization-registry-v1:sha256:3ca420b42e64046470738773b2affad9509ffbab4f0b0df166963fcc0308d0ef |

Map canonical hash:
**e1c6d1027c96098dce96b7c86ee9259d1c50e379845c1d9bb3adeb62ba00b8cf**.

The same map serialized using the legacy sorted, indent-2, UTF-8, CRLF, terminal-newline convention
has byte hash **ec288f4a2a0435445180d593b1759d9d3040c6b9822156c09536c8a89e3773c9**.
Receipt authority uses the canonical map hash and exact output shape; it does not confuse this
with the old preserved final-map hash or combined characterization hash.

### Exact qualified profile body

```json
{
  "authored_inputs_ref": "reviewed-authored-inputs-v1:sha256:2187272f3314817ca687fd1add912c4b178b68063c864d16024cc8db14cd8a83",
  "fresh_model_retrieval_nli_permitted": false,
  "implementation_id": "diagnostic-map-plus-aligned-observations/v8",
  "issuance_mode": "registry-enrolled-reproduction-only",
  "issuer_contract": "reproduce-pinned-v8-then-issue-v1",
  "nomination_adapter_contract": "scope-requirement-role-request-context-held-bindings-v1",
  "permitted_identities": [
    {
      "status": "supported_noncurrent",
      "version": "sufficiency-semantics-v8"
    }
  ],
  "permitted_output_shape": "bare-child-keyed-sufficiency-map-with-v8-identity",
  "producer_code_manifest_ref": "producer-code-input-manifest-v1:sha256:3ea98ca41a74f6fdb6fc4e4391032ecb7c2b6b361eead954d560a02081670625",
  "producer_id": "callosum.qaib.preserved-v8-reproduction",
  "qualification_evidence": {
    "i4_2b3_context_baseline_file_sha256": "b9e5e4d1b5cd289a5ce9243721b37ae9c0eebdbcfdcc6b929d14d7006d7c2b9f",
    "i4_3c_baseline_file_sha256": "f1d178cf0cb234b3e8e80918c5cb80b63dbaf54c2599a5b665b47dd5a3eed6f1",
    "i4_3c_combined_characterization_sha256": "1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0"
  },
  "required_input_provenance": "phase28-attempt2-held-final-bindings-no-fresh-model",
  "rulesets": {
    "attribution_classifier": "i4-1-assertion-authority",
    "attribution_ruleset": "i4-2b3.0",
    "attribution_schema": "ownership-attribution-v1",
    "category_classifier": "observation-polarity/i2-1",
    "containment_semantics": "sufficiency-semantics-v8",
    "direction_semantics": "sufficiency-semantics-v8",
    "effectiveness_semantics": "sufficiency-semantics-v8",
    "grounding_semantics": "sufficiency-semantics-v5",
    "guard_semantics": "sufficiency-semantics-v7",
    "observation_basis_schema": "observation-basis-v1",
    "ownership_context_schema": "ownership-context-v1",
    "ownership_rule": "owner.local_antecedent.v1",
    "proof_schema": "relationship-proof-v1",
    "support_policy_evaluation_schema": "support-policy-evaluation-v1",
    "support_policy_semantics": "sufficiency-semantics-v7",
    "support_view_schema": "support-view-v1",
    "witness_semantics": "sufficiency-semantics-v8"
  },
  "runtime_contract": {
    "implementation": "CPython",
    "semantic_dependencies": "stdlib-and-pinned-local-callables-only",
    "version": "3.12.7"
  },
  "schema": "qualified-producer-profile-v1"
}
```

### Exact output receipt body

```json
{
  "authored_inputs_ref": "reviewed-authored-inputs-v1:sha256:2187272f3314817ca687fd1add912c4b178b68063c864d16024cc8db14cd8a83",
  "authored_requirements_sha256": "8b219f093c31e7e64215381ac4ef4113d96a1e33320be891fbbae567e541d0dc",
  "event_key": "phase28-attempt2-to-accepted-v8/reproduction-v1",
  "event_kind": "post_hoc_deterministic_reproduction",
  "historical_receipt_existed": false,
  "input_manifest_ref": "producer-event-input-manifest-v1:sha256:5ce389c0bd2baec24044131ddd464b309308a592c33a34032d8acf3f57d3ea3e",
  "map_canonical_sha256": "e1c6d1027c96098dce96b7c86ee9259d1c50e379845c1d9bb3adeb62ba00b8cf",
  "nomination_inputs_ref": "preserved-nomination-input-manifest-v1:sha256:4aac7557e6421be49255ffdeefd26508dd7b92856f88afdd291c4e6dc0a8710c",
  "output_shape": "bare-child-keyed-sufficiency-map-with-v8-identity",
  "overlay_canonical_sha256": "3cca99b5ac7078f4ae7633f4e4b53360f0e5cd1ff6e0972e9cce7f71d0979c96",
  "ownership_context_manifest_sha256": "3e3a72f4cd9be783e7932024f004b72d8177cae7788398d42ac3413567218d02",
  "producer_code_manifest_ref": "producer-code-input-manifest-v1:sha256:3ea98ca41a74f6fdb6fc4e4391032ecb7c2b6b361eead954d560a02081670625",
  "producer_id": "callosum.qaib.preserved-v8-reproduction",
  "profile_ref": "qualified-producer-profile-v1:sha256:0c739b235dd983b77f3f9adfca22bebea90255f0f51f57f45cd7e699ef0bd2cd",
  "qualification_combined_sha256": "1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0",
  "recovery_targets_sha256": "f8f0278d489d4c0fa7e5794ef2238f20a2c19301f26438d7ea2bcd45934d6cd5",
  "rulesets": {
    "attribution_classifier": "i4-1-assertion-authority",
    "attribution_ruleset": "i4-2b3.0",
    "attribution_schema": "ownership-attribution-v1",
    "category_classifier": "observation-polarity/i2-1",
    "containment_semantics": "sufficiency-semantics-v8",
    "direction_semantics": "sufficiency-semantics-v8",
    "effectiveness_semantics": "sufficiency-semantics-v8",
    "grounding_semantics": "sufficiency-semantics-v5",
    "guard_semantics": "sufficiency-semantics-v7",
    "observation_basis_schema": "observation-basis-v1",
    "ownership_context_schema": "ownership-context-v1",
    "ownership_rule": "owner.local_antecedent.v1",
    "proof_schema": "relationship-proof-v1",
    "support_policy_evaluation_schema": "support-policy-evaluation-v1",
    "support_policy_semantics": "sufficiency-semantics-v7",
    "support_view_schema": "support-view-v1",
    "witness_semantics": "sufficiency-semantics-v8"
  },
  "schema": "producer-output-receipt-v1",
  "sealed_artifact_bytes_sha256": "a70409e8f5a0937f414c73c4796b293c6c1a9ef3b31c7fc83bbfa61794c6bd5d",
  "sealed_proposition_index_sha256": "c33b1aab85ff01a38522827a41bc62cab5e378444291b89ca425c683a783d6f3",
  "sufficiency_identity": {
    "status": "supported_noncurrent",
    "version": "sufficiency-semantics-v8"
  }
}
```

### Exact independently enrolled registry body

```json
{
  "accepted_receipts": {
    "producer-output-receipt-v1:sha256:a040ad7757ee792e9c0a7f0414bead5ce22ed5eb5d19e1bdc37931b4f0d4071d": {
      "input_manifest_ref": "producer-event-input-manifest-v1:sha256:5ce389c0bd2baec24044131ddd464b309308a592c33a34032d8acf3f57d3ea3e",
      "profile_ref": "qualified-producer-profile-v1:sha256:0c739b235dd983b77f3f9adfca22bebea90255f0f51f57f45cd7e699ef0bd2cd",
      "purpose": "profile-b-offline-prerequisite"
    }
  },
  "profiles": {
    "qualified-producer-profile-v1:sha256:0c739b235dd983b77f3f9adfca22bebea90255f0f51f57f45cd7e699ef0bd2cd": {
      "consume": true,
      "issue": true,
      "lifecycle": "active",
      "producer_id": "callosum.qaib.preserved-v8-reproduction"
    }
  },
  "schema": "producer-authorization-registry-v1"
}
```

### Exact code manifest body

```json
{
  "encoding": "utf8-universal-newlines-lf-no-other-normalization",
  "files": {
    "app/backend/pdf_processing/extraction.py": "f7fc735d988d9acdcaa10c71e5e8a41bf2c9049c0ab58317dd9524fa6f82de5c",
    "experiments/ask_cli_revised/achieved_outcome_span.py": "90f59600e3e3751ccc4cbf5e8932c71e94f6a46ac3411cd307306de772289609",
    "experiments/ask_cli_revised/assertion_authority.py": "0253914cdb5e4fdebf7ea81d62e6541db33a0506a983a1ddec2fa400c240ccb0",
    "experiments/ask_cli_revised/category_polarity.py": "2974b0f8a0d8c892f5c1743cd46cae10d814ffb7c3f8662e2fb20c1618bbdccd",
    "experiments/ask_cli_revised/compatible_witness.py": "15f125396269d34057bfb362f0bd13b938b8f547af155b4103f72b5a541bbb9e",
    "experiments/ask_cli_revised/contract_directed/attribution.py": "b349b6bb6c791ee3afbfd8c621eac616b14b3df3d9fa92678e5675ada382facf",
    "experiments/ask_cli_revised/contract_directed/links.py": "691850f0bd0791f31dc07c32ab08161850d9009f6318a92bb7bbd2d285f62d38",
    "experiments/ask_cli_revised/contract_directed/sections.py": "8df1877150a5c9224261555bb8be5c083f8db282d6a5e2bce65ec70a66210b97",
    "experiments/ask_cli_revised/contract_directed/units.py": "3d6507eb4228085bd4b1ab9f72a66c2cfa57a81e934398ea930a550bc3f52f8c",
    "experiments/ask_cli_revised/decompose/execution.py": "5559aa4ba34fadfc944aeda66cebbb77bb31d137f24526bad4d99aad20c03d6b",
    "experiments/ask_cli_revised/decompose/tree.py": "d15f075c86bfa16aab05daf2cc6ab72e69d7cce8b7d672ead3e6fe866920804c",
    "experiments/ask_cli_revised/direction_target.py": "32faf360138f08165074a19bb29376129dbd540a13fe845d041e2928dac09180",
    "experiments/ask_cli_revised/hierarchy_contract.py": "85a8f9e34f7cd50a12ccae56b678d530c30e6aa154e92069b74c7bb24016192e",
    "experiments/ask_cli_revised/overview_evidence.py": "6201b607ea6342212b814e9d50da936b34f0aa1cbcf239168f22ccb23fe59d61",
    "experiments/ask_cli_revised/ownership_context.py": "bc201eb91369df75e5b3cd6c5b2303785b204fd4d9f61b72242ce28764d29382",
    "experiments/ask_cli_revised/relation_witness.py": "704f491f16f417db74f78213ebfb6f3c1224ed63b15888971145834553c3f5fd",
    "experiments/ask_cli_revised/sufficiency_authoring.py": "f42ba69f47a91d360cef117ae6714348839af3770abd418f1164a2103b78bfb1",
    "experiments/ask_cli_revised/sufficiency_diagnostic.py": "85af33acb597002bf30563f0c8aa39977e64159bacb88d2d70fb3216b06fa0dd",
    "experiments/ask_cli_revised/sufficiency_engine.py": "69f8d1970aa5bc56647f81035d77d26eb31ae7f18b4a374c4c20a4accc4b6245",
    "experiments/ask_cli_revised/sufficiency_freeze.py": "0608afb9458c6551770de5cc5054f3a9dfa8411090be180d803088b600053841",
    "experiments/ask_cli_revised/sufficiency_identity.py": "8e6c855d538dd4b84eebe8a2e5fca9568f6999e0540591fbf90214499dd6d0cf",
    "experiments/ask_cli_revised/sufficiency_mapping.py": "9a1d243d71754ec19ce69b0dde1c144e97ce18f4488b42c67f58386622eaf7c8",
    "experiments/ask_cli_revised/sufficiency_model_scope.py": "bcd122dc35acc4faf959ed49ddf6856d212b1b326b9df9245350984e89d4f906",
    "experiments/ask_cli_revised/sufficiency_recovery_targets.py": "c0a0b0d45018f8688e2b0f250d70ab20415a51a97a20749517046eecd2e477c9",
    "experiments/ask_cli_revised/support_policy.py": "cbd0ccc9d80e53bb0ad02cd3bf2292b46f53a4988e67c99da089eb89b3b7d38f",
    "experiments/ask_cli_revised/target_relevance.py": "3e2fd0f8f836a5f4594d2ac6aefaa994bd6cf28acdfc53418d752367941c1828"
  },
  "schema": "producer-code-input-manifest-v1"
}
```

### Exact reviewed authored-input body

```json
{
  "combined_hash": "9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586",
  "contract_version": "sufficiency-contract-v1",
  "frozen_file_sha256": "472cd2ab23a81d68b698038e0dcc0d98c7aafc6efadef933a2f932e9580f2da6",
  "hierarchy_frozen_sha256": "3e86cb8f0d7816bbc9aeac7d717e9ea4a709981a1e98406c577b8623aab1d0f2",
  "hierarchy_review_sha256": "2446ce15b9727d72fba9d7bc5c4f066a3edb4c5f8847894e620f11b68b791dd1",
  "hierarchy_source_hashes": {
    "hierarchy-input/approvals": "04552bd3ba45dbfa7923dcde3bbdf8522ae247b88f074e345540ddca2a682844",
    "hierarchy-input/assembled": "bd1a4fa1776bf3844130d09b6b9f7a7023705000a5fb0daf96524fcabc1c6dcc",
    "hierarchy-input/closure": "ce97bd04b369b9df96a2e82ad4242f5fce86e7a4943869319ca3e3307b2ce8bb",
    "hierarchy-input/decisions": "0a78accd144002477a9ec0ab35127073a22da563fa41a5a2142a2ae0282df52f"
  },
  "parent_map_sha256": "acf84dd0c91a996f3ed2ef30e1834a52f1a8eeabe299ec20998a05e210b69c52",
  "question_key": "aib_hier_v9",
  "requirements_sha256": "8b219f093c31e7e64215381ac4ef4113d96a1e33320be891fbbae567e541d0dc",
  "review_file_sha256": "e9b3fe781ba8819c4ae24d7590f67901a499daf842085a6f5fa70db5473ed8b9",
  "schema": "reviewed-authored-inputs-v1"
}
```

### Exact nomination-input body

```json
{
  "binding_count": 21,
  "final_map_bytes_sha256": "28478500e485137cd6930b8010d274bb1da3afd48e7f4a6208dd183610d9ca0b",
  "fresh_calls_permitted": false,
  "held_bindings_sha256": "94d68272003a6203f27cf05882ed5799cce17c7c7d8f979f611cc6efbe51a977",
  "initial_map_bytes_sha256": "46a213044bc6211702fa89710268e1bfb6c4fc348259727a46cb238ef5bbc14e",
  "model_assist_bytes_sha256": "e9802f0878bba672b487ee64b4249bb2c6611c40690924185fefcef2ab17c19e",
  "provenance_class": "phase28-attempt2-held-final-bindings-no-fresh-model",
  "qwen_calls_bytes_sha256": "9842b3f074a23b12bb91c4aefc6479676eb590c28a06eef35f1ef2fbd04cafe5",
  "replay_request_count": 33,
  "replay_request_manifest_sha256": "9ed740385b0e9f60772248ba6605529c8736e97974924842bdc510bc54ec9d01",
  "schema": "preserved-nomination-input-manifest-v1",
  "scope_context_count": 32
}
```

### Exact event-input body

```json
{
  "authored_inputs_ref": "reviewed-authored-inputs-v1:sha256:2187272f3314817ca687fd1add912c4b178b68063c864d16024cc8db14cd8a83",
  "files": {
    "experiments/ask_cli_revised/answer_plan/overlays/phase30_replay_decomposition_overlay.json": "20540c880b28950d0294358aad56b48067dfd10e4e7fe94d07e7d227cbbe59e2",
    "experiments/ask_cli_revised/attribution_i4_2b3_replay_baseline.json": "b9e5e4d1b5cd289a5ce9243721b37ae9c0eebdbcfdcc6b929d14d7006d7c2b9f",
    "experiments/ask_cli_revised/hierarchy_contract.frozen.json": "3e86cb8f0d7816bbc9aeac7d717e9ea4a709981a1e98406c577b8623aab1d0f2",
    "experiments/ask_cli_revised/hierarchy_contract.review.json": "2446ce15b9727d72fba9d7bc5c4f066a3edb4c5f8847894e620f11b68b791dd1",
    "experiments/ask_cli_revised/sufficiency_contract.aib_hier_v9.frozen.json": "472cd2ab23a81d68b698038e0dcc0d98c7aafc6efadef933a2f932e9580f2da6",
    "experiments/ask_cli_revised/sufficiency_contract.aib_hier_v9.review.json": "e9b3fe781ba8819c4ae24d7590f67901a499daf842085a6f5fa70db5473ed8b9",
    "experiments/ask_cli_revised/witness_i4_3c_replay_baseline.json": "f1d178cf0cb234b3e8e80918c5cb80b63dbaf54c2599a5b665b47dd5a3eed6f1",
    "hierarchy-input/approvals": "04552bd3ba45dbfa7923dcde3bbdf8522ae247b88f074e345540ddca2a682844",
    "hierarchy-input/assembled": "bd1a4fa1776bf3844130d09b6b9f7a7023705000a5fb0daf96524fcabc1c6dcc",
    "hierarchy-input/closure": "ce97bd04b369b9df96a2e82ad4242f5fce86e7a4943869319ca3e3307b2ce8bb",
    "hierarchy-input/decisions": "0a78accd144002477a9ec0ab35127073a22da563fa41a5a2142a2ae0282df52f",
    "preserved-run/01_request_contract.json": "65b5873f4d8020bf18aeabdc8a64e080e6a8eefaabe1dee71110f0c833536fe8",
    "preserved-run/08_evidence_packets.jsonl": "1949dc56e4abcbb58f7ebf512387c3c6041bdf0a2176facd64aaf44bea1e83f6",
    "preserved-run/11_verified_ledger.json": "a70409e8f5a0937f414c73c4796b293c6c1a9ef3b31c7fc83bbfa61794c6bd5d",
    "preserved-run/15_run_manifest.json": "4578a94793bd242ee34c29d3c14890f9906fb07a8d718da73a17f810eed5d20c",
    "preserved-run/17_sufficiency_map.initial.json": "46a213044bc6211702fa89710268e1bfb6c4fc348259727a46cb238ef5bbc14e",
    "preserved-run/17_sufficiency_map.json": "28478500e485137cd6930b8010d274bb1da3afd48e7f4a6208dd183610d9ca0b",
    "preserved-run/18_sufficiency_model_assist.json": "e9802f0878bba672b487ee64b4249bb2c6611c40690924185fefcef2ab17c19e",
    "preserved-run/qwen_calls.jsonl": "9842b3f074a23b12bb91c4aefc6479676eb590c28a06eef35f1ef2fbd04cafe5"
  },
  "nomination_inputs_ref": "preserved-nomination-input-manifest-v1:sha256:4aac7557e6421be49255ffdeefd26508dd7b92856f88afdd291c4e6dc0a8710c",
  "overlay_authority_kind": "phase30-confirmed-offline-decomposition-only",
  "overlay_canonical_sha256": "3cca99b5ac7078f4ae7633f4e4b53360f0e5cd1ff6e0972e9cce7f71d0979c96",
  "ownership_context_full_sha256": "45f0326c33294ab424fc1be390962abd528a092a24f6e7f78a1ca6f570234e3d",
  "ownership_context_manifest_sha256": "3e3a72f4cd9be783e7932024f004b72d8177cae7788398d42ac3413567218d02",
  "schema": "producer-event-input-manifest-v1",
  "sealed_proposition_index_sha256": "c33b1aab85ff01a38522827a41bc62cab5e378444291b89ca425c683a783d6f3"
}
```

Source aliases are logical locators, not caller-authorized paths. preserved-run means
.local/e2e-runs/phase28-live-parent-synthesis-attempt2-20261004T014500Z/run.
hierarchy-input aliases resolve to hierarchy_contract.DEFAULT_PATHS:
assembled/approvals in .local/decompose-runs/aib-dev/closure_v8 and decisions/closure in its
clarifications directory. Exact filenames are ASSEMBLED_HIERARCHY.json, CLOSURE_APPROVALS.json,
q_aib.v6.researcher_decisions.json and q_aib.v8.closure_decisions.json respectively.
Repository-relative paths resolve from the trusted root.

Full held-binding and sorted request material is reproducible from those pinned inputs using
the A14 extraction rule. The hashes above are not substitutes for doing that verification.
No authorization depends on the ignored audit directory or the future report's byte hash.

## A23–A26. Compatibility, guards, implementation split and readiness

**A23. Compatibility is exact.**

| Path | Required behavior |
|---|---|
| v4-v7 legacy/current | Existing identity and replay behavior; no new receipt requirement by default |
| explicit noncurrent v8 legacy characterization | Remains legacy Layer C/plan-v4; original characterization baseline unchanged |
| v8-layerc-v2-plan-v5 | Requires independently verified producer authority plus exact explicit profile opt-in |
| Unknown semantics/profile/disposition | Fail closed |

The --allow-supported-noncurrent flag alone must never activate profile B.
New trust schemas do not bump sufficiency semantics or PLAN_VERSION.

**A24. Static/purity guard plan.**

- Only the fixed trusted loader reads registry/material files; no ordinary caller override.
- One repository-owned issuer; no receipt issuance imports/calls from Layer C, parent synthesis,
  AnswerPlan, renderers or legacy replay consumers.
- Pure verification performs no file/network/database/time/random/model/NLI/retrieval calls,
  no producer execution and no mutation of inputs.
- Issuer uses the closed preserved-binding path, pinned scientific entry points and explicit v8;
  no fresh nomination provider, arbitrary function callback or caller-supplied completed map.
- Profile/receipt/event manifest schemas and content IDs are exact; accepted receipt membership
  is mandatory independently of profile membership.
- Code/input snapshots are verified before use; no mutable-path reread or dynamic trust fallback.
- Runtime spies prohibit fresh model and network paths; exact map hash and input deep equality
  prove no scientific changes. Candidate/proof/observation/recovery outputs retain their identities.
- Source-scope guards detect new semantic dependencies; Layer C files are not new producer authority.
- Legacy v4-v8 qualification bypasses the new gate unless explicitly opting into the trust profile.
  Default v7/plan-v4 and original v8 characterization tests remain executable and exact.

**A25. Next increment: I4-4D1 only.**

1. Implement fixed registry/material loading, closed schemas and pure producer verification.
2. Implement the narrow reproduction issuer around the already-qualified scientific path and
   held-binding contract; verify source/runtime/input snapshots and exact independent authoring.
3. Materialize the prospectively enrolled profile/receipt/material only under that increment's
   explicit authorization. Reproduce the accepted map and emit its truthful post-hoc receipt
   into a separate output location after equality gates.
4. Implement all A–R and additional trust-substitution tests, issuer/static/purity controls,
   independent authoring/nomination parity and targeted replay qualification.
5. Report exact implemented refs versus this preregistration. Any unexplained material/ID drift
   must be resolved explicitly, never silently updated to whatever passes.
6. No Layer C changes or consumer activation. Then separately resume I4-4D using the verified
   authorization object. I4-4E and I2-3 remain outside both scopes.

**A26: READY for this bounded I4-4D1 design.** This does not mean an authorization implementation
exists or that I4-4D's gate has passed. The single-event enrollment restriction is load-bearing:
a proposal to accept arbitrary new outputs would require a further authority design.

## Verification evidence and stop

Completed targeted offline checks:

- **117 passed in 24.54 seconds:** 116 existing I4-3C0 identity/authorization tests plus one
  read-only inventory/replay calculation. The accepted combined v8 hash matches exactly.
- **Two planning probes passed in 2.65 seconds:** canonical prospective material/hash round trips,
  all 49 stored nomination fingerprints, 33 matching replay requests, and an independent
  frozen-authoring reproduction of the exact map/recovery digest with input immutability.
- The independent reproduction checked reviewed hierarchy source inputs, review record,
  model-facing hash and parent relationships. It did not claim the stale live code-pin check passes.
- Profile/receipt/registry and all subordinate material IDs were computed from full bodies,
  not invented or supplied by a model. D1's verification matrix remains preregistered expectations.

Ignored calculation evidence: .local/i4-4d0/inventory.json, nomination-material.json,
request-material.json, prospective-material.json, targeted.log, material-final.log and the
three audit-only test scripts. Requests are sorted by canonical full record for the final
manifest; the inventory's original execution-order request digest is diagnostic only.
The final preregistered request digest is the one in nomination_inputs above.

The existing .local/i4-4c/run_offline.py launcher uses the socket-denying I4-2b3 plugin and offline
model-library settings. No full suite was required or run. No external search, live endpoints,
retrieval, model, NLI or live E2E occurred. No production code, existing baseline or trust artifact
was edited. The only new tracked changes are this report and CONTRIBUTION-LINEAGE.md.

**STOP after I4-4D0.** No producer authorization implementation, I4-4D resumption, claim-v2/
plan-v5 activation, v8 promotion, PLAN_VERSION bump, map-semantic change or I2-3.
