# Research report — standalone CLI experimental synthesis pipeline (scoping only, REV 2)

> **See also (2026-09-07, post-baseline):** `2026-09-07_ask-run-0.5-control-plane-pivot.md` codifies a
> control-plane pivot — evidence-conditioned context selection (real envelopes, no counterfactual
> gate/discard) and decomposition self-audit — informed by the first end-to-end baseline run. Read it
> for the current intent of Stages 1 and 5.

**Status:** architectural scoping only. No production code, no CLI, no migration built by this pass. This
revision incorporates the steering decisions of 2026-09-07 (Qwen-only intermediate work; cloud terminal-only;
retrieval-anchor ≠ evidence-anchor; deterministic coverage + one gap-recovery pass in pass 1; Stage 3
disabled-but-logged; first-run freeze; model-vs-pipeline failure separation).

Legend for every infra mapping: **CONFIRMED** (exists, read it) · **SAFE-REUSE** (call as-is) · **ADAPTER**
(thin experimental glue) · **ASSUMPTION** (unverified) · **BLOCKED** (data/code unavailable) · **DEFER**.

## 1. Executive summary

The proposed staged, paper-first, corpus-grounded pipeline is **mostly buildable from existing read/inference
infrastructure**, and the revised design tests a sharper, economically-realistic hypothesis:

> Can Callosum decompose scholarly synthesis into small, grounded, inspectable natural-language tasks that a
> **small managed *local* model (Qwen)** can coordinate — with the corpus (embeddings, auto-axes, the
> deterministic verifier) supplying all scientific knowledge — such that an **optional cloud model is needed
> only for terminal prose**, not for any intermediate scholarly decision?

Four load-bearing facts shape the first experiment:

1. **Paper-first discovery is real and cheap.** The target library already holds **227 paper-level
   embeddings** (`embed_papers`, title+abstract+venue+year+author) and **10 axes / 594 axis memberships**.
   Stage 2 (paper nomination by paper-vector kNN + axis neighborhood) is SAFE-REUSE + thin ADAPTER.
2. **Stage 3 (citation-graph rescue) is BLOCKED by data.** Only **5 of 217 papers** have extracted
   `reference_instances`. It is **specified but disabled-and-logged** in pass 1 (never silently replaced);
   bulk reference extraction is a separate, later, egress-bearing, explicitly-approved task.
3. **The verifier is a hard, narrow contract, and it fixes the anchor distinction.**
   `LocalCitationVerifier.verify_many` needs each proposition to cite a specific `chunk_id` **and an exact
   verbatim quote of that chunk**. Context growth therefore separates the **retrieval anchor** (why we started
   reading here) from the **evidence anchor** (the specific inspected chunk whose verbatim substring supports
   the proposition — possibly a *neighbor*). Surrounding chunks stay interpretive context and are **never**
   concatenated into "one quote".
4. **All intermediate model-mediated work is Qwen-only.** A failed Qwen intermediate task is *experimental
   evidence*, preserved and failed-closed (or handled by a **pre-frozen** deterministic fallback), never
   masked by a cloud model. Cloud (Gemini) enters **only** at terminal synthesis, consuming the **same sealed
   verified ledger** as a parallel Qwen terminal synthesis. This keeps cloud cost out of the control plane:
   high-volume intermediate interpretation is local; cloud pays only for optional final prose.

The experiment's **primary value is the stage-by-stage failure trace** that separates *model failure* from
*pipeline failure*. The MVE is the full 12-stage pipeline (Stage 3 disabled), Qwen for every intermediate
stage, **both** Qwen and Gemini terminal syntheses from one sealed ledger, no tuning, one run.

**Hard operational prerequisite (new):** because every intermediate stage is Qwen, the run **requires a
provisioned managed Local AI** (`CALLOSUM_APP_DATA_DIR` + an installed Qwen runtime, reached in a dev/CLI
process via `tools/run_local_ai.py` / `run_dev.py --local-ai`, inc 569). If Qwen cannot be provisioned in the
dev environment, the experiment is **blocked** and that is reported — it is **not** worked around with a cloud
provider.

## 2. Current reusable infrastructure map (exact paths)

