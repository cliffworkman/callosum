# Increment 01 Notes

## Implemented

- SQLAlchemy Core schema for the persistence entities named in `docs/data-contracts.md`: Paper, Attachment, Collection, Tag, Annotation, Chunk, Embedding metadata, Axis, ClusterNode, Summary, SummarySentence, CitationMapping, and EvidenceQuote.
- Supporting SQLite tables named in `data/sqlite/README.md`: external identifiers, notes, external API cache, jobs, job errors, missing-literature suggestions, open-science signals, and processing-version records.
- Paper normalized fields plus preserved `csl_json`.
- Paper `processing_tier` values: `metadata-only`, `abstract-embedded`, `fully-chunked`.
- Citation mapping statuses: `verified`, `weak`, `contradicted`, `unverified`.
- Chunk provenance/version columns, embedding metadata/version columns, and summary/citation-mapping verified-against version columns.
- Alembic baseline migration and configuration.
- Thin data-access helpers only for Paper, Attachment, and Chunk.
- Pytest coverage for migration, Paper round-trip, DOI/Zotero identity precedence, Chunk provenance constraints, and CitationMapping version recording.

## Deferred

- Importers, PDF processing, embedding generation, sqlite-vec integration, clustering, summarization, external adapters, FastAPI routes, and frontend work are intentionally not implemented in this increment.
- Data-access helpers for entities other than Paper, Attachment, and Chunk are deferred because they are not exercised yet.
- Actual vector storage is deferred; the `embeddings` table stores metadata and a future `vector_store_ref`.

## Interpretations

- Primary keys are internal integer IDs. External IDs, DOIs, Zotero keys, citation keys, and file paths are stored as separate columns.
- JSON columns are used for CSL-JSON, provider payloads, bbox lists, scope references, and configuration because the exact normalized shapes remain future design work.
- A citation mapping row represents one sentence-to-chunk candidate; multiple chunks for one sentence can be represented as multiple mapping rows.
- The baseline migration imports the schema metadata and creates it from empty to keep the first migration aligned with the schema module.

## Deviations

- `docs/architecture.md` says sqlite-vec will eventually keep vectors inside SQLite. This increment follows the user's narrower instruction to keep vectors out for now and stores only embedding metadata plus a future vector-store reference.
