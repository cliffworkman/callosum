# Ask 0.7 — E2E topology study: revised proposal (Wave 1 + conditional Wave 2)

**Status: proposal, awaiting Cliff's go-ahead. No E2E inference has been run.** Written 2026-09-23. Companion to the bakeoff
reports (`supervisor_eval/REPORT.md`, `GEMMA27_EXTENSION.md`, `QWEN35_8K_SENSITIVITY.md`); nothing in that package is modified.

Question the study answers: *what is the strongest trustworthy model topology for the staged Ask architecture, and how much of
that performance survives simplifying the model set?* The goal is the fewest runs that can change the next decision, not an
exhaustive pairing sweep.

## 0. Task A (done): the execution-policy seam

`execution_policy.py` + `test_execution_policy.py` (25 tests; package total 345 pass; `build_battery verify` -> freeze intact).
Accurately described: **the execution-policy seam required by upcoming role binding.** No live revised-Ask stage calls it yet
(the pipeline has no Qwen3.5 / Ollama-native supervisory path); it becomes active when role binding lands (section 6).
The caller supplies base options; the policy changes only `num_predict`: Qwen3.5 recovery planning -> 8,192 (never lowering a larger
caller value), every other call keeps the caller's allowance; a missing/invalid base allowance raises. `run_stage_call` makes exactly
one call (no escalation, no retry); `length` is NO ANSWER even if partial JSON parses; a valid semantic `[]` is an answer and stays
distinct from NO ANSWER (`answer is None`); the record carries model, stage, allowance, done_reason, usable/outcome, tokens, wall.
It does not import the frozen bakeoff registry.

## 1. Vocabulary (used in the pipeline, renderer, and every report)

Source verification and responsiveness are different judgments (a foundational 0.6 distinction). Wording:

| Say | Never say |
|---|---|
| **source-verified claim** (the claim is supported by its source) | "verified claim" as if it meant relevant |
| **mapped as responsive by R** / **coverage accepted / rejected by C** | "verified as responsive", "not verified for responsiveness" |
| **source-verified but not judged responsive** | — |

"0 unsupported final claims" means only **zero final claims lacking source support**. It does *not* mean every attachment is correctly
responsive; that is an evaluated semantic property.

## 2. Roles and composition

Roles are separately bindable: **W** bounded extraction (context gate/growth, evidence selection, claim formation, recovery query),
**R** claim responsiveness, **C** coverage audit (`det` = existing `audit_coverage` is a legitimate binding), **P** recovery planning;
rendering is deterministic. R and C are *not* merged: R judges an individual source-verified claim against the obligations; C
reasons over the assembled ledger. Neither is assumed redundant.

Common round sequence (stages skipped only when a binding does not need them; a second round never lets newly source-verified
claims bypass R when C depends on R):

`W -> verify -> R -> C -> P -> W -> verify -> R -> C -> render`

- **det-C arms (T0-T4):** deterministic coverage consumes R's mappings, so R is causal. Round 2 runs R on the newly source-verified claims before C is recalculated.
- **model-C arm (T5*, was T5):** C (frozen Task-B contract, unchanged) is the final authority on coverage state and never sees R, so R would be **noncausal**. **R is off** in Wave 1: no R call is spent on it. Round 2 is `W -> verify -> C`.
- R runs after source verification, on source-verified claims only (ledger-equivalent: only source-verified claims enter the ledger and the ledger ignores `obligation_ids`; a stub-R identity test asserts it; R calls fall from ~92 to ~6-30).
- If C is later changed to *see* R's candidates, R becomes causal (W2-3). If the R/C reconciliation is ever needed, R is run **once on cached source-verified claims** (diagnostic D-R), not inside every run.
- NO ANSWER handling: R no-answer -> claim unmapped-mechanical (never `[]`); C no-answer -> obligations unresolved-mechanical; P no-answer -> no planned recovery, recorded (legacy-recovery fallback is the alternative; default is fail closed).

## 3. Wave 1 — bindings and why each arm exists

One frozen substrate for every arm (section 5): gate repair, contract repair, R-after-verification, NO ANSWER semantics,
responsiveness-aware rendering, revised recovery plumbing. `think`: **false for W**; native default for R/C/P. P on Qwen3.5 = 8,192;
everything else 4,096; `num_ctx` unchanged.

