# Callosum 0.6.0: deferred backlog (recorded, not fixed)

> *Publication note (2026-10-31, inc 616 documentation commit): absolute local paths were rewritten to `%USERPROFILE%` form and a session-scratchpad path was replaced by a description before committing. No finding, number or status was changed.*

**Revised 2026-10-31:** adds §B, the separately scoped MiniLM-family retirement workstream (directive §6).

**Criterion.** Each item here lacks a specific user-visible failure or data-safety risk *within the 0.6.0 scope*, or
belongs to 0.7.0. They are candidates for GitHub issues after Cliff reviews them; none was opened in this audit.

| # | Item | Why deferred | Evidence | Suggested follow-up |
|---|---|---|---|---|
| D1 | **Back matter re-admitted by inc 611/612 with wrong scientific labels.** 18 of the 23 NEW admissions in the held-out v2 gate were NONSCI: 11 conflict-of-interest, 3 data-availability, 3 acknowledgement/funding and 1 appendix. The 11 that went through the M1 rescue got `evidence_role = scientific` (`shape.clear_prose`); the 7 that went through the prose-fragment path got `unknown` | Not a scientific false admission (that means BIB), not a false exclusion. None reached any 8-passage evidence set. Hygiene and precision cost | `%USERPROFILE%\callosum-data\experiments\source-role-heldout-20261030\v2\ADJUDICATION_RESULTS_V2.md` | Classify standard back-matter headings as NONSCI or non-evidence before the rescue or prose veto. **Requires its own held-out check; must not be tuned on those 67 passages.** Would bump `DERIVATION_VERSION` and reuse the 0.6.0 modernization path, an additive per-paper re-derive |
| D2 | **Reference-region boundary (chunk 4134).** The anchored region is the densest matched cluster and extends forward only, so entries before the cluster (refs [1]–[3]) stay unlabelled. In papers scope no heading filter applies (`pipeline.py:288`), so 4134 is still selected (SP11, MiniLM, position 2) | Shared by old and new code; not a 611/612 regression; bounded to unanchored leading entries | Same file, T3 section; `tools/backfill_chunk_structure.py::infer_reference_region` | Backward extension with an explicit stop rule, plus a held-out check |
| D3 | **Bibliography control depends on Crossref metadata.** M2 under OLD rose from 294 to 518 by adding DOIs and Crossref references alone. Papers without DOIs, preprints, or publishers that deposit no references keep retrievable bibliographies in papers scope under both versions | Requires egress (Crossref) and a consented enrichment flow; modernization must stay cache-only | `V2_EXECUTION_RECEIPT.md` (5 of 30 papers unanchored) | Surface "reference metadata missing" as a per-paper, inspectable signal; a separate opt-in enrichment action |
| D4 | **Papers scope applies no heading-based reference exclusion** (`pipeline.py:288`, query scope only) | Behavior is unchanged since #82; M2 demotion covers anchored papers | v1 held-out analysis | Decide deliberately whether a papers-scope rescue-aware heading filter is wanted |
| D5 | **Harness labelling defect.** The `_rescued_heading` fate suffix in the held-out harness means "has a references label", not "was rescued" | Experiment tooling only; frozen files deliberately unchanged | v2 notes | Fix in any future harness version |
| D6 | **Older libraries hold `pymupdf-block-v1` / `document-text-block-v1` chunks** (research master: 1,769 + 149) | 0.6.0 indexes and classifies whatever chunks exist; no extraction change is in scope | Scope §3 | A future re-extraction generation (D7) |
| D7 | **No side-by-side chunk generations.** Chunks are single-generation; re-extraction would replace rows (citation mappings `SET NULL`; annotations survive by bbox) | Not needed while extraction is unchanged | Architecture §2 | Design generation-keyed chunks plus atomic swap **before** any release that changes extraction |
| D8 | **Pause/Resume buttons inside the Status popover** (`js/04c_status.jsx` rows have navigate and dismiss only) | Clicking the row already reaches Pause/Resume in Settings; invariant #5 is satisfied | `04c_status.jsx:173-178` | Typed per-store row actions, if wanted |
| D9 | **Battery and metered-connection awareness** | Below-normal priority, memory floors and the disk guard cover the blocking risks | — | Pause on battery below X% and on metered networks for the model download |
| D10 | **DeBERTa thresholds calibrated on MiniLM2** | Recalibration is scientific tuning, excluded from 0.6.0. Automatic preference uses the unchanged thresholds behind gate G1 (Scope §6) | `nli_profiles.py`; Phase 34 bakeoff §7 | The bakeoff's §7 qualification (natural negatives, fresh human-adjudicated set, DeBERTa-specific threshold confirmed on a second set) once DeBERTa is the long-term verifier; see §B R3 |
| D11 | **Stance features, Suggest-citation, Critical Read and re-verification stay on MiniLM2** | Deliberate inc 608 scope, pinned by `test_stance_features_and_reverify_keep_the_baseline_nli` | inc 608 notes | §B R4–R6 |
| D12 | **Arctic vs BGE-small not resolved** (the high-coverage replay found Arctic stronger on recall, BGE stronger on fidelity) | 0.6.0 scope names Arctic S; no new model comparison | Memory: high-coverage replay state | A future profile addition, which reuses the profile machinery unchanged |
| D13 | **Unfinished Qwen3 / 0.7 work**: the decomposition engine, contract-directed child answers, the reviewed route, the overview role S/T5O, paper-first retrieval, q_lld | Reserved for 0.7.0; must not be pulled into 0.6.0 | Memory entries for the Ask E2E track | 0.7.0 planning |
| D14 | **Native-region withholding limitations (research route)**: 23431, 38379 and 35671 withheld; a11/a57 mislabelled Methods regions | Research route only; strict xfail fixtures in place | `INCREMENT-607-NOTES.md` | Unchanged |
| D15 | **Retrieval index for paper and axis embeddings** stays MiniLM (Arctic is chunk-only) | Clustering and axes are outside the Ask profile scope | `profiles.eligible_chunks_query` | Revisit only if axis scoring adopts profiles |
| D16 | **Uncommitted `app/backend/llm/providers.py` in the main checkout** (separate work) | Not 0.6.0 content; must be excluded (B1). Listed so it is not lost | `git status` on main | Owner decides; a re-freeze needs documentation per the inc 557/575 precedent |

