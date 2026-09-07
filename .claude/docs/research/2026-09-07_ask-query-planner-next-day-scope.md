# Synthesize → Ask: bounded query-planner + evidence-hygiene substrate — next-day scoping (Rev 2)

- **Date:** 2026-09-07 · **Revision 2** (incorporates Cliff + Lucien steering after Rev 1 review).
- **Type:** Targeted implementation scoping (NOT implementation). Return to Cliff + Lucien before coding.
- **Deadline:** a real user demos Ask at lab meeting tomorrow on a broad, oracle-shaped question.
- **Goal:** smallest change that **safely and materially** improves broad multifaceted synthesis, combining **better query planning** with the **already-built evidence/provenance substrate (H1a/H1b/H1b.1)**, while keeping the narrow fast path and the verifier's authority untouched.
- **Product principle:** answer oracle-shaped questions with **evidence-shaped behavior**. Help the user see *what their literature says*; never become an AI paper writer.

**What Rev 1 got right (kept):** the diagnosis (single smeared retrieval vector, `top_k=8`, no diversity on the query path) and the bounded query-planner architecture — deterministic narrow/broad pre-gate; one provider-agnostic structured planner call; 3–6 facets; one retrieval query per facet (v1); per-facet retrieval; dedup; per-paper/per-facet/global budgets; narrow fallback; unchanged verifier + thresholds; one batched `verify_many`; explicit per-facet coverage; no schema migration; minimal UI.

**What Rev 2 changes:** Rev 1's boundary "tomorrow uses only legacy page-sized chunks, no H1 substrate" is **lifted**. Tomorrow also wires in the **conservative, already-built** H1a/H1b substrate (Category A below) as an evidence-hygiene + provenance seam — separated cleanly from proposition **reconstruction** (Category B), which stays guarded behind H1c-A3.

---

## 0. Substrate reality check (grounded — read before the rest)

Three findings from inspecting the real classifier + tables gate what can ship:

1. **The H1a classification is shipped "to be observed, not obeyed."** `pdf_processing/chunk_structure.py`'s own docstring: the evidence-hygiene study found **NO reason code clears the ≥95% held-out precision gate**; three adjudicated false positives would have deleted real scientific evidence. **Consequence:** hard *exclusion* by `chunk_structure` risks deleting evidence. The aligned use is **deprioritization (down-ranking), not deletion** — a demoted chunk is still retrievable if nothing better exists, so its failure mode can neither manufacture nor delete scientific evidence. This clears the steering's "failure mode cannot manufacture evidence" bar; hard exclusion does not.
2. **The substrate is backfill-only — but empirically real and usable at scale.** `chunk_structure` (H1a) and `source_pages`/`source_components`/`source_representations` (H1b/H1b.1) are written **only** by `tools/backfill_chunk_structure.py` / `tools/backfill_source_components.py` — no ingest or API path writes them, and **nothing on the retrieval path reads them today**. **Measured on a real 229-paper copy of Cliff's library** (the H1c study corpus): `chunk_structure` is **fully populated (23,782 of 23,875 chunks classified)**, `source_components` holds **1,089,546** rows, `source_representations` **114**. So the backfill produces usable data at scale — the *code* substrate is proven, and the only open question is whether Cliff's **live desktop** DB has been backfilled yet. **Consequence:** the hygiene/provenance seam **must degrade to a safe no-op when the metadata is absent or stale** (LEFT JOIN → NULL → treat as `unknown`/full-priority), and an **overnight H1a backfill against Cliff's live library is the enabling prerequisite** (cache-only, no network, per-paper-committed, resumable, idempotent). Note H1b coverage is **partial even where backfilled** (114 of 229 papers here) — a further reason component-provenance is deferred. The retrieval fix alone already materially improves the broad case; hygiene is an additive layer that activates once data exists.
3. **No safe `chunk` → `source_component` bridge exists.** The H1b tables carry **no `chunk_id`**; they key on `attachment_id`+`page`+`component_path`+`native/sorted_order`. Per CLAUDE.md H1b(a), `chunks.bbox_json["block"]` is a *post-sort* ordinal (with gaps from dropped image blocks) while `quote_matching` stores the *native* number — they disagree on **83%** of pages. **Consequence:** component-level provenance hydration (SourceLocator on a citation) requires a validated chunk→component locator that **does not exist**; inventing it tonight is forbidden by steering #6 → **DEFER**. The existing citation provenance (attachment_id + page + verified verbatim quote + `coordinate_precision` exact/region/null) is already the durable, honest chain.

