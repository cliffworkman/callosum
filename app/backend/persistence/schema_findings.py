"""Findings / open-science-signals / retraction-mirror / gap-finder tables.

Split out of ``schema.py`` (inc 137) to keep it under the 600-line cap (rule #1). Imports the shared
``metadata`` from ``schema_base`` — NOT from ``schema`` — so there is no circular import; ``schema.py``
re-exports these names, so ``from app.backend.persistence.schema import paper_findings`` keeps working.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
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

open_science_signals = Table(
    "open_science_signals",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("signal_type", String(100), nullable=False),
    Column("status", String(100), nullable=False),
    Column("evidence_snippet", Text),
    Column("evidence_url", Text),
    Column("confidence", Float),
    Column("source", String(100)),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="open_science_confidence_0_1"),
    Index("ix_open_science_signals_paper_id", "paper_id"),
    UniqueConstraint("paper_id", "signal_type", "source", name="uq_open_science_signal_paper_type_source"),
)

# Findings subsystem (inc 130): the shared FACT-vs-CANDIDATE store every METHODS check emits into. A FACT is an
# established truth (review_state NULL — not resolvable); a CANDIDATE is reviewable. content_key gives idempotency
# (re-runs preserve reviews on unchanged findings). State lives here, not localStorage.
paper_findings = Table(
    "paper_findings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("source", String(100), nullable=False),  # the producing check
    Column("kind", String(20), nullable=False),  # 'fact' | 'candidate'
    Column("tier", String(20)),  # 'primary' | 'speculative' | NULL
    Column("payload", JSON, nullable=False),
    Column("content_key", String(64), nullable=False),  # sha256(source + canonical payload) — idempotency
    Column("review_state", String(20)),  # 'unreviewed'|'confirmed'|'accepted'|'noted' | NULL (facts)
    Column("review_reason", Text),
    Column("reviewed_at", DateTime),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("paper_id", "source", "content_key", name="uq_paper_findings_paper_source_key"),
    Index("ix_paper_findings_paper_id", "paper_id"),
)

# A local mirror of the Retraction Watch Database (Crossref-hosted, CC0), refreshed on demand (inc 132). One row
# per RW notice; the producer matches a paper's DOI here offline. Replace-all on refresh (the DB is authoritative).
retraction_records = Table(
    "retraction_records",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("original_doi", String(255), nullable=False),  # the retracted paper's DOI (normalized lower) — match key
    Column("status", String(20), nullable=False),  # retracted | correction | concern
    Column("nature", String(100)),  # the raw RW nature label (display)
    Column("date", String(40)),
    Column("reason", Text),
    Column("notice_doi", String(255)),
    Column("notice_url", Text),
    Column("retrieved_at", String(40), nullable=False),  # when this snapshot was downloaded
    Index("ix_retraction_records_original_doi", "original_doi"),
)

# TOP Factor local mirror (backlog #40 -- Center for Open Science's per-journal transparency/openness rubric).
# A periodic bulk CSV snapshot (no query API exists), downloaded on demand like retraction_records above.
# categories_json carries the 9-10 named category sub-scores + justifications so `total` (COS's own defined sum)
# is never shown without its inspectable basis (Principles #7 -- no opaque scores). issn/eissn are both nullable
# -- some COS rows carry only one or the other.
top_factor_records = Table(
    "top_factor_records",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("issn", String(20)),
    Column("eissn", String(20)),
    Column("journal", Text),
    Column("categories_json", JSON, nullable=False),  # [{"name","score","max","justification"}, ...]
    Column("total", Integer, nullable=False),
    Column("retrieved_at", String(40), nullable=False),
    Index("ix_top_factor_records_issn", "issn"),
    Index("ix_top_factor_records_eissn", "eissn"),
)

# AJOL (African Journals Online) local mirror (backlog #40, inc 451) -- a third-party CC-BY-4.0 compiled snapshot
# (Alonso-Álvarez 2025, Zenodo DOI 10.5281/zenodo.14899380), NOT AJOL's own official feed. jpps_status is AJOL's
# own official "Journal Publishing Practices and Standards" rating (the real CSV column is the typo'd
# jjps_status -- stored here under the correct term). is_diamond is nullable: a malformed cell parses to unknown,
# never fabricated False. source_url is validated (rule #4) to actually start with https://www.ajol.info/ before
# storage. retrieved_at is the LOCAL download timestamp -- distinct from the data's own fixed February-2024
# vintage (a Zenodo record is immutable; see integrations/ajol/adapter.py's AJOL_SNAPSHOT_DATE).
ajol_records = Table(
    "ajol_records",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("issn", String(20)),
    Column("eissn", String(20)),
    Column("journal", Text),
    Column("country", String(80)),
    Column("jpps_status", String(40)),
    Column("is_diamond", Boolean),
    Column("source_url", Text),
    Column("retrieved_at", String(40), nullable=False),
    Index("ix_ajol_records_issn", "issn"),
    Index("ix_ajol_records_eissn", "eissn"),
)

# Gap-finder persistent cache (inc 137): one row per cached candidate, scoped by (direction, axis_id). A refresh
# replaces all rows for a scope; GET /gaps reads here and filters dismissed / now-in-library at read time.
# axis_id is a plain scope tag (no FK) — NULL means the whole library; a stale row for a deleted axis is simply
# never read (the axis won't appear in the dropdown).
gap_candidates = Table(
    "gap_candidates",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("direction", String(20), nullable=False),  # 'backward' | 'forward'
    Column("axis_id", Integer),  # NULL = whole library
    Column("openalex_work_id", String(40), nullable=False),
    Column("doi", String(255)),
    Column("title", Text),
    Column("authors", JSON),
    Column("year", Integer),
    Column("cited_by_in_library", Integer, nullable=False),
    Column("computed_at", String(40), nullable=False),
    Index("ix_gap_candidates_scope", "direction", "axis_id"),
)

# Followed-authors gap-finder source (backlog #29, inc 454): a lightweight OpenAlex-author subscription list.
# Sibling to gap_candidates, not a new column on it -- gap_candidates/GapCandidate have no room for author
# provenance and no per-author refresh scope. last_refreshed_at is set by the refresh job regardless of candidate
# count, so "this author has nothing absent" (common, expected) is distinguishable from "never refreshed" --
# mirrors feed_subscriptions.last_polled_at, the closest existing subscription precedent.
followed_authors = Table(
    "followed_authors",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("author_id", String(20), nullable=False),  # bare OpenAlex id, e.g. "A5023888391"
    Column("display_name", Text, nullable=False),
    Column("orcid", String(64)),
    Column("matched_by", String(10), nullable=False),  # "orcid" | "name" | "direct"
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("last_refreshed_at", String(40)),  # NULL = never refreshed
    UniqueConstraint("author_id", name="uq_followed_authors_author_id"),
)

# The derived candidate cache for followed_authors: one row per (author, absent work), replaced per-author on
# refresh. cited_by_count is the WORK's own OpenAlex citation count -- semantically different from
# gap_candidates.cited_by_in_library (which counts the user's own library citing it) -- never conflate in the UI.
followed_author_candidates = Table(
    "followed_author_candidates",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("author_id", String(20), nullable=False),
    Column("author_display_name", Text),  # snapshot at compute time so provenance needs no join
    Column("openalex_work_id", String(40)),
    Column("doi", String(255)),
    Column("title", Text),
    Column("year", Integer),
    Column("cited_by_count", Integer, nullable=False, server_default="0"),
    Column("computed_at", String(40), nullable=False),
    Index("ix_followed_author_candidates_author", "author_id"),
)

# My Publications Layer-4 grounded prospection (incs 386/389): bounded, explicit-refresh snapshots keyed by an
# all-publications or server-validated domain scope. Candidates retain the exact shared references + confirmed
# own-publication rows that caused them to surface. One row per scope keeps a genuine empty result distinguishable
# from "never computed" and makes replacement atomic.
my_publication_citation_gap_cache = Table(
    "my_publication_citation_gap_cache",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("scope_key", String(80), nullable=False),
    Column("scope", JSON, nullable=False),
    Column("candidates", JSON, nullable=False),
    Column("coverage", JSON, nullable=False),
    Column("computed_at", String(40), nullable=False),
    UniqueConstraint("scope_key", name="uq_my_publication_citation_gap_scope_key"),
)

# My Publications Layer-4 emerging citing topics (inc 390): the same bounded server-validated domain scopes,
# with each topic carrying the two visible window counts and the exact citing/own-publication evidence behind
# them. One row per scope distinguishes a computed empty signal from an uncomputed scope.
my_publication_emerging_topic_cache = Table(
    "my_publication_emerging_topic_cache",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("scope_key", String(80), nullable=False),
    Column("scope", JSON, nullable=False),
    Column("topics", JSON, nullable=False),
    Column("coverage", JSON, nullable=False),
    Column("computed_at", String(40), nullable=False),
    UniqueConstraint("scope_key", name="uq_my_publication_emerging_topic_scope_key"),
)

# My Publications Layer-4 citing-author evidence (inc 391): bounded, explicit-refresh snapshots with stable
# OpenAlex author ids, visible counts, and exact citing-work/own-publication evidence. The coauthor exclusion is
# coverage-qualified and computed from the same bounded own-work set.
my_publication_citing_author_cache = Table(
    "my_publication_citing_author_cache",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("scope_key", String(80), nullable=False),
    Column("scope", JSON, nullable=False),
    Column("authors", JSON, nullable=False),
    Column("coverage", JSON, nullable=False),
    Column("computed_at", String(40), nullable=False),
    UniqueConstraint("scope_key", name="uq_my_publication_citing_author_scope_key"),
)

# Overlooked-work lens persistent cache (backlog #37): one row per surfaced candidate, scoped by axis_id. A refresh
# replaces all rows for an axis; GET /overlooked reads here. Identity-agnostic by construction — there is NO author
# column (the lens measures the work's attention-vs-relevance, never who wrote it). `relevance` and `year_percentile`
# are the two SEPARATE visible inputs (never fused into one score); `year_percentile` is NULL when a year had too few
# same-vintage peers to rank (silence-not-a-certificate). axis_id is a plain scope tag (no FK) — a stale row for a
# deleted axis is simply never read.
overlooked_candidates = Table(
    "overlooked_candidates",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("axis_id", Integer, nullable=False),
    Column("openalex_work_id", String(40), nullable=False),
    Column("doi", String(255)),
    Column("title", Text),
    Column("year", Integer),
    Column("cited_by_count", Integer, nullable=False),
    Column("relevance", Float, nullable=False),  # axis cosine similarity (local); a checkable input, not a verdict
    Column("year_percentile", Float),  # citations vs. same-vintage peers; NULL = too few peers to rank
    Column("computed_at", String(40), nullable=False),
    Index("ix_overlooked_candidates_axis", "axis_id"),
)

# Per-paper OpenAlex cited-by count (inc 210, A2): a refreshable external metric, stored OUT of the canonical
# `papers` row (like every other derived datum — open_science_signals, gap_candidates). One row per paper,
# replaced by the on-demand batch. `retrieved_at` IS the "as of <date>" attribution. A displayed FACT shown
# verbatim + attributed — never folded into a composite or used to silently rank (Principles #2/#7).
paper_citation_counts = Table(
    "paper_citation_counts",
    metadata,
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
    Column("cited_by_count", Integer, nullable=False),
    Column("source", String(40), nullable=False),
    Column("retrieved_at", DateTime, nullable=False, server_default=func.current_timestamp()),
)

# Per-paper cached statcheck result (inc 400): the METHODS "Statistics" per-paper check used to recompute live on
# every panel open; this caches the exact itemized result (results_json/coverage_json are the verbatim
# StatcheckResult/StatcheckCoverage payloads, INCLUDING bbox_json/coordinate_precision) so a cached redisplay is
# byte-identical to a fresh run -- the coordinate honesty contract (invariant #2) must survive the round-trip
# exactly. content_fingerprint is compared at read time to produce a passive "may be stale" hint; it never gates
# or blocks display (silence is not a certificate, but neither is a stale flag a verdict). One row per paper,
# OR-REPLACEd by a rescan.
paper_statcheck_cache = Table(
    "paper_statcheck_cache",
    metadata,
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
    Column("checked", Integer, nullable=False),
    Column("inconsistent", Integer, nullable=False),
    Column("decision_errors", Integer, nullable=False),
    Column("results_json", JSON, nullable=False),
    Column("coverage_json", JSON, nullable=False),
    Column("content_fingerprint", String(64), nullable=False),
    Column("computed_at", DateTime, nullable=False, server_default=func.current_timestamp()),
)

# B1 SP2 (agent writes): the audit log of every MCP-agent write — action + target + enough detail to undo,
# backing the Settings "AI agent activity" review + one-click revert (migration 0029, additive/guarded). NOT a
# FK to papers — the audit history outlives a purged paper. `detail_json` carries the args + created/affected ids.
agent_writes = Table(
    "agent_writes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("action", String(20), nullable=False),  # 'tag' | 'axis' | 'reference' | 'note'
    Column("target_paper_id", Integer),
    Column("tool", String(40)),
    Column("detail_json", JSON, nullable=False),
    Column("reverted_at", DateTime),
    Index("ix_agent_writes_created", "created_at"),
)
