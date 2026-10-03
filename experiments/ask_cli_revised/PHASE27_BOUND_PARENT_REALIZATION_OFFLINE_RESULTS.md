# Phase 27 — bounded parent realization + production wiring (offline only)

> **Phase 27a supersession note (additive; the body below is the Phase-27 record and is not rewritten).** The
> whole-answer schema described in §5 carried an editorial `minLength`, a claim-id `enum`, and a `maxItems` equal to the
> claim count. Any violation made the supervisor return NO ANSWER for the entire response, so one too-short statement
> collapsed all claims to deterministic fallback. §5's "enum" description, §8.4 (the open whole-call collapse debt), and
> the §6/§7 replay counts are superseded by Phase 27a: see
> `PHASE27A_PARENT_REALIZATION_PER_CLAIM_FALLBACK_RESULTS.md`. The §7 padded-faithful baseline of 20 grounded / 4 fallback
> is unchanged by 27a. The before-state for the collapse (0/24 whole-call with an unpadded or one-short answer) was
> measured on HEAD `15d4a99f` and is recorded in the 27a results document, not in this one.

**Status: offline implementation complete; no live model call, no network, no e2e run, no recovery rerun, no
contract or pin change.** Phase 28 readiness is **FALSE** pending the upstream fix recorded in §4 (disposition B). This
is a judgment for Cliff to overrule, not a settled finding.

---

## 1. Scope and gates

Implemented exactly the Phase-27 brief's offline surface: the model decides only how to phrase an already-authorized
`ParentClaim`; a closed, claim-bounded output schema; one S2 call per run with no retry; two independent fidelity layers
with one batched local NLI pass; a heterogeneity/conflict guard; deterministic gaps and citations; a per-claim
deterministic fallback; a default-off `--parent-synthesis` flag that requires `--hierarchy`; additive artifacts; audit
extension; and an offline replay over the frozen Phase-23 state with a fake S2 client.

Not done, by instruction: no live or networked model call, no live parent-synthesis run, no recovery rerun, no c12
correction or tuning, no sufficiency-semantic change, no contract or pin change, no simple-question routing. No
existing `14_final_answer.md`, `14a_overview.*`, `14_final_answer.{child}.md`, or `14b_detailed_inspection.*` is written
or altered. `overview.py`, `overview_guards.py`, and `overview_evidence.py` are unchanged.

## 2. Files changed

| File | Change |
|---|---|
| `parent_synthesis.py` | **New.** The realization stage: closed prompt and schema builders, `authorized_claim_text`, output parsing, the claim-value and source-passage screens, the heterogeneity guard, the single batched NLI pass, and `realize()`. |
| `parent_synthesis_render.py` | Additive. Artifact-name constants (`15a_…json`, `15_parent_answer.md`, `15b_…md`); `render_answer` accepts `realized_text`/`cite`; `construction_record` accepts `realization`; `render_inspection`. Phase-26 default output is unchanged. |
| `parent_synthesis_audit.py` | Additive. Nine realization re-derivations run only when a record carries `realized_segments`, so a Phase-26 record audits exactly as before. |
| `parent_synthesis_test_support.py` | Additive. `FakeParentClient`, `make_s2_supervisor`, `FakeEntail`, on top of the Phase-26 helpers. |
| `topology.py` | Additive. `PARENT_SYNTHESIS_S_OPTIONS = dict(SUPERVISOR_BASE_OPTIONS)`. |
| `e2e.py` | Additive. `execute(parent_synthesis_enabled=False)`; the `_parent_synthesis_outputs` helper; `run_topology(parent_synthesis=…)`; the `--parent-synthesis` flag; the manifest block, present only when requested. |
| `hierarchy_test_support.py` | Additive. `HierHarness.run` forwards `parent_synthesis_enabled` (default False). |
| `test_parent_synthesis.py` | **New.** 43 tests: the realization matrix. |
| `test_parent_synthesis_wiring.py` | **New.** 15 tests: default-off, decline, lifecycle position, flag validation, manifest, and the helper's positive path. |
| `test_parent_synthesis_replay.py` | **New.** 13 tests: 8 real frozen-state replay tests and 5 tamper-audit tests. Artifact-gated; skips cleanly when the frozen run directory is absent. |
| `PHASE27_BOUND_PARENT_REALIZATION_OFFLINE_RESULTS.md` | **New.** This document. |
| `CONTRIBUTION-LINEAGE.md` | Phase-27 entry appended; prior entries unchanged. |

Unchanged: `parent_synthesis_ledger.py`, the Phase-26 ledger, render, and audit tests (52 tests), all frozen contract and
pin files, and the Overview modules.

## 3. Preflight 0A — the c8 discrepancy (resolved from raw data)

