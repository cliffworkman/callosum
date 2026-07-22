# Data Contracts

The authoritative schema is `app/backend/persistence/schema.py`. This document summarizes the implemented tables and payload semantics that current code depends on.

## Paper Records

`papers` is the canonical bibliographic record. `csl_json` is the preserved canonical CSL-JSON payload; scalar columns are projections used for display, filtering, deduplication, and export:

- core display/search fields: `title`, `abstract`, `year`, `doi`, `venue`, `item_type`, `language`, `publication_date`, `first_author_family_name`, `citation_key`;
- provenance and external IDs: `imported_source`, `openalex_work_id`, `semantic_scholar_paper_id`, `zotero_library_id`, `zotero_item_key`;
- lifecycle: `processing_tier`, `created_at`, `updated_at`, `deleted_at`.

`deleted_at IS NULL` means live; a timestamp means the paper is in Trash. Permanent delete removes dependent embeddings/vectors and then the trashed paper row.

## Library Metadata

- `paper_external_identifiers`: provider/id pairs for a paper.
- `attachments`: managed, linked, or URL attachments with availability, original/resolved paths, checksum, size, content type, source, attachment type, and role.
- `collections` / `collection_papers`: imported or user grouping.
- `tags` / `paper_tags`: global tag names with `tags.import_source` provenance. Backlog #9 formalized this as a
  `{namespace}:{origin}` contract (`app/backend/persistence/tags_repo.py::TAG_SOURCE_NAMESPACES`): the bare
  sentinel `user` (human-typed, the sole exception), `import:{system}` (e.g. `import:zotero`), `keyword:{system}`
  (e.g. `keyword:crossref` / `keyword:openalex` / `keyword:pubmed`), `agent:{system}` (e.g. `agent:mcp`), and
  `system:{fact}` for a findings-subsystem per-paper fact projected as a real, non-editable tag — backlog #19
  (inc 335) is the first producer, `system:retraction` (`methods/retraction.py::apply_retraction()`). A new
  producer must pick an existing namespace or add one, never write a bare/ad-hoc string.
- `notes`: imported notes attached to papers.

## PDF Text And Coordinates

`chunks` stores extracted text spans with `paper_id`, `attachment_id`, page range, optional character offsets, `bbox_json`, `bbox_coordinate_system`, extraction metadata, chunking metadata, source attachment checksum, and creation time.

Current coordinate system is `pdf-points-top-left`. Bounding boxes come from PyMuPDF text spans and are rendered by the frontend as page-relative overlay percentages. Region-level or absent coordinates must never be rendered as exact passage highlights.

## Embeddings And Axes

`embeddings` records vectors for target rows. The schema enum currently allows `paper`, `chunk`, `axis`, `summary_sentence`, and `claim`; the active MVP workflows use paper/chunk/axis embeddings. Each row records model name/version, dimension, normalization, source text version, optional source chunk version, vector store kind, and vector store reference.

`axes` stores user-defined semantic axes: `label`, optional `description`, optional per-axis `scoring_gain`, and `created_at`.

`cluster_nodes` stores axis/cluster labels with optional parent and confidence. `cluster_node_papers` links papers to nodes. A manual axis assignment is represented by `cluster_node_papers.confidence IS NULL`; scored assignments use a float in `[0, 1]`.

## Annotations

`annotations` supports imported, user-authored, and synthesis-authored annotations. Imported rows use `import_source`, `external_id`, and `position_json`; native rows use `source` (`user` or `synthesis`), `color`, `bboxes_json`, `anchor_text`, `prefix`, `suffix`, and `note`.

Synthesis highlights are allowed only for verified citations with exact coordinates.

## Summaries And Evidence

- `summaries`: scope, content/status, generator identity, chunk/embedding versions verified against, verification version, and creation time.
- `summary_sentences`: ordered sentence text per summary.
- `citation_mappings`: relationship from sentence to chunk with status `verified`, `weak`, `contradicted`, or `unverified`, plus verification versioning.
- `evidence_quotes`: verbatim quote text, page range, bbox payload, and component confidences: `retrieval_confidence`, `quote_confidence`, `support_confidence`.

Sentence-level API responses mark a sentence `flagged` when it has no citations or any citation status is not `verified`. `coordinate_precision` is derived from evidence quote bbox payloads: `exact`, `region`, or `null`.

## Caches And Jobs

- `external_api_cache`: provider/cache-key request and response cache, used by external metadata lookups such as Crossref.
- `llm_cache`: content-addressed cache for raw summary-generation outputs. Local verification still reruns after cache hits.
- `dismissed_duplicate_pairs`: canonical `(paper_id_low, paper_id_high)` pairs the user marked "not a duplicate".
- `jobs` / `job_errors`: durable job schema exists; current async API routers also use in-process `JobStore` state for summarize, axis score/suggest, and duplicate scan jobs.

## Honesty Contracts

- `coordinate_precision=exact`: draw only the stored rectangles.
- `coordinate_precision=region`: open the source page/area and say it is approximate.
- `coordinate_precision=null`: no highlight rectangle.
- Verification confidence is decomposed, not collapsed: retrieval, quote, and support scores stay visible.
- Metadata edits merge into `csl_json` and update scalar projections without wiping unedited CSL fields.