## 1. Current Ask architecture (traced — exact files/functions)

(Unchanged from Rev 1; the load-bearing facts:)

| # | Stage | File · function | Behavior today |
|---|---|---|---|
| 1 | UI entry | `app/frontend/js/20_synthesis.jsx` · `start()` L164 | `launch({scope_type:"query", query, top_k:8})` — **top_k hard-coded 8**. |
| 2 | Endpoint | `api/routers/summaries.py` · `summarize_start`→`_run_summarize_job` | `POST /summarize` background job; `SummarizeRequest{scope_type,query,top_k,sections}`. |
| 3-6 | Retrieval | `summarization/pipeline.py` · `_source_chunks_for_scope`→`_rank_chunks_for_query` L340 | Query scope: all live article chunks → drop repeated boilerplate → **one** query embed → **one** `vector_store.search(top_k=8)`. `preserve_paper_coverage=False` for query → **no per-paper/facet diversity**. |
| 7 | Thresholds | `summarization/verification.py` · `VerificationConfig` | retrieval ≥0.7, quote =1.0, support ≥0.55, contradiction ≥0.55. **Authoritative — untouched.** |
| 9 | Existing hygiene | `pipeline.py` uses `exclude_repeated_boilerplate_chunks` + `is_front_matter_chunk` | Repeated running heads/footers **already excluded** (separate deterministic detector — safe, load-bearing today). |
| 10-12 | Generation | `integrations/gemini/generator.py` · `_prompt` L166, `generate` | One prompt: "**4 to 7** objects", 1-3 citations each, verbatim quote ≤80 words, over retrieved chunks. Provider-agnostic `complete(config,prompt)`. |
| 13 | Verify | `verification.py` · `LocalCitationVerifier.verify_many` | **One** batched embed + NLI over every (claim,citation). |
| 14 | Synthesis | (no separate call) | Generation *is* the synthesis; claims produced then verified; unsupported → flagged (kept, not deleted). |
| 16 | Failure | `pipeline.py` L169; `19_synthesis_failures.jsx` | `status="verified"` iff every citation verified else `"flagged"`; all-flagged renders "0 of N claims verified." |

## 2. Exact failure mechanism (unchanged diagnosis, now with the second cause named)

1. **Single smeared retrieval vector (dominant).** A 7-facet question embeds to a centroid near nothing specific → under-retrieves every facet.
2. **top_k=8, no diversity** on the query path → the 8 collapse onto 1–2 papers/facets.
3. **Evidence-pool contamination (Rev 2 adds this).** The tiny budget can be consumed by topic-dense but **non-evidential** material — reference-list entries, publication metadata, keyword lines, table debris — which resemble the query lexically but cannot support a scientific claim. Today only repeated boilerplate is filtered; `reference_entry`/structural material can still fill the 8.
4. **Generation over thin/contaminated evidence → the verifier correctly flags → "0 of 4 verified."** The verifier is doing its job; the fix is upstream (retrieval breadth + evidence hygiene) and downstream (coverage + verified-first presentation).

## 3. Category A (substrate — load-bearing candidate) vs Category B (reconstruction — deferred)

**Category A — already-built substrate/provenance (seriously considered for tomorrow):** `chunk_structure` (`chunk_type`, `evidence_role`, `reason_codes`, `confidence`, `reference_region`, `repeated_boilerplate`, staleness via `raw_sha`+`chunk_version`); `source_pages`/`source_components`/`source_representations` (attachment-keyed page/component geometry, `component_path`, `geometry_state`, completeness/currentness, source checksum, extractor/derivation identity); the existing `exclude_repeated_boilerplate_chunks` detector; attachment-instance provenance. **Failure mode of A used as deprioritization can neither manufacture nor delete evidence.**

**Category B — proposition reconstruction (guarded, NOT tomorrow):** fragment reunion, assembled EvidenceUnits, multi-component proposition reconstruction. Subject to H1c-A3. **The load-bearing rule (CLAUDE.md, inc 578 spec): assembled evidence must never masquerade as one verbatim quotation, and `canonical_text_contains` must never be relaxed to accept an assembled string.** Tomorrow's quote-matching stays over exact stored chunk text. **A is not blocked on B.**

