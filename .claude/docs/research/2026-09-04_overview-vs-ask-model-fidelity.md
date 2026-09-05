# Synthesize → Ask: model fidelity, evidence eligibility, and section-aware retrieval

**Date:** 2026-09-04
**Status:** research only — no production code, schema, migration, threshold, or prompt was modified.
**Corpus:** the maintainer's 219-paper testing library (`.local/validation-summarize/validation.sqlite`),
scoped to the **My Publications** axis.
**Provenance of every number below:** the artifacts listed in §10.

---

## 0. Why this investigation exists

Vasiliki asked Synthesize → Ask a broad, multi-construct synthesis question and got **0 of 4 claims
verified**. Splitting it into subquestions did not help. A first pass attributed this to claim
granularity. That hypothesis was **tested and refuted**, and the investigation then had to be
restarted twice on methodological grounds — both times because the corpus was being characterised in
a way that overstated the evidence actually available to the pipeline.

This document reports the corrected study. It supersedes every earlier count in this thread.

A second question motivated it: the **blinded preregistered Overview study**
(`callosum_blinded_local_model_review_final.xlsx`) found Qwen ≈ Gemini, which appeared to contradict
the Ask results. That apparent contradiction is resolved in §4.

---

## 1. Corpus definition — evidence, not membership

**Axis membership is not evidence.** The unit of available scientific evidence is *a substantive chunk
derived from a processed scholarly PDF that the production Ask pipeline can actually retrieve*.

Eligibility rules were **imported from** `summarization/pipeline.py::_source_chunks_for_scope`, not
reimplemented: live papers → **inner** join `chunks→attachments` → `attachment_document_role_clause(
ARTICLE_DOCUMENT_ROLES)` → `exclude_repeated_boilerplate_chunks` → embedding currency via
`current_chunk_embedding_ids`.

| stage | papers |
|---|---|
| in the My Publications axis | 49 |
| live (`deleted_at IS NULL`) | 48 |
| with any attachment | 40 |
| with a PDF attachment | 40 |
| PDF marked available | 40 |
| ≥1 article-role chunk (production join) | 40 |
| surviving boilerplate exclusion | 40 |
| ≥1 substantive body chunk | 40 |
| ≥1 current embedding | 40 |
| **final eligible corpus** | **40** |

Chunks: 10,976 article-role → **9,275 post-boilerplate — the pool Ask actually retrieves from** → 735
substantive under the analytic filter in §1.1.

**Collapsed distinctions.** All 115 attachments in this DB are `application/pdf` and `available`, and
all 23,875 chunks are `extraction_tool='pymupdf'`. There is no non-PDF chunk anywhere, so
"has attachment" = "has PDF" = "PDF-derived". The only real attrition is that **8 of 48 papers have no
attachment at all**. **Zero** chunks lack a current embedding.

### 1.1 A methodological note on "substantive"

A first attempt defined substantive as `len(text) >= 200`. That was an **invented threshold that
silently did most of the filtering**: this library's median chunk is **88 characters** (75th pct 201)
because it chunks at fragment level. It was replaced by "contains a sentence with a result-reporting
verb". Production applies **no** length or content filter, so 9,275 (production pool) and 735
(analytic subset) are reported separately throughout and never substituted for one another.

The 88-character median is itself a finding: the verification gate requires
`cosine(sentence, chunk) ≥ 0.7` against targets that are often one fragment long.

### 1.2 Relational coverage (not keyword coverage)

"'hippocampus' appears in 13 papers" is not evidence the corpus can answer *what the hippocampus does
in late-life depression*. Requiring facet **and** clinical outcome **and** a relational verb in one
eligible chunk:

| facet | papers | chunks |
|---|---|---|
| serotonin / SERT | 11 | 28 |
| structural MRI | 9 | 25 |
| hippocampal changes | 9 | 15 |
| mild cognitive impairment | 8 | 22 |
| amyloid pathology | 8 | 23 |
| executive dysfunction | 6 | 9 |
| fMRI / connectivity | 5 | 16 |
| glucose metabolism / FDG | 5 | 17 |
| MRS neurometabolites | 3 | 8 |
| **default mode network** | **3** | **5** |

Each construct is **substantially represented in the corpus, greatly reducing the risk that failure is
driven simply by topical absence.** This does *not* establish answerability; corpus representation and
answerability are different claims.

