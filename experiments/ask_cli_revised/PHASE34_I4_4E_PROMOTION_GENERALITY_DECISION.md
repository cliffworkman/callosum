# Phase 34 / I4-4E — promotion and generality decision

Date: 2026-10-11. **Outcome: OPTION B — ONE CONCRETE PRE-PROMOTION FIX.**
**STOP. Defaults were not promoted. NOT READY for bounded I2-3.**

Starting HEAD: `dff6d3dc1544a8178babe75002860df3eae05987`.
Verified clean canonical worktree on
`experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z` before the audit.
Final HEAD is the documentation-only commit containing this report and its lineage append;
its parent is the starting HEAD. Resolve the full final ID with
`git log -1 --format=%H -- experiments/ask_cli_revised/PHASE34_I4_4E_PROMOTION_GENERALITY_DECISION.md`.
The commit/push result supplies the literal final ID without a self-referential hash.

## Decision and single shipping blocker

**There is no accepted general fresh-run entry boundary from the current run's authored
contract and scientific output to the v2 Layer C consumers. The only public integrated
entry is the preserved-event qualification entry.**

This is a current shipping failure: arbitrary new Ask outputs cannot enter the qualified
path without requiring q_aib's enrolled receipt and bound inputs. It is not a request for
a generalized producer registry or hypothetical security hardening. Passing generic data
to a private test seam is not an existing production handoff.

The missing boundary must separate **fresh-run inputs/current identity** from **persisted
qualification inputs/recorded identity**. Its identity consequence is concrete too:
a bare current-version flip invalidates the existing recorded noncurrent authorization.
Both are acceptance obligations of that runtime-versus-qualification separation; neither
can be dismissed by renaming profile B or changing constants.

Option A fails the actual-entry and preserved-identity gates. Option C is not supported:
the existing generic claim/value/proof/report semantics pass the bounded non-q_aib controls.
No scientific delta warrants sufficiency-v9.

## Actual topology, including the product/experiment distinction

### Existing application Ask surface

`app/frontend/js/20_synthesis.jsx:107` posts to `/summarize`.
`app/backend/api/routers/summaries.py:116` schedules
`_run_summarize_job` (`:240`). That job resolves the ordinary generators/verifier,
optionally calls the bounded query planner, and calls either `summarize_faceted` or
`summarize_scope`. It then rereads the committed summary through
`_persisted_summary_response` before publishing completion. Supplementary Overview
generation follows the persisted primary response.

Static searches of app/ and integrations/ find no import/call of the experimental
`run_topology`, `profile_b`, `plan_v5`, or `ask_cli_revised` pipeline.
Thus “v7/plan-v4 are current” describes this Phase-34 experimental semantic/answer layer;
it does **not** establish that either AnswerPlan version already serves the application
Ask endpoint. Changing the experiment's constants would not change that endpoint.
The application's existing persisted trust spine must not be silently bypassed by a
future integration. This audit does not authorize rewiring the product summarizer.

### Fresh execution in the Phase-34 pipeline

`experiments/ask_cli_revised/e2e.py` is the actual guarded experimental caller:

1. `run_topology` (`:1219` vicinity) loads/verifies the request/hierarchy contract,
   reviewed sufficiency contract and parent map, then calls `execute` in process.
2. The present public hierarchy gate (`:1268`) explicitly permits only the approved
   aib request. Nonhierarchical runs leave the sufficiency contract/parent map as None.
   `_default_sufficiency_loader` (`:1198`) calls `sufficiency_freeze.load_verified()`
   with its fixed default paths. Those paths come from the q_aib authored contract.
   The loader's benign-absence documentation must not be mistaken for a implemented
   arbitrary-question contract selector.
3. `execute` (`:401`) holds the sealed verified ledger and authored contract in memory.
   It builds ownership context, runs diagnostic mapping and aligned observations at
   U1/U2 using `se.SUFFICIENCY_SEMANTICS_VERSION` (`:544`, `:559`, `:771`).
