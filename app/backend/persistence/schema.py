"""SQLAlchemy Core schema for Callosum's persistence core."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)

from app.backend.persistence.schema_base import metadata

PROCESSING_TIERS = ("metadata-only", "abstract-embedded", "fully-chunked")
ATTACHMENT_STORAGE_MODES = ("managed", "linked", "url")
ATTACHMENT_AVAILABILITY = ("available", "missing", "unresolved")
CITATION_MAPPING_STATUSES = ("verified", "weak", "contradicted", "unverified")
EMBEDDING_TARGET_TYPES = ("paper", "chunk", "axis", "summary_sentence", "claim")
PROCESSING_VERSION_TYPES = (
    "extraction",
    "chunking",
    "embedding",
    "summary",
    "verification",
)
JOB_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")


def enum_check(column_name: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    quoted = ", ".join(f"'{value}'" for value in values)
    return CheckConstraint(f"{column_name} IN ({quoted})", name=name)


def non_empty_check(column_name: str, name: str) -> CheckConstraint:
    return CheckConstraint(f"length(trim({column_name})) > 0", name=name)


papers = Table(
    "papers",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("title", Text, nullable=False),
    Column("abstract", Text),
    Column("year", Integer),
    Column("doi", String(255)),
    Column("venue", Text),
    Column("item_type", String(100)),
    Column("language", String(50)),
    Column("publication_date", String(50)),
    Column("first_author_family_name", String(255)),
    Column("imported_source", String(100)),
    Column("openalex_work_id", String(255)),
    Column("semantic_scholar_paper_id", String(255)),
    Column("zotero_library_id", String(255)),
    Column("zotero_item_key", String(255)),
    Column("citation_key", String(255)),
    Column("csl_json", JSON, nullable=False),
    Column("processing_tier", String(50), nullable=False, server_default="metadata-only"),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("deleted_at", DateTime),  # NULL = live; a timestamp = soft-deleted (in Trash). inc 54.
    enum_check("processing_tier", PROCESSING_TIERS, "processing_tier_valid"),
    UniqueConstraint("doi", name="uq_papers_doi"),
    UniqueConstraint("openalex_work_id", name="uq_papers_openalex_work_id"),
    UniqueConstraint("semantic_scholar_paper_id", name="uq_papers_semantic_scholar_paper_id"),
    UniqueConstraint("zotero_library_id", "zotero_item_key", name="uq_papers_zotero_identity"),
    Index("ix_papers_title_year_author", "title", "year", "first_author_family_name"),
)

paper_external_identifiers = Table(
    "paper_external_identifiers",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("provider", String(100), nullable=False),
    Column("identifier", String(255), nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("provider", "identifier", name="uq_external_identifier_provider_identifier"),
    Index("ix_external_identifiers_paper_id", "paper_id"),
)

attachments = Table(
    "attachments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("storage_mode", String(50), nullable=False),
    Column("availability", String(50), nullable=False),
    Column("original_path", Text),
    Column("resolved_path", Text),
    Column("checksum", String(128)),
    Column("file_size", Integer),
    Column("content_type", String(255), nullable=False),
    Column("import_source", String(100)),
    Column("attachment_type", String(100)),
    Column("role", String(100)),
    # OA-acquisition labels (inc: acquisition clean lane) — set when a copy is fetched from an OA database.
    Column("oa_color", String(20)),  # gold / green / bronze (bronze = unstable; see oa_bronze_unstable)
    Column("oa_version", String(20)),  # vor / am / preprint
    Column("oa_source", String(100)),  # resolver id (e.g. "openalex")
    Column("oa_landing_page_url", Text),
    Column("oa_license", String(100)),
    Column("oa_bronze_unstable", Integer),  # 1 iff oa_color == "bronze"
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    enum_check("storage_mode", ATTACHMENT_STORAGE_MODES, "storage_mode_valid"),
    enum_check("availability", ATTACHMENT_AVAILABILITY, "availability_valid"),
    CheckConstraint("file_size IS NULL OR file_size >= 0", name="file_size_nonnegative"),
    Index("ix_attachments_paper_id", "paper_id"),
    Index("ix_attachments_checksum", "checksum"),
)

collections = Table(
    "collections",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", Text, nullable=False),
    Column("import_source", String(100)),
    Column("external_id", String(255)),
    Column("parent_id", ForeignKey("collections.id", ondelete="SET NULL")),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("import_source", "external_id", name="uq_collections_import_source_external_id"),
)

collection_papers = Table(
    "collection_papers",
    metadata,
    Column("collection_id", ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
)

tags = Table(
    "tags",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", Text, nullable=False),
    Column("import_source", String(100)),
    Column("external_id", String(255)),
    # inc 207 (A5): an optional user-chosen color, stored as a fixed-palette KEY (e.g. "blue"), never arbitrary hex
    # — the frontend maps the key to a theme-aware token. NULL = uncolored (keeps the inc-100 provenance styling).
    Column("color", String(20)),
    UniqueConstraint("name", name="uq_tags_name"),
)

paper_tags = Table(
    "paper_tags",
    metadata,
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

# Suppressed imported-keyword tags (inc 143): when the librarian deletes an imported `keyword:*` tag, remember it
# by name per paper so a later re-resolve / backfill does NOT silently re-add it. Adding a tag by that name clears
# the suppression. Names only (the tag row is pruned on delete) — the analogue of the inc-49 user-edit guard.
suppressed_paper_tags = Table(
    "suppressed_paper_tags",
    metadata,
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_name", Text, primary_key=True),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
)

# Saved searches (inc 208, A1): a named bundle of the existing library facets (q / search_field / item_type / axis /
# tag / needs_review / signal / sort), stored as a JSON `params` blob and recalled from the library header. A metadata
# predicate over the existing GET /papers filters — NOT a semantic lens (that's an axis). Local; name is UNIQUE.
saved_searches = Table(
    "saved_searches",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", Text, nullable=False),
    Column("params", JSON, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("name", name="uq_saved_searches_name"),
)

notes = Table(
    "notes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("body", Text, nullable=False),
    Column("import_source", String(100)),
    Column("external_id", String(255)),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Index("ix_notes_paper_id", "paper_id"),
)

annotations = Table(
    "annotations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("attachment_id", ForeignKey("attachments.id", ondelete="CASCADE")),
    Column("page", Integer),
    Column("annotation_type", String(100)),
    Column("body", Text),
    Column("position_json", JSON),
    Column("coordinate_system", String(100)),
    Column("import_source", String(100)),
    Column("external_id", String(255)),
    # Native (callosum-authored) annotation columns. Added in 0002 for the highlight
    # suite; nullable so imported (e.g. Zotero) rows are unaffected. `source`
    # discriminates origin ("user" now; "synthesis" in a later increment); imported
    # rows leave it NULL. Native rows carry bboxes_json (pdf-points-top-left, the
    # increment-29 overlay basis) rather than the import-shaped position_json.
    Column("color", String(50)),
    Column("bboxes_json", JSON),
    Column("anchor_text", Text),
    Column("prefix", Text),
    Column("suffix", Text),
    Column("source", String(50)),
    Column("note", Text),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column(
        "updated_at",
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    ),
    Index("ix_annotations_paper_id", "paper_id"),
    Index("ix_annotations_attachment_id", "attachment_id"),
)

processing_versions = Table(
    "processing_versions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("version_type", String(50), nullable=False),
    Column("name", String(255), nullable=False),
    Column("version", String(255), nullable=False),
    Column("config_json", JSON),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    enum_check("version_type", PROCESSING_VERSION_TYPES, "version_type_valid"),
    UniqueConstraint("version_type", "name", "version", name="uq_processing_versions_type_name_version"),
)

chunks = Table(
    "chunks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("attachment_id", ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False),
    Column("text", Text, nullable=False),
    Column("section", Text),
    Column("page_start", Integer, nullable=False),
    Column("page_end", Integer, nullable=False),
    Column("char_start", Integer),
    Column("char_end", Integer),
    Column("bbox_json", JSON),
    Column("bbox_coordinate_system", String(100), nullable=False),
    Column("extraction_tool", String(100), nullable=False),
    Column("extraction_version", String(100), nullable=False),
    Column("chunking_strategy", String(255), nullable=False),
    Column("chunk_version", String(255), nullable=False),
    Column("source_attachment_checksum", String(128), nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint("page_start >= 1", name="page_start_positive"),
    CheckConstraint("page_end >= page_start", name="page_end_after_start"),
    CheckConstraint("char_start IS NULL OR char_start >= 0", name="char_start_nonnegative"),
    CheckConstraint("char_end IS NULL OR char_start IS NULL OR char_end >= char_start", name="char_end_after_start"),
    non_empty_check("bbox_coordinate_system", "bbox_coordinate_system_non_empty"),
    non_empty_check("extraction_tool", "extraction_tool_non_empty"),
    non_empty_check("extraction_version", "extraction_version_non_empty"),
    non_empty_check("chunking_strategy", "chunking_strategy_non_empty"),
    non_empty_check("chunk_version", "chunk_version_non_empty"),
    non_empty_check("source_attachment_checksum", "source_attachment_checksum_non_empty"),
    Index("ix_chunks_paper_id", "paper_id"),
    Index("ix_chunks_attachment_id", "attachment_id"),
    Index("ix_chunks_chunk_version", "chunk_version"),
)

embeddings = Table(
    "embeddings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("target_type", String(50), nullable=False),
    Column("target_id", Integer, nullable=False),
    Column("model_name", String(255), nullable=False),
    Column("model_version", String(255), nullable=False),
    Column("dimension", Integer, nullable=False),
    Column("normalization", String(255), nullable=False),
    Column("source_text_version", String(255), nullable=False),
    Column("source_chunk_version", String(255)),
    Column("vector_store_kind", String(100)),
    Column("vector_store_ref", String(255)),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    enum_check("target_type", EMBEDDING_TARGET_TYPES, "target_type_valid"),
    CheckConstraint("dimension > 0", name="dimension_positive"),
    non_empty_check("model_name", "model_name_non_empty"),
    non_empty_check("model_version", "model_version_non_empty"),
    non_empty_check("normalization", "normalization_non_empty"),
    non_empty_check("source_text_version", "source_text_version_non_empty"),
    Index("ix_embeddings_target", "target_type", "target_id"),
    Index("ix_embeddings_model_version", "model_name", "model_version"),
)

axes = Table(
    "axes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("label", Text, nullable=False),
    Column("description", Text),
    # The assignment cutoff this axis was last scored at (assigned = similarity >= gain). NULL means
    # "use the current default" (DEFAULT_AXIS_CUTOFF). User-adjustable per re-score (inc 45).
    Column("scoring_gain", Float),
    # Axis kind (inc 78): "standard" (the default, user-defined scored axis) or "my_publications" (the special
    # pinned, OpenAlex-resolved axis of the user's own papers — variant styling + dismissable lifecycle).
    Column("kind", String(40), nullable=False, server_default="standard"),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
)

cluster_nodes = Table(
    "cluster_nodes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("axis_id", ForeignKey("axes.id", ondelete="CASCADE")),
    Column("parent_id", ForeignKey("cluster_nodes.id", ondelete="CASCADE")),
    Column("label", Text, nullable=False),
    Column("description", Text),
    Column("confidence", Float),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="confidence_0_1"),
)

cluster_node_papers = Table(
    "cluster_node_papers",
    metadata,
    Column("cluster_node_id", ForeignKey("cluster_nodes.id", ondelete="CASCADE"), primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
    Column("confidence", Float),
    CheckConstraint(
        "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="cluster_assignment_confidence_0_1"
    ),
)

summaries = Table(
    "summaries",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("scope_type", String(100), nullable=False),
    Column("scope_ref_json", JSON),
    Column("content", Text),
    Column("overview_json", JSON),  # inc 124: per-sentence traceable Overview [{text, claim_ordinals:[int]}]
    Column("generated_by", String(255)),
    Column("chunk_version_verified_against", String(255), nullable=False),
    Column("embedding_version_verified_against", String(255), nullable=False),
    Column("verification_version", String(255)),
    Column("status", String(100), nullable=False, server_default="created"),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    non_empty_check("chunk_version_verified_against", "summary_chunk_version_non_empty"),
    non_empty_check("embedding_version_verified_against", "summary_embedding_version_non_empty"),
)

summary_sentences = Table(
    "summary_sentences",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("summary_id", ForeignKey("summaries.id", ondelete="CASCADE"), nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("summary_id", "ordinal", name="uq_summary_sentences_summary_ordinal"),
    CheckConstraint("ordinal >= 0", name="summary_sentence_ordinal_nonnegative"),
)

citation_mappings = Table(
    "citation_mappings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("summary_sentence_id", ForeignKey("summary_sentences.id", ondelete="CASCADE"), nullable=False),
    Column("chunk_id", ForeignKey("chunks.id", ondelete="SET NULL")),
    Column("status", String(50), nullable=False),
    Column("chunk_version_verified_against", String(255), nullable=False),
    Column("embedding_version_verified_against", String(255), nullable=False),
    Column("verification_version", String(255)),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    enum_check("status", CITATION_MAPPING_STATUSES, "status_valid"),
    non_empty_check("chunk_version_verified_against", "mapping_chunk_version_non_empty"),
    non_empty_check("embedding_version_verified_against", "mapping_embedding_version_non_empty"),
    Index("ix_citation_mappings_sentence_id", "summary_sentence_id"),
    Index("ix_citation_mappings_chunk_id", "chunk_id"),
)

evidence_quotes = Table(
    "evidence_quotes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("citation_mapping_id", ForeignKey("citation_mappings.id", ondelete="CASCADE"), nullable=False),
    Column("chunk_id", ForeignKey("chunks.id", ondelete="SET NULL")),
    Column("quote_text", Text, nullable=False),
    Column("page_start", Integer),
    Column("page_end", Integer),
    Column("bbox_json", JSON),
    Column("retrieval_confidence", Float, nullable=False),
    Column("quote_confidence", Float, nullable=False),
    Column("support_confidence", Float, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint("retrieval_confidence >= 0 AND retrieval_confidence <= 1", name="retrieval_confidence_0_1"),
    CheckConstraint("quote_confidence >= 0 AND quote_confidence <= 1", name="quote_confidence_0_1"),
    CheckConstraint("support_confidence >= 0 AND support_confidence <= 1", name="support_confidence_0_1"),
    CheckConstraint(
        "page_end IS NULL OR page_start IS NULL OR page_end >= page_start", name="evidence_page_end_after_start"
    ),
    Index("ix_evidence_quotes_mapping_id", "citation_mapping_id"),
)

external_api_cache = Table(
    "external_api_cache",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("provider", String(100), nullable=False),
    Column("cache_key", String(255), nullable=False),
    Column("request_json", JSON),
    Column("response_json", JSON),
    Column("status_code", Integer),
    Column("fetched_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("expires_at", DateTime),
    UniqueConstraint("provider", "cache_key", name="uq_external_api_cache_provider_cache_key"),
)

# Content-addressed cache for token-expensive LLM generation (inc 61). The key is a content hash of
# EVERYTHING that determines the output (model + prompt-version + normalized inputs), so any change to an
# input changes ``input_hash`` and misses automatically — no explicit invalidation. ``namespace`` separates
# call sites (e.g. "summary"). ``signature`` is the human-readable model/prompt identity (debugging). The
# cached value is the raw generation output ONLY; the local citation-verification step still runs on every
# result (it costs no tokens), so a hit never serves stale verification.
llm_cache = Table(
    "llm_cache",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("namespace", String(50), nullable=False),
    Column("input_hash", String(64), nullable=False),
    Column("signature", String(255), nullable=False),
    Column("output_json", JSON, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    non_empty_check("namespace", "namespace_non_empty"),
    non_empty_check("input_hash", "input_hash_non_empty"),
    UniqueConstraint("namespace", "input_hash", name="uq_llm_cache_namespace_input_hash"),
)

# Pairs the user marked "not a duplicate" (inc 64): the duplicate-detection scan drops these pairs before
# its union-find, so a dismissed pair never re-flags as a duplicate group. Canonical (low < high) so a pair
# is stored once; CASCADE so a (future) hard-delete cleans its dismissals.
dismissed_duplicate_pairs = Table(
    "dismissed_duplicate_pairs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id_low", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("paper_id_high", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint("paper_id_low < paper_id_high", name="canonical_pair_order"),
    UniqueConstraint("paper_id_low", "paper_id_high", name="uq_dismissed_duplicate_pairs_low_high"),
)

# The wanted list (inc 76): papers the user wants an open-access copy of. A row is either library-linked
# (``paper_id`` set — a PDF-less library paper to fill) or external (``paper_id`` NULL — a paper not yet
# imported, carrying its own doi/pmid/title). The OA re-check runs the resolver cascade over open rows and
# auto-acquires hits. ``status``: wanted | fulfilled. ``last_result`` is a short code (e.g. gold/vor, none,
# needs-id, error:…).
wanted_items = Table(
    "wanted_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE")),  # NULL = an external (not-yet-owned) want
    Column("doi", String(255)),
    Column("pmid", String(100)),
    Column("title", Text),
    Column("note", Text),
    Column("status", String(20), nullable=False, server_default="wanted"),
    Column("last_checked_at", DateTime),
    Column("last_result", String(100)),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Index("ix_wanted_items_paper_id", "paper_id"),
    Index("ix_wanted_items_status", "status"),
)

# The researcher's identity for My Publications (inc 78). Single-row, single-user-local (NB: per-user/session
# visibility is a later multi-user concern — not built now). ``openalex_author_id`` is cached after resolution;
# ``my_publications_dismissed`` = the deleted-the-card-don't-auto-regenerate flag.
profile = Table(
    "profile",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("display_name", Text),
    Column("name_variants", JSON),  # list of additional published-name strings
    Column("orcid", String(64)),
    Column("openalex_author_id", String(64)),
    Column("my_publications_dismissed", Integer, nullable=False, server_default="0"),
    Column("research_summary", Text),  # inc 81: the dashboard's editable, AI-generated research summary
    Column("research_domains", JSON),  # inc 83: the dashboard's domain decomposition [{label, terms, paper_ids}]
    Column("starred_paper_ids", JSON),  # inc 84: starred key publications (paper ids) — scope the AI summary
    Column("dismissed_work_dois", JSON),  # inc 85: OpenAlex works the user rejected from the missing-works queue
    Column("dismissed_gap_works", JSON),  # inc 135: gap-finder candidates the user dismissed (OA ids + DOIs)
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
)

# Confirm/reject decisions for My Publications candidates (inc 78). Survives re-matching: a "rejected" paper is
# never re-proposed; a "confirmed" paper stays a member. One row per paper.
my_publication_decisions = Table(
    "my_publication_decisions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("decision", String(20), nullable=False),  # "confirmed" | "rejected"
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("paper_id", name="uq_my_publication_decisions_paper_id"),
)

jobs = Table(
    "jobs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("job_type", String(100), nullable=False),
    Column("status", String(50), nullable=False),
    Column("input_json", JSON),
    Column("output_json", JSON),
    Column("progress_json", JSON),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("started_at", DateTime),
    Column("finished_at", DateTime),
    enum_check("status", JOB_STATUSES, "job_status_valid"),
)

job_errors = Table(
    "job_errors",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("job_id", ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column("message", Text, nullable=False),
    Column("details_json", JSON),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Index("ix_job_errors_job_id", "job_id"),
)

missing_literature_suggestions = Table(
    "missing_literature_suggestions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("candidate_title", Text, nullable=False),
    Column("candidate_year", Integer),
    Column("doi", String(255)),
    Column("openalex_work_id", String(255)),
    Column("semantic_scholar_paper_id", String(255)),
    Column("reason", Text, nullable=False),
    Column("reason_json", JSON),
    Column("score", Float),
    Column("status", String(100), nullable=False, server_default="new"),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint("score IS NULL OR (score >= 0 AND score <= 1)", name="missing_lit_score_0_1"),
)

# Watched library folders (inc 98): folders callosum re-scans to pick up new PDFs (Zotero/Mendeley-style).
# Scanning a folder registers it here; auto-rescan-on-launch + a manual "Re-scan all" reconcile them.
watched_folders = Table(
    "watched_folders",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("path", Text, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("last_scanned_at", DateTime),
    UniqueConstraint("path", name="uq_watched_folders_path"),
)

# Findings / open-science-signals / retraction-mirror / gap-finder tables live in schema_findings (split out to
# keep this file under the 600-line cap, rule #1). Re-exported here so existing
# ``from app.backend.persistence.schema import paper_findings`` imports keep working, and so importing this module
# registers those tables on the shared ``metadata`` (0001's ``metadata.create_all`` then includes them).
# Literature Feed tables (inc 187) — same split rationale; re-exported so existing import paths keep working and
# importing this module registers them on the shared metadata.
from app.backend.persistence.schema_feed import (  # noqa: E402,F401
    feed_items,
    feed_subscriptions,
)
from app.backend.persistence.schema_findings import (  # noqa: E402,F401
    gap_candidates,
    open_science_signals,
    paper_citation_counts,
    paper_findings,
    retraction_records,
)

# Sync bookkeeping tables (accounts SP3a/SP3b) — same split rationale; local-only change-tracking + identity + conflicts.
from app.backend.persistence.schema_sync import (  # noqa: E402,F401
    sync_conflicts,
    sync_identity,
    sync_state,
)
