# Independent Evidence-Unit / PDF Reconstruction Replication

Date: 2026-09-05

Status: independent findings frozen; no production implementation

Deterministic seed: `20260905`

## 1. Executive Summary

This study independently supports the central concern raised by H1a: Callosum's current unit of
PDF evidence is usually an extraction block, not necessarily a proposition. On the 120-case
probability arm, stratified back to the 23,782 eligible current chunks, an estimated **15.9%** were
proposition-bearing as standalone text (approximate design-based 95% interval **10.1-21.8%**).
The remaining chunks are not all bad evidence: many are useful fragments, table components,
captions, headings, formulas, bibliography, or page furniture. But retrieval currently embeds all
23,782 eligible chunks, so extraction granularity is directly visible to downstream retrieval.

The result is not "merge neighboring chunks." In the 180-case adjudicated sample:

- 35 were already proposition-bearing.
- 27 additional cases were faithfully reconstructable from current stored text and geometry.
- 14 more became faithfully reconstructable only after returning to richer PDF structure; current
  storage left their reconstruction ambiguous and unsafe to activate.
- 28 were context components that should be linked to evidence rather than represented as an
  independent proposition.
- 26 remained unresolved without semantic inference even after PDF reread.
- 50 were not target scientific evidence.
- 29 cases exposed at least one concrete false-join hazard.

The probability arm implies that richer deterministic PDF reread increases the estimated
faithfully reconstructable share from **27.7%** to **32.6%**, a **4.9 percentage-point** gain beyond
what current storage can support safely. That gain is scientifically important, but it is not a
license to reconstruct everything. Ambiguity preservation remains necessary.

Tables are the clearest failure mode. H1a labels 2,674/23,782 eligible chunks (11.2%) as
`table_cell_debris`, but the label is intentionally observational and imprecise. In the independent
probability sample of 11 such chunks, only four were true scientific table values after PDF review;
all four lacked a standalone referent, all four were ambiguous under current storage, and all four
were recoverable after PDF reread. The other seven were figure-axis/equation debris or non-evidence.
Across sampled pages, PyMuPDF's table finder intersected 27 cases: 17 were real table material and
10 were false table detections. Only 5/17 real detections preserved a directly usable row/column
hierarchy without further repair. Table detection is therefore useful for proposing regions, not
safe as a load-bearing evidence reconstruction.

The smallest justified production increment is **ingestion observability/schema groundwork**, not
re-chunking or retrieval replacement: preserve a deterministic source-component graph containing
page dimensions, text-block identity and bbox, line/span order, per-span text, font/style signals,
pure headings, and explicit raw-versus-sorted order. Keep current chunks and embeddings
authoritative. Backfill or re-ingest into a sibling structure, inspect it, and validate conservative
same-column prose reunion before any derived unit affects retrieval.

No model or provider was called. No production code, prompt, threshold, schema, migration,
embedding, chunk text, or production database was changed. The optional retrieval probe was not
run because reconstruction correctness is not yet mature enough for retrieval gains to be
interpretable.

## 2. Independence and Provenance

### 2.1 Isolation boundary

- H1a / increment 577 commit: `614338b25739afe6a92f4fa0a5faea93aea090e0`
- H1a tree: `4bbd758c7ac6e4aa1816d7fe9820f5b25541004e`
- Dedicated branch: `codex/evidence-unit-replication-20260905`
- Preregistration commit: `eeb63a1951acfa2a40f51ba5f67ffe476e31d866`
- Pass-A blindness-boundary commit: `6ae6b47057e8cb80172177e2c3f504c892232afc`

Before this independent report was frozen, I did not open, search, inspect, or use
`.claude/docs/research/2026-09-05_proposition-preserving-evidence-units.md`, the parallel agent's
new evidence-unit scratch directory, or any parallel-agent conclusions. The five-case overlap with
the older H1a frozen fixture set arose from deterministic random sampling; no H1a fixture was
selected or rated by copying its old adjudication.

### 2.2 Database identity

The source was the ignored validation snapshot used by Callosum's existing local research work.
To obtain a coherent snapshot while preserving WAL semantics, the study used SQLite's online
backup API rather than copying only the main file.

| Artifact | SHA-256 |
|---|---|
| Original source main file (identity only) | `16633e3b4e1acaed0aa7217c1fe8fed2e8f6e169fd2cd02d3d32b67d21bc4543` |
| Coherent pristine online backup | `fc402464bfb9eb26b02f4b7bd12a844bbdc828413dcfc751b3cbf8252da93f70` |
| Isolated H1a study database after explicit migration/backfill | `7792279fdbb8c8cfdff80f83b30498bcc67f70c5b1d0238df4b0ab21960a7061` |
| H1a `chunk_structure` rows | `68c94d20735e98cca167e93b15a44743e62240c9aaee656af72b589bc408be3b` |

Both databases passed `PRAGMA integrity_check`. Their pre-migration content counts agreed.

### 2.3 H1a artifact identity