4. With parent synthesis enabled and a hierarchical request, `:953` calls
   `_parent_synthesis_outputs` with the **same in-memory** sealed ledger,
   final map and recovery/search records.
5. `_parent_synthesis_outputs` (`:1096`) builds the legacy ParentClaim ledger and gaps,
   calls legacy realization, renders the additive 15* artifacts, and audits them.
   Its docstring explicitly says it does not replace top-level `14_final_answer.md`.
6. Final scientific-map and sealed-ledger trace writes occur afterward
   (`:979-1008`). There is no reload of an untrusted persisted map between U2
   and the existing parent consumer. Child/top-level Overview and ledger output
   remain separate from the additive parent output.

This is a trusted same-process call graph suitable for a narrow future direct handoff.
It currently transports dictionaries to **legacy** consumers. It does not provide a typed
fresh-run Layer C boundary, the independently authored plan-v5 node/reporting contract,
or a general current-profile output route. The existing `execute` injection seams can
accept caller-supplied reviewed contracts; the ordinary caller does not yet source them
for arbitrary questions. A fixed Phase-30 overlay cannot fill that gap.

The older package `__main__.py` also renders the ledger / explicit model comparison
terminals; it does not call the new Layer C consumer.

### Explicit offline profile B

`answer_plan/replay.py:159` explicitly dispatches profile B to
`profile_b_replay.replay`. That reads the snapshot and calls
`profile_b.build_profile_b` (`:57`).
The path is:

```text
snapshot bytes + enrolled receipt + actual input bundle
 -> layerc_consumer.verify_and_project
 -> D1 verifier + fixed registry
 -> project_authorized (exact verified type and fresh re-verification)
 -> unchanged validate_layerc_inputs
 -> claims / receipts / relationship units / deterministic synthesis
 -> plan-v5 / rendering
 -> downstream output manifest
```

`profile_b._build_components` is a detached component/test seam, not a public
fresh producer trust handoff. The tests intentionally use a clearly marked synthetic
authorization stand-in there. Calling that seam to avoid real verification would not
satisfy the production gate.

## Exact producer-authorization answers

**A. Existing same-run trusted boundary?** The legacy producer-to-parent call is already
same-process. It does not cross a persisted-map boundary or need replay authentication.
However, there is **no existing accepted direct typed handoff to v8 Layer C**. Therefore
the answer to “can it already feed the new path without the preserved receipt?” is no.

**B. Is D1 verification replay-only in the current integrated implementation?**
Conceptually its scope is offline qualification. In the code, every public integrated
profile-B build goes through it. `plan_v5.build_plan` also requires a
`producer_authorization` argument and serializes its reference/profile identities.
The pure lower-level builder can be called with a synthetic object, but that does not
authorize a production invocation. No general runtime profile exists.

**C. Would using the current public entry for fresh runs require the one-event registry?**
Yes. `producer_authorization.resolve_authority:64` requires exact accepted-receipt
membership. The installed registry contains one profile and one accepted receipt:
`callosum.qaib.preserved-v8-reproduction`, purpose `profile-b-offline-prerequisite`.
The verifier binds reviewed q_aib authoring, held nominations, snapshots and recovery.
Supplying another map or no receipt fails before projection.

Keep that registry narrow. Do not add wildcard producer authority, auto-enrollment,
signatures, dynamic entries, producer-ID-based approval, or a new producer ecosystem.
A same-process adapter should use the provenance of the actual trusted call and its
already accepted authoring inputs. Persisted replay must retain its existing authenticated
entry and exact enrolled-event checks.

## Generality audit: direct literals and transitive dependencies

An AST string/import audit inspected the nine D2 modules plus the projection and all
four helpers. No q_aib child/requirement/proposition IDs, C01-C17, V01-V32, domain category
vocabulary or preserved paths were found as direct semantic constants in those 14 files.
Manual inspection found no 17/32/41/nine-node runtime count assertions.