| Capability | Where | Status |
|---|---|---|
| Paper-level embedding (title+abstract+venue+year+author) | `embeddings/pipeline.py::embed_papers` / `paper_embedding_text` / `PAPER_TEXT_VERSION="paper-metadata-v1"`; `target_type="paper"` | **CONFIRMED** (227 rows) |
| Chunk embedding + vector search over a candidate id set | `embeddings/pipeline.py::embed_chunks`, `current_chunk_embedding_ids`; `embeddings/vector_store.py::VectorStore.search(conn, vector, top_k, candidate_embedding_ids)` | **CONFIRMED / SAFE-REUSE** (24,112 chunk embeddings) |
| Axes + cluster nodes + membership | `persistence/schema.py` `axes`/`cluster_nodes`/`cluster_node_papers`; `clustering/axis_scoring.py::_embed_axis` | **CONFIRMED** (10 axes / 594 memberships) |
| Resolve an external work identity → a library paper | `persistence/repository.py::find_existing_paper_by_identity` | **CONFIRMED / SAFE-REUSE** (Stage 3 later) |
| Citation edges + citation context + section | `persistence/schema_reference_integrity.py` `reference_instances`(`citing_paper_id`,`reference_entity_id`,`context_json`,`raw_text`,`source_ordinal`)→`reference_entities`(doi/openalex/title) | **CONFIRMED schema; BLOCKED data** (5/217) |
| H1a evidence hygiene (chunk_type/evidence_role, currentness-gated) | `persistence/chunk_structure_repo.py::current_structure_roles`; `pdf_processing/chunk_structure.py` | **CONFIRMED / SAFE-REUSE** (23,875/23,875 current) |
| Faceted per-facet retrieval + hygiene/budget (reference pattern) | `summarization/faceted_pipeline.py` (`_load_article_pool`,`_faceted_retrieval`,`_apply_hygiene_and_budget`) | **CONFIRMED / read as reference** |
| Section metadata per chunk | `chunks.section` (heuristic) + `chunks.grobid_section_id`→`paper_sections`; `citations/section_scope.py::candidate_section_family` | **CONFIRMED** |
| Chunk adjacency for bounded context growth | `chunks` `char_start`/`char_end`/`page_start`/`attachment_id`/`section` (order within one attachment) | **CONFIRMED / ADAPTER** (a query, not an API today) |
| Faithful source structure (H1b) | `source_pages`/`source_components`/`source_representations` (inc 578/579) | **CONFIRMED but DEFER** (non-load-bearing; assembled `evidence_form` barred from being quoted) |
| Verifier (retrieval+quote+NLI support+contradiction, batched) | `summarization/verification.py::LocalCitationVerifier.verify_many`, `VerificationConfig`(0.70/1.0/0.55/0.55), `generators.CandidateCitation{chunk_id,quote}`, `SourceChunk` | **CONFIRMED / SAFE-REUSE (unchanged)** |
| Provider seam + config resolution + tolerant JSON parse | `llm/providers.py::complete(config, prompt)`, `resolve_llm_config()`; `summarization/query_planner.py::_extract_json_object` | **CONFIRMED / SAFE-REUSE** |
| Managed Local AI (Qwen) for a dev/CLI process | `tools/run_local_ai.py` + `run_dev.py --local-ai` (needs `CALLOSUM_APP_DATA_DIR`); 4096-token output cap (inc 575) | **CONFIRMED / operational PREREQUISITE** |

## 3. Revised pass-1 dataflow

```
00 frozen question                                   [deterministic input]
01 QWEN interpretation → subquestions + obligations  [Qwen, tolerant-JSON, small tasks]
02 paper-first discovery                             [SAFE-REUSE: paper-vec kNN ∪ axis-neighborhood]
03 graph rescue                                      [DISABLED + LOGGED — insufficient corpus refs]
04 within-paper chunk retrieval                      [SAFE-REUSE: candidate-set vector search + H1a hygiene]
05 QWEN-controlled bounded context growth            [Qwen gates WHETHER/direction; det. code bounds HOW-FAR]
06 QWEN source-local proposition extraction          [retrieval_anchor ≠ evidence_anchor; verbatim quote]
07 unchanged verification                            [SAFE-REUSE: verify_many]
08 verified evidence ledger                          [deterministic]
09 deterministic coverage audit                      [deterministic: answered/partial/unresolved/unanswered]
10 ONE bounded gap-directed recovery pass            [Qwen only where language interpretation is needed]
11 FINAL SEALED VERIFIED LEDGER                      [deterministic seal + hash]
        |
        +----------------------------+
        v                            v
12A QWEN terminal synthesis     12B GEMINI terminal synthesis   [same sealed ledger; no upstream rerun]
+ full JSONL trace + raw Qwen state per intermediate call
```
**No cloud model participates before Stage 12B.**