**DMN was withheld from the primary fixture.** Literal "default mode network"/"DMN" occurs in 3 papers
/ 5 chunks, while its constituent regions (posterior cingulate, precuneus) occur in **15 papers / 46
chunks** without the DMN label. Keeping it would have reintroduced a coverage confound. It is preserved
separately (`dmn_known_weak_case.json`) as a partial-coverage case for later work on library-fit
behaviour, and is **not** in any denominator here.

---

## 2. The oracle-quote battery — is there a paraphrase-fidelity gap?

16 stratified quote→claim pairs across 8 linguistic transformations, drawn from 16 distinct eligible
My Publications papers, each verified for provenance (paper, attachment, chunk, section,
`pymupdf`/`application/pdf`). An earlier 16-pair battery drew from the whole library and only 9 pairs
qualified; **its 12/16 and 13/16 totals were withdrawn**, not carried forward.

The model is handed the supporting passage outright and asked only to restate it — plain text, no
grammar, one claim. An echo guard records token overlap so a verbatim copy cannot score as paraphrase.

| stratum | Qwen | Gemini |
|---|---|---|
| extractive | 2/2 | 2/2 |
| syntactic | 2/2 | 2/2 |
| abbreviation | 1/2 | 0/2 |
| rearrangement | 2/2 | 2/2 |
| compression | 1/2 | 2/2 |
| numerical | 2/2 | 2/2 |
| association | 2/2 | 2/2 |
| null finding | 2/2 | 2/2 |
| **total** | **14/16** | **14/16** |

**An exact tie.** This is consistent with the blinded preregistered Overview study and resolves the
apparent contradiction: there is **no broad Qwen-specific quote-to-claim paraphrase-fidelity deficit**.

The supported statement is narrow and deliberately so: *Qwen shows no meaningful disadvantage relative
to Gemini when the supporting evidence is handed to it directly.* It does **not** generalise to "Ask
failure is not model capability" — the oracle condition removes evidence selection, quote extraction,
grammar-constrained output, and multi-chunk context, all of which are themselves capability-dependent.
§4 shows that is exactly where the models diverge.

### 2.1 A verifier finding, preserved not repaired

Three of the four oracle failures are **correct abbreviation expansions that the verifier rejected**.
Thresholds were not altered.

| model | abbreviations | support | contradiction | both models |
|---|---|---|---|---|
| Qwen | DBS → deep brain stimulation; AD → Alzheimer's disease | 0.033 | 0.072 | yes |
| Gemini | DBS → deep brain stimulation; AD → Alzheimer's disease | 0.016 | 0.135 | yes |
| Gemini | MCI → mild cognitive impairment; 7T MRS → seven-tesla magnetic resonance spectroscopy | 0.005 | 0.007 | no |
| Qwen | MDD → major depressive disorder | 0.009 | 0.005 | no |

Every expansion is correct. The local NLI model (`cross-encoder/nli-MiniLM2-L6-H768`) does not know
the abbreviations, so **expanding one currently breaks citation verification** — in a corpus dense with
LLD, MCI, AD, DBS, SERT, FDG, MRS, DMN. These are **verifier calibration cases, not generator
failures** (`verifier_abbreviation_finding.json`).

---

## 3. Ask baseline (A0) — frozen evidence, both models, 3 replicates

`SummaryScope(scope_type="cluster_node", cluster_node_id=<My Publications>, query=…)` is an existing
production path: same eligibility and ranking as a query synthesis, restricted to one axis's papers.
No production change, no experimental ID injection. Retrieval ran once per question; the ordered
bundle was then pinned so both models saw byte-identical evidence. Retrieval was confirmed
**byte-identical across independent runs**.

### 3.1 What retrieval delivered

| # | chunk | paper | section | chars | content |
|---|---|---|---|---|---|
| 1 | c23924 | p11 | **references** | 468 | bibliography entry |
| 2 | c23773 | p11 | — | 493 | **"Please cite this article as:"** |
| 3 | c27995 | p34 | — | 109 | **"Key Words:"** line |
| 4 | c23865 | p11 | **references** | 306 | bibliography entry |
| 5 | c23971 | p11 | **references** | 362 | bibliography entry |
| 6 | c32651 | p54 | introduction | 1027 | **the only article prose** |
| 7 | c28075 | p34 | **references** | 1792 | bibliography block |
| 8 | c23986 | p11 | **references** | 264 | bibliography entry |

