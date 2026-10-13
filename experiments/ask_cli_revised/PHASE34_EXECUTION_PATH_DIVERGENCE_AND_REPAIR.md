# Phase 34 — Execution-path divergence: cause, repair and readiness

**Disposition: WIRING REPAIRED AND QUALIFIED OFFLINE. One input is still owed before an E2E: your review of
the q_aib reporting contract. One finding you should read before authorizing: on the evidence the October 12
run sealed, the integrated route's selected answer is close to empty.**

No E2E was run. No model was called. Models, prompts, thresholds and scientific semantics are unchanged.

## A. Root cause

**What happened, in order.**

1. **Oct 4, Phase 28.** `q_aib` ran end to end through `e2e.run_topology(..., hierarchy=True)`: the
   hierarchical route, with child syntheses and the parent claim ledger.
2. **Oct 4–10, Phases 29–34 (I4.x).** Answer planning, relation witnesses, direction targets, polarity,
   assertion authority, support policy and Layer C were built and qualified **offline, by replaying the
   preserved Phase 28 artifacts**. Phase 30 says so directly: "The preserved Phase-28 Attempt-2 artifacts are
   the only empirical input." None of it was called from `run_topology`.
3. **Oct 11, I4-4E1 (`13680c71`).** The first attempt to connect that work to a live caller stopped: the
   hierarchical caller "has no request-owned, authored reporting/node contract for plan-v5". Plan-v5 needs
   authored visible nodes; `run_topology` had none to give it.
4. **Oct 11, I4-4E1B (`9c07c6ff`).** Rather than give the hierarchical caller a reporting contract, a
   separate public entry was added: `reviewed_ask.run_reviewed_request`, which takes five reviewed inputs
   (request, scientific contract, reporting contract, parent map, joint review) and calls the same
   `e2e.execute`. Its report states the scope: "Legacy eligibility and defaults remain unchanged."
5. **Oct 11, I4-4E2 (`cd68d170`).** Semantics v8, Layer C v2 and plan-v5 were made current **for the
   reviewed invocation only**. The default stayed v7 because the version constant sits inside a byte-pinned
   producer source that offline qualification depends on. From this point the two routes ran different
   science.
6. **Oct 11–12, live qualification.** Q1–Q6 were run through the reviewed entry by a disposable driver, on a
   different 86-paper library, with inputs authored and reviewed by the assistant that ran them. `q_aib` was
   never run on the reviewed route, and no reporting contract for `q_aib` was ever authored.
7. **Oct 12, the DeBERTa E2E.** I chose the route. The assignment asked for every child synthesis and a
   parent synthesis and cited Phase 28, and only the hierarchical route produces those or has `q_aib`
   inputs. I saw that the two routes were mutually exclusive and that this choice bypassed v8, Layer C and
   plan-v5, and I did not raise it with you. **That omission is mine**, and it is why the run did not test
   what you thought it tested.

**Classification.** Incomplete integration, made durable by a deliberate temporary arrangement. The separate
entry was a reasonable way past the I4-4E1 blocker, and its documents say it left the hierarchical route
alone. Nothing afterwards brought `q_aib` onto it. It was not accidental routing: both routes did exactly
what their code says. The misunderstanding was about which one a "full E2E of q_aib" meant, and I resolved
it silently.

**What was meant to be integrated before an E2E and was not:** v8 sufficiency semantics, Layer C (claims,
evidence receipts, relation units, value coverage, `parent_synthesis_v2`), plan-v5 and its renderer. All of
it sits behind `_reviewed_inputs`.

**Why Q1–Q6 came back empty.** From their own reports, three separate causes, none of them a single
missing wire:
- *Missing data:* the first attempt's library lacked index entries for the primary papers.
- *A real integration defect, since repaired:* flat reviewed requests lost their recovery target at a
  child/subquestion ID join.
- *Scientific contracts that withhold:* after those repairs Q1, Q3 and Q6 still completed empty, with
  useful evidence "lost at verification" and "rejected during mapping"; Q2, Q4 and Q5 stopped on an
  authored-contract/runtime incompatibility. The B2 pilot then showed verification was not the only limit.

One further cause applies to any hierarchical question and was not visible in Q1–Q6: **the reviewed route
refused model-assisted role nomination outright** (`require(... not sufficiency_model_assist_enabled)`),
while the `q_aib` scientific contract authors most of its roles as `model_nomination_only`. E1B's report
describes this as something "not added by this increment", not as a scientific decision. On that route as
built, 10 of `q_aib`'s 13 requirements cannot be filled whatever the evidence says.

*Uncertain:* I have the design documents and commit messages, not the conversations behind them. Whether
merging the routes was ever explicitly planned for a named later increment I could not establish.