| Arm | W | R | C | P | What it resolves |
|---|---|---|---|---|---|
| **T0 repaired Q2.5 baseline (common-base)** | Q2.5 | Q2.5 | det | legacy `recovery_query` | what supervision adds on the *repaired* substrate. **Not** the untouched historical 0.6 pipeline; run9 stays an external descriptive reference only, and T0-vs-run9 differences are not attributable to topology |
| **T1** Q2.5 + Qwen3.5 | Q2.5 | Qwen3.5 | det | Qwen3.5 @8K | Cliff's original local-supervisor concept; Qwen3.5 only in jurisdictions it has earned (C deliberately not forced) |
| **T2** Qwen3.5 + Qwen3.5 | Qwen3.5 | Qwen3.5 | det | Qwen3.5 @8K | T1->T2 changes **W only**: is a stronger worker better |
| **T3** Qwen3.5 + Gemma12 | Qwen3.5 | gemma12 | det | gemma12 | T2->T3 changes S. Gemma's earned jurisdictions are clear-positive recall and bounded recovery; its nearest-category R errors are a known weakness and det has no auditor, so this arm measures whether they reach the final surface. **Control-like; not a strong-architecture candidate** |
| **T4** Qwen3.5 + GPT-OSS | Qwen3.5 | gpt-oss | det | gpt-oss | T2->T4 changes S: conservative, order-robust R (but never selects s1/s3) vs Qwen3.5 R |
| **T5\* role-specialist topology** (amended 2026-09-24; W was Q2.5) | **Qwen3.5** (think off) | off | **phi4** | **gemma12** | *Does assigning the demonstrated C and P specialists outperform the simpler architectures?* Composes the only tested C-passer (both orderings) with the cheap, clean recovery passer. **Not an upper bound**: R is noncausal here and the composition is untested E2E. The worker was changed from Q2.5 because the repaired Q2.5 gate discards ~95% of packets, which would leave phi4's whole-ledger audit almost nothing to test |

R evidence behind T1/T2 vs T4 (frozen Task A: claim-only, all obligations + original request): generic negatives are equal (5/5 both). At the
E2E's 4K allowance Qwen3.5 is 4/9 correct + 3/9 NO ANSWER on the positives; gpt-oss is 3/9 correct + **6/9 confident wrong `[]`**, but is
100% complete, order-robust, and ~3x faster. NO ANSWER fails closed where a wrong `[]` does not, so Qwen3.5 is the T1/T2 R. T1->T5 changes C
and P together (R is causally neutral); W2-4 splits them if the delta is ambiguous. Phi4's instability elsewhere does not bar its narrow C
jurisdiction; C prompts grow with ledger size (bakeoff: 6 propositions), so the C stage carries a prompt-size guard.

## 4. Conditional Wave 2 — each row states its trigger and the decision it changes (no answer -> pruned)

| Arm | Run only if (Wave-1 result) | Decision it changes |
|---|---|---|
| W2-1 Q2.5 + GPT-OSS (R, P = gpt-oss; C det) | T4 >= T2 on false/missed coverage **and** either T1 ~ T2 (worker upgrade not worth its cost) or Qwen3.5 R NO ANSWER >= ~15% of R calls | whether the shipped worker suffices with GPT-OSS |
| W2-2 specialist with W = Qwen3.5 | T2 beats T1 on adjudicated responsive support without added false coverage | whether the worker upgrade enters the final architecture |
| W2-3 R-causal variant: C (phi4) sees R's candidates; R = gemma12 or Qwen3.5 | T3 finds responsive evidence T2 misses **and** the cached-R diagnostic (D-R) on T5 ledgers shows R holds information C omitted, or Cliff wants R causal. Needs a 2-call qualification replay of the modified Task-B prompt first | whether R becomes causal in a C-bound architecture or is removed |
| W2-4 T1 with C = phi4, P = Qwen3.5 | T5-vs-T1 delta is ambiguous between C and P | which change drove the gain |
| W2-5 gemma12-only (C = gemma12; **labelled control**) | model-C beats det **and** phi4-as-C is impractical (latency / instability / licensing) | whether a single 12B model's isolated C weakness persists inside the pipeline |
| D-R diagnostic: R on cached T5 source-verified claims (no pipeline re-run) | a decision needs R/C agreement (W2-3 or R removal) | evidence for W2-3 |

Pruned: gpt-oss + gpt-oss (worker ~2 h/run; no distinct trigger); Qwen3.5 as C (unobserved at <=8K; no arm can change that at 4K).
Qwen3.5-as-W is exercised in T2/T3/T4 only after the `think:false` preflight (5c).

## 5. Must-fix validity prerequisites (before any comparative inference)

