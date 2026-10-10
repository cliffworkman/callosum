# Phase 34 / I4-3C0 — explicit supported-noncurrent semantics identity

Date: 2026-10-09. Bounded identity prerequisite implementation.

Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
Verified clean starting HEAD: `5dbd73946b02a8910fa477d6e74f2dccd09c9867`.
Final implementation HEAD is the single commit containing this report: resolve with
`git log -1 --format=%H -- experiments/ask_cli_revised/PHASE34_I4_3C0_SUPPORTED_NONCURRENT_IDENTITY_RESULTS.md`.
The exact commit hash is reported in the delivery receipt; it cannot be embedded in its own committed content.

**READY for separately authorized I4-3C.** The identity substrate can now distinguish a supported,
versioned, deliberately non-current and non-historical map. Current/default remains
`sufficiency-semantics-v7`; the production supported/historical sets are unchanged. No v8 constant,
routing, supported membership, replay baseline, witness implementation or alignment fields exist
as a result of this increment.

## State machine and API

Before this change, a supported version outside current/historical could be stamped but the reader
called it unsupported. The new disposition is exactly
`STATUS_SUPPORTED_NONCURRENT = "supported_noncurrent"`.

`read_map_identity` adds keyword-only `accept_supported_noncurrent=False`. Existing unversioned,
partial, mixed, non-string and empty-map checks retain their behavior. Classification remains ordered:

1. Handle unversioned maps and reject malformed identity as before.
2. Recorded version equals current: current, accepted without opt-in.
3. Recorded version belongs to HISTORICAL: historical_versioned, requires its existing flag.
4. Remaining recorded version belongs to SUPPORTED: supported_noncurrent, requires the new flag.
5. Otherwise: unsupported error even with every flag enabled.

All flags default to False. Each non-current category requires its own explicit flag; combinations
can authorize several categories without one flag implying another. Current and historical priority
are tested even when membership overlaps. No additional production version set was introduced.

The artifact still stores only its semantic version on each child. Disposition is determined by
the reader's version configuration, not written into map bytes. Authored frozen contracts and git
provenance remain distinct identities.

## Applied semantics and authorization

`applied_semantics_version` returns the recorded version for current, historical_versioned and
supported_noncurrent. Historical_unversioned still applies the contemporary current version without
attributing that version to the historical artifact. Unknown status still raises. Existing malformed
input behavior is frozen: missing version on a recognized versioned status raises KeyError;
non-mapping input raises AttributeError. This increment does not broaden that helper's validation contract.

`check_authorization_binding` now enables all three reader opt-ins internally because it checks
consistency, not entry-point permission. Its exact `bound == actual` comparison is unchanged,
including status and version. An authorization claiming current/X or historical_versioned/X fails
against supported_noncurrent/X. Unsupported/mixed actual maps and malformed bound keys fail closed.

The existing replay digest verifier continues to validate the digest, exact identity and both
recorded applied semantic rules. No catch-all status branch or version-only authorization was added.

## Explicit offline replay seam

The sole new external opt-in is
`answer_plan/replay.py --allow-supported-noncurrent`. It passes the parsed boolean directly to
the identity reader. Omitting it remains strict; either historical flag alone still rejects
supported_noncurrent. The existing CLI then applies and records the map's version in its exact
authorization. No answer construction, rendering, PLAN_VERSION or ParentClaim semantics changed.

The sentinel integration test stamps a copied preserved map, proves rejection under default and
historical-only CLI paths, runs the explicit path, checks exact status/version authorization and
verifies the input bytes remain unchanged. Because the test-only sentinel has **no semantic
implementation**, a scoped test double at build_plan asserts both received semantic arguments are
the sentinel, then uses the unchanged v7 plan/render implementation. This proves identity/replay
transport, not witness support for a hypothetical semantic version. Real v4-v7 replay gates run
without this sentinel stand-in.

## Production call-site inventory

Repository-wide search for all three APIs found only these production calls:

| Caller | Classification | Change |
|---|---|---|
| sufficiency_identity.check_authorization_binding → read_map_identity | Generic authorization consistency | Recognize new disposition internally; exact binding unchanged. |
| answer_plan.replay.main → read_map_identity | Strict default; explicit historical replay; now explicit noncurrent replay seam | New independent CLI flag only. |
| answer_plan.replay.main → applied_semantics_version | Apply accepted replay identity | No call-site change; helper recognizes new state. |
| answer_plan.replay.main → check_authorization_binding | Check newly constructed authorization | No call-site change. |
| answer_plan.replay.verify_replay_authorization → check_authorization_binding | Generic authorization consistency | No call-site change. |
| answer_plan.replay.verify_replay_authorization → applied_semantics_version | Verify recorded rules against bound identity | No call-site change. |