Phase 23a's §7 says `c8`'s `relationship_to_bias_manifestation` role "never received a single candidate, even after
recovery." The raw artifacts contradict that sentence. Checked against `sealed` (`11_verified_ledger.json`) and the
Phase-23 `sufficiency_map_final`:

- **U1** (`relationship_to_bias_manifestation`) was filled pre-recovery by `p8` via `deterministic_mapping`
  (`achieved_outcome_predicate`). `p8` is in the sealed ledger: paper 67, chunk 35111, responsive to `c3` and `c8`,
  origin `initial`.
- **U6** (`individual_difference_trait_or_construct`, four instances) was filled by `p20` via `model_mapping`
  (`model_nomination_only`, `nomination_status` fresh/held-fixed-replay), with `supporting_proposition_ids` `['p20','p9']`.
- **No instance has both roles.** The relation is filled in U1 only and the trait in U6 only, so the requirement never
  reaches `complete`. The two persisted targets are `c8::2319dd98f7ccdf62` (trait, missing, scope none) and
  `c8::74f276a249cb741e` (relation, missing, scope none).

**Verdict.** The Phase-26 ledger is correct. The `c8` requirement is correctly incomplete. Phase 23a's *mechanism*
sentence is overbroad, but its *conclusion* holds. The Phase-26 ledger carries both facts: a `role_value` claim for `p8`
under `relationship_to_bias_manifestation`, and a `category_list` claim for the trait role.

**Phase-27 clarification (additive; Phase 23a is not rewritten).** The relation role received and filled a candidate
(`p8`, instance U1, deterministic mapping, pre-recovery). It was not starved. Its unresolved target persists because the
trait and relation roles are filled in disjoint instances.

## 4. Preflight 0B — `empty_result_semantically_allowed`

**Facts (grep and read, not inferred).**
- The flag is authored on every requirement (`sufficiency_authoring.py:303`) and persisted by the engine's requirement
  constructor (`sufficiency_engine.py:224`, `:260`).
- **No consumer exists.** `sufficiency_recovery_targets.py`, the engine's completion and recovery logic, and the
  Phase-26/27 ledger and gap code never read it. The ledger records only a note (`parent_synthesis_ledger.py:482`).
- Only `c4`'s `specific-region` requirement (`exists`) carries the flag as `True` in the v9 contract.
- Pre-recovery, `c4`'s `exists` requirement had one instance and zero complete instances, with two single-role
  scope-none missing targets. The empty-result path is therefore reachable pre-recovery.
- In the frozen final state, `c4` is filled 8/8. Its eight remaining targets are instance-scoped
  `provisional_corroboration`, not empty-result gaps. **The frozen final state is unaffected.**

**The exposure.** The gap report has no field for this flag (verified: no key contains "empty"). In any run where
`c4` stays at zero instances, a semantically permitted empty result would be presented as an unresolved `missing` gap
rather than as a permitted empty answer.

**Disposition: B.** The flag is an unconsumed upstream semantic, and whether the intended Phase-28 fixture reaches the
empty path is a judgment. I classify it as affecting Phase 28 conservatively. Phase 28 readiness is therefore FALSE until
a narrow upstream fix lands in a separate, approved step. This is not a Phase-27 change: no sufficiency semantic is
altered here. **Cliff may overrule this to disposition A** if the Phase-28 fixture is known not to reach `c4`'s empty path.

## 5. The realization stage as implemented

- **Model input.** `authorized_claim_text` is the only content shown per claim: the claim's own values, its category
  description, and the relation or direction summary. No proposition ids, no passage text beyond the claim's own
  values, and no internal instance keys.
- **Closed output schema.** `items[]` with `claim_id` as an enum of the supplied ids, `statement` 15–400 characters, and
  `maxItems` equal to the claim count. There is no citation field, so the model cannot name a proposition.
- **Call discipline.** Exactly one S2 call per run, inside `call_context` (stage `S2`, resident `S`), with no retry. The
  binding check requires the parent envelope (`ollama`, `think=False`, `PARENT_SYNTHESIS_S_OPTIONS`); otherwise the stage
  is skipped with `s_binding_not_parent_envelope`. Skip order is no_claims, no_s_supervisor, no_entailment_scorer,
  s_binding_not_parent_envelope, output_cap_exceeded, prompt_too_large.
- **Two independent fidelity layers, one batched NLI pass.**
  - *Claim-value fidelity:* `overview_guards.screen` on the envelope; role-slot coverage for short values (≤8 content
    words), so a substituted slot value is withheld; `imports_other_claim:{id}`; `relation_language_not_in_claim`.
  - *Source-passage fidelity:* `overview_guards.screen` over the claim's admissible passages, plus
    `source_set_exceeds_screen_limit`, `no_admissible_passage`, and `unresolved_authorized_passage`.
  - All candidate claim/evidence pairs go into one batched `entail` call. An NLI failure yields `nli_unavailable`, and the
    segment is withheld.