## B. What ran, and what the repaired route runs

| Capability | Oct 12 route (hierarchical) | Reviewed route before repair | Repaired route for a hierarchical request | Status on real execution | Intended for 0.6.0 | Needed in the corrected E2E |
|---|---|---|---|---|---|---|
| Hierarchical decomposition (approved children) | yes | accepted but never used | **yes** | works | yes | yes |
| Retrieval, claim formation, DeBERTa verification, provenance | yes | yes (same code) | yes | works | yes | yes |
| Coverage audit, recovery planning, recovery round | yes | optional | yes | works | yes | yes |
| Sufficiency semantics | v7 | v8 | **v8** | v8 never run live on q_aib | yes | yes |
| Relation witnesses, direction targets, polarity (Ph 32–33) | v7 subset | full | **full** | offline only | yes | yes |
| Model-assisted role nomination | yes | **refused** | **yes** | works on v7; unqualified on v8 | yes for q_aib | yes |
| Assertion authority, support policy | no | yes | **yes** | offline only | yes | yes |
| Layer C v2 (claims, receipts, relation units, value coverage) | no | yes | **yes** | offline; live gave empty answers | yes | yes |
| Producer authorization | no | replay path only | replay path only | offline | qualification tooling, not a run stage | no |
| Answer plan v5 and renderer (Ph 29–31) | no | yes, selected answer | **yes, selected answer** | live gave empty answers | yes | yes |
| Child syntheses | yes | **skipped** | **yes** | works | yes | yes |
| Legacy parent claim ledger and realization (S2) | yes | skipped | skipped | works | superseded by `parent_synthesis_v2` | no |
| Narrative overview and hierarchical document | yes | skipped | **yes** | ran once, weak | presentation, undecided | yes, for comparison |
| Simple (flat) question | flat path | `reviewed_ask` entry | **unchanged** | — | yes | not in this run |

The repaired route excludes two things on purpose. The legacy S2 ledger is replaced on the reviewed route by
Layer C's deterministic parent synthesis, and running both would put two parent authorities in one run.
Producer authorization is offline qualification machinery, not a pipeline stage.

## C. Changes

All in `experiments/ask_cli_revised/`. No new route: `run_topology` can now hand a hierarchical request to
the existing reviewed branch of the existing `execute`.

| File | Change |
|---|---|
| `e2e.py` `run_topology` | New `reviewed_reporting` / `reviewed_review` (CLI `--reviewed-reporting`, `--reviewed-review`). With `--hierarchy` it binds the approved hierarchy and frozen scientific contract it already loads with the authored reporting contract under the joint review, and passes the result as `_reviewed_inputs`. Refuses before any trace directory, client or model call if the review does not match what will run. |
| `e2e.py` `execute` | (1) Model-assisted nomination is no longer refused on the reviewed route. (2) Child syntheses run for a hierarchical request on either route. (3) The hierarchical document may be built on either route. (4) Writes `21_execution_path.json`. |
| `reporting_contract.py` | `from_hierarchy`: an explicit authoring operation that makes one visible node per approved child, with that child's approved wording, parent and ownership. Like the existing `single_question`, it is not an approval; the result must be reviewed. |
| `execution_path.py` (new) | Builds the execution record from what the stages produced. |
| `hierarchy_test_support.py`, `test_reviewed_hierarchy_route.py` (new) | Test harness parameter and 8 tests. |

**Deviations to approve before the E2E.** Both are needed for the integrated route to do anything on
`q_aib`, and both are combinations that have not been qualified:
1. **Model nomination under v8.** Each is validated separately; together they are new. Offline, Layer C
   accepted model-nominated bindings and its own output validation passed.
2. **Child syntheses beside the plan-v5 answer.** They read only the sealed evidence and do not alter the
   selected answer.

Unchanged: the three generators and their settings, DeBERTa at 0.50, all prompts, all thresholds, the frozen
question contract, the default route for runs without reviewed inputs.

## D. Verification

- **Tests.** `test_reviewed_hierarchy_route.py`, 8 tests on the real frozen hierarchy and scientific
  contract with scripted clients: a hierarchical request on the reviewed route stamps v8 on every child of
  the final map and executes Layer C, plan-v5, child syntheses and the hierarchical document; the legacy
  ledger is skipped with its reason; through `run_topology` with model nomination and a recovery round, the
  record shows nomination requests, the recovery round and Layer C, and the run's mechanical checks pass; a
  review that does not match refuses before anything is written; without reviewed inputs the route is
  reported as hierarchical with Layer C skipped and its reason; an empty selected answer names the
  limitation kinds behind each empty part.
- **Suite.** Offline, `contract_directed` excluded, one network-dependent test deselected: 4,783 passed,
  2 failed. The two are the pin-drift failures that fail on the unmodified baseline.
