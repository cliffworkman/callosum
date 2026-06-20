# Glossary

## Core Records

- Paper: the local canonical scholarly-work record. `papers.csl_json` is the preserved CSL-JSON source of bibliographic truth; scalar columns are projections.
- Attachment: a managed, linked, or URL file reference associated with a paper, usually a PDF.
- Chunk: extracted PDF text span with page range, versioning, checksum, and `pdf-points-top-left` bbox provenance.
- Annotation: imported, user-authored, or synthesis-authored note/highlight. Native rows use the `source` discriminator.
- Tag: user/imported label stored globally in `tags` and linked to papers through `paper_tags`.
- Evidence quote: verbatim source text stored for a citation mapping, with page/bbox and component confidence scores.
- Citation mapping: stored link from a summary sentence to a chunk/evidence quote with verification status.

## Verification Terms

- Verified: a citation clears retrieval, quote, and support thresholds.
- Weak: a citation is related or partly supportive but does not clear all verification thresholds.
- Contradicted: storage status for evidence that conflicts with the sentence. Current UI treats it as flagged.
- Unverified: no adequate source support was found.
- Flagged: sentence-level UI state when a sentence has no citations or any citation is not verified.
- Contrasted: product vocabulary for evidence read against a claim rather than accepted as support; implemented storage uses `contradicted` where the conflict is explicit.
- Retrieval confidence: embedding similarity signal between the sentence and cited chunk.
- Quote confidence: whether the candidate quote is found in the cited chunk/source.
- Support confidence: local NLI/entailment-style support score.

## Coordinates

- Coordinate system: current bbox space is `pdf-points-top-left`.
- `coordinate_precision=exact`: precise rectangles can be drawn and saved as synthesis highlights.
- `coordinate_precision=region`: approximate source region; open/scroll but do not draw exact quote rectangles.
- `coordinate_precision=null`: no reliable coordinates; draw nothing.

## Organization Terms

- Axis: user-defined semantic organizing dimension with a display label, description/terms, and optional scoring cutoff.
- Cluster node: axis/cluster node that can contain paper assignments.
- Manual override: axis-paper assignment with `cluster_node_papers.confidence IS NULL`; it survives re-score.
- Uncertain: scored axis assignment below the assigned cutoff but still reviewable in the UI.
- Suggested axis: locally clustered candidate axis from coverage/diversity logic, optionally polished by egress-gated Gemini.

## Local-First And Egress

- Local-first: extraction, embeddings, retrieval, clustering, verification, duplicate detection, and tag suggestion run on the user's machine.
- Egress gate: explicit consent boundary in `app/backend/llm/egress.py`; library text cannot be sent to Gemini unless enabled.
- BYO-key: future/public-user model where the user supplies their own provider key; today keys come from environment variables.
- LLM cache: content-addressed cache of raw generation outputs; local verification still reruns.

## Library Management

- Trash: soft-delete state where `papers.deleted_at` is set.
- Permanent delete: trashed-only deletion that removes app records, embeddings, and vector rows; it does not delete user PDF files.
- Dismissed duplicate pair: canonical paper-id pair stored in `dismissed_duplicate_pairs` so duplicate scan no longer flags it.
- Import source: provenance field used for records/tags/attachments/notes/annotations, such as `zotero`, `user`, or `keyword:crossref`.

## Future-Track Vocabulary

- Findings subsystem: planned FACT-vs-candidate infrastructure for retractions, statcheck, transparency, and other inspectable signals.
- System-facts tags: planned read-only/filterable facts such as `system:retraction` or transparency signals, visually distinct from user tags.
- THEORY/METHODS panes: planned module-registry UI for inspectable literature-analysis modules.
