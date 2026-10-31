# Evidence false exclusions: root causes (inc 611)

**Date:** 2026-10-30. **Branch:** `integrate/inc607-608-ask`, built on inc 610 `9d9417f9`.

**Evidence status.** The cases below come from the four-condition pilot
(`C:\Users\cliff\callosum-data\experiments\retrieval-4cond-20261030\`). Blinded AI reviewers adjudicated them, and
nobody verified them against the sources, so they are **development evidence**. They show the defects exist.
They do not estimate how often the defects occur, and they cannot validate the repair.

All tracing used the protected classified snapshot opened read-only
(`C:\Users\cliff\callosum-data\experiments\reference-backfill-20261030\classified.sqlite`).

## Two independent mechanisms

### 1. Inc 607 demotion: the prose veto rejected cited prose

`chunk_structure.classify_paper` labels every chunk inside an inferred reference region `REFERENCE_ENTRY` /
`bibliographic` (`ref_region.member`), unless `_is_clear_prose` vetoes it.

The veto requires `biblio_score < 1.5`. But `biblio_score` deliberately rewards citation apparatus:

| Feature | Score |
|---|---|
| `et al.` | 0.8 |
| up to three years | up to 1.0 |
| page range | 0.8 |

A Discussion paragraph citing its literature normally carries exactly this apparatus, so it fails the veto even
though everything else about it is prose.

| Chunk | biblio_score | words | Other veto conditions | v1 label |
|---|---|---|---|---|
| 5399 | 1.8 | ≥20 | all pass | `ref_region.member` |
| 56894 | 1.8 | ≥20 | all pass (chunk begins mid-citation: "al., 2004; …") | `ref_region.member` |
| 58052 | 1.8 | ≥20 | all pass | `ref_region.member` |
| 58043 | 2.6 | ≥20 | all pass | `ref_region.member` |
| 67832 | 1.6 | ≥20 | all pass (Vancouver superscripts flattened into text) | `ref_region.member` |
| 56618 | 0.0 | 15 | fails the 20-word floor (a sentence tail split off by chunking) | `ref_region.member` |

**Why these chunks sat inside a region at all.** `infer_reference_region` takes the densest cluster of
title/DOI matches in chunk-id order. It then spans from the first match to the last. Mixed final pages and
two-column layouts interleave Discussion and conclusion prose with the bibliography in extraction order, so the
span sweeps that prose in. Region membership is real structural evidence, but it cannot establish a chunk's
identity on its own. The original veto already acknowledged this; its score cap was the defect.

### 2. Older heading filter: the section label was treated as proof

`pipeline.exclude_reference_sections` dropped every chunk whose
`coalesce(paper_sections.section_kind, chunks.section) = 'references'`. This happened in SQL, before boilerplate
detection, vector retrieval and 607.

The ingest section tracker labels everything after a "References" heading as `references`, including headings it
misread as one. Measured on the 251-paper library:

- 13,404 chunks carry the label;
- 236 of them demonstrably are not a reference list (see the regression results).

58052 and 67832 carry `section = references`, so in whole-library scope they were removed before 607 ever ran.
Selected-papers scope never applied this filter, by design.

58043 is labelled `conflict_of_interest`. It was affected only by mechanism 1.

## Why the two mechanisms needed separate repairs

They read different signals:

| Mechanism | Signal | Persistence | Consumer |
|---|---|---|---|
| Inc 607 demotion | Persisted `chunk_structure` rows (geometry + anchored region + text shape) | The backfill | Narrow Ask, after ranking |
| Heading filter | The live `section` label | None | Whole-library and faceted candidate building, before ranking |

Repairing either one alone would have left the other dropping 58052.
