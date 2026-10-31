# Classification version and migration (inc 611)

## Explicit invalidation

`DERIVATION_VERSION` (`app/backend/persistence/schema_chunk_structure.py`) moves from `chunk-structure-v1` to
`chunk-structure-v2`.

Every consumer already compares this string:
- `structure_role_states` marks any other version `stale`;
- `evidence_selection._anchored` maps `stale` to an eligibility state that never demotes;
- `papers_with_current_structure` treats the paper as needing derivation.

So a v1 row **cannot masquerade as current**. Its two possible fates:
- **before reclassification:** it is recorded and ignored, so retrieval behaves as on an unclassified library
  (the pre-607 behaviour) rather than repeating v1's false demotions;
- **after reclassification:** it is replaced.

No schema migration is needed:
- the version column has no CHECK constraint;
- `unknown` / `unknown` already exist as a type and role.

## Reclassification

Reclassification is the existing developer tool, `tools/backfill_chunk_structure.py`. Its properties:

| Property | How |
|---|---|
| Bounded | One paper per transaction; `--limit N`, `--paper-id` |
| Resumable | A plain re-run skips papers whose every chunk has a current v2 row; an interrupted run resumes without a cursor |
| Idempotent | A completed library re-runs as 0 papers, 0 chunks, N skipped |
| Writes | `chunk_structure` only (per-paper delete + insert); never `chunks`, `embeddings`, vector tables or settings |
| Inspectable | `--summary` now leads with derivation-version coverage: papers current, papers needing (re)derivation, rows by version |

There is **no startup job**. The app never classifies at launch or ingest. That is unchanged: classification
metadata remains opt-in, observed, and run by the operator.

## Measured on the disposable replay copy

| Step | Result |
|---|---|
| Coverage before | 0 of 151 papers current; rows `{v1: 42,044}` |
| Backfill | 42,044 chunks / 151 papers in 42 s; 18 papers without cached reference metadata |
| Re-run | 0 chunks, 0 papers, 151 already current |
| Coverage after | 151 of 151; rows `{v2: 42,044}` |
| Table fingerprints (124 tables) | Only `chunk_structure` changed; every chunk, embedding and `callosum_vec_*` shadow table identical |

## v1 → v2 transitions (907 of 42,044 rows changed)

| v1 | v2 | n |
|---|---|---|
| `unknown` `fallthrough` | `scientific` `shape.clear_prose.citations_stripped` | 874 |
| `bibliographic` `ref_region.member` | `scientific` `ref_region.prose_veto.citations_stripped` | 19 |
| `bibliographic` `ref_region.member` | `unknown` `ref_region.ambiguous.prose_fragment` | 13 |
| `bibliographic` `shape.biblio_score` | `unknown` `shape.ambiguous.mixed_prose_and_entries` | 1 |

**Bibliographic rows:** 7,586 → 7,553. No row became bibliographic.

**The 874 `unknown → scientific` rows have no retrieval effect,** since only `bibliographic` demotes. A random
sample of 30 was read: all were genuine body prose. One was a questionnaire item inside a references-labelled
section.

## Tests

`tests/test_source_role_migration.py` covers:
- v1 rows are stale and never demote;
- the backfill's resumability under interruption, its idempotence, and that it writes nothing outside
  `chunk_structure`;
- the coverage report.

## Rollout guidance

After this code lands, a library re-derives with:

```
python tools/backfill_chunk_structure.py --db-url <url>
```

Until then, 607 is a no-op for that library: safe, but not demoting genuine bibliography. Do not run it against
the installed desktop library, the historical master or a protected research snapshot without explicit approval.
