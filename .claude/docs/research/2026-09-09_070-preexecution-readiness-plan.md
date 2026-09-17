# Callosum 0.7.0 — Pre-Execution Readiness Plan

**Date:** 2026-09-09
**Type:** Pre-execution readiness architecture / scoping. **Analysis and precommitment only — no
production behavior, no model inference, no downloads, no scored 0.7 benchmark cell, no edit to the
0.7 preregistration, no freeze of R_0_6, no inspection/use of the sealed claim-representation arm
key, no substitution for the pending human adjudication, nothing staged or committed.** This
document *decides what can be locked before R_0_6 exists*; a separate, explicit approval executes any
of it.

**Companion to (does not edit):**
- `.claude/docs/research/2026-09-09_local-orchestrator-benchmark-preregistration.md` — the 0.7
  MODEL × REPRESENTATION PACKAGE design (the "prereg").
- `.claude/docs/research/2026-09-09_ask-060-semantic-loss-postmortem.md` — the claim-formation
  boundary analysis that motivated the claim-representation isolation.
- `REPORT_PRE_ADJUDICATION.md` (claim-representation isolation, resumed) — the 492 first
  observations, read; its **sealed arm key was NOT opened**.
- `.claude/SCRATCH.md`; `.claude/LATENCY.md`; the `experiments/ask_cli*` harness + calibration code.

**Concurrent lane.** A Codex task is performing the Stage-0 factual/model-eligibility audit
(candidate-model identity, licensing, artifact compatibility, mechanical-preflight requirements) in a
private temp directory. This document **does not duplicate or depend on** its in-progress files, and
its per-model verdicts/quantization pins **defer** to that audit. **Codex Stage-0 remains pending and
must be reconciled before any implementation or preflight execution.**

> **Epistemic discipline (whole document).** The claim-representation isolation produced *mechanical*
> results only; it has **no human labels**, so **no semantic winner exists** and none is asserted
> here. These distinctions are load-bearing and never smoothed:
> - schema-valid ≠ semantically faithful
> - anchor validity ≠ interpretation validity
> - quotation fidelity ≠ proposition fidelity
> - mechanical completion ≠ source fidelity
> - "loads / parses" ≠ "passes"
> This document never says an arm "won" or "failed," never uses the Arm-2 anchor result to choose
> R_0_6, and never treats a procurement configuration as a population-prevalence claim.

---

## Precise status of the 0.7 preregistration (used throughout)

The 0.7 preregistration is an **authored, preserved design document** — its factorial shape
(MODEL × {R_CONTROL, R_0_6}), identifiability boundary, metric families, no-retry rules, and
interpretation rules are fixed and are **not** re-opened here. It is **not an execution freeze**: it
explicitly leaves substantive freeze-time values open (its §22 "unresolved decisions": latency
budgets, held-out set, fidelity-floor numerics, cloud breadth, quantization pins, Stage-1
semantic-floor bar, structured-output mechanism per runtime).

This readiness companion **resolves the choices the prereg left open** and records them in a **new
pre-execution freeze artifact, `freeze_manifest_v0`** — it does **not** retroactively pretend those
values were already frozen, and it does **not** reinterpret the prereg's historical state. Where a
value cannot yet be justified without observing scored outcomes or without a product decision, it is
reported as an explicit open decision, never manufactured.

---

## 1. EXECUTIVE VERDICT

**Nearly all non-semantic 0.7 infrastructure is safe to design, build, and freeze now. Only three
things must wait: the R_0_6 representation-package slot, the R_0_6-dependent (interaction) cells, and
any scored semantic inference.**

The critical path to a *concluding* 0.7 run passes through the **blinded human adjudication**, which
is the longest pole and is entirely parallel to — and unblocked by — the non-semantic preparation.
Locking the outcome-independent decisions **now**, before any semantic score is observed, is exactly
what reduces researcher degrees of freedom that could otherwise be (even unconsciously) tuned to
results later. The preparation is cheap, reversible, and — because no score is seen — structurally
un-biasable.

**Decision: READY TO BUILD NON-SEMANTIC 0.7 INFRASTRUCTURE** (see §23), contingent on: no scored
inference; reconciliation with the Codex Stage-0 audit before any preflight; and the R_0_6 slot
staying intentionally empty.

---

## 2. CURRENT DEPENDENCY GRAPH

**Critical (semantic) path — must not be short-circuited:**
```
blinded human adjudication (492 labels)            ← PENDING, the longest pole
  → claim-representation candidate                  (only if labels favor a source-preserving rep)
  → integrate into a revised 0.6 package
  → separately-authorized bounded end-to-end 0.6 acceptance
  → if READY: freeze R_0_6
  → final 0.7 execution freeze (freeze_manifest with R_0_6 pinned)
  → 0.7 semantic benchmark, run once
```