- **Heterogeneity/conflict guard.** `consensus_collapse:{cue}` and `heterogeneity_not_stated` fire when the statement
  collapses across-instance heterogeneity or conflict.
- **Per-claim fallback.** A missing, duplicate, or unknown-id candidate falls back to that claim's deterministic literal.
  A whole-call failure (NO ANSWER, malformed output, or an exception) falls back all segments as `whole_call_failed`.
- **Deterministic gaps and citations.** Citations come only from the ledger's `admissible_proposition_ids`, never from
  the model. The gap report is the full deterministic 33-entry report.
- **Artifacts.** `15a_parent_synthesis.json` (construction record, including `realized_segments`,
  `realization_state`, `call_attempted`, and model metadata), `15_parent_answer.md`, and `15b_parent_synthesis_inspection.md`.
  The top-level `14_*` artifacts are never written.
- **Default-off wiring.** `--parent-synthesis` requires `--hierarchy` (checked in the parser and independently in
  `run_topology`). `execute()` defaults to `parent_synthesis_enabled=False`, so the return dict and manifest are unchanged
  when the flag is absent. A declined record is written when there is no sufficiency map.

## 6. Tests

| Suite | Result |
|---|---|
| `test_parent_synthesis.py` (realization matrix) | 43 passed |
| `test_parent_synthesis_wiring.py` (wiring, default-off, lifecycle) | 15 passed |
| `test_parent_synthesis_replay.py` (real frozen state + tamper audit) | 13 passed |
| Phase-26 `test_parent_synthesis_ledger.py` / `_render.py` / `_audit.py` | 52 passed, unchanged |

**Full regression** (`experiments/ask_cli_revised`): see §10 for the final numbers. The run was executed through a
scratch-only launcher (§9) that refuses shared/isolated Ollama and non-loopback sockets.

## 7. Real offline replay over the frozen Phase-23 state

Read-only over `phase23_result.json` and `run/11_verified_ledger.json`. The production `_parent_synthesis_outputs` helper
runs with a real `stages.Supervisor` on the parent envelope and a fake S2 client. Nothing is written outside a temp
directory.

| Scenario | Realization state | S2 calls | Grounded / fallback | Audit | c12 relational |
|---|---|---|---|---|---|
| Faithful restatement of the authorized values | `mixed_model_and_fallback` | 1 | 20 / 4 | ok | **grounded**, wrong value preserved |
| c12 adversary: restates everything, rewrites c12's target slot | `mixed_model_and_fallback` | 1 | 19 / 5 | ok | **withheld** (`value_not_covered` on `intervention` and `target_manifestation`); fallback carries the ledger's value |

- 24 claims and 33 gap entries, as expected. Each claim is represented exactly once. Every citation resolves to the
  claim's own admissible ids.
- The faithful run's four fallbacks are real screen outcomes: `direction_or_effectiveness` c12 (`negation_introduced`)
  and the c8, c10, and c11 category lists (`hedge_dropped`).
- **The c12 wrong value is preserved.** The ledger carries `target_manifestation = "bias toward people of color"`, the
  confirmed-wrong half of Phase 23a's adjudicated contrast. The source passage contains that sentence, so the faithful
  realization grounds it. The design cannot correct an upstream role value, and this replay proves that by construction.
- The adversarial correction is rejected by the screens, and the deterministic fallback states the ledger's value.
  Neither path restores the correct target.

**Test-double defects found and corrected during this replay (fake only; no production change).** The first faithful
fake extracted only lines containing `": "`, so list items came out as an empty statement, and it produced some
sub-15-character fragments. Both were fixed in the fake, which now restates each claim's own values verbatim and gives
short fragments a neutral sentence frame. The final numbers above are from the corrected fake.

## 8. Debt and findings (recorded, not fixed; outside Phase-27 scope)

1. **The c12 wrong target survives as a grounded statement.** See §7. This is the design's intended boundary: the
   realization cannot correct upstream role values. The consequence is that a live parent answer will repeat Phase 23a's
   confirmed `c12` error with a grounded label. **This must be surfaced to Cliff before any live parent answer is shown
   as trustworthy.** An upstream role-binding fix is a separate decision.
2. **The `c8` trait category list carries Phase 23a's adjudicated-incorrect item #29**, "undesirable behaviors (less
   generosity in the DG)." That item is a behavior, not a trait, and Phase 23a rejected it. Its `category_list` claim
   lists every value, so the deterministic fallback states it. Upstream debt, not fixed here.
