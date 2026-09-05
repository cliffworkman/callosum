# Evidence-hygiene architecture: turning extracted PDF text into evidence

**Date:** 2026-09-04
**Status:** research + scratch prototype. **No production code, schema, migration, threshold, prompt,
or provider was modified.** No model generation was run.
**Prototype:** `tools/evidence_hygiene/` (dev-only, imports `app.backend.*` read-only, library DB
opened `mode=ro`). Derived data in gitignored `.local/evidence-hygiene/`.
**Baseline preserved:** the Ask study (`2026-09-04_overview-vs-ask-model-fidelity.md`) and all its
artifacts are untouched and referred to here as **B0**.

---

## 0. Why

B0 found that Callosum treats arbitrary extracted PDF text as if it were valid scientific evidence.
For the primary broad synthesis question the unrestricted top-8 held **0 usable relation-bearing
chunks**; 7 of 8 were bibliography or front matter. The follow-up section experiment identified the
shared mechanism: **bibliography entries, heading fragments and table captions are all short,
topic-dense, title-like text**, so they beat long substantive prose on embedding similarity.
Semantic similarity is not evidential usefulness, and the distinction has to be structural.

---

## 1. Current PDF → evidence pipeline

| Stage | Where | What actually happens |
|---|---|---|
| extraction | `pdf_processing/extraction.py:133-202` | `page.get_text("dict", sort=True)` → blocks/lines/spans. Image blocks dropped (`:145`). |
| normalization | `extraction.py:224`, `:566` | **`_normalize_space` only** — `" ".join(text.split())`. Nothing else. |
| chunking | `extraction.py:205-260` | **one chunk == one PyMuPDF block.** No sentence splitting, no size bounds, no merging. |
| sections | `sections.py:78-94` via `extraction.py:227` | stateful `SectionTracker`; pure single-line heading blocks are **dropped entirely** (`:227-228`); everything before the first recognized heading stays NULL. |
| filtering | `summarization/chunk_filtering.py:143-167` | `exclude_repeated_boilerplate_chunks`, whole-chunk exact key, ≥3 distinct pages, ≤25 words. |
| embedding | `embeddings/pipeline.py:58-60` | raw `chunks.text` verbatim; only in-model `normalize_text` (lower + whitespace). |
| retrieval | `summarization/pipeline.py:243-291` | live papers, article role, boilerplate exclusion, then cosine rank. |
| quote/provenance | `quote_matching.py:35-70`, `verification.py:360-384` | re-opens the PDF; `quote_confidence` is binary 0.0/1.0. |

### The finding that reframes the whole problem

**A complete canonicalizer already exists and is not used where it matters.** `extraction.py:281-505`
provides `canonicalize_faithful_text_variants`, `LIGATURE_MAP`, `SOFT_HYPHEN`, `DASH_EQUIVALENTS`,
an 18-prefix `LINE_BREAK_HYPHEN_PREFIXES` keep/remove strategy, and `_canonicalize_text` returning
`(canonical_string, token_map)`. It is called **only** from `quote_matching.py` and
`verification.py` — never from `make_chunk_drafts`, never from the embedding pipeline. Verified
live: it turns `tempo- ral`→`temporal`, `signiﬁcant`→`significant`, `supernatu- ral`→`supernatural`.

So this is largely a **wiring** problem, not a build problem.

### A correction to an earlier claim

`char_start`/`char_end` (`extraction.py:230-232`) index a **synthetic concatenation of emitted chunk
texts**, not any real document. The `char_end - char_start == len(text)` invariant holds by
construction and proves nothing about source alignment. They cannot recover a source span; exact
provenance comes only from re-reading the PDF. The prototype asserts they are never read.

---

## 2. Evidence-ready text model

Four levels, deliberately kept separate:

| Level | Meaning | Prototype representation |
|---|---|---|
| `raw_text` | immutable; **the only quoting surface and the only verification haystack** | `chunks.text`, identified by `raw_sha` |
| `normalized_text` | comparison/derivation surface; never shown to a model | sidecar + run-length alignment to raw |
| retrieval unit | what gets embedded and ranked | sidecar; **1:1 with chunk in this pass**, but modelled so future re-chunking is one mapping table |
| evidence eligibility | **a set, never a text transform** | `eligibility(policy_id, chunk_id, eligible, reason_codes)` |

Reuse rather than rewrite: `_canonicalize_text` called with
`char_token_indices = list(range(len(text)))` makes the existing `token_map` **be** the char→raw
alignment.

---

## 3. Reference-list audit and region detection

### 3.1 Reuse audit (done before building anything)

| Existing | Gives |
|---|---|
| `OpenAlexClient.fetch_referenced_works` + `fetch_work_meta` | cited work ids → title/authors/year/doi; cache-backed (`adapter.py:180`) |
| `SemanticScholarClient.fetch_reference_contexts` | production's primary source (`routers/reference_integrity.py:291`) |
| Crossref cache | **344 of 400** cached records embed the ordered `reference` array |
| `reference_instances` | persisted Meta-Reference output (only 5 papers in this library) |
| `_canonical_characters` | ligatures, soft hyphen, NFC, dash unification |
| `strip_punctuation` + `normalize_text` | punctuation→space, lower, whitespace collapse (already paired for duplicate-paper detection, `duplicate_detection.py:110`) |

**The only new primitive needed is a whitespace-free `dense_key`.** Everything else is composition.

Field coverage across the **31,122** cached reference entries: DOI 89%, year 67%, author 67%,
journal-title 62%, first-page 61%, **article-title only 42%**, unstructured 25%.

### 3.2 The dense key

```
"Functional connectiv-\nity in late-life depression"  ->  functionalconnectivityinlatelifedepression
"Functional Connectivity in Late-Life Depression"     ->  functionalconnectivityinlatelifedepression
```