**Parallel, outcome-independent path — buildable / freezable NOW:**
```
Codex Stage-0 eligibility audit (pending) ──┐→ reconcile roster / per-model quant pins
non-semantic infra: runner interface + R_CONTROL adapter + freeze-manifest machinery
  + offline scorer + per-cell artifact schema + held-out selection-procedure harness
outcome-independent freezes: latency framework, context (REALISTIC), quantization policy,
  cloud policy, Stage-1 = neutral-mechanical-only
                                            ┘→ freeze_manifest_v0 (all fields but the R_0_6 slot)
```

The two paths meet only at the **final 0.7 execution freeze**. Every item on the parallel path is
independent of *which* claim-arm the human labels favor and of *whether* R_0_6 ends up span-first —
so none of it can bias the future comparison, and all of it shortens the closure path once R_0_6
legitimately lands.

---

## 3. WHAT THE CLAIM EXPERIMENT CHANGES MECHANICALLY

The claim-representation isolation completed 492 first observations (164 units × 3 arms; no retries,
no neutral inference). Its **mechanical** findings — and only its mechanical findings — bear on 0.7
readiness:

- **Structured-output enforcement generalizes to the claim-formation stage.** Under matched
  free-paraphrase semantics, adding the established `response_format`/`json_schema` wrapper moved
  truncation 68→0 and whole-response JSON 10→164. This mechanically confirms the FORMAT-class fix
  beyond the selection stage — consistent with the prereg's design choice to hold FORMAT (structured
  decoding + adequate output budget) **constant**, because FORMAT is not the variable under study.
- **A richer typed 10-field schema still completes mechanically** (164/164 whole-JSON, schema-valid)
  at a **larger but bounded output envelope** (cap 823 vs the 192-token free-claim cap; +631 tokens,
  a pre-declared conservative one-token-per-UTF8-byte bound for the ten-field "cannot-tell" case).
- **That typed rep's exact-anchor contract is mechanically UNMET** (196 / 1376 required anchors
  resolve exactly). This is a **measured mechanical constraint** any eventual span-first/typed R_0_6
  must contend with — **not** a fidelity judgment, and not evidence that the representation is good or
  bad. Anchor existence ≠ interpretation validity; the human labels decide fidelity.

**Implication for 0.7 (flagged, not resolved — see §20):** the mechanical envelope gap (823 vs 192)
means that *if* R_0_6 turns out to be span-first/typed, it would structurally require a **larger
output budget** than R_CONTROL. That tensions the prereg's "output budget held CONSTANT across
cells" and becomes an identifiability decision to settle **before** any scored 0.7 inference.

**What this does NOT establish.** No semantic winner; no source-fidelity gain; no null/mixed/
uncertain retention verdict; no relation-endpoint verdict; no Qwen-capacity claim; and no basis for
choosing R_0_6. The Arm-2 anchor number is not a semantic adjudication and is not used as one here.

---

## 4. WHAT REMAINS SEMANTICALLY UNKNOWN

Everything the blinded human adjudication decides, and everything downstream of it:

- per-unit **source fidelity** against the exact source packet (the five-category rubric of §14);
- **distinct** null / mixed / uncertain retention;
- **relation-endpoint** preservation (nodes ≠ edges);
- whether a typed candidate annotation preserves the meaning free paraphrase mutated;
- therefore: whether R_0_6 should be span-first at all; R_0_6's **content**; the identity of the
  second representation condition; and the entire **interaction test (EQ3)** — which cannot even be
  posed with a single representation.

Until the labels exist, none of these may be pre-decided, previewed, or substituted for by any model
output.

---

## 5. SAFE-NOW / PREPARE-NOW / BLOCKED / FORBIDDEN MATRIX

Classes: **A** = safe to complete/freeze now (cannot reveal or depend on scored 0.7 semantics, not
contingent on R_0_6). **B** = safe to prepare now, freeze only after a dependency resolves. **C** =
blocked by human adjudication / R_0_6. **D** = must not occur before the final 0.7 freeze.