That lexical result is **not** a transitive generality pass:

| Module or family | Actual dependency / disposition |
|---|---|
| claim_v2.py | Authored role completion/quantifiers and projected values/proofs; no fixture ledger or count authority. |
| relation_unit_v2.py | Stored assignments, placement and semantic tuple; no fixed witness/PID authority. |
| parent_synthesis_v2.py | Typed claim/member receipts; no q_aib prompt material or model executor. |
| answer_plan/plan_v5.py | Authored nodes/reporting obligations; generic values; output identity currently coupled to profile B and a verified-producer object. |
| answer_plan/render_v5.py | Plan/receipts/synthesis; no fixture node labels/counts. |
| layerc_presentation.py | Existing presentation checks on authorized local paths; no fixture source discovery. Retains the existing generic “trait” role-name presentation heuristic, not a list of q_aib trait names. This audit does not redesign that accepted presentation contract. |
| layerc_projection.py + _layerc_common/_layerc_validation/_layerc_observations/_layerc_values | Generic structural/reference validation, supported value strategies and schemas. Admission currently requires the exact profile name and noncurrent/v8 identity. Candidate schema validation, quote canonicalization and link parsing are generic dependencies. |
| layerc_consumer.py | **Transitively fixture-bound:** imports D1 verifier and fixed registry loader. Builds the compatibility envelope only after real verification. |
| profile_b.py | **Transitively fixture-bound public entry:** always calls that bridge; output schema requires noncurrent/v8. |
| profile_b_replay.py | **Qualification transport**, not a general runtime adapter; snapshot has all exact bound producer inputs. |
| producer_authorization.py / _producer_inputs.py / fixed material store | Intentionally one-event: exact membership; fixed aib_hier_v9 authoring paths, nomination counts (including 32 slots), hierarchy/Phase-30 overlay and preserved artifact identities. Correct for qualification; prohibited as ordinary-question requirements. |
| answer_plan/replay.py / overlay.py | Existing Phase-28 replay defaults, q_aib hand-audit comparisons and Phase-30 replay-only overlay. Remain characterization tools. |
| e2e.py / sufficiency_freeze.py | Current caller is approved-hierarchy/frozen-authoring scoped, not a generic question-to-reviewed-contract/node adapter. |

The role/value/proof layer is reusable. The **public entry and authored-input/output
routing** are not a general default today. Neither a no-literal grep nor a passing q_aib
fixture establishes that boundary.

## Bounded generic offline controls A–J

Executed against unchanged source through the explicit detached test seam. The contracts
use generic child/requirement keys, item/outcome roles, alpha/beta, Amber/Cobalt and P1/P2.
No q_aib IDs, category terms, expected claim/value/node counts or preserved receipt are
inputs to these semantic controls. They prove component generality, not runtime authority.

| Control | Observed result |
|---|---|
| A — atomic named value | One authored item yields role_value/claim-v2 and an answered plan-v5 node. |
| B — same-proposition relation | Compatible stored P2 proof; relational claim and unit use P2; answered report. |
| C — incompatible filled supports | Separate filled values remain available; no relational claim or witnessed relation is invented; report partial. |
| D — category positive | Amber positive observation reported; category reporting answered. |
| E — category null | Amber null reported; positive-presence goal unestablished; recovery not closed. |
| F — multiple members | Amber's receipt cites P0 and Cobalt's cites P1; every rendered member checked against its own citation receipt. |
| G — inherited context | Inherited operand stays inherited; child P2 remains own witness authority; parent PID not inserted into child witness intersection. |
| H — nonrepresentative witness | P2 proof wins over P1 representative without rewriting binding; order reversal identical; no P1 relationship citation. |
| I — opposite directions | Both paths preserved, null consensus, within-instance conflict, no across-instance heterogeneity. |
| J — legacy/default compatibility | Default and supported-noncurrent-only routes stay legacy; explicit profile A stays legacy; defaults still v7/plan-v4. |

