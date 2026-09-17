# Callosum 0.7.0 Local-Orchestrator Benchmark — Preregistration

**Status:** Execution-ready, first-run-frozen experimental protocol (preregistration). **No inference, no
model downloads, no code changes, no Ask/0.6.0 changes, no benchmarking, no architecture decision, no winner
chosen. Nothing here is staged or committed by the authoring pass.** This document *defines* an experiment; a
separate, explicit approval executes it.

**Companion to / derived from:**
- `.claude/docs/research/2026-09-09_local-orchestration-feasibility-study.md` (the decision this operationalizes:
  *HARDWARE EVIDENCE SUPPORTS LOCAL-ORCHESTRATOR BENCHMARKING*; hardware tiers, JUNO calibration, §9 memory
  math, §10 model roster, §15 matrix sketch).
- `.claude/docs/research/2026-09-07_ask-cli-experiment-scoping.md` (the staged-synthesis pipeline; the
  architectural lineage of R_0_6).
- `.claude/docs/research/2026-09-07_ask-run-0.5-control-plane-pivot.md` (evidence-conditioned judgment; the
  A/B/C/D/E minimum-sufficient-context task; decomposition self-audit — the source-anchored family).
- `.claude/SCRATCH.md` A0–A3 + cap-repeat entries (the planner experiments; the model × representation
  confound; the frozen questions and their evaluation referents).
- `.claude/LATENCY.md` (binding for all model-backed measurement; §15 host-state recording).

**Authoring provenance note (load-bearing).** An audit of the frozen artifacts was performed before writing
§6 (Representation Conditions). It corrected a drafting error and changed the representation set — see §6 and
§22. The audit is why this protocol runs **two** representation conditions, not three.

---

## 1. PURPOSE

The feasibility study established *that* a local-orchestrator sweep is justified. It did not say **what
controlled experiment** would tell us whether **model capability**, **request-representation package**, or
**their interaction** determines orchestration fidelity for Callosum's Ask control plane. This preregistration
is that experiment.

It answers one question and refuses two temptations:

- **Answers:** Given Callosum's real Ask control-plane tasks over a bounded, trusted, pre-embedded local
  corpus, does moving *model capability* and/or *request-representation package* change request fidelity,
  mechanical reliability, and contamination — and is any capability benefit **conditional on** a richer
  representation (an interaction), or present regardless (a main effect)?
- **Refuses (a):** a sweep that varies *only model size*. Prior in-repo failures (A0–A3) are confounded across
  model × prompt × representation; a size-only sweep would re-inherit that confound and could not attribute
  cause.
- **Refuses (b):** defining success as *beating a cloud model*. A viable local orchestrator may be slower and
  numerically weaker than cloud and still pass, because the design goal is a **local, private, additive** path,
  not cloud parity (§11, §15).

The experiment is executable once the concurrent Codex Ask-CLI **0.6.0** task freezes its strongest request
representation (R_0_6, §6, §18). Until then the R_CONTROL model-axis column is independently runnable and is a
meaningful partial result on its own (it extends the A-series to stronger models under the *unchanged*
production representation).

---

## 2. PRIOR EVIDENCE / CONFOUND

The in-repo planner experiments (`.claude/SCRATCH.md`, HEAD `6b4b8d9`) establish the state of evidence and the
exact confound this design must break.

- **A0 — production planner, bare contract, no structured output.** Unmodified `query_planner.plan_query` on
  the two frozen questions → **NARROW / 0 facets for both**; the broad faceted pipeline never engaged. Every
  source obligation **starved** (q_aib 13/13; q_builtenv 11/11), 0 invented.
- **A1 — same planner + `response_format` structured decoding only.** Both questions still resolved
  **NARROW / 0 facets**; shape enforcement succeeded but recovered **0/2** broad plans. Headline: format
  enforcement fixed JSON *shape*, not *scope/semantics*.
- **A1 scope-only counterfactual (offline).** Forcing scope narrow→broad as the only change: q_aib became
  **VALID_BROAD / 3 facets** but **semantically lossy** (2 preserved / 4 drifted / 7 starved of the whole-facet
  tally; 0 invented); q_builtenv stayed invalid (< MIN_FACETS). Scope explains the early returns but not the
  failure to obtain *faithful* broad plans.
- **A2 — deterministic-broad, facet-only.** Forced broad + 3–6 facets + `response_format`: both
  **BROAD / 3 accepted**, both **VALID BUT SEMANTICALLY LOSSY** (q_aib whole P/D/S 2/8/3; q_builtenv 10/1/0,
  much stronger topic fidelity; 0 inventions on both, some query-only unsupported additions).
- **A3 — operation-aware facet generation.** q_aib partial improvement (P/D/S 2/8/3 → 4/7/2) with material
  loss remaining; q_builtenv **degraded** (10/1/0 → 5/5/1; operations 4/5 → 0/5). Fewer answer-substitutions
  did not rescue absent open requests.
- **Staged full pipeline, first frozen run.** The 12-stage CLI ran end-to-end but sealed few verified
  propositions; the dominant loss was the **Qwen S1 decomposition** returning a JSON object rather than the
  required array → validator reject → frozen fallback → starved ledger. Deterministic S2/S4/S7 worked; the
  **terminal fork** cleanly separated model from pipeline (given the same impoverished sealed ledger, Gemini
  honored it and listed honest gaps while Qwen fabricated domain facts not in the ledger).

**The confound, stated precisely.** Across A0→A3 the *model* was held constant (Qwen2.5-1.5B-Instruct Q4_K_M)
while **prompt, structured-decoding enforcement, scope policy, and facet-generation representation all moved
together**. Two failure *classes* are separable in the evidence but were never crossed against model
capability:

- **FORMAT** — the model won't emit bare/complete control JSON. Fixed by a grammar + adequate output budget
  (the A1/structured-decoding result, and the inc-575 "truncation by construction" class). **This is not the
  variable under study; it is held constant (§5).**
- **SEMANTICS / SCOPE** — even with valid JSON, scope selection and obligation/relationship/operation fidelity
  fail. Grammar guarantees structure, not meaning. **This is the capability question the sweep tests.**

The feasibility study's §16 names "attributing A0–A3 failure to capacity" as the single biggest analytical
risk. This design's entire reason for existing is to **not** make that error: it crosses model against
representation package so a capability conclusion is *earned*, not assumed.

---

## 3. EXPERIMENTAL QUESTIONS

**EQ1 (primary).** Holding all non-model, non-representation conditions fixed, does **model capability** change
request fidelity / mechanical reliability / contamination on the Ask control-plane tasks, **conditional on the
representation package** in use?

**EQ2 (primary).** Holding model fixed, does the **representation package** (R_CONTROL vs R_0_6) change those
outcomes, **across models**?