**Seven of eight chunks are bibliography or front matter; three papers; five chunks from one paper.**
Zero chunks are both substantive and relation-bearing.

This is systematic. References are **29% of the eligible pool but 62% of the top-8**, decaying to 36%
by depth 200 — over-represented 2.1× exactly where the `top_k=8` budget binds.

### 3.2 Generation

| model | verified / citations (rep 1, 2, 3) |
|---|---|
| **Qwen** | **0/6, 0/6, 0/6** |
| Gemini | 5/7, 4/7, 3/8 |

---

## 4. Failure chain A–G — where each model actually breaks

| question / model | n | A corpus | B top-8 | C chunk | D verbatim | **D evidential** | E follows | **F verifier agrees** | G facet |
|---|---|---|---|---|---|---|---|---|---|
| primary / Qwen | 18 | 100 | 83 | 100 | 100 | **0** | 0 | 100 | 100 |
| primary / Gemini | 22 | 82 | 68 | 91 | 100 | **36** | 27 | **64** | 82 |
| control / Qwen | 54 | 100 | 50 | 100 | **0** | **0** | 0 | 100 | 100 |
| control / Gemini | 21 | 100 | 100 | 100 | 86 | **100** | 48 | 100 | 100 |

*(the "control" question is a same-corpus, denser social/facial/moral fixture — §5)*

### 4.1 Qwen breaks at D — quote selection

Qwen emits **DOI/URL locator strings as its quote**: 69 of its 72 non-evidential quotes are DOIs. In
the control block **not one of 54 quotes was even verbatim** in its cited chunk. In the primary block
all 18 *were* verbatim — because the retrieved chunks were bibliographies that genuinely contain those
DOI strings. Either way: **zero evidential quotes across 72 citations**, so nothing downstream can
succeed.

The oracle battery removed precisely this operation, and there Qwen tied Gemini. **The divergence is
entirely in verbatim quote extraction from multi-chunk context under the JSON grammar** — not in
paraphrase fidelity.

### 4.2 Gemini breaks at F — and this is the serious one

With clean evidence Gemini is sound (100% evidential quotes, verifier agrees 100%). With
bibliography-polluted retrieval, **verifier agreement falls to 64%**: of 12 "verified" citations,
**10 are grounded in non-evidential text** — 6 `references`, 4 front matter.

> **Claim:** "There is no association found between lower hippocampal volume and Alzheimer's disease
> pathology in late-life depression." — **verified, support 0.975**
> **Evidence:** a bibliography entry — `den Stock, J., … 2017. No Association of Lower Hippocampal
> Volume With Alzheimer's Disease Pathology in Late-Life Depression.`

The system put a green verified badge on a substantive scientific claim whose only support is **a
reference-list title in another paper**. That paper does not report the finding; it cites it. Another
verified at 0.9826 against `"Please cite this article as: Christopher W. Davies-Jenkins…"`.

The verifier is not malfunctioning — NLI correctly finds the claim entailed by the quoted title.
**A title is not a finding, and nothing in the pipeline encodes that distinction.** This is a false
positive with a green badge, and it is worse than the false negatives.

---

# PART II — SECTION-AWARE EVIDENCE EXPERIMENT

Separately commissioned: *can constraining retrieval to more appropriate article sections materially
rescue Ask?* Manipulated variable is **only** `SummaryScope.sections`, the existing production filter.
Question, corpus, `top_k=8`, embeddings, query vector, prompts, and thresholds held constant.

## 5. Section-label audit

Labels come from `pdf_processing/sections.py::SectionTracker` — a **stateful heuristic** matching exact
normalized headings against a fixed alias table; a chunk inherits the last recognized heading, so
everything before the first match stays NULL. Canonical values: `abstract, introduction, methods,
results, discussion, data_availability, code_availability, funding, conflict_of_interest, ethics,
references, supplementary_material`. `discussion` absorbs *conclusion/limitations*; `methods` absorbs
*participants/procedure/measures/statistical analysis*.

| section | chunks | papers | substantive | relation-bearing |
|---|---|---|---|---|
| references | 2,696 | 39 | 0 | 0 |
| **(NULL)** | **1,957** | 40 | 407 | 20 |
| discussion | 1,310 | 38 | 470 | **75** |
| results | 1,174 | 36 | 441 | **52** |
| methods | 895 | 36 | 445 | **49** |
| introduction | 816 | 28 | 324 | 31 |
| supplementary_material | 290 | 7 | 28 | 0 |
| abstract | 18 | 8 | 9 | 1 |
| funding / COI / data_avail / code_avail | 119 | — | 45 | 0 |