**5a. Context gate — MUST FIX. Invariant: mechanical failure != semantic accept/reject.** `qwen.context_gate` is unconstrained at 48 tokens; any
failure falls to `_FROZEN_GATE_FALLBACK = accept` (run9: 99/152 gate calls truncated, then silently accepted). Narrow repair:
(i) schema-constrain the call to `{"action": enum}` — the same mechanism `select_evidence`/`form_claim`/`map_obligations` already use
(0 provider failures in run9); (ii) any residual mechanical failure returns a distinct **NO ANSWER**, never `accept`; (iii) `grow_context`
fails closed on it: the packet is not accepted and not grown, is excluded from evidence extraction, and is recorded as `gate_no_answer`
(distinct from a semantic `discard`). Residual gate NO ANSWERs are **recorded explicitly per run and per arm**, so no topology can look
semantically worse because its worker silently lost evidence mechanically; a run whose gate NO ANSWER rate exceeds a pre-declared
comparability limit (proposed 2% of gate calls; Cliff to confirm) is flagged mechanically confounded and its lost packets are listed.
Regression tests reproduce the run9 failure shape. The WIP `_ends_mid_clause` guard stays as a separate safeguard for genuine accepts of
visibly incomplete text. No worker-model research.

**5b. Contract validation (LLD, built-env) — inspected offline; no inference.**
- The fragments are **not segmentation bugs**: every unit is an exact substring of the request; splitting is the deliberate 0.6 cue-gated rule (literal navigation spans, not independent meanings). LLD is assumed to be `q_depr` (late-life depression, 8 units); built-env is `q_builtenv` (8 units); AIB is 6 units (Run 0.5 parity hash `6e037bab…`). Neither LLD nor built-env contains a '?', so `segment_source_units_v2` sentence-splits and comma-splits any cue-bearing sentence ("interested in", "such as", …).
- Three generic contract properties change what models are judged on, and the bakeoff never tested them (its obligations are question-shaped clauses): **(1) frame loss** — items 2..n ("amyloid", "coherence", "hominess") lose "I am interested in…", and a bare "coherence" can attract EEG spectral-coherence papers, the exact tangential-promotion failure built-env must detect; **(2) non-evidence units** — scope/format/deliverable directives (LLD u1 tail "based on the literature in my library", LLD u8 "Give me a structured account…", built-env u8); **(3) open-ended catch-alls** — "and other relevant … findings", "…and more.".
- Generic, deterministic, non-rewriting repair (property 1): when a cue-bearing sentence is split, each item unit also carries `source_sentence` (the exact containing sentence) and `list_position`; model-facing item lines show the unit **plus** its exact source sentence whenever the unit is not itself a full sentence/question. Units, ids, and question hashes are unchanged; no question is edited by hand.
- Properties 2-3 are **not** repaired by rewriting or reclassifying units. Cliff labels unit *roles* for the two questions once (facet / global head / format directive / catch-all) as an **evaluation-only rubric that never enters a model input**; headline metrics use facet and question units, the rest are reported separately.
- **Freeze:** once applied, the repaired model-facing contract representation is recorded with a hash before comparative E2E and used identically in every arm. AIB units are full sentences/questions, so its model-facing lines are expected to be unchanged; a test asserts it, and **any** prompt-level difference is disclosed (the unit/question hash staying fixed is not called byte-identical at prompt level). The property that matters is one valid contract across arms, not preservation of an accidental representation.
- Noted, not changed: each unit's retrieval view is ~95% the shared original request, so `retrieved_for` is weak provenance.

**5c. Qwen3.5 `think:false` worker preflight (only before T2/T3/T4).** ~8 neutral-fixture calls, minutes, on the isolated Ollama 0.34.3: the model accepts
`think:false` (non-empty content, no reasoning field); the four worker schemas hold (gate enum, span-id enum, claim string, query); every call
ends `done_reason=stop` within its worker cap. Pass/fail only. No worker bakeoff; the E2E answers whether it is a better worker.

## 6. Exact pipeline changes before E2E (a separate TDD build increment after Cliff approves)

1. **Base freeze:** decide the fate of the uncommitted WIP in `qwen.py` / `retrieval.py` / `__main__.py` / tests (recommended: commit as the E2E base after a green run); record the SHA in every run manifest.
2. Contract repair + frozen contract hash + audit report for all three questions (5b). 3. Gate repair (5a). 4. Execution-policy seam (done).
5. Role-binding profile with per-role backends: managed-local (Q2.5, shared Ollama) vs Ollama-native (isolated); `think` per binding; R/C/P individually `off`.
6. Phase-ordered rounds (`W -> verify -> R -> C -> P -> W -> verify -> R -> C -> render`) with explicit unload/residency checks between phases (one 8 GB GPU, `MAX_LOADED_MODELS=1`, two Ollama processes).
7. R after source verification on the frozen Task-A contract generalized to dynamic questions/obligations, run in **both** rounds; NO ANSWER != `[]`.
8. C stage (frozen Task-B contract, prompt-size guard); P stage (frozen Task-C contract) + plan-driven recovery executor (one bounded round).
9. **Responsiveness-aware deterministic renderer** (verbatim only), in the section-1 vocabulary: source-verified claims with "mapped as responsive by R" / "coverage accepted by C", unresolved obligations preserved, "source-verified but not judged responsive" listed separately, and a scope statement limited to the evidence retrieved (no literature-absence claim). Today it prints every source-verified claim regardless of mapping, so built-env's honest result is neither expressible nor measurable. Principles-gated: model attachments stay candidates, never facts.
10. Telemetry, mechanical checker, frozen-label reuse, adjudication sheet generator (private directory outside the repo). 11. Library-copy verification (`.local/ask-060-fix-run/library_copy.sqlite` vs its manifest). 12. `think:false` preflight, then a tiny unscored plumbing smoke per binding type.

