# Phase 34 / I2-3 — Scientific answer presentation and disclosure

## Starting checkpoint and scope

Started from clean HEAD `cd68d1701e8a069a11b02af42cf582b1ddf12ce7` on
`experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`, in the canonical
`.claude/worktrees/ask-060-hier11-recpm3-citefix-20260929T212442Z` worktree.
The accepted E2 promotion remains closed. This increment changes downstream presentation
for current reviewed Ask; scientific v8, parent-claim-v2, parent-synthesis-v2 and plan-v5
retain their versions and scientific meanings.

Authority for the implementation was the actual projection, presentation, synthesis,
plan, rendering and fresh invocation code, informed by the accepted I4-4A/I4-4B coverage
and reporting contracts, I4-4C substrate, I4-4D2 consumers, I4-4E/E1B/E2 reports and
contribution lineage. No new scholarly method or external tool is introduced.

## Observed gaps and available evidence

| Existing boundary | Observed behavior before I2-3 | Smallest correction |
|---|---|---|
| Projection/value coverage | Retains category polarity independently of scientific goal satisfaction; candidate provenance, exclusions, attachment uncertainty and aligned summaries remain available | Read those records; do not classify or change them |
| Presentation and parent synthesis | Finalizes authorized quotations and transports each member's receipt, source and citation; restricted values remain inspectable | Keep these consumers unchanged |
| Plan-v5 | Computes report state, category axes, relation establishment and scientific goal state; does not explain important differences | Add reference-bearing facet disclosures for fresh invocations |
| Render-v5 | Renders authorized text/citations and only two generic limitations; an answered null category gets no positive-goal qualification; partial relations and conflicting observations can go unexplained | Render the stored qualifications and limitations in the selected answer |
| Fresh handoff | Authenticates recovery/search snapshots but does not pass them to the planner | Transport the already bound snapshots; do not reconstruct search completion |
| Supporting evidence/audit | Existing value coverage, claim receipts, relation units, synthesis items, projection references and invocation records carry the detail | Reuse these structures rather than introducing a new hierarchy or UI |

The metadata needed for the bounded disclosures is sufficient. No scientific inference,
new retrieval, authority adjudication, evidence ranking or policy evaluation is required.
Reporting coverage never closes recovery. A missing search record never certifies that
the search completed or found nothing.

## Implementation and interfaces

- `answer_plan/disclosure_v5.py` is a pure presentation helper over validated records.
  It follows each existing value coverage path to its own support view and candidate
  metadata. It reads polarity, goal state, display state, exclusion facts, attachment
  uncertainty, authored quantifier, relation-unit display state and stored observation
  summaries. It neither chooses a new support nor recomputes a scientific conclusion.
- `fresh_layerc.py` and `layerc_pipeline.py` transport the invocation's existing `recovery`
  and `search` snapshots through keyword arguments to plan-v5.
- `answer_plan/plan_v5.py` verifies those snapshots against the trusted invocation's
  existing hashes, appends facet `disclosures`, and carries `disclosure_context` and
  per-coverage-path `source_qualifications`. Existing report/scientific states remain
  unchanged. The existing plan hash and output manifest bind the additional presentation
  material; no authorization, schema version or scientific identity changes.
- `answer_plan/render_v5.py` displays qualifications beside the authorized statement and
  limitations beneath the authored reporting node. Quotation text and member-specific
  receipt/citation associations remain intact. Identical fresh limitation prose is
  shown once per node, while all scoped records remain inspectable.
- `test_i2_3_disclosure.py` adds the presentation matrix, public selected-answer checks
  and a detached p8/p36 disclosure probe. `test_reviewed_fresh.py` extends the existing
  offline worker-boundary harness for reviewed category inputs, empty evidence and
  explicit recovery reason codes. `test_profile_b_static.py` and `test_layerc_static.py`
  explicitly enroll the pure helper in the closed consumer import/call checks.
  `test_sufficiency_support_schema.py` narrowly exempts the literal stored receipt key
  `support_policy_evaluation` from its older I4-1g substring ban in this helper alone;
  authored `support_policy`, policy APIs and raw candidate APIs remain forbidden.

The persisted historical profile-B branch retains its original plan and rendering.
Fresh invocation authority activates the added presentation metadata. This preserves
exact D2 reproduction without disabling the correction for the actual current public
route. Detached matrix probes do not mint or impersonate trusted fresh invocation
authority, and do not rewrite or reauthorize historical artifacts.

Display warnings apply to an established value lacking an authorized display path;
an alternative authorized path for the same value avoids redundant warnings. Stored
relationship establishment and joint display remain distinct. A witnessed relationship
without an authorized joint quotation gets a display limitation, not a claim of absence.
Open-list examples do not acquire a claim of exhaustive reporting.

Attribution wording comes from selected candidate metadata, never from a representative
candidate or a new reading of the sentence. Attributed and synthetic supports remain
legitimate. Legacy paths without ownership metadata acquire no invented ownership label.
Excluded and ambiguous candidates can explain unresolved reporting but cannot supply
positive quotations or citations. Attachment and exclusion facts remain orthogonal.