## 4. Stage-by-stage mapping (concept → Callosum)

- **S1 Interpretation (Qwen)** — reuse the *pattern* of `query_planner.plan_query` (prompt → tolerant
  `_extract_json_object` → strict dataclass validation → **fail-closed** to a pre-frozen deterministic
  fallback), not its facet schema. New ADAPTER: an `obligations` schema (§12). Prefer **several small Qwen
  calls** (e.g. "list the distinct sub-questions"; then per sub-question "list the requested fields") over one
  large decomposition, to keep each task low-entropy (§8). Log `01_decomposition.json` + raw Qwen state.
- **S2 Paper discovery (deterministic + embeddings/axes)** — SAFE-REUSE `embed_papers` vectors +
  `VectorStore.search` over `{paper embeddings}` per subquestion; PLUS axis neighborhood: embed subquestion,
  cosine vs each of the 10 axis vectors (`_embed_axis`), take member papers (`cluster_node_papers`) of the top
  axes. ADAPTER `nominate_papers(subq)` unions both with a **preserved reason** per paper. No model here; axes
  *nominate*, never manufacture synonyms.
- **S3 Graph rescue** — **specified, DISABLED, LOGGED.** Trace records `status:
  disabled_insufficient_corpus_data`, `reason: citation convergence cannot be estimated reliably`, and the
  corpus coverage stat (papers-with-references / total). Not silently replaced. No bulk extraction here.
- **S4 Within-paper retrieval (deterministic + embeddings)** — mirror `_faceted_retrieval` but restrict
  candidate embedding ids to chunks whose `paper_id ∈ nominated papers`; apply `current_structure_roles`
  hygiene + per-paper cap. Retain {subquestion, paper, nomination reason, retrieval score, section,
  chunk_type}. Original subquestion always retained; a corpus-bridge term (§9) may augment, never replace.
- **S5 Context growth (Qwen gate + deterministic bounds)** — see §11. Distinguishes retrieval anchor from
  evidence anchor.
- **S6 Proposition extraction (Qwen)** — see §12. Emits `evidence_anchor_chunk_id` + a **verbatim** quote of
  that chunk; atomic, source-local, no cross-paper synthesis.
- **S7 Verification (unchanged)** — see §13.
- **S8 Ledger** — deterministic JSON keyed by subquestion→obligation, full provenance incl. both anchors.
- **S9 Coverage audit (deterministic)** — see §14; runs in pass 1.
- **S10 Gap recovery (one bounded pass)** — see §14; runs in pass 1.
- **S11 Seal** — deterministic: freeze the verified ledger + a content hash; nothing downstream may mutate it.
- **S12A/S12B Terminal synthesis** — see §6/§15; Qwen and Gemini each over the identical sealed ledger.

## 5. Provider / model responsibility boundary (the central revision)

- **Deterministic Callosum code:** orchestration, budgets, structural guards, H1a hygiene, provenance,
  quote-substring validation, candidate-set construction, coverage rules, seal, trace writing.
- **Embeddings / RAG:** semantic retrieval + ranking (paper + chunk).
- **Auto-axes:** corpus-native paper nomination / recall support.
- **LocalCitationVerifier / NLI:** evidence support + contradiction adjudication.
- **Qwen (managed local):** *every* bounded natural-language interpretation/navigation task in Stages 1, 5, 6,
  and 10 (and only there) — decomposition, context-growth gating, proposition extraction, corpus-bridge
  interpretation, and any recovery-query reformulation. **Never an epistemic authority.**
- **Cloud (Gemini):** **terminal synthesis only** (Stage 12B), after the ledger is sealed.

**Prohibited in pass 1:** any cloud provider at Stages 1–10; any `--interpret-model gemini` / `--extract-model
gemini` style flag; any opportunistic cloud fallback when Qwen underperforms. A failing Qwen task **fails
closed** (or uses a fallback frozen *before* the run) and is preserved as evidence.

