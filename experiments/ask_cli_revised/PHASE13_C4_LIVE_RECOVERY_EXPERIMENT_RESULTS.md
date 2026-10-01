# Phase 13 — one live, isolated RecoveryTarget experiment on `c4::0c3e1a392e7868e4` (2026-10-01)

**Scope:** exactly ONE live recovery execution for `target_id c4::0c3e1a392e7868e4`
(`reason=provisional_corroboration`, `search_child_id=c4`). No other RecoveryTarget. No generic
recovery gap. No second target. Executed exactly once; no retry (none was needed). v9
`combined_hash` unchanged throughout: `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.

## Commits

- `ba50b570` — pre-live diagnostic harness (`phase13_c4_recovery_experiment.py`), dry-run-verified,
  no live call made by this commit.
- This report + lineage entry are committed separately, after the live run (below).

**Final HEAD at hand-back:** see the commit this report ships in (the next commit after this file).

## Pre-run: a real, disclosed blocker (and the explicit decision to proceed)

`hierarchy_contract.load_contract_for_live` fails pin verification — `hierarchy_contract.py`'s own
code hash drifted from the pin file (last touched by bug-fix commit `d075fa36`, *after* the pin
file's last install, `617699de`; `decompose/execution.py`/`decompose/tree.py` match their pinned
hashes exactly; the hierarchy DATA is unaffected). This predates Phase 9-13 and is unrelated to any
of this work. **Presented to Cliff before any live call; he explicitly chose: bypass via
`load_contract(question, pins=None)` (the module's own documented "structural checks only" mode),
disclosed, with re-freezing pins left as a separate, later decision.** This is the one deviation
recorded in the authorization artifact's `disclosed_deviation` field.

## A. Experiment isolation

The normal pipeline (`e2e.execute()`) cannot isolate one target — its sufficiency-extension block
generates and appends a synthetic row for **every** surviving `RecoveryTarget` (by Phase 12's own
design: no suppression based on a generic gap). A smallest diagnostic-only harness was added:
`phase13_c4_recovery_experiment.py`. It changes **zero** `_recover`/retrieval semantics — it calls
the unchanged `cli._recover`, `discovery.nominate_papers`, `retrieval.within_paper_retrieve`,
`stages.run_coverage_audit` exactly as they exist, and only *selects* the one gap passed to
`_recover` as input. No STOP condition under Section A was triggered.

Seeding reused `e2e.seed_pass_from`'s own inner `_seed` closure, unchanged, called directly
(outside `execute()`'s hierarchical guard, which exists specifically to stop a *scored* run from
silently slicing/seeding its approved children — this is not that; it is a diagnostic reading the
same preserved sealed ledger a scored run already produced).

## B. Pre-run mechanical gate — all 12 passed

Run via `python -m experiments.ask_cli_revised.phase13_c4_recovery_experiment` (dry-run, no `--live`)
before the live call, and reproduced identically immediately before the live call itself:

| # | Gate | Result |
|---|---|---|
| 1 | HEAD == `0b676a5d` plus only the disclosed diagnostic-isolation commit (`ba50b570`) | ✅ |
| 2 | v9 `combined_hash` byte-identical | ✅ `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586` |
| 3 | No-live replay regenerates `target_id == c4::0c3e1a392e7868e4` | ✅ (one note: the Phase 12 report's markdown table abbreviated this to 8 hex chars, `c4::0c3e1a39` — the full, real id is 16 chars, `c4::0c3e1a392e7868e4`; confirmed identical, not a discrepancy) |
| 4 | Exactly one selected target executes | ✅ `len(gaps) == 1` |
| 5 | `search_child_id == c4` | ✅ |
| 6 | `affected_descendants` reflects the shared c4/c6 obligation | ✅ `["c4", "c6"]` |
| 7 | Hint excludes the current model-mapped exact_text | ✅ hint = `"a specific NAMED brain area"`; guessed value = `"the specific amygdala response"` |
| 8 | Synthetic gap uses `subquestion_id=c4`, `field_id=c4` | ✅ |
| 9 | No generic recovery gap included | ✅ `gaps = [gap]` only |
| 10 | No other structured RecoveryTarget included | ✅ |
| 11 | Exact preserved library/evidence snapshot identified and fixed | ✅ `library_copy.verify()` against `library_copy.sqlite.fingerprint.json`; sha256 `4f2e98a54c92790e791d841ef63e2fd60c4b411246f9c29590c19e56da892523`, matching the ORIGINAL Phase-5 run's own recorded `library_fingerprint_sha256` |
| 12 | Benchmark-isolation checks remain green | ✅ `test_sufficiency_leakage.py` + `test_sufficiency_recovery_targets.py`, 52/52 |

## C. Authorization artifact

Written to `.local/e2e-runs/phase13-c4-recovery-experiment/phase13_authorization.json`
(sha256 `12532fa4ad69ce3bc07add52ec7a9c163bc27506f6e6c3954d76a7ded6f67e1f`), self-checked via the
real, unmodified `hierarchy_contract.check_authorization()` (not a new ad-hoc check) before any
live call:

```json
{
  "experiment_id": "phase13_c4_recovery_isolated_20261001",
  "authorized_by": "Cliff (via Claude, explicit Phase 13 authorization)",
  "authorized_at": "2026-10-01T18:20:58.694587+00:00",
  "brief_confirmed": true,
  "question_sha256s": ["6e037bab4baad2c0b4427a1c73c6e1720296292b3be36189cd9cf02436e57030"],
  "question": "aib",
  "v9_combined_hash": "9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586",
  "target_id": "c4::0c3e1a392e7868e4",
  "search_child_id": "c4",
  "library_fingerprint_sha256": "4f2e98a54c92790e791d841ef63e2fd60c4b411246f9c29590c19e56da892523",
  "exactly_one_recovery_execution": true,
  "no_other_recovery_targets_authorized": true,
  "qwen_recovery_model": {"endpoint": "isolated", "model": "qwen3.5:9b", "think": false},
  "coverage_sealing_model": {"endpoint": "isolated", "model": "phi4:14b"},
  "disclosed_deviation": "hierarchy loaded via pins=None (pin-drift bypass); see script module docstring"
}
```

A separate, prior authorization artifact (the original Phase-5/T5C run's own
`authorization.json`) was **not** reused — this is a new artifact naming this exact experiment.

## D. Pre-registered falsification criteria — outcomes

1. **Redirection failure?** No. The generated query ("specific named brain areas where
   anomalous-is-bad bias manifests") is built from c4's own search-owner context; it contains no
   c6 pairing language.
2. **Confirmation-bias failure?** No, at the **input** level — the exact distinction the brief
   asked to preserve: the `obligation_note` fed to `qwen.recovery_query` was the hint
   `"a specific NAMED brain area"`, never the guessed `"the specific amygdala response"`.
   Separately, as its own fact: the model's **output** also did not independently hypothesize
   "amygdala" — the generated query names no specific region at all. Both facts are recorded
   separately below (input provenance and output content), as instructed.
3. **Dedup failure?** No. `len(recovery_log) == 1` — exactly one search executed for the shared
   c4/c6 obligation.
4. **Target-ID failure?** No. The executed gap's `_recovery_target_id` is exactly
   `c4::0c3e1a392e7868e4`.
5. **Scope failure?** No. The `gaps` list passed to `_recover` contained exactly the one entry.
6. **Provenance failure?** No. `target_id → search_child_id → hint → recovery_query → nominated
   papers → retrieved hits → newly-verified evidence → post-recovery sufficiency state` is fully
   reconstructable from the recorded JSON (below).

**Architecture mechanically PASSED all six.**

## E. Live execution record

Full raw record: `.local/e2e-runs/phase13-c4-recovery-experiment/phase13_result.json`
(sha256 `9d1f3bb893104ced8db70454698e8b3d41d20e365cd2caad02bb194a38db4f51`).

- **Exact target object:** `search_child_id=c4`, `trigger_child_id=c4`, `requirement_id=
  c4#suff:specific-region`, `target_roles=["named_brain_region_or_network"]`,
  `reason=provisional_corroboration`, `goal_mode=single_role`, `scope={"kind":"none"}`,
  `dependency_origins=[{"child_id":"c4","requirement_id":"c4#suff:specific-region","role":
  "named_brain_region_or_network","instance_key":null}]`, `affected_descendants=["c4","c6"]`.