## Before/after examples

Ordinary atomic answer, unchanged:

> 1. What was found about alpha?
> We found alpha increased. [1]

Null reporting previously displayed only the authorized null quotation. The current
public answer adds the distinction already present in its category records:

> 1. What was found about alpha?
> alpha was not significant. [1]
> The null finding can answer what was found; it does not establish the positive finding sought.
> Recovery has not completed the scoped search for this obligation.

Its search qualification is also displayed from the bound run records; the pending
positive-goal recovery targets remain unchanged. An answered report is still not a
positive scientific finding.

For an incomplete recovery attempt the selected answer says:

> Recovery was attempted, but the scoped search is incomplete.

For the existing certified empty-search outcome it says:

> The completed scoped search found no satisfying evidence; this does not establish absence beyond that search.

For independently supported operands without the required witness:

> The available evidence does not establish the requested relationship; separately supported findings do not suffice.

An attributed selected path adds “The source reports prior evidence:” to its authorized
statement. Synthesis paths receive synthesis wording, including unresolved-ownership
synthesis; they are not rejected or silently described as direct current-study findings.
An established but undisplayable value gets a presentation limitation. Stored conflicting
direction observations get an explicit conflict qualification without a new consensus.

## Qualification matrix

Every detached case compares the entire scientific input before/after, all claims,
receipts, relation units, finalized value coverage and parent synthesis against the
unchanged baseline consumers. Existing plan states are compared exactly after removing
only the added disclosures. Rendered citation records remain equal; every displayed
member retains its authorized value/source receipt. Tests inspect actual rendered text.

| Required case | Evidence and result |
|---|---|
| 1. Atomic positive | Generic real-v8 fixture and public route; ordinary quotation/citation unchanged |
| 2. Relational positive | Public current route; aligned relation and citations retained |
| 3. Null answers reporting | Category report remains answered and the null quotation stays null |
| 4. Null does not establish positive goal | Goal remains incomplete, recovery stays open; displayed qualification added; preserved p8/p36 covered |
| 5. Established but display limited | Scientific establishment retained; no unauthorized quotation/citation or false absence claim |
| 6. Incomplete recovery | Actual public structured recovery produces incomplete-search wording |
| 7. Completed scoped empty search | Actual public structured terminal status produces bounded empty-search wording, never universal absence |
| 8. Attributed/indirect | Own selected candidate metadata controls prior-work/synthesis wording; no global suppression |
| 9. Incompatible operands | No relation is created; missing relationship explicitly disclosed |
| 10. Nonrepresentative P2 witness | Relationship statement uses P2 members; separate P1 support cannot donate a relational citation |
| 11. Direction conflict | Stored aligned conflict disclosed; positive and negative authorized observations retain their sources |
| 12. Mixed answer | Established Alpha, null Beta and unresolved Gamma retain separate category axes; partial reporting stays partial |
| 13. Ordinary readability | Actual public atomic/relational answers remain two lines, without extra boilerplate |

Additional checks cover absent search status, unattempted recovery, all four ownership/
synthesis combinations, guard/policy/combined exclusions, independently attachment-ambiguous
and excluded candidates, and avoiding a display warning when another authorized path exists.

## Scientific and historical protection

Only plan/render presentation and their bounded context handoff change. No modifications
to projection validation, scientific mapping, role bindings, category satisfaction,
witness selection, observation algorithms, claim construction, quotation authorization,
parent synthesis, producer registration or the installed issuer are part of this change.

Public atomic and relational controls compare the entire scientific map against E1B/E2
and all scientific Layer C components plus invocation provenance against the preserved
E2 outputs. Those comparisons also require the ordinary rendered answer to remain exact.
New current plan/manifest hashes are expected because the fresh presentation metadata
is now included. They are not historical hash updates.

The atomic map remains `b3930349c64ca8308157c4685b557fd12f4a888b46c4bb196c0319071e783be4`;
the relational map remains `d3276cd074eb12e0bfb8d5d9894e628ef81452cfe364983d4894fe588822b365`.
The current output combined hashes are respectively
`5d0d4dab335cbb0552d6c1c2ad5bbb3fb44e8a39f04b90a1080d89542abeacd8` and
`02b69d26b6690ce51762ace0d3a63297ad164add24eb93f7b37075d3ee98fe1d`.
The complete scientific components, invocation provenance and ordinary render compare
equal to E2, not merely their summarized states.

Protected historical combined hashes:

| Artifact | SHA-256 |
|---|---|
| v4 | `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a` |
| v5 | `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77` |
| v6 | `dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be` |
| v7 | `04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72` |
| v8 profile A | `1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0` |
| D2 profile B | `e697596b8fb3dd3ce426cdc1b82909ca93f4bbc3346e46b74bf2f96f980eafde` |

D1 profile, receipt, verified authorization, registry identity and all 26 installed
producer source fingerprints remain protected by the existing exact reproduction tests.
Recorded historical v8 remains supported_noncurrent; fresh reviewed Ask remains current/v8
with parent-claim-v2, parent-synthesis-v2 and `answer-plan-step2-v5`.