3. **`empty_result_semantically_allowed` is unconsumed** (§4). Disposition B; Phase 28 is blocked on a narrow upstream fix.
4. **A single schema-invalid statement collapses the whole call.** The supervisor enforces the closed schema, so one
   statement under 15 characters (or any other schema violation) returns NO ANSWER, and every claim falls back. A real
   model is unlikely to emit a bare fragment, but this is a fragile contract. Relaxing it to per-item acceptance is a design
   decision for a later phase, not a Phase-27 change, because the schema is the contract.
5. **Duplicate values inside a category list are not deduplicated.** The `c10` and `c11` lists carry "Hadza" twice, so the
   statement reads "Hadza; Hadza". This is a ledger presentation issue, not a fidelity failure.
6. **No positive `execute()`-level realization fixture exists offline.** Synthetic evidence cannot reach the deterministic
   fill. Coverage is provided by the helper-level wiring tests and the frozen-state replay above. The first positive
   end-to-end exercise is therefore the Phase-28 live run, which requires a separate authorization.

## 9. Known gaps and disclosures

- **Scratch launcher for the regression run.** The full `ask_cli_revised` run used a scratch-only launcher
  (`p27_guarded_pytest.py`, not committed). It refuses any socket connection to the shared Ollama (11434) or isolated
  JUNO Ollama (11435) and any non-loopback host, before a byte is sent. Two pre-existing tests open real sockets to those
  ports: `contract_directed/test_coverage_budget_guard.py::…isolated_endpoint_through_to_the_real_socket` and
  `contract_directed/test_live_command.py` (a raw `connect` probe to 11434). The first is covered by the shim. The second
  was **not run**: its probe would read as a false failure under the shim, and it is unrelated to Phase 27. Reported as NOT
  RUN.
- **Three known baseline failures** (recorded in Phase 26 §22, reproduced on the clean Phase-25 baseline) were not fixed:
  `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`,
  `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`, and
  `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`.
  The third is the loopback-Ollama `ConnectError` flake. Under the shim it fails through the same refusal path.
- **Pre-existing formatting drift in `topology.py`.** `ruff format --check` flagged one line-wrap in the `CHILD_OVERVIEW_PROFILES`
  `T5C` block from an earlier phase, which the pre-commit `ruff-format` hook then blocked on. Formatted that single
  line (formatting-only; no code change) so the hook passes; it is the only non-Phase-27 line in this commit.
- **Audit gate.** Phase 27 adds no new endpoint, no new external fetch, and no new dependency. It adds a model-backed
  stage, so `.claude/LATENCY.md` applies. The stage makes one call, uses the existing batched NLI seam, and adds no
  polling, retry, or per-item inference. The latency claim is structural and has not been benchmarked: no live run exists.

## 10. Final results

- Phase-27-area focused suites: **123 passed** (43 + 15 + 13 + 52).
- Full `experiments/ask_cli_revised` regression, run on the final formatted tree through the scratch launcher (§9):
  **2469 passed, 11 skipped, 3 failed** (204 s). The 3 failures are exactly the three named Phase-26 baseline failures
  (§9): `test_e2e_run.py::RunTopologyGuardTests::…unscored_smoke_run…`, `test_hierarchy_contract.py::RealPinsTests::…generated_pin_candidate…`,
  and `test_hierarchy_e2e.py::MainOrderingTests::…preflight_only…`. Their causes are unchanged: the loopback-refusal flake
  (now produced by the shim) and the pin-drift `rc=3` rejection (`AssertionError: 3 != 0`). **No new failure.**
- Count reconciliation against the Phase-26 baseline (2402 passed, 11 skipped, 3 failed): +67 passed, which is the 71 new
  Phase-27 tests minus the 4 tests in the deliberately ignored `contract_directed/test_live_command.py` (§9).
- ruff (Phase-27 files only, scoped per the shared-tree rule): `ruff check` and `ruff format --check` pass on every
  Phase-27 file, including `topology.py` after the one-line formatting-only fix recorded in §9.

## 11. Phase 28 readiness and hand-back

- **Phase 27 offline implementation:** complete, subject to the regression result in §10.
- **Phase 28 readiness:** **FALSE.** Blocked on the upstream `empty_result_semantically_allowed` consumption fix (§4,
  disposition B), which needs its own approval. Also needs a decision on §8.1 (the c12 wrong target reaching the answer
  as grounded) and §8.2 (item #29) before a live parent answer is presented as trustworthy.
- **Next step, requiring explicit authorization:** a Phase-28 live parent-synthesis run. Nothing in Phase 27 runs a model,
  and this document does not authorize one.
