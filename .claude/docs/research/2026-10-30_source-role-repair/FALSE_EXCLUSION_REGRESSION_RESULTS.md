# False-exclusion regression results (inc 611)

## Automated tests (serial, focused, local, no models downloaded or invoked)

| File | Tests | What it proves |
|---|---|---|
| `tests/test_source_role_repair.py` (new) | 56 | Pure assessment and classifier on synthetic paraphrases of each failure shape. **Kept:** cited conclusion, orphan citation tail, superscript-cited prose, null result, limitation, qualification. **Ambiguous:** split sentence tail; prose then entries. **Kept as references:** APA, consecutive entries, scientific-sounding title, title-then-Vancouver source, cross-page entry start, numbered Vancouver, DOI-only fragment, title fragment. Anchored and shape-only references stay `reference_entry`; captions are not promoted; the new veto catches cases whose `biblio_score ≥ 1.5`; publisher notices are not rescued; the rescue memo never serves a stale decision |
| `tests/test_source_role_migration.py` (new) | 4 | v1 rows are stale and never demote. The backfill is interrupt/resume-safe and idempotent, and writes nothing outside `chunk_structure` (chunks, embeddings and papers byte-identical). **Ask integration**, whole-library and selected-papers, under MiniLM and an Arctic-shaped profile: cited and mislabelled prose reach the pool; the heading-labelled genuine entry stays excluded; the anchored genuine entry is demoted last; slots ≤ 8 (3 under the selected-papers budget), with demotion promoting prose into the slots; vector count unchanged; the incomplete Arctic index still fails closed with no embedding |
| `tests/test_reference_exclusion.py` | 4 (1 new) | GROBID preference and NULL-kept semantics unchanged. New: a rescued conclusion returns in chunk-id order on the first and the memoized pass; a genuine entry stays out |

**Fixture policy.** The fixtures are paraphrases written for the tests; no library text was copied.

**Known cases.** 5399, 56894, 56618, 58052 and 67832 are represented by shape, never by id. A source-wide grep
confirms no app code names them.

**Mutation check.** I disabled both repairs: classifier assessment forced to `not_prose`, rescue forced off.
11 of the new tests then failed: every cited-prose, ambiguity and rescue assertion, the backfill reclassification
test and the Ask integration test. So the suite detects the defect.

**Existing-test conflict.** `tests/test_reference_exclusion.py` called the removed `exclude_reference_sections`
wrapper directly, so its helper now calls `reference_filtered_rows`. No assertion changed: fixture text `"body"`
is not prose, so every references-labelled fixture is still excluded. No frozen assertion encoded the misleading
behaviour, so none needed replacing.

**Combined focused run:** 227 passed, covering:
- the files above;
- `test_chunk_structure`, `test_reference_eligibility_selection`, `test_evidence_eligibility`,
  `test_backfill_doi_owners`;
- `test_ask_integration_607_608`, `test_faceted_synthesis`, `test_document_scope`, `test_summaries`;
- `test_embedding_profiles`, `test_source_components`, `test_nli_profiles`, `test_sql_batch`.

`test_frontend_assembly` cannot run in this worktree: there is no `node_modules`, so esbuild is absent. No
frontend file changed.

## Library-scale safety inspection (replay copy, in-sample)

**Classification.**

| Population | n | Inspection |
|---|---|---|
| v1 `bibliographic` → v2 `scientific` | 19 | All 19 read in full: every one is Discussion, conclusion or limitation prose with in-text citations (includes 5399, 56894, 58043, 58052, 67832) |
| v1 `bibliographic` → v2 `unknown` (fragment) | 13 | 1 split sentence tail (56618), 1 equation-definition sentence, 1 Discussion tail, 10 declarations or data statements. None is a reference entry |
| v1 `bibliographic` → v2 `unknown` (mixed) | 1 | A Methods paragraph with an author-year citation |
| v1 `bibliographic` → still `bibliographic` | 7,553 | Unchanged |

**Rule errors found and fixed while reading population samples.** These were shape errors, not tuning to
adjudicated outcomes:
1. `Surname, I. (Year)` entry starts were stripped as citations and looked like prose.
2. `1(3/4)` issue ranges escaped the volume(issue) test.
3. A single title-like sentence followed by a source line was read as mixed.

Before the fixes, 1 reference entry (a title-plus-source chunk) was "substantive" and 12 were "mixed". After the
fixes, none are.

**Heading-filter rescue.**

| Bucket | n |
|---|---|
| `references`-labelled | 13,404 |
| Rescued | 236: substantive 188, fragment 47, mixed 1 |
| Excluded publisher/licence notices that read as prose | 117 |
| Rescued chunks carrying a v2 `bibliographic` label | **0** (the two mechanisms agree) |

Reading samples of rescued chunks found conclusions, limitations, Methods tails, supplementary-table captions,
questionnaire items, author biographies and a book preface. None was a reference entry. The last three are
non-scientific prose; see the contract's known limitations.

## What this does not establish

All of the above is **in-sample**. The rules were written after looking at these failures, and the population
was inspected on the same library. Whether the rules generalise needs a held-out, source-verified evaluation.