## 6. Terminal synthesis fork (sealed ledger → dual output)

Stage 11 produces a **sealed verified evidence ledger** (verified propositions + coverage + explicit gaps +
provenance + a hash). Stage 12 forks:
- **12A** `complete(qwen_config, prompt)` → `14a_final_answer.qwen.md`
- **12B** `complete(gemini_config, prompt)` → `14b_final_answer.gemini.md`

Both receive **exactly the same substantive ledger** and the same instruction: *organize only what is verified,
state the gaps, never fill unsupported fields*. Neither terminal call may rerun retrieval, inspect new chunks,
repair decomposition, reinterpret rejected evidence, rescue papers, add propositions, or touch coverage/gaps —
enforced structurally (the terminal prompt contains the ledger only; no engine/DB handle is passed to the
synthesis step). The comparison isolates **terminal generator quality** from **pipeline quality**.

## 7. Deterministic (no-model) boundaries

Paper-vec kNN, axis cosine, candidate-set vector search, H1a hygiene ordering, chunk-adjacency growth *distance*
+ caps, verbatim-quote precondition, the entire verifier, ledger assembly + seal, obligation→proposition
mapping (id/string match), the **default coverage rule**, initial vs recovery bookkeeping, and all trace
writing. The model decides *whether/what to read/assert*; deterministic code decides *how far / whether it
verifies / whether it counts as covered*.

## 8. Qwen task contracts (small, low-entropy, decompose-not-broaden)

Every contract: bounded output (fits 4096), tolerant-JSON parse, strict validation, **fail-closed** or a
pre-frozen deterministic fallback; the model **interprets/organizes**, never supplies domain facts. If a task
proves unreliable, the response is to **decompose it further**, never to broaden the prompt or grant more
epistemic freedom.

- **Interpret** (possibly split into two small calls): out `[{subquestion_id, text, obligations:[{field_id,
  kind∈{brain_region, brain_behavior_relation, behavior, brain_attitude_relation, attitude_construct,
  personality_trait, instrument, population_culture, measurement_method, intervention, comparator, outcome,
  effectiveness}, note}]}]`.
- **Context gate** (per packet): out `{proposition_bearing:bool, answers_obligation:bool,
  grow∈{none,before,after,both}, dead_end:bool}` — e.g. "Is this a list of abbreviations rather than a
  scientific proposition?", "The text says 'these associations' — is preceding context needed to resolve the
  referent?".
- **Extract proposition**: "Using ONLY this supplied source text, identify subject/relation/object/direction/
  population/measure/qualifier, the obligation ids covered, the **specific inspected chunk** that contains the
  support, and its **exact supporting quotation**." Out per proposition: `{subject, relation, object,
  direction, population, measure, qualifier, obligation_ids[], evidence_anchor_chunk_id, quote:"<verbatim
  substring of that chunk>"}`.