## 4. Explicit non-goals (Rev 2)

- No general agent framework — **one** planner seam.
- **No Category B**: no reconstruction, no assembled EvidenceUnits, no adjacent-chunk merging, no text normalization that could break verbatim quote matching.
- No change to `VerificationConfig` thresholds or the verifier's authority.
- **No hard exclusion by `chunk_structure`** (the H1a study bars it) — deprioritize, don't delete. The only hard exclusion remains the already-shipped repeated-boilerplate detector.
- No `unknown` penalization; no global ban on captions/Results/tables.
- No invented `chunk`→`component` mapping.
- No raised output ceilings; no optimizing for claim count.
- No schema migration; no large frontend project.

## 5. Proposed control flow (Rev 2)

```
question
  → [gate] deterministic narrow/broad pre-gate            (no provider call)
      → narrow → EXISTING summarize_scope (unchanged)
      → maybe-broad → [planner] ONE structured complete() → {scope, facets[3..6]{label, query}}
            → narrow/invalid/failure → FALL BACK to EXISTING path
            → broad → summarize_faceted:
                per-facet retrieval (batch-embed facet queries; per-facet vector search)
                  → EVIDENCE-HYGIENE SEAM (deprioritize by evidence_role; reuse repeated-boilerplate exclusion)
                  → diversity + dedup + per-paper/per-facet/global budgets
                  → build FacetEvidence objects (faithful text + hygiene/provenance metadata + facet)
                  → bounded per-facet generation (target 1-3 claims/facet)   [existing generator]
                  → ONE batched verify_many over ALL claims                  [verifier UNCHANGED]
                  → verified-first assembly + explicit per-facet coverage
                  → persist (scope_ref_json) → render (coverage strip; verified primary)
```

## 6. Evidence-eligibility / hygiene seam (steering #3, #4, #5)

Location: in the new `faceted_pipeline.py`, after per-facet candidate retrieval, before diversity/budget. **LEFT JOIN `chunk_structure` on `chunk_id`, gated on currentness** (`raw_sha` + `chunk_version` match the live chunk; stale/absent → treat as `unknown`). **Policy (deprioritization-first, grounded in the classifier confidences + the H1a study):**

| Signal (source) | Treatment | Tier |
|---|---|---|
| Repeated boilerplate (existing `exclude_repeated_boilerplate_chunks` detector) | **Hard exclude** (already shipped; a ≥3-page verbatim repeat is never unique scientific evidence) | MUST SHIP (reuse) |
| `evidence_role == scientific` (`body_prose`,`abstract_prose`,`caption`) | Full priority (**captions retained**) | MUST SHIP |
| `evidence_role == unknown` | Full priority (**never penalized** — holds real fragmentary statistics) | MUST SHIP |
| `evidence_role == bibliographic` (`chunk_type == reference_entry`) | **Deprioritize** — filled only after scientific/unknown exhausted for the facet | SHIP IF LOW-RISK (needs data) |
| `evidence_role == structural` (`table_cell_debris`,`heading_fragment`,`publication_metadata`,`keyword_line`,`citation_instruction`,`math_or_symbol`) | **Deprioritize** | SHIP IF LOW-RISK (needs data) |
| `chunk_structure` absent/stale | Treat all as `unknown` → seam is a **no-op** (graceful) | MUST SHIP |

**Why deprioritize, not exclude:** the H1a study found no code clears 95% precision. Deprioritization protects the tiny budget (real evidence leads) without ever deleting a chunk (a demoted chunk still surfaces if it is all a facet has). **This is the exact "cannot manufacture certainty" posture the steering asks for.** Hard exclusion via `chunk_structure` is **DEFERRED**.