This makes line-break artifacts irrelevant **without** first solving the general hyphenation
problem. Token n-gram matching cannot do it — it sees `["connectiv", "ity"]` and never recovers the
word. Measured effect: title matching rose from **31% → 90%** of a paper's known references.

### 3.3 Per-prong results (96 papers with both chunks and cached reference metadata)

| prong | papers where a region was inferred | median references matched | median region span |
|---|---|---|---|
| DOI only | 32 / 96 | 0.55 | 0.08 |
| **title only (dense key)** | **69 / 96** | **0.90** | 0.05 |
| title + author/year | 72 / 96 | 0.98 | 0.08 |
| **combined** | **77 / 96** | **0.98** | 0.08 |

**DOI is the weakest prong in practice despite 89% metadata coverage** — the DOI is in the record
but frequently not *printed* in the reference list, exactly as predicted for older works. Only
627 of 4,243 matches came through it in an earlier run. **Title is the powerful general signal.**
Author/year is corroboration-only and never establishes a region alone, because in-text citations
carry the same surname and year.

### 3.4 Region inference

Density-based, not first-match: the region is the sustained cluster where bibliographic matches are
far denser than the paper's own baseline, trimmed to actual match positions, then extended by
bibliographic *shape* at the end. Two calibration bugs were found and fixed by measurement:

- a `n // 20` window gave a 21-chunk window on a 424-chunk paper and 62 on a 1,253-chunk one,
  diluting a real reference list until it vanished → capped at 15;
- an absolute 0.25 density floor rejected a correctly-located region (8 matched entries, positions
  284–322, first and last both unmistakable numbered entries) at density 0.238 → floor is now purely
  relative to the paper's own peak.

### 3.5 Adjudicated bound accuracy

Six papers inspected by reading the boundary neighbourhoods:

| paper | start | end |
|---|---|---|
| p17 | correct (first real entry) | correct (last real entry; page number excluded) |
| p60 | **perfect** — immediately after a literal `References` heading | off by ~1 (entry continuation) |
| p4 | off by 1 (landed on a continuation line) | off by ~1 (journal footer) |
| p58 | bleeds earlier into Discussion prose | correct |
| p128 | correct | correct |
| p70 | bleeds earlier into Discussion prose | includes a running head |

**Ends are now largely correct; starts are correct in about half and bleed earlier in the rest.**
The bleed is handled downstream by the classifier's prose veto, which decides per chunk rather than
moving a boundary — the right division of labour. A start-retraction heuristic was tried and
**rejected by adjudication**: on p60, whose start was exactly right, it moved the boundary four
positions earlier onto a conference announcement.

### 3.6 Evidence role, not deletion

A reference-region chunk is typed `reference_entry` and made ineligible **for scientific-claim
synthesis only**. It remains real bibliographic evidence for "what does this paper cite?". Nothing
is deleted and no content is erased.

---

## 4. Paper-global boilerplate

Production's `exclude_repeated_boilerplate_chunks` groups per paper but only over **the candidate
list it is handed**, which `pipeline.py:274-277` has already section-filtered. Measured directly on
the My-Publications axis:

| section filter | pool | excluded | **running-head chunks that leak through** |
|---|---|---|---|
| whole paper | 11,069 | 1,711 | — |
| intro + discussion | 2,410 | 186 | **77** |
| results + discussion | 2,921 | 365 | **47** |
| methods | 1,059 | 28 | **112** |

Example leaking into a Methods-scoped synthesis: `r 5HT Transporter and Resting-State Imaging in
MCI r`. This confirms backlog #79 with numbers.

The prototype detects whole-paper, independent of any later filter, and adds **position + x-stability**
(≥3 distinct pages, x0 σ ≤ 6pt) — the half production's text-only detector lacks, and what makes
hard exclusion defensible. It also character-canonicalizes the repetition key, because 865 chunks
contain U+00AD and a head rendered with a discretionary hyphen on one page otherwise yields a
different key. Result: **1,018 running heads across 82 papers**, e.g. `THE ANOMALOUS-IS-BAD BIAS IN
HADZA HUNTER GATHERERS` at σ=0.0 across 24 pages.

**An ordering claim I had to revise.** I asserted bibliography must be fenced before repetition
detection. Measurement showed that applies to **substring/shingle** repetition, which can nominate
journal and author strings from reference content and then match them inside body prose.
**Exact-key** repetition is safe to run first and is *needed* first, because page furniture
otherwise depresses the bibliographic density signal below its floor. Layout repetition and
cross-paper semantic repetition remain separate detectors; **semantic repetition is measured, never
enforced** — excluding near-duplicate Methods across papers would delete exactly the convergent
evidence a synthesis needs.

---

## 5. Line-wrap / hyphenation

Stored text contains `"meth- ods"` (hyphen + space) because newlines are collapsed before anything
else runs. Measured: **2,800 chunks (11.7%) across 107 papers** carry a `word- word` artifact;
865 contain U+00AD; **zero** contain `word-\nword`.

The existing canonicalizer already handles the character classes and discretionary hyphenation, but
its `remove` variant **corrupts genuine compounds** not on the 18-prefix list. Paper-local corpus
evidence (does the joined or hyphenated form appear elsewhere in this same paper?) resolves
**76%** of 6,643 distinct occurrences — 71.1% JOIN, 4.9% KEEP, 0.6% ambiguous, 23.4% no evidence.

Against the existing prefix heuristic, on the 5,050 cases where corpus evidence exists, the two
**disagree on 566 (11.2%), in both directions**:

| corpus says | engine produces | examples |
|---|---|---|
| KEEP | joined (wrong) | `two- tailed`→`twotailed`, `three- dimensional`, `perspective- taking`, `large- scale`, `spatio- temporal` |
| JOIN | hyphenated (wrong) | `pre- vious`→`pre-vious`, `super- natural`, `inter- actions`, `sub- set` |