| Artifact | SHA-256 |
|---|---|
| Increment 577 notes | `8ecc473ab043a3cccfa8a617476cf76a01523965e7d20aca91b1e7d267276ef2` |
| H1a evidence-hygiene report | `9ff684ac78e04af5bbfb1e914959ac59e51806bd39940643940aef8c97e0e809` |
| Classifier | `0a7180466679c75589c5b455cbaa297109ce9c67f099073b03fe451c208b5951` |
| Schema | `88bf28877d7efdb99ee6311dc1341bd4be1058636acff95f1d031aa4e803e98b` |
| Backfill | `a8069c1229f4fe444a56073c672260d199584e0e547ba732b8d4e37fc5dc1ee0` |
| H1a ignored sidecar | `1a4eef57cf093df993ef3851caa4519eb2ea8e76d5088dab05f014840806361f` |
| Frozen H1a fixtures | `d436a929cb21c90cdd953c5ab2e557f9e8133d864b7eae7a5fda25abe9d69713` |
| Normalization/anchor safety receipt | `14aa581e0e6210687a879bded7099d533d8b131c6cb6a780420ca3ca35af29c5` |
| Retrieval receipt | `72d31a4133e9972e01c753e84ebd707a8ceba2f32f91c7491bb8332c70078577` |
| Reference-region receipt | `a2a96884c72f2744de231f08d45db92cb3716cd4d89d41cee1ab9589de963834` |

### 2.4 Independent study artifacts

Raw sample material remains ignored because it contains extracted article text and local
attachment paths. The tracked research harness contains only case indices/rubric decisions, not
the source text.

| Artifact | SHA-256 |
|---|---|
| Private 180-case sample | `a1d7901a73804cfdb62abd3c4f258ad029f59fd41d825f07d6a0a1b7b761abaa` |
| Privacy-safe sample manifest | `1dfbeee230acb7f1d9aaa869003cc37f1a62ce063b6fe76a10000801b5276903` |
| Shuffled Pass-A text packet | `18d42df6ab344706e60aa1fb3bf51826a28def0e92fd9ba1ca1ced2912f3b97a` |
| Frozen Pass-A ratings | `acce3518863d44fb71706a050339392fc0c97e33c7f54e60af8d98c94a37253b` |
| Revealed context/PDF hierarchy | `2c431b544635558008a580b9be0c22298e53f65b9fd4c288736ad6f6532cb33c` |
| PDF-reread measurements | `6e6696609de5fdf13d1a44a0b852233ed2bca804574db59247a908e4e5d197f8` |
| Frozen Pass-B ratings | `2351ca0121a2b48cade930874d3e504d1dea04aa7056f6082003abd9c2b683ea` |
| Final independent research harness | `6be345171d7dbef781c461a9c633b6929fc28ea9a8a3805f5eb77c8ca7f28453` |

### 2.5 Documented protocol corrections

Three preregistered amendments were committed before their affected measurement:

1. `413add64fb80514c7f1529b557d220ad493b5b12`: Alembic's CLI ignored the attempted settings
   variable and migrated the configured default database, not the isolated study DB. The H1a
   backfill then failed closed. No sample or outcome had been inspected.
2. `c49c43da5f3cd37dbe859cefd6232da89e574dd2`: corrected the first amendment's description of the
   accidental target to the literal `sqlite:///callosum.db` target.
3. `3b8226b7f02f1cbeb7b5d08ef9350164e779b8c7`: corrected the embedding-identity measurement after
   discovering that vectors live in sqlite-vec tables rather than a nonexistent
   `embeddings.vector` column.

The isolated erroneous default database is excluded audit material. The study database was
restored from the pristine backup and migrated through an explicitly supplied programmatic
Alembic URL before measurement.

## 3. H1a Verification From Code and Database

### 3.1 Structural metadata is non-load-bearing

Verified from code. `chunk_structure` is an additive sibling table. Neither
`app/backend/summarization/pipeline.py` nor `app/backend/embeddings/retrieval.py` reads it.
Increment 577's only retrieval behavior change is the independent correction that computes
repeated-boilerplate keys over each paper's whole chunk set before applying a requested section
filter. Default Ask does not issue that extra query.

### 3.2 Raw text and embeddings remain authoritative

Verified from code and the isolated DB. `chunks.text` remains the embedded/retrieved content, and
the H1a backfill only populates the sibling metadata. Pre/post digests were identical:

| Invariant | Count | SHA-256 |
|---|---:|---|
| Chunk text rows | 23,875 | `dfc55876a891be2903cb0cca598a25c25246aa1decfe97da2dce4443453663da` |
| Embedding metadata rows | 24,134 | `3bfdef4c6e275f3722292f2146c5e98e2e932d24e33d5c46393a373d73d6ff6d` |
| sqlite-vec row IDs | 24,032 | `9b5f4c024380b7f0bd2c80b56de37937db9247fd8832aff91c0d65b29a3df0a4` |
| sqlite-vec vectors | 26 pages | `31ed6c856fdecd30f4a726e60b4d147f150d808ddd3accdb4e4cfe8b491cb89f` |
| sqlite-vec chunks | 26 pages | `e91084a379afdf613c6990de82a831ecec3f1a22a77581a01314a475a3c2e97e` |

The H1a backfill classified 23,782 live/current chunks across 107 papers; a second run reported all
107 already current and re-derived zero.