| 0.7 item | Class | Rationale |
|---|---|---|
| Stage-0 eligibility **rule/rubric** | **A** | Deterministic paper rule; outcome-independent. |
| Stage-0 per-model verdicts + no-score **preflight DESIGN** | **B (Codex-owned)** | Reconcile, don't duplicate. Preflight *execution* is a later gated step. |
| Latency **framework + role ordering + L_screen hard ceiling (600 s, documented)** | **A** | Structure/derivation is product-derived; 600 s is documented in LATENCY.md. |
| Latency **exact B_worker / B_orch / warm-L_screen values** | **REQUIRES PRODUCT DECISION** | No repo-justified number exists; name the smallest decision, do not invent. |
| Context **REALISTIC = production 12,288** | **A** | The single context of the primary semantic comparison. |
| Context **SHORT / STRESS** | **A (mechanical/sensitivity only)** | Feasibility/sensitivity conditions, NOT semantic factorial levels. |
| Quantization **a-priori rule** (Q4_K_M primary where available; mechanical-only deviations; KV separate) | **A** | Outcome-independent; per-model pins are Codex; reconcile before freeze. |
| Cloud-reference **policy** (Gemini-only; service-level latency; not a hardware cell) | **A** | Calibration policy; a 2nd provider is model-shopping risk. |
| Stage-1 screen → **neutral-mechanical-only, NO semantic items** | **A** | Even descriptive semantic output is observed outcome information. |
| Scoring machinery (5-category + co-occurring-flags rubric + offline scorer) | **A (specify+build)** | External referents + frozen rubrics; independent of R_0_6. *Running* it = C. |
| Per-cell artifact/receipt schema | **A (specify+build)** | Generalizes `15_run_manifest.json`; no inference. |
| Freeze-manifest machinery → **freeze_manifest_v0** (all fields but R_0_6) | **B** | NEW artifact; hashes questions, referents, R_CONTROL SHA, contexts, seeds, host-state, policies. |
| Benchmark runner (interface + R_CONTROL adapter + no-retry/failure-receipt scaffold) | **B** | R_0_6 enters only as a pluggable package adapter. |
| Held-out **selection procedure** (coverage criteria + deterministic corpus-presence receipt + negative-control designation) | **A** | Freeze the procedure before contents. |
| Held-out **exact contents** | **B (apply procedure now)** | Real scholar questions; corpus-presence via inspectable deterministic receipt; Cliff supplies domain context, not sole criterion. |
| Hardware **replication plan/policy** | **A** | JUNO full matrix + finalist-only Apple/floor; procurement = proxy, never prevalence. |
| R_0_6 package (§18 items 1–10) | **C** | adjudication → candidate → integration → acceptance → freeze. |
| R_0_6-dependent (EQ3 interaction) cells | **C** | An interaction needs two representations. |
| Running **any** scored benchmark cell (incl. the R_CONTROL column) | **D (not now)** | Scored semantic inference; R_CONTROL is its own separately-approved partial run. |
| Any Stage-1 semantic item / semantic elimination | **D (removed)** | Neutral-mechanical-only Stage-1 removes it entirely. |
| Inspect sealed key; substitute for adjudication; edit prereg; freeze R_0_6; stage/commit | **D (forbidden)** | Explicit task boundaries. |

---

## 6. BENCHMARK-RUNNER READINESS

**A generic runner can be prepared now, without knowing R_0_6** (design only in this task; build is
the recommended next step). R_0_6 enters the runner **solely as a pluggable representation-package
adapter behind a stable interface** — everything else is representation-agnostic.

Desired properties, all buildable now:
- **Explicit cell IDs** = `(model × representation_package × hardware × context × frozen_task_hash)`.
- **Representation-package adapter interface** — `R_CONTROL` implemented now via
  `query_planner.plan_query`'s `Facet{label, query}` (exercised as A1/A2 exercised it); `R_0_6` a
  named, empty, pluggable slot.
- **Model adapter interface** — one structured-decoding contract per runtime (Ollama
  `response_format`; llama.cpp `b10516` top-level `json_schema`), selected by cell, never silently
  swapped.
- **Hardware / context identity capture** — host state (LATENCY.md §15) recorded per cell.
- **One-run / no-retry enforcement** — a model/task failure is a datum; only a pre-declared genuine
  *technical* fault (provisioning/tunnel/OOM-from-environment) may re-attempt, logged as such.
- **Deterministic task ordering**; **failure receipts** `{decision, reason_code, inputs, kept}`;
  **no silent fallback** (never substitute cloud for a failing local cell, never swap quant/context
  to rescue a cell).
- **No semantic interpretation embedded in the runner.** The runner *records*; scoring is a separate
  offline pass over frozen artifacts (§14). This keeps the runner un-opinionated and re-runnable.

**Reuse:** `experiments/ask_cli/runtime.py` (staged execution + per-run manifest), the calibration
`structured_output.py` `response_format`/`json_schema` `strict:true` wrapper (the FORMAT control),
`run06/freeze.py` (freeze discipline), and the claim-isolation runner's no-retry / blinding /
freeze-manifest machinery. None of this runs a model in the preparation phase.