- **Simple questions.** The flat reviewed entry and the flat legacy path are untouched; their existing tests
  pass and now also produce an execution record.

**Execution record (`21_execution_path.json`, copied into the manifest).** Per component: `executed` plus
evidence taken from its output, or `skipped_reason`. It records the route, the semantics version read off
the final map, the model for each stage from the stage log, nomination request counts, recovery targets by
outcome, child synthesis states, Layer C component counts, plan node states, and for the selected answer
each visible node's statement count and the limitation kinds that explain an empty one.

## E. Remaining limitations

**1. Offline preview: the integrated route's selected answer is nearly empty on evidence that contains the
answers.** I ran the reviewed path (v8 → Layer C → plan-v5) over the 64 claims the October 12 run sealed.

| | Requirements filled / partial / missing | Nodes with a displayed statement |
|---|---|---|
| Deterministic mapping only (reviewed route as built) | 2 / 1 / 10 | 1 of 11 |
| With the worker's nominations replayed where the prompt matched (18 of 31) | 6 / 4 / 3 | 3 of 11 |

Even with six requirements filled, most parts render one of two lines: "The available evidence does not
establish…" or "An evidence-supported value cannot be displayed with an authorized quotation here; this is a
presentation limitation, not scientific absence." The amygdala parts are in the second group: the map
fills them and the renderer declines to show a value. No amygdala, Hadza or NAME sentence appears.

This preview understates a live run in two ways (13 nominations had no matching prompt, and I passed no
recovery or search state) and so should be read as a direction, not a prediction. But it is consistent with
Q1–Q6, and it says the integrated architecture's limit is what Layer C and plan-v5 will display, not what
the pipeline finds. The corrected E2E will show this for real. I have not tried to fix it.

**2. The reporting contract is authored but not reviewed.** `from_hierarchy` produced eleven nodes, one per
approved child. The route will not start until a review record names it.

**3. Two parent presentations in one run.** The selected answer is the plan-v5 render; the hierarchical
document is built beside it from the child syntheses. They are not reconciled, and the run will show both.

**4. Hierarchy pins.** The live contract loader still reports pin drift on its own source file, so the
driver keeps the `pins=None` departure used on Oct 4 and Oct 12.

**5. Recovery reuse is off in the prepared run,** to keep the comparison with October 12 clean. It remains
untested live.

**6. The earlier regression findings are untouched,** as instructed: the lexical screens, the truncated
Hadza passage and the rest.

## F. E2E readiness

**Before authorizing, one action is yours.** Read
`.local/e2e-runs/phase34-integrated-reviewed-e2e/inputs/q_aib.reporting.json` (eleven nodes; c5 and c6 under
c4, c9 under c8, c11 under c10). If it is right, save `q_aib.review.PENDING.json` as `q_aib.review.json` with
`"status": "reviewed"`, your name in `reviewed_by` and a timestamp in `reviewed_at`. The content references
in it must stay as they are.

**Configuration (three generators, unchanged):**

```
python .local/e2e-runs/phase34-integrated-reviewed-e2e/runner.py --live
```

which calls

```python
e2e.run_topology(
    "T5C", "aib", hierarchy=True, scored=True,
    sufficiency_model_assist=True, sufficiency_recovery_gate=True,
    parent_synthesis=False,            # superseded on this route by Layer C parent_synthesis_v2
    parent_narrative=True, timing_enabled=True,
    reviewed_reporting=".../inputs/q_aib.reporting.json",
    reviewed_review=".../inputs/q_aib.review.json",
    nli_verifier="deberta",
)
```

W = qwen3.5:9b (thinking off), C = phi4:14b, P = gemma3:12b, S = qwen3.5:9b; DeBERTa at 0.50; the Sept-30
library on a fresh working copy; JUNO with the host-side monitor, temperature limits alert-only as you last
set them unless you say otherwise. It needs its own authorization file and your go-ahead for JUNO.

**How to confirm the intended architecture ran,** from `15_run_manifest.json` → `execution_path`:

- `route` is `reviewed` and `effective_semantics_versions` is `["sufficiency-semantics-v8"]`.
- `components.layer_c_v2.executed` and `components.answer_plan_v5.executed` are true, with non-zero counts.
- `components.model_nomination.executed` is true with a request count.
- `components.child_synthesis.evidence.children` is 11.
- `stage_models` lists qwen3.5:9b, phi4:14b and gemma3:12b against their stages.
- `selected_answer.withheld_or_empty_attribution` gives, for each of the eleven parts, how many statements
  were shown and what kind of limitation accounts for the rest.

The driver will print a warning that the S2 call count is 0. That is expected on this route.