### 3.3 Geometry exists, but the source representation is incomplete

Verified from code and DB:

- All 23,875 stored chunks had nonempty `bbox_json`.
- Every chunk mapped to exactly one PyMuPDF text block and one page.
- `bbox_json` stores page, block, line, span indices and per-span rectangles.
- SQLAlchemy returns the JSON column as an already-decoded list; raw sqlite returns JSON text.
- `char_start`/`char_end` are offsets in a synthetic concatenation of emitted normalized blocks, not
  offsets in the PDF's original content stream.
- `extract_pdf()` initially observes page width/height, block bbox, span text, font, size, and order,
  but `make_chunk_drafts()` discards page dimensions, block bbox, per-span text, font/style, image
  block geometry, and pure section-heading blocks.
- Extraction calls `page.get_text("dict", sort=True)`. Stored block numbers therefore represent the
  sorted PyMuPDF structure, not an independently preserved original content-stream order.

### 3.4 Pure headings are discarded

Verified from `SectionTracker.observe_block()` and `make_chunk_drafts()`: a pure recognized section
heading updates the section tracker and causes the block to be skipped. On the 161 independently
reread sample pages, 98 current-reread block-text mismatches occurred. Forty-six were positively
identified as skipped pure headings: Methods 15, Discussion 10, Introduction 8, References 6,
Abstract 3, Results 3, and Conflict of Interest 1. The other 52 include formula/table blocks and
span-spacing normalization differences and are not all treated as discarded content.

### 3.5 `bbox_json` runtime representation matters

Verified independently by reading both raw sqlite and the application path. The same column is a
JSON string in raw sqlite and a list after SQLAlchemy decoding. H1a's parser now accepts both. This
is not cosmetic: the earlier list/string mismatch disabled geometry rules corpus-wide while unit
tests using strings continued to pass.

### 3.6 H1a aggregate sanity check

The independent backfill reproduced the reported distribution exactly:

| H1a type | Chunks | Share |
|---|---:|---:|
| unknown | 13,220 | 55.6% |
| table_cell_debris | 2,674 | 11.2% |
| reference_entry | 2,128 | 8.9% |
| body_prose | 1,998 | 8.4% |
| math_or_symbol | 1,476 | 6.2% |
| running_head | 839 | 3.5% |
| caption | 629 | 2.6% |
| running_footer | 284 | 1.2% |
| publication_metadata | 231 | 1.0% |
| abstract_prose | 152 | 0.6% |
| heading_fragment | 75 | 0.3% |
| keyword_line | 60 | 0.3% |
| citation_instruction | 16 | 0.1% |

The classifier is appropriately non-load-bearing. The independent sample contains real prose in
`unknown`, publisher material in `body_prose`, figure-axis ticks in `table_cell_debris`, and
scientifically useful table material in both `unknown` and `math_or_symbol`.

## 4. Sample and Rubric

### 4.1 Sample

The universe required: live paper; available PDF attachment; canonical article-fulltext role;
attachment/checksum agreement; current H1a row; and a current chunk embedding. It contained
23,782 chunks from 107 papers and 113 attachments. All 23,782 were currently embedded.

The 180-case sample covered 76 papers:

- **Probability arm (120):** stratified by all 13 nonempty H1a classes, with at least four per
  class and remaining allocation proportional to stratum capacity. This arm supports population
  estimates.
- **Stress arm (60):** five each from 12 deterministic proxy strata: short/truncated,
  heading/body, null-section scientific, Results prose, Methods/statistical, caption/panel, simple
  table, complex table, isolated cell, significance footnote, multi-column, and multi-page table.
  These proxies deliberately over-sample hazards and are not population prevalence estimates.

Five sampled chunk IDs happened to overlap the 134 older H1a fixtures. Their old labels were not
used in adjudication.

### 4.2 Proposition-bearing rubric

A unit is proposition-bearing only when the extracted representation itself preserves enough
source-supported context to identify what a reported finding, method, or value refers to.
Grammatical sentence form is not required. A caption that states a result may qualify; a title,
axis tick, caption label without a finding, or `p = .146` does not.

Pass A exposed only shuffled opaque IDs and current chunk text. It hid chunk ID, paper,
attachment, page, class, section, geometry, neighbors, and PDF. Those ratings were committed before
context reveal.

Pass B independently recorded:

- whether current storage supports a faithful reconstruction;
- whether PDF reread supports it;
- the expected representation (authoritative source text, derived multi-region unit, linked
  context component, ambiguity, or exclusion); and
- explicit false-join hazards.

These are single-investigator research judgments. They are not production labels or verifier
gates.

## 5. Primary Measurements

### 5.1 Text-only Pass A

Across all 180 cases, 35 were proposition-bearing, 145 were not. Eighty-two visibly contained
scientific content or a scientific structural label, 48 were ambiguous unlabeled values/symbols,
and 50 were not scientific evidence as extracted.

The probability-arm, class-stratified estimate is:

| Measure | Estimated population share | Approx. 95% design interval |
|---|---:|---:|
| Standalone proposition-bearing | 15.9% | 10.1-21.8% |
| Not standalone proposition-bearing | 84.1% | 78.2-89.9% |