**Empirical shape (229-paper copy of Cliff's library) — and a critical nuance:** `evidence_role` distributes as **unknown 55.6% (13,220)**, structural 23.8% (5,655), scientific 11.7% (2,779), bibliographic 8.9% (2,128). **`unknown` is the dominant class and holds most real evidence** (the classifier leaves the bulk of body content unclassified; its docstring: `unknown` holds real fragmentary statistics like "β = 0.086, SE = 0.015, z = 5.664, p < 0.00001"). Therefore `scientific` and `unknown` are **peers at full priority — the seam must never promote `scientific` above `unknown`**, or it would bury most of the evidence. The seam's *only* job is to demote the clearly-non-evidential **~33% tail** (bibliographic 8.9% + structural 23.8%: reference entries, table debris, running heads, math/symbol fragments, publication metadata) beneath that full-priority bulk. This is a real, safe budget-protection effect (a third of lexically-matching candidates on a broad query are furniture), not a reordering of genuine evidence.

**Reference correction (steering #4):** the deprioritization signal is `chunk_type == reference_entry` / `evidence_role == bibliographic` (**entry identity**), **not** `chunks.section == "references"` (**region location**). The classifier docstring documents why the section label cannot be load-bearing (10/108 papers have no references-labeled chunk; labeled-references chunks are often real prose). `reference_region` is a supporting, not decisive, signal. When `chunk_structure` is absent, the seam does **not** fall back to the coarse section filter (unreliable; steering warns against it as primary) — it simply no-ops.

## 7. The evidence object handed to generation (steering #7)

New `FacetEvidence` (in `faceted_pipeline.py`) wraps the existing `SourceChunk` and adds:
`facet_label`; and, **when available and current**, `evidence_role`, `chunk_type`, `repeated_boilerplate`, `source_representation_state` (attachment-level; H1b, if backfilled). **The generation `text` remains the exact stored chunk text — no normalization or assembly — so verbatim quote matching (`canonical_text_contains`, quote =1.0) is unaffected.** The extra metadata drives the deterministic **hygiene ranking, coverage, and provenance rendering**; it is **not** injected into the model prompt (the prompt keeps only `chunk_id`/`paper_id`/`page`/`text`, avoiding biasing the model with role labels). Facet attribution is recorded for coverage.

## 8. Per-facet generation volume (steering #8)

4–7 claims × 6 facets = 24–42 candidates → facet-level over-generation and a noisy answer. **Fix: bound the per-facet claim target to 1–3 (fewer when evidence is thin).** Two combinable mechanisms:
- **(preferred) Parameterize the claim target** — add an optional `claim_target=(4,7)` to the generator/`_prompt`; the faceted path passes `(1,3)`; the **narrow path keeps the default (contract unchanged)**. Requires bumping `SUMMARY_PROMPT_VERSION` → `summary-v6` (invalidates the synthesis cache — acceptable). `1–3 ⊂` the managed-local grammar's `7`-claim cap and its 2,048-token output ceiling, so this is **safer** for Local AI than 4–7 (no ceiling change). **SHIP IF LOW-RISK.**
- **(always) Post-hoc cap in assembly** — keep at most 3 verified claims per facet in the rendered synthesis, deterministically (highest support first); the rest become secondary "additional" material (see §9). **MUST SHIP** (bounds the answer even if the prompt change is dropped).

If the prompt parameterization proves risky, retain 4–7 generation and rely on the post-hoc cap — documented limitation: extra provider tokens spent, but the rendered answer stays bounded. **Do not raise ceilings; do not optimize for claim count — optimize for useful verified synthesis.**

## 9. Verified-claim presentation (steering #9)

Keep generate-then-verify (no evidence-first rewrite). For the **broad path only**, presentation changes (persistence keeps everything — transparency, no verifier information deleted):
- **Verified claims → the primary rendered synthesis** (deterministic verified-first ordering). **MUST SHIP.**
- **Flagged/unverified/contradicted claims → NOT shown as established findings**: grouped under an explicit "unverified candidates" affordance (collapsible), retaining their existing status pills + citation diagnostics. **SHIP IF LOW-RISK** (verified-first ordering alone is the MUST-SHIP fallback).
- **Unsupported facet → a coverage/gap statement** (§10), never an established claim and never a library-absence claim.

This prevents a broad result dominated by confident-looking claims the verifier already rejected, while preserving full transparency into verifier behavior.

## 10. Partial-coverage semantics (unchanged intent; honesty rule restated)

Per facet, from verification results: **supported** (≥1 verified claim) · **partial** (some verified, some flagged) · **retrieved_unverified** (evidence retrieved, 0 verified) · **no_evidence_retrieved** (nothing retrieved for the facet). **Honesty rule (hard):** the latter two read as *"no verifying evidence found in your library's retrieved passages for this facet"* — **never** *"your library does not cover this."* Retrieval failure ≠ evidence absence.

## 11. Provenance (H1b) — what ships vs defers (steering #6)

- **Ships tomorrow (already durable, no new mapping):** every citation keeps `attachment_id` + `page` + **verified verbatim quote** + `coordinate_precision` (exact/region/null) — the coordinate-honesty contract. `attachment_id` is retained precisely because identical PDFs can be attached multiple times.
- **SHIP IF LOW-RISK (needs H1a backfill present):** surface each citation's `evidence_role`/`chunk_type` (inspectability — "this quote is body prose / a caption / a reference entry"). Additive response field; no mapping.
- **DEFER (next increment):** component-level provenance (`component_path`/SourceLocator, component coordinates) on citations. **No safe `chunk`→`source_component` bridge exists** (§0.3); a durable locator needs `attachment_id` + source checksum + extraction/derivation identity + page + `component_path` and a **validated** chunk→component resolution. Guardrails to honor when built: surrogate `source_component.id` is not durable provenance (use SourceLocator); require `source_representation` complete/current before trusting component provenance; `geometry_state` is authoritative (don't reconstruct validity from persisted NULL coordinates); valid zero-area geometry is not automatically usable for area-overlap.

## 12. Retrieval-budget, diversity, dedup (unchanged from Rev 1, hygiene inserted)

`PER_FACET_TOP_K=6` candidates/facet (reuse `_rank_chunks_for_query` machinery); **apply the §6 hygiene ordering**; then dedup by `chunk_id` (attribute to best-ranked facet), `PER_PAPER_CAP=3` globally, `GLOBAL_CHUNK_CAP=36`; per-facet caps enforced before the global cap (anti-starvation, round-robin across facets). All deterministic post-retrieval filters — no retrieval redesign. Provenance preserved exactly.

## 13. Bounded planner contract (unchanged from Rev 1)

Heuristic pre-gate → one structured `complete()` → `{scope, facets:[{label,query}]}`; validate every field; `3 ≤ facets ≤ 6`; dedup near-identical queries; one query per facet (v1). Any parse/validation/timeout/egress-off/`<3`-facet outcome → `narrow` → existing path. **Planner failure can only degrade to today's behavior. Planner decisions never make a claim true.**

## 14. Provider-call budget (Rev 2)

| Path | Planner | Generation | Verify (batched) | Embeds |
|---|---:|---:|---:|---:|
| Narrow (unchanged) | 0 | 1 | 1 | 1 query + verify |
| Broad | 1 | F (≤6) | **1** | 1 (F facet queries, batched) + verify |

Worst-case broad = **1 + 6 = 7** provider calls; verifier stays one batched call (LATENCY.md, inc 418). Hygiene/coverage/provenance add **zero** provider calls (local metadata joins). Latency: F sequential generations on flash-lite ≈ 15–40 s, absorbed by the background job + long-poll + progress; **bounded generation concurrency is a sanctioned follow-up** (`ThreadPoolExecutor`, inc-418 pattern) — DEFER. Provider-agnostic throughout (`complete()`).

## 15. Files likely to change (Rev 2)

**New:** `summarization/query_planner.py` (pre-gate + `plan_query` + validation + fallback); `summarization/faceted_pipeline.py` (per-facet retrieval + **hygiene seam** + budgets + `FacetEvidence` + bounded generation + one `verify_many` + verified-first assembly + coverage); `tests/test_query_planner.py`, `tests/test_evidence_hygiene_seam.py`, `tests/test_faceted_synthesis.py`.
**Modified (small):** `pipeline.py` — extract a reusable `verify_and_persist(...)`; the hygiene seam reads `chunk_structure` via a new small helper in `persistence/chunk_structure_repo.py` (currentness-gated LEFT JOIN — read-only). `api/routers/summaries.py::_run_summarize_job` — query-scope routing. `summaries_response.py` — optional `coverage` (+ optional per-citation `evidence_role`). `integrations/gemini/generator.py::_prompt` — optional `claim_target` (+ `summary-v6`) [SHIP IF LOW-RISK]. `app/frontend/js/20_synthesis.jsx` — coverage strip + verified-first grouping; `19_synthesis_failures.jsx` copy. **No production write path changes `chunk_structure`/H1b** — the seam only reads.

## 16. Acceptance test (steering #10, #11) — REPLACES the Vasiliki literal query

Cliff's library does not hold the built-environment fMRI/EEG literature, so the literal Vasiliki query is retired. **Process (must precede implementation eval):**
- Cliff + Lucien **freeze ONE broad multifaceted query BEFORE seeing rebuilt-Ask results**, on a topic **actually represented in Cliff's library**, preserving Vasiliki's *structure*: broad phenomenon + several named facets + related findings + a structured account of findings/roles. Chosen before, never cherry-picked after.
- Retain a set of **narrow regression queries** (e.g., a single-paper stat lookup) that must return **byte-identical** results to today's single-query path.
- **Product question:** *does rebuilt Ask materially outperform old Ask on a realistic oracle-shaped question Cliff's actual library can answer?*
- **A substrate-populated corpus is already available for integration** — a 229-paper copy of Cliff's library (the H1c study DB) has `chunk_structure` and `source_components` fully backfilled — so both the frozen acceptance query (drawn from topics his library actually covers) and the old-vs-new artifact, including the real evidence-role/hygiene distribution, can be measured against real data. Use a fresh copy (copy-then-read); do not run against the live H1c-A3 study DBs.

**Old-vs-new comparison is an acceptance artifact** (an audit-style script, not shipped in the app), recording for the frozen query — **OLD:** retrieved chunk count, contributing papers, obvious bibliographic/boilerplate contamination, claims generated, verified claims, coverage behavior; **NEW:** planner facets, retrieved evidence by facet, contributing papers, evidence-role/hygiene distribution, claims generated, verified claims, facet coverage, provenance quality. **Criterion is not "more claims" — it is materially more useful VERIFIED synthesis, cleaner evidence selection, broader relevant coverage, stronger provenance.**

## 17. Test plan (Rev 2 additions in bold)

**Unit (pure, fast):** narrow/broad routing; facet schema validation; facet cap (≤6, <3→narrow); duplicate-query suppression; malformed planner response → fallback; provider-shape agnosticism (fake `complete` for messages/chat_completions/responses/gemini); budget policy (per-facet/per-paper/global, dedup, anti-starvation); coverage classification incl. **retrieval-failure ≠ absence**; provenance preservation; verifier-authority (fake generator's unsupported claim stays flagged). **Hygiene seam: scientific/unknown lead; bibliographic/structural demoted-not-deleted; captions retained; `unknown` never penalized; absent/stale `chunk_structure` → no-op (identical ordering to no-seam); currentness gating (stale row ignored).** **Per-facet claim-target bound (≤3 rendered).** **Verified-first assembly ordering.**
**Integration (real embed + real NLI; seeded generator; against a backfilled real corpus):** broad path yields materially more verified claims + populated coverage + cleaner evidence-role distribution than the single-query path; narrow regression identical; complete retrieval failure → `no_evidence_retrieved` (not absence); planner-failure fallback identical; **hygiene demotion measurably reduces reference-entry/structural chunks in the evidence pool without dropping scientific/unknown evidence.**
**Unit vs integration:** routing/validation/caps/dedup/coverage/hygiene-ordering/assembly are **unit**; retrieval quality, verified-claim counts, real classifier data, and the frozen acceptance case are **integration**.

## 18. Migration / schema impact

**None.** Facet plan + coverage ride `summaries.scope_ref_json` (the `generation_truncated` precedent). Optional per-citation `evidence_role` is read from `chunk_structure` at render time. `chunk_structure`/H1b tables **already exist** (migrations 0079–0081); the seam only **reads** them.

## 19. Implementation sequence

0. **Prerequisite (overnight, cheap, no network):** run/confirm `tools/backfill_chunk_structure.py` against Cliff's library; check `--summary`. Without it the hygiene tier is a safe no-op (retrieval fix still ships).
1. `query_planner.py` (+ unit tests) — pure, provider-mockable.
2. Extract `verify_and_persist` from `pipeline.py` (behavior-preserving; existing tests are the net).
3. `chunk_structure_repo` currentness-gated read helper (+ unit tests).
4. `faceted_pipeline.py`: retrieval → hygiene seam → budgets → `FacetEvidence` → bounded generation → one `verify_many` → verified-first assembly → coverage (+ unit tests on pure parts).
5. Route `_run_summarize_job` (narrow unchanged); `summaries_response` coverage/evidence_role.
6. `_prompt` claim-target + `summary-v6` [if low-risk]; frontend coverage strip + verified grouping (+ `build_frontend.py`).
7. Old-vs-new artifact on the frozen query; narrow regressions; `pytest -n auto -q`; Principles/LATENCY/QA/Experience sign-off.

## 20. Component disposition — MUST SHIP / SHIP IF LOW-RISK / DEFER

**MUST SHIP TOMORROW**
- Deterministic narrow/broad pre-gate; bounded provider-agnostic planner (3–6 facets, validation, fallback).
- Per-facet retrieval; dedup; per-paper/per-facet/global budgets; reuse of existing repeated-boilerplate exclusion.
- `FacetEvidence` with **faithful text**; one batched `verify_many` (verifier unchanged).
- Verified-first assembly; per-facet coverage with retrieval-failure ≠ absence; post-hoc ≤3-claims/facet cap.
- Graceful no-op when `chunk_structure`/H1b absent; no schema migration; minimal coverage strip; narrow-path fallback unchanged.

**SHIP IF LOW-RISK**
- **The `chunk_structure` deprioritization hygiene tier** (the "wire in H1a" piece) — gated on the overnight backfill; no-ops otherwise.
- Overnight H1a backfill against Cliff's library (enables the tier).
- Per-facet claim-target `(1,3)` via parameterized prompt (`summary-v6`).
- Flagged-claim grouping/collapse; per-citation `evidence_role` surfacing.

**DEFER**
- Category B (reconstruction / assembled EvidenceUnits) — H1c-A3.
- Hard exclusion via `chunk_structure` — H1a study (no code clears 95% precision).
- H1b **component-level** provenance hydration (SourceLocator/`component_path` on citations) — no safe chunk→component bridge; build + validate the locator next.
- H1b source-representation-state annotation on citations (needs H1b backfill; modest value).
- Multiple queries per facet; generation concurrency; evidence-first rewrite; persisting facets in real columns.

## 21. Estimated risk

- **Low:** planner, budgets/dedup, coverage, hygiene **ordering** (no deletion → cannot lose evidence), `scope_ref` persistence, coverage strip, graceful no-op.
- **Medium:** `verify_and_persist` extraction (trust-spine refactor — mitigated by existing summary tests); faceted orchestration; the `_prompt` claim-target change (bumps cache signature).
- **Watch:** substrate **population** in Cliff's library (backfill prerequisite); broad-path latency (sequential generations — background-absorbed); provider variance in planner JSON (robust parse + fallback). **Verifier + thresholds untouched, so the honesty invariants cannot regress.**

---

RECOMMENDED NEXT-DAY IMPLEMENTATION:
Ship a bounded query-planner **plus** a conservative evidence-hygiene seam on the Ask (query-scope) path. A deterministic narrow/broad pre-gate routes narrow questions to today's exact path; broad questions get one structured, provider-agnostic `complete()` producing 3–6 validated facets (one subquery each), per-facet retrieval, then a **deprioritization-only** hygiene pass using the already-built H1a `chunk_structure` (`evidence_role`: scientific/unknown lead, bibliographic/structural demoted-not-deleted, captions/unknown retained; reuse the existing repeated-boilerplate exclusion) — **no hard exclusion (H1a study), graceful no-op when the backfill is absent** — followed by dedup + per-paper/per-facet/global budgets, `FacetEvidence` carrying faithful text + role metadata, **bounded 1–3-claim/facet** generation via the existing generator, one unchanged batched `verify_many`, verified-first assembly, and honest per-facet coverage (retrieval-failure never rendered as library-absence), persisted in `scope_ref_json` with a small coverage strip. Provenance stays the existing durable attachment+page+verified-quote+precision chain; component-level SourceLocator hydration and any Category-B reconstruction are **deferred** (no safe chunk→component bridge; H1c-A3 still validating). Narrow path and verifier thresholds are untouched; ≤ 1 + 6 provider calls; no schema migration. Enabling prerequisite: an overnight H1a backfill on Cliff's library. Acceptance is a pre-frozen broad query on a topic Cliff's library actually covers, judged by an old-vs-new artifact on verified-synthesis usefulness, cleaner evidence selection, coverage, and provenance — not claim count.