---

## B. MiniLM-family retirement (separately scoped architectural workstream)
**Goal.** A compact model stack:
- Arctic S for embedding and retrieval where scientifically appropriate;
- DeBERTa for NLI verification;
- Qwen3 for generation from 0.7.0, once separately qualified.

**Not a 0.6.0 blocker.** No step may break a working scientific workflow merely to remove a dependency. Legacy
vectors, model files and shared Hugging Face caches are removed only after every dependency is demonstrably retired,
and under an explicit ownership and retention policy.

### B.1 Inventory of remaining dependencies (2026-10-31, integration branch @ `829f35f4`)
| # | Dependency | Model | Code | Contract / thresholds | Stored data | Intended replacement | Validation needed | Priority |
|---|---|---|---|---|---|---|---|---|
| R1 | Ask retrieval fallback generation | MiniLM | `query_ranking.py`, `faceted_pipeline.py`, ingest `embed_chunks` (`pdf_processing/ingest.py:219,291`; `embeddings/admission.py`) | None beyond identity isolation | MiniLM chunk vectors (desktop: 68k) | Arctic S as the only chunk index, once ingest embeds Arctic directly | Ingest-time Arctic embedding latency (LATENCY.md); catch-up never needed | 1 (retire last among retrieval items: needed while any library is mid-modernization) |
| R2 | Verification similarity gate (retrieval ≥ 0.70) and quote extraction in synthesis | MiniLM | `summarization/verification.py:70-77`, `routers/summaries.py` (baseline `model`) | **0.70 calibrated on MiniLM cosine** | Uses the MiniLM chunk vectors | Arctic S cosine, **or** dropping the similarity gate in favour of NLI-only | **Recalibration study** (a new threshold, not transplanted), preregistered | 2 |
| R3 | Synthesis NLI verifier (compatibility) | MiniLM2 | `nli_profiles.py`, `dependencies.resolve_support_scorer` | support/contradiction 0.55 (calibrated on MiniLM2) | None | DeBERTa (automatic preference, B8) | G1 at minimum; full qualification for DeBERTa-specific thresholds (Phase 34 §7) | 1 |
| R4 | Stance features: Suggest-citation, citation context, classify-stance, beyond-library | MiniLM2 | `summarization/stance.py`, `citations/suggest.py`, `methods/citation_context.py`, `routers/citation_stance.py`, `citations/beyond_library.py` | Own stance thresholds (support/mention/contrast; inc 460 reuses the 0.7/0.55 config) | None | DeBERTa | Per-feature calibration; label-order contract (`stance._label_index` positional fallback hazard) | 3 |
| R5 | Critical Read (single, set, WIP) and Tier-2 critique verification | MiniLM2 + MiniLM | `methods/critical_review.py`, `critical_review_set.py`, `routers/wip_critical_review.py` | High-confidence contrast threshold | Transient draft embeddings (WIP) | DeBERTa + Arctic S | Calibration on contrast pairs | 3 |
| R6 | Imported-synthesis re-verification | MiniLM2 + MiniLM | `summarization/reverify.py` | Must match the original verifier to be meaningful | Historical `scope_ref_json` | Verify with the verifier recorded in provenance | A policy decision: re-verify historical runs with their own model or with the current one | 4 |
| R7 | Paper embeddings | MiniLM | `embeddings/pipeline.embed_papers`; `target_type="paper"` rows | — | Paper vectors | Arctic S paper embeddings | Regeneration plus downstream checks (R8–R10) | 2 |
| R8 | Axis embeddings and axis scoring | MiniLM | `clustering/axis_scoring.py:28-29` | **assignment 0.7 / uncertainty 0.5 calibrated on MiniLM** | Axis vectors, `cluster_node_papers` | Arctic S | Recalibration on curated axes; membership-change review | 2 |
| R9 | Agglomerative clustering, duplicates, discovery/acquisition/capture similarity | MiniLM | `clustering/*`, `routers/duplicates.py`, `discovery`, `acquisition/*`, `capture/provisional*.py` | Feature-specific cosine cut-offs | Uses R7 | Arctic S | Per-feature threshold review | 3 |
| R10 | Registration publication retrieval | MiniLM | `routers/registration_retrieval.py` | Weak-search expansion threshold | Uses chunk vectors | Arctic S | Recalibrate the expansion threshold | 3 |
| R11 | Historical provenance | — | `scope_ref_json`, `embedding_version_verified_against`, `verification_version` | Must stay readable | Summary rows | Keep forever (read-only); never rewrite | None | — |
| R12 | Model files | MiniLM, MiniLM2 snapshots | HF cache | — | ≈90 MB + ≈330 MB | Remove only after R1–R10 retire | A cache-ownership policy (the shared HF cache may hold other tools' models) | last |

### B.2 Retirement conditions
1. Every function in R1–R10 runs on Arctic S or DeBERTa with its own validated threshold, or is deliberately
   redesigned.
2. Upgrade path: an additive regeneration of paper and axis vectors through the same supervised, resumable
   infrastructure (inc 610), with a complete-index switch and no partial serving, mirroring 0.6.0.
3. Only then:
   - delete MiniLM vectors, through a migration plus a VACUUM policy and a disk preflight;
   - stop embedding MiniLM at ingest;
   - drop the MiniLM2 load paths.
4. Historical provenance stays readable, and old syntheses still display which model produced them.
5. Expected payoff:
   - **disk:** ≈1.5 KB per chunk of vectors freed, ≈1.5–2.7 GB at 4,000 papers;
   - **memory:** one embedding model and one NLI model resident instead of four;
   - **maintenance:** one calibration lineage per role.