---

## 7. FREEZE-MANIFEST READINESS

`freeze_manifest_v0` is a **new pre-execution artifact** (not a reinterpretation of the prereg). The
following can be hashed/pinned **now**:

- **Questions:** q_aib (`6e037bab…`), q_builtenv (`36e4623e…`), each with raw==trimmed assertion.
- **External evaluation referents:** the 13 / 11 source-obligation inventories + the relationship /
  operation / exact-construct / open-request / qualifier labels — **external to any package**, each
  hashed.
- **R_CONTROL package:** the exact `query_planner` Facet{label,query} prompt/template + schema +
  preprocessing, pinned to a git SHA.
- **Contexts** (SHORT / REALISTIC=12,288 / optional STRESS token counts); **output cap** (the frozen
  production value); **seeds (42) / temperature (0)**; **structured-output mechanism per runtime**.
- **Quantization policy** (§11); **verifier thresholds** (0.70 / 1.0 / 0.55 / 0.55, unchanged);
  **embedding-model id**.
- **Scoring rubrics:** the **5-category + co-occurring-flags** fidelity rubric (§14), the asymmetric
  minimum-sufficient-context rubric, the contamination rubric — each versioned/hashed.
- **Stage-1 rules:** neutral-mechanical-only (§13) — which **removes** the prereg's open semantic-floor
  bar from the manifest entirely.
- **Cloud policy** (§12); **corpus:** a read-only DB copy (path + row counts + schema version) with
  before/after SHA-256 unchanged; **host state** (LATENCY.md §15); **git HEAD**.
- **Held-out selection procedure** (§8), frozen before its contents.

**Awaits R_0_6:** only the §18 R_0_6 package hashes (its spec/prompts/schema/tests/acceptance). That
single reserved slot is the only intentional empty in the manifest.

**Recorded as OPEN (not pinned):** the exact latency values B_worker / B_orch / warm-L_screen (a
product decision, §9), the fidelity-floor numerics, the per-model quant pins (Codex), and the
output-budget-vs-package decision (§20). Recording these as explicit open items — rather than
inventing values — is itself a degrees-of-freedom control.

---

## 8. HELD-OUT-SET FREEZE DECISION