**Unresolved cases stay unresolved.** No default JOIN: a genuinely ambiguous occurrence is stored as
a bounded candidate set with no preferred reconstruction, and every downstream containment test uses
the any-of-variants semantics production already uses.

**Bibliography detection does not depend on solving this** — the dense key sidesteps it entirely.

---

## 6. Terminology / acronyms

**1,105 candidate `(paper, short-form)` definitions across 104 papers** from explicit
`long form (SHORT)` patterns, including non-uppercase scientific forms. Detection is paper-local and
preserves the original surface form; the intended representation is an annotation
(`LLD [defined in this paper as late-life depression]`), never a rewrite of the quote.

This connects to a live B0 finding: **three of four oracle-battery failures were correct
abbreviation expansions the verifier rejected** (`DBS`→deep brain stimulation, support 0.033;
`MCI`/`7T MRS` expanded, support 0.005). Those remain verifier-calibration cases, preserved in
`verifier_abbreviation_finding.json` with thresholds untouched.

**Not validated in this pass**: no acronym normalization was applied to any embedding or verifier
comparison, per the instruction to establish correctness first.

---

## 7. Chunk-type classification

Closed set; `unknown` is a real answer and is **never excluded**.

| type | n | share |
|---|---|---|
| unknown | 11,936 | 50.2% |
| reference_entry | 2,922 | 12.3% |
| body_prose | 2,687 | 11.3% |
| table_cell_debris | 2,516 | 10.6% |
| math_or_symbol | 1,473 | 6.2% |
| running_head | 1,018 | 4.3% |
| caption | 637 | 2.7% |
| publication_metadata | 288 | 1.2% |
| abstract_prose | 151 | 0.6% |
| heading_fragment | 77 | 0.3% |
| keyword_line | 60 | 0.3% |
| citation_instruction | 17 | 0.1% |

Front matter is **split**, never one undifferentiated class: `abstract_prose` is evidence;
`keyword_line`, `citation_instruction` and `publication_metadata` are not.

`table_cell_debris` requires narrow width **plus grid siblings** (`grid_support ≥ 3`). A first
version counted all peers and fired on **74%** of the corpus, because every body paragraph shares a
left margin with every other one; only narrow fragments can be a cell's siblings.

Captions are typed but **not assumed universally non-evidential** — they are tested as their own
separate policy, last.

---

## 8. Tiny fragments

**36% of chunks are under 40 characters**; the corpus median chunk is **73 characters**. Composition
of the sub-40 population: ~36% single short tokens (`LLD`, `C`, `GSH`), ~29% numeric/symbol only
(`10`, `#`), 21% truncated without terminal punctuation, 11% lowercase continuations. **93% have a
narrow single-span box** — table-cell debris, roughly **23% of the whole corpus**, each carrying its
own embedding and competing as an independent retrieval unit.

**Naive neighbour merging will not fix this:** only **12%** of truncated fragments are followed by a
lowercase-starting chunk, so chunk-id order does not track reading order. Re-chunking is the real
fix and is deliberately **not** attempted here; §12 sketches it.

---

## 9. Ordering

Empirically derived, each with its failure-if-reversed:

```
calibration → character normalization → EXACT-key layout repetition
   → reference-region anchoring → shape/geometry features
   → chunk-type classification → eligibility → retrieval
```

- calibration first: width rules must normalize against `col_w` (the paper's own body-prose modal
  width), never the page — page W/H are discarded at ingest and every body chunk in a two-column
  paper is "narrow" relative to the page;
- exact-key repetition before reference anchoring (revised claim, §4);
- **substring/shingle** repetition only *after* bibliography fencing;
- hyphen repair before acronym discovery (`electro- encephalography (EEG)` otherwise yields the
  long form `encephalography` and the definition is silently discarded);
- classification consumes one lexical surface only, to avoid two rules disagreeing about whether a
  chunk contains `—` or `-` and silently never firing together.

---

## 10. Regression corpus

**Partially built.** Feature extraction, per-type samples, per-prong reference outputs and the
adjudicated boundary neighbourhoods are all recorded in the sidecar and study artifacts, and the
strata are defined (`easy_case`, `no_references_label`, `region_not_inferred`,
`no_reference_metadata`, `sparse_DOIs`, no-DOI, older papers). **The frozen, fully adjudicated
fixture file with expected normalization / chunk type / eligibility per fixture is NOT yet written.**
That is the largest outstanding piece of this pass and it gates the exclusion-precision numbers in
§14.

---

## 11. B0 vs B1 retrieval

Frozen embeddings. Same query vector, same store, same index; the **only** difference is the
`candidate_embedding_ids` set. Full-depth retrieval once per arm, sliced offline, because
`SQLiteVecVectorStore._search_limit` is `min(len(candidates), top_k, max_knn_k)` and a shrunken
candidate set with a fixed `top_k` would conflate exclusion with a changed KNN limit.

**Primary question**, My Publications pool (10,976 embedded chunks):

| policy | excluded | **junk in top-8** | papers | context chars | Jaccard vs P0 |
|---|---|---|---|---|---|
| P0 production | 0 | **7/8** | 3 | 4,821 | 1.00 |
| P1a + running heads | 539 | 7/8 | 3 | 4,821 | 1.00 |
| P1b + table debris | 1,473 | 7/8 | 3 | 4,821 | 1.00 |
| **P1c + references** | 2,900 | **2/8** | 6 | 9,822 | 0.231 |
| **P1d + publisher furniture** | 3,072 | **0/8** | 4 | 9,760 | 0.067 |
| P1f + headings/math | 3,612 | 0/8 | 4 | 9,760 | 0.067 |
| P1g + captions | 3,867 | 0/8 | 4 | 9,760 | 0.067 |

