# Increment 577 — H1a: instrumented hygiene baseline

**Not the final H1 evidence substrate.** This is the first, deliberately **non-load-bearing**
hygiene increment: it ships observability, one validated bug fix, and regression protection. The
proposition-preserving evidence-unit / re-chunking research pass comes next, and needs this
increment's metadata to be empirical rather than speculative.

Authority: the FINAL VALIDATION section of
`.claude/docs/research/2026-09-04_evidence-hygiene-architecture.md`.

## Implemented

**Schema (additive, migration `0079_chunk_structure`).**
`app/backend/persistence/schema_chunk_structure.py` declares a `chunk_structure` sibling table on the
shared `schema_base.metadata`, re-exported from `schema.py` — the 0074 `paper_sections` precedent.
No column on `chunks` is added or altered, so no `op.batch_alter_table` copy-and-move was needed.
Two CHECK constraints pin the closed vocabularies; both verified rejecting an out-of-vocabulary
value on a real database.

**Classifier.** `app/backend/pdf_processing/chunk_structure.py` — `classify_paper(chunks, *,
reference_region, reference_region_source, repeated)`. Pure by construction: it opens no connection,
builds no client, makes no network call and never reads a PDF. Every test constructs inputs from
literals.

**Repository.** `app/backend/persistence/chunk_structure_repo.py` — per-paper replace,
staleness resolved against the live chunk row.

**Backfill + inspection.** `tools/backfill_chunk_structure.py` owns all I/O and hands resolved
inputs to the classifier. Cache-only (no network), per-paper commit, resumable, idempotent.
`--inspect <chunk_id>` and `--summary` are the developer audit surface; **no API endpoint, no UI**.

**The one behavior change.** `exclude_repeated_boilerplate_chunks` split into detection
(`repeated_boilerplate_keys`) and filtering. `_source_chunks_for_scope` now computes the key set
from the paper's whole article-role chunk set **before** the section filter narrows the query.

## Key technical detail

**Detection scope was fused to the candidate list.** `exclude_repeated_boilerplate_chunks` grouped
per paper but only over the list it was handed, which `pipeline.py` had already section-filtered. A
header appearing on five pages could survive into too few selected-section chunks to reach the
three-page floor — measured, `sections=['methods']` kept **112** running-head chunks that whole-paper
scope removes.

The extra SELECT runs **only when a section filter exists** (without one the candidate rows already
*are* the whole-paper pool) and fetches only `paper_id, page_start, text`. Measured after the fix:

| scope | result |
|---|---|
| no section filter (default Ask) | **identical** — no extra query, no change |
| `[introduction, discussion]` | excludes c28063 *"Structural Imaging in Late Life Depression"* |
| `[results, discussion]` | excludes c28063, c28031 |
| `[methods]` | excludes c28007, c42609 |

Every newly-excluded chunk is a genuine running head. c28063 is the fragment Qwen "verified" against
in the B0 study.

**A real bug found during implementation.** `chunks.bbox_json` is a SQLAlchemy `JSON` column, so a
DB read returns an **already-decoded list** while a fixture returns a string. Calling `json.loads()`
on the list raised `TypeError`, which the guard swallowed — silently disabling **every geometry
rule**. Symptom: 3,228 repeats detected but all filed `middle_band`, zero `running_head`, zero
`table_cell_debris`. Both parse sites now accept either form. This is exactly the failure class the
research warned about: a broad `except` converting a type error into a silent wrong answer.

## Verification

- Migration on a **fresh** DB: head `0079_chunk_structure`, both CHECK constraints enforce.
- Migration + full backfill on a **copy of the 219-paper library**: 23,782 chunks across 107 papers.
- **Raw text digest unchanged** — `878a7c1950e0f88786df9d76` before and after.
- **Embeddings unchanged** — 24,134 rows before and after.
- **Resumability** — a second run reports `107 already current`, 0 re-derived.
- Classification distribution: unknown 55.6%, table_cell_debris 11.2%, reference_entry 8.9%,
  body_prose 8.4%, math_or_symbol 6.2%, running_head 3.5%, caption 2.6%, running_footer 1.2%.
- `tools/check_line_budget.py`: all 589 application-source files under the 600-line cap.
- `ruff format` + `ruff check` clean on every touched file (scoped, never repo-wide).

## Tests

`tests/test_chunk_structure.py` (16) promotes the maintainer-adjudicated fixtures as regression
cases: F44485/F39057 (proposition-bearing captions stay scientific), F45476 (a *sentence about* a
table is prose, not a caption), F26458 (`(c)` sub-figure label is not copyright), F29836 (orphan
value is structural), F36125 (Results prose inside a reference region is vetoed back to prose), plus
the guard that **isolated short evidence is never table-cell debris** and that `unknown` is never
treated as ineligible.

`tests/test_chunk_filtering.py` (+3) pins the fused-vs-split difference directly, plus the safety
valve and exact backward compatibility when `keys` is omitted.

`tests/test_pdf_processing.py` (+2) adds the **real-locator** exact-anchor regression — never
monkeypatched — and pins the production invariant that an unrecoverable rectangle degrades
*precision* without falsifying an already-verified quote.

## Deliberately NOT implemented

No hard exclusion, no deprioritization, no caption policy, no re-chunking, no fragment merging, no
table/figure reconstruction, no normalized embeddings, no stored or model-facing normalized text, no
persisted hyphen candidate sets, no threshold changes, no adaptive top_k, no prompt engine.

**No reason code cleared the ≥95% held-out precision gate**, so nothing here may change retrieval.
The only exception is the scoped boilerplate correction, which is a defect fix in an existing
detector and does not consult the new metadata.
