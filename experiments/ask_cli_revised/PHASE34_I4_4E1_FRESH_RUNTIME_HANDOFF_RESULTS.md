# Phase 34 / I4-4E1 — fresh runtime handoff results

**Decision: STOP.** The selected fresh caller has no request-owned, authored reporting/node
contract for plan-v5. This is the concrete missing caller capability specified as a stop
condition in the E1 request, sections 12–13. No handoff or recorded-identity implementation
was started. This report does not claim readiness for I4-4E2.

## Checkpoint and scope

- Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
- Starting HEAD: `35b800473bc5c756d6950eb680c2ff27dd2ef7fa`.
- Full HEAD and clean worktree were verified before the investigation.
- Final HEAD remains `35b800473bc5c756d6950eb680c2ff27dd2ef7fa`.
- This increment changes only this report and an append to
  `experiments/ask_cli_revised/CONTRIBUTION-LINEAGE.md`.
- No implementation commit or push: section 34 authorizes the atomic implementation
  commit only if every gate passes; the prerequisite stop condition was reached instead.

The request authorizes a bounded implementation, but explicitly requires stopping if the
fresh caller cannot supply its required authored reporting contract. That check precedes
building an adapter. The accepted generic claim/value/proof/report semantics were not
reopened. Neither a detached builder nor a test-supplied overlay would establish the
missing production caller capability.

## Fresh topology and the missing input

Source locations below refer to the unchanged starting HEAD.

| Boundary | Actual available input or behavior | Reporting limitation |
|---|---|---|
| `request_contract.py:60–99` | Generic literal request, original question hash, source-unit offsets and retrieval obligations. Explicitly records semantic completeness as not certified. | Navigation spans do not authorize a semantic reporting decomposition or node-to-child ownership. |
| `hierarchy_contract.py:198–251, 653–676` | Approved child wording, parent links, scope, qualifications, obligation ownership, folded children and readiness. | These are execution/retrieval children and hierarchy metadata; there is no authored visible reporting-node contract. |
| `e2e.py:1219–1296` (`run_topology`) | Hierarchy mode accepts only the approved aib request. It loads its hierarchy and sufficiency contract; the flat path builds literal-request-v1. | No reporting-contract loader/argument or reviewed reporting input is supplied. The hierarchy/sufficiency loader seams do not supply plan-v5 nodes. |
| `e2e.py:401–417` (`execute`) | Accepts the request contract, reviewed sufficiency contract and parent map, plus execution options. | No separate reporting contract is accepted, nor does the actual request contract contain one. |
| `e2e.py:953–967` | Passes the final in-memory map, sealed evidence, recovery/search state and question to the parent consumer after scientific production. | The call does not supply authored reporting nodes or a bound decomposition for plan-v5. |
| `e2e.py:1096–1154` (`_parent_synthesis_outputs`) | Legacy parent claims, gaps, realization and additive 15* artifacts. No persisted-map reload intervenes. | The consumer does not build a reporting contract and does not select a plan-v5 answer. |
| `answer_plan/plan_v5.py:115–135` | Iterates `authored["overlay"]["nodes"]`, aggregates facets via each node's `owning_child_ids`, and emits authored `label`, `literal_text` and `parent`. | Those inputs are mandatory authored reporting decisions, not properties derivable from output state. |

The missing capability is therefore precise: **the actual fresh caller must supply and
bind reviewed/request-owned visible nodes, their literal wording and parent relationships,
and their ownership of scientific children to the same invocation's authored requirements.**
The requirement contract already supplies role-completion and quantifier obligations;
those alone do not specify the visible reporting structure.

Inspection searched the production experiment Python sources for `owning_child_ids`,
`literal_text`, `reporting_contract` and `report_contract`, and inspected both request
builders, the topology, the post-U2 call and the plan consumer. The node-ownership usages
are in the answer-plan overlay/plan consumers. No fresh producer of this contract was
found. This conclusion is based on caller construction and field consumption, not solely
on the absence of a conveniently named parameter.

## Why the existing material does not fill the gap

`answer_plan/overlay.py:1–6, 17–18, 41–44` explicitly defines its overlay as replay-only.
Its default artifact, `answer_plan/overlays/phase30_replay_decomposition_overlay.json`,
records `REPLAY_ONLY_OFFLINE_OVERLAY`, the preserved Phase-28 run, and confirmation
postdating that run. Its scope statement expressly does not claim the old live execution
carried this authorization. It also says future runs must use the confirmed decomposition
before retrieval. Nothing in the selected fresh caller loads or binds that material as
part of its actual invocation.