**21% of chunks are NULL-section.** `abstract` exists but is nearly empty.

**Label noise is confirmed, not assumed.** GROBID has been run on part of this library (386 eligible
chunks carry a `grobid_section_id`). Where both labels exist they disagree: **32 chunks the heuristic
labels `references` are labelled `Discussion` by GROBID**, and 16 NULL-section chunks have a GROBID
section. GROBID coverage is far too sparse here to substitute, but it confirms mislabelling in both
directions. Production's section filter reads `chunks.section` only — the heuristic — and never GROBID.

## 6. Primary section ablation — retrieval

"Usable" = substantive article prose **and** carrying facet + outcome + relation.

| arm | sections | **usable/8** | substantive/8 | contamination/8 | papers | max 1 paper | facets/8 | median d |
|---|---|---|---|---|---|---|---|---|
| **A0** | unrestricted | **0** | 1 | 7 | 3 | 5 | 4 | 0.393 |
| **A1** | intro + discussion | **5** | 6 | 2 | 5 | 3 | 6 | 0.437 |
| A2 | intro + results + discussion | 4 | 5 | 3 | 4 | 3 | 6 | 0.434 |
| A3 | results + discussion | 4 | 5 | 3 | 3 | 5 | 5 | 0.437 |
| A4 | abstract + intro + discussion | 5 | 6 | 2 | 5 | 3 | 6 | 0.437 |

**A4's frozen top-8 is the identical eight chunks as A1** — no abstract chunk reached the top-8 — so it
is not a distinct condition and was not given a duplicate generation run.

**At the retrieval stage the answer is yes, decisively.** A0 returns **zero** usable chunks; A1 returns
**five**. Contamination 7/8 → 2/8, papers 3 → 5, single-paper dominance 5 → 3, facets 4/8 → 6/8.

Critically, **median distance rises** (0.393 → 0.437). The bibliography chunks were genuinely the
*closest* matches. Similarity was working as designed and selecting non-evidence — which is why
"similarity ≠ evidential usefulness" must be enforced structurally, not by tuning a threshold.

## 7. Primary section ablation — generation and verification

2 replicates per cell. **GENUINE** = verified **and** source chunk is substantive article prose **and**
the claim is not a near-verbatim echo of its own quote (token overlap < 0.9).

| arm | model | usable/8 | citations | verified | echo | non-evidential source | **GENUINE** |
|---|---|---|---|---|---|---|---|
| A0 | Qwen | 0 | 18 | 0 | 0 | 0 | **0** |
| A0 | Gemini | 0 | 22 | 12 | 0 | 10 | **2** |
| A1 | Qwen | 5 | 22 | 0 | 0 | 0 | **0** |
| A1 | Gemini | 5 | 19 | 1 | 0 | 0 | **1** |
| A2 | Qwen | 4 | 16 | 6 | **6** | 0 | **0** |
| A2 | Gemini | 4 | 14 | 2 | 0 | 0 | **2** |
| A3 | Qwen | 4 | 21 | 4 | **4** | 3 | **0** |
| A3 | Gemini | 4 | 14 | 1 | 0 | 0 | **1** |

**Raw verified count moved in the wrong direction while evidence quality improved sharply.** That is
not an experimental defect — it shows **verified-count is an invalid success metric across these arms**,
because A0's high count was manufactured by the bibliography-title false positive. Removing the
bibliography removed the easy "verifications".

### 7.1 A third false-positive mechanism: verbatim echo

**Every one of Qwen's 10 "verified" citations in the whole study is a near-verbatim echo** (overlap
≥ 0.9). It emits chunk text as its own claim and the same text as the quote; a sentence trivially
entails itself. Examples awarded *verified*:

- *"Structural Imaging in Late Life Depression"* — a **section heading** (42 chars), support 0.9207, retrieval 1.0
- *"improvement in cognition and larger gray matter volumes was observed. The speciﬁc frontal, tempo- ral, and parietal cortical regions implicated in the structural ana"* — a **truncated mid-word fragment**, support 0.9892