This is a property of the current chunk representation in this validation corpus, not a universal
PDF statistic. It also does not mean 84.1% should be dropped; many require reconstruction or serve
other task-relative roles.

### 5.2 Recovery topology

The 180-case adjudicated topology was:

| Outcome | Current storage | PDF reread |
|---|---:|---:|
| Already proposition-bearing | 35 | 35 |
| Faithfully reconstructable | 27 | 41 |
| Ambiguous, unsafe to activate | 14 | 0 |
| Context component only | 28 | 28 |
| Unresolved without semantic inference | 26 | 26 |
| Not target scientific evidence | 50 | 50 |

Probability-arm estimates (stress arm excluded) were:

| Outcome | Current storage | PDF reread |
|---|---:|---:|
| Already proposition-bearing | 15.9% | 15.9% |
| Faithfully reconstructable | 27.7% | 32.6% |
| Ambiguous, unsafe to activate | 4.9% | 0.0% |
| Context component only | 12.5% | 12.5% |
| Unresolved without semantic inference | 14.1% | 14.1% |
| Not target scientific evidence | 24.9% | 24.9% |

Approximate intervals are wide; for example, PDF-reread faithful reconstruction is 23.6-41.6%.
The useful conclusion is the topology and direction, not decimal precision.

### 5.3 Short fragments

In the eligible universe, 13,100/23,782 chunks (55.1%) contain at most 12 whitespace-delimited
words. A broader `<=30 words and no terminal punctuation` proxy marks 15,630/23,782 (65.7%). These
are intentionally overinclusive: they include headings, bibliography, tables, equations, and
figure labels. They demonstrate that short-unit handling is central, not that all short chunks are
broken prose.

Among 16 independently identified prose fragments requiring reunion, conservative same-column
geometry supported 14 faithful reconstructions from current storage. The other two required
cross-column or cross-page reasoning and were left ambiguous until PDF reread. This supports a
narrow prose-reunion prototype, not general neighbor merging.

### 5.4 Captions

Captions are 629/23,782 (2.6%) of the H1a population. In the five probability-arm caption cases,
two stated proposition-bearing scientific results and three were context-only. Treating every
caption as noise would delete evidence; treating every caption as an independent result would
detach labels from the referenced table/figure. Captions need a linked component role.

## 6. Reconstruction Experiments

### 6.1 Current-storage prose reunion

The useful current signals are page, block/line/span IDs, rectangles, and text. A conservative
prototype concept groups candidate text blocks only when they share a calibrated column, have
compatible vertical spacing, and show a strong continuation boundary (hyphen break, lowercase
continuation, or incomplete syntax). It explicitly excludes table/figure regions and preserves the
source regions separately.

This was successful in 14/16 sampled prose-fragment cases. It failed as a general rule at page and
column boundaries. Examples included:

- a sentence beginning at the bottom of a two-column page whose antecedent was on the previous
  page;
- a left-column result fragment whose continuation was emitted before it because the right-column
  block started slightly higher;
- a bottom-right block followed in emitted order by an unrelated bottom-left block; and
- a left-column paragraph continuing into the right column even though y coordinates ran upward.

### 6.2 Why emitted/chunk order is insufficient

Current IDs were monotonic with the stored `sort=True` block sequence in the audited database.
That does **not** establish semantic adjacency. A simple text-shape candidate rule identified 46
sample cases as possible continuations; only 16 actually required prose reunion. It also selected
table headers, paper titles, bibliography fragments, captions, and already complete propositions.
Within the true fragment set, cross-column/page cases demonstrate that predecessor/successor
direction can be wrong even when emitted order is internally consistent.

Therefore H3 is supported for a stronger reason than ID inversion: IDs preserve an extractor's
sorted block stream, but the stream does not encode paragraph identity, column flow, table
structure, or semantic continuity.

### 6.3 PDF hierarchy reread

All 180 sampled cases had readable original PDFs. The reread processed 161 unique pages and matched
177/180 target texts exactly to their recorded block. The remaining three differed only because
the research export's simple span concatenation omitted spaces that production's geometric
span-joining function inserts; they were not source drift.

Reread restored page dimensions, text-block bbox, per-span text, font/size/flags, explicit
block/line/span hierarchy, image block geometry, and access to adjacent pages. This resolved the 14
current-storage-ambiguous sampled cases without an LLM. It also exposed 46 positively identified
pure section headings that current chunks intentionally discard.

Reread does not solve everything. Formula layout, vector figures, panel semantics, complex tables,
and orphan chart labels remained ambiguous unless a deterministic structure parser preserved the
relationship. Proximity alone was not accepted as meaning.

### 6.4 False-reconstruction measurements

Twenty-nine of 180 sampled cases carried an observed false-join hazard:

| Hazard | Occurrences |
|---|---:|
| Wrong row/column association | 15 |
| Figure axis classified/treated as table | 7 |
| Multi-page table context | 5 |
| Cross-column neighbor | 4 |
| Cross-page continuation | 2 |
| Wrong caption/table semantics | 1 |
| Wrong table caption | 1 |
| Body prose merely near a table | 1 |
| Two side-by-side tables | 1 |
| Multiple nearby captions | 1 |
| Duplicate interaction label | 1 |
| Emitted-order reversal | 1 |
| Figure panel label treated as table | 1 |
| Multiple nearby tables | 1 |