The hierarchy's child wording, execution parent links and folded records are legitimate
inputs. Treating each executable child as a visible plan node, choosing visible labels,
or mapping them to the historical overlay's labels would add a reporting-authoring decision
that this caller has not supplied. In particular, execution hierarchy and visible reporting
ownership are not interchangeable merely because both describe the request.

The accepted E report already identifies this limitation in its topology analysis and
requires E1 to surface it if unresolved. E1 sections 12–13 prohibit substituting fixture
material or inventing a general question-decomposition system. Accordingly no fallback,
new authoring system, fixture import or synthetic-only public-path claim was introduced.

## Handoff, authority and identity status at stop

| Requested result | E1 result |
|---|---|
| Public fresh post-U2 entry to v2 Layer C | Not implemented; required authored reporting input is unavailable. |
| Fresh invocation provenance type/schema/ref | Not created. No fake producer authorization or receipt was minted. |
| Fresh/replay trust separation | Existing replay authentication remains unchanged; no new fresh path exists. |
| Shared scientific projection/validation | Unchanged. No bypass, duplicate scientific implementation or weakened reference/proof/value check. |
| Plan-v5 upstream authority generalization | Not implemented. Existing qualification output remains exact by leaving its code and artifacts untouched. |
| Recorded historical disposition separation | Not implemented after the prerequisite stop. The E finding remains unresolved. |
| Hypothetical v8-current regression | Not rerun or claimed passing in E1. The accepted E experiment found the old noncurrent receipt fails under a hypothetical current-v8 classification. |
| Public non-q_aib fresh run | Not executed; cannot truthfully satisfy it with the existing reporting inputs. |
| Generic A–J through fresh handoff | Not run; no handoff exists. Accepted E generic-component results remain prior evidence only. |
| Proof that fresh runs need no q_aib receipt | Not established by a runtime test. It remains the required boundary design. |
| Persisted replay requires D1 | Existing code retained: `profile_b.build_profile_b` calls `layerc_consumer.verify_and_project`; producer authorization checks exact enrolled event/profile/input bindings. No fresh-deserialization bypass was added. |

The unchanged identity code confirms the earlier mechanism: `sufficiency_identity.py:90`
classifies against today's current version first; `check_authorization_binding:126–145`
compares the recorded pair to that classification. `producer_authorization.py:106–108`
requires the exact noncurrent/v8 pair and calls that binding check. This source inspection
does not constitute an identity repair or a new regression-test result. Current defaults
remain v7/plan-v4. No v9, replacement receipt or rewritten historical disposition exists.

## Historical evidence and verification limits

The following hashes are the accepted, previously rerun E baseline values, reproduced here
as historical evidence. **They were not recomputed during this stopped E1 increment.**

| Artifact | Accepted combined SHA-256 |
|---|---|
| v4 | `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a` |
| v5 | `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77` |
| v6 | `dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be` |
| v7 | `04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72` |
| v8 profile A, legacy plan-v4 | `1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0` |
| D2 profile B, recorded noncurrent/v8 | `e697596b8fb3dd3ce426cdc1b82909ca93f4bbc3346e46b74bf2f96f980eafde` |

No historical artifacts, profile/receipt IDs, baselines or production source files were
edited. Scientific immutability here is a no-change source/artifact check, **not** a
before/after fixture run through a new consumer. No new scientific outputs were produced.

Implementation tests, full offline experiments suite and optional psutil qualification
were not run after the explicit prerequisite stop. There is no E1 test-pass count and
no claim of independently reconfirming the five known suite failures. Those previously
recorded failures remain:

1. `ask_070/tests/test_corpus_and_referents.py::test_dev_eval_separation` — missing frozen dev inputs.
2. `ask_070/tests/test_schema_validation.py::test_real_frozen_nonsemantic_artifact_schemas` — missing corpus-presence artifact.
3. `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored` — offline Ollama tags access denied.
4. `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts` — existing hierarchy code-pin drift.
5. `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects` — same existing hierarchy-pin failure.

These are prior qualification results, not five freshly observed E1 failures. No external
search, retrieval, live model/NLI calls or live E2E occurred. The final diff is documentation
only and is checked for whitespace errors. No hook bypass is used.

## Stop disposition

**STOP — one concrete remaining promotion blocker: the selected fresh caller cannot
supply an authored, request-owned reporting/node contract required by plan-v5.**

This prevents completing the authorized fresh-runtime boundary; the associated identity
repair remains unimplemented as part of that stopped increment. No partial implementation
is presented as ready. No automatic follow-on planning arc, promotion, I4-4E2, I2-3,
application `/summarize` rewiring or producer-enrollment expansion was begun.
