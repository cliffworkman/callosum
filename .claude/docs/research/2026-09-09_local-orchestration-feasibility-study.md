# Callosum 0.7.0 Local Orchestration Feasibility Study

**Status:** Architectural research / hardware-ecology / model-scoping only. No code, no benchmarking, no
model downloads, no migrations, no Ask-CLI changes. This report defines the *design space* for a possible
0.7.0 orchestration layer and the empirical sweep that would test it — it does not build or run anything.

**Author lane:** Claude 0.7.0 research (concurrent with a separate Codex 0.6.0 Ask-CLI lane). Companion
to the Ask staged-synthesis scoping (`2026-09-07_ask-cli-experiment-scoping.md`) and the control-plane
pivot (`2026-09-07_ask-run-0.5-control-plane-pivot.md`).

**Evidence tags used throughout** (per the commissioning brief):
`[DIRECT DATA]` measured/first-party · `[PROCUREMENT PROXY]` a purchasing standard, not a prevalence
count · `[INSTALLED-BASE EVIDENCE]` fleet/share data · `[INFERENCE]` reasoned from the above ·
`[USER LOCAL OBSERVATION]` Cliff's/JUNO's own facts · `[UNKNOWN]` not established. Sources are listed in
§ Sources; every important claim carries a tag.

---

## 1. Executive summary

The 1.5-billion-parameter worker size was chosen partly to run on *a particularly weak laptop*. The
product's real primary population — research-active scholars — plausibly runs materially stronger
hardware than that laptop, so the size ceiling deserves to be **reopened as a testable question**, not
treated as settled. Three findings drive this:

1. **The institution-issued baseline has already moved to 16 GB RAM machines** [PROCUREMENT PROXY], and
   **base Apple Silicon shifted to a 16 GB minimum at the M4 generation** [DIRECT DATA, secondary]. A
   4-year (some 5-year) replacement cycle [PROCUREMENT PROXY] means a 2026 researcher's institutional
   machine is plausibly a 2021–2023 purchase — but even a 2021 machine in this population is far from the
   weak laptop that set the 1.5B ceiling.
2. **The orchestration job is low-frequency** (roughly once per query, maybe once more for
   gap/escalation), so it can tolerate latency a per-chunk worker cannot. Viability =
   *latency × invocation-frequency × epistemic-importance*; an 8–15 s once-per-query orchestrator call is
   acceptable if it prevents large request-fidelity loss.
3. **Feasibility must be judged on total runtime memory at realistic context** — weights + KV cache +
   runtime overhead — not GGUF size [DIRECT DATA, formula]. On that basis a **~4B** orchestrator fits
   comfortably on the broad researcher baseline and on JUNO; a **~7–8B** orchestrator fits on capable
   tiers (16 GB+ Apple Silicon, discrete-GPU/large-RAM machines) and on JUNO only with reduced context.