Cases can have multiple hazards, so counts exceed 29. These are stress opportunities, not corpus
prevalence. They establish that false reconstruction is common enough to require an explicit
failure state and provenance audit.

## 7. Table-Specific Recoverability

### 7.1 H1a table-cell candidates

H1a marks 2,674/23,782 chunks (11.2%) as `table_cell_debris`. Its geometry rule was never validated
as a table parser and remains non-load-bearing.

In the 11-case probability sample from this class:

- 4 were genuine scientific table values;
- 5 were figure/equation ticks or symbols;
- 2 were publication/reference material;
- 0/11 were proposition-bearing alone;
- 4/4 genuine values lacked their row/column/caption referent;
- 0/4 were safe to activate from the tested current-storage association alone;
- 4/4 were manually recoverable after deterministic PDF reread.

The separate stress sample contained ten more H1a `table_cell_debris` cases: six genuine table
values and four figure/reference fragments. All six genuine values again required external
row/column context.

The probability estimate that 36.4% of this H1a class represents useful true table values is based
on only 11 cases and must not be generalized precisely. The robust result is qualitative: the
class contains both valuable stranded evidence and substantial non-table debris.

### 7.2 PyMuPDF table finder

Across 161 sample pages, `page.find_tables()` proposed 80 table regions on 40 pages. Twenty-seven
sample targets intersected a proposed region. Independent PDF review classified 17 intersections
as true table material and 10 as false table detections, including body prose, a copyright block,
figures, axis ticks, an equation matrix, and an experimental choice diagram.

Of the 17 true table intersections, only five yielded a directly usable row/column hierarchy
without repair. Several ruled scientific tables were extracted as 13-18 sparse columns containing
large compound cells; an unruled regression table collapsed into a 2x2 container with almost all
content in one cell; and a bilateral neuroanatomical table expanded into 21 columns. Conversely,
eight independently identified data-bearing table cases were not detected at all.

This supports using deterministic table detection as a candidate-region signal with quality
checks and abstention. It rejects treating the parser output as ground truth.

### 7.3 Simple versus complex tables

Simple tables with explicit rules, one header hierarchy, stable row baselines, and no spanning
continuation were often recoverable after reread. Complex failures involved:

- multiple header tiers and merged cells;
- repeated `p`, `p_age`, `p_sex`, and `p_GM` lines inside one conceptual cell;
- bilateral or side-by-side sub-tables;
- multi-page continuation without repeated caption/header;
- captions below rather than above the table;
- significance markers whose definitions live in a footnote;
- unruled tables; and
- values whose visual placement is encoded by text spans rather than a real PDF table object.

H4 and H5 are supported: a table cell generally needs explicit structural context, and current
geometry sometimes contains enough clues, but reliable reconstruction requires richer ingestion
metadata plus abstention.

## 8. Figure Feasibility

No plot was interpreted and no value was estimated from a chart. The feasibility check found:

- 56/161 sample pages contained at least one raster image block;
- 360 raster image blocks were visible to PyMuPDF on those pages;
- 43,837 vector drawing groups were returned, illustrating why raw vector count is too noisy to be
  a figure detector;
- captions and some panel labels are extractable as text;
- current ingestion discards non-text block geometry, so it cannot link captions to raster image
  bounds from stored DB state alone.

Future ingestion can preserve image/figure candidate bounds, captions, panel labels, extracted
axis/legend text, and neighboring prose with provenance. Scientific plot interpretation remains a
separate research track.

## 9. Hypothesis Results

| Hypothesis | Result | Independent evidence |
|---|---|---|
| H1: useful chunks are often not standalone propositions | **Supported** | 15.9% estimated standalone rate; many additional reconstructable/context cases. |
| H2: some prose can be faithfully reunited from current geometry | **Supported** | 14/16 sampled prose-fragment cases conservatively recoverable from current storage. |
| H3: ID/emitted order is insufficient for safe general merging | **Supported** | 46 text-shape candidates but only 16 true reunion cases; column/page direction failures. |
| H4: table cells need structural context | **Supported** | Every genuine sampled H1a table-cell value lacked a standalone referent. |
| H5: some table relationships are recoverable, many need richer metadata | **Supported** | PDF reread recovered sampled true values, but table detection had false regions, misses, and malformed grids. |
| H6: deterministic ingestion metadata can recover evidence without an LLM | **Supported, bounded** | 14 additional cases resolved by page/block/span/table reread; unresolved cases retained. |
| H7: referent recovery, not chunk count/similarity, is the scientific metric | **Supported by protocol** | Ratings required explicit referents and false-join review; no retrieval result was allowed to validate reconstruction. |

## 10. Minimal Evidence-Unit Model

The minimum design should preserve four distinct layers rather than overwriting `chunks`:

```text
source_document
  -> source_page
      -> source_component (block / line / span / image / table candidate)
          -> derived_evidence_unit (zero or more components, ordered)
              -> retrieval_surface
```

### 10.1 Source document/page

Required identity:

- attachment ID and immutable attachment checksum;
- extractor name/version and representation schema version;
- page number, width, height, rotation, and coordinate system.

### 10.2 Source component

Required fields:

- stable component ID scoped to attachment checksum/extraction version;
- component kind (`text_block`, `line`, `span`, `image_candidate`, `table_candidate`, etc.);
- raw extractor order and geometrically sorted order, separately;
- parent/child hierarchy;
- bbox;
- exact per-span text plus normalized display/retrieval variants kept separately;
- font name, size, flags, and writing direction where exposed;
- pure headings retained as components;
- parser confidence/reason codes that never imply eligibility by themselves.

### 10.3 Derived evidence unit

A derived unit may reference multiple ordered source regions. It needs:

- reconstruction strategy/version;
- ordered component references and roles (body, heading context, table caption, row header,
  column header, value, footnote);
- an explicit abstained/ambiguous state;
- reconstruction diagnostics and confidence calibrated by layout class;
- authoritative source surfaces preserved unchanged;
- derived retrieval text that is never represented as one contiguous verbatim quotation.

### 10.4 Quote/provenance behavior

If an evidence unit joins three regions, its provenance must expose three regions. A quote request
must return either the exact contiguous source region selected by the user/model or a structured
multi-region citation. The derived contextual rendering can say, for example, `Table 6 > mI > PCC
> DKEFS > p = .761`, but it must not pretend that string appeared contiguously in the PDF.

Verification should validate each source component against the attachment checksum/extraction
version and validate the reconstruction recipe separately. Meaning is not established merely by
text concatenation.

## 11. Ingestion Fields: Necessary, Useful, or Noisy

| Field | Assessment | Reason |
|---|---|---|
| Page width/height/rotation | Necessary | Normalized columns, margins, tables, figures, and cross-page flow. |
| Text-block bbox | Necessary | Block region and overlap; union-of-spans is insufficient for omitted/empty components. |
| Raw and sorted block order | Necessary | Preserve extractor evidence while avoiding one implicit reading order. |
| Line/span hierarchy and order | Necessary | Rebuild exact text and associate values with visual positions. |
| Per-span text | Necessary | Current multi-value block text cannot be mapped reliably back to span rectangles. |
| Pure heading blocks | Necessary | Current extraction positively discards them; section context is otherwise lossy. |
| Font name/size/flags | Useful, bounded | Heading/caption/header evidence; never sufficient alone. |
| Raster image bbox | Useful | Figure/caption/panel structural linkage. |
| Vector drawing groups | Noisy raw signal | 43,837 groups on 161 pages; requires grouping and validation. |
| Candidate table cells/edges | Useful, optional | Helps propose grids but current detector is neither complete nor precise. |
| Character-level glyph geometry | Defer | Potential formula/OCR value but much larger and not justified by this increment. |

## 12. Implementation-Readiness Matrix

| Capability | Classification | Rationale |
|---|---|---|
| Page dimension preservation | READY TO IMPLEMENT | Deterministic, already available at ingest, required for normalization. |
| Block bbox preservation | READY TO IMPLEMENT | Deterministic and small. |
| Per-span text preservation | READY TO IMPLEMENT | Required to map content to geometry. |
| Explicit raw/sorted order preservation | READY TO IMPLEMENT | Prevents one extractor order becoming implicit truth. |
| Heading preservation | READY TO IMPLEMENT | Forty-six skipped headings independently observed on sample pages. |
| Prose reconstruction | LIMITED PROTOTYPE ONLY | Strong 14/16 same-column signal; page/column hazards remain. |
| Heading/body context units | LIMITED PROTOTYPE ONLY | Useful, but heading scope/column association needs evaluation. |
| Table-region detection | LIMITED PROTOTYPE ONLY | Useful candidate signal; false detections and misses prohibit activation. |
| Caption/table association | RESEARCH FURTHER | Caption direction, side-by-side objects, and multi-page scope vary. |
| Row/column/value reconstruction | RESEARCH FURTHER | Only 5/17 detected real tables had directly usable hierarchy. |
| Table footnotes | RESEARCH FURTHER | Marker scope and repeated symbols are ambiguous. |
| Multi-page tables | RESEARCH FURTHER | Continuation identity/header inheritance not explicit. |
| Evidence-unit persistence | LIMITED PROTOTYPE ONLY | Schema can be designed now; semantics should stay non-load-bearing. |
| Evidence-unit retrieval | RESEARCH FURTHER | Correctness must precede re-embedding/ranking experiments. |
| Derived-unit verification/provenance | LIMITED PROTOTYPE ONLY | Multi-region provenance model is clear; verifier/UI behavior needs fixtures. |
| Figure structural metadata | LIMITED PROTOTYPE ONLY | Raster bounds/captions feasible; vector grouping remains noisy. |
| Figure quantitative interpretation | REJECT (this track) | Not tested; would require separate scientific/vision validation. |
| General adjacent-chunk merging | REJECT | Order and proximity do not establish semantic relation. |

## 13. Smallest Justified Next Increment

Implement **H1b: source-component preservation, still non-load-bearing**:

1. Add a versioned sibling representation for pages and extracted components.
2. At ingestion, persist page dimensions/rotation, raw and sorted block order, block bbox,
   line/span hierarchy, per-span text, font/style signals, pure headings, and non-text image bounds.
3. Bind every component to attachment checksum, extractor/version, and deterministic derivation
   version.
4. Keep current `chunks`, embeddings, retrieval, prompts, verifiers, and quote behavior unchanged.
5. Provide an ignored inspection/backfill tool and privacy-safe aggregate receipt.
6. Promote the 16 prose-fragment cases, representative multi-column/page hazards, the 21 sampled
   H1a table-cell cases, table-parser false positives/misses, and multi-region quote cases into a
   frozen reconstruction fixture set.
7. Prototype only conservative same-column prose reunion against those fixtures. Require zero
   harmful joins in the safety set before considering any load-bearing experiment.

This increment creates the substrate needed to test propositions without prematurely deciding how
retrieval should use them. Table reconstruction should follow as a separate limited prototype, not
be bundled with prose reunion.

## 14. Implications for Earlier Model Findings

The evidence-unit problem is a plausible contributor to Ask failures because some retrieval units
do not preserve proposition-level referents before generation begins. It does **not** explain away
model behavior. A generator can still make an unsupported claim from a perfectly adequate source
unit, and this study made no model calls.

The architecture now supports a sequenced interpretation:

1. improve deterministic evidence preservation;
2. verify reconstructed-unit fidelity independently of retrieval/model performance;
3. only then rerun representation/model interaction experiments;
4. leave model capacity, query planning, prompts, thresholds, and provider routing as separate
   maintainer decisions.

No production decision follows automatically from this report.

## 15. Limits

- One investigator performed the 180-case adjudication.
- The corpus is one 107-paper validation library and is not representative of all scholarly PDFs.
- H1a strata are observational and imprecise; stress tags are proxies, not truth.
- Approximate design intervals account for stratified finite sampling, not adjudicator uncertainty.
- PDF reread used the locally installed PyMuPDF 1.27.2.3; other versions may differ.
- Rendered-page review was targeted at difficult table/column cases, not all 180 pages.
- `find_tables()` results were audited as candidate structures, not treated as authority.
- The study did not evaluate OCR, scanned PDFs, mathematical semantics, plot interpretation,
  re-embedding, retrieval quality, or downstream generation.
- "Recoverable" means the sampled source relationship could be recovered faithfully with the
  specified deterministic information; it does not mean a production-general algorithm already
  exists.

## 16. Validation

- Isolated worktree remained rooted at increment 577; unrelated worktree changes untouched.
- SQLite integrity checks passed for pristine and study snapshots.
- H1a migration/backfill completed on the explicit study DB and reran idempotently.
- Chunk text and all embedding/vector-store digests remained unchanged.
- Sample generation reproduced all four frozen sample hashes.
- Pass-A ratings were committed before metadata/context/PDF reveal.
- All 180 sampled PDFs were readable; 177 exact target-block matches plus three explained
  span-spacing matches.
- `tests/test_chunk_structure.py`, `tests/test_chunk_filtering.py`, and
  `tests/test_pdf_processing.py`: **52 passed**.
- Research harness: Ruff format/check clean and Python compilation clean.
- `git diff --check`: clean.
- Tracked-artifact secret scan: no credential pattern found.
- No model/provider/API process was launched.
- No optional retrieval probe was run.

## 17. Independent Decision

**H1a is valid as a non-load-bearing observability baseline. General chunk merging and load-bearing
table reconstruction are not ready. Source-component preservation is ready to implement as the
smallest next, still non-load-bearing increment; conservative prose reconstruction is ready only as
a limited prototype.**

These observations, interpretations, and recommendations are frozen independently before any
post-hoc comparison with the parallel agent.

## 18. Post-Hoc Comparison With Claude Code

This section was written only after the independent findings above had been frozen in commit
`7e0f9489219dd512dab021baf591643ac60d611c`. The compared report was the then-untracked
`.claude/docs/research/2026-09-05_proposition-preserving-evidence-units.md` in the primary
worktree, SHA-256
`81871e8c1d5d994c819da9c4848c3a219f5db4361a3f932a1234a94a740bf891`. Its scratch reread
summary had SHA-256
`1f6ccfb147f18d1a0db7b8928e8aa32501104dd54a9951eefd1b3230f1cae667`. Neither source was
opened before the independent freeze. Nothing in Sections 1-17 was rescored or revised after
comparison.

### Comparison of major findings