- **Exact generated hint / input to `qwen.recovery_query`'s `obligation_note`:**
  `"a specific NAMED brain area"`.
- **Exact search-owner subquestion:** c4's own subquestion text (its `source_wording_span`:
  *"Please return the specific brain areas in which the anomalous-is-bad bias manifests."*).
- **Raw `qwen.recovery_query` output (the actual generated query):**
  `"specific named brain areas where anomalous-is-bad bias manifests"`.
- **Effective model options:** `{"num_ctx": 12288, "num_predict": 4096, "temperature": 0, "seed":
  42, "num_thread": 6, "num_batch": 512}` (T5's `SUPERVISOR_BASE_OPTIONS`), with `recovery_query`'s
  own task-level cap `output_cap=64` tokens (`qwen.py::_RECOVERY_OUTPUT_TOKENS`).
- **Thinking state:** off (`think=False`, T5's own W binding) — no reasoning trace.
- **Retrieval:** action `LEGACY` (no plan supplied — the P-stage planner was deliberately not
  invoked for this isolated experiment, since the brief authorized only the recovery search, not an
  additional live planning call); `existing_candidate_papers=0` (seeded with none), so the LEGACY
  path's own "nominate if deepening added nothing" branch fired: `discovery.nominate_papers` over
  the generated query returned **23** candidate papers (via `paper_kNN` and two axes, "Facial
  Perception and Stigma"/"Social Perception Accuracy"); `within_paper_retrieve` over those 23
  produced **6** hits; verification kept **1** newly source-verified proposition.
  `reason_code=recovery_added_evidence`.
- **Newly verified evidence (exactly one):** paper **74**, chunk 35979, span
  `e8`: *"Functional magnetic resonance imaging (fMRI) studies have demonstrated a critical role
  for a cortical region in the right temporo-parietal junction (RTPJ) in 'theory of mind' (ToM), or
  mental state reasoning."* Verification: `retrieval=0.800, quote=1.0, support=0.982,
  contradiction=0.004, coordinate_precision=exact`.
- **Timing by stage:** `W2_c4_recovery` (qwen3.5:9b, recovery query + retrieval + verification):
  **122.2 s**. `C2_coverage_sealing` (phi4:14b, the mechanical sealing step, not a second
  RecoveryTarget — see §G): **146.5 s**.
- **GPU residency (JUNO, single 8 GB GPU, one model resident at a time):** W2 loaded `qwen3.5:9b`
  (5.77 GB, fully resident). C2 unloaded it and loaded `phi4:14b` (11.8 GB total, 6.88 GB VRAM —
  partial offload, within the known single-GPU constraint). Both unloaded cleanly at the end
  (`ResidencyGuard.release_all()`).
- **Exactly one attempt occurred:** confirmed — `len(recovery_log) == 1`; the harness asserts this
  mechanically and would have raised before writing any result otherwise.

## F. Scientific / retrieval adjudication (manual, no tuning after seeing the result)

One new piece of evidence (the RTPJ/ToM sentence from paper 74). Classification:

- **Relevance to the RecoveryTarget: ambiguous.** It names a specific brain region (satisfying the
  letter of "a specific NAMED brain area") in a context *plausibly* conceptually adjacent to the
  bias (RTPJ is classically implicated in social-cognitive/mentalizing processing, and the
  already-established amygdala finding's own correlates — just-world beliefs, empathic concern,
  prosociality — are social-cognitive constructs too). But the verbatim quote itself is a general
  theory-of-mind framing statement, not a direct assertion that RTPJ's activity correlates with or
  manifests the anomalous-is-bad bias specifically. It reads as background/scene-setting from
  paper 74 (which was independently relevant to the governing axes), not as the paper's own
  bias-specific finding.
- **What it does, concretely:** it neither independently supports a *bias-manifesting* brain
  region nor conflicts with the existing amygdala finding; it does not improve the existing
  evidence anchor (the deterministic `region_bears_on_bias_evidence` binding is unchanged — see
  §G, still bound to p11's amygdala-correlates quote); it is not a repeat of existing evidence
  (genuinely new content); it does not enable a deterministic mapping that was unavailable before
  (`named_brain_region_or_network` has no deterministic strategy at all — it is structurally
  `model_nomination_only`, so no retrieval result, however strong, can bind it without a model
  nomination pass); and whether it would itself become a *new* model-nominated candidate region is
  **undetermined by this experiment** (see §G's own disclosed limitation) — remaining
  model-dependent is the honest, unresolved status, not a finding either way.

## G. Post-recovery recomputation — before vs after

**A real methodological issue was found and resolved before writing this section, not glossed
over:** the harness's own "after" recomputation (`compute_diagnostic_sufficiency_map(sealed, ...,
model_client=None)`) is **deterministic-only** — it never re-ran a model nomination pass (correctly
out of this experiment's scope: the brief authorized one recovery search plus the coverage-sealing
step, not an additional nomination call). The Phase-12 inventory's own "before" snapshot was Phase
5's **with-model** replay. Comparing them directly would show large, *apparently* sweeping changes
across unrelated children (c1, c2, c5, c8, c9, c10, c11, c12) that are actually a pure artifact of
this mismatch, not real effects of the recovery search. **Verified by an offline (no live call)
check**: recomputing `sufficiency_phase5_replay.replay()["deterministic_only"]` (the same replay's
own deterministic-only half) and comparing its target set, child by child, against this
experiment's own "after" targets — **every child except c4 produces an identical target set**,
confirming those apparent differences are the mismatch artifact, not evidence of anything the
search did or didn't affect.

**c4** (`c4#suff:specific-region`):

| | Before (with-model, Phase-5 replay — the real prior state) | After (this experiment's deterministic-only recomputation) | Apples-to-apples baseline (deterministic-only, same replay, BEFORE) |
|---|---|---|---|
| requirement state | `filled` | `partially_filled` | `partially_filled` (**identical to "after"**) |
| instance count | 1 | 1 | 1 |
| `named_brain_region_or_network` | `filled`, `candidate_source=model_mapping`, `exact_text="the specific amygdala response"` | `missing` | `missing` (**identical to "after"**) |
| `region_bears_on_bias_evidence` | `filled`, `candidate_source=deterministic_mapping`, `exact_text=`"...amygdala response to facial anomalies correlated with..."` (p11) | **unchanged**, same p11 binding | same |
| `compute_stop_search_certified` | `False` (provisional — the whole reason this target existed) | `True`, but **vacuously** (the predicate is trivially true whenever `state != "filled"`; this is not a certification improvement, it is the predicate's own documented no-op case) | same vacuous `True` |

The decisive, apples-to-apples fact: **c4's deterministic-only state did not change at all between
before and after.** The new RTPJ evidence did not alter `region_bears_on_bias_evidence`'s existing
deterministic binding (still p11, byte-identical exact_text) and could not, by itself, fill
`named_brain_region_or_network` (structurally un-fillable without a model). **Whether the amygdala
nomination survives re-confirmation, or whether RTPJ would be nominated as an additional or
alternative candidate region, is genuinely undetermined** — it requires a further, separately
authorized model-nomination pass over c4's updated candidate pool, which this experiment correctly
did not run.

**c6** (`c6#suff:brain-attitude` + `c6#suff:implicit-explicit-coverage`):

| | Before (with-model, Phase-5 replay) | After (deterministic-only) | Apples-to-apples baseline (deterministic-only, before) |
|---|---|---|---|
| `brain-attitude` state | `filled` (2 instances, both complete) | `missing` | `missing` (**identical**) |
| inherited `named_brain_region_or_network` | `filled` via `parent_context`, `upstream_model_dependent=True`, `model_dependency_origins=[{child_id:c4, requirement_id:c4#suff:specific-region, role:named_brain_region_or_network}]`, `exact_text="the specific amygdala response"` | `missing` | `missing` (**identical**) |
| `attitude_type_or_measure` | `filled` ×2 instances (model_mapping, "Explicit Bias Questionnaire", two distinct propositions) | `missing` | `missing` (**identical**) |
| `compute_stop_search_certified` | `False` | `True` (vacuous, same caveat as c4) | same |
| `implicit-explicit-coverage` state | `partially_filled` (explicit filled, implicit missing) | `partially_filled` (same shape) | `partially_filled` (**identical**) |

c6's state is **entirely unchanged** by this experiment under the apples-to-apples comparison — it
never had its own search run, and its one dependency on c4 (the inherited region) is exactly as
undetermined as c4's own.

**Other children:** confirmed, by the offline check above, **identical** target sets to their own
deterministic-only baseline for every one of c1, c2, c3, c5, c8, c10, c11, c12 (c9 produces zero
targets in both, consistent — it depends entirely on c8's own model-nominated trait, which
deterministic-only mapping can never supply). **No child changed unexpectedly.**

## H. Two questions, assessed separately

**1. Architecture validity: YES.** Correct search owner (c4, never c6); no guessed-value feedback
at the input level (confirmed directly); exactly one deduplicated attempt for the shared c4/c6
obligation; full provenance reconstructable end to end; bounded execution (one recovery call, one
mechanical sealing call, no retry); correct, apples-to-apples-verified recomputation once the
methodological mismatch was caught and corrected for. All six pre-registered falsification
criteria passed.

**2. Recovery usefulness: no material change.** The search executed correctly and found one
genuinely new, verified piece of evidence, but it is ambiguous in relevance and did not alter any
binding for c4 or c6 under the only recomputation this experiment's scope permits (deterministic-
only). Whether it — or the pre-existing amygdala nomination — would be judged differently under a
further model-nomination pass is a **separate, undetermined question**, not a negative result:
this is exactly the honestly-disclosed "nothing useful found within this bounded attempt" outcome
the architecture's own design (round 2 §7) treats as scientifically legitimate, not a failure.

## I. Next-step decision

**B. ARCHITECTURE MECHANICALLY VALID BUT QUERY/RETRIEVAL TARGETING NEEDS REFINEMENT** is the
closest honest fit, with one caveat worth stating precisely: nothing about *this* query's
construction was architecturally wrong (it correctly avoided the guessed value, correctly scoped
to c4's own context) — the retrieval it produced surfaced a real but ambiguously-relevant finding.
A real refinement candidate, suggested by this one data point and not yet validated: the generic
hint `"a specific NAMED brain area"` is maximally safe (no confirmation bias) but gives the query
nothing to anchor *which* bias-relevant framing to search within, unlike the relational-missing-
role template's own "associated with {clean sibling value}" scaffolding (round 2 §6) — a
corroboration-specific hint template that adds the REQUIREMENT's own non-guessed context (e.g. the
bias construct itself, already present in `source_wording_span`, never the target's own guessed
region) might retrieve more directly on-point evidence. This is a hypothesis from n=1, not a
conclusion — exactly why a broader run is not recommended yet.

**A broader recovery experiment is explicitly NOT run or recommended in this phase.**

## J. Regression / provenance

- `phase13_c4_recovery_experiment.py` is clearly diagnostic/experimental (module docstring, file
  name, outside `run_topology()`'s gated path).
- Full regression before the live call: `experiments/ask_cli_revised/` tree — **2097 passed, 11
  skipped**, the same 2 pre-existing, unrelated failures (confirmed via the same `git stash`
  method Phase 12 used).
- `ruff check` / `ruff format --check`: clean on the new script.
- v9 `combined_hash` confirmed unchanged both before and after the live call:
  `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.
- `CONTRIBUTION-LINEAGE.md`'s Phase 13 entry is appended after this report (below), not before;
  Phases 1-12 are untouched.