- **Coverage interpretation (recovery only, optional)**: kept deterministic by default (§14); a Qwen call is
  used only to phrase a **recovery query** for a specific missing obligation ("The user requested a trait and
  the instrument used to measure it; produce a short retrieval phrase for the missing instrument"), never to
  decide truth.

Inappropriate (never asked): "what does the literature say about X", "suggest synonyms for X", "what concepts
might the user have forgotten", "fill in missing scientific information".

## 9. Corpus primacy / query-local bridges

Any alternate terminology used for retrieval must derive from **corpus text** (title, abstract, axis
neighborhood, source passage; later, citation context once Stage 3 is enabled). Qwen may **interpret**
corpus-authored language (e.g. an abstract that frames the phenomenon as "negative attitudes toward facial
disfigurement") into a retrieval phrase, but must not free-associate synonyms. Bridges are **query-local,
retrieval-only, provenance-bearing**, never persisted as ontology. In pass 1 the primary bridge source is the
nominated papers' own abstracts (Stage 3 citation-context bridges are disabled with Stage 3).

## 10. Paper discovery / axes design

Per subquestion: embed the subquestion text; (a) `VectorStore.search` over the 227 paper-embedding ids → top-K
papers by cosine; (b) cosine(subq, each of 10 axis vectors) → member papers of the top axes (with membership
confidence). Union, dedupe, cap (~15–25 papers/subq), **store the reason** (`semantic_paper`, `axis:<label>`).
Log papers each source contributes and near-miss papers (for the postmortem's "never nominated" diagnosis).

## 11. Context-growth design (retrieval anchor ≠ evidence anchor)

A retrieved chunk is the **retrieval anchor** (`retrieval_anchor_chunk_id`) — it records *why* reading started
here and stays in provenance. Deterministic code then assembles a bounded **context packet** of neighboring
chunks in the same attachment (order by `char_start`): **same paper; prefer same `section`; ≤2 growth
iterations; ≤~1,500 context tokens; never cross body↔references (`evidence_role`/`section` guard); dedupe
overlapping packets.** A Qwen **context gate** decides *whether* to grow and *which direction* (or dead-end);
deterministic code decides *how far*. Example: retrieval anchor chunk 100 ("…implicates specific brain
areas."); packet {99,100,101,102}; proposition A's **evidence anchor** = chunk 101 (the amygdala sentence),
quote = a verbatim substring of chunk 101. Each proposition names its own `evidence_anchor_chunk_id` (possibly
≠ the retrieval anchor). Surrounding chunks remain interpretive context and are **never** merged into the
quote. **Do NOT use H1b `source_components` reconstruction** — chunk adjacency is the safe, already-faithful
unit; H1b's assembled `evidence_form` is explicitly barred from being quoted (inc 578).

## 12. Proposition representation

```
{ subject, relation, object, direction∈{+,-,none,mixed}, population, measure, qualifier,
  obligation_ids[], subquestion_id,
  retrieval_anchor_chunk_id,        # why we read here (provenance)
  evidence_anchor_chunk_id,         # the chunk whose verbatim substring supports this proposition
  quote,                            # verbatim substring of evidence_anchor chunk
  paper_id,
  provenance{ nomination_reason, retrieval_score, context_read:[chunk_ids...], corpus_bridge?, origin∈{initial,recovery} },
  verification{ status, retrieval, quote, support, contradiction } }
```
Atomic, source-local; `quote` (from the **evidence** anchor) is the object that reaches the verifier.

## 13. Verification integration (exact contract, unchanged thresholds)

`LocalCitationVerifier(model, vector_store, config=VerificationConfig()).verify_many(conn, items, source_chunks)`
where `items=[(proposition_text, CandidateCitation(chunk_id=evidence_anchor_chunk_id, quote=verbatim_quote))]`
and `source_chunks=[SourceChunk(...evidence-anchor chunks...)]`. Marshaller precondition: `quote` is a
whitespace-normalized substring of the **evidence-anchor** chunk text
(`pdf_processing/extraction.canonical_text_contains`) — else the proposition is dropped **pre-verify** with a
logged reason (`quote_not_verbatim`). Returns `VerificationResult{status, retrieval_confidence,
quote_confidence, support_confidence, contradiction_confidence, page/bbox, coordinate_precision}`. Batch via
`verify_many` (never loop per item). No threshold change.

## 14. Coverage audit (pass 1, deterministic) + one gap-recovery pass (pass 1)

**Coverage (deterministic, no Qwen by default):** for every subquestion/obligation, from the ledger:
- **answered** — ≥1 *verified* proposition maps to the obligation.
- **unresolved** — relevant candidate evidence/propositions existed but none verified.
- **unanswered** — no verified proposition and no surviving mapped evidence.
- **partial** — a multi-field obligation has only some fields covered.
Written as `12_coverage_audit.json` (obligation → state). This state is an explicit input to recovery + both
terminal syntheses.

**Gap recovery — exactly ONE bounded pass:** for each *meaningful* uncovered obligation:
(1) start from the original approved subquestion; (2) retain the exact missing obligation/field; (3) search the
already-nominated candidate paper set first (rerun S4 scoped to the obligation, optionally with a Qwen-phrased
recovery query, §8); (4) if still empty, permit **one** new paper-nomination pass scoped to the missing
obligation (S2); (5) rerun within-paper retrieval (S4); (6) rerun bounded context growth (S5); (7) rerun
proposition extraction (S6); (8) rerun unchanged verification (S7); (9) update ledger + coverage; (10) STOP.
**No recursion, no autonomous loop, no post-hoc tuning.** The trace tags all recovery evidence
`origin: recovery` so it is distinguishable from initial evidence.

## 15. Final synthesis integration

Two `complete()` calls over the sealed ledger (§6): 12A Qwen, 12B Gemini, identical ledger + instruction, no
raw chunks, no engine/DB handle. Persist both outputs separately.

## 16. Logging / trace artifact schema

Run dir `experiments/ask_cli/runs/<ts>/`:
`00_question.json · 01_decomposition.json · 02_direct_papers.json · 03_axis_nominations.json ·
04_graph_rescue.json (status=disabled_insufficient_corpus_data + corpus stats) · 05_candidate_papers.json ·
06_chunk_retrieval.jsonl · 07_context_growth.jsonl · 08_evidence_packets.jsonl · 09_propositions.jsonl ·
10_verification.jsonl · 11_verified_ledger.json (sealed + hash) · 12_coverage_audit.json ·
13_gap_recovery.json · 14a_final_answer.qwen.md · 14b_final_answer.gemini.md · 15_run_manifest.json`.
Every prune/promote carries `{decision, reason_code, inputs, kept:bool}` (codes incl. `paper_kNN`,
`axis:<label>`, `graph_rescue_disabled_no_refs`, `chunk_nonproposition`, `grew_context_after`,
`context_budget_exhausted→uncertain`, `quote_not_verbatim→dropped`, `support_failed`, `obligation_unanswered`,
`recovery_added_evidence`, `recovery_no_new_evidence`). **Every Qwen intermediate call persists raw state:**
`{stage, input_text, raw_output, parse_ok, validation_ok, failure_reason?, deterministic_fallback_used?,
downstream_consequence}` — so the postmortem can attribute a loss to Qwen specifically. Propositions carry both
anchors. Manifest (`15`): question hash, DB-copy path + row counts, Qwen + Gemini model/version ids, verifier
thresholds, all caps, git SHA, embedding model id, ledger hash, `origin` counts.

## 17. CLI layout and invocation

`python -m experiments.ask_cli --db <copy.sqlite> --out runs/<ts> [--terminal both|qwen|gemini]`. **No
intermediate-provider flags.** Intermediate stages are Qwen (required); the only provider choice is the
terminal fork, defaulting to **both**. Lives **outside `app/`** (`experiments/ask_cli/`, the `tools/`
precedent) so it never enters production import paths or the 600-line cap. Runs against a **copy** of
`library.sqlite`. Reuses production read/inference by importing `app.backend.*` (allowed for a tools-like
script). Requires a provisioned Qwen (`run_dev.py --local-ai` / `CALLOSUM_APP_DATA_DIR`); if unavailable →
report blocked, do not substitute cloud.

## 18. Runtime / caching + the economic constraint

The design deliberately keeps cloud cost **out of the control plane**: high-volume intermediate interpretation
(decompose, gate, extract, recover) is local Qwen; corpus search/evidence/verification is local/deterministic;
cloud pays only for optional terminal prose. Bottlenecks: (a) many small Qwen calls on CPU — mitigate by
minimizing call count (batch a subquestion's packet gates where the sequential context-growth logic allows;
see §19) and keeping each output tiny (≤4096); (b) NLI verification — batch via `verify_many`; (c) context
growth iterations — hard caps. Within-run caching: subquestion embeddings, paper-vector search results, axis
vectors; chunk/paper embeddings already persisted (no re-embed).

## 19. Failure modes & adversarial critique

- **Qwen intermediate weakness is now first-class experimental evidence, not a bug to paper over.** The three
  hardest Qwen tasks are proposition extraction under a verbatim-quote constraint (a 1.5B model may paraphrase
  → `quote_not_verbatim` drop, or lose qualifiers), context-gate judgment, and clean decomposition. The design
  response is **decompose further** (§8) + fail-closed + preserve raw state — never a cloud fallback. If Qwen
  is too weak, that is the finding.
- **Stage 3 inert on this corpus** (5/217) — disabled+logged, biggest deferred risk.
- **Paper-first can lose an isolated finding** in a topically-peripheral paper (its paper vector is far from
  the subquestion though one chunk answers it) — the classic recall loss the postmortem must catch; mitigate
  with generous S2 caps + near-miss logging, accept as measured.
- **Axes are coarse** (10) — likely redundant with paper-kNN; keep as secondary recall aid, measure marginal
  recall.
- **Retrieval↔evidence anchor drift** could let extraction "wander" to a neighbor that is off-topic; bounded by
  the same-paper/same-section/token/iteration caps + the verifier (an off-topic evidence anchor fails
  retrieval/support).
- **Gap recovery combinatorial risk** — bounded to exactly one pass, one optional new nomination per missing
  obligation, no recursion.
- **Context-growth batching vs sequential logic** — growth is inherently sequential (a gate decision depends on
  the last read), so Qwen gate calls cannot all be batched; keep them few via the deterministic pre-filter
  (H1a `structural`/`unknown` + length already prunes abbreviation lists before Qwen sees them).
- **Redundancy** — `faceted_pipeline` already does S4+S7+verified assembly; the genuinely new ideas under test
  are **Qwen-coordinated S1 (obligations), S2 (paper-first), S5 (anchor-split context growth), S9/S10
  (coverage-driven recovery)**, and the **Qwen-only intermediate + dual terminal** economic structure. Keep the
  experiment focused there.

## 20. Postmortem: separating model failure from pipeline failure

The trace must let a known target (amygdala, Dictator Game, IAT, empathic concern/IRI, just-world/scale,
warmth/competence, Hadza cross-cultural, intervention evidence) be classified by the transition where it
disappeared: **paper never nominated** (discovery) · **paper nominated, chunk missed** (within-paper retrieval)
· **chunk found, context didn't expand** (context growth) · **packet good, Qwen extracted a bad proposition**
(proposition-interpretation — Qwen) · **faithful proposition rejected** (verifier/evidence mismatch) ·
**verified but obligation mapping wrong** (coverage) · **correctly-missing but recovery failed** (gap-recovery)
· **in sealed ledger but absent from final** (terminal synthesis — and, since 12A/12B share the ledger, the
Qwen-vs-Gemini terminal diff isolates terminal-generator quality). For every Qwen-mediated transition, the
persisted raw state (§16) determines whether **Qwen itself** caused the loss vs. an upstream deterministic/RAG
stage.

## 21. Minimum viable experiment (pass 1)

The **full revised 12-stage pipeline** (§3) with Stage 3 disabled-and-logged, **Qwen for every intermediate
stage (1,5,6,10)**, deterministic S2/S4/S7/S8/S9/S11, **both** Qwen and Gemini terminal syntheses over one
sealed ledger, full trace + raw Qwen state, on a DB copy, the single frozen benchmark question. **First-run
freeze:** freeze question, prompts/contracts, caps, nomination logic, growth limits, Qwen contracts, verifier
thresholds, gap-recovery policy; run **once**; retry only genuine technical failures per a predefined policy;
**no tuning** because the answer is disappointing; **seal all stage artifacts before** the human known-answer
postmortem.

## 22. Do NOT build (pass 1)

Live Stage 3 graph rescue; bulk reference extraction (separate approved egress task); any cloud provider at
Stages 1–10; any intermediate-provider flag or cloud fallback; recursive/multi-round recovery or an autonomous
agent loop; any H1b/H1c reconstruction as evidence; a persisted corpus-bridge ontology; a production
framework/generalization; any UI; any schema migration; any verifier/threshold change; the postmortem
evaluator (supplied separately); tuning after the first run.

## 23. Proposed sequence for a second, separately-approved pass

(1) Build + run the pass-1 MVE (§21) + trace. (2) Run the supplied evaluator → the stage-by-stage failure
matrix; separate Qwen-model failures from pipeline failures. (3) Fix the single largest measured loss only. (4)
If S1/S5/S6 Qwen tasks are the bottleneck: decompose those tasks further (never add cloud). (5) Separately
approve + run bulk reference extraction (egress), then enable Stage 3 as a drop-in. (6) Iterate the terminal
Qwen-vs-Gemini comparison as pipeline quality improves. Each step gated on the prior trace showing it is the
actual bottleneck.

---

*Feasibility figures are from a read-only probe of `C:\Users\cliff\callosum-data\library.sqlite`
(mode=ro): 217 live papers, 184 with abstracts, 227 paper embeddings, 24,112 chunk embeddings, 10 axes / 594
axis memberships, 347 reference_instances across only 5 citing papers. No data was modified.*