The unchanged D1 identities are:

- Profile: `qualified-producer-profile-v1:sha256:0c739b235dd983b77f3f9adfca22bebea90255f0f51f57f45cd7e699ef0bd2cd`.
- Receipt: `producer-output-receipt-v1:sha256:a040ad7757ee792e9c0a7f0414bead5ce22ed5eb5d19e1bdc37931b4f0d4071d`.
- Verified authorization: `verified-producer-authorization-v1:sha256:aa9ccbfa94f100a4c8cc0cbe85f60f27eebb289528e0f280447f0fcd23bb04b2`.
- Registry: `producer-authorization-registry-v1:sha256:3ca420b42e64046470738773b2affad9509ffbab4f0b0df166963fcc0308d0ef`.

## Regression evidence

Final targeted qualification: **471 passed in 166.61s**. This includes all historical
hash/identity/source-pin protections, the 27 disclosure cases and three local public
output inspections. Optional psutil qualification: **7 passed in 14.01s**. Independent
known-failure rerun: **exactly 5 failures in 19.53s**, with the same causes as E2.
Logs and XML are retained under `.local/i2-3`.

Final full offline qualification: **5,496 passed, exactly 5 known failures, 12 skipped,
9 xfailed and 276 passing subtests in 308.43s**. The XML failure inventory compares
exactly equal to the independently rerun known-five inventory. **Zero unexplained new
failures.** The final schema/consumer-boundary rerun also passed **74 tests in 16.08s**.
These are actual I2-3 results, not carried-forward E2 counts.

An initial targeted run caught the missing explicit enrollment of the new pure helper
in the Layer C consumer import allowlist. The narrow enrollment was added; the consumer
boundary/disclosure rerun passed all 53 checks, followed by the successful 471-test final
targeted run. No scientific boundary was relaxed. The superseded full run was stopped
and a full run started on the corrected tree. That run found an additional stale
I4-1g substring ban on reading the stored `support_policy_evaluation` receipt. Its narrow
literal-key exception preserves the ban on authored policy and evaluation APIs. Final
full qualification was rerun after that test correction. No historical expected text
was rewritten to accept a new output.

The offline runner is `.venv/Scripts/python.exe .local/i4-4c/run_offline.py`.
The full command uses `experiments -q --tb=short` and excludes only
`experiments/ask_cli_revised/contract_directed/tools/test_run_gate_integration_live.py`.
That mocked optional module runs separately with the existing Anaconda Python providing
psutil. Targeted paths are the E2 suite, the new disclosure matrix and
`.local/i2-3/test_inspection.py`. Final JUnit paths are `matrix.xml`, `targeted-final.xml`, `full-qualified.xml`,
`optional.xml` and `known-five.xml` under `.local/i2-3`.

Known E2 failures are independently rerun, rather than silently excluded:

1. `ask_070/tests/test_corpus_and_referents.py::test_dev_eval_separation`: absent frozen
   `dev_inputs_v0.json`.
2. `ask_070/tests/test_schema_validation.py::test_real_frozen_nonsemantic_artifact_schemas`:
   absent frozen `corpus_presence_v0.json`.
3. `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`:
   offline Ollama tags probe is denied.
4. `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`:
   pre-existing `hierarchy_contract.py` pin drift.
5. `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`:
   the same pin drift returns code 3.

## Limits and disposition

This qualification uses preserved evidence and offline worker-boundary fixtures, not a
live scientific E2E run. It does not claim unattended question authoring or application
integration. It reports existing scientific decisions faithfully; it does not remedy
upstream limitations or infer ownership when upstream ownership metadata is absent.
Historical rendering deliberately remains frozen for exact reproduction.

No external search, live retrieval, model/NLI calls, frontend or `/summarize` changes,
new semantics/plan version, or live E2E qualification occurred. Stop after the bounded
increment; fresh live adversarial qualification requires separate authorization.

All final code hooks pass except the unchanged frontend 615-line cap:
whitespace/EOF, merge-conflict/large-file checks, Ruff format/lint, Bandit and Tach pass.
The initial mixed line endings in the static-test edit were normalized and rechecked.
Frontend worktree and starting-HEAD blobs both equal
`03f9d3dfee3763533a78d5da601a99cb81bb37f1`; no application/frontend file is staged.
The user's narrowly authorized `--no-verify` exception therefore applies to this single
bounded commit after all substantive gates passed. No semantic, source-pin, authority,
historical-output or qualification check is bypassed. Code hook evidence is
`.local/i2-3/hooks-verified.log`; the final documentation check is `hooks-docs.log`.

**I2-3 COMPLETE - READY FOR LIVE E2E QUALIFICATION.** The current selected answer now
discloses existing scientific and reporting distinctions, with no scientific behavior
change. The full commit hash and push/worktree state are reported in delivery and resolve
from the commit containing this report. Stop here; do not begin live E2E or product integration.