**Control question:** P0 2/8 junk → 0/8 at P1c; Jaccard 0.6; chars 6,273 → 5,894.

**7/8 non-evidence → 0/8, and the context roughly doubles in characters** — more real content, not
merely fewer chunks. The resulting top-8 is responsive prose (*"Major depressive disorder in
late-life is a risk factor for the development of all-cause dementia…"*, *"executive function,
memory and motor speed, even after remission of their depressive symptoms"*).

For comparison, the best **section-filtering** arm in B0 reached 5/8 usable. **Hygiene is the
stronger intervention.**

Two honest observations: **running heads and table debris changed nothing for these two queries**
(Jaccard 1.00) despite being 4.3% and 10.6% of the corpus — references did essentially all the work
here; and paper diversity rose 3→6 at P1c but fell back to 4 at P1d, which is **not yet explained**.

---

## 12. Recommended minimum implementation

**Clearly justified**

1. **Wire the existing canonicalizer into ingest and embedding.** It exists, it is already trusted
   by verification, and it fixes ligatures, soft hyphens, NFC and dashes corpus-wide.
2. **Make repetition detection whole-paper, independent of the section filter** (backlog #79),
   adding position + x-stability. Retrieval-time; no schema change.
3. **A `chunk_type` + `scientific_claim_eligible` pair**, with references typed rather than deleted.
   This is the one real schema addition, and it is additive.
4. **Reference-region detection from already-cached reference metadata**, multi-prong with fallback
   (title-dense-key primary, DOI where printed, author/year corroboration, shape heuristic when no
   metadata exists).

**Uncertain / not yet justified**

- per-occurrence hyphen resolution written into stored text (see R1);
- caption exclusion — typed and testable, but it changed nothing measurable here;
- re-chunking table regions (design sketch only, §8);
- acronym expansion reaching embeddings or the verifier.

**Ingestion-time vs retrieval-time:** character canonicalization and chunk typing belong at
ingestion (they are properties of the document). Eligibility belongs at retrieval (it is a property
of the *question* — references are ineligible for a claim and eligible for "what did this cite?").

**Provenance:** `raw_text` stays the only quoting surface and the only verification haystack. A
normalized surface is a derivation with a run-length alignment back to raw.

**Reprocessing:** typing and eligibility are derivable from stored columns without re-reading PDFs,
so they can be backfilled incrementally per paper. Only a change to stored *text* would require
re-extraction and re-embedding — which is why this pass deliberately did not make one.

---

## 13. Amendment 7: the `quote_confidence = 1.0` after anchoring failure

**Not a production correctness bug.** `_quote_confidence` (`verification.py:360-384`) establishes
verbatim-in-chunk via `canonical_text_contains` **before** any PDF access; the subsequent
`locate_quote_for_attachment` answers a different question — whether a box can be drawn.
`location.py`'s own docstring states the design: *"Exact PDF rectangles are an enrichment of the
already-persisted chunk provenance. A linked file may be moved… that must degrade to the caller's
honest page/region fallback rather than abort synthesis verification."* Confidence 1.0 with
precision `region` is invariant #1 and invariant #2 each answering their own question honestly.

**The real issue is a testing gap.** The region fallback conflates moved file, unreadable file, and
tokenizer mismatch with no distinguishing signal, and `tests/test_quote_matching.py` monkeypatches
`locate_quote` away entirely — so a regression in the exact-anchor rate would be invisible. All 252
confidence-1.0 quotes in this library carry a bbox.

---

## 14. Risks

- **R1 (highest).** Per-occurrence hyphen resolution produces a string in **neither** of
  `canonicalize_faithful_text_variants`' two variants, so a model quote spanning two
  differently-resolved artifacts would fail the binary `quote_confidence` gate. The corpus-wide
  `canonical_text_contains(normalized, raw)` failure count has **not yet been measured**; it must be
  before any normalized text is stored.
- **R2.** Silent exact→region coordinate degradation, invisible to current tests (§13). Any recipe
  that lowers the exact-anchor rate must be rejected regardless of retrieval gains.
- **R3.** `bbox_json` has per-span geometry but no per-span text, so line-level text attribution is
  approximate. Approximations may inform features and must never emit coordinates.
- **R4.** Page width/height are discarded at ingest; all fractional geometry is estimated. Mitigated
  by calibrating against `col_w`.
- **R5.** Over-excluding legitimately short evidence (effect sizes, CIs). `grid_support ≥ 3` is the
  guard; a methods/statistics query stratum is the detector.
- **R6.** Reference-region start bleed into Discussion prose (§3.5), mitigated by the prose veto.
- **R7.** Production's safety valve ("keep everything if a paper would be emptied") can mask
  over-exclusion at paper granularity.

**The ≥95% hard-exclusion gate is NOT yet satisfied for any reason code**, because it requires
held-out sample size and a per-code uncertainty interval and the adjudicated fixture set (§10) is
incomplete. Until then every code should be treated as deprioritize-only.

---

## 15. Unresolved

1. The frozen adjudicated regression corpus (§10).
2. Per-reason-code exclusion precision with confidence intervals (§14).
3. The R1 breakage count.
4. The exact-anchor precision probe (R2).
5. Why paper diversity falls 6→4 between P1c and P1d (§11).
6. 19 of 96 papers where no reference region is inferred, and 11 with no cached reference metadata.
7. Relevance ground truth for recall/MRR — must be manually adjudicated responsive passages, never
   B0 retrieval output; where incomplete, report retention/recovery of known responsive evidence.

## 16. Changes NOT justified by this pass

Deleting references; treating captions as universally useless; any `len(text) >= N` rule; hard
section filtering; trusting `chunks.section` or GROBID labels as ground truth; an LLM normalizer or
classifier; re-chunking; re-embedding; loosening any verification threshold; and resuming
Qwen-vs-Gemini generation experiments.

---

## Artifacts

`tools/evidence_hygiene/{store,corpus,features,structure,refregion,refregion_eval,classify,experiment}.py`;
`.local/evidence-hygiene/{hygiene.sqlite,b0_vs_b1_retrieval.json,refregion_prongs.json}`.
B0 artifacts referenced but unmodified.

---

# FINAL VALIDATION (G1–G4)

Gating pass. No production code, schema, threshold, prompt or embedding was changed; no generation
was run. Artifacts: `.local/evidence-hygiene/{fixtures_frozen.json, safety_r1_r2.json,
refregion_prongs.json, b0_vs_b1_retrieval.json}`.

## FV1. Frozen fixture corpus

**134 fixtures** drawn from real chunks: 103 adjudicated or contestable, **31 unresolved and
excluded from every denominator**. Sampling is two-sided — per predicted class (supports precision)
plus a uniform random draw and targeted strata (the only way a false negative can enter). Every
verdict was reached by reading the raw text, never by consulting the classifier being measured.

Strata covered: reference entries, unlabeled bibliography, reference continuations, Discussion prose
at region boundaries, "Please cite this article as", keyword lines, publication metadata, running
heads, standalone headings, table-cell debris, captions, legitimate short evidence, NULL-section
prose, section-label disagreement, hyphenation artifacts, and the known truncated fragments.

## FV2. Maintainer spot-check set

Only **4 fixtures** are genuine judgment calls, all turning on one question — *does a number without
its referent count as scientific evidence?*

| fixture | text | proposed |
|---|---|---|
| F44485 | "Table 3 The first component explained 18.3% of the variance…" | caption, **eligible** |
| F39057 | "Figure 1. Effects of injury severity on global network measures…" | caption, **eligible** |
| F41636 | "56 ADM 14.5 4.87 <0.0001* 0.46" | table row, not eligible |
| F29836 | "p = 0.146" | table debris, not eligible |

**RULED 2026-09-04 — accepted as proposed. See FV11 for the ruling, its governing principle, and
the consequences, which supersede the caption rows in FV4 and FV8.**

## FV3. Per-reason-code precision (Wilson 95% CI)

| reason code | TP | FP | n | precision | 95% CI | harmful FPs |
|---|---|---|---|---|---|---|
| keyword_line | 6 | 0 | 6 | 100% | [0.61, 1.00] | 0 |
| table_cell_debris | 9 | 0 | 9 | 100% | [0.70, 1.00] | 0 |
| caption | 5 | 1 | 6 | 83% | [0.44, 0.97] | 1 |
| heading_fragment | 5 | 1 | 6 | 83% | [0.44, 0.97] | 0 |
| publication_metadata | 5 | 1 | 6 | 83% | [0.44, 0.97] | 1 |
| reference_entry | 10 | 3 | 13 | 77% | [0.50, 0.92] | 1 |
| citation_instruction | 4 | 2 | 6 | 67% | [0.30, 0.90] | 0 |
| running_head | 4 | 2 | 6 | 67% | [0.30, 0.90] | 0 |
| math_or_symbol | 2 | 5 | 7 | 29% | [0.08, 0.64] | 0 |

**No reason code satisfies the ≥95% gate.** The two at 100% observed are underpowered exactly as the
rule anticipates (lower bounds 0.61 and 0.70).

**Three false positives would delete real scientific evidence:**

1. `publication_metadata` on *"(height), (c) placed onto a plain white background using the GIMP 2
   software package"* — a **sub-figure label** `(c)` matched as a copyright mark. Real Methods prose.
2. `caption` on *"Table 4 below shows the number of extracted statistics and the number of identified
   errors…"* — a sentence **referring** to a table, not a caption.
3. `reference_entry` on *"= 0.15, p = .70, partial h2 = .006; scenarios featuring negative outcomes
   contained the same number of words…"* — real Results content inside an inferred reference region.

**An important non-error class:** most remaining mismatches are confusions *between two
non-evidential types* (`math_or_symbol` vs `table_cell_debris`, `publication_metadata` vs
`running_head`). Those are **eligibility-neutral** — the chunk is excluded either way — and must not
be counted as harm.

Two positive validations: the **prose veto works** (five chunks the section label called
"references" but which are real prose were all correctly kept), and **`unknown` must never be
excluded** — six fragments carrying genuine statistics were classified there.

## FV4. Policy table

| type | disposition | empirical basis |
|---|---|---|
| reference_entry | **DEPRIORITIZE** | 77% [0.50, 0.92], and one FP deleted real Results content |
| running_head | **DEPRIORITIZE** | 67% [0.30, 0.90]; errors non-evidential but underpowered |
| table_cell_debris | **DEPRIORITIZE** | 100% but only n=9, lower bound 0.70 |
| keyword_line | **DEPRIORITIZE** | 100% but only n=6, lower bound 0.61 |
| citation_instruction | **DEPRIORITIZE** | 67% [0.30, 0.90] |
| publication_metadata | **DEPRIORITIZE** | 83%, and the sub-figure-label FP deletes Methods prose |
| heading_fragment | **DEPRIORITIZE** | 83% [0.44, 0.97] |
| caption | **KEEP + deprioritize** (see FV11.5) | captions demonstrably carry findings; 1 FP deleted prose |
| math_or_symbol | **KEEP** | 29% precision — not fit to change eligibility at all |
| shingle contamination | **UNRESOLVED** | not implemented or measured |
| unknown | **KEEP, always** | holds real fragmentary statistics |
| body_prose / abstract_prose | **KEEP** | evidence |

**No class is cleared for hard exclusion in this pass.**

## FV5. R1 — normalization vs faithful quote matching

Per-occurrence hyphen resolution over 2,616 affected chunks; decisions **join 5,882, keep 457,
unresolved 1,694** (unresolved left untouched — no default JOIN).

| representation | chunks failing `canonical_text_contains(normalized, raw)` |
|---|---|
| character canonicalization only | **539** |
| character + per-occurrence hyphen | **528 (20.2% of affected chunks)** |

Failure mix: `join` 153, `join+unresolved` 140, `join+keep` 103, `join+keep+unresolved` 82,
`keep` 29, `keep+unresolved` 7, `unresolved` 14. **Pure-join cases fail too**, so this is not solely
the mixed-variant hazard predicted earlier — a chunk containing a hyphen break the artifact pattern
does not match diverges from the raw text's own "remove" variant as well.

**Safety by intended use — these are not equivalent:**

| use | verdict |
|---|---|
| 1. comparison only (reference matching, repetition keying) | **SAFE** — ephemeral, never stored, never quoted; the dense key already relies on it |
| 2. model-facing semantic text | **UNSAFE** — a model quoting normalized text produces a quote that fails the binary `quote_confidence` gate in 20.2% of affected chunks |
| 3. embeddings | **RESEARCH FURTHER** — embeddings need no round-trip to raw, so R1 does not directly apply; the risk is retrieval drift and was not measured (embeddings were deliberately frozen) |
| 4. stored normalized text | **FAILS** — R1 above plus R2 below |

## FV6. R2 — exact-anchor precision through the real locator

250 quotes probed against real PDFs via `locate_quote_for_attachment`, **not monkeypatched**;
sample deliberately over-weights chunks containing hyphen artifacts.

| surface | exact | region | miss |
|---|---|---|---|
| raw | **240 (96.0%)** | 0 | 10 |
| normalized | **233 (93.2%)** | 0 | 17 |

**7 exact → miss regressions**, all in chunks with hyphen decisions applied (e.g. c29081
*"citalopram- induced changes in cerebral metabolism"*, decisions keep+join). Cause is
**canonicalization mismatch**, not file movement or geometry: the region rate stays 0, so failures
are outright locator misses rather than degraded precision.

**Normalization reduces exact-anchor reliability by 2.8 points, so it fails the R2 gate for any use
touching quote localization — regardless of retrieval benefit.**

**Minimum production regression test recommended:** a fixture set of (attachment, quote) pairs run
through the *real* `locate_quote_for_attachment`, asserting a floor on the exact-anchor rate.
`tests/test_quote_matching.py` currently monkeypatches the locator away, so this entire failure class
is invisible today; `test_pdf_processing.py::FIXTURE_QUOTES` is the table-driven shape to extend.

## FV7. P1c to P1d diversity drop: explained, benign

**Primary.** P1c's top-8 ranks 1 and 2 were `c23773` ("Please cite this article as: Christopher W.
Davies-Jenkins…", paper 11) and `c27995` ("Key Words: Late-life depression…", paper 34). P1d removes
exactly those two, under `citation_instruction` and `keyword_line`.

**Papers 11 and 34 contributed nothing else to the top-8.** Their only representation was
non-evidence, so removing it removed the paper. The freed slots went to `c32087` (p52) and `c27682`
(p32, *"Objective: Late-life depression (LLD) has a substantial public health impact…"* — real
abstract prose).

So the P1c count of 6 was **inflated by the diversity metric counting papers represented solely by
junk**. P1d's 4 papers all contribute real evidence; P1c had 4 such papers plus 2 junk-only ones.
Replacements adjudicated: one clearly better (c27682, substantive prose), one marginal (c32087, a
title-like line).

**Control is unaffected** — P1c and P1d top-8 are identical, 6 papers both.

**Verdict: benign ranking consequence plus a metric artifact.** Not over-filtering. There is mild
**source concentration** worth watching (p32 rises 2 to 3 slots, p52 1 to 2), which is an argument
for a later diversity constraint — deliberately not added here.

## FV8. Implementation-readiness matrix

| component | status | reason |
|---|---|---|
| reference-region typing | **READY TO IMPLEMENT** | 77 of 96 eligible papers, median 98% of known references matched; typing is additive and reversible |
| reference scientific-claim exclusion | **READY ONLY AS DEPRIORITIZATION** | 77% precision [0.50, 0.92]; one FP deleted real Results content |
| paper-global exact boilerplate detection | **READY TO IMPLEMENT** | fixes a confirmed scope defect (112 running heads leak into a Methods-scoped synthesis); whole-paper scope is strictly more correct than today |
| running-head geometry rule | **READY ONLY AS DEPRIORITIZATION** | 67% [0.30, 0.90]; geometry gate is sound but underpowered |
| substring/shingle contamination | **RESEARCH FURTHER** | designed, never implemented or measured |
| table-cell debris handling | **READY ONLY AS DEPRIORITIZATION** | 100% but n=9, lower bound 0.70 |
| publication-metadata handling | **READY ONLY AS DEPRIORITIZATION** | the sub-figure-label FP deletes Methods prose |
| heading handling | **READY ONLY AS DEPRIORITIZATION** | 83% [0.44, 0.97] |
| caption handling | **READY ONLY AS DEPRIORITIZATION** (FV11.5) | ruling received; the states-a-finding detector remains an unvalidated proxy |
| safe character canonicalization | **RESEARCH FURTHER** | 539 chunks fail faithful relatability even at this level; safe for comparison, not yet for storage |
| paper-local hyphen JOIN/KEEP | **BLOCKED** for stored text | R1 20.2% failure, R2 minus 2.8pp exact anchoring |
| unresolved candidate-set representation | **READY TO IMPLEMENT** | 1,694 occurrences correctly left unresolved; no default JOIN was needed anywhere |
| acronym extraction | **RESEARCH FURTHER** | 1,105 candidates found; no correctness validation run |
| normalized-text embeddings | **RESEARCH FURTHER** | not measured; embeddings were frozen by design |
| exact-anchor regression testing | **READY TO IMPLEMENT** | the probe exists and works; production has no equivalent and cannot see this failure class |

## FV9. Remaining unresolved

1. Maintainer ruling on the 4 contestable fixtures (gates caption policy).
2. Every reason code is underpowered; reaching the 95% gate needs roughly 60–100 adjudicated
   fixtures **per code**, not per corpus.
3. Shingle contamination unimplemented.
4. Embedding-level effects of normalization unmeasured.
5. Recall/MRR ground truth still absent — must be manually adjudicated responsive passages.
6. 19 of 96 papers where no reference region is inferred; 11 with no cached reference metadata.
7. Mild source concentration after publisher-furniture exclusion (FV7).

## FV10. Recommended FIRST production hygiene increment

**Ship the things that are correct independently of any precision gate, and ship no exclusion.**

1. **`chunk_type` + `evidence_role` as recorded, inspectable metadata** — additive columns, derived
   from stored data, backfillable per paper, no retrieval behaviour change. This makes hygiene
   *visible and auditable* before it is ever *load-bearing*, and lets provenance show
   `Paper X | Results | p. 7` and flag a citation grounded in a reference list.
2. **Fix the boilerplate scope defect (backlog #79)** — make repetition detection whole-paper rather
   than over the already-section-filtered candidate list. This is a bug fix whose correct behaviour
   does not depend on any new classifier.
3. **Add the exact-anchor regression test** using the real locator, so the R2 failure class stops
   being invisible.

**Explicitly not in the first increment:** any hard exclusion, any stored normalized text, any
re-embedding, any re-chunking, and any caption policy. Deprioritization-based ranking changes should
follow only once per-code precision is powered, and normalized text should not be stored at all
until R1 and R2 both pass.

---

# FV11. Maintainer ruling and its consequences

## FV11.1 The ruling

Accepted as proposed, and recorded in `fixtures_frozen.json` with status `maintainer_reviewed`:

| fixture | verdict |
|---|---|
| F44485 "Table 3 The first component explained 18.3% of the variance…" | caption, **eligible = true** |
| F39057 "Figure 1. Effects of injury severity on global network measures…" | caption, **eligible = true** |
| F41636 "56 ADM 14.5 4.87 <0.0001* 0.46" | orphan table row, **eligible = false** |
| F29836 "p = 0.146" | bare statistic, **eligible = false** |

**Governing principle (maintainer, 2026-09-04):**

> A quantitative value is usable scientific evidence only when the extracted/reconstructed unit
> retains enough trustworthy context to identify what the value is evidence about. Captions that
> themselves state a scientific relationship or finding remain potentially eligible. Tables/figures
> are not globally non-evidential.

## FV11.2 A correction to FV2

FV2 said "only 4 fixtures are genuine judgment calls". The frozen file actually held **9**
contestable entries. The other five — F41795 (author biography), F25828/F25864 (stimulus vignette
text), F34562 (numbered sub-heading), F41314 (table significance footnote) — are all classified into
**KEEP-side types** (`body_prose` / `unknown`), so **none of them can produce an exclusion error**.
That is why they did not reach the spot-check list, but the phrasing overstated the position. The
accurate statement: 4 fixtures could change an exclusion decision; 5 more are contestable but
eligibility-neutral. F41314 is additionally now settled by the principle — a significance-marker
footnote carries no referent.

## FV11.3 Consequence 1: caption eligibility is per-caption, not per-class

The principle makes eligibility a property of the individual caption. Operationalized as "the
caption states a relationship or finding" and measured across all **637** captions:

| | n | share |
|---|---|---|
| states a relationship/finding → potentially eligible | **204** | **32%** |
| labels contents only → not eligible | 433 | 68% |

Eligible examples: *"TABLE III. Correlations between the acute cerebral metabolic response to
citalopram and age…"*, *"Table 4 Peak voxels for brain regions in which grey matter volume is
correlated with cognitive performance"*.
Label-only examples: *"Table 1 Demographic and clinical characteristics of subjects by group"*,
*"Fig. 4 Model accuracy with different optimization algorithms and learning rates"*.

**This detector is a proxy and is not itself validated.** A first version missed *"A Face Orientation
× Target Race × Word Type interaction **emerged** in Study 1"* — a plain finding — which is why the
estimate moved from 28% to 32% after adding obvious verbs. It needs its own adjudicated fixture set
before it could gate anything.

**A genuine grey zone remains**, and it is the principle's own boundary: captions such as *"Table 2
Results of linear regression analysis for relationships between metabolite levels and cognitive
performance"* **identify what the values are evidence about but do not carry the values** — those
live in table cells. Caption alone is not evidence; caption **plus** its table would be.

## FV11.4 Consequence 2: the principle reframes the fragment problem

**210 chunks of ≤8 words carry a bare statistic** (`p = 0.609`, `p = 0.884`, `shame weakened after
excluding outliers (t=1.6, p=.11)`). Under the principle these **can never be usable evidence as
extracted** — they retain no referent.

This is the sharpest architectural consequence of the ruling: **no eligibility setting fixes them.**
Excluding them loses real statistics; keeping them yields units that can never verify. The only
repair is **re-chunking that restores the referent** — reuniting a value with the sentence or table
header it belongs to. Combined with the earlier measurement that ~23% of the corpus is table-cell
debris, and that caption-plus-table reunification is what would make label-only captions usable,
this promotes re-chunking from an optimization to **the intervention that determines whether roughly
a quarter of the corpus can ever be evidence at all**.

It also explains a B0 observation that previously had no mechanism: Qwen emitting DOI strings and
verbatim chunk echoes as "quotes". A substantial share of the retrievable units genuinely contain no
proposition to quote.

## FV11.5 Amendments to the policy and readiness tables

These supersede the corresponding rows in FV4 and FV8:

| type | disposition | basis |
|---|---|---|
| caption — states a finding (32%) | **KEEP, eligible** | maintainer ruling; carries a stated relationship |
| caption — label-only (68%) | **DEPRIORITIZE, not excluded** | identifies the referent but carries no value; excluding risks the 32% given an unvalidated 
detector |

| component | status | reason |
|---|---|---|
| caption handling | **READY ONLY AS DEPRIORITIZATION** | policy is now settled by the ruling, but the states-a-finding detector is an unvalidated proxy with a demonstrated miss |
| re-chunking (value/referent reunification) | **RESEARCH FURTHER — now high priority** | the principle makes it the only repair for 210 bare-statistic fragments and ~23% debris; previously scoped as optional |

No change to the FV10 first increment: it still ships typing, the backlog #79 scope fix, and the
exact-anchor regression test, with **no exclusion**.

---

# IMPLEMENTATION APPENDIX — inc 577 (H1a, instrumented hygiene baseline)

Shipped 2026-09-05. **This is not the final H1 substrate**; the proposition-preserving
evidence-unit / re-chunking research pass follows, and this increment exists to make that study
empirical. Full narrative: `.claude/docs/increment-notes/INCREMENT-577-NOTES.md`.

## Production files changed

| file | change |
|---|---|
| `app/backend/persistence/schema_chunk_structure.py` | NEW — `chunk_structure` table, closed vocabularies |
| `app/backend/persistence/chunk_structure_repo.py` | NEW — per-paper replace, staleness resolution |
| `app/backend/pdf_processing/chunk_structure.py` | NEW — pure classifier, no I/O |
| `alembic/versions/0079_chunk_structure.py` | NEW — additive table, no `chunks` column touched |
| `tools/backfill_chunk_structure.py` | NEW — owns all I/O; `--inspect` / `--summary` |
| `app/backend/persistence/schema.py` | re-export (one import block) |
| `app/backend/summarization/chunk_filtering.py` | detection split from filtering |
| `app/backend/summarization/pipeline.py` | paper-global keys when a section filter exists |
| `tests/test_chunk_structure.py` | NEW — 16 cases |
| `tests/test_chunk_filtering.py` | +3 section-independence cases |
| `tests/test_pdf_processing.py` | +2 real-locator exact-anchor cases |

**No API endpoint, no JobStore, no Status entry, no UI, no QA route.** Deliberate: those surfaces
attach obligations that should not be spent on metadata not yet trusted.

## Derivation version

`chunk-structure-v1`. Stored per row with the FULL sha256 of the chunk text and its `chunk_version`,
so a re-ingest makes a row recognisably stale rather than letting it masquerade as current.

## Observed retrieval difference

The only behavior change is the boilerplate scope correction. Measured on the real library:

- **default Ask path (no section filter): byte-identical top-8**, and no extra query is issued;
- section-scoped paths correctly exclude genuine running heads that previously leaked
  (`"Structural Imaging in Late Life Depression"`, `"Psychiatry Research: Neuroimaging 321 (2022)"`).

No difference is attributable to the new metadata, because nothing on the retrieval path reads it.

## A finding that revises the research interpretation

FV6 measured normalization at **-2.8 points of exact-anchor reliability** and inferred
canonicalization mismatch. Implementation surfaced a second, independent mechanism worth carrying
into the next pass: `chunks.bbox_json` is a SQLAlchemy `JSON` column, so a DB read yields a decoded
list while a fixture yields a string. A `json.loads()` on the list raised `TypeError` that a broad
`except` swallowed, **silently disabling every geometry rule** — 3,228 repeats detected but all
filed `middle_band`, zero running heads, zero table debris. The research prototype read the column
through raw `sqlite3` (strings) and never hit it.

This does not change any FV conclusion, but it does mean **prototype-to-production parity must be
verified on distributions, not just on unit cases** — the failure was invisible per-chunk and obvious
in aggregate.

## Structural data available for the evidence-unit study

Already stored and now exposed via `--inspect`: chunk/paper/attachment ids, page, heuristic section,
raw text, per-span geometry (`page`, `block`, `line`, `span`, `x0/y0/x1/y1`), chunk id ordering,
`chunk_type`, `evidence_role`, reason codes, reference-region membership + source, repeated-
boilerplate status, derivation version. **Line structure is reconstructible** by grouping spans on
`(page, block, line)`.

## Structural information currently LOST at extraction

The next study should treat these as constraints, not oversights:

1. **Block bounding box** — `TextBlock.bbox` is computed and discarded; only span boxes persist.
2. **Page width/height** — never stored, so all fractional geometry is estimated against `col_w`.
3. **Per-span text** — geometry has no text attribution, so "the text of line k" is approximate.
   Any allocation may inform a feature and must never emit a coordinate.
4. **Pure heading blocks** — dropped entirely at ingest (`extraction.py:227-228`), so a caption whose
   "Table 1" line was its own block has no recoverable label.
5. **True reading order** — `char_start`/`char_end` index a synthetic concatenation, and only 12% of
   truncated fragments are followed by a lowercase continuation, so chunk-id order does not track
   reading order.

Items 1, 2 and 5 are the ones most likely to gate table/caption reunification.

## Deferred (unchanged from FINAL VALIDATION)

Hard exclusion, deprioritization, caption policy, re-chunking, fragment merging, table/figure
reconstruction, normalized embeddings, stored or model-facing normalized text, persisted hyphen
candidate sets, acronym expansion in verification, threshold changes, adaptive top_k, facet planning,
prompt engine, split-and-stitch Ask, provider routing, query-scope KNN redesign.