**EQ3 (primary).** Is there a **model × representation-package interaction** — i.e., does capability help only
under a richer representation, or does a richer representation help only above some capability floor?

**EQ4 (secondary).** Where does the **smallest reliable worker** sit, and is there a single ~4B model that can
serve **both** the bounded worker role and the low-frequency orchestrator role on the Broad Researcher
Baseline?

**EQ5 (secondary, calibration).** How do bounded **cloud references** (Gemini ± one Claude/OpenAI) score on the
identical sealed inputs / output contract / scoring — as a *reference*, explicitly **not** as privileged ground
truth and **not** as a hardware-equivalent cell (§11)?

**What these questions can and cannot resolve — identifiability boundary (per methodological correction #2).**
The factor is a **representation *package***, which necessarily bundles a frozen prompt/template, a schema,
deterministic preprocessing, and representational machinery. The design can estimate: (i) **model effects
conditional on a package**, (ii) **package effects across models**, and (iii) their **interaction**. It
**cannot** independently identify *prompt effects* versus *representation effects* versus *preprocessing
effects* — those move together inside a package. Isolating them would require an additional factor and is
**out of scope**. No claim of the form "the representation (as opposed to its prompt) caused X" may be made
from this design.

---

## 4. HYPOTHESES

Stated as pre-registered candidate outcomes with the interpretation rule each triggers (full rules in §19).
Because the evidence base is two questions plus a small held-out set (small-n, per-obligation counts of 13 and
11), every hypothesis is evaluated **per question, never averaged across questions** (the A-series explicitly
refused to average q_aib and q_builtenv, whose fidelity profiles diverge), and with an explicit small-n caveat
(§15).

- **H_model (model main effect).** Stronger models improve fidelity/reliability under *both* representation
  packages. → capability matters largely independent of representation.
- **H_repr (representation-package main effect).** R_0_6 improves fidelity/reliability across *all* model
  sizes. → the representation package matters largely independent of capability.
- **H_interaction (the design's focal hypothesis).** Capability helps *materially more* (or *only*) under
  R_0_6, or R_0_6 helps *materially more* (or *only*) above some capability floor. → cause is the pairing, not
  either factor alone. This is the outcome the crossed design exists to detect and the one the confounded
  A-series could not.
- **H_ceiling.** Small and larger local models perform equivalently under the best available representation. →
  capability is not the binding constraint at these sizes for this narrow job.
- **H_cloud_only.** A cloud reference materially exceeds every local candidate on fidelity/contamination under
  the same representation. → the local-orchestrator leg is not yet viable; small-local + focal-cloud remains
  the path (still additive, never a mandate).
- **H_local_sufficiency.** One or more local candidates clear the pre-registered fidelity/contamination floor
  (§15) on both frozen questions, **even if cloud remains numerically stronger**. → a fully-local orchestrator
  is viable for the core tier; this is the target outcome and is judged against the floor, not against cloud.

These are not mutually exclusive across the worker vs orchestrator size classes: it is a legitimate result
that, e.g., H_ceiling holds in the worker class while H_interaction holds in the orchestrator class.

---

## 5. FACTORIAL DESIGN

**Design: MODEL × REPRESENTATION PACKAGE**, everything else held fixed. (Named "package," not "prompt" or
"representation" alone, per the §3 identifiability boundary.)

- **Factor A — MODEL:** the Stage-1 survivors from the Stage-0-eligible roster (§7), spanning a worker class
  (~1.5–4B) and an orchestrator class (~7–14B), with **Qwen2.5-1.5B-Instruct Q4_K_M as the incumbent control**.
- **Factor B — REPRESENTATION PACKAGE:** **R_CONTROL** and **R_0_6** (§6). Exactly two conditions; R_SOURCE was
  audited and omitted (§6, §22).

**Held fixed across every cell (not variables under study):**
- **Structured decoding + adequate output budget** — the FORMAT-class fix (§2). On JUNO/Ollama this means the
  OpenAI-standard `response_format: {type:"json_schema", json_schema:{…}}` (the durable finding: Ollama
  **ignores** production's top-level `json_schema`; `response_format` **is** enforced). On the shipping
  llama.cpp `b10516` runtime, top-level `json_schema` works. Whichever runtime a cell uses, structured decoding
  is **on** and the output budget is set to the current production cap; the sweep never runs a
  no-grammar/undersized-budget cell, because that would re-introduce the format failure the design controls
  for.
- **Temperature 0, fixed seed (42), fixed context window, fixed output cap, fixed quantization per model
  (§8/§13), fixed verifier thresholds** (retrieval 0.70 / exact-quote 1.0 / support 0.55 / contradiction 0.55 —
  unchanged; the closed retrieval-gate experiment forbids touching them), **fixed corpus (a read-only DB
  copy), fixed frozen questions + held-out set, fixed scoring rubrics** (§14, §17).

**Cell = (model × representation package × hardware).** The hardware axis is deliberately **not** fully crossed
(§12): JUNO is the near-term substrate for the full model × package matrix; other hardware is finalist-only
replication.

**What the design estimates (restating §3 for the analysis plan):** model-conditional-on-package effects,
package-across-model effects, and their interaction — **not** isolated prompt/representation/preprocessing
effects.

**Runnability now vs. on R_0_6 freeze.** The **R_CONTROL** column is runnable now and is a standalone result
("does a bigger model rescue the A-series failures under the *unchanged* production representation?"). The
**interaction test (EQ3), which is the design's whole point, requires R_0_6** — a single representation cannot
test an interaction. Hence the readiness verdict (§23) is *READY EXCEPT FOR R_0_6*.

---

## 6. REPRESENTATION CONDITIONS

Each condition is a **package**: prompt/template + schema + deterministic preprocessing + representational
machinery, frozen as a unit (§3, §17).

### R_CONTROL — frozen production Facet{label,query} request representation
The current production broad-Ask request representation: **`query_planner.plan_query`'s Facet{label, query}
schema** (inc 581), exercised exactly as A1/A2 exercised it, with structured decoding + output budget applied
(held constant, §5). It emits a bounded set of facets, each a `{label, query}` pair; scope (narrow/broad) is
the planner's own choice.

**Obligations are NOT part of R_CONTROL (per methodological correction #4).** The 13 (q_aib) and 11
(q_builtenv) source-obligation inventories are **external evaluation referents** — the frozen ground-truth
decomposition of each user request against which *any* representation's output is scored (§14, §17). Production
does not emit them and is not defined in terms of them. R_CONTROL is described purely by what production emits:
`Facet{label, query}`. This distinction is preserved everywhere in this document: obligations live in the
**scoring/referent** layer, never inside a representation package's definition.

### R_0_6 — RESERVED SLOT (strongest revised-Ask 0.6.0 representation)
The strongest request representation produced by the concurrent Codex Ask-CLI **0.6.0** task. **It is not
invented, sketched, or reconstructed here.** Its architectural family is the source-anchored / evidence-
conditioned lineage (staged-synthesis scoping + the control-plane pivot), but its exact frozen form is Codex's
to deliver. The precise artifacts Codex must hand over for R_0_6 to be frozen into this benchmark are specified
in **§18**. Until those land, R_0_6 is empty and the interaction cells (EQ3) cannot run.

### R_SOURCE — AUDITED AND OMITTED
The original plan proposed a provisional third condition, R_SOURCE, described as "the source-anchored
representation already scored against q_aib/q_builtenv in A2/A3." **A pre-authoring audit of the frozen
artifacts found that description false and the condition not admissible.** Findings:

1. **A2/A3 are not source-anchored.** A2/A3 operated on the **production Facet{label,query} planner** (forced
   broad; operation-aware facet guidance) — i.e., they are *variants of R_CONTROL's family*, not a source-
   anchored representation.
2. **The genuine source-anchored work is a separate, unfrozen, still-adjudicating arc.** It lives in
   `experiments/ask_cli_revised/calibration/` (Runs 0.5/0.6/0.6a/0.6b): a **decomposition-selection** procedure
   (choosing among Qwen decomposition styles + a deterministic source-unit baseline) plus an
   **evidence-screen** (P1/P2 primitives). It is **upstream-only** (decomposition + evidence screen; obligation
   mapping, coverage, recovery, and terminal synthesis are explicitly out of its scope), **STOPPED-for-review**,
   and its selection policy is **unresolved** (the Policy-A drift tie-break, per-unit vs whole-question
   granularity, and a not-yet-run Run 0.7 grounded fidelity judge are all open). It is a *moving selection
   policy*, not a single clearly-specified executable representation package — it even selects different
   decomposition styles per question (q_aib→multi/minimal; q_builtenv→baseline fallback).
3. **It is the ancestor of R_0_6, not a distinct condition.** Freezing a snapshot of this arc as R_SOURCE would
   substantially overlap whatever R_0_6 becomes — i.e., factorial-padding, which the commissioning brief and
   the correction both forbid ("do not multiply representations merely to make the factorial richer";
   "omit it rather than reconstructing a third condition for factorial completeness").
4. **The staged full pipeline** (`experiments/ask_cli/`) is executable and full-pipeline, but its own S1
   source-anchored decomposition **fell back** on its single frozen run, so it does not provide a *working*
   frozen source-anchored representation either.

**Disposition: OMIT R_SOURCE.** The representation axis is **R_CONTROL × R_0_6** (two conditions — the brief's
stated minimum). R_SOURCE may be **re-admitted only** if, before the Stage-2 freeze, a *clearly specified,
executable, historically grounded* source-anchored package with unambiguous provenance is identified and
frozen (e.g., a Run-0.6 decomposition-selection policy promoted to a full, fixed request representation) — and
only if it is materially distinct from R_0_6. This is recorded as an unresolved decision (§22), not a planned
inclusion.

---

## 7. MODEL CANDIDATES

From the feasibility study §10/§14/§19. All are GGUF / llama.cpp `b10516` / Ollama-compatible (a hard
requirement Callosum's managed stack imposes). **No model is admitted or eliminated on leaderboard reputation**
— reputation informs neither Stage 0 nor Stage 1.

**Worker class (~1.5–4B):**
| Model | Params | License | Native ctx | ~Q4 weights |
|---|---|---|---|---|
| Qwen2.5-1.5B-Instruct **(control)** | 1.5B | Apache-2.0 | 32K | ~1.0 GB |
| Qwen3-1.7B | 1.7B | Apache-2.0 | 32K | ~1.1 GB |
| Qwen3-4B | 4B | Apache-2.0 | 128K (YaRN) | ~2.3 GB |
| Phi-4-mini | 3.8B | MIT | 128K | ~2.3 GB |
| Gemma 3 4B | 4B | Gemma (custom) | 128K | ~2.5 GB |
| Llama 3.2 3B | 3B | Llama community | 128K | ~1.9 GB |
| Ministral 3 (3B) | 3B | Apache-2.0 | long | ~1.9 GB |

**Orchestrator class (~7–14B; run where the hardware tier allows):**
| Model | Params | License | Native ctx | ~Q4 weights |
|---|---|---|---|---|
| Qwen3-8B | 8B | Apache-2.0 | 128K | ~4.7 GB |
| Ministral 3 (8B) | 8B | Apache-2.0 | long | ~4.7 GB |
| Qwen3-14B | 14B | Apache-2.0 | 128K | ~8 GB |
| Gemma 3 12B | 12B | Gemma (custom) | 128K | ~7 GB |
| Phi-4 (14B) | 14B | MIT | 16K | ~8 GB |

**Cloud references (bounded, calibration only — §11):** the existing Gemini provider path (default
`gemini-2.5-flash-lite`), optionally one Claude and/or one OpenAI model **only if it adds calibration rather
than model-shopping**. Cloud references are **not** hardware cells (§11, §12).

Every model above receives a Stage-0 verdict in §8. Not every listed model is assumed to survive to the full
factorial.

---

## 8. STAGE-0 ELIGIBILITY RULES (deterministic; NO inference)

Stage 0 is a **paper exercise** — no model is loaded or run. For each candidate freeze the following, and emit
one verdict ∈ {ELIGIBLE, ELIGIBLE_WITH_CONSTRAINTS, INELIGIBLE, UNKNOWN_REQUIRES_PREFLIGHT}:

1. exact model + version (and instruct/base variant);
2. immutable model identifier / GGUF blob hash where available (the control's is byte-identical to the
   A-series artifact: `sha256-6a1a2eb6…` == `EXPECTED_PREVIEW_MODEL_DIGEST`);
3. license (and whether it permits *bundling* vs *user-download-only*);
4. GGUF source (publisher/repo);
5. exact quantization candidate (Q4_K_M primary; Q5_K_M for borderline-fit; Q8 KV-cache option on the 7–8B
   tier);
6. llama.cpp `b10516` / Ollama compatibility;
7. structured-output support (grammar / `response_format`) — *declared* support, confirmed only at preflight;
8. model context limits (native + any RoPE/YaRN extension);
9. realistic **total runtime memory** estimate = **weights + KV cache + overhead** at the evaluated context
   (feasibility §9 formula) — **never GGUF size alone**;
10. expected JUNO fit (8 GB VRAM; system-RAM offload for 12–14B);
11. expected Apple-Silicon fit (16 / 24 / 32 GB unified);
12. any license/bundling blocker.

**Verdict rubric:**
- **ELIGIBLE** — pinned/proven artifact, permissive license, fits the primary hardware at realistic context,
  structured output confirmed in-repo. *Only the control currently qualifies unconditionally.*
- **ELIGIBLE_WITH_CONSTRAINTS** — admissible but carrying a named constraint (custom license → user-download +
  legal review before any bundling; short native context relative to the realistic Callosum envelope; requires
  system-RAM offload on JUNO). The constraint is recorded and feeds §12/§13, not an elimination.
- **UNKNOWN_REQUIRES_PREFLIGHT** — cannot be settled without a **no-score preflight** (load the exact GGUF on
  the exact runtime; confirm it loads at realistic context within memory; confirm it emits *complete, valid*
  structured output on a neutral, non-semantic smoke). Preflight runs no scored task and produces no fidelity
  data.
- **INELIGIBLE** — a hard, representation-independent blocker (no GGUF; incompatible with `b10516`/Ollama;
  cannot load at even the SHORT control context within the target memory; license forbids the research use).

**Provisional Stage-0 dispositions (to be locked at freeze):**
| Model | Verdict | Reason |
|---|---|---|
| Qwen2.5-1.5B (control) | **ELIGIBLE** | Pinned, proven, byte-identical to the A-series artifact; Apache-2.0; trivial JUNO fit; structured output confirmed on Ollama (`response_format`). |
| Qwen3-1.7B / Qwen3-4B / Ministral-3-3B | **UNKNOWN_REQUIRES_PREFLIGHT** | Apache-2.0 and fit fine on paper, but exact GGUF identity + `b10516`/Ollama structured-output completion unproven in-repo. |
| Phi-4-mini (3.8B) | **UNKNOWN_REQUIRES_PREFLIGHT** | MIT (bundling-friendly); paper-fit fine; artifact/structured-output preflight required. |
| Gemma 3 4B | **ELIGIBLE_WITH_CONSTRAINTS** + preflight | Custom Gemma license → user-download, legal review before bundling; else fits; artifact preflight required. |
| Llama 3.2 3B | **ELIGIBLE_WITH_CONSTRAINTS** + preflight | Llama community license (attribution/AUP/700M-MAU) → user-download, legal review before bundling; artifact preflight required. |
| Qwen3-8B / Ministral-3-8B | **ELIGIBLE_WITH_CONSTRAINTS** | Apache-2.0; fit on JUNO only with reduced context and/or Q8 KV (weights ~4.7 GB + KV); comfortable on 16 GB Apple Silicon. Artifact preflight required. |
| Qwen3-14B / Gemma 3 12B | **ELIGIBLE_WITH_CONSTRAINTS** | ~7–8 GB weights → JUNO needs **system-RAM offload** (slow, dated CPU); Gemma also carries the custom-license constraint. Runnable, flagged. |
| Phi-4 (14B) | **ELIGIBLE_WITH_CONSTRAINTS** | MIT; **16K native context** is short vs the realistic Callosum envelope (§13) — a real constraint on the orchestrator role; JUNO needs offload. |
| Gemini (+ optional Claude/OpenAI) | Reference, not a hardware cell | Admitted under §11 policy only. |

No model is eliminated at Stage 0 on reputation; the only INELIGIBLE path is a hard mechanical/license blocker,
and none of the listed models hits it on current facts.

---

## 9. STAGE-1 SCREEN DESIGN (defined; DO NOT RUN)

**Purpose:** cheaply remove *clearly unsuitable* candidates before the expensive full factorial — **without
biasing the model × representation interaction test** (methodological correction #1).

### 9.1 The bias hazard and the rule that prevents it
If Stage 1 eliminated a model on a *semantic* screen run under **one** representation (e.g., R_CONTROL alone),
it could cut a model precisely because it *needs* R_0_6 — biasing EQ3 before Stage 2 ever runs. Therefore:

- **Default elimination levers are REPRESENTATION-INDEPENDENT mechanical/runtime failures only.** A model is
  eliminated at Stage 1 only for: (a) failure to load at the realistic Callosum context within the target
  memory; (b) inability to produce **any complete, schema-valid** structured output on a neutral,
  non-semantic structured-output smoke (the FORMAT capability, tested identically for all); (c) **catastrophic
  latency** exceeding a pre-registered ceiling (a single orchestration-scale call exceeding the LATENCY.md
  600 s local-inference bound, or exceeding a pre-registered warm ceiling `L_screen`); (d) runtime
  instability / crash. These are properties of the *model+runtime+hardware*, not of any representation.
- **Semantic elimination, if used at all, must be REPRESENTATION-COMPLETE and CONSERVATIVE.** A model may be
  eliminated on a semantic floor **only if** it fails a **pre-registered multi-item minimum bar under *every*
  representation package that will enter Stage 2** — i.e., no representation available rescues it.
  Consequently, **semantic elimination is itself gated on R_0_6 being frozen**; before R_0_6 exists, Stage 1
  may eliminate on mechanical/runtime grounds *only*. **One semantic miss is never sufficient** to eliminate.
- The frozen semantic screen items are still *run* (under every available package) to **characterize**
  candidates and to compute the mechanical structured-output-**completion** rate — but their role is
  description, not (by default) elimination.

### 9.2 Frozen screen contents (the brief's required minimum)
A **small** frozen subset of *actual* Callosum orchestration tasks (not generic leaderboard items), each with
frozen inputs / representation package(s) / prompt / temperature 0 / seed 42 / context / output budget /
quantization / scoring / one-run-no-retry:
1. broad/narrow **scope classification**;
2. **obligation / request preservation** (scored against the external referents, §14);
3. **≥1 relationship / operation preservation** case;
4. **exact specialist-construct preservation** (e.g., a named instrument/scale/region survives verbatim);
5. **structured-output completion** (valid AND non-truncated).

### 9.3 Elimination criterion (pre-registered, conservative)
- **Mechanical/runtime (hard, representation-independent):** any of 9.1(a)–(d) → **ELIMINATED**, recorded as a
  mechanical failure (§16), not repaired.
- **Semantic floor (soft, representation-complete, R_0_6-gated):** ELIMINATED only if the candidate misses the
  pre-registered multi-item minimum bar **under every** Stage-2 representation package. The bar is a *floor to
  clear*, not a ranking key; survivors are **not** ranked by Stage-1 score ("no ranking by vibes"). The exact
  bar (how many of the screen items, at what fidelity) is a value to lock at freeze (§22).

Everything in Stage 1 is frozen before any inference; each cell is evaluated once; a mechanically-failed cell
is recorded as failure, never silently rerun (§16).

---

## 10. STAGE-2 FULL EXPERIMENT (defined; DO NOT RUN)

**Population:** Stage-1 survivors only. **Design:** every surviving model × every frozen representation package
(R_CONTROL, R_0_6) under identical task conditions, on the primary hardware substrate (JUNO), one evaluation
per cell.

**Tasks — Callosum's real Ask control plane (not generic leaderboards):** decomposition / obligation
preservation; scope selection (narrow vs broad); minimum-sufficient-context selection (the A/B/C/D/E envelope
task from the control-plane pivot); source-local proposition extraction under the verbatim-quote constraint;
coverage/gap interpretation; terminal synthesis. Each task's inputs are frozen; the verifier is unchanged.

**Inputs (frozen before any inference):** the two frozen questions **q_aib** (SHA `6e037bab…`, 13 external
source-obligation referents) and **q_builtenv** (SHA `36e4623e…`, 11 referents), both raw==trimmed; **plus a
small held-out set** chosen and frozen **before** inference (§17). No large synthetic benchmark is created.

**Primary outcomes (grouped; correctness kept separate from performance — §14):**
- **REQUEST FIDELITY** — preserved / drifted / starved per obligation referent; relationships & operations
  preserved; exact target/construct identity; open-request preservation; qualifiers / populations / measurement
  constraints; invention / answer-substitution.
- **MECHANICAL RELIABILITY** — structured-output **validity**; structured-output **completion** (non-truncation);
  truncation events; retries required (**prohibited** in the primary analysis — a retry-needing cell is a
  failure, §16).
- **PERFORMANCE** — cold latency; warm latency; tokens/sec; peak VRAM; peak RSS / system RAM; actual context
  used; KV-cache configuration (local cells only; cloud gets service-level latency only, §11/§14).
- **CONTAMINATION** — unsupported-answer insertion; target generalization; lexical corruption; unsupported
  connective synthesis where applicable (the terminal-fork "honored the sealed ledger vs invented domain facts"
  behavior).

**Per-question, never averaged.** Every outcome is reported separately for q_aib, q_builtenv, and each held-out
item; the divergent fidelity profiles (A-series) make averaging misleading.

**R_CONTROL is runnable now; R_0_6 cells wait on §18.** Stage 2 may produce the complete R_CONTROL column as a
standalone partial result; the interaction analysis (EQ3) is computed only once both columns exist.

---

## 11. CLOUD REFERENCE POLICY

Cloud models (Gemini; optionally one Claude and/or OpenAI) are **calibration references and optional
orchestration providers — NOT privileged ground truth, and NOT hardware-equivalent cells.**

- **Identical semantic inputs, representation package, output contract, and scoring** as the local cells (the
  staged pipeline's dual-terminal design already feeds one sealed ledger to multiple providers).
- **Minimal required provider calls;** no cloud retries unless the protocol permits the *same* retry allowance
  for **every** model (it does not — §16 prohibits retries in the primary analysis, so cloud gets none either).
- **Not a hardware cell (methodological correction #5).** Cloud memory characteristics are **not measured or
  compared** — there is no VRAM/RSS/KV figure for a hosted model. Cloud **latency is interpreted as
  service-level** (network + queue + provider), explicitly *not* local-runtime performance, and is never placed
  on the same axis as a local cell's cold/warm latency.
- **Egress gate.** Any cloud call runs only under the existing explicit egress consent (invariant #3); the
  benchmark honors "no silent cloud fallback."
- **Accessibility framing (load-bearing).** The architecture must preserve **weak hardware + focal cloud
  orchestration as a first-class accessibility path**. A stronger local path is **ADDITIVE, not exclusionary**.
  Cloud's role here is to calibrate how far a local candidate sits from a strong hosted model — never to define
  the pass bar (§15: success is not "beats Gemini").

---

## 12. HARDWARE PLAN

**Primary near-term substrate: JUNO** — Debian 12; Intel i7-8700 (6c/12t, 2017); NVIDIA RTX 3050 8 GB VRAM;
CUDA; Ollama. Measured anchor: ~28 tok/s on a quantized 7B. JUNO is **architecturally different per axis**
(GPU-above the typical integrated-graphics research laptop; CPU-below modern machines; 8 GB-capacity-capped vs
Apple's larger unified memory) and is **explicitly not a proxy for all users** — above all, not a proxy for
Apple Silicon (the most common researcher accelerator).

**Replication cells (finalist-only, later):**
- **APPLE BASELINE** — 16 GB Apple Silicon.
- **APPLE MAINSTREAM** — 24–32 GB Apple Silicon (if available).
- **ACCESSIBILITY FLOOR** — integrated-graphics / CPU-only / ~8 GB machine, where practical.

**Rule:** the full model × representation matrix runs on **JUNO**. **Hardware replication happens only for
finalists** (candidates that clear the §15 thresholds on JUNO), **unless a hardware interaction is itself the
object of study**. Do **not** require every (model × representation) cell on every platform — that multiplies
cost without answering the primary questions, and JUNO's idiosyncrasies (§7 feasibility) mean a cross-platform
claim needs an Apple-Silicon reference *before* it is made, not a full Apple matrix. Record full host state per
LATENCY.md §15 for every local cell.

---

## 13. CONTEXT / MEMORY PLAN

**"Loads" is never "viable."** Every memory figure is **total runtime memory at the evaluated context** =
weights + KV cache + overhead (feasibility §9), never GGUF size. KV cache is model-dependent via grouped-query
attention (Qwen's aggressive GQA is far more KV-efficient than Llama-family) and may be **Q8-quantized** to
halve it on the borderline 7–8B tier.

Three context settings, frozen:
- **SHORT CONTROL CONTEXT** — just enough for the bounded orchestration packet (a floor that even the
  Accessibility-Floor tier could host); establishes best-case latency/memory.
- **REALISTIC CALLOSUM CONTEXT** — the real Ask/control-plane envelope. Anchor to the managed Local-AI
  Preview's production context window (**12,288 tokens**) and the **current production output cap** (frozen at
  the shipped value; the cap lives in four places that must move in lockstep — Rust `PREVIEW_OUTPUT_TOKENS`,
  Python `expected_output_tokens`, the cache signature, and `tools/run_local_ai.py` — and is not changed by
  this benchmark). This is the setting the pass/fail thresholds (§15) are judged at.
- **STRESS CONTEXT (optional)** — a larger envelope to probe headroom and the KV/offload cliff (especially the
  8B-on-JUNO and 14B-offload cases, and Phi-4-14B's 16K native ceiling).

For each (model × context): estimate then **runtime-measure** weights, KV cache, overhead, peak memory
(VRAM + RSS), and latency (cold/warm). A model that "loads" at REALISTIC context but cannot perform the
orchestration task within the latency budget at that context has **not** passed (§15).

---

## 14. METRICS

Correctness and performance are reported separately (LATENCY.md; never blend a fidelity number with a latency
receipt). Fidelity is scored against the **external evaluation referents** (the 13/11 source obligations and
the frozen relationship/operation/construct/open-request labels) — which are *not* part of any representation
package (§6, correction #4).

**A. REQUEST FIDELITY (per obligation referent, per question, never averaged):**
- obligation state: **preserved / drifted / starved** (the A-series scoring);
- **relationships** preserved (e.g., brain→behavior, area→role mappings);
- **operations** preserved (the requested analytic/comparative operation);
- **exact target / construct identity** (named region/instrument/scale survives verbatim);
- **open-request preservation** (open-ended "and other findings" scope not silently instantiated or dropped);
- **qualifiers / populations / measurement constraints** preserved;
- **invention / answer-substitution** count (an obligation answered with content not requested).

**B. MECHANICAL RELIABILITY (per call):**
- structured-output **validity** rate; structured-output **completion** (non-truncation) rate; truncation
  events; **retries required** (prohibited in primary analysis — presence = failure, §16).

**C. PERFORMANCE (local cells only):**
- cold latency; warm latency; tokens/sec; peak VRAM; peak RSS / system RAM; actual context used; KV-cache
  configuration. **Cloud cells: service-level latency only** (network/queue/provider) — no memory metrics, not
  comparable to local runtime (correction #5).

**D. CONTAMINATION:**
- unsupported-answer insertion; target generalization (a specific target broadened into a generic one);
  lexical corruption of a specialist term; unsupported connective synthesis (asserting a relation the ledger
  does not contain). Scored especially at the **terminal-synthesis fork** given a sealed ledger.

Every metric is attributable to a (model × representation package × hardware × context) cell and to a specific
frozen input.

---

## 15. PRE-REGISTERED SUCCESS THRESHOLDS

**Priority order (fixed; not benchmark-score superiority):** (1) preservation & contamination; (2) mechanical
reliability; (3) realistic-context fit; (4) low-frequency latency. **Success is never "beats Gemini"** — a
viable local orchestrator may be slower and numerically weaker than cloud and still pass (§11).

All thresholds are judged at **REALISTIC CALLOSUM CONTEXT** (§13), **per question (never averaged)**, on
**both** frozen questions plus the held-out set, **one run, no retries** (§16). Because n is small
(13 and 11 obligation referents), each pass claim is reported **with a binomial (Wilson) lower bound**, and a
threshold met on one question but not the other is **not** a pass. Candidate numeric values below are the
**pre-registration proposal, to be locked at freeze** (§22); they are deliberately strict on the honesty axes
and permissive on latency.

**WORKER PROMOTION** (promote a >1.5B model as the new baseline *worker*, compared to the Qwen2.5-1.5B control
**under the same representation package**, so the comparison is a clean capability contrast):
- **Contamination = 0** — zero unsupported-answer insertions / fabricated domain facts on both questions
  (hard gate; no tolerance).
- **Structured-output validity AND completion ≥ 99%** of calls; **0 retries**.
- **Preserved-obligation count does not regress** vs the control on either question, **and strictly improves on
  at least one** with **no increase in inventions/answer-substitutions** — and, where the worker tasks are in
  scope, **reduces** the localized mechanical failure classes (`quote_not_verbatim` / paraphrase-drift /
  mis-gate).
- **Fits REALISTIC context** on JUNO **and** the 16 GB Broad-Baseline reference within measured peak memory.
- **Warm per-call latency ≤ `B_worker`** (a bounded, high-volume role → a tight budget; proposed a few seconds
  warm, value locked at freeze).

**LOCAL ORCHESTRATOR VIABILITY** (adopt a fully-local orchestrator for the core tier):
- **Contamination = 0** on both questions at the terminal fork given a sealed ledger (hard gate).
- Clears a **pre-registered fidelity floor** on **both** frozen questions under **≥1 representation package**
  (the target being R_0_6): proposed floor — **preserved ≥ drifted+starved** on the obligation referents *and*
  relationships/operations/exact-construct preserved above a locked count, with Wilson lower bounds reported.
- **Structured-output validity + completion ≥ 99%; 0 retries.**
- **Fits REALISTIC context** on **≥ the Broad Researcher Baseline (16 GB)** reference within measured peak
  memory (JUNO fit is sufficient but not necessary — JUNO is idiosyncratic).
- **Low-frequency latency within budget `B_orch`** — orchestration runs ~once/query (+ maybe once for
  gap/escalation), so `B_orch` is generous (proposed **≤ ~15 s warm per call**, higher cold tolerated); a
  candidate is **not** disqualified on per-chunk-latency grounds.
- **Not contingent on matching or beating cloud.**

**REPRESENTATION IMPROVEMENT** (conclude a representation package helps, EQ2):
- Holding model fixed, package R (vs R_CONTROL) **increases preserved obligations and/or reduces
  starved+drifted and/or reduces contamination** on **both** questions, with **no regression** in structured
  validity/completion. An **interaction** (EQ3) is declared when this improvement is materially larger at
  higher capability, or present only above a capability floor — judged by the §19 rules, per question.

A candidate that clears WORKER PROMOTION or LOCAL ORCHESTRATOR VIABILITY on JUNO becomes a **finalist** and only
then enters hardware replication (§12).

---

## 16. FAILURE / NO-RETRY RULES

- **First-run freeze.** Freeze everything (§17) before any inference. **No tuning after a disappointing
  result** — not prompts, not thresholds, not the questions, not scope policy, not verifier thresholds.
- **One evaluation per cell.** Each (model × representation package × hardware × context) cell is run **once**.
- **Retries are prohibited in the primary analysis.** A cell that would need a retry is a **failure** and is
  recorded as one. (A *genuine technical failure* — provisioning fault, tunnel drop, OOM from an environment
  mistake, not a model behavior — may be re-attempted under a pre-declared technical-retry policy, and the
  re-attempt is logged as such; a *model/task* failure is never retried.)
- **If a cell fails mechanically, record the failure; do not silently repair and rerun.** A truncation, an
  invalid-JSON, an OOM-at-context, a crash, or a latency-ceiling breach is a datum, not a bug to hide.
- **No mid-run substitution.** Never substitute cloud for a failing local cell mid-run; never swap a model's
  quantization or context to rescue a cell.
- **"Loads" ≠ "passes."** A successful load with a failed task is a failure of the task.
- **Contamination is disqualifying**, not a deduction — a fabricated domain fact against a sealed ledger fails
  the honesty gate outright (invariant #1 lineage).

---

## 17. ARTIFACT / HASH FREEZE PLAN

Before any inference, produce a **freeze manifest** (`freeze_manifest.json`) hashing/pinning every input, so a
disappointing result cannot be laundered by a quiet change:

- **Questions:** q_aib (`6e037bab…`), q_builtenv (`36e4623e…`), each with raw==trimmed assertion; **held-out
  set** items, each hashed, frozen before inference.
- **Evaluation referents:** the 13/11 source-obligation inventories + the frozen relationship / operation /
  exact-construct / open-request / qualifier labels (external to any representation — §6), each hashed; DEV vs
  EVAL split declared (only DEV may inform a ≤1 permitted prompt clarification *before* freeze; EVAL is
  post-hoc only, no accuracy language).
- **Representation packages:** for **R_CONTROL**, the exact `query_planner` Facet{label,query} prompt/template
  + schema + preprocessing, pinned to a git SHA; for **R_0_6**, the artifacts from §18 with their hashes.
- **Prompts / templates / schemas / deterministic preprocessing** for every package.
- **Model identifiers:** exact version + immutable GGUF blob hash per model (control = `sha256-6a1a2eb6…`).
- **Quantizations** per model; **context settings** (SHORT / REALISTIC / STRESS token counts); **output caps;
  seeds (42); temperature (0)**; runtime + structured-output mechanism per hardware (Ollama `response_format`
  vs llama.cpp `b10516` top-level `json_schema`).
- **Scoring rubrics** (the A-series fidelity rubric; the asymmetric minimum-sufficient-context scoring;
  contamination rubric), each versioned/hashed.
- **Pass/fail thresholds** (§15) with their locked numeric values.
- **Stage-1 elimination rules** (§9), including the R_0_6-gated semantic-floor rule.
- **Cloud-reference rules** (§11): providers, models, call budget, egress-consent state.
- **Corpus:** a **read-only DB copy** (path + row counts + schema version), source-before/after SHA-256
  unchanged; JUNO/model identity (Ollama tag `callosum-managed-local`, GGUF hash) recorded.
- **Environment:** git HEAD, embedding-model id, verifier thresholds, full host state per LATENCY.md §15.

Per-cell artifacts carry the cell key + the frozen-input hashes so every number is reproducible and every
prune/failure carries `{decision, reason_code, inputs, kept}`. Nothing is tuned after the freeze.

---

## 18. R_0_6 CODEX HANDOFF CONTRACT

R_0_6 is frozen into the benchmark **only** when the concurrent Codex Ask-CLI 0.6.0 task delivers **all** of the
following, with hashes, so it can be pinned into §17's freeze manifest **without reconstruction or interpretation
by the benchmark author**:

1. **Representation specification** — a precise, self-contained statement of the R_0_6 request representation:
   what it emits (its schema), its scope policy, and its deterministic preprocessing/machinery — described as a
   *package* (§3).
2. **Exact prompts / templates** — byte-exact, with any per-stage variants, pinned to a git SHA.
3. **Schema(s)** — the structured-output schema(s) the package uses, with the structured-decoding mechanism
   (grammar / `response_format`) it assumes.
4. **Frozen benchmark inputs it consumes** — confirmation it runs on the *same* frozen q_aib / q_builtenv /
   held-out inputs (§17), byte-identical hashes; any additional inputs it requires, frozen.
5. **Source / request-ancestry artifacts** — the source-anchoring / evidence-conditioning machinery
   (decomposition, source-unit derivation, context envelopes, obligation-emission) it depends on, specified and
   pinned.
6. **Obligation / coverage representation** — how the package *emits* obligation/coverage structures (kept
   distinct from the external evaluation referents of §6/§14).
7. **Relevant hashes** — a manifest of every prompt/schema/module/artifact hash for R_0_6.
8. **Tests** — the package's own passing test suite (e.g., a `selfcheck`), with counts.
9. **0.6.0 acceptance report** — the frozen acceptance evidence (what was run, on what corpus copy, with what
   metrics), so R_0_6's provenance is unambiguous and historically grounded (the same bar that disqualified
   R_SOURCE, §6).
10. **Any unresolved known defects** — an explicit list of open issues / caveats in the 0.6.0 representation,
    so the benchmark records them rather than discovering them mid-run.

Until items 1–9 are delivered and pinned, R_0_6 is empty, the interaction cells (EQ3) cannot run, and the
readiness verdict stays **READY EXCEPT FOR R_0_6** (§23). **The benchmark author must not inspect, interfere
with, or pre-empt the active Codex task** to obtain these — they arrive as a handoff.

---

## 19. ANALYSIS / INTERPRETATION RULES (pre-registered)

Computed per question (never averaged), per size class (worker vs orchestrator), with Wilson bounds on every
rate. Map the observed (fidelity × reliability × contamination) pattern across the model × package cells to one
of the pre-declared readings:

1. **Model main effect (H_model)** — stronger models improve outcomes under **both** packages → capability
   matters largely independent of representation.
2. **Representation-package main effect (H_repr)** — R_0_6 improves outcomes across **all** model sizes →
   package matters largely independent of capability.
3. **Interaction (H_interaction, focal)** — capability helps materially more (or only) under R_0_6, **or** R_0_6
   helps materially more (or only) above a capability floor → the *pairing* is the cause; neither factor alone
   explains it. This is the reading the confounded A-series could not reach.
4. **Ceiling (H_ceiling)** — small and larger local models are equivalent under the best package → capability
   is not the binding constraint at these sizes for this narrow job.
5. **Cloud-only advantage (H_cloud_only)** — a cloud reference materially exceeds every local candidate on
   fidelity/contamination under the same package → the local-orchestrator leg is not yet viable; small-local +
   focal-cloud remains the (additive) path.
6. **Local sufficiency (H_local_sufficiency, target)** — ≥1 local candidate clears the §15 floor on both
   questions even if cloud is numerically stronger → a fully-local orchestrator is viable for the core tier.

**Binding interpretation constraints:**
- **Success is defined against the §15 floor, not against cloud.** Cloud is calibration, not the bar (§11).
- **Format ≠ semantics.** A structured-output-completion improvement is a mechanical result, never counted as a
  fidelity/semantic gain.
- **Identifiability (correction #2).** Report effects as *model-conditional-on-package*, *package-across-model*,
  and *interaction*. **Do not** claim the design isolated *prompt* from *representation* from *preprocessing* —
  it cannot; those are bundled in a package.
- **Per-question divergence is a finding, not noise.** If q_aib and q_builtenv disagree (as in the A-series),
  report both and do not collapse them.
- **A confounded-looking result is reported as confounded.** If only R_CONTROL ran (R_0_6 not yet frozen), the
  result is a *model main-effect-under-current-representation* finding only — the interaction is explicitly
  marked *not yet estimable*.
- **Contamination overrides.** Any fabrication against a sealed ledger fails the candidate regardless of other
  metrics.

---

## 20. STOP CONDITIONS

- **R_0_6 not delivered** → run the R_CONTROL column only (partial result); **stop** before claiming any
  interaction; hold the verdict at READY EXCEPT FOR R_0_6.
- **Structured output cannot be enforced on the chosen runtime/topology** (the Ollama top-level-`json_schema`
  gotcha) → **stop and report**, do not silently revert to unconstrained JSON (that would reintroduce the
  controlled FORMAT variable).
- **Managed local model cannot be provisioned** in the benchmark environment → **stop and report BLOCKED**; do
  **not** substitute a cloud provider for a local cell.
- **A model is INELIGIBLE / fails preflight** → record and drop it from the roster; do not improvise a
  substitute mid-run.
- **All Stage-1 mechanical eliminations remove the entire orchestrator class** → report that JUNO cannot host
  the orchestrator class at realistic context, and confine conclusions to the worker class + the Apple/finalist
  replication plan.
- **Freeze integrity broken** (an input hash changes) → **stop**; a run on unfrozen inputs is void.
- **Contamination observed on the control under R_CONTROL** → still complete the run (it is a datum), but flag
  that even the incumbent fabricates, which strengthens the case for the honesty gate rather than weakening the
  benchmark.
- **Completion:** once each planned cell has been evaluated once, **freeze all artifacts and stop** — no tuning
  pass, no "one more run."

---

## 21. EXECUTION CHECKLIST (for the separately-approved execution pass)

1. Obtain explicit approval to execute (this document does not authorize inference/downloads).
2. Provision the managed local model on JUNO (`callosum-managed-local`, GGUF `6a1a2eb6…`) via the documented
   detached-tunnel + descriptor path; verify structured output via a **neutral, non-semantic** smoke
   (`response_format`); if it cannot be enforced → STOP/REPORT (§20).
3. **Stage 0:** fill the eligibility table (§8) for every candidate; run **no-score preflights** for every
   UNKNOWN_REQUIRES_PREFLIGHT model (load + memory-at-context + structured-output-completion only).
4. Freeze the manifest (§17): questions, held-out set, referents, both representation packages (R_0_6 per §18),
   prompts, schemas, model ids + GGUF hashes, quantizations, contexts, seeds, caps, rubrics, thresholds,
   Stage-1 rules, cloud rules, corpus copy, host state.
5. **Stage 1:** run the frozen screen; eliminate on **mechanical/runtime** grounds by default; apply the
   **representation-complete, conservative, R_0_6-gated** semantic floor only if R_0_6 is frozen; record every
   elimination as a datum; do **not** rank survivors.
6. **Stage 2:** run each survivor × {R_CONTROL, R_0_6} on JUNO at SHORT / REALISTIC (/ STRESS) context, once
   per cell; capture fidelity / mechanical / performance / contamination; **no retries** (§16).
7. Run the **cloud references** on the identical sealed inputs / contract / scoring (service-level latency only;
   no memory comparison; egress consent recorded) (§11).
8. Score against the frozen rubrics/referents; compute the §15 thresholds per question with Wilson bounds;
   identify finalists.
9. **Finalists only:** run the Apple-baseline / Apple-mainstream / accessibility-floor replication cells (§12).
10. Apply the §19 interpretation rules; write the results report; **freeze and stop** — no tuning.

---

## 22. UNRESOLVED DECISIONS (values to lock at freeze, or later approvals)

- **R_0_6 content** — awaits Codex's §18 handoff. The single blocker to full execution.
- **R_SOURCE re-admission** — OMITTED (§6). Re-admit **only** if a clearly-specified, executable, historically
  grounded source-anchored package with unambiguous provenance, **materially distinct from R_0_6**, is
  identified and frozen before the Stage-2 freeze. Not planned; not reconstructed for completeness.
- **Stage-1 semantic-floor bar** — the exact multi-item minimum (how many screen items, at what fidelity, under
  every package) to lock at freeze; conservative by default.
- **Latency budgets** — `L_screen` (Stage-1 catastrophic-latency ceiling), `B_worker`, `B_orch` — propose a few
  seconds warm for the worker, ≤ ~15 s warm for the orchestrator; lock at freeze.
- **Fidelity floor numerics** — the preserved-vs-(drifted+starved) count and the relationship/operation/
  construct counts for LOCAL ORCHESTRATOR VIABILITY; lock at freeze with Wilson-bound reporting.
- **Held-out set** — its size and contents (kept small; frozen before inference).
- **Cloud reference breadth** — Gemini is in; whether to add one Claude and/or one OpenAI model turns on whether
  it adds calibration rather than model-shopping; decide before freeze.
- **Structured-output mechanism per runtime** — Ollama `response_format` vs llama.cpp `b10516` top-level
  `json_schema`; pin per hardware cell (transfer between runtimes is itself an open question the feasibility
  work flagged).
- **Quantization for borderline-fit models** — Q4_K_M vs Q5_K_M, and Q8-KV on the 7–8B tier; pin per model at
  freeze.
- **Apple-Silicon availability** — whether a 24–32 GB Mainstream unit is available for finalist replication.

---

## 23. GO / NO-GO READINESS VERDICT

**READY EXCEPT FOR R_0_6.**

The protocol is fully specified and executable **now** for the R_CONTROL column across the entire model axis:
Stage-0 eligibility rules, the bias-safe Stage-1 screen, the Stage-2 task battery, the frozen questions +
referents, the metrics, the numeric thresholds, the freeze/hash discipline, the no-retry rules, the cloud
policy, the hardware plan, and the interpretation rules are all in place. No model/runtime fact blocks it
(every candidate is at worst UNKNOWN_REQUIRES_PREFLIGHT or ELIGIBLE_WITH_CONSTRAINTS — a resolvable no-score
preflight, not a design blocker), and no experimental-design gap remains (the confound is broken by the crossed
design; identifiability is honestly bounded; R_SOURCE was audited and omitted rather than reconstructed).

The **one** thing outstanding is the reserved **R_0_6** representation condition, which the concurrent Codex
Ask-CLI 0.6.0 task must freeze and hand over per §18. Because the **interaction test (EQ3) is the whole point**
and an interaction cannot be measured with a single representation, the full experiment cannot conclude until
R_0_6 lands — while the R_CONTROL model-axis column can run in the interim as a legitimate standalone partial
result. This is the expected and legitimate outcome the brief anticipated.

*(Not the verdict: READY TO EXECUTE — false while R_0_6 is empty; BLOCKED BY MODEL/RUNTIME FACTS — no such
blocker exists, only resolvable preflights; BLOCKED BY EXPERIMENTAL DESIGN — the design is complete and the
confound is addressed; MORE RESEARCH REQUIRED — the feasibility study already supplied the antecedent research
and this document is execution-ready but for one handoff.)*