**Two epistemic cautions bound the conclusions.** First, the in-house A0–A3 planner experiments show
Qwen2.5-1.5B failing the control-plane tasks (decomposition, scope selection, obligation preservation),
but those failures are confounded across *model × prompt × representation* — the experiments' own notes
say enforcement helped shape without recovering broad plans, and "no proof Facet representation caused
it." **Stronger-model capability is therefore a hypothesis this study recommends testing, not a
diagnosis this study asserts** [INFERENCE]. Second, the staged-synthesis pipeline is an
*architecturally-relevant antecedent* (it already separates "the model interprets language; code owns
schemas") — but it is Qwen-for-all-intermediate + deterministic + cloud-terminal-only; it does **not**
itself implement worker/orchestrator *size*-tiering, so it is a precursor, not an instance, of the
proposed architecture.

**Decision:** **HARDWARE EVIDENCE SUPPORTS LOCAL-ORCHESTRATOR BENCHMARKING** — scoped to a controlled
JUNO sweep (ideally with one Apple-Silicon reference), across a worker class (~1.7–4B) and an
orchestrator class (~7–14B, run where it fits), with the incumbent Qwen2.5-1.5B as control, and with
**small-local + focal-cloud orchestration retained as the accessibility-tier design** rather than
discarded. The hardware case for the *core* population is strong enough to justify the (cheap, reversible)
benchmark that would resolve the model-vs-representation question; it is **not** strong enough to commit
to a single fully-local orchestrator for *all* users.

---

## 2. Research question / decision frame

**Primary question:** Does the hardware that Callosum's research-active users actually possess make a
*stronger local orchestrator* plausible enough to justify an empirical model sweep — and if so, at what
size class, on what hardware, for what accessibility floor?

**Why this is a decision, not a curiosity.** Callosum already ships a managed Local AI stack (llama.cpp
`b10516`, one pinned Qwen GGUF, Tauri-owned loopback lifecycle, no cloud fallback) [DIRECT DATA, repo].
A 0.7.0 control plane would sit directly on that stack. The candidate architecture is a **three-tier
control plane**: deterministic substrate (embeddings, auto-axes, the local verifier) + a small **worker**
model (bounded, high-volume, noisy tasks) + a stronger **orchestrator** model (low-frequency: preserve
and structure user intent, identify request obligations, allocate bounded work, inspect coverage/gaps,
escalate only when necessary), with the orchestrator **provider-swappable** (a stronger local open model,
or Gemini/Claude/OpenAI). This report determines whether the hardware makes the *local-orchestrator* leg
of that swap realistic for the core population, and what the sweep should test.

The frame deliberately separates two model roles with **different latency budgets and different capability
demands**, and treats "how strong must the orchestrator be" as the open empirical variable.

---

## 3. Target user definition

**Core scholarly-production population** (the tier the richest local path should optimize around):
tenure-track/tenured faculty, postdocs, research scientists and technical research staff, PhD-stage
graduate researchers, and independent/professional researchers. Defining traits relevant to hardware:
they produce scholarship as their primary output; they frequently receive an **institution-issued**
primary machine on a refresh cycle; and a meaningful subset (computational fields especially) also owns
or is issued **accelerated** hardware.

**Broader accessibility population:** undergraduates, coursework-stage students, researchers at
under-resourced institutions, users on older personal machines, and anyone whose only device is a
budget/integrated-graphics laptop or an 8 GB base machine.

**Why they must not be conflated.** The 1.5B ceiling was set by the *accessibility tail* (a weak laptop).
Optimizing the richest fully-local architecture around the weakest supportable machine is a category
error: it lets the accessibility floor dictate the ceiling. The correct posture is **graceful capability
scaling** — a floor everyone gets, and richer local capability that capable hardware unlocks — not a
single design pinned to the weakest device. Accessibility remains a hard commitment (§8); it is honored
by a *fallback path*, not by capping the *core path*.

---

## 4. Evidence quality / limitations

- **Procurement standards are not prevalence.** University "standard configuration" pages and faculty
  computer-purchase programs tell us what institutions *buy new* [PROCUREMENT PROXY]; they do not
  directly measure the *installed base* a researcher is using today. I keep these distinct throughout and
  never convert a purchasing menu into a population percentage.
- **Institution-issued ≠ personally-owned.** Most hard evidence here concerns institution-issued
  machines. Researchers frequently also own a personal machine (often a Mac); the split, and which
  machine they'd actually run Callosum on, is **[UNKNOWN]** at population scale. I flag this at each use.
- **Replacement-cycle length is established, not assumed** — see §5; multiple published university
  policies converge on 4–5 years, which lets me bound machine age rather than guess it.
- **Disciplinary stratification is coarse.** Directional evidence exists (macOS over-represented among
  researchers vs. the global desktop share; computational fields more likely to hold accelerated
  hardware) but a clean discipline × hardware table is **[UNKNOWN]**.
- **No first-party Callosum hardware telemetry.** Callosum's usage instrumentation is counts/timestamps
  with structurally no payload, and does not record device specs [DIRECT DATA, repo]. So the core
  population's real device mix is triangulated, not measured — a genuine limitation the Decision accounts
  for (it authorizes a *benchmark*, whose cost is low, rather than an architecture commitment).
- **US bias.** The procurement and share evidence is strongest for US research-intensive institutions;
  international coverage is weaker and noted where it matters.
- **Model facts are dated to 2026-09** and cross-checked against vendor/model-card sources; the field
  moves monthly, so the *size-class* conclusions are more durable than any specific model pick.

---

## 5. Hardware ecology

### 5.1 Replacement cycle (established quantity) [PROCUREMENT PROXY]
Published university replacement policies converge tightly: **4-year** cycles (Xavier, Wesleyan, Univ.
of Michigan School of Nursing) and **5-year** cycles (Univ. of Akron, SUNY Purchase, Western Kentucky).
No sampled policy exceeded five years for primary faculty/staff machines. **Established bound:** an
institution-issued machine in service in 2026 is, at the far edge of the cycle, a 2021–2022 purchase; at
the near edge, a 2024–2025 purchase. This is the age envelope the local path must assume for
institution-issued hardware — *not* a decade-old laptop.

### 5.2 Current new-purchase standard [PROCUREMENT PROXY]
2025–26 institutional standard configurations cluster on **16 GB RAM** as the floor:
- **Windows:** Dell Pro 13/14/16 at Intel **Core Ultra 7, 16 GB, 512 GB** (e.g., CU Boulder OIT, OSU
  Engineering Technology Services); Lenovo ThinkPad equivalents. These are **integrated-graphics** business
  laptops (Intel Arc/Iris) — **no discrete GPU** in the standard build (§7).
- **Apple:** MacBook Air M4 **16 GB / 512 GB**; MacBook Pro M5 **16 GB** base — issued under faculty
  computer-purchase programs at many R1s.

### 5.3 Apple Silicon memory and the end of the 8 GB base [DIRECT DATA, secondary]
Base Apple Silicon shipped **8 GB** through the M1/M2/M3 base tiers (2020–2023) but moved to a **16 GB
minimum at the M4 generation** (2024–25). Unified memory (CPU/GPU/Neural Engine share one pool) scales
16 → 24 → 32 → 48 → 64 → 128 GB across Pro/Max variants; bandwidth ranges from ~100 GB/s (base) to
546 GB/s (M4 Max). **Consequence:** *new* Macs in this population are ≥16 GB; the *installed base* is
bimodal — many 8 GB M1/M2 machines from 2020–2023 remain in service [INFERENCE], defining part of the
accessibility tail.

### 5.4 OS mix among researchers [INSTALLED-BASE EVIDENCE + INFERENCE]
Global desktop share is ~70–73% Windows, ~14–15% macOS, ~4–5% Linux. macOS is **over-represented in US
higher education and among researchers** (especially CS, data science, quantitative/biomedical, and
creative fields), and Linux is over-represented among computational researchers, relative to those global
figures. A precise researcher-stratified split is **[UNKNOWN]**; the directional, decision-relevant point
is that a local-AI design must run well on **macOS/Apple Silicon and Windows**, with Linux a real
minority worth supporting (Callosum already covers all three) [DIRECT DATA, repo].

### 5.5 Discrete-GPU prevalence [PROCUREMENT PROXY + INFERENCE]
The standard institution-issued research laptop (Dell Latitude/Pro, ThinkPad) uses **integrated
graphics** and has **no CUDA GPU**. Discrete NVIDIA GPUs appear on (a) workstation-class desktops issued
to computational labs, (b) personally-owned gaming/ML rigs, and (c) a minority of mobile-workstation
laptops. So among the core population, **discrete-GPU acceleration is a minority capability**, while
**Apple-Silicon GPU/Neural-Engine acceleration via unified memory is common** (every Mac has it). Any
local-orchestrator design that *depends* on CUDA would serve a minority; one that runs on Apple-Silicon
unified memory and on CPU-with-modest-RAM serves the majority [INFERENCE].

### 5.6 Personally-owned machines [UNKNOWN, flagged]
Researchers commonly run a personal machine alongside the institutional one, and may run Callosum on
either. The population split and the "which machine runs Callosum" question are unmeasured. This matters
because a personal machine may be *newer and better* (a self-bought MacBook Pro) or *older and weaker*
(a hand-me-down) than the institutional one — it widens variance in both directions and is a reason the
design needs graceful scaling rather than a single assumed device.

---

## 6. Proposed hardware tiers

Empirically derived (not forced). Coverage percentages are **deliberately omitted** where evidence cannot
support them; the population lacks a first-party device census, so these are tiers with *characterizations
and uncertainty*, not a calibrated CDF.

| Tier | Representative machine | RAM / memory | GPU | OS | Age window | Local-model implication |
|---|---|---|---|---|---|---|
| **Accessibility Floor** | 8 GB base laptop; older MacBook Air M1/M2 8 GB; budget Windows w/ integrated GPU | 8 GB (shared/system) | none / integrated | mixed | 2019–2023 | Deterministic core + a small worker (≤~1.5–3B) at modest context; orchestration via focal cloud/free-tier. Fully-local orchestration NOT assumed. |
| **Broad Researcher Baseline** | 2025-era institutional standard: Dell Pro Ultra 7 16 GB; MacBook Air/Pro 16 GB | 16 GB | integrated (Win) / unified (Mac) | Win + macOS | 2022–2026 | Comfortable **~4B** local model at real context; **7–8B** feasible on Apple-Silicon unified memory; low-freq orchestration realistic. |
| **Mainstream Current Research Machine** | 24–32 GB Apple Silicon (M-Pro), or 32 GB Windows workstation | 24–32 GB | unified (Mac) / integrated or entry discrete (Win) | Win + macOS | 2023–2026 | **7–8B** comfortable; **12–14B** feasible (Apple 24 GB+, or discrete-GPU/large-RAM). Strong local-orchestrator candidate tier. |
| **Accelerated Local-AI Tier** | Discrete NVIDIA (≥8–12 GB VRAM), or M-Max/large-unified Macs | 32–128 GB / 8–24 GB VRAM | discrete CUDA or M-Max | Win/Linux + macOS | 2021–2026 | **14B+** local models; the richest fully-local path. Minority of the population. **JUNO lives here on the GPU axis but not the CPU axis** (§7). |

The important structural point: the **Broad Researcher Baseline (16 GB) already clears the bar for a ~4B
local orchestrator at usable context**, and the **Mainstream tier clears 7–8B** — both well above the
1.5B worker size. The Accessibility Floor is the tier that genuinely needs the small-worker + focal-cloud
fallback.

---

## 7. JUNO calibration

JUNO: **Debian 12; Intel i7-8700 (6c/12t, Coffee Lake, 2017/2018 desktop); NVIDIA RTX 3050 8 GB VRAM;
CUDA; Ollama host** [USER LOCAL OBSERVATION].

The right question is not "is JUNO average?" but "where does JUNO sit *functionally* for low-frequency
local orchestration relative to likely researcher hardware?" — and the answer is **architecturally
different, not simply better or worse**, and *different on each axis*:

- **CPU (below/dated).** The i7-8700 is a 2017 platform — materially behind modern Core Ultra and every
  M-series chip in per-core throughput and memory bandwidth. For any work that spills to CPU (large
  context, big models offloaded from VRAM, or CPU-only inference), JUNO is **slower than a modern
  mainstream researcher machine** [INFERENCE].
- **GPU (above the typical laptop, below the enthusiast desktop).** A dedicated RTX 3050 8 GB with CUDA
  is **more** local-AI-capable than the integrated graphics in the standard institution-issued laptop
  (§5.5) — JUNO is GPU-*advantaged* vs. the median research laptop. It is **less** capable than an M-Max
  Mac or a ≥12 GB discrete card. Measured throughput: **~28 tok/s on a quantized 7B** [DIRECT DATA];
  comparable-class cards (RTX 3060 12 GB) do 14B Q4 at ~22.7 tok/s / 16K context.
- **Memory (dedicated-but-capped 8 GB vs. unified-but-bandwidth-bound).** JUNO's 8 GB VRAM is fast for
  models that *fit*, but hard-capped; a 16 GB Apple-Silicon Mac has *more* addressable model capacity
  (unified) but is bandwidth-bound in speed. This is the clearest "different, not better" axis:
  **JUNO wins tokens/sec for models that fit in 8 GB; Apple Silicon wins capacity and holds larger
  models/context** [INFERENCE from §5.3, §9].
- **Thermals / sustained inference (above laptops).** JUNO is a **desktop** — sustained inference without
  the thermal throttling a thin-and-light laptop suffers on a long orchestration+worker run. This is a
  genuine advantage for repeated worker calls [INFERENCE].
- **Model capacity (the operative envelope).** With realistic context (§9): **1.7–4B models fit fully in
  8 GB VRAM with generous context**; **7–8B Q4 fits with reduced context** (KV cache must be watched, and
  Qwen's GQA helps); **12–14B requires system-RAM offload → JUNO's dated CPU makes that meaningfully
  slower**.

**Net:** JUNO is a **reasonable, if idiosyncratic, orchestrator-benchmarking substrate** — GPU-stronger
than the typical researcher laptop, CPU-weaker than modern machines, and capacity-capped at 8 GB. It is
**not** a proxy for Apple Silicon (the most common researcher accelerator), so the sweep should include an
Apple-Silicon reference before any cross-platform conclusion. JUNO is fine for the near-term sweep; it is
not sufficient on its own to characterize the core population's real envelope.

---

## 8. Accessibility analysis

The accessibility commitment is preserved *without* letting it cap the core path, via **graceful
capability scaling**:

- **Deterministic core, always.** Extraction, embeddings, vector search, clustering, and the local
  verifier run on every tier and offline after import [DIRECT DATA, repo]. The scientific substrate does
  not depend on any orchestrator.
- **Small local worker on every tier that can host one** (Accessibility Floor upward). The worker handles
  bounded, high-volume language interpretation.
- **Orchestration scales by tier:** fully-local orchestration on Broad-Baseline-and-up; **focal
  cloud/free-tier orchestration** on the Accessibility Floor and for users who prefer it; the orchestrator
  is **provider-swappable** so the same code path serves a local open model or Gemini/Claude/OpenAI.
- **Egress stays gated and off by default** (invariant #3) [DIRECT DATA, repo]. A cloud-orchestration
  fallback is an *opt-in* the user chooses, never a silent default — consistent with the existing
  Local-AI "no silent cloud fallback" rule. The Accessibility-Floor fallback must be presented as a
  consent choice, not a quiet escalation.

**Bundling-burden assessment for a small local worker as base infrastructure** (i.e., not opt-in
"Local AI" but ordinary infrastructure):
- **Installer / first-run download / disk:** the model is *downloaded on first run* (the current Local-AI
  pattern), not shipped in the installer, so installer size is unaffected; first-run adds a bounded model
  download (~1–3 GB for a 1.7–4B Q4) and disk footprint. A 4B is a larger first-run than 1.5B but still
  modest [INFERENCE].
- **RAM/VRAM at runtime:** governed by §9 math; a ~4B worker is comfortable on 16 GB machines and on
  JUNO. On the 8 GB Accessibility Floor it competes with the OS and the app — a real constraint that
  argues for keeping the *floor* worker small (≤~1.5–3B) even if the baseline worker grows.
- **Battery:** sustained local inference on a laptop draws power and generates heat; a low-frequency
  orchestration call is cheap, but a high-volume worker loop on battery is not free — an argument for
  keeping worker calls bounded and few (which the staged-synthesis design already emphasizes).
- **Privacy/consent:** a *local* worker/orchestrator is a **privacy win** — it keeps intermediate library
  interpretation on-device, which is exactly why the staged pipeline routes all intermediate work locally
  and reserves cloud for optional terminal prose. Making the worker base infrastructure *strengthens* the
  local-first posture; the consent surface only appears at the cloud-orchestration fallback.
- **Platform support:** the pinned llama.cpp bundle already covers Windows/macOS/Linux [DIRECT DATA,
  repo]; a larger worker is the same runtime with a different GGUF, so platform burden is ~unchanged.

**Conclusion:** making a small local worker *base infrastructure* is defensible and privacy-positive; the
main constraint is the 8 GB Accessibility Floor, which argues for a **tier-aware worker size** (small on
the floor, larger on the baseline) rather than one universal worker.

---

## 9. Local LLM memory / latency implications

**Total runtime memory ≠ GGUF size** (the crux). Total = **weights + KV cache + runtime overhead**:
- **Weights (Q4_K_M):** ≈ 0.5–0.6 GB per 1B params → 1.5B ≈ 1 GB; 4B ≈ 2.3 GB; 8B ≈ 4.5 GB; 14B ≈ 8 GB
  [INFERENCE from standard Q4 sizing].
- **KV cache** = `2 × layers × KV_heads × head_dim × bytes_per_elt × context_tokens`, and is
  **strongly model-dependent via grouped-query attention** [DIRECT DATA, formula]:
  - Llama-3-8B (32 layers, 8 KV heads, head-dim 128, FP16): ≈ **0.125 MB/token → ~4.1 GB at 32K** context.
  - Qwen-family 7–8B (fewer KV heads via aggressive GQA) is far more KV-efficient (~1.5–2 GB at 32K)
    [INFERENCE from GQA config]. **KV cache can be quantized to Q8 to halve it.**
- **Overhead:** ~0.5–1 GB (activations, buffers) [INFERENCE].

**Worked implications:**
- A **4B Q4** model: ~2.3 GB weights + modest KV + overhead ≈ **fits comfortably at 12–16K context on
  8 GB VRAM (JUNO) and on any 16 GB machine.**
- An **8B Q4** model: ~4.5 GB weights + ~4 GB KV (Llama, 32K, FP16) ≈ **~9 GB → exceeds JUNO's 8 GB VRAM
  at large context.** It "loads" but does not "run at 32K on JUNO"; it *does* fit with **reduced context
  and/or Q8 KV and/or a KV-efficient (Qwen) model** — and fits comfortably on a 16 GB Apple-Silicon Mac.
- **"Loads" vs. "performs the orchestration task at usable context + latency" are different claims.** The
  sweep must measure the model **at Callosum's real context** (the Preview runs 12,288-token context /
  2,048-token output today [DIRECT DATA, repo]) and at real task latency, not just confirm the file loads.

**Latency framing — orchestration is low-frequency.** Worker calls may run dozens–hundreds of times per
query; the orchestrator runs ~once at query start and maybe once for gap/escalation. So:
> **orchestrator viability = latency × invocation-frequency × epistemic-importance.**
An 8–15 s orchestrator call that runs twice per query and prevents large request-fidelity loss is
acceptable; the same latency per-chunk would not be. **Do not disqualify an orchestrator candidate on
per-chunk-latency grounds.** (The latency contract's "measure before optimizing," runtime reuse, batching,
and the 600 s local-inference bound already accommodate slow-but-rare local calls [DIRECT DATA, repo].)

**Throughput anchors** [DIRECT DATA]: RTX 3050 8 GB ≈ 28 tok/s (7B, quantized); M2 Max ≈ 28 tok/s (8B);
M1 16 GB ≈ 40–80 tok/s (3–9B); M4 Pro 24 GB ≈ 35–55 tok/s (14–35B). Apple-Silicon inference is
memory-bandwidth-bound and scales ~linearly with bandwidth; MLX is 20–87% faster than llama.cpp for <14B
on Apple Silicon (relevant if a future Apple path uses MLX rather than the pinned llama.cpp).

---

## 10. Current open model landscape

Facts dated **2026-09**, cross-checked against vendor/model-card sources; size-class conclusions are more
durable than any single pick. Callosum's runtime is **llama.cpp `b10516` / Ollama-compatible**, so
GGUF + llama.cpp/Ollama support is a hard requirement — **all families below satisfy it** [DIRECT DATA].

### 10.1 Worker candidates (~1–4B)
| Model | Params | License | Context | ~Q4 weights | Notes |
|---|---|---|---|---|---|
| **Qwen2.5-1.5B-Instruct** *(incumbent)* | 1.5B | Apache-2.0 | 32K | ~1 GB | Current worker; the control. |
| **Qwen3-1.7B** | 1.7B | Apache-2.0 | 32K | ~1.1 GB | Newer generation, same class. |
| **Qwen3-4B** | 4B | Apache-2.0 | 128K (YaRN) | ~2.3 GB | Class-leading function-calling; strong instruction following. |
| **Gemma 3 4B** | 4B | Gemma (custom) | 128K | ~2.5 GB | Multimodal, multilingual, structured output + function calling. |
| **Llama 3.2 3B** | 3B | Llama community | 128K | ~1.9 GB | Solid baseline + broad ecosystem; attribution/AUP/700M-MAU license clauses. |
| **Phi-4-mini** | 3.8B | **MIT** | 128K | ~2.3 GB | Reasoning/math above weight; most bundling-friendly license. |
| **Ministral 3 (3B)** | 3B | Apache-2.0 | long | ~1.9 GB | Dec-2025 edge series; base/instruct/reasoning variants. |

### 10.2 Orchestrator candidates (~7–14B; run where the tier allows)
| Model | Params | License | Context | ~Q4 weights | Notes |
|---|---|---|---|---|---|
| **Qwen3-8B** | 8B | Apache-2.0 | 128K | ~4.7 GB | Strong function-calling (BFCL) in class; KV-efficient GQA. |
| **Qwen3-14B** | 14B | Apache-2.0 | 128K | ~8 GB | Needs 16 GB+/offload; strong reasoning. |
| **Ministral 3 (8B)** | 8B | Apache-2.0 | long | ~4.7 GB | Best-in-class cost/perf per Mistral; Apache. |
| **Gemma 3 12B** | 12B | Gemma (custom) | 128K | ~7 GB | Multimodal; strong general. |
| **Phi-4 (14B)** | 14B | **MIT** | 16K | ~8 GB | Reasoning-dense; competitive with much larger; short native context. |

### 10.3 Capability signals that matter (not MMLU/GPQA trivia)
- **Function-calling / tool-use (BFCL):** Qwen3 leads its size class; specialized 8B tool-callers
  (e.g., ToolACE) can match GPT-4/Claude-3.5 on BFCL; Llama tool-calling only in 8B+ and trails Qwen;
  Gemma3 trails Qwen on tool-calling [DIRECT DATA, leaderboard]. **Directly relevant** because
  orchestration = obligation extraction + bounded work allocation, which is tool/schema-shaped.
- **Instruction following (IFEval) and structured reasoning:** Phi-4-mini punches above weight on
  reasoning/math (synthetic-data training); Qwen3-4B is strong and, with test-time scaling, competitive
  with much larger models; Llama-3.2-3B is a solid general baseline [DIRECT DATA/INFERENCE]. Exact
  head-to-head IFEval numbers for the specific 3–4B instruct variants are partly **[UNKNOWN]** from
  public snippets and are a *sweep* output, not a settled ranking.
- **License realism for bundling:** **Apache-2.0** (Qwen3, Ministral 3) and **MIT** (Phi-4) are the most
  bundling-friendly; **Gemma** and **Llama community** licenses carry custom terms (usage policy,
  attribution, and — Llama — a 700M-MAU clause) that are usable but need legal review before *bundling*
  vs. *user-downloads* [DIRECT DATA]. This mirrors the existing AGPL/GPL boundary discipline the repo
  already applies to the EndNote/MariaDB question.

---

## 11. Frontier-research infrastructure crosswalk

Is Callosum reinventing known infrastructure? **Partly yes — the pattern is well-established — but the
big-lab instances differ from Callosum's problem in ways that change the model-strength answer.**

- **Anthropic multi-agent research system** [DIRECT DATA, eng post]: an explicit **orchestrator-worker**
  pattern — a lead agent (Claude Opus 4) plans and spawns subagents (Claude Sonnet 4), each with its own
  context window; +90.2% vs. single-agent Opus on internal research eval; **token budget explains ~80% of
  performance variance**; ~15× the tokens of chat. **Note:** *both* roles are frontier models — the
  "worker" is Sonnet, not a tiny model.
- **OpenAI Deep Research** [DIRECT DATA]: a **single-agent**, RL-fine-tuned o3 running a Plan-Act-Observe
  (ReAct) loop with a clarification step — again a *frontier* reasoning model for the whole loop.
- **Google high-volume serving** [DIRECT DATA/INFERENCE]: current AI Overviews run Gemini 3 (frontier),
  but the durable, well-evidenced pattern is that **hyperscale, latency/cost-sensitive serving leans on
  distilled Flash / Flash-Lite–tier models** (Gemini 1.5 Flash was distilled from 1.5 Pro; Gemini 3.5
  Flash-Lite is positioned for "high-volume agents"). *(On the user's motivating observation — that Search
  uses a "Gemini 1.5-class" model — the literal, current version is **unverified/likely stale** (Search
  moved up to Gemini 3); the defensible principle it points at is real: even hyperscale serving
  deliberately uses smaller-than-frontier distilled models where volume and latency dominate.)*
- **NVIDIA, *Small Language Models are the Future of Agentic AI*** (arXiv 2506.02153, 2025) [DIRECT DATA]:
  the keystone counter-weight — argues SLMs (<10B) are "sufficiently powerful, inherently more suitable,
  and necessarily more economical" for the *repetitive, specialized* invocations that dominate agent
  graphs (tool-calling, structured reasoning, orchestrated steps), 10–30× cheaper, with large models
  reserved for tasks that are "tough, very open-ended, or need long context," and **heterogeneous
  (mixed-model) systems as the natural choice.**

**Synthesis for Callosum.** Two facts sit in tension and their resolution is the whole point:
1. The big-lab *research products* use frontier models for the whole loop — but they solve **unbounded,
   adversarial, open-web** research where the model must judge untrusted sources and plan
   arbitrarily-deep trajectories.
2. Callosum's orchestration is over a **bounded, trusted, pre-embedded local corpus with a deterministic
   verifier and deterministic coverage accounting** — a **much narrower job**: preserve intent, name
   obligations, allocate bounded work over a known corpus, inspect deterministic coverage output, escalate
   the hard minority. The NVIDIA thesis applies squarely to *that* shape.

So Callosum is **not** reinventing the open-web-research stack, and the frontier requirement of those
products **should not be assumed to transfer**. The honest position is the NVIDIA one: the worker can be
small; the orchestrator may often be small-to-mid **with escalation on the hard minority** — and *how
strong the orchestrator must be for Callosum's specific narrow job is exactly the open empirical question*
(§13, §15).

---

## 12. Supervisor/worker architecture plausibility

The three-tier control plane (deterministic substrate + small worker + swappable orchestrator) is
**architecturally plausible and partly precedented in-repo** — with the antecedent stated precisely.

- **In-repo antecedent (not equivalence).** The staged-synthesis pipeline already enforces the load-bearing
  separation "the model interprets language; deterministic code owns IDs, schemas, provenance, verifier
  policy, and coverage." That is the *philosophy* the orchestrator/worker split needs. **But** the
  pipeline as built is *Qwen-for-all-intermediate + deterministic + cloud-terminal-only*; it does **not**
  implement worker/orchestrator **size**-tiering, and its cloud model enters only for terminal prose, not
  for orchestration. It is therefore an **architecturally-relevant antecedent, not an instance** of the
  proposed system. The 0.7.0 idea is a genuine extension: promote a *stronger* model into the
  intermediate control-plane role (orchestration), keep a *smaller* model for the bounded worker tasks,
  and make the orchestrator swappable local↔cloud.
- **Where the boundary should sit** (from the crosswalk + the pivot doc): deterministic code keeps
  everything it already owns; the **orchestrator** does the low-frequency, high-epistemic-leverage
  language judgments (intent preservation, obligation identification, coverage/gap interpretation,
  escalation decisions); the **worker** does the high-volume bounded interpretation (per-packet context
  gating, source-local proposition extraction, recovery-query phrasing). This maps cleanly onto the
  staged pipeline's existing Qwen stages (S1, S5, S6, S10) — the question the sweep answers is *which of
  those stages need the orchestrator vs. the worker*.
- **Escalation, not always-on frontier.** Consistent with the NVIDIA thesis and the pivot doc's "discovery
  may be curious because verification stays conservative": route the hard minority (a failed coverage
  gate, an ambiguous decomposition) to the stronger model; keep the common case on the small worker.
- **Structured-output reality check** [DIRECT DATA]: llama.cpp GBNF / Ollama JSON-schema decoding
  guarantees **valid JSON structure** via per-token masking — but it does **not** guarantee **completion**
  (a model can exhaust its token budget mid-JSON — precisely the baseline truncation failure, and the
  inc-575 "truncation by construction" class) and it does **nothing** for **scope/semantic** fidelity
  (the A1 experiment found `response_format` fixed shape while recovering **0/2** broad plans). This
  cleanly separates the two failure classes the architecture must handle: **format** (solved by grammar +
  adequate output budget) vs. **semantics/scope** (the capability question the sweep tests). It is the
  strongest in-repo reason to believe *a bigger model might help the part grammar cannot* — stated as a
  hypothesis, not a finding.

---

## 13. Qwen 1.5B reassessment

**Worker role:** the evidence *supports keeping a small model as the worker* and *supports testing whether
1.5B specifically is the right small model*. The NVIDIA thesis and the BFCL/IFEval signals say the worker
tasks (bounded context gating, source-local extraction, recovery phrasing) are within reach of small
models — and that **~3–4B** models (Qwen3-4B, Phi-4-mini, Gemma3-4B) are meaningfully stronger than 1.5B
at instruction-following and function-calling while still fitting the Broad Researcher Baseline and JUNO
at real context (§9). So the worker size ceiling deserves to be **reopened** — with a specific, cheap
test: does a 3–4B worker reduce the `quote_not_verbatim` / paraphrase-drift / mis-gate failures the
staged run localized, at acceptable added latency/memory?

**On "was 1.5B chosen under an unnecessarily weak constraint?"** — **almost certainly yes as to the
*constraint*** (§5–6 show the core population runs ≥16 GB machines, far above the weak laptop), **but the
*consequence* for model choice is a hypothesis, not a settled fact.** The A0–A3 planner failures are real
but confounded across model × prompt × representation (the experiments themselves recovered 0/2 broad
plans even *with* enforcement, and explicitly declined to attribute failure to model capacity). So:
reopen the size constraint, and **let a controlled sweep — crossing model size against representation —
separate "1.5B is too small" from "the task representation was wrong"** rather than assuming the former.

**Opt-in status:** Local AI is currently a user-selected, opt-in provider. If a small worker becomes
*base infrastructure* (§8), that is a status change worth its own deliberate decision — it is
privacy-positive and platform-neutral, but it adds a first-run download and a floor-tier RAM cost, and it
should remain **tier-aware** (small worker on the 8 GB floor, larger on the baseline) rather than one
universal size. This reassessment does **not** by itself justify promoting Local AI from opt-in to default;
it justifies the sweep that would inform that decision.

---

## 14. Local orchestrator search space

The sweep should treat model choice as **two coupled searches**, not one:

- **Smallest reliable worker:** the *smallest* model that performs the bounded worker tasks
  (context-gate, source-local proposition extraction under a verbatim-quote constraint, recovery phrasing)
  reliably — candidates ~1.5–4B: Qwen2.5-1.5B (control), Qwen3-1.7B, Qwen3-4B, Phi-4-mini-3.8B,
  Gemma3-4B, Llama-3.2-3B, Ministral-3-3B.
- **Strongest practical local orchestrator a large fraction of the core population can run:** the
  *strongest* model that fits the Broad-Baseline/Mainstream tiers at Callosum's real context and
  acceptable low-frequency latency — candidates ~7–14B: Qwen3-8B, Ministral-3-8B, Qwen3-14B, Gemma3-12B,
  Phi-4-14B (short context caveat).

The two searches meet at ~4B, which is *both* a plausible strong-worker and a plausible light-orchestrator
— so the sweep should explicitly test whether **one 4B model can serve both roles** on the Broad Baseline,
versus a **1.7–3B worker + 7–8B orchestrator** split on the Mainstream/Accelerated tiers. Selection
criteria, in priority order: (1) obligation/scope/construct fidelity on the Ask control tasks;
(2) structured-output validity **and completion**; (3) function-calling/instruction-following;
(4) fit-at-real-context on target hardware; (5) license bundling-realism (Apache/MIT favored);
(6) low-frequency latency. **Qwen is included but not assumed the winner** — its BFCL lead and Apache
license make it a strong prior, but Phi-4-mini (MIT, reasoning-dense) and Ministral 3 (Apache) are
genuine contenders the sweep must not pre-empt.

---

## 15. Recommended later benchmark matrix (defined, NOT run)

A controlled sweep to be separately approved. **First-run freeze** discipline (freeze questions, prompts,
representations, caps, thresholds before any tuning; evaluate each cell once; stop and report), mirroring
the existing Ask experiment protocol.

**Design axis that resolves the confound (critical):** cross **model** against **representation** so the
sweep can separate "bigger model helps" from "better task representation helps." Do not vary only model
size. At minimum, each model runs under ≥2 representations (e.g., the current facet/obligation schema vs.
the pivot doc's source-anchored decomposition + evidence-conditioned context selection), with structured
decoding + adequate output budget held constant.

- **Models (GGUF, llama.cpp/Ollama):**
  - *Worker class:* Qwen2.5-1.5B (control), Qwen3-1.7B, Qwen3-4B, Phi-4-mini-3.8B, Gemma3-4B,
    Llama-3.2-3B, Ministral-3-3B.
  - *Orchestrator class:* Qwen3-8B, Ministral-3-8B, Qwen3-14B, Gemma3-12B, Phi-4-14B.
  - *Cloud orchestrator references (bounded, for the swap comparison only):* the existing Gemini path
    (and optionally one Claude/OpenAI) over the **same sealed ledger**, to isolate orchestrator quality
    from pipeline quality — reusing the staged pipeline's dual-terminal design.
- **Quantization:** Q4_K_M primary; Q5_K_M for the borderline-fit models; test **Q8 KV cache** on the
  7–8B tier to recover JUNO context headroom. Report total runtime memory (weights + KV + overhead) at the
  evaluated context, per §9 — never GGUF size alone.
- **Hardware:** **JUNO** (RTX 3050 8 GB / i7-8700) as the near-term substrate; **one Apple-Silicon
  reference** (16 GB baseline + ideally a 24–32 GB Mainstream unit) before any cross-platform claim; **one
  integrated-graphics / CPU-only reference** for the Accessibility Floor. Record full host state per the
  latency contract (§15 of LATENCY.md).
- **Tasks (Callosum's real Ask control plane, not generic leaderboards):** decomposition / obligation
  preservation; scope selection (narrow vs. broad); minimum-sufficient-context selection (the A/B/C/D
  envelope task); source-local proposition extraction under the verbatim-quote constraint; coverage/gap
  interpretation; terminal synthesis. Use the frozen questions (`q_aib`, `q_builtenv`) plus a small
  held-out set; freeze before tuning.
- **Metrics:** obligation fidelity (preserved / drifted / starved / invented — the A-series scoring);
  relationship & operation fidelity; exact construct identity; open-request preservation; structured-output
  **validity + completion** rate; **contamination/fabrication** rate at the terminal fork (the "honored
  the sealed ledger vs. invented domain facts" behavior the staged run already surfaced); low-frequency
  **latency** (cold/warm, per call); **peak VRAM/RSS at real context**; context headroom. Keep correctness
  metrics separate from latency receipts (LATENCY.md).
- **Stop criteria:** first-run freeze; one evaluation per (model × representation × hardware) cell;
  pre-register the fidelity threshold that would justify promoting a worker size or adopting a local
  orchestrator; separate model effect from representation effect via the crossed design; stop and report —
  **no tuning to chase a disappointing cell.**

**Do NOT** in the sweep: tune after the freeze; substitute cloud for a failing local cell mid-run; change
verifier thresholds; alter the frozen questions; treat "loads" as "passes."

---

## 16. Cost / accessibility model (conceptual)

| Path | Where compute lives | Cost profile | Privacy | Best-fit tier |
|---|---|---|---|---|
| **Fully local** (worker + local orchestrator) | On-device | Zero marginal $; pays in RAM/VRAM/battery/latency; one-time model download | Strongest (no egress) | Broad Baseline → Accelerated |
| **Small-local + focal cloud** (local worker/deterministic core; cloud orchestrates the low-frequency control decisions) | Mixed; cloud only for ~1–2 low-frequency calls/query | Low marginal $ (orchestration is low-frequency, so few tokens leave); free-tier often sufficient | Opt-in egress for a *small* control-plane payload; library text stays local | Accessibility Floor; any user preferring it |
| **Cloud-heavy** (cloud in the control plane and/or per-worker-task) | Mostly cloud | Higher $ + higher egress; per-chunk cloud is the expensive shape the staged design explicitly avoids | Weakest (most content egresses) | Not recommended as a default |

The economically and philosophically favored shape matches the staged pipeline's own logic: **keep the
high-volume worker and the deterministic substrate local; spend cloud (if at all) only on the
low-frequency orchestration decisions or optional terminal prose.** Because orchestration is
low-frequency, the *small-local + focal-cloud* path leaks very little and costs very little — it is a
genuinely good Accessibility-Floor option, not a booby prize. Fully-local remains the privacy-maximal
default wherever the tier supports it.

---

## 17. Risks / failure modes

- **Attributing A0–A3 failure to capacity (confound risk).** The single biggest analytical risk is
  concluding "1.5B is too small" when the cause was representation/prompt. The crossed model×representation
  sweep (§15) is the mitigation; without it, the study would over-claim.
- **"Loads ≠ runs" over-optimism.** Judging feasibility on GGUF size or a successful load, not on total
  runtime memory at real context and real task latency. Mitigation: §9 math + the sweep's
  memory-at-context and latency metrics.
- **JUNO ≠ Apple Silicon.** Concluding cross-platform feasibility from a CUDA desktop. Mitigation: require
  an Apple-Silicon reference before cross-platform claims (§7, §15).
- **Accessibility regression.** Letting a bigger baseline worker degrade the 8 GB floor. Mitigation:
  tier-aware worker size; keep the floor worker small; deterministic core independent of any model.
- **Egress drift.** A cloud-orchestration fallback becoming a silent default. Mitigation: keep it opt-in
  behind the existing consent gate; never silent (invariant #3; the existing "no silent cloud fallback"
  Local-AI rule).
- **Bigger model, same failure.** A stronger orchestrator may still lose scope/obligations if the
  representation is wrong — grammar guarantees structure, not semantics. Mitigation: the sweep tests the
  representation axis explicitly; adopt a local orchestrator only if it clears a *pre-registered*
  fidelity threshold, not merely "feels better."
- **License/bundling risk.** Shipping (vs. user-downloading) a Gemma/Llama-licensed model without legal
  review. Mitigation: favor Apache/MIT for anything *bundled*; treat custom-license models as
  user-download options; apply the repo's existing license-boundary discipline.
- **Model churn.** Any specific pick ages in months. Mitigation: the durable output is the *size-class +
  selection-criteria + swappable-provider* design, not a frozen model name; the roster is a `providers`
  list already.
- **Field-evidence thinness.** Population device mix is triangulated, not censused. Mitigation: the
  Decision authorizes a *benchmark* (cheap, reversible), not an architecture commitment; and Callosum's
  own opt-in, zero-content telemetry could later add a *coarse, consented* device-capability signal to
  replace [UNKNOWN]s with [DIRECT DATA] — a separate, gated proposal, not built here.

---

## 18. Decision

**HARDWARE EVIDENCE SUPPORTS LOCAL-ORCHESTRATOR BENCHMARKING.**

The core population's hardware — a 16 GB institutional baseline, 16 GB-minimum new Apple Silicon, common
Apple-Silicon acceleration via unified memory, and a 4–5 year (not decade) replacement cycle — clears the
bar for a **~4B local orchestrator/worker at real context on the Broad Researcher Baseline** and a
**~7–8B orchestrator on the Mainstream/Accelerated tiers**, both well above the 1.5B ceiling that a weak
laptop originally set. Orchestration's low frequency makes the latency of a stronger local model
acceptable. The frontier crosswalk (especially the NVIDIA SLM-agentic thesis) says Callosum's *narrow,
bounded-corpus* orchestration job is exactly the kind that small-to-mid models with escalation can
plausibly do — while the big-lab open-web research products' frontier requirement should not be assumed
to transfer.

This is a decision to **benchmark**, not to commit an architecture. It rests on two guardrails: (1) the
1.5B worker failures are real but *confounded* — the sweep must cross model against representation to earn
any capacity conclusion; and (2) **small-local + focal-cloud orchestration is retained as the
Accessibility-Floor design**, so the local-orchestrator path is the *core-tier* option, not a universal
mandate. The remaining population-device uncertainty is [UNKNOWN] but does not block the benchmark — the
benchmark is precisely the cheap, reversible instrument that resolves the open questions.

*(Not chosen: "supports only small-local + cloud" — under-reads the 16 GB baseline evidence; "evidence
too weak" — the procurement/Apple-base-RAM/replacement-cycle/inference-throughput evidence is solid enough
to justify a cheap benchmark, and the benchmark itself resolves the residuals; "poorly matched to core
hardware" — contradicted by the 16 GB baseline and Apple-Silicon prevalence.)*

---

## 19. Next step (no implementation)

**A controlled JUNO/model sweep is justified.** No code, no downloads, no runs are authorized by this
report — it defines the sweep; a separate approval executes it.

Candidate classes that earned inclusion:
- **Worker class (~1.5–4B):** Qwen2.5-1.5B (control), Qwen3-1.7B, Qwen3-4B, Phi-4-mini-3.8B, Gemma3-4B,
  Llama-3.2-3B, Ministral-3-3B.
- **Orchestrator class (~7–14B):** Qwen3-8B, Ministral-3-8B, Qwen3-14B, Gemma3-12B, Phi-4-14B.
- **Cloud orchestrator references (bounded):** the existing Gemini path (± one Claude/OpenAI) over the
  same sealed ledger.

Required before any cross-platform conclusion: an **Apple-Silicon reference** (16 GB baseline + a 24–32 GB
Mainstream unit) and a **CPU-only/integrated-graphics** Accessibility-Floor reference. The sweep must cross
**model × representation**, measure **total runtime memory at real context** and **low-frequency latency**,
score on the **Ask control-plane tasks** (not generic leaderboards), and **freeze before tuning**. Only a
model that clears a **pre-registered fidelity threshold** on the crossed design would justify promoting a
worker size or adopting a local orchestrator; the 1.5B-vs-representation question is answered by the
crossed design, not assumed.

---

## Appendix — direct answers to the 10 required questions

1. **Are research-active academics plausibly using materially stronger hardware than the weak laptop that
   originally constrained 1.5B?** Yes, plausibly. Institutional standard configs are now 16 GB machines
   and new Apple Silicon is 16 GB-minimum, on a 4–5 year cycle [PROCUREMENT PROXY / DIRECT DATA]. The
   population device *census* is [UNKNOWN], but the baseline is clearly well above a weak laptop.
2. **What hardware envelope should Callosum optimize its richest LOCAL path around?** The **Broad
   Researcher Baseline (16 GB RAM / unified memory)** for the default rich path, extending to the
   **Mainstream tier (24–32 GB)** for a stronger orchestrator — i.e., a ~4B model comfortably, 7–8B where
   the tier allows.
3. **What accessibility floor should remain supported?** The **8 GB / integrated-graphics / older-machine
   floor**: deterministic core + a small (≤~1.5–3B) worker, with orchestration via opt-in focal
   cloud/free-tier. Never capped by, but always serving, this floor.
4. **Is JUNO below / near / above / or architecturally different from the likely core-user local-inference
   envelope?** **Architecturally different, per axis:** GPU-*above* the typical (integrated-graphics)
   research laptop, CPU-*below* modern machines, and 8 GB-capacity-capped vs. Apple's larger unified
   memory. Not a proxy for Apple Silicon.
5. **What size model can JUNO reasonably run as a low-frequency orchestrator?** **~4B comfortably at real
   context; 7–8B Q4 with reduced context and/or Q8 KV** (Qwen's GQA helps); 12–14B only via slower
   system-RAM offload [DIRECT DATA/INFERENCE].
6. **What size could a modern 16/24/32 GB Apple-Silicon machine run for the same job?** **16 GB → ~7–8B
   comfortably; 24 GB → ~14B; 32 GB+ → ~32B**, at usable low-frequency latency (bandwidth-bound)
   [DIRECT DATA].
7. **Does the evidence justify reopening the 1.5B constraint?** **Yes — reopen it as a tested hypothesis.**
   The hardware constraint that set 1.5B has clearly loosened; whether a bigger model *fixes* the observed
   failures is confounded (model vs. representation) and must be measured, not assumed.
8. **Is there a plausible architecture of small-local worker = baseline, stronger local orchestrator =
   preferred open path, Gemini/Claude/OpenAI = optional substitutes?** **Yes, plausible** and partly
   precedented in-repo (the staged pipeline's language/schema separation is the antecedent). It is a
   genuine extension, not something already built.
9. **How strong does the orchestrator actually need to be?** **Open empirical question — and there is
   credible evidence that below-frontier generalists may suffice.** The NVIDIA SLM-agentic thesis and
   BFCL/IFEval signals suggest small-to-mid models handle bounded, corpus-grounded orchestration with
   escalation; the big-lab frontier requirement is for *unbounded open-web* research and should not be
   assumed to transfer. The sweep sets the actual floor.
10. **What candidate models should a later benchmark evaluate on JUNO?** See §14–15 / §19: worker class
    Qwen2.5-1.5B (control) + Qwen3-1.7B/4B + Phi-4-mini + Gemma3-4B + Llama-3.2-3B + Ministral-3-3B;
    orchestrator class Qwen3-8B/14B + Ministral-3-8B + Gemma3-12B + Phi-4-14B; with bounded cloud
    references over the same sealed ledger.

---

## Sources

Hardware ecology (procurement / replacement / configuration):
- Xavier Univ., Computer Replacement & Refresh Policy — https://www.xavier.edu/policy/documents/Computer-Replacement-And-Refresh-Policy.pdf
- Univ. of Akron, Workstation Refresh Policy — https://www.uakron.edu/infosec/policies/workstation-refresh-policy
- SUNY Purchase, Computer Replacement Cycle — https://www.purchase.edu/live/blurbs/1844-computer-replacement-cycle
- Western Kentucky Univ. CEBS, 5-Year Replacement — https://www.wku.edu/cebs/faculty_and_staff/computer-support.php
- Wesleyan Univ. ITS, Refurbished-Hardware / refresh policy — https://www.wesleyan.edu/its/policies/refurb-hardware.html
- CU Boulder OIT, Standard Computers — https://oit.colorado.edu/software-hardware/standard-computer-hardware-and-software/standard-computers
- CU Boulder OIT, Faculty Computer Purchase Program — https://oit.colorado.edu/software-hardware/faculty-computer-purchase-program
- Ohio State Univ. Engineering Technology Services, Faculty/Staff Equipment Configurations — https://ets.osu.edu/facultystaff-equipment-configurations
- EDUCAUSE 2024 Faculty and Technology Survey — https://www.educause.edu/research-and-publications/research/analytics-services/surveys/2024/educause-faculty-survey

Apple Silicon / OS share:
- Apple M4 (Wikipedia, base-RAM shift) — https://en.wikipedia.org/wiki/Apple_M4
- Apple Silicon for Local LLMs — Mac Buyer's Guide — https://llmhardware.io/guides/apple-silicon-for-llms
- 2025 Desktop OS Market Share — https://safeitexperts.com/en/2025-desktop-operating-system-market-share.html
- macOS Market Share Statistics — https://www.techlila.com/macos-market-share-statistics/

Discrete-GPU prevalence (business laptops):
- Dell Latitude (Wikipedia) — https://en.wikipedia.org/wiki/Dell_Latitude
- Dell Latitude 3440 spec (integrated GPU) — https://www.dell.com/support/manuals/en-us/latitude-14-3440-laptop/latitude_3440_ss/gpuintegrated

Local-model memory / latency:
- LLM VRAM Requirements (Spheron) — https://www.spheron.network/blog/gpu-memory-requirements-llm/
- LLM Context Length GPU Memory / KV cache (Lyceum) — https://lyceum.technology/magazine/llm-context-length-gpu-memory-requirements/index.html
- Q4 KV cache / 32K in 8 GB (dev.to) — https://dev.to/plasmon_imp/q4-kv-cache-fit-32k-context-into-8gb-vram-only-math-broke-209k
- LLM Inference Consumer GPU Performance (Puget Systems) — https://www.pugetsystems.com/labs/articles/llm-inference-consumer-gpu-performance/
- GPU ranking for local LLMs (Hardware Corner) — https://www.hardware-corner.net/gpu-ranking-local-llm/
- Local LLM benchmarks on Apple Silicon (ModelPiper) — https://modelpiper.com/blog/local-llm-benchmarks-apple-silicon
- apple-silicon-llm-bench (GitHub) — https://github.com/john-rocky/apple-silicon-llm-bench
- MLX vs llama.cpp (Groundy) — https://groundy.com/articles/mlx-vs-llamacpp-on-apple-silicon-which-runtime-to-use-for-local-llm-inference/

Model landscape (as of 2026-09):
- Qwen3 (GitHub) — https://github.com/qwenLM/qwen3 ; Simon Willison, Qwen 3 — https://simonwillison.net/2025/Apr/29/qwen-3/
- Gemma 3 developer guide — https://developers.googleblog.com/en/introducing-gemma3/ ; Gemma 3 Technical Report — https://arxiv.org/html/2503.19786v1
- Llama 3.2 3B Instruct (HF) — https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct
- Mistral Small 3 — https://mistral.ai/news/mistral-small-3/ ; Mistral 3 / Ministral 3 — https://mistral.ai/news/mistral-3/
- Phi-4 (HF) — https://huggingface.co/microsoft/phi-4 ; Phi-4-mini-instruct (HF) — https://huggingface.co/microsoft/Phi-4-mini-instruct

Capability signals (function-calling / instruction-following / structured output):
- Berkeley Function Calling Leaderboard (Gorilla) — https://gorilla.cs.berkeley.edu/leaderboard.html
- llama.cpp GBNF grammars README — https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md
- Constrained decoding guide — https://www.aidancooper.co.uk/constrained-decoding/
- Gemma 4 / Phi-4 / Qwen3 accuracy–efficiency tradeoffs — https://arxiv.org/html/2604.07035v1

Frontier-research infrastructure:
- Anthropic multi-agent research system (via ZenML LLMOps DB) — https://www.zenml.io/llmops-database/building-a-multi-agent-research-system-for-complex-information-tasks
- Anthropic, when to use multi-agent systems — https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them
- OpenAI, Introducing deep research — https://openai.com/index/introducing-deep-research/
- NVIDIA, Small Language Models are the Future of Agentic AI — https://arxiv.org/abs/2506.02153
- Google, Gemini 3 to Search & AI Mode — https://blog.google/products-and-platforms/products/search/gemini-3-search-ai-mode/
- Gemini 1.5 Flash distillation / cost — https://cloud.google.com/blog/products/ai-machine-learning/experimentation-to-production-with-gemini-and-vertex-ai

In-repo companions:
- `.claude/docs/research/2026-09-07_ask-cli-experiment-scoping.md` (staged-synthesis architecture)
- `.claude/docs/research/2026-09-07_ask-run-0.5-control-plane-pivot.md` (control-plane pivot; "model speaks language, code speaks schemas")
- `.claude/LATENCY.md` (latency contract; managed Local AI envelope)
- `.claude/SCRATCH.md` A0–A3 entries (planner experiments; model×representation confound)