## 7. Evaluation and telemetry (layered; no annotation study; no composite score)

1. **Mechanical, every run:** units preserved; ledger validity and `audit_final` conformance (final claims lacking source support = 0); NO ANSWER counts by stage/model (including `gate_no_answer`); legal plan actions (no repeated performed action, no closure of unresolved); `_b_inconsistency`; frozen `_ABSENCE` scan; recovery accounting (unique new source-verified evidence per action); scope-statement check.
2. **Existing frozen labels:** ledger claims matching the frozen AIB claims inherit Cliff's expected judgments free.
3. **Targeted human adjudication, viable completed runs only:** the claims the run *maps/accepts as responsive* without a frozen label (~3-15/run), plus **every promoted attachment on built-env**; a plain sheet with opaque ids, arm labels stripped.
4. **Pooled blinded adjudication only if needed to separate finalists** (missed coverage needs the pool).

Stages that do not causally affect a topology's output are not run for telemetry alone. Built-env success is *not* "zero retrieved": no tangential
evidence promoted to responsive coverage; unresolved obligations preserved; rendering scoped to evidence actually retrieved; no claim that the literature
lacks evidence; not rewarded for answering more. AIB is in-sample for role choice; LLD is the generalization check.
Telemetry: per call (model, role, allowance, done_reason, outcome, prompt/generated tokens, load_duration, wall, thinking chars), per phase, per run
(calls by stage/model, tokens, wall, swap overhead, peak RAM/VRAM/swap via `JunoSampler`, no-answer counts), manifest (profile, digests, runtimes, git SHA, contract hash).

## 8. Sequencing, run count, runtime (Wave 1 only)

Order: prerequisites + preflights -> **1a AIB x 6 arms (6 runs)** -> **1b built-env x 6 (safety screen: an arm that promotes tangential evidence is dropped)** -> **1c LLD x surviving arms**.
Expected 15-18 runs (max 18); every checkpoint is a review stop; Wave 2 is not scheduled.
Rough wall, from run9's 285 s and bakeoff latencies (Qwen3.5-W with thinking off is unmeasured; R calls scale with source-verified claim count and now include round 2):
T0 ~7 min; T1 25-45; T2 35-65; T3 20-35; T4 20-35; **T5 12-22** (no R). About 2.0-3.5 h per question: **1a + 1b ~ 4-7 h; full Wave 1 ~ 6-10.5 h**, plus one-time prerequisites.

## 9. Decisions needed from Cliff

1. Approve the frame-carrying contract repair and confirm LLD = `q_depr`; label unit roles (evaluation rubric only) for LLD and built-env.
2. Fate of the uncommitted WIP as the E2E base (recommended: commit after a green run).
3. The responsiveness-aware renderer's wording and behavior (principles-gated, section 6.9).
4. Gate NO ANSWER comparability limit (proposed 2%) and the P no-answer default (fail closed vs legacy recovery).

## Amendment 2026-09-24 — T5 → T5*

The original T5 (W = Q2.5) is replaced by **T5\*** (W = Qwen3.5:9b `think:false`; R off; C = phi4:14b; P = gemma3:12b). Profile key stays `T5` (an asterisk is not
path-safe); the manifest's `profile.name` reads `T5*` and its W binding is Qwen3.5. Nothing else changed: contracts, verification, execution policy, recovery contracts,
renderer, and the frozen bakeoff are untouched. Consequences for the plan above:

- T5\* differs from T2/T3/T4 in **R (off), C, and P together**, and from T0 in the worker, the responsiveness/coverage architecture, the planner, and the recovery search budget.
  A T0-vs-T5\* result is therefore a **system-level contrast**, not a causal estimate of phi4's, gemma's, or Qwen3.5's contribution.
- W2-2 ("specialist with W = Qwen3.5") is now realized by T5\* itself. The W2-4 trigger ("T5-vs-T1 delta ambiguous between C and P") no longer applies as written: T5\* also differs from T1 in W and R.
