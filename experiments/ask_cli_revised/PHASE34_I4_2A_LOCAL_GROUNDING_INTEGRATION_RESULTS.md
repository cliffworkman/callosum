# Phase 34 / I4-2a local-grounding integration — READY FOR REVIEW

2026-10-08. **I4-2a implementation gates passed; READY FOR REVIEW, acceptance recommended.** The
coordinate regression and missed test migrations are repaired. Explicit v4 parity and all locked v5 real
outcomes pass. The full offline experiments gate has zero new failures; the exact five pre-existing/environment
failures are independently reconfirmed below. Both historical stops remain documented. I4-2b was not begun.

## Continuation provenance and stop/resume

Started from `ee09b491ad57353d975b6e3e578e653efae470fd` on
`experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`, plus Claude's five uncommitted files.
Cody first read the entire partial diff and stopped without editing: the helper conflated unavailable
and multiple dependencies with genuine target-free roles. Cliff then supplied the explicit decision:
only no-dependency is target-free; unavailable, ambiguous, and multiple dependencies fail closed.
Implementation resumed only after that decision. No reset, checkout, stash, history rewrite, model call,
retrieval, or live E2E run occurred. Original partial files and diff are preserved locally in
`.local/i4-2a/claude-original/` and `claude-original.diff`.

Claude's exact original modified files:

- `experiments/ask_cli_revised/direction_target.py`
- `experiments/ask_cli_revised/relation_witness.py`
- `experiments/ask_cli_revised/sufficiency_engine.py`
- `experiments/ask_cli_revised/sufficiency_mapping.py`
- `experiments/ask_cli_revised/test_sufficiency_semantics_version.py`

Cody subsequently changed/created these files (the two unchanged Claude direction/witness edits remain part
of the combined increment):

- `experiments/ask_cli_revised/e2e.py`
- `experiments/ask_cli_revised/sufficiency_diagnostic.py`
- `experiments/ask_cli_revised/sufficiency_engine.py`
- `experiments/ask_cli_revised/sufficiency_mapping.py`
- `experiments/ask_cli_revised/sufficiency_recovery_targets.py`
- `experiments/ask_cli_revised/test_achieved_outcome_span.py`
- `experiments/ask_cli_revised/test_assertion_authority.py`
- `experiments/ask_cli_revised/test_assertion_authority_i4_1b.py`
- `experiments/ask_cli_revised/test_assertion_authority_i4_1c.py`
- `experiments/ask_cli_revised/test_assertion_authority_i4_1f.py`
- `experiments/ask_cli_revised/test_i4_1j_local_grounding.py`
- `experiments/ask_cli_revised/test_sufficiency_support_schema.py`
- `experiments/ask_cli_revised/test_sufficiency_v4_category_satisfaction.py`
- `experiments/ask_cli_revised/test_i4_2a_local_grounding.py`
- `experiments/ask_cli_revised/test_i4_2a_replay.py`
- `experiments/ask_cli_revised/phase34_i4_2a_replay_results.json`
- `experiments/ask_cli_revised/PHASE34_I4_2A_LOCAL_GROUNDING_INTEGRATION_RESULTS.md`
- `experiments/ask_cli_revised/CONTRIBUTION-LINEAGE.md`

## Historical second stop: blocking regression and remaining gates

At the second stop, `_bind_achieved_outcome_v5` validated multi-id quote equality before finding result hits. That placement
is too early: existing hierarchy integration fixtures pool `QUOTE 11`, `QUOTE 12`, and `QUOTE 13` into one
unit because `overview_evidence._dedupe_key` uses normalized word tokens, not byte identity. These units
have **zero result-predicate hits**, hence no candidate support or spans to anchor, but the new guard raises
`ValueError: plural proposition spans require byte-identical sealed passages` anyway.

Concrete reproduction: `test_hierarchy_e2e.py::SufficiencyIntegrationTests::
test_execute_reaches_sufficiency_mapping_with_zero_model_assistance` passes using the saved HEAD production
modules and fails using the current worktree. Captured unit: ids `[p3,p1,p2]`, representative `QUOTE 11`,
sealed quotes `{p3: QUOTE 13, p1: QUOTE 11, p2: QUOTE 12}`, raw hits `0`. Logs:
`.local/i4-2a/coordinate-head.log` and `coordinate-current.log`.