Additional probes pass: direct semantic-literal/import audit, generic data rejected by
the public qualification entry without receipt before Layer C, and promotion-disposition
counterfactual below.

**60 checks passed in 62.81s:** 13 local audit probes (A–J plus three boundary/static probes),
30 existing D2 profile tests, and 17 D1 static/replay tests. These rerun the accepted
profile-B baseline and all five exact historical combined hashes. No expectations were
changed. The full offline suite/optional psutil/five-known-failure rerun is required by
this request only if Option A is implemented; it was not repeated for this docs-only STOP.

Local, untracked evidence:
`.local/i4-4e/test_decision.py`, `qualification.log`, `qualification.xml`,
`static.json`, `identity_probe.json`, `replay_probe.py`,
`replay_probe.log`, `replay_identity_probe.json`.
Runner:
`.venv/Scripts/python.exe .local/i4-4c/run_offline.py .local/i4-4e/test_decision.py experiments/ask_cli_revised/test_profile_b.py experiments/ask_cli_revised/test_producer_static_replay.py -q --tb=short --junitxml=.local/i4-4e/qualification.xml`.

No retrieval, model, ranking, NLI or live E2E ran. The offline runner denied networking;
the standalone replay probe also denied socket connections. No tracked test/code was edited.

## Identity promotion: measured behavior, not a migration proposal

Maps store a semantic version per child, not the historical disposition. In
`sufficiency_identity.read_map_identity:90`, current-version comparison precedes
historical/noncurrent classification. `check_authorization_binding:126` compares an
authorization's complete status/version pair against that **present-day** classification.

A process-local, restored patch of only
`se.SUFFICIENCY_SEMANTICS_VERSION = se.SUFFICIENCY_SEMANTICS_V8` produced:

| Question | Observed answer |
|---|---|
| How does the old v8 map read? | Changes from supported_noncurrent/v8 to current/v8, even with accept_supported_noncurrent=True. |
| Is the enrolled receipt honestly still noncurrent? | Yes; its immutable body/profile still require the recorded noncurrent/v8 pair. |
| Does D1 still verify it? | **No.** “authorization binds ... supported_noncurrent ... but the map carries ... current”. |
| Does D2's public qualification rebuild still have upstream authority? | **No.** Same verifier fails before projection. Merely skipping it is prohibited. |
| Does the unchanged pure legacy-v8 characterization become scientifically unreplayable? | **No.** Explicit v8 mapping plus legacy plan-v4 still reproduces its exact original combined hash. |
| Does the legacy CLI preserve the old authorization meaning automatically? | **No.** It calls the current-relative identity reader and writes that disposition into replay authorization. A previously recorded noncurrent binding fails its equality check. |
| What if the old plan.py PLAN_VERSION is relabeled v5 too? | Legacy combined output changes to 8fd93d427a2798321ce02328de947c4784677209d8738cb605c7be63bc70c694 while map/recovery remain equal. This is relabeling legacy output, not activating the v5 builder. |
| Must a current receipt/profile be issued to keep historical qualification? | No scientific need; doing so would substitute a new qualification event rather than preserve the old one. Do not do it. |
| Is v9 needed? | No scientific semantic change was found. The problem is runtime entry and historical disposition handling. |

The v8-constant-only pure legacy combined hash stayed
`1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0`.
This distinction matters: the old scientific computation remains reproducible, but
authenticated replay interpretation is not preserved by the existing identity reader.
The probe restored both constants and reverified the original authorization successfully.

The projection's admission envelope (`layerc_projection.py:74`), bridge
(`layerc_consumer.py:37`), plan output metadata and `profile_b.validate_output:181`
also explicitly encode supported_noncurrent/v8. They are qualification contracts,
not ready-made current-runtime contracts. A general path must not falsify that status
merely to reuse them.