There is no additional ordinary production read_map_identity call to relax. The replay default
remains current-only. Static AST guards inventory every new opt-in keyword in production experiments,
app and integrations: only the consistency helper's literal True and the replay CLI's parsed flag
are allowed. Behavioral flag matrices reject permissive-default/catch-all behavior.

## Lifecycle and promotion

Tests use only `sufficiency-semantics-test-supported-noncurrent`, inserted into the supported set
with scoped monkeypatching. No sentinel survives in production configuration.

The same serialized map first reads supported_noncurrent under explicit opt-in. A test-only current
promotion makes those exact bytes read current. The earlier noncurrent authorization then fails,
including when its recorded version still matches. A freshly generated current authorization passes.
A subsequent test-only historical classification requires its own historical flag and rejects the
prior noncurrent receipt. Current wins even when also listed historical; historical wins before
the generic supported branch. Map bytes never change during these transitions.

## Verification

**116 new identity tests passed** in the full run. The targeted identity, semantic-version/threading,
AnswerPlan replay, referent-containment and four-version replay battery passed **206 tests**.
These overlapping counts are not summed.

All eight flag combinations are exercised against each of four dispositions and eight invalid-map
forms. Additional cases cover applied versions/malformed identities, all four matching authorizations,
wrong-status/same-version bindings, wrong versions, malformed bound keys, digest tampering, applied-rule
tampering, lifecycle transitions, CLI transport, static opt-in ownership and absence of real v8 support.

| Explicit replay | Exact unchanged SHA-256 |
|---|---|
| v4 | `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a` |
| v5 | `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77` |
| v6 | `dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be` |
| v7 | `04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72` |

The existing four-version frozen-baseline gate recomputed these bytes from preserved inputs.
No replay artifact or baseline file changed. Existing current and historical disposition expectations
also pass. No supported version was reclassified by the production configuration.

Full offline experiments: **5,002 passed, five independently reconfirmed baseline failures,
12 skipped, nine existing xfails, 276 subtests passed**. The optional dependency-complete offline
module passed **seven tests** in the existing Anaconda environment. There were no unexplained
new failures.

Known failures were independently reproduced using starting-HEAD identity/replay modules loaded
from exact git bytes, with the other production modules unchanged and hierarchy resources at their
original path. The five failures are not hidden or marked xfail:

| Existing failure | Reconfirmed cause |
|---|---|
| ask_070/test_corpus_and_referents::test_dev_eval_separation | Missing frozen/dev_inputs_v0.json. |
| ask_070/test_schema_validation::test_real_frozen_nonsemantic_artifact_schemas | Missing frozen/corpus_presence_v0.json. |
| test_e2e_run::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored | Existing Ollama /api/tags probe denied by the offline guard. |
| test_hierarchy_contract::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts | Existing hierarchy_contract.py code-input pin drift. |
| test_hierarchy_e2e::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects | Same pin rejection returns 3 rather than 0. |

Local verification receipts are under `.local/i4-3c0/`: full.log/xml, known-head.log and optional.log.
The full suite used the existing socket-denial offline fixture. The optional module's actual live
clients/runtime are replaced by scripted test doubles and guarded by endpoint refusal.
No live retrieval, model call or live E2E occurred.

Ruff format/check, content hooks, Bandit and Tach pass. The initial hook invocation used system
Python without Bandit/Tach; rerunning with the repository virtual environment on PATH resolved
those environment errors. The sole remaining hook failure is the pre-existing 615-line frontend
file. Its starting and working Git blob hashes are both
`03f9d3dfee3763533a78d5da601a99cb81bb37f1`. The user's I4-3C0-only bypass authorization applies;
the frontend is untouched. The complete hook receipt is `.local/i4-3c0/hooks-final.log`.

## Exact changed files and stop

All paths are under `experiments/ask_cli_revised/`:

- sufficiency_identity.py — new disposition, orthogonal reader opt-in, application and consistency recognition.
- answer_plan/replay.py — explicit offline CLI flag and reader forwarding only.
- test_i4_3c0_supported_noncurrent.py — matrices, lifecycle, authorization, CLI and static guards.
- PHASE34_I4_3C0_SUPPORTED_NONCURRENT_IDENTITY_RESULTS.md — this receipt.
- CONTRIBUTION-LINEAGE.md — append only.

No candidate, witness, observation, engine-version, policy, guard, attribution, ParentClaim or
AnswerPlan semantic implementation changed. No unrelated module allowlist changed.

**STOP after I4-3C0.** The identity substrate is READY. I4-3C witness implementation requires
separate authorization and has not resumed. No I4-4 or I2-3.