Qwen's **genuine** verified total across the entire study is **zero**. The echo guard built for the
oracle battery is exactly what production verification lacks.

### 7.2 Why good evidence still fails for Gemini

Gemini's A1 claims are responsive, correctly grounded, 19/19 verbatim from real prose — and still
mostly fail, for three distinct reasons:

1. **The retrieval gate rejects well-supported claims.** Of 3 citations with support ≥ 0.55, **2 fail
   only on `retrieval_confidence`**. Worst case: *"Late-life depression is associated with an increased
   risk of all-cause dementia…"* — **support 0.9389, retrieval 0.6962**, rejected by 0.004.
   Mechanism: `cosine(sentence, chunk)` favours short topic-dense text, so a 1,000–4,000-character
   Discussion chunk is *diluted* relative to the claim — **genuine evidence scores lower on this gate
   than a bibliography title did.** The same pathology bites at retrieval and again at verification.
2. **Abbreviation expansion** — *"…in **late-life depression**"* against a quote saying *"…of **LLD**"* →
   support 0.0022. Same blind spot as §2.1.
3. **Cross-quote synthesis** — *"Studies using structural MRI have inconsistently reported decreased
   gray matter volumes"* is supported by two quotes jointly but by **neither alone**, and the verifier
   requires one quote to entail the whole sentence.

## 8. Question-type routing study (retrieval only)

Three corpus-supported questions, each against unrestricted / hypothesized-appropriate /
deliberately-inappropriate section sets. Responsiveness was judged **per question type** (sample
language for methods, reported-effect language for findings, interpretive framing for interpretation)
rather than by one fixed rule, so the conclusion is not built into the metric.

| question | arm | responsive/8 | substantive/8 | papers | median d |
|---|---|---|---|---|---|
| Q_METHODS | unrestricted | 1 | 4 | 5 | 0.270 |
| | *expected* methods+results | 1 | 5 | 5 | 0.344 |
| | inappropriate intro+discussion | **2** | 7 | 6 | 0.311 |
| Q_FINDINGS | unrestricted | 2 | 5 | 2 | 0.237 |
| | *expected* results+discussion | **0** | 7 | 4 | 0.332 |
| | inappropriate intro+methods | **4** | 7 | 5 | 0.376 |
| Q_INTERPRETATION | unrestricted | 2 | 5 | 5 | 0.306 |
| | *expected* intro+discussion | **2** | 7 | 6 | 0.312 |
| | inappropriate methods+results | 0 | 3 | 5 | 0.335 |

**Only 1 of 3 went in the hypothesized direction.** The Q_FINDINGS reversal was inspected rather than
assumed, and it is **real, with an identified cause**: the "expected" Results arm retrieved **eight
table and figure captions** —

> *"Table 4 Lower Serotonin Transporter Availability in Late-Life Depressed (LLD) Patients…"*
> *"Fig. 1. Decreased Serotonin Transport Availability in LLD Patients and Healthy Controls…"*

— which are topically dense (they name the exact variables) and so win on cosine similarity, but state
what a table *shows*, not what was *found*: no comparison statement, no statistics. Meanwhile the
"inappropriate" Introduction arm returned real prose that does state associations.

This is the **same underlying pathology in a third guise**. Short, topic-dense, title-like text beats
long substantive prose on embedding similarity, whether it is a **bibliography entry** (§3.1), a
**section heading fragment** (§7.1), or a **table/figure caption** (here).

The architectural implication is that the discriminator that matters is **chunk type**
(caption / heading / bibliography / prose), *not* section label.

## 9. Hard-filter false negatives

Measured against all 228 usable relation-bearing chunks in the eligible pool:

| arm | keeps | loses | of which NULL-section | facets lost *only* to filtering |
|---|---|---|---|---|
| A1 | 106/228 | 122 | 20 | **none** |
| A2 | 158/228 | 70 | 20 | **none** |
| A3 | 127/228 | 101 | 20 | **none** |

Every constrained arm discards the same **20 usable NULL-section chunks** (8.8% of usable evidence),
but **no facet becomes falsely absent** — each arm retains 8/8 facets at pool level. So on this corpus
a hard filter costs recall without creating a facet-level blind spot. Combined with the confirmed label
noise (§5), that favours **preferred-sections-first with a coverage check and fallback** over a
permanent hard gate — but it does not show a hard gate failing catastrophically here.

## 10. Architectural hypotheses — what the data support