## Preserved exact history

| Accepted artifact | Exact combined SHA-256, rerun unchanged |
|---|---|
| v4 | 4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a |
| v5 | 109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77 |
| v6 | dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be |
| v7 | 04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72 |
| v8 profile A, legacy Layer C/plan-v4 | 1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0 |
| D2 profile B, qualified under noncurrent/v8 | e697596b8fb3dd3ce426cdc1b82909ca93f4bbc3346e46b74bf2f96f980eafde |

D2's exact 17 claims/32 values/13 inherited placements/41 units/nine statuses remain
fixture tests only. The ordinary runtime must not adopt those counts as its output contract.
No baseline, enrolled material, disposition record or expected identity was rewritten.

## Smallest next increment — specification only

Proposed **I4-4E1: fresh-run Layer C adapter with recorded-qualification identity separation**.
This is the single missing runtime/qualification boundary identified above, not generalized
producer enrollment. Do not implement it under this audit's authorization.

Bound its acceptance to:

1. At the actual post-U2 handoff, accept the current run's already reviewed authored
   sufficiency contract, request-owned visible/reporting nodes, sealed evidence, final map
   and recovery/search state. Do not load q_aib authoring, nominations, overlay or counts as
   fallback. Identify the exact caller supplying those inputs; an injected unit-test object
   alone is not a general default route.
2. Provide a narrow same-process adapter to the existing reference/value validator and
   v2 consumers. Provenance comes from the trusted invocation, not a fabricated
   VerifiedProducerAuthorization or self-hashed replay envelope. Keep persisted inputs on
   the enrolled replay path. Do not skip validation, recompute science, or add a registry.
3. Separate execution disposition for new current runs from the authenticated recorded
   disposition of accepted qualification. Keep old v8/noncurrent receipts and both old
   baselines byte-for-byte. Preserve explicit legacy plan-v4 selection instead of changing
   its module constant to label legacy objects v5. Validate recorded qualification version
   and exact event binding without depending on today's current-version classification.
   The precise narrow API change needs its own review; no migration framework or new
   scientific version is warranted.
4. Exercise the **public fresh caller** with a non-q_aib authored request and make its
   v2 output the selected answer-layer result, not just an additive/test artifact. Repeat
   generic A–J, public routing, untrusted-replay rejection, old identity and exact baseline
   checks before any subsequent default promotion.

These are acceptance conditions of one adapter/profile separation, not four independently
authorized projects. In particular, this report does not pretend arbitrary-question
authoring or application endpoint integration already exists. Do not invent a new authoring
system or cross the application's persisted trust spine to make the adapter appear
complete. If the selected fresh caller cannot supply its approved contract/reporting
inputs, surface that concrete caller limitation in E1 rather than smuggling the fixture in.

No broader cryptography, extensible producer ecosystem, role ontology, schema cleanup or
future unsupported-feature work is on this critical path. No I2-3 prose changes belong here.

## Files, hooks, and stop

Tracked change set is exactly:

- `experiments/ask_cli_revised/PHASE34_I4_4E_PROMOTION_GENERALITY_DECISION.md`
- `experiments/ask_cli_revised/CONTRIBUTION-LINEAGE.md` — appended decision entry.

Normal documentation hooks: all applicable checks passed (whitespace, EOF, merge conflicts,
large files). Python/security/module/line-budget hooks correctly skipped this Markdown-only change.
No hook bypass is authorized or used for Option B. No production code, tests, versions,
authorization material, scientific behavior or baselines changed.

**OPTION B. NOT READY for bounded I2-3.** Stop after documenting/committing/pushing this
decision. Do not implement E1, promote v8/plan-v5, begin I2-3/live E2E, add enrollment or
signatures, register same_local_assertion, or implement claim-goal/authority-veto semantics.