| Finding | Classification | Comparison |
|---|---|---|
| H1a is a valid non-load-bearing observability baseline; raw chunk text remains authoritative | AGREEMENT | Both code/database audits found additive metadata rather than rewritten chunks, embeddings, or retrieval behavior. |
| Current chunks frequently fail to preserve proposition-level meaning | AGREEMENT | Both studies found that a majority of current units are not safely usable as standalone propositions, despite different estimators and rubrics. |
| Standalone proposition-bearing prevalence | PARTIAL AGREEMENT | This study's blinded, stratified probability-arm estimate is 15.94% (approximate design interval 10.14-21.75%). Claude's deterministic full-corpus proxy reports 22.3%. Both support the same qualitative conclusion, but the proxy and human-coded estimand are not interchangeable. |
| Conservative prose reunion can recover some true fragmentation | PARTIAL AGREEMENT | This study recovered 14/16 independently identified true prose fragments. Claude's general candidate generator produced only 12 correct joins among 44 proposals, with 26 false joins. Together these results locate the hard problem at safe candidate identification: known true fragments are often geometrically recoverable, but broad automatic proposal generation is not yet precise enough. |
| General neighbor/chunk-id merging is unsafe | AGREEMENT | Both studies measured substantial false-join/order hazards and reject deployment. Claude additionally quantified median stored/native order disagreement at 0.267 and found that chunk-id adjacency matched the native successor only 65.6% of the time. |
| Pure headings are discarded and heading scope should be preserved | AGREEMENT | Both rereads independently observed source headings absent from stored chunks and recommend additive preservation rather than synthetic inference. |
| Tables require caption, row, column, and footnote context rather than isolated cells | AGREEMENT | Both studies reject cell proximity as semantic proof and reject load-bearing table reconstruction now. |
| Default `page.find_tables()` yield | NOT COMPARABLE | Claude found 2 tables on 105 pages from 8 PDFs; this study found 80 proposed tables on 161 pages spanning 76 papers, with 17 true and 10 false proposals intersecting sampled targets. Both used PyMuPDF 1.27.2.3 and the default call. The PDF/page populations differ radically, so neither count falsifies the other. A frozen identical-page rerun is required. |
| PyMuPDF table detection is production-ready | AGREEMENT | Despite different raw yields, both manual audits conclude it is not: this study observed false positives, misses, and only 5/17 true detections with directly usable hierarchy; Claude observed near-total misses under the default strategy and catastrophic prose-as-table behavior under the text strategy. |
| Richer deterministic PDF structure should be retained at ingestion | AGREEMENT | Both recommend page dimensions, geometry, and explicit source/native order while keeping current retrieval unchanged. |
| Minimum H1b field set | PARTIAL AGREEMENT | Claude favors a smaller floor of page dimensions, block bbox, native order, guarded boilerplate evidence, and existing GROBID descriptions. This study additionally recommends line/span hierarchy, per-span text/style, raw and sorted order, headings, and image bounds because sampled table/context reconstruction needed component-level text-to-geometry mappings. This is an implementation-scope decision for the maintainer, not an empirical conflict about whether the current representation is insufficient. |
| Reconstructed units need explicit multi-region provenance | AGREEMENT | Both distinguish contiguous verbatim source from assembled evidence and prohibit presenting a derived multi-region unit as one contiguous quote. |
| Figure interpretation belongs outside this increment | AGREEMENT | Both limit this track to structural metadata/caption association and make no scientific interpretation of plots. |
| Retrieval or model changes should wait | AGREEMENT | Both favor fixing and validating the evidence substrate before retrieval, prompt, planner, or model-capacity experiments. |

### Findings unique to either investigation

**CODEX-ONLY:** blinded text-only Pass A before geometry/PDF reveal; a 180-case stratified
design-based estimate; all-PDF context audit across 76 papers; the estimate that PDF reread raises
faithful standalone recovery from 27.73% to 32.60%; the probability-sample finding that 4/11 H1a
`table_cell` cases were true scientific values and all four lacked standalone referents; and the
target-intersection manual audit of default table candidates.

**CLAUDE-ONLY:** full-corpus deterministic proxy classification; quantitative native-versus-stored
reading-order discordance; the broad bounded-neighbor candidate-generator audit; guarded
digit-masked repeated-header/footer detection; detailed inspection of the existing GROBID and
`document_tables.py` pathways; and a counterfactual residual false-reconstruction estimate after
H1a hygiene filtering.

These are complementary observations, not replications of identical estimands.

### Unresolved disagreement and discriminating experiment

The only conspicuous numeric divergence is default table-detection yield. The compared scratch
receipt shows Claude's 105 pages came from only 8 attachments, while this study's 161 distinct
pages were selected through a 180-case sample across 76 papers. The next table-methodology check
should therefore freeze one list of attachment checksums and page numbers, one PyMuPDF build, and
the exact `find_tables()` arguments; run both harnesses on those same bytes; and compare hashed
per-page table bboxes, row counts, headers, exceptions, and rendered-page adjudication. If outputs
still differ, the harnesses—not corpus composition—are the target of diagnosis.

This discrepancy does not change the independent decision: neither observed behavior supports
load-bearing table reconstruction.

### Post-hoc synthesis

The strongest joint conclusion is narrower than either a general re-chunker or a table parser:
preserve deterministic source components and provenance first, keep them non-load-bearing, and
evaluate reconstruction methods against false-join fixtures before changing retrieval. The two
studies independently disfavor adjacent-chunk merging, production table reconstruction, and any
attempt to use retrieval gains as a substitute for semantic fidelity.

The sequencing choice that remains for maintainer approval is how much component detail H1b should
persist initially. A conservative decision is to retain the richer component hierarchy once per
ingestion, while exposing only the smaller page/block/order subset to the first limited prototype.
That preserves future table/heading work without making unvalidated semantics operational.