This is Cody's newly introduced integration regression, not a pre-existing failure. **No fix was applied
after identifying it**, honoring the stop instruction. Candidate-coordinate checking needs to be limited
to actual candidate construction, without allowing spans across unequal quotes. Any genuinely grounded,
relevant multi-id candidate whose sealed texts differ must still fail closed; no offset conversion or
unit-splitting semantics have been authorized or implemented.

Two additional unfinished test migrations were identified: I4-1f's independent static guard still forbids
the authorized mapper seam, and a semantic-threading test still uses v5 as its unsupported future version.
These are recorded, not silently bypassed. The scratch offline guard also collided with two test-owned
network guards; the full-suite environment lacks `psutil`. All must be accounted for before acceptance.

## Implemented v5 contract

- Current identity is `sufficiency-semantics-v5`; v1–v4 remain readable through explicit historical paths.
- Only deterministic `achieved_outcome_predicate` mapping changes. Existing disqualifying guards run before
  localization, unchanged. No predicate vocabulary widening or evidence-type exclusion is introduced.
- Raw result hits join through the existing containing-assertion API; unresolved joins produce no candidate.
  Dedupe identity is `(span_proposition_id, assertion_span)`, across the collection, so equal numeric offsets
  in different propositions do not collapse. The first raw hit retains predicate/content provenance.
- `resolve_target_dependency` returns `target_free`, `ready`, `unavailable`, or `ambiguous`, with reason,
  role, target text, and proposition scope. The binder handles each status explicitly, with no fallthrough.
- Other required roles and required alternative groups are dependency slots. More than one slot fails closed.
  For a single alternative group, exactly one filled member may supply the target; zero is unavailable and
  multiple filled members are ambiguous. Optional roles add no dependency. A group containing the evidence
  role itself is satisfied by that evidence role and imposes no additional sibling dependency.
- A unique dependency must be filled, have nonblank exact_text, and have a nonempty support set. Missing
  completion context itself is unavailable. No role or child names are interpreted by production code.
- The existing mapper passes the current fork's already-bound roles and the requirement's role_completion.
  Required sibling mapping order remains the authored order. No two-pass mapper or new nomination is added.
- Scope is the sibling's existing relationship support set (singular compatibility id union existing plural
  provenance). Assertions are scoped by actual unit provenance before lexical matching. The matcher remains
  ignorant of why scope exists. Target matching retains every match in discovery order.
- Every grounded/relevant assertion remains in `candidate_supports`; only the first projects to legacy
  `RoleBinding.proposition_id/exact_text`. There is no ranking or new instance fork for multiple assertions.
- `candidate_support.exact_text` and legacy `exact_text` are the full **local assertion region**, including its
  subject; `content_span` is the tighter localization. Neither is the original multi-assertion passage.
  Offsets refer to the sealed quote, not the shortened exact_text. The join may accept partial intersection,
  and punctuation can make content_span extend a character beyond the assertion span.
- `admissible=None` and `inadmissibility_reason=None` mean policy has not evaluated the candidate. True/False
  remain explicit future evaluation states. Boolean integers/strings are rejected. No support policy or
  reference-future policy helper is consumed.
- `same_local_assertion` stays unregistered and unauthored. PLAN_VERSION stays `answer-plan-step2-v4`.
  Assertion-authority RULESET_VERSION stays `i4-1f.0`.

## Provenance and offset identity

Removed the partial binder's `sorted(proposition_ids)` and the set-iteration ordering of matched candidates.
Candidate provenance copies the input unit's deterministic order. Existing `units_by_child` prioritizes that
child's responsive ids while preserving order within each partition; this existing order is inherited,
not replaced with lexical order. Historical model-nomination and direction sorting are separate pre-existing
contracts and were not changed.

The unit constructor actually groups normalized words, so byte identity is not guaranteed by grouping alone.
The diagnostic unit view now supplies exact sealed `proposition_passages`; the v5 binder checks equality.
The equality check now runs only after raw hits exist and before assertion joining. Duplicate provenance ids are rejected,
not silently removed or reordered.

