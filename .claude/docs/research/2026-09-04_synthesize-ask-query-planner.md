# Synthesize → Ask: scoping a query planner

**Architectural research. No implementation.** 2026-09-04, at increment 575.

Prompted by Vasiliki Meletaki's real failure and by Cliff's product commitment: *users should not have
to learn prompt engineering to use Callosum*. Her broad research questions are the representative case;
Cliff's narrow ground-truth test questions were the unrepresentative ones. Her behaviour is the
evidence, not the error.

---

## 1. Executive summary

**The failure.** Asked for *"a synthesis of the brain areas involved in the human perception of built
environment based on fMRI and EEG studies… aesthetic appreciation, coherence, fascination, hominess,
ceiling height, visuospatial processing and more. Give me a list of the brain areas involved and their
role"*, Ask returned **0 of 4 claims verified**. Splitting it into narrower questions by hand did not
rescue it either.

**What I expected to find, and what the experiment actually showed.** I hypothesised that the binding
constraint was *claim granularity*: verification scores a whole sentence against a ≤80-word quote, so a
sentence naming six constructs should be structurally unverifiable. Cliff improved my three-arm design
into a 2×2 factorial (claim shape × retrieval quality), which is what exposed the truth. **The
hypothesis is refuted.**

| | | verified |
|---|---|---|
| **Local 1.5B**, current claims, current retrieval | A | **0/9** |
| Local, current claims, references excluded | B | 0/8 |
| Local, **atomic claims**, current retrieval | C | 0/7 |
| Local, atomic claims, references excluded | D | 0/6 |
| **Gemini**, current claims, current retrieval | A ×3 | **5/6, 1/4, 1/8** |
| Gemini, current claims, references excluded | B | 1/5 |
| Gemini, **atomic claims**, current retrieval | C | **0/5** |

**Totals: local 1.5B 0/30 verified. Gemini 8/28.** Same question, same retrieval, same thresholds, same
library.

**The three findings that matter:**

1. **Model capability is the dominant factor, by a wide margin.** The managed Local AI model
   (Qwen2.5-1.5B-Instruct Q4_K_M) produced **zero** verified citations across four conditions and 30
   citations. It quotes verbatim competently (21/30 exact) but writes sentences its own quotes do not
   support: **median NLI support 0.009**, median retrieval cosine 0.534. Gemini on identical evidence
   reaches 0.978 support and 6/6 retrieval in its best run.
2. **Verification is correctly calibrated and is not the problem.** A control on the NLI scorer:
   identical sentences 0.989, a genuine paraphrase entailment 0.990, unrelated sentences 0.013
   (contradiction 0.972). The same thresholds that reject the local model's output accept Gemini's.
   *Nothing here argues for loosening a threshold.*
3. **A real architectural gap remains, but it is smaller than assumed.** Even Gemini typically returns
   **one** verified claim for this six-construct question (5/6, 1/4, 1/8, 1/5). That is a thin answer to
   a broad question — which is where planning, coverage, and output shape genuinely help.

**Recommended direction.** A query planner is worth building, but **it is not the first move and it
would not have fixed Vasiliki's case.** Sequence: (i) tell the truth about provider capability and stop
blaming the user's library; (ii) make evidence coverage a first-class, per-facet concept; (iii) fix the
output-shape mismatch; (iv) only then per-facet retrieval and decomposition.