| | verdict |
|---|---|
| **H1** section filtering is enough | **Unsupported.** Retrieval was fixed (0 → 5 usable/8); genuine verified yield did not rise (2 → 1/2/1). |
| **H2** helps but insufficient | **Supported.** Best arm still covers 6/8 facets and wastes 2/8 slots on heading fragments at `top_k=8`. |
| **H3** question-aware section routing | **Not supported as hypothesized** (1 of 3 correct direction). The signal that matters is chunk type, not section. Routing is not refuted as an idea — the *section* proxy for it is. |
| **H4** hard filters unsafe | **Partially supported.** Real label noise (32 references↔Discussion disagreements), 20 NULL-section usable chunks lost per arm — but no facet lost. Favours preference + fallback. |
| **H5** Results need special handling | **Supported, with cause identified**: not numeric density but **caption and heading fragments outcompeting Results prose**. Results hold 52 usable relation-bearing chunks — second only to Discussion. |
| **H6** section choice is secondary | **Supported for Qwen** (0 genuine verified in every arm regardless of evidence). For Gemini the blocker *moved* from retrieval to the verification gates — a different finding than "secondary". |

### The single most consequential result

Section filtering **converted fake verifications into honest failures**. A0/Gemini showed 12 verified,
10 of them grounded in bibliography or front matter; A1 showed 1 verified, grounded in real prose.
The pipeline became more honest and no more productive. That is the right direction for a tool whose
premise is that every claim carries its evidence — but it means the binding constraints are elsewhere:
**quote-type eligibility, the retrieval-similarity gate's bias against long prose, verifier abbreviation
blindness, and single-quote entailment.**

## 11. Frontend / prompt-engine implications — to evaluate, not implement

- A visible, editable, overridable section scope is **not yet justified by the routing data** (§8). The
  same UI keyed on **chunk type** ("exclude bibliography and captions") is better supported.
- **No warning modal for Results.** The experiment found no user-facing risk that justifies
  interrupting the workflow; the difficulty is a chunking artifact, not a property of Results prose.
  Explanatory microcopy would be honest; a modal would not be earned.
- **Section in provenance** (`Paper X | Results | p. 7`) is supported independently of routing: §4.2
  shows a user currently cannot tell that a verified claim was grounded in a reference list. Surfacing
  the section is the cheapest available mitigation for the false-positive class.

## 12. Limitations

1. **One corpus, one axis, 40 papers, one maintainer's own publications.** Findings about reference-list
   density and caption-heavy Results may not generalise to other libraries or publishers.
2. **`substantive` and `responsive` are my analytic constructs**, not production concepts, and are
   regex-based. The `substantive` test does **not** detect table/figure captions — the responsiveness
   test caught those; a chunk-type classifier would need real work.
3. **2 replicates per section arm, 3 for the baseline.** Gemini varies run to run (A0: 5/7, 4/7, 3/8);
   single-arm differences of ±1 verified are within noise. The Qwen result (0 genuine in all 8 cells)
   is not.
4. **Generation ran under CPU contention** from a parallel agent session on the same machine; this
   affected latency (144–497 s per local run) and caused one transient provider timeout, but not
   determinism — frozen retrieval was byte-identical across independent runs.
5. **An earlier baseline attempt was contaminated** by two concurrent processes writing one filename;
   those results were discarded, not reported. Retrieval was unaffected (deterministic) and verified as
   identical. The quarantined file is `CONTAMINATED_ask_batch_results.json`.
6. **The DMN weak-coverage case and the Q_METHODS/Q_INTERPRETATION routing arms were retrieval-only.**
7. **No claim is made about Overview.** The blinded study was not re-run; §2 only shows the Ask oracle
   result is consistent with it.

## 13. Artifacts

`eligible_corpus.json` · `relational_coverage.json` · `dmn_known_weak_case.json` ·
`verifier_abbreviation_finding.json` · `oracle_battery_v2.json` · `oracle_local.json` ·
`oracle_gemini.json` · `ask_batch_run_20260904-201107.json` · `failure_chain_coded.json` ·
`section_ablation_retrieval.json` · `section_generation_20260904-204436.json` · `routing_study.json`
(scratchpad; harnesses `eligible_corpus.py`, `oracle_bridge.py`, `ask_batch.py`, `section_ablation.py`,
`section_generation.py`, `routing_study.py`, `code_chain.py`).