Every multi-id unit in preserved Attempt2 was independently checked byte-for-byte. All ten physical
multi-id units pass. The cited duplicate-passage group is actually `[p1,p4,p8,p12,p24]`; p12 also shares it.
Its raw hit crosses two assertions and fails the join, so it emits no candidate. Real emitted plural
supports include c1 `[p2,p11]`, c4 `[p11,p2]`, and c3 `[p7,p3,p14,p17,p26]`. Their first id is an
**offset coordinate anchor only**, not a sole semantic source. The plural list is authoritative provenance.
The annex contains every child-view order and quote hash, and every emitted candidate's spans.

## Version-threading audit

| Site | Decision and evidence |
|---|---|
| sufficiency_engine.py constants/identity | v5 current, v4 historical, supported set explicit; no future-version catch-all |
| recompute_instance / recompute_requirement | Explicit v4/v5 category goal gate; all other recompute rules unchanged |
| sufficiency_mapping.py role dispatch | Own v5 achieved-outcome branch; historical v1–v4 whole-passage branch unchanged |
| cardinality category mapping and rejection outside cardinality | Explicit v4/v5 category rule, unchanged |
| direction observation dispatch | Explicit v1/v2 historical path and v3/v4/v5 target-aware path; unknown versions refused |
| sufficiency_recovery_targets.py | Both category semantic-goal targets and initial-plus-raw-final obligations explicitly inherit v4 in v5 |
| e2e.py | Raw-final recovery target computation explicitly accepts v4/v5; production calls already pass current constant |
| relation_witness.py | Explicit v5 table entry reuses v4 case-insensitive referent containment |
| direction_target.py | Explicit v5 table entry reuses v4's disabled single-operand fallback |
| sufficiency_diagnostic.py | Version passed through; mismatched map identity still rejected; exact quote metadata added for coordinate checking |
| sufficiency_model_scope.py | No hardcoded semantic-version branch; request fingerprints/authorization/receipt behavior unchanged |
| effectiveness | Existing function is version-independent; no new policy; only changed grounding changes available evidence |
| sufficiency_identity.py | Current/historical validation derives from explicit engine sets; absent identity is never inferred current |
| answer_plan/replay.py | Explicit historical-version acceptance and authorization binding retained; unversioned compatibility explicitly applies contemporary rules, not attributed to old map |
| answer_plan/plan.py, relations.py, classify.py | Pass selected containment/direction versions to shared explicit dispatch tables; no source changes or PLAN_VERSION bump |
| remaining answer_plan/* | No independent sufficiency-version routing; no candidate-support consumption |
| parent_synthesis_ledger.py / parent synthesis | Consume recomputed bindings/observations; no independent version switch, no implementation changes |
| production diagnostic/recovery drivers | Existing explicit current-constant arguments suffice; semantic-threading static checks retained |
| sufficiency_phase2_replay.py | Historical recorded replay remains pinned to v3; do not add v5 |
| parent_synthesis_test_support.py | Historical fixture construction remains pinned to v3 |
| contract freeze / pin / preflight diagnostics | No v4-only semantic allow-list; authored contracts and pin files unchanged; known hierarchy pin drift not repaired |
| semantic-threading tests | v1–v5 explicitly accepted; synthetic v999 rejected; the stale negative v5 assertion is repaired |

No other production version-routing sites were found by repository searches for version constants, literals,
comparisons, dispatch tables, and allowed-version sets. Final gate results are recorded below.

## Static guard migration

The classifier and result-localizer repository scans allow only the exact
`experiments/ask_cli_revised/sufficiency_mapping.py` production path. The I4-1j guard now scans all production
subtrees rather than a short file list. New tests prove a second consumer, even a different file also named
`sufficiency_mapping.py`, is rejected. Mapper API usage is limited to predicate localization, assertion join,
relation/support-label annotation, and target matching. Support-schema guards allow only candidate collection
names at that seam; support_policy and future evaluation helpers remain forbidden. AnswerPlan remains outside
the allow list. The separate I4-1f guard, missed at the second stop, now allows the same exact mapper path.
Its new negative test proves that `app/sufficiency_mapping.py` remains forbidden even though its basename matches.

## Historical replay preservation

Before consumption, all three recovered artifact hashes were checked:

- `11_verified_ledger.json`: `a70409e8f5a0937f414c73c4796b293c6c1a9ef3b31c7fc83bbfa61794c6bd5d`
- `17_sufficiency_map.initial.json`: `46a213044bc6211702fa89710268e1bfb6c4fc348259727a46cb238ef5bbc14e`
- `17_sufficiency_map.json`: `28478500e485137cd6930b8010d274bb1da3afd48e7f4a6208dd183610d9ca0b`

The replay harness holds recorded model-role bindings fixed by `(child, requirement, role, request_context)`;
it does not call a model or create new nominations. It runs the production diagnostic mapper, forking,
normal recomputation, witness attachment, direction/effectiveness annotation, recovery projection, ParentClaim
construction, AnswerPlan assembly, rendering, and invariant checks. All 26 achieved-outcome role instances
match the preserved map exactly under v4: **15 filled, eight distinct historical proposition ids**, with
whole-passage exact_text and historical c2/c4/c8 states retained.

The same harness ran against isolated production modules read from committed HEAD and against the working
implementation under explicit v4. The serialized combined map/targets/claims/plan/render/diagnostics artifact
is byte-identical. Both SHA-256 values are
`4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a`.
Thus the AnswerPlan object and rendering are byte-identical for the same explicit v4 input. This is not a
claim that a v4 map's current-vs-historical authorization label stays current after the version bump.

Reproduce (from the canonical worktree, `.venv/Scripts/python.exe`):

```
-m experiments.ask_cli_revised.test_i4_2a_replay --version v4 --out .local/i4-2a/current-v4.json
-m experiments.ask_cli_revised.test_i4_2a_replay --version v5 --out .local/i4-2a/current-v5.json
```

The `--baseline` option prepends the saved HEAD module directory under `.local/i4-2a/baseline`;
those files were extracted with git show, without changing the worktree or the original partial edits.

## Real v4 → v5 results

The complete machine-readable annex is [phase34_i4_2a_replay_results.json](phase34_i4_2a_replay_results.json).
For **every** achieved-outcome instance it includes v4 and v5 state, proposition identity, exact_text,
compatibility binding, completion/requirement state, all candidates with plural identity and all spans,
relation/aggregation/kind/label, target source/value/scope/status, counts, and an explanation. It also includes
full recovery additions/removals, changed target payloads, ParentClaims, node states, rendered statements,
and per-call diagnostics. It is a report snapshot, not runtime input or a refreshed contract pin.

| Child | Concrete change |
|---|---|
| c1 | Unique filled alternative `brain_region_or_network` targets “the specific amygdala response”. Generic p1 becomes local p2/p11 evidence, anchor p2 in c1's input order. Instance and requirement partially_filled → filled. |
| c2 | All three historically used p4. p35 and p46 instances now missing evidence; p47 gets its own local assertion and becomes complete. Requirement partially_filled → filled under exists. |
| c3 | True target-free control survives. Historical p8 raw hit intersects two assertions and fails closed; next grounded assertion comes from p7/p3/p14/p17/p26, anchor p7. Remains filled/complete. Category requirement unchanged. |
| c4 | Instance 1 stays on p11 with local region and plural p11/p2 support. Instance 2 corrects p11 → p40, becomes complete; p40 relation is unresolved and retained. Requirement remains filled. |
| c8 | Five p41-bound instances stay filled. Attractiveness/trustworthiness → [43,200]; anger/dominance/threateningness → [208,372]. Four p20-bound instances were already missing and remain so; two empty partitions also remain missing. |
| c10 | Both evidence roles remain missing. Existing hedged guard excludes p29/p53; p21 has no recognized result predicate. |
| c12 | Three previously filled evidence roles (p24/p30/p31) become missing; all six instances now missing. Requirement partially_filled → missing after normal recompute. Authorized grounding correction, not policy gating. |

Overall: **15 → 10 filled achieved-outcome roles**; five newly missing roles (two c2, three c12), no revival
of previously missing evidence. No provenance/directness category causes a rejection. c1/c4 unresolved
supports remain filled, and p41's unresolved second assertion remains on three c8 bindings.

## Diagnostics

Counts below are summed across the 26 production role-instance binding calls, including repeated examination
of the same units for different forks. Eligible units means caller-offered units before existing guards;
target-scoped/matched/unmatched counters apply only to ready dependencies, not target-free roles.

- `candidate_supports_emitted`: 10
- `eligible_units`: 75
- `guard_excluded_units`: 21
- `join_failures`: 6
- `locally_grounded_assertions`: 28
- `missing_no_grounded_relevant_support`: 16
- `previously_filled_roles_becoming_missing`: 5
- `raw_hits_deduplicated`: 8
- `raw_result_predicate_hits`: 42
- `successful_assertion_joins`: 36
- `target_matches`: 9
- `target_scoped_assertions`: 14
- `target_unmatched`: 5

No diagnostic value controls state. The replay checks that calling with and without diagnostics returns the
same binding. p41 independently proves three raw hits → three successful joins → two assertion supports;
per-instance target matching then retains the correct one.

## Downstream exposure (rules unchanged)

Normal same_proposition recomputation makes c1, c2's p47 instance, and c4's second instance complete. Existing
content-derived keys change wherever evidence text/identity changes. c5/c6 each grow from two to four paired
instances because both c4 parents now qualify. c9 remains five instances but follows the changed c8 parent
keys. The held-fixed replay retains recorded model-dependency origin keys as historical nomination provenance;
those keys are not rewritten to claim a new nomination occurred.

Recovery: **40 → 48 raw targets; 19 removed, 27 added, 21 identities retained**. One retained target changes
its payload: historical c4-origin corroboration is now triggered through descendants and loses c4 from its
affected-descendants list. c12 replaces six partial-role targets with nine missing-role targets across the
three newly empty instances. c1/c2 replace relationship-unverified work with existing provisional-corroboration
work where completeness is newly achieved. c4/c5/c6 expose additional corroboration obligations; c9's five
scale deficits simply receive new parent-derived keys. Existing exists-quantifier and model-dependence rules
explain why the two still-partial c2 instances do not cause independent missing-role searches once p47 is
complete. No recovery search was executed. Exact target records are in the annex.

Witnesses: c4 instance 2 now has p40; instance 1's plural witness set becomes p11/p2. c8 witnesses stay p41.
c5/c6 remain relation-unwitnessed even when completion is true; this existing distinction is preserved.
Direction: no new eligible relation sign or consensus. c5/c6 repeat their existing operand observations across
the additional parent instances, with all those observations still relation-ineligible. Effectiveness: c12's
three per-instance observations disappear as their evidence bindings disappear; its empty complete-instance
summary remains empty. No direction/effectiveness policy was redesigned.

ParentClaims: **20 → 17**. Newly complete c1/c2/c4 instances produce relational claims; generic evidence
claims change or disappear, and c12 loses its outcome category list. Full ledger records are in the annex.
No parent narrative/model pass was executed.

AnswerPlan consumes the new compatibility surfaces and identity without crashing, and existing renderer
invariants pass for both replays. Node 3 changes partial → answered after c3's local direct finding is available;
node 7 changes partial → not_established after c12's generic outcome bindings disappear. Other node statuses
stay unchanged, although disclosures and claim identities differ. **It is not yet candidate-aware**: it and
ParentClaims consume the singular projection, and AnswerPlan can revisit whole sealed sentences and apply its
own older attribution screen. For example, c4/p40 remains unresolved-but-relevant in the mapper while the
answer layer describes earlier work using its own passage screen. This is a known, explained semantic
mismatch to resolve in I4-4, not authorization to change AnswerPlan here. Multiple-candidate completeness,
plural provenance, assertion boundaries, and policy explanations all need explicit downstream handling.
I4-3 remains a planning question; no same_local_assertion registration was made.

## Historical verification at the second stop

- Focused grounding/schema/static/pure-primitive run: **269 passed, 9 xfailed**.
- Real I4-2a replay tests: **3 passed**.
- Additional engine/mapping/diagnostic triage: **180 passed, 2 subtests passed**.
- Full offline experiments suite (four workers, temporary socket-denial fixture): **3738 passed, 34 failed,
  12 skipped, 9 xfailed, 1 collection error, 276 subtests passed**. This includes the required sufficiency,
  recovery, witness, direction, effectiveness, parent synthesis, AnswerPlan, and I4 families; it is not accepted.
- Failure accounting: 25 coordinate-check integration regressions; one unmigrated I4-1f static guard;
  one stale future-version assertion; two scratch guard/test-guard conflicts; five failures in the previously
  reported baseline families; one missing-psutil collection error. The five baseline-family failures were
  not independently rerun byte-for-byte after this new-regression stop, so no gate waiver is claimed.
- Representative coordinate failure is independently demonstrated to pass with HEAD modules and fail here.
- Ruff initially found an unused test import and lambda style issue; both were corrected before the full run.
  Final formatting/lint verification has not been rerun following the stop. No hook was bypassed.
- Full logs, XML, and failure classification: `.local/i4-2a/full.log`, `full.xml`,
  `failure-classification.json`. Head/current replay JSON and focused logs remain alongside them.

Simple Ask received no implementation or global evidence-type policy. Review/descriptive evidence is not
globally invalidated. The matcher remains literal/case-insensitive with its existing dehyphenation fallback;
no synonym or model expansion was added. Multi-target grounding remains deliberately unspecified. Candidate
caption/structural context metadata currently follows the local classifier's default because the unit view
does not supply those inputs; there is no new caption filtering. Existing guard silent-discard asymmetry and
an explicit default support-policy function remain I4-2b concerns, not repaired here.

**Historical second-stop status: NOT READY for I4-2b planning.** At that point, resume had to repair and verify the premature
coordinate check, finish the two test migrations, reconcile the offline harness/environment, and rerun the
required gates. Only then may this combined Claude+Cody increment be committed and pushed as one commit.
At that stop the canonical working tree remained intentionally dirty, HEAD unchanged, with no commit or push.


## Coordinate-regression repair

Cliff explicitly resolved the second stop: guards → raw result localization → skip zero-hit units →
validate plural quote equality → join assertions → collect resolved records → emit candidate supports.
The previous equality check ran before localization and rejected the pooled fixture with ids `[p3,p1,p2]`,
representative `QUOTE 11`, and sealed quotes `{p3: QUOTE 13, p1: QUOTE 11, p2: QUOTE 12}` despite zero hits.
Zero hits create no span-bearing evidence or coordinate claim. The repaired binder therefore returns ordinary
no-match behavior. Once any hit exists, unequal or absent plural passage metadata still raises the existing
`ValueError` **before assertion joining**, with no candidate construction, splitting, filtering, or conversion.
Input provenance order is preserved; the first id is only the coordinate anchor. Single-id behavior is unchanged.

The exact hierarchy representative now passes (`coordinate-repaired.log`). Twelve coordinate-focused cases
pass, including the explicit A–E matrix across v4/v5: unequal/no hits, unequal/hits, identical/hits, single id,
and historical v4 isolation. A forbidden-join spy proves that rejected coordinates never enter assertion joining.
The independent I4-1f allow-list and its second-consumer negative test are repaired. The semantic-threading
acceptance test now includes v4 historical and v5 current, and rejects `sufficiency-semantics-v999`.

Post-repair HEAD-v4 and current-v4 SHA-256 both remain:
`4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a`.
The complete repaired v5 JSON equals the stopped-run v5 JSON, including map, targets, witnesses/direction/
effectiveness, ParentClaims, AnswerPlan, rendering, invariants, and diagnostics. Its SHA-256 is
`109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77`.
All real outcomes and the 15 → 10 evidence count above are preserved. The diagnostic totals were recomputed:
75 eligible, 21 guard-excluded, 42 raw hits, 36 successful joins, 6 failed joins, 8 duplicate hits, 28 grounded,
14 target-scoped, 9 matches, 5 unmatched, 10 supports, 16 missing, and 5 newly missing roles. No counter changed:
the real replay has byte-identical plural passages; only zero-hit synthetic fixture reachability changed.
The existing machine-readable annex therefore remains accurate without rewriting its semantic records.

## Environment and independently reconfirmed baseline

The normal declared toolchain is the worktree `.venv` (Python 3.12.7, pytest 9.1.1, xdist 3.8.0).
Two previous failures were scratch fixture collisions, not production failures:

- `experiments/ask_070/tests/test_offline_boundaries.py::test_guards_block_network_and_processes`
- `experiments/ask_adjudication_revision/tests/test_storage_cli_boundaries.py::test_offline_guard_blocks_network_subprocess_model_and_prohibited_archive_reads`

Both pass with their normal repository invocation (**2 passed**). The scratch socket-denial fixture now defers
to their autouse `deny_model_and_network` / `synthetic_offline_boundaries` guards. Those subtrees retain their
own stricter network/process/archive restrictions. Other tests remain under socket denial; no live call occurred.

The collection dependency was `contract_directed/tools/test_run_gate_integration_live.py`, importing `psutil`
through `run_gate_integration_live.py`. Despite its filename, all seven tests are offline: the runtime/client
are scripted and `endpoint_guard.refuse_all()` protects entry-point tests. `psutil` is absent from pyproject,
uv.lock, and both requirements manifests, so this is an undeclared optional experiment prerequisite, not a
missing declared project dependency. The existing Anaconda Python 3.12.7 environment already has psutil 5.9.0
and pytest 8.4.2: the module passes there (**7 passed**). No installation or production import change was made.
The full experiments gate is partitioned: declared `.venv` suite with this one module excluded from collection,
plus all seven tests in its existing dependency-complete environment.

Each of the following five tests was independently rerun against the saved committed-HEAD production modules
and the current implementation, under the same offline guard. Both runs fail in precisely the same five tests
and for the same causes (`known-head.log`, `known-current.log`), not merely the same total count:

| Exact test | Independently observed cause |
|---|---|
| `experiments/ask_070/tests/test_corpus_and_referents.py::test_dev_eval_separation` | Missing `frozen/dev_inputs_v0.json` |
| `experiments/ask_070/tests/test_schema_validation.py::test_real_frozen_nonsemantic_artifact_schemas` | Missing `frozen/corpus_presence_v0.json` |
| `experiments/ask_cli_revised/test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored` | Real Ollama `/api/tags` check occurs before the mocked runtime; denied offline with `httpx.ConnectError` |
| `experiments/ask_cli_revised/test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts` | Existing frozen code-input pin drift for `hierarchy_contract.py` |
| `experiments/ask_cli_revised/test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects` | Hierarchy preflight returns 3 rather than 0 from the same pin rejection |

The pin files, hierarchy_contract.py, and these five tests are unchanged by I4-2a. They remain disclosed baseline/
environment failures, not repaired or silently marked xfail. Baseline modules were loaded from saved `git show`
files in an isolated process; no checkout/reset/stash or working-file swap was used.


## Reproduction commands

Run from the canonical worktree; no live services are needed. The scratch baseline directory contains
byte-for-byte verified `git show ee09b491:experiments/ask_cli_revised/<module>` copies of all seven changed
production modules, listed with SHA-256 in `.local/i4-2a/baseline-module-hashes.json`.

```powershell
& .venv/Scripts/python.exe -m experiments.ask_cli_revised.test_i4_2a_replay --baseline --version v4 --out .local/i4-2a/head-v4-repaired.json
& .venv/Scripts/python.exe -m experiments.ask_cli_revised.test_i4_2a_replay --version v4 --out .local/i4-2a/current-v4-repaired.json
& .venv/Scripts/python.exe -m experiments.ask_cli_revised.test_i4_2a_replay --version v5 --out .local/i4-2a/current-v5-repaired.json
$env:PYTHONPATH = (Join-Path (Get-Location) '.local/i4-2a')
& .venv/Scripts/python.exe -m pytest experiments/ -n 4 -p i4_offline --ignore=experiments/ask_cli_revised/contract_directed/tools/test_run_gate_integration_live.py -q --tb=short --junitxml=.local/i4-2a/full-repaired.xml
& C:/Users/cliff/anaconda3/python.exe -m pytest experiments/ask_cli_revised/contract_directed/tools/test_run_gate_integration_live.py -q --tb=short
```

The local `i4_offline` plugin denies socket connect/connect_ex/create_connection with ConnectionRefusedError;
it yields guard ownership to the two named subtree autouse fixtures above. It is a test harness only, not
production code or a test-outcome exemption. The five baseline failures remain visible in the full run.
The optional module's separate invocation uses its own endpoint guard. No dependency paths are injected
into the declared project environment and no permanent environment files were changed.


## Final verification and acceptance recommendation

| Gate | Final result |
|---|---|
| Exact hierarchy coordinate representative | 1 passed, before larger suites |
| Coordinate regression matrix and existing coordinate tests | 12 passed |
| Focused I4-1 through I4-1j, I4-2a, schema, versions/threading, engine/mapping/hierarchy/static | 1371 passed, 9 xfailed, 85 subtests passed; only the two independently confirmed hierarchy baseline failures |
| Full declared-environment experiments suite | 3776 passed, 5 known failures, 12 skipped, 9 xfailed, 276 subtests passed; 0 collection errors; 173.29 seconds |
| Optional psutil-dependent offline module, existing Anaconda environment | 7 passed |
| Combined full experiments coverage across the two environments | **3783 passed, 5 known failures, 12 skipped, 9 xfailed, 276 subtests passed; zero new failures, zero unresolved collection errors** |
| Normal invocations of the two previously colliding guard tests | 2 passed; also pass in final full suite |
| Explicit v4 combined replay, saved HEAD and current | Both match required `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a` |
| Real v5 semantic, diagnostic, downstream output | Entire replay identical to pre-repair v5; 15 historical → 10 current filled achieved-outcome roles |
| Formatter and lint | All 19 touched Python files formatted with repository-pinned Ruff 0.9.6; ruff check passes |
| Repository security / module boundaries | Bandit and Tach pass; local security review recorded in `.claude/security-audits/2026-10-08_ask-i4-2a-local-grounding.md` |

The XML failure identities were checked against the exact five-node set, and there are no `<error>` entries.
Compared with the stopped full run, all 25 coordinate failures, both migration failures, and both harness
collisions are gone. Eight coordinate matrix cases plus one I4-1f negative-guard parameter case add nine
new tests. Logs: `.local/i4-2a/focused-repaired.log` / `.xml`, `full-repaired.log` / `.xml`,
`optional-normal.log`, `final-failure-accounting.json`, and `baseline-provenance-and-preflight.log`.
No unexplained downstream change or unresolved I4-2a code failure remains. The optional environment issue
is classified and its tests actually executed, not waived.

**Recommendation: accept I4-2a after reviewer confirmation. READY for I4-2b planning once that acceptance
is recorded; this implementation stops here.** Remaining decisions belong to later increments: explicit
default support policy and guard discard/explanation treatment (I4-2b), whether/how to use same_local_assertion
(I4-3 planning), and candidate-aware ParentClaims/AnswerPlan consumption and attribution alignment (I4-4).
Multi-dependency grounding remains deliberately fail-closed. Caption/structural context limitations and the
five baseline/environment issues above remain disclosed. None is authorization to silently expand I4-2a.
No policy function, guard semantics change, verifier registration, AnswerPlan edit/version bump, I2-3 work,
or live retrieval/model/E2E work was performed.


## Commit-hook accounting

The normal commit attempt ran every applicable hook. Trailing whitespace, end-of-file, merge-conflict,
large-file, Ruff format/check, Bandit, and Tach passed. YAML/TOML had no staged inputs. The **sole failure**
was the pre-existing `app/frontend/js/20_synthesis.jsx` 615-line budget violation. `git diff HEAD` confirms
that frontend file is unchanged. The single combined I4-2a commit therefore uses Cliff's explicit,
this-commit-only `--no-verify` authorization. No replay, invariant, semantic-threading, static-guard, or
unexplained-regression check was bypassed. Hook output is preserved in `.local/i4-2a/commit-hooks.log`.