**Confidence.** High on the local-vs-cloud gap (0/30 vs 8/28 is not a subtle effect, replicated across
four conditions). High on atomicity being refuted (it never helped anywhere and coincided with
Gemini's worst run). Moderate on the residual architectural gap — Gemini runs vary 1–5 verified, n=3.

---

## 2. Current Synthesize → Ask architecture

### Call graph

```
20_synthesis.jsx  (Ask box, section chips)
  └─ POST /summarize   {scope_type:"query", query, top_k: 8}      ← top_k HARDCODED, line 164
       routers/summaries.py::summarize_start → BackgroundTasks
         └─ _run_summarize_job → summarization/pipeline.py::summarize_scope
              Phase 1  _source_chunks_for_scope
                        ├─ SELECT chunks JOIN attachments  (live papers, ARTICLE_DOCUMENT_ROLES)
                        ├─ optional  chunks.section IN (scope.sections)
                        ├─ exclude_repeated_boilerplate_chunks   (per-paper running headers)
                        └─ _rank_chunks_for_query
                             ├─ current_chunk_embedding_ids  (inc 575)
                             ├─ embed_chunks (only stragglers)
                             └─ vector_store.search(top_k, candidate_embedding_ids)
              Phase 2  generator.generate                          ← no DB handle held
                        managed_summary_generator → with_managed_output_contract
                          → GeminiSummaryGenerator → providers.complete
                             _prompt(): "4 to 7 objects … exactly one complete standalone sentence"
                             managed-local only: json_schema grammar (_PRIMARY_SYNTHESIS_SCHEMA)
                        _parse_response_text → salvage_complete_objects on failure (inc 575)
              Phase 3  _refresh_source_chunks  (re-read; guards Phase-2 drift)
                        verification.py::verify_many
                        _insert_summary / _persist_verification
  └─ GET /summarize/{job_id} → summaries_response.py → 20_synthesis.jsx
```

### Key files and responsibilities

| stage | file | notes |
|---|---|---|
| entry | `app/frontend/js/20_synthesis.jsx:164` | **`top_k: 8` hardcoded for query scope.** Papers scope scales to `MAX_CHUNKS = 50`; query scope has no user control. |
| API | `app/backend/api/routers/summaries.py:105` | `SummarizeRequest` (`top_k` ≤ 50, ≤16 sections); async job |
| retrieval | `app/backend/summarization/pipeline.py::_source_chunks_for_scope` | one candidate pool; sections filter; boilerplate filter |
| ranking | same, `_rank_chunks_for_query` | single query embedding; `partition_by_phase` section-family reorder (inc 479) |
| vector | `app/backend/embeddings/vector_store.py::SQLiteVecVectorStore` | `max_knn_k = 4096`; candidate scoping via temp table |
| prompt | `integrations/gemini/generator.py::_prompt` | 4–7 objects, 1–3 citations, ≤80-word verbatim quotes |
| grammar | `app/backend/llm/managed_local.py::_PRIMARY_SYNTHESIS_SCHEMA` | **managed-local only** — cloud providers are unconstrained |
| verification | `app/backend/summarization/verification.py::verify_many` | three gates, below |
| response | `app/backend/api/routers/summaries_response.py` | `scope_ref_json` carries `source_chunk_count`, `generation_truncated` |

### The verification contract (the invariant everything else must respect)

`verify_many` scores `(sentence, citation)` pairs through **three independent gates**:

| gate | computation | threshold |
|---|---|---|
| retrieval | `cosine(embed(sentence), cited_chunk_embedding)` | ≥ 0.70 |
| quote | the quote must occur **verbatim** in the chunk | = 1.00 |
| support | NLI entailment, **premise = the quote**, hypothesis = the **whole sentence** | ≥ 0.632 |

Plus `contradicted` when contradiction ≥ 0.55 *and* exceeds support. Note the premise is the **quote**,
not the chunk — deliberate (`verification.py`), so a long page cannot truncate the cited passage out of
the cross-encoder's input.

---

## 3. Why broad queries fail

The prompt asked me to separate four candidate causes. The experiment separates them cleanly.

### A. Retrieval insufficiency — real, but not decisive

- Query scope gets **8 chunks for the entire question** — ~1.3 per construct for six constructs.
- One embedding represents the whole question; there is **no MMR, diversity constraint, per-document
  cap, or per-facet budget** anywhere in `_rank_chunks_for_query`.
- `references` is the **largest section in the corpus — 5,635 of 23,875 chunks (24%)** — and
  bibliography text is keyword-dense across many topics. A real run retrieved **4 of 8 chunks from
  `section='references'`**. Vasiliki's own screenshot shows the same: Introduction ×3, Abstract,
  References, plus an off-target "transient sadness and happiness" Results chunk.
- **But excluding references did not raise verified yield** (local 0→0; Gemini 1/8 → 1/5, noise). It
  improved *prose quality* — vacuous "X has been studied using fMRI" became "increased activity in the
  insula, anterior cingulate" — without improving verification.

### B. Generation granularity — refuted as the binding constraint

The hypothesis: a sentence spanning six constructs cannot be entailed by one ≤80-word quote. Plausible,
and the prompt does push toward it ("4 to 7 objects, each … exactly one complete standalone sentence"),
producing sentences like *"The brain areas involved in aesthetic appreciation, coherence, fascination,
hominess, ceiling height, visuospatial processing, and more are studied in neuro-architecture."*

**The experiment refutes it.** An explicit atomic-claim instruction ("one region, one role, one study;
do not combine constructs; state what was found, not that it was studied") yielded **0/7** local,
**0/6** local with clean retrieval, and **0/5 on Gemini — its worst run of five.** Granularity is a real
property of the output, but it is not what gates verification here.

*Why the intervention may actively hurt:* pushing a model toward specific findings appears to push it
past what its quote supports. Suggestive, n=1 on Gemini — but enough to warn against shipping a prompt
change of this kind on intuition.

### C. Verification granularity — not the problem

The scorer control settles it:

| pair | support |
|---|---|
| identical sentence | 0.989 |
| *"Participants showed increased activation in the orbitofrontal cortex during aesthetic judgments of buildings"* → *"Orbitofrontal cortex activity increased during aesthetic judgment of buildings"* | **0.990** |
| unrelated sentences | 0.013 (contradiction 0.972) |

The middle row is exactly the atomic claim shape a planner would aim to produce, and it clears the
threshold comfortably. **Verification is ready for better claims; it is not obstructing them.**

### D. Absence of evidence in the library — ruled out

Gemini reached **5/6 verified on the same 8 chunks**. The evidence to answer this question is present
and retrievable. The library is not the limitation — which matters, because the UI currently says it is
(§11).

### The actual dominant cause: generation fidelity, which is a model-capability property

| | local 1.5B | Gemini |
|---|---|---|
| verified | **0/30** | 8/28 |
| quote verbatim (=1.0) | 21/30 | 28/28 |
| retrieval ≥ 0.70 | 3/30 | 19/28 |
| support ≥ 0.632 | **0/30** | 7/28 |
| median support | **0.009** | 0.036 (best run 0.978) |
| median retrieval | 0.534 | 0.776 |

The local model **copies quotes correctly and then writes a sentence about something else**. Both the
retrieval gate (is the sentence about the chunk?) and the support gate (does the quote entail it?) fail
together, which is the signature of an unfaithful claim rather than of weak evidence.

### Does the system know which of these is happening? No.

There is no mechanism distinguishing "no evidence retrieved" from "evidence retrieved but unfaithful
claims generated". The single terminal state is `summary_status = "flagged"` plus one message.

---

## 4. Intervention options

| | option | verdict |
|---|---|---|
| A | Pre-retrieval decomposition | **Worth doing, later.** Fixes coverage, not fidelity. Would not have fixed the observed failure. |
| B | Iterative retrieval after a coverage check | Valuable but depends on a coverage model that does not exist yet (§8). |
| C | Adaptive top-k, no decomposition | Cheapest retrieval win. Query scope's hardcoded 8 is indefensible for a six-construct question. Does not address fidelity. |
| D | Multi-query retrieval, single synthesis | Good cost/benefit; reuses `search_similar(query_vector=…)` unchanged. |
| E | Hierarchical: retrieve → verify → synthesise verified intermediates | Best *evidential* story; highest cost; premature until fidelity is solved. |
| F | Hybrid | Where the staged plan lands (§19). |
| G | **No planner; improve retrieval/reranking** | Measured: reference exclusion did **not** improve verified yield. Insufficient alone. |
| H | **Atomic claims / better evidence matching** | **Measured and refuted.** Made Gemini worse. |

Cost note: decomposition multiplies embedding calls, vector searches, model calls and verification
passes by the facet count. On the managed local model a single 8-chunk synthesis takes **250–375 s**; a
six-facet plan would be 25–35 minutes. That is not viable on the current local model — an independent
argument for sequencing capability before planning.

---

## 5. Query decomposition analysis

**Triggers.** Vasiliki's question carries its own facet list ("aesthetic appreciation, coherence,
fascination, hominess, ceiling height, visuospatial processing"), a modality contrast (fMRI vs EEG),
and an output shape ("a list … and their role"). Deterministic signals — enumerations, conjunctions,
compare/contrast language, multiple output dimensions — get a long way without a model call.

**The user already named the facets. Prefer that to inference.** Having the model decide how to
decompose a question is the model making a structural claim about the literature — judgment, not
narration, and the wrong side of PRINCIPLES #4 (the deterministic substrate is the source of truth) and
#5 (the human is the filter). A parsed, **visible and editable** facet list keeps the human as the
filter. If the model ever proposes a split, show it before it is used.

**Representation.** Existing conventions suggest a frozen dataclass beside `SummaryScope` in
`pipeline.py` rather than new vocabulary. `SummaryScope` already carries `sections`; a facet list is the
same kind of scoping object.

**Dependencies and recursion.** Facet retrieval is parallel; a "which regions recur" facet is a
dependent aggregation over *verified* intermediates. **Recursion should be prohibited in v1** — bound
depth at 1. Nothing observed here justifies recursive planning, and it is the fastest route to runaway
cost.

**Determinism.** Retrieval, embedding, verification and thresholds are already deterministic. Managed
local generation is temperature 0 / seed 42 (`managed_local_ai.rs`); **cloud generation is not** — the
three Gemini replicates of the identical arm returned 5/6, 1/4 and 1/8. "Deterministic enough" should
mean: *plan construction* is deterministic given the same question; *generation* is not, and the UI
should never imply otherwise.

**Inspectability.** Yes — retain the plan. §17.

---

## 6. Evidence-grounding architecture

The hierarchy the prompt proposes — chunk → atomic claim → verified finding → cross-source synthesis —
fits the existing data model, which already stores per-citation `chunk_id`, quote, page, bbox,
coordinate precision, and three confidences.

**The hard constraint on aggregation:** a synthesis statement spanning facets is entailed by *no single
quote*, so it can never clear the support gate. Therefore an aggregated statement must either (a) carry
the union of its constituents' provenance and be marked as an aggregation rather than a verified claim,
or (b) not be generated at all. **Do not generate a connecting sentence across facets** — no retrieved
chunk supports a claim about the relationship *between* facets.

**Should final synthesis operate over verified claims rather than raw chunks?** Evidentially yes. But
on the measured numbers it would currently have **nothing to operate on** — 0 verified claims locally,
~1 on Gemini. Sequencing matters more than the ideal.

---

## 7. Atomic claim analysis

Verification is sentence-level; one sentence maps to 1–3 citations, each scored independently, and a
sentence is `flagged` unless all of its citations verify. So a compound sentence is *penalised* — the
architecture already prefers atomic claims.

**But making the model produce them, by instruction, did not work** (0/7, 0/6, 0/5). Atomic claim
generation should therefore be treated as a **measured hypothesis, not a design principle**. If revisited,
the promising variant is *post-hoc decomposition* — split a generated sentence into propositions and
verify each against its own quote — which does not depend on instruction-following, and which the
verification stack would accept (the 0.990 control). That is a different, testable intervention.

---

## 8. Evidence coverage model

Callosum has no concept of "do I have enough evidence?" The terminal states should be distinguished:

| state | meaning |
|---|---|
| no evidence retrieved | nothing matched this facet |
| retrieved, weakly matched | retrieval below threshold |
| retrieved, claims unfaithful | **the observed local case** — evidence fine, generation not |
| verified but sparse | one source |
| multiple independent sources | the strong case |
| conflicting verified evidence | `contradicted` already exists as a status |

Vasiliki should have been able to see *"aesthetic appraisal: verified · ceiling height: limited ·
hominess: no evidence retrieved · EEG: sparse"* rather than one global failure. Coverage should drive
further retrieval, the abstention wording, and the UI — and it is the prerequisite for honest partial
answers.

---

## 9. Retrieval budgeting

**Do not invent numbers — a precedent already ships.** `methods/critical_review.py`'s
`search_contested_claim_scopes` performs per-target retrieval at **`CRITIQUE_TOP_K = 5` × `max_claims =
12` = 60 retrievals**, batched (inc 490) with per-stage progress. A facet planner should adopt that
shape and those magnitudes rather than new ones.

Safeguards: cap facets (≤ 8, matching the enumerations observed), depth 1, a global chunk cap, dedupe
across facets by `chunk_id`, and a wall-clock budget. Early termination when a facet is clearly
unsupported or retrieval returns only duplicates.

**Latency is the binding practical constraint locally**: 250–375 s per single-pass synthesis measured
today.

---

## 10. Local-first analysis

This is the uncomfortable finding. **The managed Local AI model cannot currently support Synthesize →
Ask on a question like this: 0/30 verified.** It is not a retrieval, threshold, or prompt problem.

Implications:

- Planner work targeted at local users would be building on a generation step that fails first.
- Deterministic parts (facet parsing, retrieval, dedupe, coverage accounting, verification) are all
  local and cheap. **The expensive, unreliable part is exactly the part the local model does worst.**
- Options worth separate investigation: a larger local model for synthesis specifically; presenting
  Local AI's synthesis limitation honestly; or restricting the *broad-question* path to capable
  providers while narrow questions stay local.

**Immediate, non-architectural action:** Vasiliki has a Gemini key. On this question that is the
difference between 0 and some verified claims.

---

## 11. UX recommendation

**The abstention is currently wrong, and that is the cheapest fix in this report.**

> "No claim cleared local verification — your question may not be well-addressed in these papers."
> — `20_synthesis.jsx:375`

Measured: her papers **did** address it (Gemini 5/6 on the same chunks). The message blames the user's
library for a limitation of the model. This is the same defect class as inc 573's "repair your cache"
and inc 574's "restart to install" — asserting a cause the evidence does not establish.

It should distinguish, at minimum, *no evidence found* from *evidence found but claims could not be
verified*, and where the provider is the managed preview model it should say so.

Planning visibility: **transparent but automatic** — show detected facets and per-facet coverage,
progressive results as facets complete, no plan-editing UI in v1. Do not turn Ask into an agent
dashboard.

---

## 12–15. Intent preservation, output contract, execution vs answer, state

**The output-shape mismatch is a first-class finding.** Vasiliki asked for *"a list of the brain areas
involved and their role"* — an enumerable set of (region → role → modality → source) rows. The synthesis
contract can only ever return **4–7 prose sentences** (`_PRIMARY_SYNTHESIS_SCHEMA`). **No amount of
decomposition fixes a shape mismatch**: splitting into six subquestions returns 6 × (4–7 prose
sentences), which is why manual splitting still disappointed.

This argues for the prompt's execution-plan / answer-contract distinction being **real and useful**:

- *execution plan* — which facets to search, budgets, dedupe
- *answer contract* — the shape owed back: rows, columns, and which requested dimensions were answered

With the invariant: **every requested dimension is either answered with verified evidence or explicitly
marked unsupported. Silent omission is failure.**

**State:** one request should carry an in-memory plan object; the existing `JobStore` already provides
progress and cancellation. No new persistence is needed for v1 — but the plan should be recorded
alongside the summary (`scope_ref_json` already carries per-run metadata such as `source_chunk_count`
and `generation_truncated`, so this needs no migration).

---

## 16. Failure modes

Beyond those the prompt lists, the inspection and experiment add:

- **Unfaithful generation that quotes correctly** — the observed local failure; a planner would multiply
  it across facets rather than fix it.
- **A prompt intervention that helps one model and harms another** — measured (atomic claims: Gemini
  5/6 → 0/5). Any prompt change must be tested per provider.
- **Provider variance masquerading as a system property** — identical Gemini runs gave 5/6, 1/4, 1/8.
  Single-run evaluations of planner changes will mislead.
- **Reference-list chunks consuming the evidence budget** — 24% of the corpus, measured 4/8 in a real run.
- **Latency-driven abandonment** — a six-facet local plan is 25–35 minutes.
- **The abstention teaching users a false lesson** — a user told their library is inadequate may go and
  add papers that were never the problem.

---

## 17. Observability

A planner turns one opaque pass into many. Minimum trace: the question, complexity signals and whether
planning triggered, facets, per-facet retrieval counts and chunk ids, dedupe decisions, coverage state,
per-citation **three-gate confidences** (already computed — currently discarded after status
derivation), and aggregation inputs.

The three gate scores are the single highest-value diagnostic: they distinguish "no evidence" from
"unfaithful claim" instantly, and they are already computed and thrown away. **Persisting them would
have answered this entire investigation without a bespoke experiment.**

Never log paper content beyond the quotes already stored.

---

## 18. Interaction with existing features

Reusable today: `search_contested_claim_scopes` (per-target retrieval + budgets + progress),
`search_similar(query_vector=…)`, `verify_many`, `JobStore`, `scope_ref_json` for per-run metadata.

**Do not generalise yet.** Ask should be the only implementation target. LLM Critique already has its
own per-claim retrieval; a shared planner abstraction should be extracted only after Ask's version has
survived contact with real questions.

---

## 19. Recommended architecture

### Minimal viable (highest value per unit risk)

1. **Honest abstention + provider disclosure.** Stop blaming the library; distinguish no-evidence from
   claims-not-verified; name the managed preview model when it is the provider. *Cheapest item here and
   it addresses a live user harm.*
2. **Persist the three gate confidences** per citation. Turns future diagnosis into a query.
3. **Adaptive `top_k` for query scope.** The hardcoded 8 is indefensible; scale with detected facets
   within the existing ≤50 cap.
4. **Default query-scope retrieval to exclude `references`.** A bibliography entry is a pointer to a
   finding, never the verbatim evidence for a claim. (Backlog #82.)

### Robust target

5. **Evidence coverage as a first-class model** (§8), driving retrieval, abstention and UI.
6. **Answer contract** separate from execution plan (§12–15), with the no-silent-omission invariant.
7. **Per-facet retrieval** on `search_contested_claim_scopes`' shape, facets from the user's own words.
8. **Post-hoc claim decomposition** — split then verify — as a *measured* experiment, not an assumption.

### Explicitly rejected

- **Loosening verification thresholds.** Controls show them correctly calibrated (0.990 vs 0.013).
- **Instructing the model to write atomic claims.** Measured: never helped, coincided with Gemini's
  worst run.
- **Raising `top_k` blindly**, or assuming a larger context window helps — the local failure is fidelity,
  not context.
- **Recursive planning / agent loops.** Nothing observed justifies the cost or the unbounded behaviour.
- **A planner as the first move.** It would not have fixed the reported failure.

---

## 20. Proposed sequence

| phase | objective | ships alone? | success measure |
|---|---|---|---|
| **A** | Honest abstention + provider disclosure (`20_synthesis.jsx`, `summaries_response.py`) | yes | no message asserts a cause the data does not establish |
| **B** | Persist three gate confidences (`schema_summaries.py` + response) | yes | a failed synthesis is diagnosable from stored data alone |
| **C** | Adaptive top-k + reference exclusion for query scope (`pipeline.py`, `20_synthesis.jsx`) | yes | evidence-per-facet up; verified yield **measured, not assumed** |
| **D** | Evidence coverage model | yes | partial answers replace global failure |
| **E** | Answer contract + completeness check | yes | no requested dimension silently dropped |
| **F** | Per-facet retrieval | after C/D | facet coverage up at bounded cost |
| **G** | Post-hoc claim decomposition experiment | after B | verified yield change, per provider |

Phases A–C are independently valuable **whether or not a planner is ever built**.

---

## 21. Open questions

1. **Can any locally-runnable model produce faithful claims here?** The most consequential open
   question. Test a larger local model on the same fixture before investing in local-facing planner work.
2. **Is Gemini's variance (5/6, 1/4, 1/8) reducible** by temperature/seed control, or intrinsic?
   Determines whether planner changes can be evaluated at n=1.
3. **Does post-hoc claim splitting raise verified yield?** Testable with the harness built here.
4. **What does Vasiliki actually want the answer to look like?** The output contract should be derived
   from a real desired artefact, not inferred.
5. **Is the retrieval gate (cosine ≥ 0.70) appropriate for aggregated statements?** They are about
   several chunks by construction.

---

## Method note

Nine runs against the 219-paper `validation-summarize` library: four local 2×2 cells (Cliff's design;
my original three arms confounded claim shape with retrieval quality), three Gemini replicates of the
control, one Gemini reference-excluded, one Gemini atomic. 58 citations scored. Local generation is
temperature 0 / seed 42; Gemini is unseeded, hence the replicates. Production code was not modified —
the atomic arms monkeypatched `_prompt` in the experiment process only.

**One real bug was found by running this**, not by reading: `salvage_complete_objects` (inc 575)
returned syntactically-complete objects, but only the managed-local path constrains output with a
grammar, so a cloud provider can emit a well-formed object whose citation has no `quote`. Converting it
raised `KeyError` *inside the recovery path*. Fixed in `b4bcff2`.