**Freeze the SELECTION PROCEDURE now; apply it to author the contents now.** The five job types
(scope classification / obligation preservation / ≥1 relationship-operation / exact-construct
preservation / structured-output completion) are **coverage criteria** — they are *not* the surface
tasks of the items. **Held-out items are natural researcher Ask questions** whose *required answer
structure exercises* those jobs. The benchmark must keep testing the system researchers actually
use; it must not be taught to speak Callosum internals (an item whose literal prompt is "preserve
these obligations" would do exactly that).

**Selection procedure (frozen now):**
1. Assemble candidate real Ask questions. Cliff may supply domain/context knowledge (what construct
   names to look for, what counts as on-topic), but is **not** the sole inclusion criterion.
2. **Exclude development-exposed questions from EVAL** — **q_aib, q_builtenv, and q_depr**. All three
   were used in A-series / 0.6 development, and R_0_6's ancestry (the calibration Runs 0.5/0.6) was
   developed against them, so **q_depr is not a clean EVAL item**. They remain DEV.
3. For each candidate, produce a **deterministic, inspectable corpus-presence receipt** against the
   frozen corpus: a reproducible lexical/structural presence check of the named constructs in chunk
   text (**no model inference, no generative or embedding-benchmark call**). Positive-evidence
   inclusion requires the receipt.
4. **Negative-control status is explicit and separately recorded**, each with its own receipt (the
   built-environment "confirmed absence" pattern), never inferred from a miss.
5. Build each item's obligation-referent inventory exactly as q_aib(13) / q_builtenv(11) were built.
6. Keep the set small (≈3–5) and hand-auditable; select for **task-type diversity, never expected
   performance** (no scores exist to select on, and none may ever be used to). Freeze before any
   inference; reuse `experiments/ask_cli_revised/calibration/datasets.py`'s DEV/held-out split
   discipline (deterministic assignment; "never encoded into a prompt").

`datasets.py`'s app-history questions q_h3 ("psychology of face perception") and q_h4 ("art therapy
for PTSD in veterans") are candidate simple-question "is it over-split?" items, but they are
**upstream-only decomposition tests**, not full-pipeline benchmark tasks; treat them as optional
decomposition-coverage items, not as the primary held-out set.

**Recommendation:** author + freeze the held-out set **now, before R_0_6 integration**, so it is
provably uncontaminated by R_0_6 development. The one residual input required is Cliff's domain
confirmation of candidate topics; corpus presence/absence is then settled by the deterministic
receipt, not memory.

---

## 9. LATENCY-BUDGET FREEZE DECISION

Latency budgets **should** be set before model outcomes (so they cannot be tuned to results) — but
**only from an existing product/UX requirement, from LATENCY.md, or from an explicit human product
decision.** This document does **not** manufacture thresholds. Three quantities are kept distinct:

- **Catastrophic Stage-1 infrastructure ceiling.** Anchor the **hard** ceiling to LATENCY.md's
  documented **600 s** local-inference bound — **freezable now**. Any *warm* Stage-1 ceiling stricter
  than 600 s is a product decision; absent one, set `warm-L_screen = 600 s` (the documented bound).
- **Preferred interactive worker latency (`B_worker`).** Bounded, high-volume role → should be tight.
  **REQUIRES EXPLICIT PRODUCT DECISION BEFORE FREEZE** — no repo-justified value exists.
- **Acceptable orchestrator latency (`B_orch`).** ~once per query (+ maybe one gap/escalation call) →
  generous. **REQUIRES EXPLICIT PRODUCT DECISION BEFORE FREEZE.**

**Smallest decision Cliff must make:** *the maximum warm per-call latency that keeps the bounded
high-volume worker role acceptable (`B_worker`), and the maximum warm per-call latency acceptable for
the once-per-query orchestrator role (`B_orch`).* The derivation frame — `role frequency × acceptable
interaction cost × epistemic importance` — and the ordering (`B_worker` tight `<` `B_orch` generous)
are frozen now; the two numbers are the open product input. **Never** peek at model outcomes to set
them.

---

## 10. CONTEXT-WINDOW FREEZE DECISION

**REALISTIC = production 12,288 tokens + the frozen production output cap** is the **single context
of the primary semantic comparison**, and is freezable now (production-anchored; the benchmark does
not alter production — the output cap lives in four lockstep places and is out of scope to change
here).

**SHORT and STRESS are mechanical feasibility / sensitivity conditions, NOT semantic factorial
levels.** The primary inferential shape stays **MODEL × REPRESENTATION** (judged at REALISTIC),
exactly as the prereg registered (its §15 thresholds are judged at REALISTIC; SHORT establishes
best-case latency/memory, STRESS probes the KV/offload cliff). This readiness plan **does not** expand
the design into MODEL × REPRESENTATION × CONTEXT; SHORT/STRESS inform feasibility and headroom, and
their inferential role is stated as such wherever they appear. If a future decision genuinely wants
context as a semantic factor, that is a **prereg-level change**, not a silent expansion here.

---

## 11. QUANTIZATION-POLICY FREEZE DECISION

**A-priori rule (freeze now; reconcile per-model pins with Codex Stage-0 before pinning):**

- **Q4_K_M is the common primary weight quantization where available.**
- **Deviations are allowed only for a pre-declared mechanical reason** — artifact/runtime
  availability, memory fit, or an explicitly defined sensitivity condition — **never a semantic
  score.**
- **KV-cache quantization is a separate runtime dimension** and is recorded separately from weight
  quantization (they are not interchangeable — e.g. Q8-KV halves cache pressure on the borderline
  7–8B tier without touching weight quant).
- Any model-specific deviation becomes part of **that model's deployed artifact configuration** and
  **must be exposed in interpretation** (a model that only fits at a different quant is reported as
  that configuration, not silently normalized to a common one).

The earlier draft's "Q5_K_M for borderline fit" is **dropped as incoherent** — Q5 costs *more* memory
than Q4, so it is not a remedy for a memory-borderline candidate. Per-model feasibility and the exact
pins are Codex Stage-0 territory; the rule above is what freezes now.

---

## 12. CLOUD-REFERENCE FREEZE DECISION

**Gemini alone is the cleanest calibration plan — freeze now.** Use the single already-integrated,
already-run Gemini reference (`gemini-2.5-flash-lite`). Adding a second provider (a Claude and/or
OpenAI model) risks model-shopping, adds egress/cost, and buys little calibration for a design whose
goal is **not** cloud parity. Cloud is:

- run on the **identical** sealed inputs / representation package / output contract / scoring;
- **service-level latency only** (network + queue + provider) — **not a hardware cell**, no VRAM/RSS/KV
  comparison;
- **egress-gated** (invariant #3), with **no retries** (parity with the local no-retry rule);
- **never the pass bar** — success is defined against the §15 floor, never "beats Gemini."

The option to admit exactly one additional provider is held as an **explicit pre-freeze decision**;
the default is **Gemini-only**.

---

## 13. STAGE-1 SCREEN DESIGN REVIEW — NEUTRAL-MECHANICAL-ONLY, NO SEMANTIC ITEMS

**Recommendation: Stage 1 eliminates on neutral, representation-independent mechanical/runtime
grounds ONLY, and runs no semantic items whatsoever — not even "descriptively."**

Stage-1 contains only **neutral probes**: loadability at the realistic context; realistic-context
memory allocation; a **neutral, non-semantic structured-output completion smoke** (schema-valid,
non-truncated output on content that is not a benchmark task); crash/runtime behavior; a
catastrophic-latency ceiling; deterministic cleanup. **No q_aib / q_builtenv / q_depr; no held-out
scholarly question; no obligation, relationship, or semantic-fidelity task.**

Why any semantic Stage-1 use is removed:
- **Observed-but-unused semantic output is still observed outcome information.** Even if a semantic
  screen score is never used for elimination, seeing it before the final 0.7 freeze can contaminate
  later decisions (it is the exact class of leakage the first-run-freeze discipline exists to
  prevent). All semantic characterization belongs to the **final, frozen Stage-2 execution**.
- **A semantic pre-cull risks the EQ3 interaction bias** — eliminating a model precisely because it
  needed R_0_6 — which the prereg already flagged and already R_0_6-gated.
- **Contamination = 0** is better applied in Stage 2, where the full model × package interaction is
  visible.
- It **preserves the full model × package interaction into Stage 2** and **removes an entire class of
  pre-freeze decisions** (the multi-item semantic-floor bar and its R_0_6 gate).

Cost saved by a semantic pre-cull is small: the roster is already bounded, and neutral mechanical
elimination already removes the genuinely unsuitable (won't load, can't emit complete structured
output, catastrophic latency, crash). This resolves the prereg's open Stage-1 latitude (its §9.1
"semantic elimination, if used at all") **conservatively** — it is not a prereg edit.

---

## 14. SCORING / ANALYSIS READINESS

**Specify and build the offline scorer now.** It operates entirely on the external referents and the
frozen rubrics — independent of R_0_6 — and is a pure offline pass, so it is buildable and
unit-testable now (on synthetic label inputs) and only **runs** once Stage-2 outputs exist (C).

**The fidelity rubric is not a mutually-exclusive four-way.** The frozen Run-0.6a / adjudication set
has **five overall categories** — **FAITHFUL / LOSS / ADDITION / LOSS_AND_ADDITION /
MALFORMED_OR_UNUSABLE** — **plus independent, co-occurring LOSS / ADDITION / MALFORMED flags** (a
representation can drop a qualification *and* add unsupported meaning). The scorer **must**:
- **preserve co-occurrence explicitly** (never collapse `LOSS_AND_ADDITION` or the independent flags
  into a single exclusive label);
- keep the **overall fidelity category distinct from the independent failure dimensions**;
- also encode the **asymmetric minimum-sufficient-context** scoring and the **contamination** rubric.

Analysis protections (all specifiable now):
- **per question, never averaged** (q_aib and q_builtenv diverge; each held-out item reported
  separately);
- **contamination as a separate HARD outcome** (a fabrication against a sealed ledger is
  disqualifying, never a deduction);
- **structured validity kept separate from semantics** (a completion improvement is a mechanical
  result, never counted as fidelity);
- report effects as **model-conditional-on-package**, **package-across-model**, and **interaction** —
  and **never** claim the design isolated *prompt* from *representation* from *preprocessing*;
- **Wilson lower bounds** on every rate (n is small: 13 and 11 referents);
- **no prompt-vs-representation causal claim.**

---

## 15. ARTIFACT / RECEIPT SPECIFICATION

Generalize the existing per-run `15_run_manifest.json` into a **per-cell receipt** so later execution
is boring and inspectable. Each observation carries:

- **cell key:** `(model × representation_package × hardware × context × frozen_task_hash)`;
- **all frozen-input hashes** (question, referents, package, corpus copy, rubric, git HEAD);
- **raw wire body + verbatim response**;
- **mechanical metrics:** structured-output validity; completion (non-truncation); truncation events;
  finish reason; cold + warm latency; prompt/completion tokens; peak VRAM; peak RSS; actual context
  used; KV-cache configuration (local cells only — cloud carries service-level latency only, no memory
  metrics);
- **host state** per LATENCY.md §15 (OS/CPU/cores/RAM/Python/lib versions/model identity/backend/
  device/threads/batch/PID/load);
- **per-prune record** `{decision, reason_code, inputs, kept}`.

Every number is therefore attributable to **model × representation package × hardware × context ×
exact frozen task**. Privacy per LATENCY.md §14: performance receipts carry counts / token-length
statistics / timing / memory / truncation metadata — **never** raw scholarly text, quotes, titles,
authors, prompts, or file paths.

---

## 16. HARDWARE-REPLICATION READINESS

**Specify the plan now; replicate later.** JUNO (Debian 12; i7-8700; RTX 3050 8 GB; Ollama) runs the
full model × representation matrix. **Replication is finalist-only** — a candidate that clears the
§15 floor on JUNO is then replicated on:

- **Apple baseline** — 16 GB Apple Silicon;
- **Apple mainstream** — 24–32 GB Apple Silicon (if a unit is available — an open procurement
  question);
- **Accessibility floor** — integrated-graphics / CPU-only / ~8 GB, where practical.

Full host state recorded per cell (§15). **Procurement configurations are proxies, never
population-prevalence claims** — the population device census is UNKNOWN (no first-party telemetry),
and the readiness plan says so rather than converting an institutional standard config into a
prevalence statistic. Replication is post-Stage-2 (finalist-gated): a plan now, not an action now.

---

## 17. WHAT CODE COULD SAFELY BE IMPLEMENTED BEFORE R_0_6 (analysis only — not implemented here)

All as experimental code outside `app/` (the `experiments/` precedent), zero production change, and
**no model runs**:

1. the **runner interface** + cell-ID scheme + one-run/no-retry + failure-receipt scaffold;
2. the **R_CONTROL** representation-package adapter;
3. the **model-adapter shim** (Ollama `response_format` / llama.cpp `json_schema`) — construction and
   request-shaping only, no calls;
4. the **`freeze_manifest_v0` builder** (all fields but the R_0_6 slot);
5. the **per-cell artifact writer** (§15 schema);
6. the **offline scorer** + the **5-category + co-occurring-flags** rubric encoding, unit-tested on
   synthetic labels;
7. the **held-out selection-procedure harness** — deterministic corpus-presence receipt generator,
   negative-control receipt, referent-inventory builder.

Stage-1 probes are authored as **neutral-only**. Everything reuses the `ask_cli` / calibration
machinery. **None of this runs a model, and none of it can observe a semantic score.**

---

## 18. WHAT MUST WAIT FOR R_0_6

- The **R_0_6 representation-package adapter**, and the prereg-§18 handoff artifacts Codex must
  deliver: representation spec (as a package); byte-exact prompts/templates; schema(s) + decoding
  mechanism; confirmation it runs on the same frozen inputs (byte-identical hashes); source/
  request-ancestry artifacts; obligation/coverage emission (distinct from the external referents); a
  hash manifest; its passing tests; a frozen 0.6.0 acceptance report; and any known defects.
- The **EQ3 interaction cells** (an interaction cannot be measured with one representation).
- The **output-budget-vs-package decision** (§20), which cannot be settled until R_0_6's shape is
  known.
- The **final Stage-2 execution freeze** that pins R_0_6.

Separate approvals (**not** R_0_6-blocked, but not part of this preparation): running the R_CONTROL
standalone column (a legitimate partial result under the *unchanged* production representation); and
running the Stage-0 no-score preflights.

---

## 19. EXACT READY_FOR_R_0_6 CRITERIA

READY_FOR_R_0_6 is reached when all of the following hold:

1. Every A-item is frozen into `freeze_manifest_v0`: the latency **framework + L_screen hard ceiling**
   (with B_worker / B_orch recorded as pending product decisions); context REALISTIC = 12,288 (SHORT/
   STRESS labeled mechanical/sensitivity); the quantization policy; the cloud policy (Gemini-only);
   Stage-1 neutral-mechanical-only; the 5-category + co-occurring-flags scoring rubric; the metric
   families; the artifact schema; the hardware plan; the Stage-0 rule; and the held-out selection
   procedure.
2. The runner + R_CONTROL adapter + offline scorer + artifact writer are built and unit-tested, with
   **no scored inference performed**.
3. The held-out set is authored and frozen, each item carrying a deterministic corpus-presence
   receipt (or an explicit negative-control receipt).
4. The Codex Stage-0 audit is reconciled into the roster; per-model verdicts and quantization pins are
   recorded.
5. The R_0_6 package slot is the **only** intentional empty in the manifest.
6. **No 0.7 scored semantic inference has occurred.**

When R_0_6 legitimately lands (post-adjudication → candidate → revised-0.6 integration → bounded
end-to-end acceptance → freeze), the remaining closure path is short, explicit, and auditable: drop
in the R_0_6 adapter + hashes; run the neutral Stage-1 mechanical screen; run the Stage-2 cells once
each; run the offline scorer; apply the §19 interpretation rules; freeze and stop.

---

## 20. REMAINING DEGREES OF FREEDOM

- **Output budget vs representation package (identifiability — resolve before scored 0.7 inference).**
  Do not resolve now (R_0_6 absent). Sharpened for the eventual decision: a **common, sufficiently
  large output cap** across R_CONTROL and R_0_6 preserves FORMAT comparability more cleanly and is
  **preferred**. A **package-specific cap** may be legitimate if mechanically necessary — but then the
  estimand is explicitly the effect of the **representation package (including its output envelope)**,
  and it **must never later be described as an isolated "representation effect."** Freeze this before
  any scored 0.7 inference.
- **Latency exact values** — B_worker, B_orch, any warm-L_screen: explicit product decision (§9).
- **Held-out exact contents** — apply the frozen procedure; receipts inspectable (§8).
- **A 2nd cloud reference** — default no (§12).
- **Fidelity-floor numerics; per-model quantization pins** — lock at freeze, reconciled with Codex.
- **Structured-output mechanism transfer** between Ollama and llama.cpp runtimes.
- **Apple 24–32 GB unit availability** — procurement (§16).

---

## 21. COLLISION / CONCURRENCY RISKS

- **Codex Stage-0 lane.** Codex owns model eligibility / licensing / artifact identity / mechanical-
  preflight requirements. This lane does **not** write Codex's temp dir, does **not** duplicate the
  audit, and **defers** per-model verdicts and quantization pins to it. The Stage-0 audit is
  **pending** and **must be reconciled before any implementation or preflight execution** (before any
  manifest pins model IDs).
- **Single SCRATCH writer.** This lane is the only SCRATCH writer in the pair; it appends exactly one
  compact handoff, preserves prior content byte-for-byte, and verifies persistence.
- **The blinded adjudication is the human's.** Nothing built here substitutes for it, previews it, or
  reads the sealed arm key.
- **The prereg is a design document, not an execution freeze.** This readiness plan resolves its open
  decisions in a **new** `freeze_manifest_v0`; the Stage-1 neutral-only choice exercises the prereg's
  own §9.1 latitude and is **not** an edit to the prereg.

---

## 22. RECOMMENDED NEXT IMPLEMENTATION TASK AFTER THIS REVIEW

**Reconcile the Codex Stage-0 audit, then freeze the outcome-independent decisions into
`freeze_manifest_v0` and build the non-semantic scaffold** — all as experimental code outside `app/`,
**with no scored inference**:
- the runner interface + R_CONTROL adapter + model-adapter shim;
- the `freeze_manifest_v0` builder + per-cell artifact writer;
- the offline scorer + the 5-category + co-occurring-flags rubric encoding (unit-tested on synthetic
  labels);
- the held-out selection-procedure harness (deterministic corpus-presence + negative-control
  receipts), then author + freeze the held-out set.
Obtain from Cliff: the two latency product numbers (B_worker, B_orch) and confirmation of held-out
domain topics (corpus presence settled by receipt, not memory). **Do not run the R_CONTROL column
yet** — that is its own separate execution approval.

---

## 23. DECISION

**READY TO BUILD NON-SEMANTIC 0.7 INFRASTRUCTURE.**

Nearly all 0.7 infrastructure is independent of R_0_6 and of which claim-arm the human labels favor;
building and freezing it now is cheap, reversible, degrees-of-freedom-reducing, and — because no
semantic score is observed — structurally un-biasable. The human adjudication is the true long pole
and is fully parallel, so waiting would waste the parallel window.

- *Not* **WAIT FOR R_0_6 BEFORE ANY 0.7 WORK** — most infrastructure is R_0_6-independent, and holding
  it hostage to the adjudication wastes the parallel window while reducing no risk.
- *Not* **MORE 0.7 DESIGN WORK REQUIRED BEFORE IMPLEMENTATION** — the preregistration already supplied
  the design; this pass resolves the last open *non-semantic* decisions (Stage-1 neutral-only, the
  latency framework, context role, quantization rule, cloud policy, held-out procedure, scoring
  rubric, artifact schema) and names the few that require a product decision or await R_0_6.

**Contingent on:** no scored inference; reconciliation with the Codex Stage-0 audit before any
preflight; the R_0_6 slot staying intentionally empty; and the dependency chain preserved —
`human adjudication → candidate representation → revised 0.6 integration → bounded end-to-end
acceptance → R_0_6 → final 0.7 execution freeze → semantic benchmark once.`
